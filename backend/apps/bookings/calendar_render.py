"""One RFC 5545 serializer for authenticated downloads and subscription feeds."""
from icalendar import Calendar, Event


def booking_calendar(rows, extra=()):
    """`extra` carries ready-made components, e.g. the feed's busy blocks (`busy_overlay_ics`)."""
    calendar = Calendar()
    calendar.add("prodid", "-//SpaceWorks//Bookings//EN")
    calendar.add("version", "2.0")
    rows = list(rows)
    from apps.bookings.organization_booking import organization_names
    organizations = organization_names(booking.pk for booking in rows)  # decision 223 (k)
    for booking in rows:
        event = Event()
        event.add("uid", f"booking-{booking.public_token}@spaceworks")
        event.add("dtstamp", booking.calendar_updated_at)
        event.add("last-modified", booking.calendar_updated_at)
        event.add("sequence", booking.calendar_sequence)
        event.add("dtstart", booking.starts_at)
        event.add("dtend", booking.ends_at)
        organization = organizations.get(booking.pk)
        event.add("summary", f"{booking.space.name} ({organization})" if organization else booking.space.name)
        event.add("status", "CANCELLED" if booking.status in ("cancelled", "rejected") else
                  "TENTATIVE" if booking.status == "pending" else "CONFIRMED")
        calendar.add_component(event)
    for component in extra:
        calendar.add_component(component)
    return calendar.to_ical()
