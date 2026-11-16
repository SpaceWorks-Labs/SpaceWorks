"""Money linked to physical loans, read from the payments ledger and never recomputed.

A loan's charges are the ledger rows whose subject is the request (deposit, late fee, rental) or one
of its lost/damaged accountability records. Amounts are grouped by ledger status; settlements are the
effective offline receipts (the head of each correction chain) written against those charges.
"""
from decimal import Decimal

from django.db.models import Count, Q

CHARGE_FIELDS = (
    "charge_currency", "charge_count", "charge_pending_amount", "charge_paid_amount",
    "charge_waived_amount", "settlement_count",
)
MIXED = "mixed"


def empty_charges():
    return {"charge_currency": "", "charge_count": 0, "charge_pending_amount": Decimal("0"),
            "charge_paid_amount": Decimal("0"), "charge_waived_amount": Decimal("0"), "settlement_count": 0}


def charge_rollup(space, request_ids):
    """{request_id: charge fields}. Two currencies on one loan are labelled ``mixed`` and not summed."""
    from apps.hardware_requests.return_models import RequesterAccountability
    from apps.payments.models import ManualSettlement, Payment

    ids = list(request_ids)
    if not ids:
        return {}
    owners = dict(RequesterAccountability.objects.filter(
        makerspace=space, request_id__in=ids).values_list("pk", "request_id"))
    payments = list(Payment.objects.filter(makerspace=space).exclude(status=Payment.Status.CANCELED).filter(
        Q(subject_type__in=Payment.LOAN_SUBJECT_TYPES, subject_id__in=ids)
        | Q(subject_type__in=Payment.LOAN_ACCOUNTABILITY_SUBJECT_TYPES, subject_id__in=list(owners))
    ).values("pk", "subject_type", "subject_id", "status", "amount", "currency"))
    receipts = dict(ManualSettlement.objects.filter(
        payment_id__in=[row["pk"] for row in payments], amended_by__isnull=True,
    ).values_list("payment_id").annotate(n=Count("pk")))
    result = {}
    for row in payments:
        loan = owners[row["subject_id"]] if row["subject_type"] in Payment.LOAN_ACCOUNTABILITY_SUBJECT_TYPES \
            else row["subject_id"]
        out = result.setdefault(loan, empty_charges())
        out["charge_count"] += 1
        out["settlement_count"] += receipts.get(row["pk"], 0)
        if out["charge_currency"] not in ("", row["currency"]):
            out["charge_currency"] = MIXED
        elif out["charge_currency"] != MIXED:
            out["charge_currency"] = row["currency"]
        bucket = ("charge_pending_amount" if row["status"] == Payment.Status.PENDING
                  else "charge_waived_amount" if row["status"] == Payment.Status.WAIVED else "charge_paid_amount")
        out[bucket] += row["amount"]
    for out in result.values():
        if out["charge_currency"] == MIXED:
            for key in ("charge_pending_amount", "charge_paid_amount", "charge_waived_amount"):
                out[key] = Decimal("0")
    return result
