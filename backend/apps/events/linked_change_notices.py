"""An event moved or was cancelled: tell its linked booking and loans (decision 216).

Nothing is changed by these notices. The linked room booking keeps its time, status and
charge, and a linked loan keeps its due date; the notices only ask people to review:

* `bookings.linked_event_changed` reaches the booker of the event's CURRENT reservation (the
  tail of the decision's replacement chain) and the space's booking staff and rooms. The copy
  never names the event: a booking manager may not be allowed to see it
  (`booking_calendar_labels`);
* `hardware_requests.linked_event_changed` reaches each borrower whose open loan is linked to
  the event (`EventLoanContext`), saying the due date is unchanged unless staff change it.

Registrants already hear through the existing event notices (the `registration_updated`
invite on a reschedule, the `cancelled` owner fan-out), so nothing is added for them. Silent
while Events or the target module is off; one notice per event version, re-checked at send.
"""

from django.utils.translation import gettext, gettext_noop
from apps.hardware_requests.notifications_p2 import fanout as loan_fanout, safe_adapter
from apps.integrations.notification_links import local_link
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.operations.notifications_p2 import body, fanout, revision, safe_notification, staff_link

BOOKING_SOURCE = "events.linked_booking_notice"
LOAN_SOURCE = "events.linked_loan_notice"
EVENT = "linked_event_changed"
WORDS = {"moved": gettext_noop("was rescheduled"), "cancelled": gettext_noop("was cancelled")}
ACTIVE_BOOKINGS = ("pending", "confirmed")
OPEN_LOANS = ("pending_approval", "accepted", "issued", "partially_returned")
MAX_LOANS = 500


def _on(space, module):
    return is_servable(space) and module_enabled(space, "events") and module_enabled(space, module)


def _revision(event, change):
    return revision("Event", event.pk, change, event.version)


def current_booking(event):
    """The event's current reservation (the replacement chain's tail), or None."""
    from apps.bookings.models import Booking
    from .booking_decision_replacement import MAX_CHAIN
    from .models_booking_decision import EventBookingDecision
    booking_id = EventBookingDecision.objects.filter(
        event_id=event.pk, makerspace_id=event.makerspace_id).values_list("booking_id", flat=True).first()
    if booking_id is None:
        return None
    for _step in range(MAX_CHAIN):
        following = Booking.objects.filter(replaces_id=booking_id).values_list("pk", flat=True).first()
        if following is None:
            break
        booking_id = following
    else:
        return None  # an unbounded chain is for staff review, never a notice
    return Booking.objects.select_related("space__makerspace", "member").filter(
        pk=booking_id, space__makerspace_id=event.makerspace_id).first()


def _change_current(event, change):
    if change == "cancelled":
        return event.status == event.Status.CANCELLED
    return change == "moved" and event.status in (event.Status.DRAFT, event.Status.PUBLISHED)


@safe_notification
def notify_linked_booking(event, change):
    space = event.makerspace
    if change not in WORDS or not _on(space, "bookings"):
        return None
    booking = current_booking(event)
    if booking is None or booking.status not in ACTIVE_BOOKINGS:
        return None
    what, room = gettext(WORDS[change]), booking.space.name
    values = {"what": what, "room": room, "id": booking.pk}
    subject = gettext("A linked event %(what)s: booking #%(id)s") % values
    staff_text = gettext(
        "Booking #%(id)s in %(room)s holds the room for an event that %(what)s. "
        "The room booking was not changed. Review it in Bookings."
    ) % values
    owner_text = gettext(
        "The event your booking #%(id)s in %(room)s is for %(what)s. Your room booking was "
        "not changed. Review it, and contact the space if it should change."
    ) % values
    link = staff_link(space, f"bookings?space={booking.space_id}&booking={booking.pk}&bookingTab=requests")
    version, context = _revision(event, change), {"booking_id": booking.pk, "event_id": event.pk, "change": change}
    result = fanout(row=booking, space=space, feature="bookings", stream="bookings", event=EVENT,
                    source_kind=BOOKING_SOURCE, revision=version, owner=booking.member,
                    owner_body=body(subject, owner_text, local_link(space, "member", "bookings")) if booking.member_id
                    else None, staff_body=body(subject, staff_text, link),
                    context=context, staff_context={"booking_id": booking.pk})
    # Decision 221(f): the room's own grant holders and an account-less guest booker hear too.
    from .linked_change_recipients import notify_grant_holders, notify_guest
    notify_grant_holders(booking, event_name=EVENT, version=version, rendered=body(subject, staff_text, link),
                         context=context)
    notify_guest(booking, event_name=EVENT, version=version, subject=subject, text=owner_text)
    return result


