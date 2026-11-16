"""Compatibility URLs resolve signed canonical references and account-link nonces."""
from django.core import signing
from django.db import transaction
from django.utils.crypto import salted_hmac

from .models_contract import NotificationDelivery
from .models_endpoints import ChannelConfiguration, NotificationEndpointChallenge
from .notification_providers import CallbackEvent, EndpointProof
from .notification_wa_meta_reference import SALT


def referenced_row(receipt, data):
    value = data.get("client_reference", "")
    if receipt.provider != "meta" or not isinstance(value, str) or not 0 < len(value) <= 512:
        return None, False
    try:
        config_id, generation, delivery_id, attempt = signing.loads(value, salt=SALT)
    except (signing.BadSignature, ValueError, TypeError):
        return None, False
    if any(type(v) is not int or v < 1 or v > 9223372036854775807 for v in [config_id, generation, delivery_id, attempt]):
        return None, False
    rows = NotificationDelivery.objects.filter(pk=delivery_id, channel=receipt.channel,
        provider=receipt.provider, sender_key=receipt.sender_key, integration_generation=generation)
    if receipt.makerspace_reference:
        rows = rows.filter(makerspace_id=receipt.makerspace_reference)
    row = rows.first()
    if row is None:
        return None, False
    # The signed reference names the endpoint's original installation, including
    # after endpoint revocation. A different installation cannot borrow its row.
    if row.endpoint_id and row.endpoint.configuration_id != config_id:
        return None, False
    return (row if row.attempt_count == attempt else None), row.attempt_count > attempt


def inbound(receipt, data):
    if receipt.channel != "whatsapp" or receipt.provider != "meta" or not data.get("destination"):
        return receipt.protection_applied
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    from .notification_wa_window import inbound_time
    configs = ChannelConfiguration.objects.filter(channel="whatsapp", provider="meta", sender_key=receipt.sender_key)
    if receipt.makerspace_reference:
        configs = configs.filter(makerspace_id=receipt.makerspace_reference)
    number, code = data["destination"], data.get("proof_code", "")
    moment = inbound_time(data.get("timestamp"))
    # Sender-level STOP protection already committed in ingress protect(), outside
    # any tenant gate. Per-tenant endpoint effects skip a frozen tenant; the receipt
    # then stays held in the journal so recovery applies that tenant part later.
    counts = {"skipped": 0}
    for config in configs.order_by("makerspace_id"):
        with fanout_tenant_write(config.makerspace_id, operation="notification_legacy_inbound",
                                 counts=counts) as permitted:
            if not permitted:
                continue
            _apply_inbound(receipt, data, config, number, code, moment)
    return receipt.protection_applied and not counts["skipped"]


def _apply_inbound(receipt, data, config, number, code, moment):
    from .notification_proofs import apply_verified_event, digest
    from .notification_whatsapp_consent import proof_receipt
    from .notification_callback_times import provider_time
    from .notification_destination_events import live_destination
    from rest_framework.exceptions import ValidationError
    identity = salted_hmac("notification.endpoint.identity.v1",
        f"{config.pk}:{config.generation}:{number}", algorithm="sha256").hexdigest()
    proof = None
    if code and NotificationEndpointChallenge.objects.filter(configuration=config,
            integration_generation=config.generation, code_digest=digest(code)).exists():
        proof = EndpointProof(code, number, config.integration_identity, number, private=True)
    with transaction.atomic(), proof_receipt(receipt.received_at):
        try:
            apply_verified_event(config, CallbackEvent(identity_digest=identity,
                opt_out=bool(data.get("stop")), proof=proof),
                decision_at=provider_time(data.get("timestamp")) or receipt.received_at)
        except ValidationError:
            # An expired nonce is a rejected proof, never a reason to replay it.
            return
        if moment and not data.get("stop"):
            live_destination(config, identity).filter(last_inbound_at__isnull=True).update(last_inbound_at=moment)
            live_destination(config, identity).filter(last_inbound_at__lt=moment).update(last_inbound_at=moment)
