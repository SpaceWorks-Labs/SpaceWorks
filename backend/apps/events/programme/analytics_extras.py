"""Per-event analytics extras (G8): counts only, never a person, never free text.

* arrivals -- first check-in per registration, in 15-minute local windows;
* check-in methods -- the same first check-ins split by source (QR, staff, station, ...);
* answer charts -- feedback choice questions only, counted against the form's declared
  options; short text and paragraphs are never read into a chart;
* waitlist conversion -- people promoted off the waitlist vs. still waiting;
* series turnout -- registered vs. attended per occurrence of the event's series;
* short-link visits -- L1's PII-free daily counter, while `events.short_links` is on.
"""

import json
from zoneinfo import ZoneInfo

from django.db.models import Count, Min, Q

from apps.makerspaces.platform import feature_enabled

CHOICE_TYPES = frozenset({"single_choice", "dropdown", "multi_choice", "yes_no"})
WINDOW_MINUTES = 15


def arrivals(event):
    from apps.events.models_attendance import EventCheckInEvent
    zone = ZoneInfo(event.timezone_name)
    first = (EventCheckInEvent.objects.filter(event=event).values("registration_id")
             .annotate(at=Min("attended_at")).values_list("registration_id", "at"))
    sources = dict(EventCheckInEvent.objects.filter(event=event).order_by("registration_id", "attended_at", "pk")
                   .distinct("registration_id").values_list("registration_id", "source"))
    windows, methods = {}, {}
    for registration_id, at in first:
        local = at.astimezone(zone)
        start = local.replace(minute=local.minute - local.minute % WINDOW_MINUTES, second=0, microsecond=0)
        windows[start] = windows.get(start, 0) + 1
        source = sources.get(registration_id, "legacy")
        methods[source] = methods.get(source, 0) + 1
    timeline = [{"window_start": start, "count": windows[start]} for start in sorted(windows)]
    return timeline, [{"method": key, "count": value} for key, value in sorted(methods.items())]


def _choice_values(answer, options):
    value = answer.get("value")
    if answer.get("type") == "yes_no":
        return ["Yes" if value else "No"] if isinstance(value, bool) else []
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, str) and item in options]


def answer_charts(event):
    from apps.events.models_feedback import EventFeedbackSurvey
    survey = EventFeedbackSurvey.objects.filter(event=event).first()
    if survey is None:
        return []
    questions = {question["id"]: question for question in survey.questions if question.get("type") in CHOICE_TYPES}
    counts = {question_id: {} for question_id in questions}
    for snapshot in survey.responses.only("answers_snapshot").iterator():
        try:
            parsed = json.loads(snapshot.answers_snapshot)
        except (TypeError, ValueError):
            continue
        for answer in parsed.get("answers", []) if isinstance(parsed, dict) else []:
            question = questions.get(answer.get("id")) if isinstance(answer, dict) else None
            if question is None:
                continue
            options = ["Yes", "No"] if question["type"] == "yes_no" else list(question.get("options") or [])
            for value in _choice_values(answer, options):
                counts[question["id"]][value] = counts[question["id"]].get(value, 0) + 1
    charts = []
    for question_id, question in questions.items():
        options = ["Yes", "No"] if question["type"] == "yes_no" else list(question.get("options") or [])
        rows = [{"label": option, "count": counts[question_id].get(option, 0)} for option in options]
        charts.append({"question_id": question_id, "label": question.get("label", ""), "type": question["type"],
                       "answers": rows, "total": sum(row["count"] for row in rows)})
    return charts


def waitlist_conversion(event):
    from apps.audit.models import AuditLog
    ids = [str(pk) for pk in event.registrations.values_list("pk", flat=True)]
    promoted = AuditLog.objects.filter(
        makerspace_id=event.makerspace_id, action="event.registration_promoted",
        target_type="events.eventregistration", target_id__in=ids).values("target_id").distinct().count()
    waiting = event.registrations.filter(status="waitlisted").count()
    joined = promoted + waiting
    return {"ever_waitlisted": joined, "promoted": promoted, "still_waiting": waiting,
            "conversion_percent": round(promoted * 100 / joined, 1) if joined else None}


def series_turnout(event):
    if not event.series_id:
        return []
    from apps.events.models import Event
    rows = (Event.objects.filter(series_id=event.series_id, makerspace_id=event.makerspace_id)
            .order_by("starts_at", "pk")[:24]
            .annotate(registered=Count("registrations", filter=Q(registrations__status__in=("registered", "attended"))),
                      attended=Count("registrations", filter=Q(registrations__status="attended"))))
    return [{"event_id": row.pk, "title": row.title, "starts_at": row.starts_at,
             "registered": row.registered, "attended": row.attended} for row in rows]


def short_link_visits(event):
    if not feature_enabled(event.makerspace, "events.short_links"):
        return None
    try:
        from apps.events.short_links import visits
    except ImportError:  # L1 not installed in this build
        return None
    return visits(event, days=30)


def extras(event):
    timeline, methods = arrivals(event)
    return {"event_id": event.pk, "timezone_name": event.timezone_name, "arrivals": timeline,
            "checkin_methods": methods, "answers": answer_charts(event),
            "waitlist": waitlist_conversion(event), "series": series_turnout(event),
            "short_link_visits": short_link_visits(event),
            "submission_stages": _stage_funnel(event),
            "window_minutes": WINDOW_MINUTES}


def _stage_funnel(event):
    from apps.events.submissions.stage_analytics import stage_funnel  # #180 S16.
    return stage_funnel(event)
