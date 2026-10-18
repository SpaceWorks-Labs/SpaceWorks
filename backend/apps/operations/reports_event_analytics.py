"""Registration cohorts and cumulative signups without attendee identities."""

from django.db.models import Count, Q

from apps.events.models import EventRegistration
from .reports_common import apply_range, period_expression
from .reports_de_common import source_spaces as report_spaces
from .report_fields_de import SIGNUP_FIELDS, FUNNEL_FIELDS
from .reports_de_common import report_window as booking_window
from .reports_de_common import next_period, percent, period_at, result


def build_event_signups(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "events"):
        start, end = booking_window(space, date_range)
        qs = EventRegistration.objects.filter(event__makerspace=space)
        if end:
            qs = qs.filter(created_at__lt=end)
        rows = qs.annotate(period=period_expression("created_at", grain, makerspace=space)).values(
            "event_id", "event__title", "period").annotate(
                count=Count("pk"), new_count=Count("pk", filter=Q(created_at__gte=start) if start else Q()),
            ).order_by("event_id", "period")
        events = {}
        for row in rows:
            event = events.setdefault(row["event_id"], {"title": row["event__title"], "periods": {}})
            event["periods"][row["period"]] = (row["count"], row["new_count"])
        last = end or (next_period(max(row for event in events.values() for row in event["periods"]), grain) if events else None)
        for event_id, event in events.items():
            counts = event["periods"]
            first = period_at(start, grain, space) if start else min(counts)
            cumulative = sum(count[0] for period, count in counts.items() if period < first)
            at = first
            while at < last:
                total, count = counts.get(at, (0, 0))
                cumulative += total
                records.append(dict(makerspace_id=space.pk, event_id=event_id, title=event["title"],
                                    period=at, registrations=count, cumulative_registrations=cumulative))
                at = next_period(at, grain)
    records.sort(key=lambda r: (r["makerspace_id"], r["period"], r["event_id"]))
    return result(SIGNUP_FIELDS, records, makerspace_id, limit, meta={
        "basis": "All registration creations; cumulative values include pre-window history",
    })


def build_event_funnel(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in report_spaces(makerspace_id, "events"):
        qs = apply_range(EventRegistration.objects.filter(event__makerspace=space), "created_at", booking_window(space, date_range))
        # These are current outcomes of creation cohorts, not invented transition dates.
        rows = qs.annotate(period=period_expression("created_at", grain, makerspace=space)).values(
            "event_id", "event__title", "period").annotate(
                registrations=Count("pk"),
                confirmed=Count("pk", filter=Q(status__in=("registered", "attended"))),
                attended=Count("pk", filter=Q(status="attended")),
            ).order_by("period", "event_id")
        for row in rows:
            records.append(dict(makerspace_id=space.pk, event_id=row["event_id"], title=row["event__title"],
                                period=row["period"], registrations=row["registrations"], confirmed=row["confirmed"],
                                attended=row["attended"], confirmation_rate_percent=percent(row["confirmed"], row["registrations"]),
                                attendance_rate_percent=percent(row["attended"], row["confirmed"])))
    return result(FUNNEL_FIELDS, records, makerspace_id, limit, meta={
        "basis": "Current outcomes of registration-creation cohorts; confirmed means registered or attended",
    })
