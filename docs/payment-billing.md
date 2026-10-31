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
reference, an optional receipt photo (staging-key presign, promoted once) and the source that
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
