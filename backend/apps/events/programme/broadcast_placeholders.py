"""The one data-only placeholder context every broadcast render uses (send, preview, test).

Values are public navigation or display text only: no bearer, check-in token or contact
detail is ever a placeholder. `organization` names the first active co-hosting
organisation, else the venue makerspace.
"""

from apps.makerspaces.website_directory import public_url


def organizer_name(event):
    from apps.events.organizer_models import EventOrganizer
    name = (EventOrganizer.objects.filter(event=event, organization__is_active=True)
            .order_by("created_at", "pk").values_list("organization__name", flat=True).first())
    return name or event.makerspace.name


def _site(event, page):
    # The event website lives under /events/<token>/<page> (custom domain) or
    # /m/<slug>/events/<token>/<page>; the "events" kind alone maps to the short /e/ path.
    return public_url(event.makerspace, f"events/{event.public_token}", page)


def placeholder_context(event, *, name, ticket_url):
    return {
        "name": name, "event_title": event.title, "event_date": event.starts_at.isoformat(),
        "event_location": event.location, "ticket_url": ticket_url,
        "event_url": public_url(event.makerspace, "events", str(event.public_token)),
        "feedback_url": _site(event, "feedback"), "schedule_url": _site(event, "schedule"),
        "organization": organizer_name(event),
    }
