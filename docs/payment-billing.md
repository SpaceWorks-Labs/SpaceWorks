# Core billing: due dates, reminders and manual refunds

These surfaces remain available without the `payments` online module or credentials.
No new module key is introduced. Charge tracking still controls whether a debt is raised;
switching it off does not erase, settle or refund existing money.

New charges snapshot `due_at`. The default is the raise instant, or the makerspace's
`payment_terms_days` local calendar days later. Booking/event seams pass their start;
dues pass an existing active term's start, and renewal charges pass the current term's
end (the next term's start). Historic charges
keep a null due date. Due dates are immutable, including SQL updates. `due_state` is
derived only for pending charges: `upcoming`, `due_today` or `overdue`, using the owning
makerspace's local day. The server also returns `due_date`, so the browser never shifts
the date into its own timezone. Staff and member lists sort dated rows before nulls.

Managers configure `GET/PATCH admin/makerspace/<id>/billing-settings` (core, audited).
Defaults follow the research policy: due on raise, 3 days before, on the due day,
7 days after, and a cap of 2 steps. Increase the cap to 3 to include the default
overdue step, or configure a longer ladder. `billing.reminders` defaults OFF. Delivery additionally
requires `notifications`, `email` and the PAYMENTS/email matrix cell ON. Reminder
offsets are distinct positive local-calendar-day counts; the cap retains the earliest
configured steps, including the due-day step when it fits. Zero disables all steps.

The F1 sweeper owns claims and idempotency in `ReminderSchedule`; a duplicate payment
reminder log would introduce a second source of truth. The explicit `payments.due`
consumer revalidates pending status, tenant, due date and policy before dispatch.
Completed/uncertain claims are never retried. After downtime, only the latest eligible
step dispatches; earlier steps become skipped claims.
Advance and due-day notices expire after their scheduled local day, so downtime never
sends a stale "due today" message. Reminders send only to the charge
owner's current account address, respecting membership revocation and notification
opt-out. They never send staff email, chat, webhook or push and never alter debt.

PAYMENTS events already run on charge raised, money received and refund issued. They
now belong to the core ledger rather than the removable rail. Only the payer's receipt
email defaults ON; an explicit PAYMENTS/email OFF suppresses it. Other matrix defaults
remain OFF. Financial amounts stay out of staff chat.

`refund-offline` records money actually returned on any `paid_offline` charge kind and
requires `record_payment`. It is immediately succeeded and requires method, returned
date and an optional financial reference. Pending and succeeded refunds share the
original collected amount as their upper bound. `release-deposit` adds a closed-loan
check (`returned` or `closed_with_issue`). The return workflow itself never invents a
cash transfer: staff record the money handed back through the dialog after closing it.
Rail refunds remain on their existing provider-only route.

`payments/<payment>/refunds/<refund>/amend` appends corrected method/reference/date
metadata. The amount and currency are fixed. A receipt can be amended once; a later
correction amends its replacement. PostgreSQL guards cover raw/bulk bypasses as well as
model methods. No correction emits another refund event. Reconciliation and the
`payment-cash-book` report count only effective chain heads. The cash book groups by
method/currency and filters on actual receipt/refund dates, without mixing currencies
or inferring online settlement dates.

## Refund cases and policies

A `RefundCase` records what a member MAY be owed on a settled charge; it never moves
money. Only a staff approval creates a `Refund`, under the Payment then case row locks.

- **Due cases** open when a paid charge's subject is cancelled and the policy owes more
  than zero: a space-cancelled event owes the full balance (`event_cancelled`); a
  member cancelled registration or booking follows that area's `RefundPolicy` (a booking
  staff cancel on a member's behalf is owed in full, `staff_cancelled`, decision 72)
  (full window, partial window and percent, fee in the space currency, rounded down to
  min(currency exponent, 2) places, minus anything already refunded). Bookings open the
  case in the cancellation's own transaction; the events path is post-commit and a
  missed case is rebuilt by the hourly `rebuild-refund-cases` sweep (beat and beat-less),
  which looks back 7 days but never before the deploy watermark (the apply time of the
  `payments.0023_refund_cases` migration), so deploying back-fills nothing.
- **Memberships** (owner decision 68): cancelling a paid membership term opens a due under
  the membership policy -- a space default plus optional per-plan rules: a full refund
  within N days of the term start, then pro rata of the unused term time or a percentage
  (the policy chooses), then nothing after the term ends, minus an optional fee. Dues and
  admission charges have no term, so they stay request-only. "Do not renew" only voids a
  pending renewal. Per-plan rules: `refund-policies/membership/plans/<plan>`.
  Release 2 (L4): financial-year and fixed-end terms are pro-rated to their own end; a
  lifetime term is refunded in full within `full_within_days`, then nothing; a paid but
  unopened next term is owed in full. The member sees the policy's suggested amount
  before asking (`member/makerspaces/<id>/payments/<pid>/refund-suggestion`, X20) and
  staff see it on the case (`.../refund-cases/<case>/membership-suggestion`). Approving a
  membership case ends the term the payment bought once the approval commits -- an
  early-paid upcoming term is cancelled -- unless staff send `keep_membership: true`
  (X21); ending it opens no second case. Joining fees and dues stay `Payment` income in
  the `membership` domain for the finance ledger.
- **Requests**: a member may ask on any own settled charge except a loan deposit. One
  active (open or approval-failed) case per payment; asking on an open due case adds the
  member's reason to it. Only an open request can be withdrawn.
- **Decisions**: approve/decline need the charge's subject authority (VIEW_FINANCE is
  read-only). Online approval raises a provider refund after commit; a refusal moves the
  case to `approval_failed` for retry or decline. Offline approval needs RECORD_PAYMENT and
  a receipt, recorded as a manual refund. With the rail removed an online case returns
  409 `refund_rail_unavailable` and can only be declined.
