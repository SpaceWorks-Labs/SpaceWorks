"""Analytics views: ticket types, ticket orders and order lines (L6). No quote digests,
pricing snapshots, claim tokens or attendee emails."""

from .types import Col, View

D = "tickets"
VIEWS = (
    View("event_ticket_types", D, "Ticket types and their prices.",
         "FROM {events.EventTicketType} t", "t.makerspace_id", (
             Col("ticket_type_id", "t.id", "Ticket type id."),
             Col("event_id", "t.event_id", "Event (events)."),
             Col("series_id", "t.series_id", "Series, for a series ticket."),
             Col("name", "t.name", "Ticket name."),
             Col("amount", "t.amount", "Price."),
             Col("pricing_mode", "t.pricing_mode", "Fixed or pay-what-you-want."),
             Col("capacity", "t.capacity", "Seats on sale."),
             Col("is_active", "t.is_active", "On sale."),
             Col("sales_start_at", "t.sales_start_at", "Sales open."),
             Col("sales_end_at", "t.sales_end_at", "Sales close."),
         )),
    View("event_orders", D, "Ticket orders with their totals; the buyer is a member id only.",
         "FROM {events.EventOrder} o", "o.makerspace_id", (
             Col("order_id", "o.id", "Order id."),
             Col("event_id", "o.event_id", "Event (events)."),
             Col("series_id", "o.series_id", "Series, for a series pass."),
             Col("member_id", "o.buyer_id", "Buyer (members)."),
             Col("kind", "o.kind", "Order kind."),
             Col("status", "o.status", "Order state."),
             Col("currency", "o.currency", "Currency."),
             Col("subtotal", "o.subtotal", "Before discounts and fees."),
             Col("discount_total", "o.discount_total", "Discounts."),
             Col("fee_total", "o.fee_total", "Booking fees."),
             Col("total", "o.total", "Total."),
             Col("created_at", "o.created_at", "Created."),
             Col("paid_at", "o.paid_at", "Paid."),
             Col("closed_at", "o.closed_at", "Closed."),
         )),
    View("event_order_lines", D, "The tickets, add-ons and passes in each order.",
         "FROM {events.EventOrderLine} l JOIN {events.EventOrder} o ON o.id = l.order_id", "o.makerspace_id", (
             Col("order_line_id", "l.id", "Line id."),
             Col("order_id", "l.order_id", "Order (event_orders)."),
             Col("kind", "l.kind", "Ticket, add-on or pass."),
             Col("ticket_type_id", "l.ticket_type_id", "Ticket type (event_ticket_types)."),
             Col("addon_id", "l.addon_id", "Add-on."),
             Col("pass_type_id", "l.pass_type_id", "Series pass type."),
             Col("label", "l.label", "Line label."),
             Col("quantity", "l.quantity", "Quantity."),
             Col("unit_amount", "l.unit_amount", "Frozen unit price."),
             Col("discount_amount", "l.discount_amount", "Discount on the line."),
             Col("line_total", "l.line_total", "Line total."),
         )),
)
