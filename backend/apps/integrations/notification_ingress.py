"""Signature verifiers feed this durable journal; acknowledgements follow its commit."""
import hashlib
import json
import logging
from dataclasses import asdict
from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from .models_cutover import NotificationIngress, NotificationLegacyMapping
from .notification_cutover import boundary, state, guarded

logger = logging.getLogger(__name__)


def accept(*, transport, channel, provider, sender_key, identity, payload,
           makerspace_id=None, configuration=None, credential_version=0, signed_user_id=None):
    """Only call after provider authentication; dedupe includes installation identity."""
    generation = configuration.generation if configuration else 0
    key = hashlib.sha256(json.dumps([transport, provider, channel, sender_key,
        getattr(configuration, "pk", None), generation, identity], sort_keys=True).encode()).hexdigest()
    candidate = NotificationIngress(transport=transport, channel=channel, provider=provider,
        sender_key=sender_key, makerspace_id=makerspace_id,
        generation=generation, credential_version=credential_version,
        signed_user_id=signed_user_id,
        integration_identity=configuration.integration_identity if configuration else "", dedupe_key=key)
    from .models_endpoints import ChannelConfiguration
    from apps.makerspaces.models import Makerspace
    candidate.configuration_reference = configuration.pk if configuration else None
    candidate.makerspace_reference = makerspace_id
    candidate.configuration_id = configuration.pk if configuration and ChannelConfiguration.objects.filter(pk=configuration.pk).exists() else None
    candidate.makerspace_id = makerspace_id if Makerspace.objects.filter(pk=makerspace_id).exists() else None
    candidate.set_payload(payload)
    with boundary(), transaction.atomic():
        receipt, created = NotificationIngress.objects.get_or_create(dedupe_key=key, defaults={
            field.name: getattr(candidate, field.attname) for field in candidate._meta.fields
            if field.name not in {"id", "dedupe_key", "received_at", "configuration", "makerspace", "signed_user"}
        } | {"configuration_id": candidate.configuration_id, "makerspace_id": candidate.makerspace_id,
             "signed_user_id": candidate.signed_user_id})
        # Protection and receipt commit together. Failure cannot acknowledge STOP.
        protect(receipt)
        if created:
            from apps.audit.services import record
            record(None, "notification.webhook_received", makerspace=receipt.makerspace, target=receipt,
                meta={"channel": channel, "provider": provider})
    # Replay errors never erase the committed receipt. STOP failure above propagates.
    try:
        process(receipt.pk)
    except Exception as exc:
        logger.warning("notification_ingress_deferred", extra={"receipt_id": receipt.pk, "failure_type": type(exc).__name__})
    return receipt


def accept_legacy(**values):
    payload = {**values["payload"], "kind": values["kind"]}
    signed_user_id = None
    if payload.get("proof_code"):
        from .models_endpoints import NotificationEndpointChallenge
        from .notification_proofs import digest
        from .notification_sender import configuration_sender_key
        challenge = NotificationEndpointChallenge.objects.select_related("configuration").filter(
            code_digest=digest(payload["proof_code"])).first()
        if challenge:
            signed_user_id = challenge.user_id
            payload["proof_user_id"] = signed_user_id
            try:
                matching_sender = configuration_sender_key(challenge.configuration) == values["sender_key"]
            except Exception:
                matching_sender = False
            if matching_sender and values.get("makerspace_id") is None:
                values["makerspace_id"] = challenge.makerspace_id
    identity = {"id": values["dedupe_id"], "payload": {key: value for key, value in payload.items()
        if key not in {"protection_applied", "client_reference", "destination", "proof_code", "correlation_missing", "proof_user_id"}}}
    return accept(transport="legacy", channel=values["channel"], provider=values["provider"],
        sender_key=values["sender_key"], makerspace_id=values.get("makerspace_id"),
        credential_version=values.get("credential_version", 0), identity=identity, payload=payload,
        signed_user_id=signed_user_id)


