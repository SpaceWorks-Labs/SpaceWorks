"""Live source checks for every bookings envelope, run at each send/retry/release/digest.

The shared layer already re-checks account standing, tenant servability, staff scope,
channel gates, personal preference and endpoint consent. These checks add what only the
bookings domain knows: the booking still exists in this tenant at the SAME revision the
notice describes, the explicit owner still owns it, the requester toggle is still on, a
resource grant is still live, and a campaign is still authorized and still targets them.
"""

from django.utils import timezone

from apps.integrations.notification_sources import NotificationSource, register_source
from apps.makerspaces.platform import module_enabled

from .models import Booking

REMINDER_SOURCE = "bookings.reminder"
BROADCAST_SOURCE = "bookings.broadcast"


def _booking(envelope):
    row = Booking.objects.select_related("space__makerspace").filter(
        pk=envelope.source_id if str(envelope.source_id).isdecimal() else 0,
        space__makerspace_id=envelope.makerspace_id,
    ).first()
    if row is None or str(row.calendar_sequence) != envelope.revision:
        return None
    return row if module_enabled(row.space.makerspace, "bookings") else None


def lifecycle_eligible(envelope):
    from .notifications import requester_enabled
    row = _booking(envelope)
    if row is None:
        return False
    if envelope.audience == "requester":
        return row.member_id == envelope.recipient_id and requester_enabled(row, envelope.event)
    return envelope.audience == "staff"


def grant_eligible(envelope):
    from .booking_authority import can
    row = _booking(envelope)
    return bool(row and envelope.audience == "member" and can(envelope.recipient, row.space, "manage_reservations"))


def reminder_eligible(envelope):
    from .communication_recipients import notification_account
    from .notifications import _effective_toggle
    from apps.makerspaces.reminder_policy import reminder_offsets
    row = _booking(envelope)
    return bool(row and envelope.audience == "requester" and row.member_id == envelope.recipient_id
                and row.status == Booking.Status.CONFIRMED and row.starts_at > timezone.now()
                and _effective_toggle(row)
                and type(envelope.context.get("offset_seconds")) is int
                and envelope.context["offset_seconds"] in reminder_offsets(row.space.makerspace, "booking")
                and type(envelope.context.get("booking_id")) is int
                and envelope.context["booking_id"] == row.pk
                and notification_account(row.space.makerspace, row.member_id, "reminder") is not None)


def broadcast_eligible(envelope):
    from rest_framework.exceptions import APIException
    from .broadcasts import bookings, campaign_enabled
    from .communication_recipients import notification_account
    from .models_broadcasts import BookingBroadcast
    campaign = BookingBroadcast.objects.select_related("space__makerspace", "created_by").filter(
        pk=envelope.source_id if str(envelope.source_id).isdecimal() else 0, makerspace_id=envelope.makerspace_id,
    ).first()
    if campaign is None or campaign.status not in ("queued", "sending", "sent"):
        return False
    try:
        from .broadcasts import authorize
        authorize(campaign, campaign.created_by)  # the original sender's authority, live
    except APIException:
        return False
    return bool(campaign_enabled(campaign) and bookings(campaign).filter(member_id=envelope.recipient_id).exists()
                and notification_account(campaign.makerspace, envelope.recipient_id, "broadcast") is not None)


def register_notification_sources():
    from .notification_guest_mail import register_guest_mailbox
    register_guest_mailbox()
    from .notifications import GRANT_SOURCE, LIFECYCLE_SOURCE
    register_source(LIFECYCLE_SOURCE, NotificationSource(lifecycle_eligible))
    register_source(GRANT_SOURCE, NotificationSource(grant_eligible))
    register_source(REMINDER_SOURCE, NotificationSource(reminder_eligible))
    register_source(BROADCAST_SOURCE, NotificationSource(broadcast_eligible))
    from .organization_hours_notice import register as register_hours_bank
    register_hours_bank()
