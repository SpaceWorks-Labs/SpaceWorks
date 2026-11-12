# Decisions: Money and payments

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-360 — Payments review follow-ups
- **Area:** money
- **Date:** 12 November
- **Decision:** Retained Stripe keys survive a provider switch (documented); Connect fees for 3-decimal currencies round to tens of fils; an unparseable refund response means outcome unknown and stays reserved; Stripe checkout counts as paid only on `paid` or `no_payment_required`; Razorpay webhooks are deduplicated by signed-body hash.
- **Why:** Never mark money as settled or released on ambiguous provider answers.
- **Status:** current
- **Implemented in:** `backend/apps/payments_rail/`

### D-354 — Payments on mobile
- **Area:** money
- **Date:** 12 November
- **Decision:** Native payments cover member charges, history, receipts, the native payment sheet (Stripe PaymentSheet, Razorpay native SDK) with strong-authentication handling and status polling, "pay at desk" for unclaimed charges, typed rail-off responses and staff settlement/refunds; Connect onboarding is a browser exception and only publishable keys reach the app.
- **Why:** Payments are the highest-risk parity area.
- **Status:** current
- **Implemented in:** `docs/mobile/MOBILE-API-0.12.0.md`

### D-268 — Full 3-decimal money
- **Area:** money
- **Date:** 11 November
- **Decision:** Every money column is `MoneyDecimalField` (13 digits, 3 decimal places). A 3-decimal currency moves in 10-fils steps on the charge path because Stripe and Razorpay need the last minor digit to be 0, and an amount a provider cannot capture is refused, never rounded. Money reads back trimmed so existing displays keep their look. Superseded "I paid" claims or maker-checker proposals are marked REJECTED with an audit row when another path settles the charge. Shop orders accept an `Idempotency-Key` header; Razorpay refunds use `X-Refund-Idempotency`.
- **Why:** KWD, BHD, OMR, JOD and TND need real precision; supersedes the 2-decimal storage note in D-260.
- **Status:** current
- **Implemented in:** `backend/apps/bookings/migrations/0030_money_three_decimals.py`, `backend/apps/shop/checkout.py`

### D-260 — Payments audit rules
- **Area:** money
- **Date:** 10 November
- **Decision:** A configured Connect platform keeps settling, refunding and expiring existing charges regardless of the hosting switch; the gateway poll never cancels a native rail; an open "I paid" claim or maker-checker proposal blocks any online page (409 `payment_settlement_pending`); one rounding rule (tax engine `q`) applies to every charge; pending gifts are never debts; unknown refund outcomes keep the balance reserved and are polled; refunded tax receipts are annotated at render. Restricted or suspended accounts can see and pay their own outstanding charges, while revoked accounts stay refused.
- **Why:** Paying is how restrictions get cleared; the rest closes audit findings (3 High, 19 Medium).
- **Status:** partly superseded by D-268 (the 3-decimal currency deferral)

### D-259 — Payment claims, handover desk payments and report groups
- **Area:** money
- **Date:** 10 November
- **Decision:** Area payment claims are filterable by area with ordering and an "all statuses" view. The Handover desk gets an area Payments queue limited to loan charges its issue/return actions own (no record_payment grant). The full dashboard payload includes `payments_to_record` for record_payment holders, and the report catalogue is grouped People, Safety, Machines, Inventory, Donations.
- **Why:** Integration follow-ups; reason not otherwise recorded.
- **Status:** current

### D-256 — End-to-end payments audit before release
- **Area:** money
- **Date:** 10 November
- **Decision:** Every charge type per area, the online rail, offline settlement with ManualSettlement receipts and maker-checker, claims, pay links, refunds, reconciliation, receipts and currency handling are audited so there is no double charge or refund under concurrency, quote equals charge equals receipt, every money move is audited, and module on/off is respected.
- **Why:** Money paths must be correct before a release.
- **Status:** current
- **Implemented in:** `backend/apps/payments`, `backend/apps/payments_rail`

### D-252 — Donations: Fundraising role and non-profit schemes
- **Area:** money
- **Date:** 10 November
- **Decision:** Delegation of donations is a combinable fixed role, Fundraising, holding only the new action `manage_donations` (Space Manager holds it through manage_makerspace; it is not grantable through organizations). Fundraising also covers sponsors, the donations finance domain, donation refund cases and donation reports. Non-profit schemes are in_80g, in_12a, us_501c3, uk_charity, ca_charity, au_dgr and other; the signatory name is institutional, and donors are anonymous unless they opt in to public recognition.
- **Why:** Custom roles no longer exist in the fixed role catalogue, so a new fixed role is the delegation path.
- **Status:** current

