"""Replay authenticated facts only into exact canonical installation/mapping targets."""
from dataclasses import replace
from types import SimpleNamespace

from django.utils import timezone

from .models_contract import NotificationDelivery
from .models_endpoints import ChannelConfiguration
from .notification_providers import CallbackEvent, EndpointProof


def apply(receipt, data):
    if receipt.transport == "legacy":
        return legacy(receipt, data)
    config = ChannelConfiguration.objects.filter(pk=receipt.configuration_id).first()
    if config is None:
        # Purge/module removal cannot resurrect endpoint authority. Durable STOP
        # has already committed; terminal facts can still settle surviving rows.
        values = data.get("event", {})
        from apps.makerspaces.models import Makerspace
        tenant = Makerspace.objects.filter(pk=receipt.makerspace_reference).first()
        if tenant is not None and values.get("state") and not values.get("proof"):
            from .notification_delivery import apply_callback
            previous = SimpleNamespace(makerspace=tenant, channel=receipt.channel,
                provider=receipt.provider, generation=receipt.generation,
                integration_identity=receipt.integration_identity, sender_key=receipt.sender_key)
            from apps.tenant_migration.gate_runtime import tenant_write
            with tenant_write(tenant.pk):
                apply_callback(previous, CallbackEvent(**values), observation=data.get("protection"))
        return receipt.protection_applied
    # A retired verifier proves its old generation, never the new configuration.
    config.generation, config.integration_identity = receipt.generation, receipt.integration_identity
    config.provider, config.sender_key = receipt.provider, receipt.sender_key
    values = dict(data["event"])
    if values.get("proof"):
        values["proof"] = EndpointProof(**values["proof"])
    event = CallbackEvent(**values)
    if data.get("inbound_at"):
        event = replace(event, inbound=False)
    from .notification_proofs import apply_verified_event
    from .notification_delivery import apply_callback
    from apps.tenant_migration.gate_runtime import tenant_write
    with tenant_write(config.makerspace_id):
        if event.state == "failed":
            apply_callback(config, replace(event, state="accepted"))
        try:
            from .notification_whatsapp_consent import proof_receipt
            with proof_receipt(receipt.received_at):
                result = apply_verified_event(config, event)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError
            if event.proof and isinstance(exc, ValidationError):
                return True  # Authenticated but invalid/expired proof; never create authority.
            raise
        if event.state:
            apply_callback(config, event, observation=data.get("protection"))
        if event.state == "retrying" and data.get("extra"):
            from .notification_wa_meta_ingress import _retry_failure
            result = _retry_failure(config, data["extra"], event)
        if data.get("inbound_at") and not event.opt_out:
            from django.utils.dateparse import parse_datetime
            from .notification_destination_events import live_destination
            moment = parse_datetime(data["inbound_at"])
            if moment:
                live_destination(config, event.identity_digest).filter(
                    last_inbound_at__isnull=True).update(last_inbound_at=moment)
                live_destination(config, event.identity_digest).filter(
                    last_inbound_at__lt=moment).update(last_inbound_at=moment)
        if event.state:
            rows = NotificationDelivery.objects.filter(makerspace_id=receipt.makerspace_id,
                channel=receipt.channel, provider=receipt.provider, integration_generation=receipt.generation,
                integration_identity=receipt.integration_identity, provider_id=event.provider_id)
            if event.delivery_id and event.delivery_attempt is not None:
                stale = NotificationDelivery.objects.filter(pk=event.delivery_id, makerspace_id=receipt.makerspace_id,
                    channel=receipt.channel, provider=receipt.provider, integration_generation=receipt.generation,
                    integration_identity=receipt.integration_identity, attempt_count__gt=event.delivery_attempt)
                if stale.exists():
                    return True
            return rows.exists()  # A duplicate terminal observation is successfully replayed.
        return bool(result or not event.proof)


def legacy(receipt, data):
    from .models_messaging_delivery import MessagingDelivery
    from .notification_ingress import mapped_delivery
    from .notification_delivery import apply_callback
    if data["kind"] == "inbound":
        from .notification_legacy_ingress import inbound
        return inbound(receipt, data)
    from .notification_legacy_ingress import referenced_row
    referenced, stale = referenced_row(receipt, data)
    if stale:
        return True
    canonical = NotificationDelivery.objects.filter(channel=receipt.channel, provider=receipt.provider,
        sender_key=receipt.sender_key, provider_id=data.get("message_id") or "__missing__")
    if receipt.makerspace_reference:
        canonical = canonical.filter(makerspace_id=receipt.makerspace_reference)
    matches = [referenced] if referenced else list(canonical[:2])
    if len(matches) > 1:
        return False
    rows = MessagingDelivery.objects.filter(channel=receipt.channel, provider=receipt.provider,
        sender_key=receipt.sender_key)
    if receipt.makerspace_reference:
        rows = rows.filter(makerspace_id=receipt.makerspace_reference)
    old = rows.filter(provider_message_id=data.get("message_id") or "__missing__").first()
    opaque = str(data.get("delivery_id", ""))
    if old is None and receipt.provider == "meta" and opaque.isascii() and opaque.isdigit() and len(opaque) <= 19:
        old = rows.filter(pk=int(opaque)).first()
    delivery = matches[0] if matches else mapped_delivery(old.pk) if old else None
    if delivery is None:
        from .models_cutover import NotificationProviderReference
        references = NotificationProviderReference.objects.filter(provider=receipt.provider,
            sender_key=receipt.sender_key, provider_id=data.get("message_id"), ambiguous=False)
        if receipt.makerspace_reference:
            references = references.filter(makerspace_reference=receipt.makerspace_reference)
        reference = references.first()
        if reference:
            delivery = NotificationDelivery.objects.filter(pk=reference.delivery_reference).first()
            if delivery is None:
                return receipt.protection_applied  # Retired target; facts remain in the journal.
    if delivery is None or delivery.sender_key != receipt.sender_key or delivery.provider != receipt.provider:
        return False
    if delivery.provider_id and delivery.provider_id != data.get("message_id"):
        return False
    config = SimpleNamespace(makerspace=delivery.makerspace, channel=delivery.channel, provider=delivery.provider,
        generation=delivery.integration_generation, integration_identity=delivery.integration_identity, sender_key=delivery.sender_key)
    from apps.tenant_migration.gate_runtime import tenant_write
    with tenant_write(delivery.makerspace_id):
        if not delivery.provider_id:
            NotificationDelivery.objects.filter(pk=delivery.pk).update(provider_id=data["message_id"])
            delivery.provider_id = data["message_id"]
        if receipt.provider == "meta" and not delivery.historical:
            from .notification_wa_meta_http import error_result
            code = data.get("error_code", "")
            if isinstance(code, str) and code.isascii() and code.isdigit() and error_result(400, {"error": {"code": int(code)}}).retryable:
                from .notification_wa_meta_ingress import _retry_failure
                event = CallbackEvent(provider_id=data["message_id"], state="retrying",
                    delivery_id=delivery.pk, delivery_attempt=delivery.attempt_count)
                apply_callback(config, event, observation=data)
                _retry_failure(config, {"id": data["message_id"], "errors": [{"code": int(code)}]}, event)
                return True
        apply_callback(config, CallbackEvent(provider_id=data["message_id"], delivery_id=delivery.pk,
            state={"queued": "accepted", "sending": "accepted", "undelivered": "failed"}.get(data.get("status"), data.get("status", ""))),
            observation=data)
        if data.get("billed_segments") is not None:
            NotificationDelivery.objects.filter(pk=delivery.pk).update(billed_segments=data["billed_segments"])
    return True
