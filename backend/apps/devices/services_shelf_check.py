"""The "Check shelves" walk (decision 331c): list locations, save one walk as a ShelfCheck, read past walks.

Authorised like the rest of shelf work (404 while ``machines.integrations`` is off) but writing a check needs
``EDIT_INVENTORY`` or ``MANAGE_DEVICES``: handover staff may light a shelf, not sign off a stock walk. Locations come
only from this space's own products, never from the client, so a check cannot name a place that is not there.
"""
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit import services as audit
from apps.devices.models import ShelfCheck
from apps.devices.services_adapter_core import AdapterError
from apps.devices.services_shelf_pointer import Action, _live_poses, authorize

CHECK_ACTIONS = (Action.EDIT_INVENTORY, Action.MANAGE_DEVICES)
MAX_LOCATIONS = 500


def _products(makerspace_id):
    from apps.inventory.models import InventoryProduct
    return InventoryProduct.objects.filter(makerspace_id=makerspace_id, is_archived=False).exclude(storage_location="")


def locations(actor, makerspace_id, prefix=""):
    """Every storage location in the space (optionally one shelf prefix) with its item count and pointer coverage."""
    authorize(actor, makerspace_id)
    rows = _products(makerspace_id)
    if prefix:
        rows = rows.filter(storage_location__istartswith=prefix)
    counts = rows.values("storage_location").annotate(items=Count("pk")).order_by("storage_location")
    covered = {p.target_id for p in _live_poses(makerspace_id) if p.target_type == "storage_location"}
    return [{"location": r["storage_location"], "item_count": r["items"],
             "covered": r["storage_location"] in covered} for r in counts[:MAX_LOCATIONS]]


def record(actor, makerspace_id, scope_label, entries):
    authorize(actor, makerspace_id, CHECK_ACTIONS)
    known = set(_products(makerspace_id).values_list("storage_location", flat=True).distinct())
    seen = set()
    for entry in entries:
        if entry["location"] not in known or entry["location"] in seen:
            raise AdapterError("invalid_location", "Each location must be one of this space's storage locations, once.")
        seen.add(entry["location"])
    ok = sum(1 for e in entries if e["status"] == "ok")
    from apps.makerspaces.models import Makerspace
    makerspace = Makerspace.objects.get(pk=makerspace_id)
    with transaction.atomic():
        from apps.managed_hosting.extra_quotas import check_extra_quota_locked
        check_extra_quota_locked(makerspace, "shelf_checks_monthly")  # decision 337e: refuses only a NEW check
        row = ShelfCheck.objects.create(
            makerspace=makerspace, checked_by=actor, scope_label=scope_label, ok_count=ok,
            attention_count=len(entries) - ok, created_at=timezone.now(),
            entries=[{"location": e["location"], "status": e["status"], "note": e.get("note", "")} for e in entries])
        audit.record(actor, "devices.shelf_check_saved", makerspace=makerspace, target=makerspace, meta={
            "shelf_check_id": str(row.pk), "ok_count": row.ok_count, "attention_count": row.attention_count})
    return row


def history(actor, makerspace_id):
    authorize(actor, makerspace_id)
    return ShelfCheck.objects.filter(makerspace_id=makerspace_id).select_related("checked_by").order_by(
        "-created_at", "-id")


def detail(actor, pk):
    row = ShelfCheck.objects.select_related("checked_by").filter(pk=pk).first()
    if row is None:
        raise NotFound()
    authorize(actor, row.makerspace_id)
    return row
