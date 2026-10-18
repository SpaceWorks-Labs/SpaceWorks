# Lane R handoff

Implemented on `lane/recon-R`, after wave-1 head `0579b1b3`. No staging,
commits, merges, Docker, pytest, Codex CLI or review gates were run.

## Result

- The registered communications builder is now
  `operations.reports_communications.build_communications_health` (version 4).
  Canonical deliveries supply addressed/personal chat facts. EmailLog supplies
  physical email outcomes once; per-device ledgers supply push outcomes once.
  Retained room logs and optional inbox reads keep their measurement contracts.
- Legacy MessagingDelivery is never queried by production reporting. Its unique
  NotificationLegacyMapping supplements the canonical row with original progress
  and suppression, without adding a second delivery. T foundation mappings also
  preserve observations predating the timestamp expansion. Lookup batches use the
  indexed legacy identity, validating canonical target and tenant before use.
- Delivery/read evidence survives late failures; pending, sending, held and canceled
  histories remain distinct. Requester audience and own/platform source are retained.
  SMS billed zero wins over estimates. Provider text/reasons use closed vocabularies.
- Current held ingress and original abandoned-receipt observations are separate
  measures. Original abandonments come from immutable mappings, with original dates,
  and do not assert that replayed receipts remain abandoned. Reports never replay,
  mutate, activate or dispatch anything.
- Member consent is a current member-account snapshot, independent of date filters
  and excluded from organization totals. SMS compares current phone verification,
  sender and generation; WhatsApp uses current signed endpoint proof and opt-outs.
  Staff sharing a phone cannot enter the member total. Account-only recipients still
  enter delivery cohorts; the explicitly named member snapshot does not count them.
- Shared SQL buckets resolve calendar labels in each tenant before filtering.
  Mobile grants also recognize A's fixed staff tenant. Presence coverage no longer
  loses its substantive report to a duplicate dict key. Event/booking subject/table
  contracts and document/settlement accounting remain intact; pending debt never
  contributes to collected platform revenue.
- Platform services use canonical addressed/personal facts and push-parent tenant
  attribution, preserving OTP distinction and anonymous hidden-provider buckets.
  The platform dashboard includes canonical failures. Module health includes SMS/WA
  delivery cohorts. Push metrics tolerate an absent optional inbox app and label holds.
  The beat-less runner retains canonical/recovery schedules and excludes inbox tasks
  when that app is tombstoned.

## Schema and migrations

No model columns, constraints, routes or migrations added. The actual operations
leaf was listed and is `0013_stocktake_discipline`; no forward is warranted.
Reports consume M's 0041 expansion/0042 mappings and A's 0041 staff tenant snapshot.
The OpenAPI row allowlist adds `held_count` and `held_webhook_count`; the existing
dynamic counts serializer picks them up. Communications version is 4; platform
services and module health are 3; mobile devices/auth are 2. G regenerates artifacts.

## Interface requests

- **P**: complete the planned single concrete FK from MemberPushDelivery to
  integrations.NotificationDelivery and nullable `inbox_row` with SET_NULL. Reporting
  discovers that FK by target model, so its spelling is unconstrained. Preserve child
  columns `platform`, `provider_source`, `status`, `attempts`, `last_error`, `created_at`.
  Parent supplies makerspace and envelope feature/audience, including with no inbox.
  No push-parent outcome is counted alongside its device children. The no-inbox
  integration test deliberately requires P's schema and cannot pass on this pre-P tree.
- **M**: the retained public function in `integrations/reports_communications.py`
  must delegate to R's registered operations builder (lazy import) or be retired after
  callers are repointed. R cannot edit that M-owned file; the registry already uses
  the canonical builder. Its old direct entry point still has inbox-only push reads.
- **M**: preserve original `MessagingWebhookEvent.received_at` on the mapped
  NotificationIngress during conversion. `_notification_conversion_v1.receipts`
  currently creates it with auto_now_add and never restores the original timestamp.
  This affects held-receipt cohort dates and potentially replay's original-time proof
  window. R preserves original abandonment dates from mappings, but cannot repair
  M's conversion/processing timestamp contract. Add a forward repair if 0042 has
  already run; do not rewrite deployed migration history.
- **G/U**: regenerate OpenAPI/TypeScript once lanes settle, expose/label the new
  hold counters, and update messaging measurement docs/INVARIANTS/SOURCE-MAP for the
  canonical builder, mapping history, proof-bound snapshots and report versions.
  No generated artifacts or G-owned prose were edited here.

## Verification and ignored tests

Both operations test conflicts were resolved: audit export retains the stable private
phone sentinel; finance retains staff account kind and the local header assertion
that omits the deployment-only makerspace dimension. New regression files cover
canonical/mapped history, suppression, holds, monotonic progress, billed-zero segments,
original receipt history, DST/local filtering, weighted organization rates, sender/
phone-instance consent, signed WhatsApp proof, account-kind/contact isolation, platform
privacy, pending debt, report permissions/table metadata and inbox-independent push.

AST parsing, line ceilings, conflict/note scans and git diff whitespace checks are
recorded in `backend/tests/operations/_reconciliation_artifacts/lane_R_handoff.json`.
There were no tracked MERGE-RECON(R) notes in the incoming tree; owned M/P scheduler
wording was reconciled and removed. The ignored delta ZIP includes all seven changed
test/helper files and hashes against the immutable wave-1 suite. Claude/G must
transport it and run collection and `./scripts/dev.sh test tests/operations` after P
and the M requests above land. Runtime checks, migration upgrade checks and all gates
remain with Claude/G; static success is not a claim of passing runtime tests.
