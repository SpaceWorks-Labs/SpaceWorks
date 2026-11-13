"""Presentation entries: release-2 lane L12 (consumables, vendors, loans depth, machine jobs).

``permitted`` lists only reviewed non-personal leaf paths (ids, counts, statuses, timings);
a member's free-text reason or note stays in the raw audit row for auditors."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("procurement.auto_tobuy_created", gettext_noop("Automatic To-Buy created"),
      ("to_buy_item_id", "product_id", "consumable_id", "available", "reorder_point", "remaining", "threshold")),
    P("procurement.consumable_refilled", gettext_noop("Machine consumable refilled from To-Buy"),
      ("item_id", "consumable_id", "amount", "remaining")),
    P("procurement.bought", gettext_noop("To-Buy item marked bought"),
      ("item_id", "ledger_entry_id", "vendor_id", "domain", "machine_type_id", "credited_product_id",
       "credited_consumable_id")),
    P("vendor.created", gettext_noop("Vendor added"), ("vendor_id",)),
    P("vendor.updated", gettext_noop("Vendor changed"), ("vendor_id", "fields")),
    P("vendor.archived", gettext_noop("Vendor archived"), ("vendor_id", "fields")),
    P("request.cancelled", gettext_noop("Request withdrawn"), ("from_status", "by_owner", "released_units")),
    P("request.expired", gettext_noop("Request expired uncollected"), ("pickup_until", "released_units")),
    P("inventory.waitlist_joined", gettext_noop("Joined a waitlist"), ("entry_id", "product_id", "quantity")),
    P("inventory.waitlist_offered", gettext_noop("Waitlist offer held"), ("entry_id", "product_id", "quantity")),
    P("inventory.waitlist_claimed", gettext_noop("Waitlist offer claimed"),
      ("entry_id", "product_id", "request_id"), request_refs=("request_id",)),
    P("inventory.waitlist_lapsed", gettext_noop("Waitlist offer lapsed"), ("entry_id", "product_id")),
    P("inventory.waitlist_left", gettext_noop("Left a waitlist"), ("entry_id", "product_id")),
    P("machine_downtime.started", gettext_noop("Machine out of service"), ("downtime_id", "kind")),
    P("machine_downtime.ended", gettext_noop("Machine back in service"), ("downtime_id", "kind")),
    P("machine_downtime.updated", gettext_noop("Downtime details updated"), ("downtime_id",)),
    P("machine_type.job_settings_updated", gettext_noop("Machine type job settings changed"), ("machine_type_id", "fields")),
    P("work_order.created", gettext_noop("Work order opened"), ("work_order_id", "subject_type", "machine_id", "priority")),
    P("work_order.started", gettext_noop("Work order started"), ("work_order_id", "subject_type", "machine_id")),
    P("work_order.held", gettext_noop("Work order put on hold"), ("work_order_id", "subject_type", "machine_id")),
    P("work_order.closed", gettext_noop("Work order closed"), ("work_order_id", "subject_type", "machine_id", "log_id")),
    P("work_order.cancelled", gettext_noop("Work order cancelled"), ("work_order_id", "subject_type", "machine_id")),
    P("work_order.assigned", gettext_noop("Work order assigned"), ("work_order_id", "subject_type", "assigned")),
)
