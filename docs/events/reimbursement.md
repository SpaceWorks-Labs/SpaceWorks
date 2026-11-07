# Event reimbursements

Travel support is available through the optional `event_reimbursements` module.
Its member and staff routes cover requests, finite budgets, awards, claims and appeals;
core Payments owns permanent obligations, payee revisions and append-only payout
records. This guide describes the integrated contract, while final browser, storage,
finance-authority and recovery acceptance require their own exact-source evidence.

Travel support applies to ordinary events and hackathons. A participant explicitly
requests support at registration/application or after acceptance, according to the
event's programme policy. Requesting support never grants admission.

| Step | Responsible person | Financial effect |
| --- | --- | --- |
| Request | Applicant, for themselves | Estimates only; no money reserved |
| Offer | Authorized event reviewer or finance | Reserve the offered cap from the event pool |
| Accept | Applicant before the deadline | Freeze the accepted cap, currency and rule evidence |
| Claim | Applicant after the event | Submit itemized expenses and ready receipt metadata |
| Decide | Host finance | Commit approved amount and release unused reservation |
| Routing details | Applicant after positive approval | Encrypted details for this obligation only |
| Record payout | Finance with the dedicated recording action | Record a payment a human already made |

The optional `event_reimbursements` module owns support requests, awards, claims and
budgets. Staged forms belong to Events. Permanent obligations, payee revisions,
receipt metadata and payout entries belong to core Payments. The online payment
rail is not required for reimbursement recording.

All amounts are integer minor units. Each pool has one currency; available funds
equal total minus reserved minus committed. Partial approval releases the unused
award capacity. Paying an obligation does not release its committed budget.
Appeals may require a new funded hold; available funds must cover it first.

Applicants see their own status, decisions and payout history. Event reviewers
see screening data and receipt metadata. Only host finance can read receipt bytes
or reveal payee details. `RECORD_PAYMENT` does not grant reimbursement finance
authority. Recording or amending payouts additionally requires the new dedicated
action and recent server-owned reauthentication.

Recorded payouts are append-only. Correcting a reference, date or amount creates
an amendment that replaces that chain's effective tip. For example, 10000 corrected
to 9000 means 9000 paid. A separate partial payment of 1000 then reaches 10000.
The original recording always remains visible.

No automated transfer, provider payout, bank-ready CSV or card storage is part of
this feature. A masked checklist cannot mark a claim paid. See
[operations](reimbursement-operations.md) for retention, archive and correction rules.
