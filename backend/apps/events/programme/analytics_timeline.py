"""Event analytics over time (parity E-B7): sign-ups per day, adaptive arrival windows, written-answer counts.

Counts only. A person, an answer's text and a registration id never leave this module.
"""

import json
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count
from django.db.models.functions import TruncDate

WINDOW_CHOICES = (15, 30, 60, 120, 240, 480)  # minutes; 15 minutes up to 8 hours
TARGET_BUCKETS = 48
WRITTEN_TYPES = frozenset({"short_text", "paragraph"})


def window_minutes_for(span_minutes):
    """The smallest window that keeps the arrival chart within about 48 bars (15 min to 8 h)."""
    for window in WINDOW_CHOICES:
        if span_minutes / window <= TARGET_BUCKETS:
            return window
    return WINDOW_CHOICES[-1]


def bucket_start(local, window):
    """Floor a local datetime to a window measured from that local day's midnight."""
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes = int((local - midnight).total_seconds() // 60)
    return midnight + timedelta(minutes=minutes - minutes % window)


def arrival_windows(first_checkins, zone):
    """Bucket first check-in instants into adaptive local windows; returns (timeline, window_minutes)."""
    locals_ = [at.astimezone(zone) for at in first_checkins]
    if not locals_:
        return [], WINDOW_CHOICES[0]
    span = (max(locals_) - min(locals_)).total_seconds() / 60
    window = window_minutes_for(span)
    counts = {}
    for local in locals_:
        start = bucket_start(local, window)
        counts[start] = counts.get(start, 0) + 1
    return [{"window_start": start, "count": counts[start]} for start in sorted(counts)], window


def signups_by_day(event):
    """Registrations created per local day (crew excluded; later cancellations still count as sign-ups)."""
    zone = ZoneInfo(event.timezone_name)
    rows = (event.registrations.filter(is_crew=False)
            .annotate(day=TruncDate("created_at", tzinfo=zone)).values("day")
            .annotate(count=Count("pk")).order_by("day"))
    return [{"day": row["day"], "count": row["count"]} for row in rows]


def written_answer_counts(event):
    """For each short-text or paragraph feedback question, how many people wrote something. Text is never read out."""
    from apps.events.models_feedback import EventFeedbackSurvey
    survey = EventFeedbackSurvey.objects.filter(event=event).first()
    if survey is None:
        return []
    questions = {question["id"]: question for question in survey.questions if question.get("type") in WRITTEN_TYPES}
    counts = {question_id: 0 for question_id in questions}
    for snapshot in survey.responses.only("answers_snapshot").iterator():
        try:
            parsed = json.loads(snapshot.answers_snapshot)
        except (TypeError, ValueError):
            continue
        for answer in parsed.get("answers", []) if isinstance(parsed, dict) else []:
            if not isinstance(answer, dict) or answer.get("id") not in counts:
                continue
            value = answer.get("value")
            if isinstance(value, str) and value.strip():
                counts[answer["id"]] += 1
    return [{"question_id": qid, "label": questions[qid].get("label", ""), "type": questions[qid]["type"],
             "answered": counts[qid]} for qid in questions]
