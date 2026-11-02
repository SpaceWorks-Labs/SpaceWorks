"""Presentation entries: release-2 lane L12 (consumables, vendors, loans depth, machine jobs).

``permitted`` lists only reviewed non-personal leaf paths (ids, counts, statuses, timings);
a member's free-text reason or note stays in the raw audit row for auditors."""

from .presentation_catalog_types import P

ENTRIES = (
    P("procurement.auto_tobuy_created", "Automatic To-Buy created",
      ("to_buy_item_id", "product_id", "consumable_id", "available", "reorder_point", "remaining", "threshold")),
    P("procurement.consumable_refilled", "Machine consumable refilled from To-Buy",
      ("item_id", "consumable_id", "amount", "remaining")),
    P("procurement.bought", "To-Buy item marked bought",
      ("item_id", "ledger_entry_id", "vendor_id", "domain", "machine_type_id", "credited_product_id",
       "credited_consumable_id")),
    P("vendor.created", "Vendor added", ("vendor_id",)),
    P("vendor.updated", "Vendor changed", ("vendor_id", "fields")),
    P("vendor.archived", "Vendor archived", ("vendor_id", "fields")),
    P("request.cancelled", "Request withdrawn", ("from_status", "by_owner", "released_units")),
    P("request.expired", "Request expired uncollected", ("pickup_until", "released_units")),
    P("inventory.waitlist_joined", "Joined a waitlist", ("entry_id", "product_id", "quantity")),
    P("inventory.waitlist_offered", "Waitlist offer held", ("entry_id", "product_id", "quantity")),
    P("inventory.waitlist_claimed", "Waitlist offer claimed",
      ("entry_id", "product_id", "request_id"), request_refs=("request_id",)),
    P("inventory.waitlist_lapsed", "Waitlist offer lapsed", ("entry_id", "product_id")),
    P("inventory.waitlist_left", "Left a waitlist", ("entry_id", "product_id")),
    P("machine_downtime.started", "Machine out of service", ("downtime_id", "kind")),
    P("machine_downtime.ended", "Machine back in service", ("downtime_id", "kind")),
    P("machine_downtime.updated", "Downtime details updated", ("downtime_id",)),
    P("machine_type.job_settings_updated", "Machine type job settings changed", ("machine_type_id", "fields")),
    P("work_order.created", "Work order opened", ("work_order_id", "subject_type", "machine_id", "priority")),
    P("work_order.started", "Work order started", ("work_order_id", "subject_type", "machine_id")),
    P("work_order.held", "Work order put on hold", ("work_order_id", "subject_type", "machine_id")),
    P("work_order.closed", "Work order closed", ("work_order_id", "subject_type", "machine_id", "log_id")),
    P("work_order.cancelled", "Work order cancelled", ("work_order_id", "subject_type", "machine_id")),
    P("work_order.assigned", "Work order assigned", ("work_order_id", "subject_type", "assigned")),
)
