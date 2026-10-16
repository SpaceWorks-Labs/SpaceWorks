"""Shared lifecycle adapter for booking notifications."""

from apps.bookings.models import Booking
from apps.accounts import rbac
from apps.integrations.email_templates import render
from apps.integrations.email_templates_fablab import bookings_context
from apps.integrations.email_templates_registry_fablab_defaults import (
    BOOKINGS_REQUESTER_BODIES,
)
from apps.integrations.destinations import NotificationScope
from apps.integrations.notify import EmailDelivery, LifecyclePayload, notify_lifecycle
from apps.integrations.recipients import has_selection, requester_selected
from apps.integrations.staff_notifications import staff_emails_for_feature
from apps.notifications.inbox import InboxDelivery, eligible_owner

BOOKING_NOTIFICATION_EVENTS = frozenset(
    {"created", "confirmed", "rejected", "cancelled", "restored", "completed", "no_show"}
)


def _effective_toggle(booking):
    override = booking.space.requester_notifications_enabled
    if override is not None:
        return override
    return booking.space.makerspace.booking_requester_notifications_enabled


def _restored_owner_eligible(booking):
    from apps.bookings.access import require_booking_account
    from apps.presence.guard import MemberPresenceRequired, WaiverAcceptanceRequired

    if not eligible_owner(booking.space.makerspace, booking.member_id):
        return False
    try:
        require_booking_account(booking.member, booking.space.makerspace)
    except (MemberPresenceRequired, WaiverAcceptanceRequired):
        return False
    return True


def notify_booking_status(booking, event, *, sync=False):
    booking_id = booking.pk
    makerspace = booking.space.makerspace

    def build():
        row = rbac.scope_notification_policy(
            Booking.objects.all(), makerspace_id=makerspace.pk, field="space__makerspace_id",
        ).select_related("space__makerspace", "member").get(pk=booking_id)
        # One context, both audiences: the wording differs per template, the facts do not.
        context = bookings_context(
            row, event, next_steps=BOOKINGS_REQUESTER_BODIES.get(event, "")
        )
        emails = []
        scope = NotificationScope(machine_type=row.space.machine_type_id) if event == "restored" and row.space.machine_type_id else None
        requester_enabled = _effective_toggle(row) and (event != "restored" or (
            _restored_owner_eligible(row) and (not has_selection(makerspace, "bookings", event, scope)
                                             or requester_selected(makerspace, "bookings", event, scope))))
        requester_email = row.member.email if event == "restored" and row.member_id else row.email
        if requester_enabled and requester_email:
            member = render(makerspace, "bookings", "requester", event, context)
            emails.append(
                EmailDelivery(
                    to_email=requester_email,
                    subject=member["subject"],
                    text_body=member["text_body"],
                    html_body=member["html_body"],
                    audience="requester",
                    stream="bookings",
                    user_id=row.member_id,
                )
            )
        staff = render(makerspace, "bookings", "staff", event, context)
        requester_summary = f"Your booking for {row.space.name} is {event.replace('_', ' ')}."
        if event == "restored":
            requester_summary = (f"{row.space.name}. Status: {row.status}. Time: {context['booking'].when}. "
                                 + context["next_steps"])
        emails.extend(
            EmailDelivery(
                to_email=recipient,
                subject=staff["subject"],
                text_body=staff["text_body"],
                audience="staff",
                stream="bookings",
            )
            for recipient in staff_emails_for_feature(
                makerspace, "bookings", event=event, scope=scope
            )
        )
        # `text` is the STAFF body: chat channels are a staff surface, so the member's
        # "your booking is confirmed" wording must never be what reaches a room.
        return LifecyclePayload(
            text=staff["text_body"], emails=tuple(emails), context=context, scope=scope,
            data={"booking_id": row.pk, "space_id": row.space_id},
            inbox=(InboxDelivery(row.member_id, f"Booking {event.replace('_', ' ')}",
                                 requester_summary,
                                 f"/m/{makerspace.slug}/member"),) if row.member_id and requester_enabled else (),
        )

    return notify_lifecycle(
        makerspace,
        feature="bookings",
        event=event,
        build=build,
        sync=sync,
    )
