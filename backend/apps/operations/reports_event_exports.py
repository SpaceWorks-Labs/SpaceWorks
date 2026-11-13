"""PII reads go through model accessors (including encrypted feedback snapshots)."""

import json
from apps.events.models import EventRegistration, EventFeedbackResponse
from .report_definitions_events import REGISTRATION_FIELDS, FEEDBACK_FIELDS
from .report_types import ReportResult


def _reply(row):
    reply = getattr(row, "attendance_reply", None)
    return reply.answer or "asked" if reply is not None else ""


def build_registrations(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    rows = EventRegistration.objects.filter(
        event_id=subject_id, event__makerspace_id=makerspace_id,
    ).select_related("event", "attendance_reply").order_by("pk")
    if date_range:
        start, end = date_range
        if start:
            rows = rows.filter(created_at__gte=start)
        if end:
            rows = rows.filter(created_at__lt=end)
    if limit is not None:
        rows = rows[:limit]
    return ReportResult(REGISTRATION_FIELDS, [{
        "crew": "yes" if row.is_crew else "", "attendance_reply": _reply(row),
        "registration_id": row.pk, "name": row.name, "email": row.email, "phone": row.phone,
        "status": row.status, "created_at": row.created_at,
        "answers": json.dumps(row.custom_answers, ensure_ascii=False),
    } for row in rows])


def build_feedback(makerspace_id, *, subject_kind, subject_id, limit=None, date_range=None):
    rows = EventFeedbackResponse.objects.filter(
        survey__event_id=subject_id, survey__event__makerspace_id=makerspace_id,
    ).select_related("survey__event").order_by("pk")
    if date_range:
        start, end = date_range
        if start:
            rows = rows.filter(created_at__gte=start)
        if end:
            rows = rows.filter(created_at__lt=end)
    if limit is not None:
        rows = rows[:limit]
    return ReportResult(FEEDBACK_FIELDS, [{
        "response_id": row.pk, "created_at": row.created_at, "registration_id": row.registration_id,
        "answers": json.dumps(json.loads(row.answers_snapshot), ensure_ascii=False),
    } for row in rows])
