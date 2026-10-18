"""Addressed checks are independent of the optional member inbox."""
from .models_endpoints import ChannelConfiguration


def eligible(envelope, channel, endpoint=None):
    from apps.makerspaces.platform import module_enabled
    from .messaging.ties import has_tenant_tie
    from .messaging.consent import live_consent
    from .messaging.protections import recipient_hash, suppressed
    from .notification_sender import configuration_sender_key, sms_sender
    from .notification_personal_policy import personal_enabled
    from apps.makerspaces.models import MakerspaceMembership
    from apps.accounts import rbac
    user, space = envelope.recipient, envelope.makerspace
    user.refresh_from_db()
    if not user.is_active or user.access_status != "active" or user.is_tenant_dump_stub or user.deletion_requested_at:
        return False
    if not module_enabled(space, channel):
        return False
    if envelope.audience != "staff" and not has_tenant_tie(user, space):
        return False
    membership = rbac.scope_notification_policy(MakerspaceMembership.objects.all(),
        makerspace_id=space.pk).filter(user=user).first()
    if membership and (membership.status == "revoked" or not membership.receives_notifications):
        return False
    if not personal_enabled(space, user.pk, envelope.feature, channel, event=envelope.event):
        return False
    config = ChannelConfiguration.objects.filter(makerspace=space, channel=channel,
        enabled=True, personal_enabled=True, activation_hold=False).first()
    if config is None:
        return False
    from .messaging.resolver import resolve_sender
    current_sender = resolve_sender(space, channel)
    if current_sender is None:
        return False
    from .models_cutover import NotificationProviderReference
    if NotificationProviderReference.objects.filter(provider=current_sender.provider,
            sender_key=current_sender.sender_key, ambiguous=True).exists():
        return False
    if channel == "sms":
        sender = sms_sender(config)
        return bool(sender and live_consent(space, user, channel, configuration=config)
            and not suppressed(channel, sender.sender_key, recipient_hash("phone", user.phone_e164)))
    # WhatsApp uses its own signed endpoint proof, not SMS/phone-login consent.
    from .notification_resolution import endpoint_eligible
    if not endpoint_eligible(endpoint, envelope):
        return False
    from .models_messaging_consent import MessagingConsent
    latest = MessagingConsent.objects.filter(makerspace=space, user=user, channel="whatsapp").order_by("-pk").first()
    if latest and latest.action == "opted_out":
        return False
    return not suppressed(channel, configuration_sender_key(config), recipient_hash("phone", endpoint.destination))


def snapshot(envelope):
    from .notification_sender import sms_sender
    from .messaging.consent import live_consent
    from .messaging.protections import recipient_hash
    from .models_messaging_consent import MessagingConsent
    config = ChannelConfiguration.objects.filter(makerspace=envelope.makerspace, channel="sms").first()
    sender = sms_sender(config) if config else None
    user = envelope.recipient
    user.refresh_from_db()
    if sender and live_consent(envelope.makerspace, user, "sms", configuration=config):
        consent = MessagingConsent.objects.filter(makerspace=envelope.makerspace, user=user, channel="sms").order_by("-pk").first()
        return {"configuration": config.pk, "generation": config.generation,
            "sender_key": sender.sender_key, "provider": sender.provider,
            "credential_version": config.credential_version, "source": sender.provider_source,
            "phone_hash": recipient_hash("phone", user.phone_e164),
            "phone_verified_at": user.phone_verified_at.isoformat(), "consent_id": consent.pk}
    return None


def binding_current(envelope, config, sender):
    bound = envelope.routing_snapshot.get("sms")
    current = snapshot(envelope)
    return bound is not None and bound == current and bound.get("sender_key") == sender.sender_key


def send_sms(delivery):
    from .messaging.projections import PROJECTION_KEYS, render_sms
    from .messaging.segments import prepare_sms
    from .messaging.twilio import send_message
    from .models_contract import NotificationDelivery
    from .notification_providers import ProviderResult
    from .notification_sender import sms_sender
    envelope = delivery.envelope
    config = ChannelConfiguration.objects.filter(makerspace=delivery.makerspace, channel="sms").first()
    sender = sms_sender(config) if config else None
    if not sender or not binding_current(envelope, config, sender) or not eligible(envelope, "sms"):
        return ProviderResult(False, error_code="skipped")
    audience = "member" if envelope.audience == "requester" else envelope.audience
    allowed = PROJECTION_KEYS.get((envelope.feature, envelope.event, audience))
    if allowed is None:
        return ProviderResult(False, error_code="template_required")
    context = {key: envelope.context[key] for key in allowed if key in envelope.context}
    content = prepare_sms(render_sms(envelope.feature, envelope.event, audience, context))
    NotificationDelivery.objects.filter(pk=delivery.pk).update(estimated_segments=content.estimated_segments)
    from .notification_resolution import eligible as source_eligible
    from .messaging.protections import recipient_hash
    if (not source_eligible(envelope) or not eligible(envelope, "sms")
            or not binding_current(envelope, config, sender)
            or delivery.recipient_phone_hash != recipient_hash("phone", envelope.recipient.phone_e164)):
        return ProviderResult(False, error_code="skipped")
    result = send_message(sender, to=envelope.recipient.phone_e164, body=content.body, delivery_id=delivery.pk)
    if result.error_code in {"21610", "21211", "21614"}:
        from .messaging.stops import suppress_recipient
        suppress_recipient("sms", sender.sender_key, delivery.recipient_phone_hash,
            reason="provider_opt_out" if result.error_code == "21610" else "permanent_failure")
    return ProviderResult(bool(result.message_id), provider_id=result.message_id, retryable=result.retryable,
        error_code=result.error_code, ambiguous=result.ambiguous)


def prepare_whatsapp(delivery):
    from django.db import transaction
    from django.utils import timezone
    from .messaging.correlation import claim_canonical_probe
    from .messaging.locks import lock_whatsapp_sender
    from .models_contract import NotificationDelivery
    with transaction.atomic():
        lock_whatsapp_sender(delivery.sender_key)
        row = NotificationDelivery.objects.select_for_update().get(pk=delivery.pk)
        result = claim_canonical_probe(row)
        if result in {"confirmed", "probe"}:
            return True
        row.state = "retrying" if result == "wait" else "held" if result == "ambiguous" else "skipped"
        row.last_error = "identity_unconfirmed"
        row.claim_until = None
        row.retryable = result == "wait"
        if row.retryable:
            from datetime import timedelta
            row.attempt_count -= 1
            row.next_attempt_at = timezone.now() + timedelta(minutes=5)
        row.save()
        return False


def endpoint_sendable(config, endpoint):
    from .messaging.protections import recipient_hash, suppressed
    from .models_messaging_consent import MessagingRecipientCorrelation
    from .notification_sender import configuration_sender_key
    sender = configuration_sender_key(config)
    from .models_cutover import NotificationProviderReference
    if NotificationProviderReference.objects.filter(provider=config.provider, sender_key=sender, ambiguous=True).exists():
        return False
    phone_hash = recipient_hash("phone", endpoint.destination)
    if suppressed("whatsapp", sender, phone_hash):
        return False
    return not MessagingRecipientCorrelation.objects.filter(sender_key=sender, phone_hash=phone_hash,
        state="blocked").exists()