def accept_callback(config, event, *, identity, protection=None, inbound_at=None, extra=None):
    from .notification_sender import configuration_sender_key
    from .models_endpoints import NotificationEndpointChallenge
    from .notification_proofs import digest
    proof_user_id = (NotificationEndpointChallenge.objects.filter(configuration_id=config.pk,
        integration_generation=config.generation, code_digest=digest(event.proof.code))
        .values_list("user_id", flat=True).first()) if event.proof else None
    return accept(transport="canonical", channel=config.channel, provider=config.provider,
        sender_key=configuration_sender_key(config), identity=identity, configuration=config,
        makerspace_id=config.makerspace_id, credential_version=config.credential_version,
        signed_user_id=proof_user_id,
        payload={"event": asdict(event), "protection": protection or {}, "inbound_at": inbound_at,
                 "extra": extra or {}, "proof_user_id": proof_user_id})


def protect(receipt):
    from .messaging.locks import lock_whatsapp_sender
    from .messaging.stops import process_stop, suppress_recipient
    if receipt.channel == "whatsapp":
        lock_whatsapp_sender(receipt.sender_key)
    receipt = NotificationIngress.objects.select_for_update().get(pk=receipt.pk)
    if receipt.protection_applied:
        return
    data = receipt.get_payload()
    protection = data if receipt.transport == "legacy" else data.get("protection", {})
    code = protection.get("error_code")
    phone = protection.get("phone_hash", "")
    if not phone and code in {"21610", "21211", "21614", "131050"}:
        phone = addressed_hash(receipt, data)
    unresolved = ((protection.get("stop") and protection.get("correlation_missing"))
        or (protection.get("stop") and not phone and not protection.get("alias_hash"))
        or (code in {"21610", "21211", "21614", "131050"} and not phone))
    from .messaging.protections import recipient_hash
    from .models_messaging_consent import MessagingSuppression
    hold_hash = recipient_hash("alias", f"unresolved-receipt:{receipt.pk}")
    if unresolved:
        # A fast 21610 without To can precede the REST response/provider ID. Keep
        # the whole physical sender stopped until exact delivery correlation exists.
        suppress_recipient(receipt.channel, receipt.sender_key, hold_hash, kind="sender",
            reason="provider_opt_out" if code else "inbound_stop")
        return
    if protection.get("stop"):
        process_stop(SimpleNamespace(payload=protection, channel=receipt.channel,
            sender_key=receipt.sender_key))
    if code in {"21610", "21211", "21614", "131050"} and phone:
        suppress_recipient(receipt.channel, receipt.sender_key, phone,
            reason="provider_opt_out" if code in {"21610", "131050"} else "permanent_failure")
    MessagingSuppression.objects.filter(channel=receipt.channel, sender_key=receipt.sender_key,
        recipient_hash=hold_hash, recipient_kind="sender", lifted_at=None).update(lifted_at=timezone.now())
    receipt.protection_applied = True
    receipt.save(update_fields=["protection_applied"])


def addressed_hash(receipt, data):
    from .models_contract import NotificationDelivery
    from .models_messaging_delivery import MessagingDelivery
    event = data if receipt.transport == "legacy" else data.get("event", {})
    message_id = event.get("message_id") or event.get("provider_id")
    if not message_id:
        return ""
    from .models_cutover import NotificationProviderReference
    reference = NotificationProviderReference.objects.filter(provider=receipt.provider,
        sender_key=receipt.sender_key, provider_id=message_id).first()
    if reference:
        if reference.ambiguous or (receipt.makerspace_reference and receipt.makerspace_reference != reference.makerspace_reference):
            return ""
        if reference.phone_hash:
            return reference.phone_hash
    rows = NotificationDelivery.objects.filter(sender_key=receipt.sender_key, provider=receipt.provider,
        provider_id=message_id)
    if receipt.makerspace_reference:
        rows = rows.filter(makerspace_id=receipt.makerspace_reference)
    hashes = list(rows.values_list("recipient_phone_hash", flat=True)[:2])
    if len(hashes) == 1:
        return hashes[0]
    if hashes:
        return ""
    old = MessagingDelivery.objects.filter(sender_key=receipt.sender_key, provider=receipt.provider,
        provider_message_id=message_id)
    if receipt.makerspace_reference:
        old = old.filter(makerspace_id=receipt.makerspace_reference)
    hashes = list(old.values_list("recipient_phone_hash", flat=True)[:2])
    return hashes[0] if len(hashes) == 1 else ""


