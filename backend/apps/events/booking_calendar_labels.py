"""Which bookings hold a room for a linked event, labelled for one viewer (decision 216).

Read-only. A booking belongs to an event when it is the event's retained decision booking, one
of its workshop machine links (P2-1, `EventMachineBookingLink`), or a replacement descending
from either (`Booking.replaces`, walked back at most `MAX_CHAIN` steps).
The event's title and status are shown only to a viewer who may see that event
(`event_authority.can(..., VIEW)`); anyone else gets the generic `reserved` label, so a
linked reservation never leaks an event the viewer cannot open. Bookings imports this
lazily, only while the events app is installed and the space's `events` module is on.
"""

from . import event_authority, event_permissions
from .booking_decision_replacement import MAX_CHAIN
from .models_booking_decision import EventBookingDecision
from .models_machine_booking_link import EventMachineBookingLink


def _roots(booking_ids):
    """Map each booking to the first booking of its replacement chain."""
    from apps.bookings.models import Booking
    roots = {pk: pk for pk in booking_ids}
    parents = dict(Booking.objects.filter(pk__in=booking_ids, replaces__isnull=False)
                   .values_list("pk", "replaces_id"))
    for _step in range(MAX_CHAIN):
        if not parents:
            break
        for pk, parent in parents.items():
            for child, root in roots.items():
                if root == pk:
                    roots[child] = parent
        parents = dict(Booking.objects.filter(pk__in=set(parents.values()), replaces__isnull=False)
                       .values_list("pk", "replaces_id"))
    return roots


def linked_event_labels(actor, makerspace, booking_ids):
    """{booking_id: label} for the given bookings that hold a room for an event."""
    booking_ids = [pk for pk in booking_ids if pk]
    if not booking_ids:
        return {}
    roots = _roots(booking_ids)
    decisions = {row.booking_id: row.event for row in EventBookingDecision.objects.filter(
        makerspace_id=makerspace.pk, booking_id__in=set(roots.values())).select_related("event__makerspace")}
    decisions.update({row.booking_id: row.event for row in EventMachineBookingLink.objects.filter(
        makerspace_id=makerspace.pk, booking_id__in=set(roots.values()), unlinked_at__isnull=True).select_related("event__makerspace")})
    labels, visible = {}, {}
    for pk, root in roots.items():
        event = decisions.get(root)
        if event is None:
            continue
        if event.pk not in visible:
            visible[event.pk] = event_authority.can(actor, event, event_permissions.VIEW)
        labels[pk] = ({"kind": "event", "event_id": event.pk, "title": event.title, "event_status": event.status}
                      if visible[event.pk] else {"kind": "reserved"})
    return labels
