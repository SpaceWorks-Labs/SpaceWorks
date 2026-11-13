"""Optional `qr_code` import column: link labels printed outside SpaceWorks during import.

Every problem is found in the PREVIEW and blocks apply (even an async job that would
otherwise skip bad rows): a value repeated in the file, a value already linked to another
item or revoked in this makerspace, an update row whose item already has a different
active QR, an individual-tracked row (its labels belong on units), or a caller without
`manage_qr`. Apply links each code in the same savepoint as its row, and any conflict
that appears between preview and apply aborts the whole import.
"""
from collections import defaultdict

from django.utils.translation import gettext

from apps.accounts import rbac
from apps.boxes.external_qr import holder_conflict_code
from apps.boxes.models import QrCode
from apps.boxes.qr_lookup import by_scanned_key, scanned_in_q
from apps.inventory.models import InventoryProduct, TrackingMode

FIELD = "qr_code"


def check_rows(makerspace, mapped, errors, actor=None):
    """Mark rows whose `qr_code` cannot be linked. Mutates `mapped` and `errors`."""
    coded = [item for item in mapped if (item["data"] or {}).get(FIELD)]
    if not coded:
        return
    rows_by_value = defaultdict(list)
    for item in coded:
        rows_by_value[item["data"][FIELD]].append(item["row"])
    may_link = actor is None or rbac.can(actor, rbac.Action.MANAGE_QR, makerspace.id)
    names = {item["data"].get("name") for item in coded}
    existing = {
        product.name: product
        for product in InventoryProduct.objects.filter(makerspace=makerspace, name__in=names)
    }
    # A fixed number of queries for the whole file: who already holds each value (active
    # or revoked, active wins) and which existing items already carry an active QR.
    holders = by_scanned_key(
        QrCode.objects.filter(makerspace=makerspace).filter(scanned_in_q(rows_by_value)).order_by("-status", "-id")
    )
    coded_products = set(QrCode.objects.filter(
        makerspace=makerspace, target_type=QrCode.TargetType.PRODUCT, status=QrCode.Status.ACTIVE,
        target_id__in=[product.id for product in existing.values()],
    ).values_list("target_id", flat=True))
    # SpaceWorks payloads are deployment-unique; one from another space never re-links here.
    foreign = set(QrCode.objects.filter(payload__in=rows_by_value).exclude(
        makerspace=makerspace).values_list("payload", flat=True))
    context = (foreign, rows_by_value, existing, holders, coded_products)
    for item in coded:
        message = _problem(item, context, may_link)
        if message:
            _flag(item, errors, message)


def has_blocking_errors(preview):
    return any(FIELD in entry["errors"] for entry in preview["errors"])


def _problem(item, context, may_link):
    foreign, rows_by_value, existing, holders, coded_products = context
    data = item["data"]
    value = data[FIELD]
    if not may_link:
        return gettext("You need QR management permission to link QR codes.")
    others = [row for row in rows_by_value[value] if row != item["row"]]
    if others:
        return gettext("Duplicate QR code in this file (also row {rows}).").format(
            rows=", ".join(str(row) for row in others))
    if data.get("tracking_mode") == TrackingMode.INDIVIDUAL:
        return gettext("Individual-tracked items take QR codes per unit; link those from the scanner.")
    product = existing.get(data.get("name"))
    target_id = product.id if product else None
    holder = holders.get(value)
    if holder is not None:
        code = holder_conflict_code(holder, QrCode.TargetType.PRODUCT, target_id)
        if code == "revoked":
            return gettext("This QR code was revoked in this makerspace and cannot be linked again.")
        if code is not None:
            return gettext("This QR code is already linked to another item; the existing link is kept.")
        return None
    if value in foreign:
        return gettext("This is a SpaceWorks label from another makerspace and cannot be linked here.")
    if product is not None and product.id in coded_products:
        return gettext("This item already has an active QR code. Revoke it before linking another.")
    return None


def _flag(item, errors, message):
    item["action"] = "error"
    for entry in errors:
        if entry["row"] == item["row"]:
            entry["errors"][FIELD] = message
            return
    errors.append({"row": item["row"], "errors": {FIELD: message}})