- A refund raised outside a case voids every active case once nothing is left to refund.
- Stripe Connect refunds send `refund_application_fee=true` when the charge carried a
  platform fee (direct charges: no transfer to reverse). Razorpay is unchanged.
- The `refunds` report (VIEW_FINANCE) groups cases and case-less refunds (`manual`) by
  local month, area, reason and currency.
- Notifications: `refund_due_opened` and `refund_request_received` reach staff;
  `refund_request_approved` and `refund_request_declined` reach the payer.
- Open and approved cases join the money fingerprint; an undecided case blocks account
  deletion (`refund_under_review`); purges delete cases before refunds.

Portable dumps preserve due dates and refund correction chains, remapping identities.
They reset automatic-mail policy and drop F1 claims; the target must opt in afresh.
The money fingerprint includes due dates and every refund amendment. The coordinator
must recompute the merged catalog digest and regenerate the OpenAPI snapshot/client.

Native online payments use the charge's resolved vendor: Stripe returns PaymentSheet
parameters; Razorpay returns native Checkout Order parameters. Both include `vendor`
and `payment_id`. Hosted links and native payments cannot be mixed on one charge.
Razorpay Orders are recovered by exact receipt and charge details before creating;
waiving or recording an offline payment closes the Order locally because Razorpay
has no Order cancellation API. A late capture after waiver settles online and retains
its refund anchor. A different capture on an already settled charge raises one
`payment.double_paid_refund_required` audit per provider payment ID, including the
captured amount in minor units and currency. Staff refund that excess in the provider
dashboard; the original charge and its refund balance remain unchanged.

## Tax and GST

`billing.tax` (off by default, a Space Manager-only finance setting, never delegable) turns on the
tax engine. `GET/PUT admin/makerspace/<id>/billing/tax` holds the policy: mode `none`, `single`
(a named tax such as VAT at a rate in basis points) or `gst_india` (supplier GSTIN with format,
state-prefix and check-character validation, state, regular or composition scheme, exempt supplies,
SAC code `999599` by default, and for foreign-currency charges either "outside GST" or export under
LUT with the LUT number). Prices are inclusive (default) or exclusive; an exclusive policy adds the
tax on top of the price a domain computed. `POST .../billing/tax/validate-gstin` checks a GSTIN
offline and `POST .../billing/tax/preview` renders a sample invoice for unsaved settings. Writes
answer 409 `tax_not_enabled` while the switch is off and 400 `gstin_invalid` for a bad GSTIN.

The policy is **frozen per charge**: `create_payment` stores `Payment.tax_snapshot` (rate, mode,
supply type, place of supply from the payer's state or GSTIN, falling back to the supplier state,
and the exact taxable/component split). Editing the policy never changes an existing charge or
document; the database refuses any change to a snapshot. CGST/SGST (UTGST in union territories)
versus IGST follows the place of supply, and every split is exact at the ledger's two decimals by
largest remainder (a yen has no subunit; a fils is capped to two places). Composition and exempt
supplies issue a **bill of supply**; LUT exports a zero-rated tax invoice.

