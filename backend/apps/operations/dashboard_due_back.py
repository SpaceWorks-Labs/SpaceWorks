"""Decision 242(n)/IN2/IN3: server-side loan due counts and stock-health counts.

The "Due back" panel used to read page 1 (24 rows) of the loan list, so more than 24 overdue loans
hid "due within 3 days". These counts are exact and made once, with the same direct-loan exclusion as
`dashboard_handover.handover_home`: a direct or self-checkout loan carries a workflow request AND a
tool-loan row, and counting both doubled it. Everything goes through `rbac.scope_by_makerspace`.
"""

from datetime import timedelta

from django.db.models import F

from apps.accounts import rbac
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.makerspaces.local_time import local_day_bounds, to_local

OPEN_STATUSES = (HardwareRequest.Status.ISSUED, HardwareRequest.Status.PARTIALLY_RETURNED)
SOON_DAYS = 3


def _scope(actor, queryset):
    return rbac.scope_by_makerspace(actor, queryset) if actor is not None else queryset


def due_back_counts(actor, makerspace, now):
    """`due_today_loans` and `due_soon_loans` (the next 3 local days), each counted once."""
    today = to_local(makerspace, now).date()
    start = local_day_bounds(makerspace, today)[0]
    tomorrow = local_day_bounds(makerspace, today + timedelta(days=1))[0]
    horizon = local_day_bounds(makerspace, today + timedelta(days=1 + SOON_DAYS))[0]
    direct = _scope(actor, PublicToolLoan.objects.filter(makerspace=makerspace, returned_at__isnull=True))
    requests = _scope(actor, HardwareRequest.objects.filter(makerspace=makerspace, status__in=OPEN_STATUSES))
    requests = requests.exclude(pk__in=direct.values("request_id"))

    def window(low, high):
        return (requests.filter(return_due_at__gte=low, return_due_at__lt=high).count()
                + direct.filter(due_at__gte=low, due_at__lt=high).count())

    return {"due_today_loans": window(max(start, now), tomorrow), "due_soon_loans": window(tomorrow, horizon)}


def stock_health_counts(actor, makerspace):
    """`true_low_stock` (at or below 20 % of the total, still in stock) and `in_repair` units."""
    products = _scope(actor, InventoryProduct.objects.filter(makerspace=makerspace, is_archived=False))
    low = products.filter(total_quantity__gt=0, available_quantity__gt=0).annotate(
        available_x5=F("available_quantity") * 5).filter(available_x5__lte=F("total_quantity")).count()
    repair = _scope(actor, InventoryAsset.objects.filter(
        makerspace=makerspace,
        status__in=(InventoryAsset.Status.DAMAGED, InventoryAsset.Status.MAINTENANCE))).count()
    return {"true_low_stock": low, "in_repair": repair}
