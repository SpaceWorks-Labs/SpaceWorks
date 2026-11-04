"""NOT REGISTERED. Analytics views pre-written for lanes that are not in this lane's base.

At merge, once a lane's models are on the combined tree, move its tuple into a domain module
(``donations.py``, ``shop.py``; the L21a views go into ``events.py``), add the domain to
``registry.DOMAIN_MODULES``, bump ``VIEWS_VERSION`` (set ``since`` to the new version), and
document the views in docs/analytics-views.md. ``View.installed()`` already skips a view whose
app is absent, but nothing here is imported until then.

Never exposed (coordinator instruction for L18): ``payments.DonorTaxDetail``, every ``donor_*``
and ``contact_*`` column, ``access_secret``, ``manage_secret``, ``tax_receipt`` and the whole
personal calendar feed table (so donations carry no donor id either). L22 (its L25 contract): never ``pickup_code``, ``status_secret``, ``digest``,
``guest_*``, ``pricing_snapshot`` or image keys; the buyer id is masked like a name and no
created_by, collected_by, actor or cash-session user id appears at all. L21b (its L25 contract):
the payout ``recipient_id`` is masked; payout references, judge notes and criterion values never appear. L21a: never answers, dietary notes or
consents. L24 adds refund reasons only: the registered ``refund_cases`` view already covers
them (its ``reason_code`` column), so L24 needs no new view.
"""

from .types import Col, View

L18_DONATIONS = (
    View("donation_campaigns", "donations", "Donation campaigns and funds with their goals.",
         "FROM {payments.DonationCampaign} c", "c.makerspace_id", (
             Col("campaign_id", "c.id", "Campaign id."),
             Col("kind", "c.kind", "Campaign or standing fund."),
             Col("name", "c.name", "Campaign name."),
             Col("goal_amount", "c.goal_amount", "Goal."),
             Col("currency", "c.currency", "Currency."),
             Col("starts_at", "c.starts_at", "Opens."),
             Col("ends_at", "c.ends_at", "Closes."),
             Col("is_active", "c.is_active", "Open."),
             Col("is_public", "c.is_public", "Public."),
             Col("created_at", "c.created_at", "Created."),
         ), since=2),
    View("donations", "donations", "Donations: amount, campaign and state; no donor column at all.",
         "FROM {payments.Donation} d", "d.makerspace_id", (
             Col("donation_id", "d.id", "Donation id."),
             Col("campaign_id", "d.campaign_id", "Campaign (donation_campaigns)."),
             Col("pledge_id", "d.pledge_id", "Recurring pledge it came from."),
             Col("amount", "d.amount", "Amount."),
             Col("currency", "d.currency", "Currency."),
             Col("source", "d.source", "Online, cash and so on."),
             Col("status", "d.status", "Donation state."),
             Col("wants_tax_receipt", "d.wants_tax_receipt", "Asked for a tax receipt."),
             Col("period_start", "d.period_start", "Pledge period it pays."),
             Col("created_at", "d.created_at", "Recorded."),
             Col("paid_at", "d.paid_at", "Paid."),
             Col("cancelled_at", "d.cancelled_at", "Cancelled."),
         ), since=2),
    View("donation_pledges", "donations", "Recurring donation pledges.",
         "FROM {payments.DonationPledge} p", "p.makerspace_id", (
             Col("pledge_id", "p.id", "Pledge id."),
             Col("campaign_id", "p.campaign_id", "Campaign (donation_campaigns)."),
             Col("amount", "p.amount", "Amount per period."),
             Col("currency", "p.currency", "Currency."),
             Col("interval", "p.interval", "Monthly, yearly and so on."),
             Col("status", "p.status", "Pledge state."),
             Col("starts_on", "p.starts_on", "Starts."),
             Col("next_due_on", "p.next_due_on", "Next due."),
             Col("ends_on", "p.ends_on", "Ends."),
             Col("created_at", "p.created_at", "Created."),
             Col("cancelled_at", "p.cancelled_at", "Cancelled."),
         ), since=2),
    View("donation_settings", "donations", "The space's donation page settings (amounts only).",
         "FROM {payments.DonationSettings} s", "s.makerspace_id", (
             Col("minimum_amount", "s.minimum_amount", "Minimum gift."),
             Col("tax_exempt_valid_until", "s.tax_exempt_valid_until", "Tax-exemption registration valid until."),
             Col("updated_at", "s.updated_at", "Last changed."),
         ), since=2),
    View("sponsor_tiers", "donations", "Sponsor tiers and their prices.",
         "FROM {payments.SponsorTier} t", "t.makerspace_id", (
             Col("tier_id", "t.id", "Tier id."),
             Col("name", "t.name", "Tier name."),
             Col("rank", "t.rank", "Order."),
             Col("amount", "t.amount", "Price."),
             Col("currency", "t.currency", "Currency."),
             Col("created_at", "t.created_at", "Created."),
         ), since=2),
    View("sponsors", "donations", "Sponsors (organisations) with their tier and term; no contact details.",
         "FROM {payments.Sponsor} s", "s.makerspace_id", (
             Col("sponsor_id", "s.id", "Sponsor id."),
             Col("name", "s.name", "Sponsor (an organisation) name."),
             Col("organization_id", "s.organization_id", "Linked organisation."),
             Col("tier_id", "s.tier_id", "Tier (sponsor_tiers)."),
             Col("starts_on", "s.starts_on", "Sponsorship starts."),
             Col("ends_on", "s.ends_on", "Sponsorship ends."),
             Col("show_on_wall", "s.show_on_wall", "Shown on the sponsor wall."),
             Col("created_at", "s.created_at", "Added."),
             Col("archived_at", "s.archived_at", "Archived."),
         ), since=2),
    View("sponsor_perks", "donations", "Perks owed to sponsors and whether they were delivered.",
         "FROM {payments.SponsorPerk} k", "k.makerspace_id", (
             Col("perk_id", "k.id", "Perk id."),
             Col("tier_id", "k.tier_id", "Tier template (sponsor_tiers)."),
             Col("sponsor_id", "k.sponsor_id", "Sponsor (sponsors)."),
             Col("due_on", "k.due_on", "Due."),
             Col("fulfilled_at", "k.fulfilled_at", "Delivered."),
             Col("created_at", "k.created_at", "Created."),
         ), since=2),
    View("sponsorship_charges", "donations", "Charges raised to sponsors.",
         "FROM {payments.SponsorshipCharge} c", "c.makerspace_id", (
             Col("sponsorship_charge_id", "c.id", "Charge id."),
             Col("sponsor_id", "c.sponsor_id", "Sponsor (sponsors)."),
             Col("amount", "c.amount", "Amount."),
             Col("currency", "c.currency", "Currency."),
             Col("created_at", "c.created_at", "Raised."),
         ), since=2),
    View("sponsor_event_links", "donations", "Which sponsors back which events.",
         "FROM {payments.SponsorEventLink} l", "l.makerspace_id", (
             Col("link_id", "l.id", "Link id."),
             Col("sponsor_id", "l.sponsor_id", "Sponsor (sponsors)."),
             Col("event_sponsor_id", "l.event_sponsor_id", "The event's sponsor entry."),
             Col("created_at", "l.created_at", "Linked."),
         ), since=2),
)

