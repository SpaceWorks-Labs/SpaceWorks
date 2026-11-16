from datetime import timedelta

from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.integrations.models_contract import NotificationEnvelope
from tests.events.collab_helpers import client_for, make_member, make_staff
from tests.events.ticketing_helpers import account, event_space


def space(slug, **kwargs):
    return event_space(slug, **kwargs)


def event(space_row, *, status="published", days=1, **values):
    starts = timezone.now() + timedelta(days=days)
    return Event.objects.create(makerspace=space_row, title=values.pop("title", "Workshop"), status=status,
                                starts_at=starts, ends_at=starts + timedelta(hours=2), is_public=True,
                                registration_audience=values.pop("registration_audience", "accounts"), **values)


def registration(event_row, user, status="registered"):
    return EventRegistration.objects.create(event=event_row, member=user, name=user.username,
                                            email=user.email, phone="1", status=status,
                                            registered_via_makerspace=event_row.makerspace)


def envelopes(**filters):
    # Legacy room/matrix reservations ("legacy.lifecycle", no recipient) are not personal intents.
    return NotificationEnvelope.objects.exclude(source_kind="legacy.lifecycle").filter(**filters)


__all__ = ["account", "client_for", "envelopes", "event", "make_member", "make_staff", "registration", "space"]
