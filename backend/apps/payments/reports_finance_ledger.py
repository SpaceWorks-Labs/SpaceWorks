"""Income versus spending by month, area and machine type; the per-event money view (#94, #100).

Built from `finance_rows.money_rows`, so every report reads the same four sources and a
movement is counted once. Each builder narrows rows to what the actor's finance view sees
(`finance_scope`): a Space Manager or view_finance holder sees every area, an area
manager only theirs, a Machine Manager only their machine types. Without an actor (a
scheduled delivery) the registry has already checked the creator's action and the
area-specific reports keep to their own areas. Amounts never mix currencies.
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.payments.finance_rows import COLUMNS, MONEY_IN, money_rows

FIELDS = ("month", "domain", "machine_type", "currency", *COLUMNS, "money_in", "money_out", "net")
EVENT_FIELDS = ("event_id", "event", "currency", "income", "refunds", "other_income", "expenses", "payouts",
                "budget", "budget_left", "net")
ZERO = Decimal("0.00")
AREAS = {
    "finance-inventory": ("inventory", "loans"),
    "finance-machines": ("machines",),
    "finance-bookings": ("bookings",),
    "finance-events": ("events",),
}


def _spaces(makerspace_id):
    from apps.makerspaces.models import Makerspace
    from apps.operations.report_scope import scoped_ids

    return Makerspace.objects.filter(pk__in=scoped_ids(makerspace_id)).order_by("pk")


def visible_rows(space, date_range, actor, areas=None):
    view = None
    if actor is not None:
        from apps.payments.finance_scope import finance_view
        view = finance_view(actor, space.pk)
    for row in money_rows(space, date_range):
        if areas is not None and row.domain not in areas:
            continue
        if view is not None and not view.sees(row.domain, row.machine_type_id):
            continue
        yield row


def _type_names(ids):
    from apps.machines.models import MachineType

    return dict(MachineType.objects.filter(pk__in=[pk for pk in ids if pk]).values_list("pk", "name"))


def _totals(values):
    money_in = sum((values[name] for name in MONEY_IN), ZERO)
    money_out = sum((values[name] for name in COLUMNS if name not in MONEY_IN), ZERO)
    return {**values, "money_in": money_in, "money_out": money_out, "net": money_in - money_out}


def build_income_spending(makerspace_id, *, limit=None, date_range=None, actor=None, areas=None):
    records = []
    for space in _spaces(makerspace_id):
        groups = defaultdict(lambda: dict.fromkeys(COLUMNS, ZERO))
        for row in visible_rows(space, date_range, actor, areas):
            key = (to_local(space, row.at).strftime("%Y-%m"), row.domain, row.machine_type_id, row.currency)
            groups[key][row.column] += row.amount
        names = _type_names({key[2] for key in groups})
        for key in sorted(groups, key=lambda item: (item[0], item[1], item[2] or 0, item[3])):
            month, domain, machine_type, currency = key
            records.append({"month": month, "domain": domain, "machine_type": names.get(machine_type, ""),
                            "currency": currency, **_totals(groups[key])})
    return ReportResult(FIELDS, records if limit is None else records[:limit], {
        "definition": "Every money movement by the makerspace-local month it happened: member charges "
                      "collected (income), other receipts such as donations (other_income), refunds that "
                      "went back, expenses recorded in the finance ledger, and event reimbursement and "
                      "prize payouts.",
        "columns": "money_in=income+other_income; money_out=refunds+expenses+payouts; net=money_in-money_out.",
        "scope": "Rows are limited to the finance areas the viewer manages.",
        "calendar": "makerspace local time",
    })


def _area_builder(key):
    def build(makerspace_id, *, limit=None, date_range=None, actor=None):
        return build_income_spending(makerspace_id, limit=limit, date_range=date_range, actor=actor,
                                     areas=AREAS[key])
    build.__name__ = f"build_{key.replace('-', '_')}"
    return build


build_finance_inventory = _area_builder("finance-inventory")
build_finance_machines = _area_builder("finance-machines")
build_finance_bookings = _area_builder("finance-bookings")
build_finance_events = _area_builder("finance-events")


def event_finance(space, date_range=None, actor=None, event_id=None):
    """Per-event rows (income less refunds, expenses and payouts, against the budget)."""
    from apps.events.models import Event
    from apps.payments.models_event_budget import effective_budgets

    groups = defaultdict(lambda: dict.fromkeys(COLUMNS, ZERO))
    for row in visible_rows(space, date_range, actor, ("events",)):
        if row.event_id is None or (event_id is not None and row.event_id != event_id):
            continue
        groups[(row.event_id, row.currency)][row.column] += row.amount
    budgets = effective_budgets(space.pk, None if event_id is None else [event_id])
    for budget_event, currency in budgets:
        groups.setdefault((budget_event, currency), dict.fromkeys(COLUMNS, ZERO))
    titles = dict(Event.objects.filter(pk__in={key[0] for key in groups}).values_list("pk", "title"))
    rows = []
    for (event, currency), values in sorted(groups.items()):
        budget = budgets.get((event, currency))
        spent = values["expenses"] + values["payouts"]
        net = values["income"] + values["other_income"] - values["refunds"] - spent
        rows.append({"event_id": event, "event": titles.get(event, ""), "currency": currency, **values,
                     "budget": budget, "budget_left": (budget - spent) if budget is not None else None, "net": net})
    return rows


def build_event_finance(makerspace_id, *, limit=None, date_range=None, actor=None):
    records = []
    for space in _spaces(makerspace_id):
        records.extend(event_finance(space, date_range, actor))
    return ReportResult(EVENT_FIELDS, records if limit is None else records[:limit], {
        "definition": "Per event: registration income less refunds, money spent on the event (expenses "
                      "and reimbursement or prize payouts), against the event's finance budget.",
        "columns": "budget_left=budget-expenses-payouts; net=income+other_income-refunds-expenses-payouts.",
    })