L21A_PARTICIPATION = (
    View("application_decisions", "events", "Committed admission decisions, per stage.",
         "FROM {events.ApplicationDecision} d JOIN {events.ApplicationDecisionBatch} b ON b.id = d.batch_id "
         "JOIN {events.Event} e ON e.id = b.event_id", "e.makerspace_id", (
             Col("decision_id", "d.id", "Decision id."),
             Col("event_id", "b.event_id", "Event (events)."),
             Col("application_id", "d.application_id", "Application (event_applications)."),
             Col("stage_id", "d.stage_id", "Admission stage."),
             Col("outcome", "d.outcome", "Offer, waitlist, reject or advance."),
             Col("reason_code", "d.reason_code", "Reason code."),
             Col("batch_state", "b.state", "Draft, committed or cancelled batch."),
             Col("sent_at", "d.sent_at", "Sent to the applicant."),
         ), since=2),
    View("event_crew", "events", "Event crew (volunteers, mentors and others); no answers or dietary notes.",
         "FROM {events.EventCrewMember} c", "c.makerspace_id", (
             Col("crew_id", "c.id", "Crew entry id."),
             Col("event_id", "c.event_id", "Event (events)."),
             Col("member_id", "c.member_id", "Crew member (members)."),
             Col("origin", "c.origin", "Signed up or invited."),
             Col("crew_role", "c.crew_role", "Role on the crew."),
             Col("state", "c.state", "Crew state."),
             Col("decided_at", "c.decided_at", "Decided."),
             Col("created_at", "c.created_at", "Joined."),
         ), since=2),
)

