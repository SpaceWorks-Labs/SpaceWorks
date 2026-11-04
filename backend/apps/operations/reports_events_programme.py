"""Counts-only event funnel and bounded local-date signup timeline."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.events.models import Event, EventRegistration
from apps.events.capacity import confirmed_occupancy, spots_left
from apps.events.models_feedback import EventFeedbackResponse
from apps.events.programme.providers import Respondent, application_respondents
from apps.operations.report_scope import scoped_ids
from apps.operations.report_types import ReportResult


FIELDS = ("event_id", "generated_at", "timezone_name", "stages", "timeline", "capacity", "caveat", "reading", "hint")


def percentage(numerator, denominator):
    return min(100.0, round(numerator * 100 / denominator, 2)) if denominator else None


def _registrants(event, *, since=None, until=None):
    rows = EventRegistration.objects.filter(event=event)
    if since:
        rows = rows.filter(created_at__gte=since)
    if until:
        rows = rows.filter(created_at__lt=until)
    return [Respondent(key=("member", member_id) if member_id else ("registration", pk), submitted_at=created)
            for pk, member_id, created in rows.values_list("pk", "member_id", "created_at")]


def _dedupe(rows):
    result = {}
    for row in rows:
        if row.key not in result or row.submitted_at < result[row.key]:
            result[row.key] = row.submitted_at
    return result


def project_funnel(event, *, actor=None, now=None):
    """Report runner supplies the resolved event scope; actor adds a direct-service gate."""
    if actor is not None:
        from apps.events import event_authority
        event_authority.require(actor, event, None)
    now = now or timezone.now()
    zone = ZoneInfo(event.timezone_name)
    today = now.astimezone(zone).date()
    first = today - timedelta(days=13)
    previous_first = first - timedelta(days=14)
    start = datetime.combine(previous_first, time.min, tzinfo=zone)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
    domain = application_respondents(event=event, actor=actor, since=None, until=end)
    ordinary = _registrants(event, until=end)
    # A returns real submitted applications, never virtual drafts or practice data.
    is_hackathon, applications = domain if domain is not None else (False, ())
    responded = _dedupe([*ordinary, *applications] if is_hackathon else ordinary)
    going_rows = event.registrations.filter(status__in=("registered", "attended"))
    going = _dedupe(Respondent(key=("member", member) if member else ("registration", pk), submitted_at=created)
                    for pk, member, created in going_rows.values_list("pk", "member_id", "created_at"))
    attended_rows = event.registrations.filter(status="attended")
    checked = _dedupe(Respondent(key=("member", member) if member else ("registration", pk), submitted_at=created)
                      for pk, member, created in attended_rows.values_list("pk", "member_id", "created_at"))
    feedback = EventFeedbackResponse.objects.filter(
        survey__event=event, registration__event=event, registration__status="attended",
    ).values("registration_id").distinct().count()
    stages = []
    for key, label, count, denominator in (
        ("responded", "Responded", len(responded), None),
        ("going", "Going", len(going), len(responded)),
        ("checked_in", "Checked in", len(checked), len(going)),
        ("feedback", "Feedback", feedback, len(checked)),
    ):
        stages.append({"key": key, "label": label, "count": count, "denominator": denominator,
                       "percent": percentage(count, denominator) if denominator is not None else None})
    dates = {}
    for at in responded.values():
        if start <= at < end:
            day = at.astimezone(zone).date()
            dates[day] = dates.get(day, 0) + 1
    timeline = [{"date": (first + timedelta(days=index)).isoformat(),
                 "count": dates.get(first + timedelta(days=index), 0),
                 "previous_count": dates.get(previous_first + timedelta(days=index), 0)} for index in range(14)]
    occupancy = confirmed_occupancy(event)
    capacity = {"limit": event.capacity, "going": occupancy,
                "remaining": spots_left(event),
                "state": "unlimited" if not event.capacity else (
                    "over_capacity" if occupancy > event.capacity else "full" if occupancy == event.capacity else "available")}
    caveat = "Current registration states; anonymous feedback cannot be attributed and is excluded. Shares are capped at 100%."
    if domain is None:
        caveat += " Application funnel integration is unavailable; responded currently counts registrations only."
    return {"event_id": event.pk, "generated_at": now, "timezone_name": event.timezone_name,
            "stages": stages, "timeline": timeline, "capacity": capacity, "caveat": caveat,
            "reading": f"{len(checked)} of {len(going)} going participants are currently checked in.",
            "hint": "Compare the two local-date periods before changing your outreach."}


def build_event_programme(makerspace_id, *, limit=None, date_range=None, subject_kind=None, subject_id=None):
    """Tenant/event-only report adapter; G registers it with existing subject authorization."""
    if makerspace_id is None or subject_kind != "event" or subject_id is None:
        raise ValidationError("An event funnel requires one tenant and an event subject.")
    event = Event.objects.filter(makerspace_id__in=scoped_ids(makerspace_id, "events"), pk=subject_id).first()
    if event is None:
        from rest_framework.exceptions import NotFound
        raise NotFound()
    return ReportResult(FIELDS, [project_funnel(event)])
