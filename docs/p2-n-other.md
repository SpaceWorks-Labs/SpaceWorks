# Phase 2 lane n-other handoff

Branch: `lane/p2-n-other`. Implementation and static checks only; **Django/Docker
tests have not run**. Nothing was staged, committed, merged or pushed. The index
is empty. Frozen contract files, profile contracts, frontend and integrator-owned
documentation were not edited.

**Phase 3 status (2026-10-17):** member broadcasts, source-intent legacy inbox dedup and catalog
strings are wired. Direct-mail compatibility is preserved by `direct_mail_unless_routed`; the
source-bound resolver default itself is still absent. Stocktake's procurement gate, revoked
application owners, non-equipment room retries and report sent-status limits remain. The lane
validation below is historical; no runtime pass is claimed by this documentation refresh.

## Implemented behavior

- Membership applications, activation/welcome, approval, verification, admission
  decisions/payment deadlines, renewal/lapse/grace/failure/cancellation, known
  invitations/referrals and vouches reserve explicit personal envelopes.
- Approval and its welcome reserve the same owner intent. Verification uses the
  immutable audit event as its revision, so a second verification call does not
  suppress the first notice. A later unverification invalidates it.
- Requested -> awaiting-vouches in one transaction keeps the pending notice.
- Renewal callbacks now reserve envelopes before domain commit. Payment, renewal
  and admission reminder dispatch commit their completion and envelopes together;
  the sweeper recognizes a queued outbox result as dispatched.
- Ledger charge/receipt/refund/failure/dunning and payment-document notices use
  live ledger sources. Account-only owners need no membership; the online rail
  is not a prerequisite. Settled debts suppress delayed pending-debt notices.
  Refunds and reminder steps have distinct durable revisions.
- API-access and subdomain outcomes have separate private owner content and staff
  summaries. Admin mutations now encompass their audit/outbox writes in a
  transaction; API requests are locked against repeated concurrent resolution.
- Device notices refer to immutable outage/recovery events. The encrypted,
  templated edge snapshot cannot be rewritten by subsequent recovery.
- Stocktake schedule/completion and first-email-failure adapters are wired.
  Failure alerts contain only the log ID, are deduplicated per first failure and
  cannot recursively generate alerts for their own failed transport.
- Scheduled report role/action recipients receive source-backed navigation
  notices. The source rechecks creator authority, current selection, report
  availability and expiry. Raw recipient email addresses never establish chat
  identities. Existing external email remains; room content no longer contains
  storage download grants. Staff links name the source makerspace.
- The member-broadcast adapter includes live sender/segment checks; Phase 3 wires its existing
  producer in `notifications/broadcasts.py` inside the audited transaction.
- Personal deliveries use the frozen outbox. Separate staff-room summaries retain
  the existing destination/scoping/quota/template dispatcher, with transactional
  room logs and stable intent metadata. Native push is not also sent as a room.
- Snapshot failures roll back a savepoint, log identifiers/error type only and
  cannot poison the domain transaction.

## Routes / APIs added

None. No methods, paths, request fields, response fields or OpenAPI schema changes.
Existing Python notification entry points remain importable; their `sync` keyword
is retained for caller compatibility, but converted delivery is transactional and
asynchronous. Delivery telemetry belongs to the personal delivery records.

## Models / migrations / registries

No new models, model fields or migrations. No changes to the portable catalog pin,
PII/export/import registries, route guards, task catalogs or module keys are needed
for these adapters: all persisted content uses existing encrypted envelopes and
existing room/email logs.

Query-free, idempotent `AppConfig.ready()` registrations add these sources:

| Source | Owning adapter |
|---|---|
| `membership.lifecycle`, `membership.application` | makerspaces/notifications_p2_members.py |
| `membership.term` | makerspaces/notifications_p2_terms.py |
| `membership.vouch` | makerspaces/notifications_p2_vouches.py |
| `membership.broadcast` | makerspaces/notifications_p2_broadcasts.py |
| `makerspaces.subdomain` | makerspaces/notifications_p2_subdomains.py |
| `payments.ledger`, `payments.document` | payments/notifications_p2.py |
| `apiclients.request` | apiclients/notifications_p2.py |
| `devices.state_edge` | devices/notifications_p2.py |
| `operations.stocktake`, `operations.email_failure` | operations/notifications_p2_alerts.py |
| `operations.report_ready` | operations/notifications_p2_reports.py |

The operations app also registers `p2.email_first_failure`, an EmailLog post-save
signal. It ignores raw fixture loads and its own alert's transport.

## Integrator requests

1. **Member broadcasts — DONE in Phase 3.** `backend/apps/notifications/broadcasts.py`, in
   `send_broadcast`, uses the following inside its existing atomic transaction:

   ```python
   from apps.makerspaces.notifications_p2_broadcasts import notify_broadcast
   for user_id in ids:
       notify_broadcast(broadcast, user_id=user_id, segment=segment)
   ```

   Keep its existing authorization, bounded audience, persisted broadcast and
   audit. The adapter stores safe segment selectors on each envelope, so no
   MemberBroadcast model migration is required.