### D-207 — Shop configuration completeness
- **Area:** money
- **Date:** 7 Nov 2026
- **Decision:** All existing Shop controls (catalogue, products, variants, images, SKU/stock, visibility, pricing, tax, member prices, holds, pickup, returns/refund approval, reminders, receipts, payment settings) must be reachable in Shop settings and manuals. The pickup-only and opt-in online-rail decisions, Shop Manager locks, audit and quantity owners are unchanged.
- **Why:** Reason not recorded
- **Status:** current

### D-200a — Final-gap choices (charges, paused spaces, audit search)
- **Area:** money
- **Date:** 6 Nov 2026
- **Decision:** A staff-opened membership term charges under a new subject `membership_term_start` (settled by `manage_members`, refunded or voided on cancel, nothing when membership is free). A free events shop runs with no prices; a dearer ticket-type change in a free domain switches at once while a cheaper one still refunds collected money. Desk "pay on phone" with the rail off answers 409 `online_payments_off`. A paused space's bootstrap 404 says `space_paused` (no reason, no name). Platform audit search lives in Platform settings with a `platform_only` filter. Modules whose rows belong to another owner are listed NOT_SEPARABLE and every first-party app is CORE or SEPARABLE (`CORE_APPS`).
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** backend/apps/separability

### D-197a — Money gaps: charges are recorded per domain, free copy is explicit
- **Area:** money
- **Date:** 5 Nov 2026
- **Decision:** Quotes and damage/lost charges on a domain that is not tracked answer 404 `charges_off`. `charges.machines` no longer requires modules, `charges.shop` is parented to `shop`, and `charges.donations` is parentless, default on and always on in setup (off refuses gifts, pledges and sponsor charges with 400 `charges_off`; skipped pledge periods are never back-charged). A shop with `charges.shop` off sells nothing, free orders keep their lines at unit price 0, promo codes are not spent but access codes are, and free joining activates at admission. The frontend fails open (shows money) while the bootstrap is unknown; stored prices are never cleared and free copy reads "X charges are off in this space, so X is free".
- **Why:** Every sale must be recorded in the ledger (earlier money rules), so a shop that cannot record cannot sell. Money history and admin views stay visible on purpose.
- **Status:** current
- **Implemented in:** backend/apps/payments, backend/apps/shop, docs/INVARIANTS.md

### D-197i — Hackathon money and superadmin control details
- **Area:** money
- **Date:** 5 November
- **Decision:** Paying a prize share clears routing details and keeps the tax ID masked; the finance reveal needs a stated reason and payment authority; the tax ID is asked for only when prize tax is on; deposits are per registration and never on crew. Space suspension is a lifecycle state; read-only blocks every user's writes while delivery, expiry, retention, settlement, cleanup and exports keep running; ownership transfer to an outsider invites first; announcements go to staff by default with a members toggle; the paused reason is shown only to the superadmin. Plans need the switch and managed mode (override over plan over deployment default), hosting invoices are numbered `SWH-<year>-<5 digits>` and outlive a purge.
- **Why:** Small design calls recorded under the standing rule to take the recommended option.
- **Status:** partly superseded by D-234 and D-236 (hosting-plan wording)

### D-184 — Money-mode scenario matrix
- **Area:** money
- **Date:** 5 November
- **Decision:** Every chargeable domain (lending, machines, bookings, events, membership, shop, donations, hackathon prizes; ID cards are always free) must work in three modes: completely free (nothing priced, no money UI), paid offline only (pending charge settled by staff with a receipt), and paid online through the optional rail. Mixed spaces are supported and one domain's mode never leaks into another.
- **Why:** Paid and free usage must both be complete, not an afterthought.
- **Status:** current

### D-171 — Machine service job refunds and vendor data
- **Area:** money
- **Date:** 2 November
- **Decision:** Vendor contact details are treated as space business data (not encrypted PII). Cancelling a prepaid job before it starts, or a prepaid job costing less than its quote, opens a refund case pending staff approval. Staff-run service jobs only refuse when someone else holds the booking.
- **Why:** Follows the rule that refunds are offered and a manager approves.
- **Status:** current
- **Implemented in:** `backend/apps/machines/job_refunds.py`

