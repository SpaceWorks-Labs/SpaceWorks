"""Booking lifecycle notifications through source-backed personal envelopes.

Audiences are explicit and never inferred from an address:

* the booking OWNER (an account) gets one personal envelope per lifecycle event, through
  whatever channels they selected (email + in-app by default);
* every authorized STAFF recipient (Booking Managers and the tenant's notification
  selection) gets their own staff-worded envelope, and resource-grant holders with
  `manage_reservations` on this space get the same staff wording;
* staff ROOMS (Telegram/Slack/Mattermost/Discord/webhook) keep the legacy lifecycle summary,
  and account-less guest bookings keep their contact-address email.

Requester wording never reaches a room. Each envelope is written inside the domain
transaction, and `notification_sources` re-checks the live booking (same revision, owner,
toggle, grant) before every send, retry and deferred release.
"""

import logging
from django.db import transaction

from apps.integrations.notification_links import local_link
from apps.accounts import rbac
from apps.bookings.models import Booking
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_fablab import bookings_context
from apps.integrations.email_templates_registry_fablab_defaults import BOOKINGS_REQUESTER_BODIES
from apps.integrations.notify import EmailDelivery, LifecyclePayload, notify_lifecycle
from apps.integrations.recipients import has_selection, requester_selected
from apps.integrations.staff_notifications import staff_user_ids_for_feature

logger = logging.getLogger(__name__)

BOOKING_NOTIFICATION_EVENTS = frozenset(
    {"created", "confirmed", "rejected", "cancelled", "restored", "completed", "no_show"}
)
LIFECYCLE_SOURCE = "bookings.lifecycle"
GRANT_SOURCE = "bookings.grant_alert"


def _effective_toggle(booking):
    override = booking.space.requester_notifications_enabled
    if override is not None:
        return override
    return booking.space.makerspace.booking_requester_notifications_enabled


def _restored_owner_eligible(booking):
    from apps.bookings.access import require_booking_account
    from apps.integrations.recipients_owners import eligible_owner
    from apps.presence.guard import MemberPresenceRequired, WaiverAcceptanceRequired

    if not eligible_owner(booking.space.makerspace, booking.member_id):
        return False
    try:
        require_booking_account(booking.member, booking.space.makerspace)
    except (MemberPresenceRequired, WaiverAcceptanceRequired):
        return False
    return True


def scope_for(row, event):
    if event == "restored" and row.space.machine_type_id:
        return NotificationScope(machine_type=row.space.machine_type_id)
    return None


def requester_enabled(row, event):
    """The requester toggle (on by default) plus the restored-event owner/selection rules."""
    if not _effective_toggle(row):
        return False
    if event != "restored":
        return True
    makerspace, scope = row.space.makerspace, scope_for(row, event)
    return _restored_owner_eligible(row) and (not has_selection(makerspace, "bookings", event, scope)
                                              or requester_selected(makerspace, "bookings", event, scope))


def _with_reason(text, row, event):
    if event in ("rejected", "cancelled") and row.decision_reason:
        return f"{text.rstrip()}\n\nReason: {row.decision_reason}\n"
    return text


def requester_content(row, event, context):
    message = render(row.space.makerspace, "bookings", "requester", event, context)
    reasoned = event in ("rejected", "cancelled") and bool(row.decision_reason)
    # With a reason the plain-text body carries it; the authored HTML would silently omit it.
    return {"subject": message["subject"], "text": _with_reason(message["text_body"], row, event),
            "html": "" if reasoned else message["html_body"],
            "link": local_link(row.space.makerspace, "member", "bookings")}


def staff_content(row, event, context):
    from apps.operations.notifications_p2 import staff_link
    message = render(row.space.makerspace, "bookings", "staff", event, context)
    query = ("?view=requests&status=pending" if row.status == "pending"
             else f"?space={row.space_id}&booking={row.pk}&bookingTab=requests")
    return {"subject": message["subject"], "text": _with_reason(message["text_body"], row, event), "html": "",
            "link": staff_link(row.space.makerspace, f"bookings{query}")}


def grant_recipient_ids(space):
    from apps.accounts.models import User
    from .booking_authority import can
    candidates = space.bookingspacestaffgrant_rows.filter(
        revoked_at__isnull=True, permissions__contains=["manage_reservations"]).values("user_id")
    return {user.pk for user in User.objects.filter(pk__in=candidates) if can(user, space, "manage_reservations")}


