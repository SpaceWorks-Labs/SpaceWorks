"""Host-owned event ledger activity; discounts are attributed once to the charge."""

from decimal import Decimal

from apps.events.models import EventRegistration
from apps.payments.models import Payment
from .reports_de_common import source_spaces as report_spaces
from .report_fields_de import REVENUE_FIELDS
from .reports_de_common import period_at, result
from .reports_finance_sources import finance_sources

MONEY_FIELDS = ("charged_amount", "promo_discount_amount", "collected_amount", "refunded_amount", "outstanding_amount")


def build_event_revenue(makerspace_id, *, limit=None, date_range=None, grain="day"):
    groups = {}
    for space in report_spaces(makerspace_id, "events"):
        # Payment.subject_id is polymorphic: constrain BOTH type and host tenant,
        # then join to registrations hosted here. Collaborator provenance is not ownership.
        payments = Payment.objects.filter(makerspace=space, subject_type=Payment.SubjectType.EVENT_REGISTRATION)
        registrations = {r["pk"]: r for r in EventRegistration.objects.filter(
            event__makerspace=space, pk__in=payments.values("subject_id")
        ).values("pk", "event_id", "event__title", "discount_amount")}
        subjects = {pk: registrations[subject_id] for pk, subject_id in payments.values_list("pk", "subject_id")
                    if subject_id in registrations}
        for _, source in finance_sources(space.pk, date_range=date_range, subject_type=Payment.SubjectType.EVENT_REGISTRATION):
            registration = subjects.get(source["payment_id"])
            if registration is None or not source["effective"]:
                continue
            if source["row_kind"] == "refund" and source.get("refund_status") != "succeeded":
                continue
            period = period_at(source["date"], grain, space)
            key = (space.pk, period, source["currency"], registration["event_id"])
            target = groups.setdefault(key, dict(makerspace_id=space.pk, period=period, currency=source["currency"],
                                                 event_id=registration["event_id"], title=registration["event__title"],
                                                 charge_count=0, **{field: Decimal(0) for field in MONEY_FIELDS}))
            if source["row_kind"] == "charge":
                target["charge_count"] += 1
                target["charged_amount"] += source["amount"]
                target["promo_discount_amount"] += registration["discount_amount"]
            target["collected_amount"] += source.get("collected_amount", 0)
            target["refunded_amount"] += source.get("refunded_amount", 0)
            target["outstanding_amount"] += source.get("owed_amount", 0)
    records = []
    for key in sorted(groups):
        row = groups[key]
        row["net_amount"] = row["collected_amount"] - row["refunded_amount"]
        records.append(row)
    return result(REVENUE_FIELDS, records, makerspace_id, limit, meta={
        "basis": "Host-owned event ledger; discounts recorded once per charge, partitioned by currency",
        "money_dates": "Charge creation; manual received/refunded dates; online settled timestamp",
        "legacy_dates": "Payment updated timestamp for undocumented historical settlements",
        "owed": "Currently pending debt by charge creation, not historical balances",
        "limitations": "Free registrations without a linked charge have no frozen ledger currency and are omitted",
    })