### D-163 — Price-drop refunds and per-space analytics
- **Area:** money
- **Date:** 1 November
- **Decision:** When a price is lowered, staff see affected paid, not-yet-used items (upcoming bookings, event tickets, machine job quotes, membership fees for terms not started) and the difference; each refund is a staff-approved refund case and nothing is refunded automatically. A price rise never charges anyone more. It sits behind `charges.price_drop_refunds`, off by default. A new `analytics` module (off by default) gives each space its own read-only Postgres login with row-level security over curated, versioned views with no secrets, evidence keys or unmasked PII, embedded in the staff console through signed embedding. Viewers need the new `view_analytics` action; every credential create, rotate, revoke and view is audited.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/payments/models_refund_cases.py`, `backend/apps/analytics/`, `docs/analytics-views.md`

### D-159 — Booking quotes and discounts
- **Area:** money
- **Date:** 1 November
- **Decision:** A booking needing approval is charged at the price quoted when it was requested (snapshot and digest frozen on the request). Account-less walk-in self-checkout loans raise no loan fees. The all-members discount applies to active memberships in that space only. Failed-job charging follows D-142.
- **Why:** Reason not recorded
- **Status:** current

### D-155 — Finance defaults and two-person check scope
- **Area:** money
- **Date:** 31 October
- **Decision:** Defaults: `finance.ledger`, `billing.disputes` and `billing.capture_flags` are on; `billing.offline_claims`, `billing.pay_links`, `billing.tax` and `billing.maker_checker` are off. The two-person check covers charge settlements only; manual ledger receipts (donations, misc) are entered by one person and can be voided with a reason. Ledger receipt uploads accept PDFs as well as images.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/payments/`

### D-100 — Finance visibility per domain
- **Area:** money
- **Date:** 24 October
- **Decision:** Inventory, Booking and Machine managers see money in and out for their own area only (machine managers limited to their machine types), through ledger rows, reports and exports. Space Managers and VIEW_FINANCE holders see everything, scoping goes through rbac, and a manager never sees other areas' rows.
- **Why:** Reason not recorded.
- **Status:** current

### D-94 — All money is in the finance ledger
- **Area:** money
- **Date:** 24 October
- **Decision:** Every money movement is recorded in the space's ledger and reports: fees, machine charges, bookings, events and memberships in; purchases, technician payouts, reimbursement payouts and refunds out. Marking a To-Buy item bought records amount, supplier, method and a receipt as an expense and raises stock. Inventory, machine and booking managers record spending in their own domain, with no extra approval threshold, and reports show income against spending by month.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/procurement`, `backend/apps/payments`

### D-85 — Pricing rules
- **Area:** money
- **Date:** 23 October
- **Decision:** Per-day rental timing is a setting (charge at checkout for planned days with a cap, or at return for actual days), and staff can waive a fee with an audited reason. One best automatic discount applies, then an event promo code, and nothing else stacks. Damage and lost fees need the return photo, late fees stay per loan, rounding is half-up to 2 decimals per line, kiosk and direct handouts are charged like reviewed loans, failed machine jobs are free by default, and a price of 0 on an item means "inherit the default".
- **Why:** Reason not recorded.
- **Status:** current

### D-84 — Paid and free everywhere
- **Area:** money
- **Date:** 23 October
- **Decision:** Every chargeable module supports free and paid with one pattern: the Space Manager sets the module default and rates per makerspace, each item, machine, room, event or plan can override it, and members or tiers get discounts. This covers lending (per-loan or per-day rental with cap, refundable deposit, late/damage/lost fees), machines, bookings, events, memberships and classes. Payment is online when payments is on or staff-recorded cash/UPI with a receipt, and money owed is always tracked.
- **Why:** Reason not recorded.
- **Status:** current

### D-68 — Membership refunds
- **Area:** money
- **Date:** 21 October
- **Decision:** Every membership type or plan gets a refund policy: full refund within N days of term start, then pro-rata of unused time or a percentage, then none, with an optional fee. Pro-rata is measured on the term the payment bought, lifetime plans are full within N days then none, and cancelling a paid membership opens a refund due for staff approval. Policy areas are events, bookings and memberships.
- **Why:** Reason not recorded.
- **Status:** current

### D-59 — Refund policies and refunds due
- **Area:** money
- **Date:** 21 October
- **Decision:** Cancelling a paid event registration, booking or membership computes a "refund due" from per-space, per-area policy (full refund up to N before, then a percentage, then none, optional fee) that waits for staff approval. Online payments refund through the provider (Connect refunds return the application fee), offline ones record a receipt, members can request refunds, and money never moves automatically. Space-cancelled events and staff-cancelled bookings owe the full amount, and the refund sweep starts from deploy with no back-fill.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/payments/models_refund.py`, `backend/apps/payments/models_refund_cases.py`, `backend/apps/payments/refund_cancellation.py`

### D-34 — Travel and expense reimbursement is in scope
- **Area:** money
- **Date:** 18 October
- **Decision:** Reimbursement (earlier deferred) covers hackathons and ordinary events: request at application or after acceptance, award with caps/tiers/budget pool, post-event claim with receipts and attendance check, finance review (approve, partial, reject with reason), and payout recording (method, reference, date) with no automated transfers. Payee details are encrypted and visible to finance roles only.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/event_reimbursements`
