"""Email-only compatibility for the booking owner's same, unverified mailbox."""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.accounts import rbac
from apps.integrations.delivery_sources import DeliverySource, register
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration
from .models import Booking

KIND = "bookings.owner_mailbox"
SOURCES = frozenset({"bookings.lifecycle", "bookings.reminder"})


def logs(envelope):
    return rbac.scope_notification_policy(EmailLog.objects.all(), makerspace_id=envelope.makerspace_id).filter(
        source_kind=KIND, source_id=envelope.pk, recipient_id=envelope.recipient_id,
    )


def email_reserved(envelope):
    # A pending/in-flight/retry leg owns email too: verification can change while
    # SMTP is in flight. Only a skipped compatibility leg releases that ownership.
    return envelope.audience == "requester" and logs(envelope).exclude(status="skipped").exists()


def needs_direct(envelope):
    from apps.integrations.notification_resolution import eligible, resolve, selected_policy
    from apps.integrations.dispatch_policy import email_module_blocks
    from apps.integrations.email_preferences import blocked_reason
    from apps.integrations.notification_catalog import is_notification_enabled
    from apps.integrations.recipients import has_selection, requester_selected
    if envelope.source_kind not in SOURCES or envelope.audience != "requester":
        return False
    user = envelope.recipient
    user.refresh_from_db()
    if user.email_verified_at or not user.email or not eligible(envelope):
        return False
    try:
        validate_email(user.email)
    except ValidationError:
        return False
    row = rbac.scope_notification_policy(Booking.objects.all(), makerspace_id=envelope.makerspace_id,
        field="space__makerspace_id").filter(pk=envelope.source_id, member_id=user.pk).first()
    # Booking.email is scoped PII; compare its decrypted accessor, never query the
    # encrypted DB column for a plaintext email.
    if (row is None or row.email.strip().casefold() != user.email.strip().casefold()
            or email_module_blocks(envelope.makerspace, envelope.stream, envelope.event)):
        return False
    if blocked_reason(envelope.makerspace, user.email, user_id=user.pk, feature=envelope.feature,
                      stream=envelope.stream, event=envelope.event):
        return False
    if (has_selection(envelope.makerspace, "bookings", envelope.event)
            and not requester_selected(envelope.makerspace, "bookings", envelope.event)):
        return False
    config = rbac.scope_notification_policy(ChannelConfiguration.objects.all(),
        makerspace_id=envelope.makerspace_id).filter(channel="email").first()
    if config is not None and not (config.enabled and config.personal_enabled):
        return False
    channels, _ = selected_policy(envelope)
    return ("email" in channels and is_notification_enabled(envelope.makerspace, "bookings", "email")
            and not any(target.channel == "email" for target in resolve(envelope))
            and not envelope.deliveries.filter(channel="email", state__in=["accepted", "sent", "delivered", "read"]).exists())


def notify_owner(envelope):
    if not needs_direct(envelope):
        return None
    from apps.integrations.dispatch import dispatch_email
    from apps.integrations.notification_sources import render
    # Emission holds the envelope lock until the unique compatibility leg exists.
    # This makes repeated lifecycle/reminder emission return the same EmailLog.
    with transaction.atomic():
        rbac.scope_notification_policy(NotificationEnvelope.objects.select_for_update(),
            makerspace_id=envelope.makerspace_id).get(pk=envelope.pk, recipient_id=envelope.recipient_id)
        existing = logs(envelope).first()
        if existing:
            return existing
        content = render(envelope)
        return dispatch_email(makerspace=envelope.makerspace, to_email=envelope.recipient.email,
            recipient_id=envelope.recipient_id, feature=envelope.feature, stream=envelope.stream,
            event=envelope.event, audience="requester", source_kind=KIND, source_id=envelope.pk,
            subject=content["subject"], text_body=content["text"], html_body=content.get("html", ""))


def prepare(log):
    from apps.integrations.delivery_content import render as set_content
    from apps.integrations.notification_sources import render
    envelope = rbac.scope_notification_policy(NotificationEnvelope.objects.all(),
        makerspace_id=log.makerspace_id).select_related("recipient", "makerspace").filter(
            pk=log.source_id, recipient_id=log.recipient_id).first()
    if envelope is None or not needs_direct(envelope) or envelope.recipient.email != log.to_email:
        return False
    if (log.feature, log.stream, log.event, log.audience) != (
            envelope.feature, envelope.stream, envelope.event, "requester"):
        return False
    content = render(envelope)
    from apps.integrations.notification_links import external_links
    content = external_links(envelope.makerspace, content)
    from apps.integrations.inline_attachments import confirmation_attachments  # #169 (lane L6)
    set_content(log, to_email=log.to_email, subject=content["subject"], text_body=content["text"],
                html_body=content.get("html", ""), attachments=confirmation_attachments(envelope))
    return True


def register_owner_mailbox():
    register(KIND, DeliverySource(prepare, finished=finished, digestible=False))


def finished(log):
    if log.status != "skipped":
        return
    # When account verification supersedes an unsent compatibility leg, release
    # the reservation and durably wake the original envelope. A processed inbox
    # leg must not strand its newly eligible email leg, even if the broker is down.
    rows = rbac.scope_notification_policy(NotificationEnvelope.objects.all(), makerspace_id=log.makerspace_id).filter(
        pk=log.source_id, recipient_id=log.recipient_id, audience="requester", source_kind__in=SOURCES,
    )
    with transaction.atomic():
        if not rows.update(processed_at=None):
            return
        from django.utils import timezone
        from apps.integrations.models_contract import NotificationDelivery
        from apps.integrations.notification_outbox import enqueue
        now = timezone.now()
        delivery, created = NotificationDelivery.objects.get_or_create(
            envelope_id=log.source_id, channel="email", defaults={"makerspace_id": log.makerspace_id,
                "target_key": "email", "provider": "builtin", "next_attempt_at": now})
        if not created and delivery.state == "skipped":
            NotificationDelivery.objects.filter(pk=delivery.pk, state="skipped").update(
                state="retrying", next_attempt_at=now)
        # A retrying delivery keeps this handoff visible to the sweeper even if
        # another in-flight worker writes processed_at after this transaction.
        transaction.on_commit(lambda: enqueue(log.source_id), robust=True)
