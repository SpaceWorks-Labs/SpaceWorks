"""Presentation entries: Machine, service, maintenance, warranty and procurement audit actions.

Generated from the audit AST discovery, then reviewed. Every literal action has one
entry; ``permitted`` lists only reviewed non-personal LEAF paths (no names, free
text, secrets, object keys or before/after payloads)."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("consumable.cost_recorded", gettext_noop("Consumable cost recorded")),
    P("certification.granted", gettext_noop("Certification granted")),
    P("certification.override", gettext_noop("Certification override"), ("certification_type_id",)),
    P("certification.revoked", gettext_noop("Certification revoked"),
      ("certification_type_id", "membership_id")),
    P("certification_type.created", gettext_noop("Certification type created"), ("machine_type_id",)),
    P("certification_type.deactivated", gettext_noop("Certification type deactivated")),
    P("certification_type.updated", gettext_noop("Certification type updated"), ("fields",)),
    P("machine.created", gettext_noop("Machine created")),
    P("machine.publicity_changed", gettext_noop("Machine publicity changed")),
    P("machine.status_changed", gettext_noop("Machine status changed")),
    P("machine.typed_usage_logged", gettext_noop("Machine typed usage logged")),
    P("machine.updated", gettext_noop("Machine updated")),
    P("machine_service.consumption_recorded", gettext_noop("Machine service consumption recorded")),
    P("machine_service.file_attached", gettext_noop("Machine service file attached")),
    P("machine_service.file_deleted", gettext_noop("Machine service file deleted")),
    P("machine_service.file_staged", gettext_noop("Machine service file staged")),
    P("machine_type.created", gettext_noop("Machine type created")),
    P("machine_type.updated", gettext_noop("Machine type updated")),
    P("machine_type_pricing.set", gettext_noop("Machine type pricing set")),
    P("machine_type_pricing.updated", gettext_noop("Machine type pricing updated")),
    P("maintenance.document_added", gettext_noop("Maintenance document added"),
      ("log_id", "machine_id", "size_bytes")),
    P("maintenance.document_deleted", gettext_noop("Maintenance document deleted"),
      ("document_id", "log_id", "machine_id", "size_bytes")),
    P("maintenance.logged", gettext_noop("Maintenance logged")),
    P("maintenance.schedule_completed", gettext_noop("Maintenance schedule completed"),
      ("interval_days", "log_id", "new_next_due", "old_next_due")),
    P("maintenance.schedule_created", gettext_noop("Maintenance schedule created"),
      ("interval_days", "machine_id")),
    P("maintenance.schedule_deactivated", gettext_noop("Maintenance schedule deactivated"), ("machine_id",)),
    P("maintenance.schedule_updated", gettext_noop("Maintenance schedule updated"), ("changed_fields",)),
    P("procurement.item_added", gettext_noop("Procurement item added")),
    P("procurement.item_removed", gettext_noop("Procurement item removed")),
    P("procurement.item_updated", gettext_noop("Procurement item updated")),
    P("procurement.low_stock_flagged", gettext_noop("Procurement low stock flagged"),
      ("pool_id", "remaining", "threshold", "to_buy_item_id")),
    P("procurement.moved_to_inventory", gettext_noop("Procurement moved to inventory"),
      ("item_id", "mode", "product_id", "quantity")),
    P("procurement.moved_to_printing", gettext_noop("Procurement moved to printing"),
      ("item_id", "kernel", "result_id")),
    P("procurement.receipt_added", gettext_noop("Procurement receipt added")),
    P("procurement.receipt_removed", gettext_noop("Procurement receipt removed")),
    P("warranty.created", gettext_noop("Warranty created")),
    P("warranty.document_added", gettext_noop("Warranty document added")),
    P("warranty.document_removed", gettext_noop("Warranty document removed")),
    P("warranty.updated", gettext_noop("Warranty updated")),
)