2. **Personal legacy mirrors — DONE in Phase 3.** The legacy shared feed is intentionally
   retained. `emit_notification` now carries source intent from the stocktake producers and
   `integrations/dispatch_delivery.py` first-failure producer. `notifications/legacy_inbox.py`
   uses `get_or_create` and the same per-user event UUID as `notification_builtin`:
   `uuid5(NAMESPACE_URL, envelope.dedup_key)`.
   The adapter's key is `p2:{identity(space_id, source_kind, source_id, revision,
   event)}:u:{user_id}`. Preserve the shared Notification row and independent
   failure in-app visibility. Merely removing all legacy mirrors loses that
   visibility for staff selecting only chat/email.

3. **Loan financial dedup, lane n-hw.** For the owner's deposit/late-fee notice,
   use `payments.notifications_p2.notify_payment(payment, "charge_raised")`.
   Do not emit a second owner intent under the hardware event name. This function
   uses `payments.ledger`, the Payment PK and `financial_revision`, so repeat calls
   from both domain and payment seams reserve the same intent. Domain staff-only
   summaries can retain their separate event names.

4. **Catalog entries — DONE in Phase 3.** These strings are in `integrations/notification_catalog.py`
   `FEATURE_EVENTS`: members = `joined`, `verified`, `invitation`, `vouched`;
   payments = `document_issued`; api_access = `subdomain_request_resolved`,
   `email.failed`, `scheduled_report`; stock = `scheduled`, `completed`.
   Current adapters use existing category keys, so there is no new enum/module key.
   Subdomain/report/failure selections currently share `api_access`, the existing
   administrative category. Their source predicates still enforce actual authority.

5. **Tests.** Run the lane directory and existing notification/email/timing suites
   on the Django host. Tests are intentionally gitignored and must be included in
   the integration artifact explicitly. Existing implementation-coupled tests in
   `makerspaces/test_membership_notifications_j3.py`,
   `test_api_key_resolution_notifications_w0.py`,
   `devices/test_device_notifications.py` and notification-family tests mock
   removed `notify_lifecycle`/direct-mail internals or assert synchronous transport
   counts. Those assertions need conversion to envelope/source/fake-provider
   behavior; they are known compatibility work, not a claimed green baseline.

6. Update integrator-owned SOURCE-MAP/INVARIANTS/PROJECT-HISTORY as appropriate.
   No module-key or route change requires MODULES/OpenAPI edits.

## Contract change requests

1. **Preserve existing direct-mail defaults (mitigated by the compatibility leg below).** Frozen
   `notification_resolution.target_eligible` currently grants an email default
   only to `payments/payment_received`. Add an equivalent, source-bound default
   for `(membership.lifecycle, joined|approved|verified)`,
   `(membership.application, invitation)` and
   `(payments.document, document_issued)`. Apply existing verified-address,
   suppression, module and personal-selection gates; these are not new mandatory
   mail exemptions. Envelope email alone still omits these formerly direct notices when
   the members/payments matrix defaults OFF. The compatibility leg described below preserves
   that mail; migrating its defaults into the shared resolver remains pending.

2. **Stocktake's domain gate.** Frozen `notification_resolution.eligible` calls
   `feature_available(space, "stock")`, which requires procurement. For
   `operations.stocktake`, require `stocktake` instead, or add a registered
   source-module override consulted by both resolution and channel availability.
   The source already checks stocktake and EDIT_INVENTORY. Do not globally remap
   stock: procurement notices in the hardware lane still need their real module.

3. **Application owners returning after revocation.** The shared owner predicate
   rejects every revoked membership, including an explicit owner of a fresh live
   application. Existing admission mail had an applicant-owner exception. Add a
   narrow exception for `membership.application` after validating its source,
   explicit account, active account standing and live request. Do not weaken the
   revoked-owner refusal for payment or arbitrary personal notices.

4. **Room retry authority.** The personal seam cannot address rooms. Existing
   `dispatch_channels_delivery._deliver_notification` does not consume the
   source metadata written by these adapters. Add a room-source validation/render
   registry and consult it on send/retry/release for payloads containing
   `p2_intent`, `source_kind`, `source_id`, `revision`. Keep scoped destinations
   and never use an owner body. Current room handling preserves legacy behavior;
   it does not claim the personal worker's live source/authority guarantees.

5. **Scheduled-report status.** ReportDelivery only has `sent|failed`, whereas
   selected personal legs now enqueue asynchronously. Add a queued/accepted report
   status or an envelope completion hook before treating its legacy `sent` label
   as transport proof. The personal NotificationDelivery states already report
   acceptance/sent/delivery accurately. No migration or contract alteration was
   made in this lane to invent such a status.

## Preserved / deferred by ownership

Password reset, verification OTP and MFA authentication proofs are unchanged,
email-only and redacted. Platform archive-request mail remains ungated. All five
mandatory-mail module exemptions and the separate closed-with-issue exception are
untouched. Existing backup custody producers are outside this lane and were not
converted. Account-less staff invitations retain email/private-share delivery;
no account link or chat identity is inferred from their email ciphertext.

No provider implementation, callback, webhook or profile activity source was added.

## Validation

- Static AST parse and unresolved-global-name checks passed for all 49 changed/new
  Python files, including the eight ignored lane test files.
- Every imported local `apps.*` module exists. Touched production files remain
  below 300 lines (largest: report_schedule_services.py).
- `git diff --check` passed; staged diff is empty; branch is `lane/p2-n-other`.
- Seven test modules cover individual lifecycle rows, account-only delivery with
  email/rail/membership off, selected multiple media, source authority withdrawal,
  tenant mismatch, dedup, rollback, actual savepoint recovery, device snapshots,
  report disclosure, recursive failure suppression and unchanged security mail.
- No runtime tests or real network calls were performed by this lane.

## Files changed

All paths below are relative to the worktree.

```text
backend/apps/apiclients/admin_requests.py
backend/apps/apiclients/apps.py
backend/apps/apiclients/notifications.py
backend/apps/apiclients/notifications_p2.py
backend/apps/devices/apps.py
backend/apps/devices/notifications.py
backend/apps/devices/notifications_p2.py
backend/apps/makerspaces/admin_subdomains.py
backend/apps/makerspaces/apps.py
backend/apps/makerspaces/membership_admission_notifications.py
backend/apps/makerspaces/membership_legacy.py
backend/apps/makerspaces/membership_notifications.py
backend/apps/makerspaces/membership_notifications_research.py
backend/apps/makerspaces/membership_renewal_charges.py
backend/apps/makerspaces/membership_renewal_notifications.py
backend/apps/makerspaces/membership_renewal_reminders.py
backend/apps/makerspaces/membership_renewals.py
backend/apps/makerspaces/membership_self_service.py
backend/apps/makerspaces/membership_vouching.py
backend/apps/makerspaces/notifications_p2_broadcasts.py
backend/apps/makerspaces/notifications_p2_members.py
backend/apps/makerspaces/notifications_p2_subdomains.py
backend/apps/makerspaces/notifications_p2_terms.py
backend/apps/makerspaces/notifications_p2_vouches.py
backend/apps/makerspaces/subdomain_notifications.py
backend/apps/operations/apps.py
backend/apps/operations/membership_payment_reminders.py
backend/apps/operations/notifications_p2.py
backend/apps/operations/notifications_p2_alerts.py
backend/apps/operations/notifications_p2_reports.py
backend/apps/operations/reminder_sweeper.py
backend/apps/operations/report_schedule_services.py
backend/apps/operations/services_stocktake_workflow.py
backend/apps/operations/stocktake_discipline.py
backend/apps/payments/apps.py
backend/apps/payments/document_delivery.py
backend/apps/payments/documents.py
backend/apps/payments/failure_notifications.py
backend/apps/payments/notifications.py
backend/apps/payments/notifications_p2.py
backend/apps/payments/reminders.py
backend/tests/p2_n_other/conftest.py
backend/tests/p2_n_other/test_access_devices.py
backend/tests/p2_n_other/test_broadcast_vouch.py
backend/tests/p2_n_other/test_membership.py
backend/tests/p2_n_other/test_operations.py
backend/tests/p2_n_other/test_payments.py
backend/tests/p2_n_other/test_security_platform.py
backend/tests/p2_n_other/test_terms.py
docs/p2-n-other.md
```

## Claude verification changes (2026-10-17)

- **Direct-mail parity** (contract request 1 mitigated in-lane): `operations.notifications_p2.direct_mail_unless_routed`
  keeps the pre-Phase-2 direct emails that the members/payments matrix never governed — welcome
  (`approved`/`joined`), `verified`, known-account `invitation`, payment `document_issued` (sync, body not
  persisted, exactly as before). It is sent after commit, deduplicated by `source_metadata.p2_direct`, and
  skipped whenever the owner's own envelope resolves an email leg, so there is never a second copy. Once the
  resolver grows the source-bound defaults, the direct leg switches itself off.
- **Scheduled reports**: a presign failure no longer reaches `_send` with an unbound URL (restored the old
  "send only after a successful build" rule; no envelope either). Selected staff keep the existing signed-link
  email unless their own report envelope already emails them.
- First-email-failure signal pre-checks status/attempts before opening the adapter savepoint.
- Loan financial dedup: lane n-hw now emits no owner charge intent; this lane's `payments.ledger`
  `charge_raised` (raised by `create_payment`) is the single owner notice.
