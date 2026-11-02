"""What "purge this capability's data" deletes, per folded capability (#128 C-8).

Since #97 maintenance, To-Buy and warranty are switches under each parent, so their data
purge follows the same split: purging `machines.tobuy` deletes printing (machine
consumable) rows only and never an inventory row, and the reverse. The old module purge
plans for `maintenance`/`procurement` are reused here, narrowed per parent.

Each plan offers `preview` (row counts, no writes) so the /control/ confirmation can show
exactly what goes before anything is deleted. Collectors obey the module-purge rules:
only what this capability owns, model imports function-local.
"""

from dataclasses import dataclass
from typing import Callable

from .module_purge_collectors import (
    maintenance_delete,
    maintenance_private_key_sizes,
    maintenance_private_keys,
)
from .module_purge_collectors_single_model import _counts, _delete


@dataclass(frozen=True)
class CapabilityPurgePlan:
    key: str
    summary: str
    delete: Callable
    preview: Callable
    private_keys: Callable | None = None
    private_key_sizes: Callable | None = None
    # Restore-rollback copies are filed under the app's old module key. Only a plan that
    # owns that whole key may sweep them; a per-parent split leaves them to retention.
    rollback_module: str | None = None
    public_image_keys: Callable | None = None


def _maintenance_preview(space):
    from apps.maintenance.models import (
        MaintenanceCalendarFeed, MaintenanceLog, MaintenanceLogDocument, MaintenanceSchedule,
    )
    return {
        "schedules": MaintenanceSchedule.objects.filter(machine__makerspace=space).count(),
        "logs": MaintenanceLog.objects.filter(machine__makerspace=space).count(),
        "documents": MaintenanceLogDocument.objects.filter(log__machine__makerspace=space).count(),
        "calendar_feeds": MaintenanceCalendarFeed.objects.filter(makerspace=space).count(),
    }


def _machine_work(space):
    """L12: machine work orders and the downtime ledger ride `machines.maintenance` too."""
    from apps.machines.models import MachineDowntime
    from apps.maintenance.models import WorkOrder
    return (WorkOrder.objects.filter(makerspace=space, subject_type="machine"),
            MachineDowntime.objects.filter(makerspace=space))


def _maintenance_delete(space, cursor):
    orders, downtimes = _machine_work(space)
    order_count, order_labels = _delete(orders)
    downtime_count, downtime_labels = _delete(downtimes)
    counts = maintenance_delete(space, cursor)
    return _counts(model_labels=counts.model_labels | order_labels | downtime_labels,
                   work_orders=order_count, downtime_periods=downtime_count, **counts)


def _maintenance_preview_all(space):
    orders, downtimes = _machine_work(space)
    return {**_maintenance_preview(space), "work_orders": orders.count(), "downtime_periods": downtimes.count()}


def _tobuy_items(space, kind):
    from apps.procurement.models import ToBuyItem
    return ToBuyItem.objects.filter(makerspace=space, kind=kind)


def _tobuy_receipts(space, kind):
    from apps.procurement.models import ToBuyReceipt
    return ToBuyReceipt.objects.filter(to_buy_item__makerspace=space, to_buy_item__kind=kind)


def _tobuy(kind):
    def delete(space, cursor):
        receipts, receipt_labels = _delete(_tobuy_receipts(space, kind))
        items, item_labels = _delete(_tobuy_items(space, kind))
        return _counts(model_labels=receipt_labels | item_labels, receipts=receipts, to_buy_items=items)

    def preview(space):
        return {"to_buy_items": _tobuy_items(space, kind).count(),
                "receipts": _tobuy_receipts(space, kind).count()}

    def keys(space, add):
        for key in _tobuy_receipts(space, kind).values_list("object_key", flat=True):
            add(key)

    return delete, preview, keys


def _warranties(space, host):
    from apps.warranty.models import Warranty
    return Warranty.objects.filter(makerspace=space, **{f"{host}__isnull": False})


def _warranty_documents(space, host):
    from apps.warranty.models import WarrantyDocument
    return WarrantyDocument.objects.filter(warranty__makerspace=space, **{f"warranty__{host}__isnull": False})


def _warranty(host):
    def delete(space, cursor):
        documents, document_labels = _delete(_warranty_documents(space, host))
        warranties, warranty_labels = _delete(_warranties(space, host))
        return _counts(model_labels=document_labels | warranty_labels,
                       documents=documents, warranties=warranties)

    def preview(space):
        return {"warranties": _warranties(space, host).count(),
                "documents": _warranty_documents(space, host).count()}

    def keys(space, add):
        for key in _warranty_documents(space, host).values_list("object_key", flat=True):
            add(key)

    return delete, preview, keys


def _sessions_delete(space, cursor):
    """L23: sessions and their amendments. Charges stay in the ledger; usage entries stay."""
    from apps.machines.models import MachineSession, MachineSessionAmendment
    amendments, amendment_labels = _delete(MachineSessionAmendment.objects.filter(makerspace=space))
    sessions, session_labels = _delete(MachineSession.objects.filter(makerspace=space))
    return _counts(model_labels=amendment_labels | session_labels, sessions=sessions, amendments=amendments)


def _sessions_preview(space):
    from apps.machines.models import MachineSession, MachineSessionAmendment
    return {"sessions": MachineSession.objects.filter(makerspace=space).count(),
            "amendments": MachineSessionAmendment.objects.filter(makerspace=space).count()}


_machine_tobuy, _inventory_tobuy = _tobuy("printing"), _tobuy("hardware")
_machine_warranty, _inventory_warranty = _warranty("machine"), _warranty("asset")

PLANS = (
    CapabilityPurgePlan(
        "machines.maintenance", "Machine maintenance schedules, logs, log documents, calendar feeds, machine "
        "work orders and the downtime ledger.",
        _maintenance_delete, _maintenance_preview_all, maintenance_private_keys,
        maintenance_private_key_sizes, rollback_module="maintenance",
    ),
    CapabilityPurgePlan(
        "machines.tobuy", "Machine-consumable (printing) To-Buy rows and their receipts. Inventory rows stay.",
        _machine_tobuy[0], _machine_tobuy[1], _machine_tobuy[2],
    ),
    CapabilityPurgePlan(
        "inventory.tobuy", "Inventory (hardware) To-Buy rows and their receipts. Machine-consumable rows stay.",
        _inventory_tobuy[0], _inventory_tobuy[1], _inventory_tobuy[2],
    ),
    CapabilityPurgePlan(
        "machines.warranty", "Warranty records and documents on machines. Asset warranties stay.",
        _machine_warranty[0], _machine_warranty[1], _machine_warranty[2],
    ),
    CapabilityPurgePlan(
        "inventory.warranty", "Warranty records and documents on inventory assets. Machine warranties stay.",
        _inventory_warranty[0], _inventory_warranty[1], _inventory_warranty[2],
    ),
    CapabilityPurgePlan(
        "machines.sessions", "Machine sessions and their staff corrections. Charges they raised stay in the "
        "ledger, and the machine-usage entries they wrote stay with the machine.",
        _sessions_delete, _sessions_preview,
    ),
)
BY_KEY = {plan.key: plan for plan in PLANS}
