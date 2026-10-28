"""Currency-separated ledger ageing. Domain pools are supplied by a typed port."""
from datetime import timedelta
from django.db.models import BigIntegerField, Case, Exists, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from .obligation_models import EventPayoutObligation
from .payout_models import EventPayoutEntry
from .eligibility_models import PayoutHold

_pool_reader = None


def install(pool_reader):
    global _pool_reader
    if _pool_reader is not None and _pool_reader is not pool_reader:
        raise RuntimeError("Payout dashboard provider already installed.")
    _pool_reader = pool_reader


def project(space):
    now = timezone.now()
    tips = EventPayoutEntry.objects.filter(obligation_id=OuterRef("pk"), amended_by__isnull=True,
        is_void=False).order_by().values("obligation_id").annotate(total=Sum("amount_minor")).values("total")
    # Row-level values carry their own names: re-using an output name (paid_minor,
    # approved_minor) in the grouped annotate below would make Sum() refer to the
    # aggregate itself, which Django refuses with a FieldError.
    rows = EventPayoutObligation.objects.filter(makerspace=space).annotate(
        row_hold=Exists(PayoutHold.objects.filter(obligation_id=OuterRef("pk"), action="hold", released_by_entry__isnull=True)),
        row_paid=Coalesce(Subquery(tips), Value(0), output_field=BigIntegerField()),
        row_remaining=F("approved_minor") - F("row_paid"))

    def total(expression="row_remaining", condition=None):
        if condition is not None:
            expression = Case(When(condition, then=F(expression)), default=Value(0), output_field=BigIntegerField())
        return Coalesce(Sum(expression), Value(0), output_field=BigIntegerField())

    sums = {
        "approved_minor": total("approved_minor"), "paid_minor": total("row_paid"),
        "approved_unpaid_minor": total(condition=Q(row_paid=0, state="open")),
        "part_paid_remaining_minor": total(condition=Q(row_paid__gt=0, row_remaining__gt=0)),
        "held_remaining_minor": total(condition=Q(row_hold=True) | Q(eligibility_status="held") | ~Q(hold_reason_code="")),
        "ageing_0_7_minor": total(condition=Q(created_at__gte=now - timedelta(days=8))),
        "ageing_8_30_minor": total(condition=Q(created_at__lt=now - timedelta(days=8), created_at__gte=now - timedelta(days=31))),
        "ageing_31_plus_minor": total(condition=Q(created_at__lt=now - timedelta(days=31))),
    }
    grouped = rows.values("currency").annotate(**{f"sum_{key}": value for key, value in sums.items()}).order_by("currency")
    currencies = [{"currency": row["currency"], **{key: row[f"sum_{key}"] for key in sums}} for row in grouped]
    # Missing/tombstoned domain data is explicitly unavailable, never guessed zero
    # or reconstructed from core debt. The domain owns all pool arithmetic.
    pools = _pool_reader(makerspace_id=space.pk) if _pool_reader else None
    return {"currencies": currencies, "budget_snapshot": pools}
