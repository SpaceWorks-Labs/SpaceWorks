"""One RFC 5545 serializer for authenticated downloads and subscription feeds."""
from icalendar import Calendar, Event


def booking_calendar(rows):
    calendar = Calendar()
    calendar.add("prodid", "-//SpaceWorks//Bookings//EN")
    calendar.add("version", "2.0")
    for booking in rows:
        event = Event()
        event.add("uid", f"booking-{booking.public_token}@spaceworks")
        event.add("dtstamp", booking.calendar_updated_at)
        event.add("last-modified", booking.calendar_updated_at)
        event.add("sequence", booking.calendar_sequence)
        event.add("dtstart", booking.starts_at)
        event.add("dtend", booking.ends_at)
        event.add("summary", booking.space.name)
        event.add("status", "CANCELLED" if booking.status in ("cancelled", "rejected") else
                  "TENTATIVE" if booking.status == "pending" else "CONFIRMED")
        calendar.add_component(event)
    return calendar.to_ical()
