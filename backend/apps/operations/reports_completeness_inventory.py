"""Decision 248 / 224(a): the Inventory Manager's valuation, category utilisation and overdue-by-borrower tables.

All three are per space and tenant-local. `inventory-valuation` multiplies the recorded unit cost by the stock
on hand per product (products with no recorded cost are listed with an empty value, never guessed).
`inventory-utilisation-by-category` rolls the live quantity buckets up by category. `overdue-by-borrower` names
who holds overdue items -- identity-bearing, so a superadmin needs an open PII window.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from apps.hardware_requests.display import requester_label
from apps.hardware_requests.models import HardwareRequest, PublicToolLoan
from apps.inventory.models import InventoryProduct
from apps.makerspaces.anonymous_requesters import anonymous_requester_ids
from apps.operations.report_types import ReportResult

VALUATION_FIELDS = ("category", "product", "currency", "total_quantity", "unit_cost", "stock_value")
UTILISATION_FIELDS = ("category", "products", "total_quantity", "issued_quantity", "reserved_quantity",
                      "available_quantity", "damaged_or_lost_quantity", "utilisation_percent")
OVERDUE_BORROWER_FIELDS = ("borrower", "overdue_loans", "oldest_due_at", "max_days_overdue", "items")
UNCATEGORISED = "Uncategorised"


def _products(makerspace_id):
    return InventoryProduct.objects.filter(makerspace_id=makerspace_id, is_archived=False)


def _cap(rows, limit):
    return rows if limit is None else rows[:limit]


def build_inventory_valuation(makerspace_id, *, limit=None, date_range=None, actor=None):
    rows = []
    for product in _products(makerspace_id).select_related("category").order_by("category__name", "name", "pk"):
        cost = product.unit_cost
        rows.append({"category": product.category.name if product.category_id else UNCATEGORISED,
                     "product": product.name, "currency": product.cost_currency or "",
                     "total_quantity": product.total_quantity, "unit_cost": cost,
                     "stock_value": (cost * product.total_quantity).quantize(Decimal("0.01")) if cost is not None else None})
    return ReportResult(VALUATION_FIELDS, _cap(rows, limit), {
        "definition": "Recorded unit cost x total quantity per active product, grouped by category.",
        "limitations": "Products without a recorded cost show no value; values are in each product's own cost currency "
                       "and are never summed across currencies.",
    })


def build_inventory_utilisation_by_category(makerspace_id, *, limit=None, date_range=None, actor=None):
    groups = defaultdict(lambda: defaultdict(int))
    for row in _products(makerspace_id).values("category__name").annotate(
            products=Count("pk"), total=Sum("total_quantity"), issued=Sum("issued_quantity"),
            reserved=Sum("reserved_quantity"), available=Sum("available_quantity"),
            damaged=Sum("damaged_quantity"), lost=Sum("lost_quantity")):
        group = groups[row["category__name"] or UNCATEGORISED]
        for key in ("products", "total", "issued", "reserved", "available", "damaged", "lost"):
            group[key] += row[key] or 0
    rows = []
    for name, g in sorted(groups.items()):
        in_use = g["issued"] + g["reserved"]
        rows.append({"category": name, "products": g["products"], "total_quantity": g["total"],
                     "issued_quantity": g["issued"], "reserved_quantity": g["reserved"],
                     "available_quantity": g["available"], "damaged_or_lost_quantity": g["damaged"] + g["lost"],
                     "utilisation_percent": round(100 * in_use / g["total"], 1) if g["total"] else 0})
    return ReportResult(UTILISATION_FIELDS, _cap(rows, limit), {
        "definition": "Units out or held (issued + reserved) as a share of total units, by inventory category, today.",
        "calendar": "snapshot of current quantities",
    })


def build_overdue_by_borrower(makerspace_id, *, limit=None, date_range=None, actor=None):
    now = timezone.now()
    principals = set(anonymous_requester_ids([makerspace_id]))
    borrowers = {}

    def add(key, label, due_at, items):
        row = borrowers.setdefault(key, {"borrower": label, "overdue_loans": 0, "oldest_due_at": due_at,
                                         "max_days_overdue": 0, "items": 0})
        row["overdue_loans"] += 1
        row["items"] += items
        row["oldest_due_at"] = min(row["oldest_due_at"], due_at)
        row["max_days_overdue"] = max(row["max_days_overdue"], (now - due_at).days)

    requests = HardwareRequest.objects.filter(
        makerspace_id=makerspace_id, status__in=("issued", "partially_returned"), return_due_at__lt=now,
        public_tool_loan__isnull=True).select_related("requester").prefetch_related("items")
    for request in requests.iterator(chunk_size=500):
        if request.requester_id in principals:
            continue
        add(("u", request.requester_id), requester_label(request), request.return_due_at,
            sum(item.issued_quantity or 0 for item in request.items.all()))
    for loan in PublicToolLoan.objects.filter(makerspace_id=makerspace_id, status=PublicToolLoan.Status.CHECKED_OUT,
                                              due_at__lt=now).select_related("requester").iterator():
        if loan.requester_id not in principals:
            add(("u", loan.requester_id), loan.requester.username, loan.due_at, 1)
    rows = sorted(borrowers.values(), key=lambda row: (-row["max_days_overdue"], row["borrower"]))
    return ReportResult(OVERDUE_BORROWER_FIELDS, _cap(rows, limit), {
        "definition": "Open loans past their due date, one row per borrower. Account-less principals are excluded.",
        "calendar": "snapshot as of now",
    })