def process(pk):
    from .notification_ingress_apply import apply
    with boundary():
        # Shared cutover lock precedes all tenant/sender/event locks.
        if state().route != "canonical":
            return False
        snapshot = NotificationIngress.objects.get(pk=pk)
        if snapshot.state == "processed":
            return True
        # Sender protection precedes optional tenant writes, even for frozen tenants.
        with transaction.atomic():
            protect(snapshot)
        snapshot.refresh_from_db(fields=["protection_applied"])
        return _process_serialized(pk)


def _process_serialized(pk):
    from .notification_ingress_apply import apply
    from .messaging.locks import advisory_lock
    with transaction.atomic():
        # Serialize processing before tenant/sender/row locks; ingress protection
        # never takes this lock and has already committed in a separate transaction.
        advisory_lock(f"notification-receipt:{pk}")
        snapshot = NotificationIngress.objects.get(pk=pk)
        if snapshot.state == "processed":
            return True
        data = snapshot.get_payload()
        try:
            with transaction.atomic():
                done = apply(snapshot, data) and snapshot.protection_applied
        except Exception as exc:
            logger.warning("notification_ingress_replay_failed", extra={"receipt_id": pk, "failure_type": type(exc).__name__})
            done = False
        NotificationIngress.objects.filter(pk=pk).update(state="processed" if done else "held",
            processed_at=timezone.now() if done else None, attempts=snapshot.attempts + 1,
            next_attempt_at=timezone.now() + timedelta(seconds=min(60 * 2 ** min(snapshot.attempts, 10), 86400)),
            last_error="" if done else "correlation_or_tenant_hold")
        protection = data if snapshot.transport == "legacy" else data.get("protection", {})
        if done and protection.get("stop"):
            from .messaging.stops import append_stop_consents
            event = SimpleNamespace(payload=protection, channel=snapshot.channel, sender_key=snapshot.sender_key)
            transaction.on_commit(lambda: append_stop_consents(event), robust=True)
        return done


@guarded()
def recover(limit=200):
    from .models_cutover import NotificationCredentialVersion
    for pk in NotificationIngress.objects.filter(next_attempt_at__lte=timezone.now()).exclude(
            state="processed").order_by("next_attempt_at", "pk").values_list("pk", flat=True)[:limit]:
        try:
            process(pk)
        except Exception as exc:
            NotificationIngress.objects.filter(pk=pk).update(state="held", last_error="receipt_unavailable",
                next_attempt_at=timezone.now() + timedelta(minutes=5))
            logger.warning("notification_ingress_recovery_deferred", extra={"receipt_id": pk, "failure_type": type(exc).__name__})
    # Never wipe a retired verifier while a correlated receipt still needs replay.
    cutoff = timezone.now() - timedelta(days=14)
    for version in NotificationCredentialVersion.objects.filter(retired_at__lt=cutoff, wiped_at=None):
        if not NotificationIngress.objects.filter(configuration_reference=version.configuration_reference,
                generation=version.generation).exclude(state="processed").exists():
            version.credentials, version.wiped_at = "", timezone.now()
            version.save(update_fields=["credentials", "wiped_at"])


def mapped_delivery(legacy_id):
    from .models_contract import NotificationDelivery
    mapping = NotificationLegacyMapping.objects.filter(legacy_model="MessagingDelivery", legacy_id=legacy_id,
        canonical_model="NotificationDelivery").first()
    return NotificationDelivery.objects.filter(pk=mapping.canonical_id).first() if mapping else None
