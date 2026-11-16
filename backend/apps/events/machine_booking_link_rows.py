"""Read model for the event's "Workshop machines" list (P2-1). Read-only.

Each link is shown with the same reservation-status and replacement semantics as the room
link: the current reservation is the tail of the `Booking.replaces` chain, its state is
pending / confirmed / historical / unavailable, and only a rejected or cancelled tail is
replaceable. A link whose chain the viewer cannot authorize (booking or machine authority)
is withheld and only counted, never described. Advisory warnings (lockout, a lapsed
certification, repair) come from `bookings.admission_readiness`, which calls the admission
seams without writing.
"""
from django.http import Http404
from rest_framework.exceptions import NotFound

from .booking_decision_replacement import replaceable, reservation_chain
from .machine_booking_links import MAX_LINKS
from .machine_link_access import authorized_machine_booking, machine_of
from .models_machine_booking_link import EventMachineBookingLink
from .views_booking_decision import _reservation_state

LIVE = ("pending", "confirmed")


def _window(row):
    return {"starts_at": row.starts_at, "ends_at": row.ends_at}


def _warnings(actor, booking, state):
    if state not in LIVE:
        return []
    from apps.bookings.admission_readiness import OK, readiness
    checks = readiness(booking.space, member=booking.member, starts_at=booking.starts_at,
                       ends_at=booking.ends_at, actor=actor)["checks"]
    return [{"code": row["code"], "state": row["state"], "detail": row["detail"]}
            for row in checks if row["state"] != OK]


def link_row(actor, maker, event, link):
    if link.booking_id is None:
        return {"link_id": link.pk, "state": "booking_unavailable", "booking_id": None}
    chain = reservation_chain(actor, maker, link, authorize=authorized_machine_booking)
    current = chain[-1]
    machine = machine_of(current.space)
    state = _reservation_state(current)
    return {
        "link_id": link.pk, "state": "linked", "booking_id": link.booking_id,
        "current_booking_id": current.pk, "current_status": current.status,
        "current_space_id": current.space_id, "space_name": current.space.name,
        "machine_id": machine.pk if machine else None, "machine_name": machine.name if machine else "",
        "machine_type_id": machine.machine_type_id if machine else None,
        "booking_window": _window(current), "reservation_state": state,
        "replaceable": replaceable(event, current),
        "history": [{"booking_id": old.pk, "status": old.status} for old in chain[:-1]],
        "warnings": _warnings(actor, current, state),
        "conflicts": _conflicts(actor, event, current),
    }


def _conflicts(actor, event, booking):
    """Repair, outage and closure conflicts over the machine booking's own time (flagged only)."""
    if event.status not in (event.Status.DRAFT, event.Status.PUBLISHED):
        return []
    from .venue_conflicts import conflicts
    return conflicts(actor, booking, booking.starts_at, booking.ends_at)


def link_rows(actor, maker, event):
    """`(rows, withheld)` for the event's links the viewer may see, oldest first."""
    rows, withheld = [], 0
    links = EventMachineBookingLink.objects.filter(makerspace_id=maker.pk, event_id=event.pk,
                                                  unlinked_at__isnull=True).order_by("pk")
    for link in links[:MAX_LINKS]:
        try:
            rows.append(link_row(actor, maker, event, link))
        except (Http404, NotFound):
            withheld += 1
    return rows, withheld
