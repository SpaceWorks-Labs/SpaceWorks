"""#169 / L3 contract: confirmation emails carry an .ics invite (stable UID, SEQUENCE, CANCEL),
add-to-calendar links and the ticket PDF; the private join link never rides the invite."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from icalendar import Calendar

from apps.events import registration_invites as invites
from apps.events.services_calendar import calendar_event_changed, calendar_registration_changed
from apps.integrations.inline_attachments import InlineAttachment
from apps.integrations.notification_attachment_sources import AttachmentReference
from tests.events.ticketing_helpers import event_space, open_event, signup
from tests.events.orders_helpers import verified

pytestmark = pytest.mark.django_db

SECRET = "https://meet.example.test/private-room-42"


def _entry(data):
    calendar = Calendar.from_ical(data)
    return calendar, next(component for component in calendar.walk("VEVENT"))


def _registration():
    space = event_space("invites")
    event = open_event(space, location="Main hall")
    user = verified("guest")
    assert signup(event, user).status_code == 201
    return user.event_registrations.select_related("event__makerspace").get()


def test_invite_uid_sequence_and_cancel(monkeypatch):
    monkeypatch.setattr("apps.events.online_delivery.join_url_for", lambda registration: SECRET)
    registration = _registration()
    calendar, entry = _entry(invites.invite_bytes(registration))
    assert str(calendar["METHOD"]) == "PUBLISH"
    assert str(entry["UID"]) == f"event-{registration.event.calendar_uid}-r{registration.pk}@spaceworks"
    first = int(entry["SEQUENCE"])
    assert SECRET not in invites.invite_bytes(registration).decode()
    assert SECRET not in str(invites.links(registration))
    event = registration.event
    event.starts_at = event.starts_at + timedelta(hours=1)
    event.save(update_fields=["starts_at"])
    calendar_event_changed(event)
    registration.refresh_from_db()
    _calendar, moved = _entry(invites.invite_bytes(registration))
    assert int(moved["SEQUENCE"]) > first and str(moved["UID"]) == str(entry["UID"])
    calendar_registration_changed(registration)
    cancelled_calendar, cancelled = _entry(invites.invite_bytes(registration, cancel=True))
    assert str(cancelled_calendar["METHOD"]) == "CANCEL" and str(cancelled["STATUS"]) == "CANCELLED"


def test_confirmation_attachments_and_links(monkeypatch):
    registration = _registration()
    envelope = SimpleNamespace(audience="requester", event="registration_created", recipient_id=registration.member_id,
                               context={"registration_id": registration.pk}, source_kind="events.lifecycle", pk=1)
    items = invites.attachments(envelope)
    assert len(items) == 1 and isinstance(items[0], InlineAttachment) and "method=PUBLISH" in items[0].mimetype
    monkeypatch.setattr(invites, "_tickets_on", lambda row: True)
    items = invites.attachments(envelope)
    assert isinstance(items[1], AttachmentReference) and items[1].source_kind == "events.ticket"
    cancelled = invites.attachments(SimpleNamespace(**{**envelope.__dict__, "event": "registration_cancelled"}))
    assert len(cancelled) == 1 and "method=CANCEL" in cancelled[0].mimetype
    stranger = invites.attachments(SimpleNamespace(**{**envelope.__dict__, "recipient_id": 999999}))
    assert stranger == ()
    rendered = invites.with_links({"subject": "s", "text": "Hello", "html": "<p>x</p>"}, "registration_created",
                                  registration)
    assert "calendar.google.com" in rendered["text"] and "outlook.live.com" in rendered["text"]


def test_booking_invite_uses_the_booking_uid():
    from apps.bookings import confirmation_invites
    booking = SimpleNamespace(public_token="abc", space=SimpleNamespace(name="Laser room", location="B2"),
                              starts_at=timezone.now(), ends_at=timezone.now() + timedelta(hours=1),
                              calendar_sequence=3, calendar_updated_at=timezone.now(), status="confirmed")
    _calendar, entry = _entry(confirmation_invites.invite_bytes(booking))
    assert str(entry["UID"]) == "booking-abc@spaceworks" and int(entry["SEQUENCE"]) == 3
    cancel_calendar, _entry_cancel = _entry(confirmation_invites.invite_bytes(booking, cancel=True))
    assert str(cancel_calendar["METHOD"]) == "CANCEL"
