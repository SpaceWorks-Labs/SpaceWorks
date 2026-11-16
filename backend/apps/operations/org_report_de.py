"""Explicit D/E combinations: calendar labels, currencies and question bases stay separate."""

from .reports_common import limited
from .reports_de_common import percent


def _group(rows_by_space, keys, additive, *, limit, rates=()):
    groups = {}
    for _, rows in rows_by_space:
        for row in rows:
            # Tenant zones can have different UTC offsets: combine local calendar
            # labels, rather than accidentally merging different local dates.
            period = row.get("period")
            if hasattr(period, "date"):
                period = period.date().isoformat()
            values = {key: period if key == "period" else row.get(key) for key in keys}
            key = tuple(values.values())
            target = groups.setdefault(key, dict(**values))
            for field in additive:
                value = row.get(field)
                if value is not None:
                    target[field] = (target.get(field) or 0) + value
                else:
                    target.setdefault(field, None)
    for target in groups.values():
        for field, numerator, denominator in rates:
            target[field] = percent(target.get(numerator), target.get(denominator))
    return limited([groups[key] for key in sorted(groups, key=lambda k: tuple(str(v) for v in k))], limit)


def combine_utilization(rows_by_space, *, limit):
    return _group(rows_by_space, ("period",), (
        "booked", "completed", "no_show", "cancelled", "upcoming", "reserved_hours", "completed_hours",
        "window_hours", "reservations", "terminal_reservations"), limit=limit, rates=(
            ("reservation_utilization_percent", "reserved_hours", "window_hours"),
            ("no_show_rate_percent", "no_show", "terminal_reservations"),
            ("cancellation_rate_percent", "cancelled", "reservations")))


def combine_signups(rows_by_space, *, limit):
    periods = set()
    events = {}
    for space_id, rows in rows_by_space:
        for row in rows:
            period = row["period"]
            period = period.date().isoformat() if hasattr(period, "date") else period
            periods.add(period)
            events.setdefault((space_id, row["event_id"]), {})[period] = row
    totals = []
    carried = {}
    for period in sorted(periods):
        registrations = 0
        for key, event in events.items():
            row = event.get(period)
            if row is not None:
                registrations += row["registrations"]
                carried[key] = row["cumulative_registrations"]
        totals.append(dict(period=period, registrations=registrations, cumulative_registrations=sum(carried.values())))
    return limited(totals, limit)


def combine_revenue(rows_by_space, *, limit):
    return _group(rows_by_space, ("period", "currency"), (
        "charge_count", "charged_amount", "promo_discount_amount", "collected_amount", "refunded_amount",
        "outstanding_amount", "net_amount"), limit=limit)


def combine_funnel(rows_by_space, *, limit):
    return _group(rows_by_space, ("period",), ("registrations", "confirmed", "attended"), limit=limit, rates=(
        ("confirmation_rate_percent", "confirmed", "registrations"),
        ("attendance_rate_percent", "attended", "confirmed")))


def combine_feedback(rows_by_space, *, limit):
    # Question IDs are survey-local, not a global scale. Preserve event/question
    # identity so a 1–5 satisfaction question never mixes with a 0–100 score.
    records = _group(rows_by_space, ("event_id", "title", "period", "question_id"),
                     ("score_count", "score_total"), limit=limit)
    for row in records:
        row["average_score"] = round(row["score_total"] / row["score_count"], 2) if row["score_count"] else None
    return records
