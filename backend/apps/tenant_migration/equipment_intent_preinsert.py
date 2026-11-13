"""Resolve receipt history against already-materialized, tenant-scoped rows."""
from django.apps import apps

from apps.backup.capture_managers import every_row
from .archive_stream import database_value
from .insertion_errors import ArchiveFormatError, PrimaryKeyMapUnavailable
from .pii_equipment_intent import rebind_equipment_intent
from .pii_equipment_use_intent import rebind_use_intent

_OWNER_PATHS = {
    "events.EventRegistration": "event__makerspace_id",
    "bookings.Booking": "space__makerspace_id",
    "hardware_requests.LoanWaitlistEntry": "makerspace_id",
    "hardware_requests.HardwareRequest": "makerspace_id",
    "inventory.InventoryProduct": "makerspace_id",
    "inventory.EquipmentKitTemplate": "makerspace_id",
    "inventory.EquipmentKitAllocation": "makerspace_id",
    "inventory.EquipmentConsumablePlan": "makerspace_id",
    "operations.InventoryAdjustment": "makerspace_id",
}


def prepare_receipt_creator(row, pk_map, references):
    """Only a historical actor can become unavailable; required FKs stay strict."""
    creator = row["creator_id"]
    if creator is None:
        if not row["imported_nonreplayable"]:
            raise ArchiveFormatError("A replayable equipment receipt lacks its creator.")
        return True
    try:
        User = apps.get_model("accounts.User")
        mapped = pk_map.lookup(User, creator)
        if not references.equipment_identity_resolved(creator, mapped) or not every_row(User).filter(pk=mapped).exists():
            raise PrimaryKeyMapUnavailable("Historical creator was not retained.")
    except PrimaryKeyMapUnavailable:
        row["creator_id"] = None
        return True
    return False


def retained_source(label, source_id, *, pk_map, references, target):
    referenced = apps.get_model(label)
    mapped = pk_map.lookup(referenced, source_id)
    if not references.equipment_materialized(label, source_id, mapped):
        raise PrimaryKeyMapUnavailable("Historical intent source was not materialized.")
    if not every_row(referenced).filter(pk=mapped, **{_OWNER_PATHS[label]: target.pk}).exists():
        raise PrimaryKeyMapUnavailable("Historical intent reference was not retained.")
    return mapped


def rebind_receipt_before_insert(model, raw, *, source, row, job, target, deks, pk_map, references, creator_unavailable):
    source = dict(source)
    names = ["id", "creator", "operation_id", "imported_nonreplayable", "intent_version"]
    names += ["borrower", "fingerprint_version", "request", "consumable_plan"] if model._meta.label == "inventory.EquipmentProposalReceipt" else ["product", "quantity", "allocation", "plan", "adjustment"]
    for name in names:
        field = model._meta.get_field(name)
        source[field.attname] = database_value(field, source[field.attname])

    def retained(label, source_id):
        return retained_source(label, source_id, pk_map=pk_map, references=references, target=target)

    if model._meta.label == "inventory.EquipmentProposalReceipt":
        if not every_row(apps.get_model("accounts.User")).filter(pk=row["borrower_id"]).exists():
            raise ArchiveFormatError("Equipment proposal borrower was not retained.")
        if (source["request_id"] is None) == (source["consumable_plan_id"] is None):
            raise ArchiveFormatError("Equipment proposal has no unique required outcome.")
        label, key = (("hardware_requests.HardwareRequest", "request_id") if source["request_id"] is not None else ("inventory.EquipmentConsumablePlan", "consumable_plan_id"))
        if retained(label, source[key]) != row[key]:
            raise ArchiveFormatError("Equipment proposal outcome was not retained.")
    else:
        # These are live required receipt edges, not optional historical intent
        # selectors. A missing retained edge must abort the import.
        required = [("inventory.InventoryProduct", "product_id"), ("operations.InventoryAdjustment", "adjustment_id")]
        if (source["allocation_id"] is None) == (source["plan_id"] is None):
            raise ArchiveFormatError("Consumable use receipt has no unique required source.")
        required.append(("inventory.EquipmentKitAllocation", "allocation_id") if source["allocation_id"] is not None else ("inventory.EquipmentConsumablePlan", "plan_id"))
        for label, key in required:
            if source[key] is None or retained(label, source[key]) != row[key]:
                raise ArchiveFormatError("Consumable use receipt required reference was not retained.")
    helper = rebind_equipment_intent if model._meta.label == "inventory.EquipmentProposalReceipt" else rebind_use_intent
    return helper(model, raw, source=source, row=row,
        source_id=int(job.source_makerspace_id), target_id=target.pk, deks=deks, map_id=retained, creator_unavailable=creator_unavailable)