def _emit(row, event, recipient_id, audience, source_kind, rendered):
    from apps.accounts.models import User
    from apps.hardware_requests.notification_projection import addressed_context
    from apps.integrations.notification_outbox import emit
    try:
        with transaction.atomic():
            envelope = emit(makerspace=row.space.makerspace, recipient=User.objects.get(pk=recipient_id), feature="bookings",
                 stream="bookings", event=event, audience=audience,
                 dedup_key=f"bookings:{row.pk}:{event}:{row.calendar_sequence}:{audience}:{recipient_id}",
                 source_kind=source_kind, source_id=str(row.pk), revision=str(row.calendar_sequence), subject=row,
                 scope=scope_for(row, event),
                 context={**addressed_context(row.space.makerspace, "bookings", event, audience,
                                               bookings_context(row, event)),
                          "booking_id": row.pk, "space_id": row.space_id, "status": row.status},
                 rendered=rendered)
            if audience == "staff":
                from apps.integrations.models_contract import NotificationDelivery
                for channel in ("in_app", "native_push"):
                    NotificationDelivery.objects.get_or_create(envelope=envelope, channel=channel, defaults={
                        "makerspace": row.space.makerspace, "target_key": channel, "provider": "builtin",
                        "state": "skipped", "last_error": "legacy_matrix_channel"})
            if audience == "requester":
                from .notification_owner_mailbox import notify_owner
                notify_owner(envelope)
        return envelope
    except Exception:
        # Notification failure must never undo or block the booking decision itself.
        logger.warning("booking_envelope_emit_failed", extra={"booking_id": row.pk, "event": event, "audience": audience})


def notify_booking_status(booking, event, *, sync=False):
    if event not in BOOKING_NOTIFICATION_EVENTS:
        from apps.integrations.notify import NotificationResult
        return NotificationResult(False)
    makerspace = booking.space.makerspace
    row = rbac.scope_notification_policy(
        Booking.objects.all(), makerspace_id=makerspace.pk, field="space__makerspace_id",
    ).select_related("space__makerspace", "member").get(pk=booking.pk)
    context = bookings_context(row, event, next_steps=BOOKINGS_REQUESTER_BODIES.get(event, ""))
    scope = scope_for(row, event)
    owner_on = requester_enabled(row, event)
    if row.member_id and owner_on:
        _emit(row, event, row.member_id, "requester", LIFECYCLE_SOURCE, requester_content(row, event, context))
    staff = staff_content(row, event, context)
    staff_ids = set(staff_user_ids_for_feature(makerspace, "bookings", event=event, scope=scope))
    for user_id in sorted(staff_ids - {row.member_id}):
        _emit(row, event, user_id, "staff", LIFECYCLE_SOURCE, staff)
    for user_id in sorted(grant_recipient_ids(row.space) - staff_ids - {row.member_id}):
        # Grant holders are not tenant staff, so the shared staff audience would refuse them;
        # their authority is the live grant, re-checked by the grant source at every send.
        _emit(row, event, user_id, "member", GRANT_SOURCE, staff)

    def build():
        emails = ()
        # Guest mail is built after commit; reload its live gates just like the
        # personal worker does, rather than capturing the emission-time toggle.
        live = rbac.scope_notification_policy(
            Booking.objects.all(), makerspace_id=makerspace.pk, field="space__makerspace_id",
        ).select_related("space__makerspace").get(pk=row.pk)
        if (live.calendar_sequence == row.calendar_sequence and live.status == row.status
                and live.member_id is None and requester_enabled(live, event) and live.email):
            member = requester_content(live, event, bookings_context(live, event,
                next_steps=BOOKINGS_REQUESTER_BODIES.get(event, "")))
            emails = (EmailDelivery(to_email=live.email, subject=member["subject"],
                                    text_body=member["text"], html_body=member["html"],
                                    audience="requester", stream="bookings",
                                    source_kind="bookings.guest_mailbox", source_id=live.pk,
                                    source_metadata={"revision": str(live.calendar_sequence), "status": live.status}),)
        # `text` is the STAFF summary: chat rooms are a staff surface.
        return LifecyclePayload(text=staff["text"], emails=emails, context=context, scope=scope,
                                source={"source_kind": LIFECYCLE_SOURCE, "source_id": str(row.pk),
                                        "revision": str(row.calendar_sequence), "context": {}},
                                data={"booking_id": row.pk, "space_id": row.space_id})

    return notify_lifecycle(makerspace, feature="bookings", event=event, build=build, sync=sync)
