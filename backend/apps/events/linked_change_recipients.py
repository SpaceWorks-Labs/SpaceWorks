"""The extra audiences of a linked-event booking notice (decision 221(f)).

`linked_change_notices.notify_linked_booking` reaches the booker and the space's booking
staff. Two more people must hear that the event a room booking holds moved or was cancelled:

* per-room grant holders -- accounts holding `manage_reservations` on THAT room through a
  `BookingSpaceStaffGrant`, who are not tenant staff. They get the staff wording (no event
  title, no booker) as `audience="member"`; `grant_eligible` re-checks the live grant;
* an account-less guest booker, by one email to the booking's own contact address, gated by
  the room's requester toggle and the bookings requester selection, deduplicated per event
  version. A guest has no account, so no chat or personal channel can apply.
"""

from apps.integrations.notification_outbox import emit
from apps.operations.notifications_p2 import direct_mail_unless_routed

GRANT_SOURCE = "events.linked_booking_notice_grant"
GUEST_SOURCE = "events.linked_booking_notice_guest"


def notify_grant_holders(booking, *, event_name, version, rendered, context):
    from apps.accounts.models import User
    from apps.bookings.notifications import grant_recipient_ids
    from apps.integrations.staff_notifications import staff_user_ids_for_feature
    space = booking.space.makerspace
    staff_ids = set(staff_user_ids_for_feature(space, "bookings", event_name))
    people = User.objects.filter(pk__in=grant_recipient_ids(booking.space) - staff_ids - {booking.member_id},
                                 is_active=True, access_status="active").order_by("pk")
    for person in people:
        emit(makerspace=space, recipient=person, feature="bookings", stream="bookings", event=event_name,
             audience="member", dedup_key=f"ev:linked-event-grant:{booking.pk}:{version}:{person.pk}",
             source_kind=GRANT_SOURCE, source_id=str(booking.pk), revision=version, subject=booking,
             context=context, rendered=rendered)


def notify_guest(booking, *, event_name, version, subject, text):
    from apps.bookings.notifications import _effective_toggle
    from apps.integrations.recipients import has_selection, requester_selected
    space = booking.space.makerspace
    if booking.member_id is not None or not booking.email or not _effective_toggle(booking):
        return None
    if has_selection(space, "bookings", event_name) and not requester_selected(space, "bookings", event_name):
        return None
    return direct_mail_unless_routed(space=space, source_kind=GUEST_SOURCE, row=booking, revision=version,
                                     event=event_name, owner=None, to_email=booking.email, subject=subject,
                                     text=text, stream="bookings", audience="requester", feature="bookings",
                                     address_owner=False)


def grant_eligible(envelope):
    from apps.bookings.booking_authority import can
    from .linked_change_notices import booking_notice_eligible
    if envelope.audience != "member" or not booking_notice_eligible(envelope, grant=True):
        return False
    from apps.bookings.models import Booking
    booking = Booking.objects.select_related("space").filter(pk=envelope.source_id).first()
    return bool(booking and can(envelope.recipient, booking.space, "manage_reservations"))
