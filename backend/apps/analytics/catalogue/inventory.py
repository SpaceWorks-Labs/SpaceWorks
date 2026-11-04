"""Analytics views: inventory and loans. No storage location, box, QR, evidence or contact."""

from .types import Col, View

D = "inventory"
_QTY = tuple(
    Col(f"{name}_quantity", f"p.{name}_quantity", f"Units {label}.")
    for name, label in (("total", "in the catalogue"), ("available", "free to lend now"),
                        ("reserved", "reserved for accepted requests"), ("issued", "out on loan"),
                        ("damaged", "recorded damaged"), ("lost", "recorded lost"),
                        ("needs_fix", "waiting for repair"))
)

VIEWS = (
    View("inventory_products", D, "Every catalogue item with its live quantity counts.",
         "FROM {inventory.InventoryProduct} p", "p.makerspace_id", (
             Col("product_id", "p.id", "Item id."),
             Col("category_id", "p.category_id", "Category (inventory_categories)."),
             Col("name", "p.name", "Item name."),
             Col("manufacturer", "p.manufacturer", "Manufacturer."),
             Col("model", "p.model", "Model."),
             Col("sku", "p.sku", "Stock-keeping code."),
             Col("tracking_mode", "p.tracking_mode", "Quantity or per-asset tracking."),
             Col("is_consumable", "p.is_consumable", "Used up rather than lent."),
             *_QTY,
             Col("unit_cost", "p.unit_cost", "Unit cost, if recorded."),
             Col("cost_currency", "p.cost_currency", "Currency of the unit cost."),
             Col("deposit_amount", "p.deposit_amount", "Deposit asked when lent."),
             Col("is_public", "p.is_public", "Listed in the public catalogue."),
             Col("is_archived", "p.is_archived", "Archived item."),
             Col("created_at", "p.created_at", "When the item was added."),
         )),
    View("inventory_categories", D, "Catalogue categories.",
         "FROM {inventory.Category} c", "c.makerspace_id", (
             Col("category_id", "c.id", "Category id."),
             Col("name", "c.name", "Category name."),
             Col("loan_days", "c.loan_days", "Default loan length in days."),
             Col("max_renewals", "c.max_renewals", "Renewals allowed."),
             Col("created_at", "c.created_at", "When the category was added."),
         )),
    View("loan_requests", D, "Borrow requests through their lifecycle; the borrower is a member id only.",
         "FROM {hardware_requests.HardwareRequest} r", "r.makerspace_id", (
             Col("request_id", "r.id", "Request id."),
             Col("member_id", "r.requester_id", "Borrower (members); empty for account-less requests."),
             Col("status", "r.status", "Request state."),
             Col("created_at", "r.created_at", "Submitted."),
             Col("accepted_at", "r.accepted_at", "Accepted."),
             Col("issued_at", "r.issued_at", "Handed over."),
             Col("return_due_at", "r.return_due_at", "Due back."),
             Col("closed_at", "r.closed_at", "Closed."),
             Col("renewal_count", "r.renewal_count", "Renewals taken."),
             Col("days_out", "CASE WHEN r.issued_at IS NULL THEN NULL ELSE round((extract(epoch FROM "
                 "coalesce(r.closed_at, now()) - r.issued_at) / 86400.0)::numeric, 2) END",
                 "Days between hand-over and close (or now)."),
         )),
    View("loan_request_items", D, "The items and quantities of each borrow request.",
         "FROM {hardware_requests.HardwareRequestItem} i "
         "JOIN {hardware_requests.HardwareRequest} r ON r.id = i.request_id", "r.makerspace_id", (
             Col("request_item_id", "i.id", "Line id."),
             Col("request_id", "i.request_id", "Request (loan_requests)."),
             Col("product_id", "i.product_id", "Item (inventory_products)."),
             *(Col(f"{name}_quantity", f"i.{name}_quantity", f"Units {name.replace('_', ' ')}.")
               for name in ("requested", "accepted", "issued", "returned", "damaged", "missing", "needs_fix")),
         )),
    View("tool_loans", D, "Self-checkout and direct-handout loans of QR-tracked tools.",
         "FROM {hardware_requests.PublicToolLoan} l", "l.makerspace_id", (
             Col("tool_loan_id", "l.id", "Loan id."),
             Col("member_id", "l.requester_id", "Borrower (members)."),
             Col("request_id", "l.request_id", "Linked request, if any."),
             Col("target_type", "l.target_type", "Item or container."),
             Col("target_label", "l.target_label", "What was lent."),
             Col("status", "l.status", "Loan state."),
             Col("source", "l.source", "Self-checkout, kiosk or staff handout."),
             Col("checked_out_at", "l.checked_out_at", "Checked out."),
             Col("due_at", "l.due_at", "Due back."),
             Col("returned_at", "l.returned_at", "Returned."),
         )),
)
