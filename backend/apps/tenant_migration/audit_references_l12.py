"""Audit metadata IDs written by release-2 lane L12 (consumables, vendors, loans, machine jobs)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


EDGES = {
    **_remap("procurement.ToBuyItem", ("procurement.auto_tobuy_created", "to_buy_item_id"),
             ("procurement.consumable_refilled", "item_id"), ("procurement.bought", "item_id")),
    **_remap("inventory.InventoryProduct", ("procurement.auto_tobuy_created", "product_id"),
             ("inventory.waitlist_joined", "product_id"), ("inventory.waitlist_offered", "product_id"),
             ("inventory.waitlist_claimed", "product_id"), ("inventory.waitlist_lapsed", "product_id"),
             ("inventory.waitlist_left", "product_id")),
    **_remap("machines.MachineConsumable", ("procurement.auto_tobuy_created", "consumable_id"),
             ("procurement.consumable_refilled", "consumable_id")),
    **_remap("payments.LedgerEntry", ("procurement.bought", "ledger_entry_id")),
    **_remap("machines.MachineType", ("procurement.bought", "machine_type_id")),
    **_remap("inventory.InventoryProduct", ("procurement.bought", "credited_product_id")),
    **_remap("machines.MachineConsumable", ("procurement.bought", "credited_consumable_id")),
    **_remap("procurement.Vendor", ("procurement.bought", "vendor_id"), ("vendor.created", "vendor_id"),
             ("vendor.updated", "vendor_id"), ("vendor.archived", "vendor_id")),
    **_remap("hardware_requests.LoanWaitlistEntry", ("inventory.waitlist_joined", "entry_id"),
             ("inventory.waitlist_offered", "entry_id"), ("inventory.waitlist_claimed", "entry_id"),
             ("inventory.waitlist_lapsed", "entry_id"), ("inventory.waitlist_left", "entry_id")),
    **_remap("hardware_requests.HardwareRequest", ("inventory.waitlist_claimed", "request_id")),
    **_remap("machines.MachineDowntime", ("machine_downtime.started", "downtime_id"),
             ("machine_downtime.ended", "downtime_id"), ("machine_downtime.updated", "downtime_id")),
    **_remap("machines.MachineType", ("machine_type.job_settings_updated", "machine_type_id")),
    **_remap("maintenance.WorkOrder", *((f"work_order.{event}", "work_order_id") for event in (
        "created", "started", "held", "closed", "cancelled", "assigned"))),
    **_remap("machines.Machine", *((f"work_order.{event}", "machine_id") for event in (
        "created", "started", "held", "closed", "cancelled"))),
    **_remap("maintenance.MaintenanceLog", ("work_order.closed", "log_id")),
}
