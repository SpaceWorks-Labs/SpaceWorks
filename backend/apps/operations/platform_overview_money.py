"""Money block of the platform overview (#183A): grouped PER CURRENCY, never summed across.

Charges, collections, refunds and waivers come from the canonical dated finance seam
(`reports_finance_sources.finance_sources`), the same rows every per-space finance report
reads, so a space's numbers here match its own finance reports. Expenses and money
received outside a charge (offline donations, grants) come from the finance ledger's
non-voided `LedgerEntry` rows. Amounts stay Decimal and are returned as strings.
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum

from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.operations.platform_overview_blocks import Metric

#: The switches any of which puts money on in a space (#183A gate for this block).
SWITCHES = ("charges.enabled", "payments", "shop", "finance.donations")

METRICS = (
    Metric("charges", "Charges raised"),
    Metric("charged", "Amount charged"),
    Metric("collected", "Collected"),
    Metric("outstanding", "Still owed on these charges"),
    Metric("refunds", "Refunded"),
    Metric("waived", "Waived"),
    Metric("expenses", "Expenses"),
    Metric("donations", "Donations and sponsorship"),
    Metric("shop_sales", "Shop sales collected"),
)
AMOUNTS = tuple(metric.key for metric in METRICS if metric.key != "charges")
GIFT_SUBJECTS = ("donation", "sponsorship")


def money_on(space):
    return (feature_enabled(space, "charges.enabled") or feature_enabled(space, "finance.donations")
            or module_enabled(space, "payments") or module_enabled(space, "shop"))


def _add(table, currency, space_id, key, amount):
    if amount:
        table[currency][space_id][key] += Decimal(amount)


def _finance_rows(table, space_id, window):
    from apps.operations.reports_finance_sources import finance_sources

    for _space, row in finance_sources(space_id, date_range=window.date_range()):
        currency = row["currency"]
        if row["row_kind"] == "charge":
            table[currency][space_id]["charges"] += 1
            _add(table, currency, space_id, "charged", row["amount"])
            _add(table, currency, space_id, "outstanding", row.get("owed_amount"))
            continue
        if not row["effective"]:
            continue
        collected = row.get("collected_amount") or 0
        _add(table, currency, space_id, "collected", collected)
        _add(table, currency, space_id, "refunds", row.get("refunded_amount"))
        _add(table, currency, space_id, "waived", row.get("waived_amount"))
        if row["subject_type"] in GIFT_SUBJECTS:
            _add(table, currency, space_id, "donations", collected)
        if row["subject_type"] == "shop_order":
            _add(table, currency, space_id, "shop_sales", collected)


def _ledger_rows(table, ids, window):
    from apps.payments.models_ledger_entries import LedgerEntry

    entries = LedgerEntry.objects.filter(makerspace_id__in=ids, voided_at__isnull=True)
    if window.start is not None:
        entries = entries.filter(entry_date__gte=window.start.date())
    # The window end is exclusive; a ledger row carries a day, so take the last day inside it.
    entries = entries.filter(entry_date__lte=(window.end - timedelta(microseconds=1)).date())
    for kind, key, extra in (("expense", "expenses", {}), ("receipt", "donations", {"domain": "donations"})):
        rows = entries.filter(kind=kind, **extra).order_by().values("makerspace_id", "currency").annotate(total=Sum("amount"))
        for row in rows:
            _add(table, row["currency"], row["makerspace_id"], key, row["total"])


def collect_money(ids, window):
    """{currency: {space_id: {metric: value}}}; a currency appears only if it has money."""
    table = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    for space_id in ids:
        _finance_rows(table, space_id, window)
    _ledger_rows(table, ids, window)
    return table


def money_section(spaces, window):
    """The money block, or None when money is off in every space.

    Each currency carries its own per-space rows and its own totals; a total is the sum
    of that currency's rows only. `charges` is a count; every other value is a decimal
    string in that currency.
    """
    on = [space.pk for space in spaces if money_on(space)]
    if not on:
        return None
    table = collect_money(on, window)
    currencies = []
    for currency in sorted(table):
        per_space = table[currency]
        rows = [{"makerspace_id": space_id, **_figures(per_space[space_id])}
                for space_id in on if per_space.get(space_id)]
        totals = defaultdict(Decimal)
        for values in per_space.values():
            for key, value in values.items():
                totals[key] += value
        currencies.append({"currency": currency, "totals": _figures(totals), "rows": rows})
    return {"key": "money", "label": "Money", "switches": list(SWITCHES), "on_in": len(on),
            "off_in": len(spaces) - len(on),
            "metrics": [{"key": m.key, "label": m.label, "unit": "count" if m.key == "charges" else "money",
                         "timing": m.timing} for m in METRICS],
            "currencies": currencies}


def _figures(values):
    return {"charges": int(values.get("charges", 0)),
            "amounts": {key: str(Decimal(values.get(key, 0)).quantize(Decimal("0.01"))) for key in AMOUNTS}}