@safe_adapter
def _loan_notice(row, event, change):
    request, space = row.request, event.makerspace
    subject = f"The event for your loan #{request.pk} {WORDS[change].split()[-1]}"
    text = (f"The event your loan #{request.pk} is linked to {WORDS[change]}. Your due date has not "
            "changed; the space will tell you if it does.")
    return loan_fanout(space=space, feature="hardware_requests", stream="hardware", event=EVENT, kind=LOAN_SOURCE,
                       source=str(row.pk), version=_revision(event, change), subject=row, owner=request.requester,
                       own=body(subject, text, local_link(space, "member")),
                       context={"loan_context_id": row.pk, "request_id": request.pk, "event_id": event.pk,
                                "change": change})


def notify_linked_loans(event, change):
    from .models_loan_context import EventLoanContext
    space = event.makerspace
    if change not in WORDS or not _on(space, "request_workflow"):
        return 0
    rows = (EventLoanContext.objects.filter(makerspace_id=space.pk, event_id=event.pk, active=True,
                                            request__status__in=OPEN_LOANS)
            .select_related("request__requester").order_by("pk")[:MAX_LOANS])
    return sum(1 for row in rows if _loan_notice(row, event, change))


def event_changed(event, change):
    """Inside the event's write transaction, after a time change ("moved") or cancellation."""
    notify_linked_booking(event, change)
    notify_linked_loans(event, change)


def _event(envelope):
    from .models import Event
    return Event.objects.select_related("makerspace").filter(
        pk=envelope.context.get("event_id"), makerspace_id=envelope.makerspace_id).first()


def booking_notice_eligible(envelope, *, grant=False):
    event = _event(envelope)
    if (event is None or envelope.event != EVENT or not _on(event.makerspace, "bookings")
            or not _change_current(event, envelope.context.get("change"))):
        return False
    booking = current_booking(event)
    if booking is None or str(booking.pk) != str(envelope.source_id) or booking.status not in ACTIVE_BOOKINGS:
        return False
    if grant:  # the grant source re-checks the live room grant itself
        return envelope.audience == "member"
    if envelope.audience == "requester":
        return booking.member_id == envelope.recipient_id
    return envelope.audience == "staff"  # the shared layer re-checks booking staff scope


def loan_notice_eligible(envelope):
    from .models_loan_context import EventLoanContext
    event = _event(envelope)
    if (event is None or envelope.event != EVENT or envelope.audience != "requester"
            or not _on(event.makerspace, "request_workflow")
            or not _change_current(event, envelope.context.get("change"))):
        return False
    row = EventLoanContext.objects.select_related("request").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id, event_id=event.pk, active=True).first()
    return bool(row and row.request.requester_id == envelope.recipient_id and row.request.status in OPEN_LOANS)


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(BOOKING_SOURCE, NotificationSource(booking_notice_eligible))
    register_source(LOAN_SOURCE, NotificationSource(loan_notice_eligible))
    from .linked_change_recipients import GRANT_SOURCE, grant_eligible
    register_source(GRANT_SOURCE, NotificationSource(grant_eligible))
