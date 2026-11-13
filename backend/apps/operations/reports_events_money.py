"""Parity C19/C24: the Money and Spending sections of the post-event PDF, and a series money card.

Both read `payments.reports_finance_ledger.event_finance` -- the one per-event money view -- so a movement is
counted once and the figures match the Finance reports. Nothing here moves or records money.

Visibility (a section is simply absent, never zero):
* the space tracks event charges OR takes online event payments (`charge_tracking_enabled` /
  `online_payments_enabled`); with both off the sections do not exist;
* the viewer's finance view sees the `events` area (view_finance, or an Event Manager's own events money).
Amounts are grouped by currency and written as text per currency ("120.00 INR; 5.00 USD"); currencies never mix.
Money is formatted by `payments.money.money_text` (two places, three only when a fils is present).
"""

from apps.payments.money import money_text
from .reports_events import FIELDS as ATTENDANCE_FIELDS, build_event_attendance
from .report_types import ReportResult

MONEY_FIELDS = ("money_income", "money_refunds", "money_other_income", "money_net",
                "spending_expenses", "spending_payouts", "spending_budget", "spending_budget_left")
PDF_FIELDS = ATTENDANCE_FIELDS + MONEY_FIELDS
_SOURCES = {"money_income": "income", "money_refunds": "refunds", "money_other_income": "other_income",
            "money_net": "net", "spending_expenses": "expenses", "spending_payouts": "payouts",
            "spending_budget": "budget", "spending_budget_left": "budget_left"}


def money_visible(space, actor):
    if actor is None:
        return False
    from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
    if not (charge_tracking_enabled(space, "events") or online_payments_enabled(space, "events")):
        return False
    from apps.payments.finance_scope import finance_view
    return finance_view(actor, space.pk).sees("events")


def _text(rows, source):
    parts = [f"{money_text(row[source])} {row['currency']}" for row in rows if row.get(source) is not None]
    return "; ".join(parts)


def event_sections(space, actor, event_ids, *, single=None):
    """`{event_id: {field: text}}`, or `{}` when the sections are hidden for this viewer."""
    if not money_visible(space, actor):
        return {}
    from apps.payments.reports_finance_ledger import event_finance
    by_event = {}
    for row in event_finance(space, None, actor, single):
        if row["event_id"] in event_ids:
            by_event.setdefault(row["event_id"], []).append(row)
    return {event_id: {field: _text(rows, source) for field, source in _SOURCES.items()}
            for event_id, rows in by_event.items()}


def build_event_report_pdf(makerspace_id, *, limit=None, date_range=None, subject_kind=None, subject_id=None,
                           actor=None):
    """The post-event PDF: attendance, plus Money and Spending when this viewer may see them."""
    result = build_event_attendance(makerspace_id, limit=limit, date_range=date_range,
                                    subject_kind=subject_kind, subject_id=subject_id)
    if makerspace_id is None or not result.records:
        return result
    from apps.makerspaces.models import Makerspace
    space = Makerspace.objects.get(pk=makerspace_id)
    ids = {record["event_id"] for record in result.records}
    sections = event_sections(space, actor, ids, single=subject_id if subject_kind == "event" else None)
    if not sections:
        return result
    for record in result.records:
        record.update(sections.get(record["event_id"], dict.fromkeys(MONEY_FIELDS, "")))
    return ReportResult(result.field_order + MONEY_FIELDS, result.records, result.meta)


def series_money(space, series, actor):
    """The series money card: income, refunds, spending and net per currency over every occurrence.

    `None` when hidden (same rules as the PDF). Occurrences are summed per currency; a budget is per event,
    so it is left out of the card.
    """
    from apps.events.models import Event
    ids = set(Event.objects.filter(series=series, makerspace=space).values_list("pk", flat=True))
    if not ids or not money_visible(space, actor):
        return None
    from apps.payments.reports_finance_ledger import event_finance
    totals = {}
    for row in event_finance(space, None, actor):
        if row["event_id"] not in ids:
            continue
        sums = totals.setdefault(row["currency"], dict.fromkeys(
            ("income", "refunds", "other_income", "expenses", "payouts", "net"), 0))
        for key in sums:
            sums[key] += row[key]
    return {"occurrences": len(ids),
            "currencies": [{"currency": currency, **{key: money_text(value) for key, value in sums.items()}}
                           for currency, sums in sorted(totals.items())]}
