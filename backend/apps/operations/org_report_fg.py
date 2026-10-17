"""Organization sums of memberships and money, with weighted cohort retention/ARPU."""

from decimal import Decimal

from apps.operations.org_report_aggregate import _group_sum


def _sum_groups(rows_by_space, keys, fields, limit):
    return _group_sum([row for _, records in rows_by_space for row in records], keys, fields, limit)


def combine_growth(rows_by_space, *, limit):
    return _sum_groups(rows_by_space, ("period",), (
        "new_members", "activated_members", "revoked_members", "active_members"), limit)


def combine_retention(rows_by_space, *, limit):
    rows = _sum_groups(rows_by_space, ("cohort_month", "months_after_join"), (
        "cohort_members", "eligible_members", "retained_members", "churned_members", "reactivated_members"), limit)
    for row in rows:
        denominator = row["eligible_members"]
        row["retention_percent"] = ((Decimal(row["retained_members"]) * 100 / denominator)
                                    .quantize(Decimal("0.01")) if denominator else None)
    return rows


def combine_membership_revenue(rows_by_space, *, limit):
    # Plan primary keys are global; equal labels on different plans never merge.
    rows = _sum_groups(rows_by_space, ("period", "currency", "plan_id", "plan_name"), (
        "recurring_members", "mrr", "arr", "churned_members", "reactivated_members"), limit)
    for row in rows:
        denominator = row["recurring_members"]
        row["arpu"] = (row["mrr"] / denominator if denominator else Decimal(0)).quantize(Decimal("0.01"))
    return rows


def combine_revenue(rows_by_space, *, limit):
    return _sum_groups(rows_by_space, ("period", "currency", "subject_type", "rail"), (
        "collected_amount", "owed_amount", "refunded_amount", "waived_amount", "net_amount"), limit)


def combine_cash(rows_by_space, *, limit):
    return _sum_groups(rows_by_space, ("period", "currency", "method"), (
        "collected_amount", "refunded_amount", "net_amount"), limit)


def combine_ageing(rows_by_space, *, limit):
    rows = _sum_groups(rows_by_space, ("currency", "age_bucket"), (
        "payment_count", "outstanding_amount"), None)
    order = {bucket: index for index, bucket in enumerate(("0-30", "31-60", "61-90", "90+"))}
    return sorted(rows, key=lambda row: (row["currency"], order[row["age_bucket"]]))[:limit]


def combine_reconciliation(rows_by_space, *, limit):
    return _sum_groups(rows_by_space, ("currency", "subject_type", "status", "settlement_method"), (
        "payment_count", "amount_total", "outstanding_amount", "refunded_amount"), limit)
