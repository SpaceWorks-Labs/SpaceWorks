"""Verified account-less hardware email stays on the existing email-only path."""
from apps.accounts import rbac
from apps.integrations.delivery_sources import DeliverySource, register
from apps.integrations.email_templates import hardware_context, render
from apps.integrations.notification_catalog import is_notification_enabled
from apps.integrations.notification_rules import is_requester_muted
from apps.notifications.preferences import mandatory_email
from .models import HardwareRequest

KIND = "hardware.verified_contact"


def prepare(log):
    from apps.makerspaces.servability import is_servable
    from .notifications_p2_requests import KEYS, request_revision
    row = rbac.scope_notification_policy(HardwareRequest.objects.all(), makerspace_id=log.makerspace_id).filter(
        pk=log.source_id, requester_contact_verified=True).first()
    if row is None or not row.anonymous_idempotency_key_fingerprint or not is_servable(log.makerspace):
        return False
    if row.requester_contact_email != log.to_email or request_revision(row) != log.source_metadata.get("revision"):
        return False
    key = KEYS[log.event]
    if not mandatory_email("hardware", log.event) and (
        is_requester_muted(log.makerspace, "hardware", key)
        or not is_notification_enabled(log.makerspace, "hardware_requests", "email")
    ):
        return False
    from apps.integrations.delivery_content import render as set_content
    rendered = render(row.makerspace, "hardware", "requester", key, hardware_context(row, staff=False))
    set_content(log, to_email=row.requester_contact_email, subject=rendered["subject"],
                text_body=rendered["text_body"], html_body=rendered["html_body"])
    return True


def notify(row, event, rendered):
    """The shared anonymous principal is never a personal envelope recipient."""
    from .notifications_p2_requests import request_revision, KEYS
    from apps.integrations.dispatch import dispatch_email
    if not (row.anonymous_idempotency_key_fingerprint and row.requester_contact_verified and row.requester_contact_email):
        return
    if not mandatory_email("hardware", event) and (
        not is_notification_enabled(row.makerspace, "hardware_requests", "email")
        or is_requester_muted(row.makerspace, "hardware", KEYS[event])
    ):
        return
    # Serialisation/dedup uses the locked request, just like the personal intents.
    from apps.integrations.models import EmailLog
    version = request_revision(row)
    existing = rbac.scope_notification_policy(EmailLog.objects.all(), makerspace_id=row.makerspace_id).filter(
        source_kind=KIND, source_id=row.pk, event=event, source_metadata__revision=version).first()
    if existing:
        return existing
    return dispatch_email(makerspace=row.makerspace, to_email=row.requester_contact_email,
        feature="hardware_requests", stream="hardware", event=event, audience="requester",
        source_kind=KIND, source_id=row.pk, source_metadata={"revision": version},
        subject=rendered["subject"], text_body=rendered["text_body"], html_body=rendered["html_body"])


def register_source():
    register(KIND, DeliverySource(prepare))
    register_owner_source()


OWNER_KIND = "hardware.owner_mailbox"


def owner_needs_direct(envelope):
    """Compatibility fallback only while the shared owner-proof policy is absent.

    Once installed, the resolver owns both delivery and refusal. A fallback must
    never acquire a second route around its mute, suppression or consent checks.
    """
    from apps.integrations.models_endpoints import ChannelConfiguration
    from apps.integrations.notification_resolution import eligible, selected_policy
    from .notifications_p2_email import allowed, proven_address
    from apps.integrations import notification_resolution
    # The installed resolver owns refusals as well as successful deliveries.
    # Falling back after a mute/suppression refusal would bypass that policy.
    if getattr(notification_resolution, "EQUIPMENT_EMAIL_POLICY", None) is allowed:
        return False
    user = envelope.recipient
    user.refresh_from_db()
    if user.email_verified_at or not user.email or not proven_address(envelope):
        return False
    # Standing, servability, live source and (via source_ready) requester mutes.
    if not eligible(envelope):
        return False
    if mandatory_email(envelope.stream, envelope.event):
        return True
    config = rbac.scope_notification_policy(ChannelConfiguration.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(channel="email").first()
    if config is not None and not (config.enabled and config.personal_enabled):
        return False
    channels, _ = selected_policy(envelope)
    return "email" in channels and is_notification_enabled(envelope.makerspace, envelope.feature, "email")


def notify_owner(envelope):
    """Called beside the owner's envelope, inside the same domain transaction."""
    if envelope.source_kind not in {"hardware.request", "hardware.loan_reminder"} or not owner_needs_direct(envelope):
        return None
    from apps.integrations.dispatch import dispatch_email
    from apps.integrations.models import EmailLog
    from apps.integrations.notification_sources import render as render_envelope
    existing = rbac.scope_notification_policy(EmailLog.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        source_kind=OWNER_KIND, source_id=envelope.pk).first()
    if existing:
        return existing
    rendered = render_envelope(envelope)
    return dispatch_email(makerspace=envelope.makerspace, to_email=envelope.recipient.email,
        feature=envelope.feature, stream=envelope.stream, event=envelope.event, audience="requester",
        recipient_id=envelope.recipient_id, source_kind=OWNER_KIND, source_id=envelope.pk,
        subject=rendered["subject"], text_body=rendered["text"], html_body=rendered.get("html", ""))


def prepare_owner(log):
    """Send, retry and digest re-check the envelope and the same-mailbox proof."""
    from apps.integrations.delivery_content import render as set_content
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_sources import render as render_envelope
    envelope = rbac.scope_notification_policy(NotificationEnvelope.objects.all(),
        makerspace_id=log.makerspace_id).select_related("recipient", "makerspace").filter(pk=log.source_id).first()
    if envelope is None or not owner_needs_direct(envelope) or envelope.recipient.email != log.to_email:
        return False
    rendered = render_envelope(envelope)
    set_content(log, to_email=log.to_email, subject=rendered["subject"],
                text_body=rendered["text"], html_body=rendered.get("html", ""))
    return True


def register_owner_source():
    register(OWNER_KIND, DeliverySource(prepare_owner))