Documents issued while tax is on take a gapless **per-financial-year** series: `INV26-27/0001` for
receipts/tax invoices and a separate `CN…` credit-note series, prefixes of at most four
characters and numbers of at most 16 (CGST Rule 46). The financial year comes from the space's FY
start (April by default; L4's `financial_year` when present). Existing documents are never
renumbered, and with tax off every document and number is byte-identical to release 1. The frozen
`tax_breakdown` drives the PDF (title, identities, tax table, notes) and the returns. Credit notes
apportion the invoice's remaining taxable value and tax, so partial refunds never over-credit.

Reports (all `view_finance` + `billing.tax`): `gstr1` (B2B, B2CL, B2CS, EXP, CDNR, nil/exempt,
Table 12 SAC and Table 13 documents), `gstr3b` (3.1a/b/c/e and 3.2 by place of supply),
`tax-summary` (single-tax mode) and `documents-register` (every document plus a `gap` row for any
skipped number). `GET .../billing/tax/gstr1.json?month=YYYY-MM` downloads the GSTN offline-tool
JSON; it is a draft to review there, never filed automatically.

## Offline collection, claims and the two-person check

With `billing.offline_claims`, an INR pending charge shows a UPI QR built server-side from the
billing settings' `upi_vpa`/`upi_payee_name` for the exact amount, with the note `SW-<id>`. The
payer may post "I've paid" (`POST member/makerspaces/<id>/payments/<pid>/paid-claim`: UTR and
date; one open claim per charge, one claim per reference per space, rate-limited). Staff with
`record_payment` confirm (`paid-claims/<cid>/confirm`) -- which writes the `ManualSettlement`
receipt in the same transaction that marks the charge paid -- or reject with a note. A claim moves
no money.

`billing.maker_checker` (off) applies to **offline income only** (#128 C-5): a cash/UPI/bank
settlement becomes a `SettlementConfirmation` awaiting a second person with `record_payment`
(`settlements`, `settlements/<sid>/confirm|reject`); the recorder can never confirm their own
(409 `self_confirmation`, also a database check). Refunds, expenses and payouts never wait.

## Online exceptions: capture flags, disputes, method labels, polling

`billing.capture_flags` (on): money that arrives for a cancelled charge, a second capture, or a
different amount/currency is **accepted and flagged** (`capture-flags`); a cancelled charge is
recorded as paid online under a narrow database exception. The receipt is held until staff decide
(`capture-flags/<id>/resolve`): issue it on the amount received, open a refund case (still
approved by staff), or acknowledge with a note. Nothing is refunded automatically.

Disputes from Stripe or Razorpay webhooks (through the rail) are always recorded with an
append-only status history and a staff notice; `billing.disputes` shows them. A dispute never
cancels a booking or ticket and never refunds. Receipts show the provider's masked method label
("Visa ••4242", a masked UPI handle), filled once, never card data.

The gateway poll (every 5 minutes, both schedulers) asks providers about open online attempts and
settles a capture exactly as its webhook would; an attempt unpaid after a week is closed while
the debt stays. Pending provider refunds are polled for status for 30 days and flagged after a
day. Polling never creates, approves or cancels a refund.

## Pay links

`billing.pay_links` (off): staff with `record_payment` create a link for a pending charge that has
no account and was raised by staff (`payments/<pid>/pay-link`, optional one-time email). The link
holds a 256-bit token (only its digest is stored), expires (14 days default, 60 at most), and a new
link revokes the old one. `public/pay/<token>` shows the space, the charge label and the amount --
never who owes it -- and offers online checkout (rail) or an offline claim. Event registration
still requires an account.

## Finance ledger

Every money movement is in the space's finance ledger (#94): member charges (`Payment`), refunds,
event reimbursement/prize payouts and `LedgerEntry` rows for everything else -- expenses and
non-charge receipts such as donations or grants. Entries carry a domain (inventory, loans,
machines, bookings, events, membership, donations, shop, general), a machine type where it
applies, a category, method (cash lands in the cash account, everything else in bank), date,
reference, an optional receipt -- a photo or a PDF (#155), up to `EVIDENCE_MAX_BYTES` (10 MB),
through the staging-key presign with the MIME type bound and promoted once -- and the source that
caused them. They are voided with a reason, never edited or deleted.

Other lanes record spending through `payments.ledger_api.record_expense(makerspace, domain,
machine_type, amount, currency, method, reference, receipt, source_kind, source_id, actor, ...)`
and `ledger_api.void(entry, actor, reason)`; a repeat call for the same live source returns the
same row. Spending is always recorded; `finance.ledger` only hides the screens and reports.

Visibility follows each area (#100): Space Managers and `view_finance` see everything; the
Inventory Manager sees inventory and lending money, the Booking Manager bookings, the Machine
Manager their machine types, the Event Manager events money (#128 C-16). The same areas record
spending; finance staff with `view_finance` + `record_payment` record anywhere. Routes:
`finance/access`, `finance/summary`, `finance/entries` (+ `/<id>`, `/void`, `/receipt-url`),
`finance/receipt-upload`, `finance/opening-balances` and `finance/events/<event>` (+ `/budget`,
`?format=csv`). Reports: `income-spending`, `finance-inventory|machines|bookings|events`,
`event-finance`, `receipts-payments`, `subscription-income` and `money-methods` (provider and
method splits with the failed-online rate).

## Pricing: paid and free everywhere

Release 2, lane L15 (decisions #84 and #85, answers A1-A14). One pattern for every area: **rate
card -> item price -> loan waiver -> member discount -> frozen quote -> `Payment`**. There is no
second ledger: pricing decides the amount, the existing `create_payment` records the debt, and
L5's tax is frozen on top of the net amount (A6).

**One resolver.** `apps.payments.pricing.quote(makerspace, domain, target, member, params)`
prices every chargeable seam and every preview, so the price a member is shown is the price they
are charged (A8). Areas and components (`payments/pricing/components.py`):

| Area | Components | Notes |
|---|---|---|
| Lending | rental per loan, rental per day (cap per unit of each item line), refundable deposit, late fee per day (cap, grace), damage, lost | Deposit and late fee keep their release-1 columns on the payment settings; damage and lost are staff-set with a suggestion |
| Machines | time per hour (billing increment, minimum), material per unit, per job | Time AND material together; the machine type's price row is the middle level |
| Bookings | per booking (the room's own price), per hour (rounded up to the increment, capped per day) | |
| Events | per registration | The space default only prefills new events; a published event keeps its own price |
| Membership | dues, joining fee | Read-only here: plans own their prices (L4); a cheaper tier is a cheaper plan (A4) |

**Resolution per component**, most specific first: the item's own price field above 0 (a room's
price, an item's deposit); a per-item price (`PriceOverride`: Free or Custom, on a product,
machine, material pool or room); the machine type's price row (machines); the space rate card,
where a **Free** area resolves to 0. 0 or empty on an item means "inherit the default" (A13); set
the item to Free to keep it free under a paid default. Before a default is saved, the impact
preview lists every item whose price would move.

**Bookings awaiting approval keep the requested price** (#159): the quote is frozen on the
booking (`Booking.pricing_snapshot`, insert-only) when it is requested, and approval raises the
`Payment` from that snapshot, never re-quoting. Staff see the frozen price beside Approve. A
request from before this rule has no snapshot and is charged the approval-day price, audited as
`booking.price_quoted_at_approval`. Instant confirmations are quoted and charged at once.

**Machine sessions keep the price shown at Start** (L23, #158): a metered session freezes the
machine's hourly `time` rate (with its billing increment, minimum and the member's best discount)
when it starts; at stop the charge is rebuilt from that snapshot for the session's minutes and
raised PENDING as a `machine_session` charge. An auto-stopped session is held until staff check
and confirm it (a duration correction first is an audited amendment). Sessions that run an L12 job
are billed through the job only.

**Rounding** is half-up to two decimals per line, the total is the sum of the lines, and a cap
applies before any discount (A7).

**Discounts** (`charges.discounts`, off by default): the single best automatic rule -- all
members, the members on a plan (their active plan; display titles are never tiers), or one member
-- then an event promo code on top. Nothing else stacks and no line goes below 0 (A3). Deposits,
late, damage and lost fees are never discounted unless a rule names them. Rules are archived,
never deleted. Space Manager only (a finance setting).

**A total of 0 raises no `Payment`.** A priced charge that came to 0 (waived, discounted, a free
failed job) is audited as `charge.free_by_pricing`.

**Loans.** Rental timing is a per-space setting (A1): **at checkout** charges the planned days at
issue, **at return** charges the actual days at close; the choice made when a loan is issued sticks
to that loan. The late fee is per loan at the highest late rate among its items (A2) and applies
on top. An early return refunds nothing automatically and renewals are not charged. Direct,
kiosk and self-checkout handouts are charged like reviewed loans; a deposit never blocks them
(A10). Damage and lost charges are entered by staff (handover roles included) at return or later,
one per damage/lost row, and an amount above 0 needs the return photo that recorded the item (A5).

**Waivers** (`loans.fee_waivers`): staff with `return_request` waive a loan's rental, late, damage
or lost fees with a required reason (A14). Pending charges become `waived`; a charge already paid
is never reversed -- it opens a refund case (`fee_waived`) that a staff member approves. The
deposit is never waived. A waiver is append-only and undone only by a revocation row, which
affects charges not yet raised.

**Who edits what** (#101, A9): each area's rate card is that module's setting (the Space Manager,
or the module manager holding its settings grant); rental timing is also the Inventory Manager's
without a grant (#128 C-11d) unless the Space Manager locked it; per-item prices belong to whoever
edits the item; discounts and the currency are the Space Manager's.

**Machines: failed jobs.** Free by default (A11). `machines.service_payments.create_for_failed_request`
charges a failed job as none, material only or full; lane L12 calls it with the per-type, per-fault
choice of #142 OQ-8.

Routes (staff): `admin/makerspace/<id>/pricing/<domain>` (+ `/impact`), `pricing/loans/rental-timing`,
`pricing/currency`, `pricing/overrides/<target_type>/<target_id>`, `pricing/discounts` (+ `/<id>`,
`/<id>/archive`), `requests/<rid>/charges`, `requests/<rid>/fee-waivers` (+ `/<wid>/revoke`),
`requests/<rid>/accountability/<aid>/charge` (amount 0 records "no charge" as
`loan.accountability_not_charged`). Public: `public/<slug>/pricing/quote` (anonymous allowed,
`THROTTLE_PRICING_QUOTE`; rooms and events by id or public token), which never returns hidden
counts, storage, box, QR or requester data. The public booking and event registration submits
take an optional `quote_digest`: a moved price is refused with 409 `price_changed` and the new
quote before anything is written.

## Donations and sponsors

Four switches on the core ledger, each off by default (#128 C-14): `finance.donations`,
`finance.recurring_donations`, `finance.tax_exempt_receipts`, `finance.sponsors`; the online rail
for gifts and sponsor money is `payments.donations` (needs the `payments` module and credentials).

- **Giving.** `public/<slug>/donations` is the page (intro, suggested amounts, minimum, open
  campaigns and funds with their goal and the amount raised). Anyone gives: a signed-in person as
  themselves, a guest with name, email and the code from `donations/email-code` (the #80 contact
  code). Each gift is a `Donation` and ONE `Payment` (subject `donation`, no tax frozen on a gift),
  raised through `create_payment`; with the rail on the response carries the hosted checkout URL,
  otherwise the space's offline instructions. A guest gets a signed status link
  (`public/donation-links/<token>`: status, pay, an "I've paid" claim into the L5 claim queue when
  `billing.offline_claims` is on, the 80G PDF) and never sees anyone else's gift. Refusals are one typed
  400 `{detail, code, field}`.
- **Desk gifts.** Staff with `view_finance` + `record_payment` record a gift received in person
  (`admin/makerspace/<id>/donations`, POST with the settlement): the charge and its
  `ManualSettlement` receipt in one go, maker-checker honoured.
- **Pledges.** `public/<slug>/donations/pledges` (or the member area) promises an amount every
  month, quarter or year. The hourly `donation-pledges` job raises one gift and charge per period
  (unique per pledge and period) and reminds the giver; a missed or paused period is skipped, never
  back-charged. No card is stored: the giver pays each charge like any other.
- **Receipts.** A received gift gets the ordinary L5 receipt document. With
  `finance.tax_exempt_receipts` on and the space's registration number and validity set
  (`donations/settings`, Space Manager only), a gift whose giver asked for one freezes an 80G
  receipt (registration, validity, number, amount, date) when it is received; the PDF prints the
  giver's name, address and PAN from their encrypted columns (`DonorTaxDetail`, shared by a pledge's gifts). The PAN is asked only for an 80G
  receipt, validated, always encrypted, shown elsewhere as its last four characters, masked for a
  superadmin without a PII window, and never part of a report.
- **Money.** Gifts and sponsor money are the ledger's `donations` area, visible to the Space Manager
  and finance staff. Giving one back is a refund case in area `donations` that staff open
  (`donations/<id>/return`, `sponsors/charges/<id>/return`) and decide in the refund-case queue; the
  direct staff refund routes refuse these charges (`refund_via_case_only`).
- **Sponsors.** `admin/makerspace/<id>/sponsors` (+ tiers, perks, charges, event links, logo):
  a sponsor's public face (name, tier, logo through the public image pipeline, website, blurb,
  active window) and private contact (scoped PII). A tier's perks are copied to each of its
  sponsors as a checklist; ticking one records who and when; perks due within a week tell staff
  once (`sponsor-perk-reminders`). A sponsor's agreed payment is an account-less charge staff
  raise (`sponsorship`), settled offline or by an L5 pay link. The wall
  (`public/<slug>/sponsors`, the Pages `sponsors` section, `public/<slug>/events/<token>/sponsors`)
  shows public fields only; an event's sponsors link to `events.EventSponsor` rows (picked from
  `sponsors/event-sponsors`), never copies.

## Price-drop refunds

Lane L24 (#163A, #171). **Nothing is ever refunded automatically**: each refund below is a
`RefundCase` in the refund queue that a person approves.

**A price lowered after people paid** (`charges.price_drop_refunds`, off by default). When staff
save a LOWER price, every paid item that has not been used yet and would now cost less gets a
refund case (`price_drop`) for the difference:

- upcoming bookings of rooms and machine time (a room's price, its override, or the bookings rate
  card);
- tickets for events not yet held (a ticket type's price, or the event's own price). A SOLD
  fixed-price ticket may be lowered while the switch is on -- never raised; pay-what-you-want
  tickets and series passes are never re-priced;
- prepaid machine jobs whose quote was paid but which have not started (the machines rate card, a
  machine or material-pool price, or a machine type's price row);
- membership terms paid but not started yet, including a renewal paid early (a plan's price or
  renewal price; the joining fee is not re-priced).

The difference comes from the frozen quote, never today's list: the item is re-priced with the
inputs it was quoted with, the difference is rounded down and never exceeds what is left to refund
on the charge, and a second drop offers only the further difference. A RISE never charges anyone
more. Before saving, the price forms show the affected items and the total difference: every
price-saving endpoint accepts `?price_drop_preview=1`, which runs the save, lists the items and
rolls it back (404 while the switch is off).

**Prepaid machine jobs** (#171, always on wherever machine charging is on):

- a member cancels a prepaid job before it starts: a `job_cancelled` case for what is left on the
  charge (an unpaid prepay charge is voided instead);
- a prepaid job comes in cheaper than its quote -- at completion, or a member-fault failure under
  the space's failure charge: a `quote_difference` case for the difference.

**Who approves.** A price-difference case (`price_drop`, `quote_difference`) is approved or
declined by the Space Manager or a finance admin (`view_finance` plus `record_payment`); approving
it never ends a membership. A `job_cancelled` case is decided like any staff cancellation, by the
job's Machine Manager. Each save that opens cases writes one `pricing.price_drop_refunds_opened`
audit row; each case writes its own `payment.refund_case_opened`.

## Shop sales (release 2 L22)

A shop order is one `Payment` (subject `shop_order`, domain `shop`); its line prices come from
`pricing.quote(space, "shop", params={"lines": [(variant, quantity), ...]})` with the buyer's one best
member discount when `shop.member_prices` is on. Online, the charge is put on the rail only with
`payments.shop` and credentials; otherwise the order waits "pay at the desk", holding its stock for 48
hours (`shop.holds`). At the desk the sale and its offline receipt (cash, UPI, card on an external
terminal) are one transaction, and the L5 receipt or tax invoice is issued in the space's FY series; the
receipt screen prints at 80 mm and A4. Refunds are refund cases in area `shop`, decided by the Shop
Manager or finance staff; the direct refund routes refuse shop charges. Restock purchases are To-Buy
rows (inventory stream) whose "mark bought" records the expense and puts the units on the shop shelf.
Cash sessions (`shop.cash_up`) expect the float plus the session's cash sales minus shop cash refunds,
and with `billing.maker_checker` a second person confirms the close.
