"""`bookings.room_outage`: a room was taken out of service over existing bookings (#93).

Through the notification pipeline, never a direct send to an account:

* each affected booker with an account gets their own envelope naming the room, the window
  and their own booking number -- nobody else's;
* the space's booking staff (and their rooms) get ONE summary per outage: the room and how
  many bookings fall inside it, never who made them. Staff then cancel or keep each one.

Account-less guest bookers keep the direct email in `notify.bookers_outage`. Every envelope is
re-checked at send: the outage must still be open, the booking still affected and still the
recipient's, Bookings on (plus the room repairs or maintenance switch, `EVENT_SOURCES`).
"""

from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.notification_links import local_link
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.operations.notifications_p2 import staff_link

SOURCE = "maintenance.room_outage"
EVENT = "room_outage"


def _on(space):
    return is_servable(space) and module_enabled(space, "bookings")


def _staff_version(outage):
    return revision("RoomOutage", outage.pk, "staff")


def _booker_version(outage, booking):
    return revision("RoomOutage", outage.pk, "booker", booking.pk)


def _back(outage):
    return f" It is expected back {outage.expected_back_at:%Y-%m-%d %H:%M}." if outage.expected_back_at else ""


@safe_adapter
def staff_notice(outage, bookings):
    space, room = outage.makerspace, outage.room
    if not _on(space):
        return None
    count = len(bookings)
    text = (f"{room.name} is out of service.{_back(outage)} {count} booking{'s' if count != 1 else ''} "
            "fall in this time. Review each one in Bookings: cancel it or keep it.")
    return fanout(space=space, feature="bookings", stream="bookings", event=EVENT, kind=SOURCE,
                  source=str(outage.pk), version=_staff_version(outage), subject=outage,
                  staff={"subject": f"{room.name} is out of service"[:200], "text": text, "html": "",
                         "link": staff_link(space, f"bookings?space={room.pk}")},
                  context={"outage_id": outage.pk, "space_id": room.pk}, staff_context={"space_id": room.pk})


@safe_adapter
def booker_notice(outage, booking):
    space, room = outage.makerspace, outage.room
    if not _on(space) or booking.member is None:
        return None
    text = (f"{room.name} at {space.name} is out of service.{_back(outage)}\n\n"
            f"Your booking #{booking.pk} falls in this time. The space will contact you about it.")
    return fanout(space=space, feature="bookings", stream="bookings", event=EVENT, kind=SOURCE,
                  source=str(outage.pk), version=_booker_version(outage, booking), subject=booking,
                  owner=booking.member, own={"subject": f"{room.name} is out of service"[:200], "text": text,
                                             "html": "", "link": local_link(space, "member", "bookings")},
                  context={"outage_id": outage.pk, "booking_id": booking.pk, "space_id": room.pk})


def eligible(envelope):
    from apps.maintenance.models import RoomOutage
    from .room_outages import affected_bookings
    outage = RoomOutage.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id, ended_at__isnull=True).first()
    if outage is None or envelope.event != EVENT or not _on(outage.makerspace):
        return False
    if envelope.audience == "staff":
        return envelope.revision == _staff_version(outage)
    if envelope.audience != "requester":
        return False
    booking = affected_bookings(outage).filter(pk=envelope.context.get("booking_id")).first()
    return bool(booking and booking.member_id == envelope.recipient_id
                and envelope.revision == _booker_version(outage, booking))


def register():
    from apps.integrations.notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(eligible))