L22_SHOP = (
    View("shop_products", "shop", "Shop products.",
         "FROM {shop.ShopProduct} p", "p.makerspace_id", (
             Col("shop_product_id", "p.id", "Product id."),
             Col("kind", "p.kind", "Product kind."),
             Col("name", "p.name", "Product name."),
             Col("category", "p.category", "Category."),
             Col("members_only", "p.members_only", "Members only."),
             Col("is_public", "p.is_public", "Public."),
             Col("is_active", "p.is_active", "On sale."),
             Col("created_at", "p.created_at", "Added."),
             Col("archived_at", "p.archived_at", "Archived."),
         ), since=2),
    View("shop_variants", "shop", "Shop variants with price and stock.",
         "FROM {shop.ShopVariant} v", "v.makerspace_id", (
             Col("shop_variant_id", "v.id", "Variant id."),
             Col("shop_product_id", "v.product_id", "Product (shop_products)."),
             Col("name", "v.name", "Variant name."),
             Col("sku", "v.sku", "Stock-keeping code."),
             Col("price", "v.price", "Price."),
             Col("on_hand", "v.on_hand", "Units on hand."),
             Col("held", "v.held", "Units held for open orders."),
             Col("reorder_point", "v.reorder_point", "Reorder point."),
             Col("is_active", "v.is_active", "On sale."),
         ), since=2),
    View("shop_orders", "shop", "Shop orders; the buyer is a member id only.",
         "FROM {shop.ShopOrder} o", "o.makerspace_id", (
             Col("shop_order_id", "o.id", "Order id."),
             Col("channel", "o.channel", "Online or desk (point of sale)."),
             Col("status", "o.status", "Order state."),
             Col("member_id", "o.buyer_id", "Buyer with an account (members); masked unless member details are on.",
                 pii=True, pii_type="bigint"),
             Col("pickup_at", "o.pickup_at", "Pickup place."),
             Col("currency", "o.currency", "Currency."),
             Col("subtotal", "o.subtotal", "Before discounts."),
             Col("discount_total", "o.discount_total", "Discounts."),
             Col("tax_total", "o.tax_total", "Tax."),
             Col("total", "o.total", "Total."),
             Col("created_at", "o.created_at", "Created."),
             Col("paid_at", "o.paid_at", "Paid."),
             Col("collected_at", "o.collected_at", "Collected."),
             Col("closed_at", "o.closed_at", "Closed."),
             Col("close_reason", "o.close_reason", "Why it closed."),
         ), since=2),
    View("shop_order_lines", "shop", "The variants and quantities of each shop order.",
         "FROM {shop.ShopOrderLine} l JOIN {shop.ShopOrder} o ON o.id = l.order_id", "o.makerspace_id", (
             Col("shop_order_line_id", "l.id", "Line id."),
             Col("shop_order_id", "l.order_id", "Order (shop_orders)."),
             Col("shop_variant_id", "l.variant_id", "Variant (shop_variants)."),
             Col("quantity", "l.quantity", "Quantity."),
             Col("unit_amount", "l.unit_amount", "Unit price."),
             Col("discount_amount", "l.discount_amount", "Discount."),
             Col("tax_amount", "l.tax_amount", "Tax."),
             Col("line_total", "l.line_total", "Line total."),
         ), since=2),
    View("shop_returns", "shop", "Returned shop items and the refund cases they opened.",
         "FROM {shop.ShopOrderReturn} r", "r.makerspace_id", (
             Col("shop_return_id", "r.id", "Return id."),
             Col("shop_order_id", "r.order_id", "Order (shop_orders)."),
             Col("quantity", "r.quantity", "Units returned."),
             Col("disposition", "r.disposition", "Restocked, written off and so on."),
             Col("amount", "r.amount", "Amount."),
             Col("refund_case_id", "r.refund_case_id", "Refund case (refund_cases)."),
             Col("created_at", "r.created_at", "Recorded."),
         ), since=2),
)

L22_SHOP += (
    View("shop_stock_movements", "shop", "Stock movements per variant (no reason text, no actor).",
         "FROM {shop.ShopStockMovement} m", "m.makerspace_id", (
             Col("movement_id", "m.id", "Movement id."),
             Col("shop_variant_id", "m.variant_id", "Variant (shop_variants)."),
             Col("kind", "m.kind", "Sale, restock, return, adjustment and so on."),
             Col("quantity", "m.quantity", "Units (negative leaves stock)."),
             Col("balance_after", "m.balance_after", "Stock after the movement."),
             Col("shop_order_id", "m.order_id", "Order, if any (shop_orders)."),
             Col("created_at", "m.created_at", "Recorded."),
         ), since=2),
    View("shop_checkout_holds", "shop", "Stock held for open orders, and why each hold ended.",
         "FROM {shop.ShopCheckoutHold} h", "h.makerspace_id", (
             Col("hold_id", "h.id", "Hold id."),
             Col("shop_order_id", "h.order_id", "Order (shop_orders)."),
             Col("shop_variant_id", "h.variant_id", "Variant (shop_variants)."),
             Col("quantity", "h.quantity", "Units held."),
             Col("expires_at", "h.expires_at", "Hold expires."),
             Col("released_at", "h.released_at", "Released."),
             Col("release_reason", "h.release_reason", "Paid, expired or cancelled."),
             Col("created_at", "h.created_at", "Placed."),
         ), since=2),
    View("shop_cash_sessions", "shop", "Desk cash sessions: amounts and times only.",
         "FROM {shop.ShopCashSession} c", "c.makerspace_id", (
             Col("cash_shift_id", "c.id", "Cash session (shift) id."),
             Col("status", "c.status", "Open, closing or closed."),
             Col("currency", "c.currency", "Currency."),
             Col("opening_float", "c.opening_float", "Float at opening."),
             Col("expected_cash", "c.expected_cash", "Cash expected at close."),
             Col("counted_cash", "c.counted_cash", "Cash counted at close."),
             Col("variance", "c.variance", "Counted minus expected."),
             Col("opened_at", "c.opened_at", "Opened."),
             Col("closed_at", "c.closed_at", "Closed."),
         ), since=2),
)
