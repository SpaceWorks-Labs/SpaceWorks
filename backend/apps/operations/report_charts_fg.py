"""F1 field mappings for counts-only membership and money charts."""


def chart(x, values, *, series=(), time=False, money=False, alt, negatives="clip"):
    return {
        "series": list(series), "x": {"field": x, "kind": "time" if time else "category"},
        "values": [{"field": field, "unit": unit} for field, unit in values],
        "currency_field": "currency" if money else None,
        "partition": "currency" if money else "tenant", "negatives": negatives,
        "truncation": None, "alt_template": alt,
    }


GROWTH_CHART = chart("period", [(field, "memberships") for field in (
    "new_members", "activated_members", "revoked_members", "active_members")], time=True,
    alt="{active_members} active memberships at the end of {period}.")
RETENTION_CHART = chart("months_after_join", [("retention_percent", "percent")], series=("cohort_month",),
    alt="{cohort_month} cohort: {retained_members} of {eligible_members} retained after {months_after_join} months.")
MEMBERSHIP_REVENUE_CHART = chart("period", [("mrr", "currency_major")], time=True, money=True,
    series=("makerspace_id", "plan_id", "plan_name"), alt="{plan_name}: {mrr} {currency} MRR in {period}.")
REVENUE_CHART = chart("period", [(field, "currency_major") for field in (
    "collected_amount", "owed_amount", "refunded_amount", "waived_amount", "net_amount")],
    time=True, money=True, series=("makerspace_id", "rail", "subject_type"), negatives="allow",
    alt="{period}: {net_amount} {currency} net on {rail}.")
CASH_CHART = chart("period", [(field, "currency_major") for field in (
    "collected_amount", "refunded_amount", "net_amount")], time=True, money=True,
    series=("makerspace_id", "method"), negatives="allow", alt="{period}: {net_amount} {currency} net via {method}.")
AGEING_CHART = chart("age_bucket", [("outstanding_amount", "currency_major")], money=True,
    series=("makerspace_id",), alt="{age_bucket} days: {outstanding_amount} {currency} outstanding across {payment_count} charges.")
RECONCILIATION_CHART = chart("status", [(field, "currency_major") for field in (
    "amount_total", "outstanding_amount", "refunded_amount")], money=True,
    series=("makerspace_id", "subject_type", "settlement_method"),
    alt="{status}: {amount_total} {currency} across {payment_count} charges.")
