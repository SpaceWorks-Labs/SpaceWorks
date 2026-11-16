"""Deterministic D/E report fixtures; no external providers."""

from datetime import datetime, timedelta, timezone
import json

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event, EventRegistration, EventCheckInEvent, EventFeedbackSurvey, EventFeedbackResponse
from apps.payments.models import Payment
from tests.return_helpers import make_member, make_space

AT = datetime(2026, 10, 12, 10, tzinfo=timezone.utc)
BOUNDS = (AT.replace(hour=0), AT.replace(hour=0) + timedelta(days=2))
BOOKING_KEYS = ("booking-utilization", "booking-occupancy", "booking-lead-time", "booking-top-members")
EVENT_KEYS = ("event-signups", "event-revenue", "event-funnel", "event-checkin-times", "event-feedback-scores")
KEYS = BOOKING_KEYS + EVENT_KEYS


def setup(slug):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules) | {"reports", "bookings", "events"})
    space.timezone = "UTC"
    space.save(update_fields=["enabled_modules", "timezone"])
    actor = make_member(f"{slug}-manager", space)
    return space, actor


def booking(space, actor, *, start=AT, end=None, status="completed", created=None):
    resource = BookableSpace.objects.create(makerspace=space, name="Bench")
    row = Booking.objects.create(space=resource, member=actor, name="Private person", email=f"b{resource.pk}@example.com",
                                 phone="123", starts_at=start, ends_at=end or start + timedelta(hours=1), status=status)
    Booking.objects.filter(pk=row.pk).update(created_at=created or start - timedelta(days=2))
    return row


def event(space, title="Workshop"):
    return Event.objects.create(makerspace=space, title=title, starts_at=AT, ends_at=AT + timedelta(hours=2))


def registration(event, actor, *, at=AT, status="registered", discount="2.00"):
    row = EventRegistration.objects.create(event=event, member=actor, name="Private attendee",
                                           email=f"r{event.pk}-{actor.pk}-{status}@example.com", phone="123",
                                           status=status, discount_amount=discount)
    EventRegistration.objects.filter(pk=row.pk).update(created_at=at)
    return row


def checkin(reg, at=AT):
    return EventCheckInEvent.objects.create(makerspace=reg.event.makerspace, event=reg.event, registration=reg,
                                            source="qr", actor=reg.member, attended_at=at)


def feedback(event, score="4"):
    survey = EventFeedbackSurvey.objects.create(event=event, title="Feedback", questions=[
        {"id": "score", "label": "Score", "type": "number", "options": [], "required": False},
    ])
    row = EventFeedbackResponse.objects.create(survey=survey, answers_snapshot=json.dumps({"version": 1, "answers": [
        {"id": "score", "type": "number", "value": score, "label": "Private label"},
        {"id": "comment", "type": "paragraph", "value": "Private response"},
    ]}))
    # Immutable feedback rows cannot be backdated. Tests that need a creation range
    # use a current window; deterministic timing tests cover registrations/check-ins.
    return row


def payment(reg, actor, currency="usd", amount="10.00"):
    row = Payment.objects.create(makerspace=reg.event.makerspace, subject_type="event_registration", subject_id=reg.pk,
                                 member=actor, amount=amount, currency=currency, provider="unclaimed", created_by=actor)
    return row


def seed(space, actor):
    booking(space, actor)
    workshop = event(space)
    reg = registration(workshop, actor, status="attended")
    checkin(reg)
    feedback(workshop)
    payment(reg, actor)
    return workshop, reg
