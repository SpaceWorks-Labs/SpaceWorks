# Reimbursement operations

Implementation status: **not operational**. RB-R currently provides model definitions
and independently tested policy calculations. Do not enable routes or install the
new app in production until G1/F/P integration, migrations, guards, workflows,
retention workers and acceptance tests are complete.

Finance first initializes an event programme and its currency pool in one
reauthenticated command. Replaying initialization must not fund again. Later policy
or funding changes use current programme and pool versions. No implicit PATCH upsert
is permitted. Lowering a pool cannot consume existing reservations or commitments.

FX rates are entered manually with source and date. A rate means target major units
per source major unit. Convert each line using the supported source/target exponents
and HALF_UP rounding once, then sum integer target units. Do not sum mixed currencies
or infer currency support from the legacy two-decimal fallback. Currency normalization
and exponent lookup belong to G's shared `payments/currencies.py` helper.

Receipt bytes are finance-only. The approved default is 2555 days after terminal
financial closure, with a snapshotted policy revision and duration. Payee payloads
and routing documents have a 30-day terminal policy. Unpaid obligations and holds
defer deletion. Annual review does not create an expiry anchor. Retention must
remain active without Events or reimbursement runtime.

Storage cleanup must retain both staging/final locators, enumerate all object
versions and delete markers, retry failures and release quota only after confirmed
deletion. No expired read may fall back to object storage. The pure retention helper
does not implement storage deletion, leases or retries; those workers are unfinished.

Archive preserves money records and pauses reimbursement finance access and actions.
Actual unarchive restores normal checks; no recovery authentication exception exists.
Module purge must refuse unfinished awards/claims and missing core decision evidence
or closure records. An allowed domain purge detaches retained obligations atomically.
Whole-tenant purge remains the existing explicitly destructive full-graph operation.

An unpaid obligation may be explicitly cancelled by finance with recent proof,
versions, reason and encrypted note. Attached domain budget adjustments acquire pool
before obligation. Detached cancellation uses only core data. Effective paid greater
than zero refuses cancellation. Durable operation digest/revision evidence must
support replay after command-receipt expiry and later domain purge.

The masked payout checklist is a preparation/reconciliation aid. Use the same closed
columns and masking for preview and CSV, neutralize spreadsheet formulas, recheck
versions/holds at download and never include names, full accounts, contact emails,
receipt filenames or free-text reasons. Every actual payment is made outside the
application and recorded afterward by an authorized human.

Before acceptance, run the complete request/award/claim/payee/partial-payout/amendment
journey on both event types; test privacy, mandatory encryption, both purge paths,
archive/unarchive, correction races and retention recovery. Capture themed browser
evidence and real reminder dispatch for AO19/AO20. The local pure-policy tests do not
replace these database, integration and browser checks.
