"""Analytics views: the To-Buy list (items and machine supplies). No links or purchaser."""

from .types import Col, View

VIEWS = (
    View("to_buy_items", "procurement", "To-Buy entries from request to stock, with costs.",
         "FROM {procurement.ToBuyItem} t", "t.makerspace_id", (
             Col("to_buy_id", "t.id", "Entry id."),
             Col("kind", "t.kind", "Inventory or machine supply."),
             Col("machine_type_id", "t.machine_type_id", "Machine type, for machine supplies (machine_types)."),
             Col("name", "t.name", "What to buy."),
             Col("quantity", "t.quantity", "Quantity."),
             Col("status", "t.status", "Entry state."),
             Col("estimated_unit_cost", "t.estimated_unit_cost", "Estimated unit cost."),
             Col("actual_unit_cost", "t.actual_unit_cost", "Paid unit cost."),
             Col("vendor_name", "t.vendor_name", "Vendor (a business, not a person)."),
             Col("created_at", "t.created_at", "Added."),
             Col("ordered_at", "t.ordered_at", "Ordered."),
             Col("received_at", "t.received_at", "Received."),
             Col("moved_to_inventory_at", "t.moved_to_inventory_at", "Moved into stock."),
         )),
)
