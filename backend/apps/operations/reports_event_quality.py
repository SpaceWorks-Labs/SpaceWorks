"""First recorded check-in timing and numeric feedback summaries only."""

import json
from decimal import Decimal, InvalidOperation

from apps.events.models import EventCheckInEvent, EventFeedbackResponse
from .reports_de_common import report_window as booking_window
from .reports_common import apply_range, period_expression
from .reports_de_common import source_spaces as report_spaces
from .report_fields_de import CHECKIN_FIELDS, FEEDBACK_FIELDS
from .reports_de_common import histogram_bucket, hours, result

CHECKIN_EDGES = (-60, -15, 0, 15, 60)
CHECKIN_LABELS = ("Over 60 minutes early", "15–60 minutes early", "Under 15 minutes early",
                  "0–15 minutes late", "15–60 minutes late", "Over 60 minutes late")


def build_event_checkin_times(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "events"):
        # Re-check-ins do not create a second attendee. Legacy imports have no reliable
        # scan time; exclude them instead of treating their migration time as arrival.
        # Earliest attended_at wins even when offline evidence reaches the server later.
        earliest = EventCheckInEvent.objects.filter(makerspace=space, event__makerspace=space).exclude(
            source="legacy").order_by("registration_id", "attended_at", "id").distinct("registration_id").values("pk")
        qs = apply_range(EventCheckInEvent.objects.filter(pk__in=earliest), "attended_at", booking_window(space, date_range))
        qs = qs.annotate(period=period_expression("attended_at", grain, makerspace=space))
        groups = {}
        for row in qs.values("event_id", "event__title", "event__starts_at", "attended_at", "period"):
            minutes = hours(row["event__starts_at"], row["attended_at"]) * 60
            label = histogram_bucket(minutes, CHECKIN_EDGES, CHECKIN_LABELS)
            key = (row["event_id"], row["event__title"], row["period"], label)
            groups[key] = groups.get(key, 0) + 1
        for (event_id, title, period, label), count in sorted(groups.items(), key=lambda item: (item[0][2], item[0][0], CHECKIN_LABELS.index(item[0][3]))):
            records.append(dict(makerspace_id=space.pk, event_id=event_id, title=title, period=period,
                                timing_bucket=label, checkin_count=count))
    return result(CHECKIN_FIELDS, records, makerspace_id, limit, meta={
        "basis": "First non-legacy attendance time per registration relative to event start",
        "limitations": "Legacy attendance has no reliable arrival time and is omitted",
    })


def numeric_scores(snapshot):
    """Private snapshots may be read for arithmetic; no answer or label is returned."""
    try:
        parsed = json.loads(snapshot)
    except (TypeError, ValueError):
        return
    if not isinstance(parsed, dict) or not isinstance(parsed.get("answers"), list):
        return
    for answer in parsed["answers"]:
        if not isinstance(answer, dict) or answer.get("type") != "number" or not isinstance(answer.get("id"), str):
            continue
        value = answer.get("value")
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            continue
        try:
            score = Decimal(str(value))
        except InvalidOperation:
            continue
        if score.is_finite():
            yield answer["id"], score


def build_event_feedback_scores(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "events"):
        qs = apply_range(EventFeedbackResponse.objects.filter(survey__event__makerspace=space), "created_at", booking_window(space, date_range))
        qs = qs.annotate(period=period_expression("created_at", grain, makerspace=space))
        groups = {}
        for response in qs.only("answers_snapshot", "survey__event__id", "survey__event__title", "survey__event__makerspace_id").select_related("survey__event").iterator():
            for question_id, score in numeric_scores(response.answers_snapshot):
                key = (response.survey.event_id, response.period, question_id)
                row = groups.setdefault(key, dict(makerspace_id=space.pk, event_id=key[0], title=response.survey.event.title,
                                                 period=key[1], question_id=question_id, score_count=0, score_total=Decimal(0)))
                row["score_count"] += 1
                row["score_total"] += score
        for key in sorted(groups):
            row = groups[key]
            row["average_score"] = round(row["score_total"] / row["score_count"], 2)
            records.append(row)
    return result(FEEDBACK_FIELDS, records, makerspace_id, limit, meta={
        "basis": "Finite numeric scores by event, question and feedback creation period",
        "limitations": "Question scales are independent; no cross-question average",
    })
