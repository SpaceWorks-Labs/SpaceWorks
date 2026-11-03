"""Calendar invites for confirmation emails (#169): one builder shared by events and bookings.

An invite is a one-entry iCalendar file so Google Calendar, Apple Calendar and Outlook
offer "Add". METHOD:PUBLISH with a UID that is stable for one registration or booking;
every change carries a higher SEQUENCE (the source's own calendar sequence), and a
cancellation is METHOD:CANCEL with the same UID and STATUS:CANCELLED. Callers pass only
fields they may show the recipient: a private join link never goes into an invite.
"""

from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from .confirmation_render import google_calendar_url


def invite_ics(*, uid, title, starts_at, ends_at, sequence, updated_at, cancel=False, tentative=False,
               description="", location="", alarms=None):
    from icalendar import Calendar, Event
    calendar = Calendar()
    calendar.add("prodid", "-//SpaceWorks//Invites//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "CANCEL" if cancel else "PUBLISH")
    entry = Event()
    entry.add("uid", uid)
    entry.add("summary", title)
    if description:
        entry.add("description", description)
    if location:
        entry.add("location", location)
    entry.add("dtstart", starts_at.astimezone(dt_timezone.utc))
    entry.add("dtend", ends_at.astimezone(dt_timezone.utc))
    entry.add("dtstamp", updated_at.astimezone(dt_timezone.utc))
    entry.add("last-modified", updated_at.astimezone(dt_timezone.utc))
    entry.add("sequence", int(sequence))
    entry.add("status", "CANCELLED" if cancel else "TENTATIVE" if tentative else "CONFIRMED")
    if alarms and not cancel:
        alarms(entry)
    calendar.add_component(entry)
    return calendar.to_ical()


def outlook_calendar_url(*, title, starts_at, ends_at, description="", location=""):
    def stamp(value):
        return value.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode({
        "path": "/calendar/action/compose", "rru": "addevent", "subject": title[:200],
        "startdt": stamp(starts_at), "enddt": stamp(ends_at), "body": description[:2000],
        "location": location[:255],
    })


def calendar_links(*, title, starts_at, ends_at, description="", location=""):
    return {"google": google_calendar_url(title=title, starts_at=starts_at, ends_at=ends_at,
                                          description=description, location=location),
            "outlook": outlook_calendar_url(title=title, starts_at=starts_at, ends_at=ends_at,
                                            description=description, location=location)}


def with_calendar_links(rendered, links):
    """Append "Add to Google Calendar" and "Add to Outlook" to a rendered message."""
    import html
    rendered = dict(rendered)
    rendered["text"] = (rendered.get("text", "").rstrip()
                        + f"\n\nAdd to Google Calendar: {links['google']}\nAdd to Outlook: {links['outlook']}\n")
    if rendered.get("html"):
        rendered["html"] += "".join(
            f'<p><a href="{html.escape(url, quote=True)}">{label}</a></p>'
            for label, url in (("Add to Google Calendar", links["google"]), ("Add to Outlook", links["outlook"])))
    return rendered
