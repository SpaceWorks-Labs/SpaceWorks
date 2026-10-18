# Lane M implementation handoff

Branch: `lane/recon-M`, based on bootstrap `3fded220`.
Implementation is uncommitted. Only `backend/apps/integrations/**` (excluding
`reports_messaging.py`) and `backend/tests/integrations/**` were written.
The ignored delta manifest contains the complete changed-file inventory and hashes.

## Result and boundaries

T's `NotificationEnvelope` / `NotificationDelivery` pipeline is the personal send
authority. O's addressed enqueue/worker entry points are inert import shims; the
intentional legacy mail/room legs remain. Native push delegates through a P-owned
registered sender; the former direct T device fan-out is removed.

SMS uses canonical configuration, current phone-instance/sender-bound consent,
reviewed projections, GSM/UCS2 segments and once-only quota reservation. WhatsApp
uses signed endpoint proof independently of SMS and the optional inbox. Both
revalidate account, tenant tie, source, opt-outs and sender authority before send.
Rotating credentials invalidates queued authority. Ambiguous provider outcomes and
expired addressed leases are held, never retried to discover an outcome.
Retained opt-out/selection tables still constrain delivery when the optional inbox
app is tombstoned; these reads never grant consent or import the removed models.

Authenticated current and compatibility callbacks feed an encrypted, deduplicated
journal. STOP/provider opt-out commits before acknowledgement, including disabled
or frozen tenants. A failed protection/storage transaction returns an error.
Early opt-out without exact provider correlation creates a sender-wide hold.
Replays use exact sender/provider/tenant/generation/attempt mappings, preserve
monotonic status, and use original inbound time for the session window. START
does not grant consent. Delayed signed proofs cannot lift a newer STOP.

Template approval comes from provider refresh plus reviewed schemas. Legacy
templates import pending review. Duplicate old settings/template writes return
503 until reconciliation, then 410 directing clients to canonical APIs.

## Migration and model contract

Actual integrations leaf before changes: `0040_merge_mobile_notifications`, whose
parents remain `0035_messaging_tenant_tie` and `0039_bd_r2_notification_media`.

- `0041_notification_cutover_expansion`: additive schema and explicit channel /
  PRESENCE choice unions; no historical migration edited.
- `0042_notification_history_conversion`: irreversible, restartable historical-model
  conversion. Every target and unique legacy-ID mapping commits together; no sends.
  Preflight checks original row/schema fingerprints. T configurations remain the
  foundation; conflicting O alternatives retain encrypted provenance. Legacy queued
  rows become canceled history and uncertain rows become held historical records.
- `0043` is deliberately **not supplied**: section 5.15 requires verified M/P/C
  reconciliation before destructive retirement. Compatible models/import shims stay.

New models (all exported from `integrations.models`):

| Model | Fields / purpose |
| --- | --- |
| `NotificationCutover` | Singleton pk=1; route, sending_enabled, barrier_at, receipt_watermark, replay_watermark, snapshot, copied_at, reconciled_at, activated_at. Closed by default. Snapshot contains hashes/counts and operator sign-offs, never credentials. |
| `NotificationIngress` | Nullable configuration/makerspace/signed_user FKs; raw configuration_reference/makerspace_reference; channel/provider/transport/sender_key/generation/credential_version/integration_identity; unique dedupe_key; deployment-encrypted payload; protection_applied; state/attempts/next_attempt_at/last_error/received_at/processed_at. Partial due index. |
| `NotificationLegacyMapping` | Unique legacy_model/legacy_id; canonical_model/canonical_id; nullable makerspace; disposition; deployment-encrypted original snapshot; created_at. No send authority. |
| `NotificationCredentialVersion` | Nullable configuration FK; raw configuration_reference/makerspace_reference; generation/provider/integration_identity/sender_key; encrypted credentials; retired_at/wiped_at. Unique configuration_reference/generation. |
| `NotificationProviderReference` | Unique provider/sender_key/provider_id; phone_hash; raw delivery_reference/makerspace_reference; generation/attempt/ambiguous/created_at. Global physical correlation survives delivery/account/tenant deletion. |

Existing model field changes:

- `ChannelConfiguration`: use_platform_sender (default false), sender_key,
  credential_version, activation_hold. Canonical channel choices include SMS/WA.
- `WhatsAppTemplate`: nullable configuration, template_name length 512, feature,
  provider_identity, validation_schema, needs_review; conditional global binding
  uniqueness. Global imports never auto-select into a tenant installation.
- `NotificationDelivery`: HELD choice; sender_key/provider_source/credential_version;
  recipient_phone_hash/recipient_alias_hash; estimated_segments/billed_segments;
  quota_reserved_at; historical; accepted_at/sent_at/delivered_at/read_at/failed_at.
- `MessagingConsent`: sender_key, configuration_generation, nullable endpoint
  **PROTECT** FK. The append-only trigger remains; SET_NULL would mutate history.
- `MessagingRecipientCorrelation`: nullable probe_notification_delivery FK; retain
  old probe reference until its historical outcome is reconciled.
- `MessagingSuppression.recipient_kind`: adds sender for unresolved physical holds.
- `MessagingSenderIdentity`: makerspace changes CASCADE to SET_NULL; adds raw
  tenant_reference. Retired credentials/protection must survive tenant purge.
- `PlatformWhatsAppSettings`: app_id, required for canonical Meta configuration.
- Explicit choice unions: NotificationPreference, ChannelConfiguration,
  NotificationDelivery, NotificationDeliveryLog, DailyNotificationCounter channels;
  ChatTemplate/NotificationRecipient/NotificationDeliveryLog/NotificationPreference
  features include PRESENCE. No module key added.

## Deployment checkpoints for C / Claude

1. Apply A constraints, M0041 and P's nullable push expansion before the barrier.
   Deploy compatible runtime/HTTP ingress. Drain **all** old application instances,
   inline processors and provider calls; record uncertain leases/outcomes.
2. `python manage.py notification_cutover barrier --old-instances-drained`
3. Apply M0042 and P's restartable parent/mapping conversion. The push snapshot
   includes physical table columns and works without the optional app installed.
4. `python manage.py notification_cutover route`
5. Repeat `python manage.py notification_cutover replay --limit 200` until due
   receipts and continuing-tail events settle. Holds require evidence/manual review;
   replay backs off unresolved events. It never retries a held provider send.
6. After actual cross-lane checks:
   `python manage.py notification_cutover verify --producer-coverage-reviewed --push-reviewed --registries-reviewed`
   Verification requires no unresolved receipts, held attempts or ambiguous provider
   references; validates original mapping fingerprints/counts, canceled old queues,
   push mappings and preserved suppression identities; records verified watermark.
7. Prepare/test a separate retirement forward only once those proofs permit it.
   Activation is separately explicit: `python manage.py notification_cutover activate`.
   Never run expand/convert/retire unattended on populated installations.

Lock order: cutover boundary -> tenant boundary -> sender -> User/configuration ->
challenge/delivery/receipt rows. The cutover lock uses a dedicated connection and
spans provider I/O without holding an application transaction. Receipt replay has
its own serialization lock before tenant/sender locks. Protection commits before
optional tenant state, so a frozen tenant cannot prevent STOP storage.

## Exact interface requests (unowned files were not edited)

- **P**: in `notifications/apps.py::ready`, register a query-free callback through
  `notification_builtin.register_native_push_sender(fn)`. Signature:
  `fn(delivery, rendered) -> ProviderResult`. It owns per-device leased children,
  invalid-token cleanup and aggregate result. Enter M's shared cutover boundary
  **before** claims/provider I/O and retain it through completion; no inbox fan-out.
  Depend on M0041, not M0042. For every original push row write
  `NotificationLegacyMapping(legacy_model="MemberPushDelivery", legacy_id=old.pk,
  canonical_model=..., canonical_id=..., disposition=..., makerspace=...,
  snapshot=<encrypted exact original row JSON>)` in the parent-copy transaction.
  Preserve all original columns listed by `NotificationCutover.snapshot['_push']`;
  verification hashes that original projection. Enforce non-null/uniqueness only
  after complete dispositions. Resolve existing push-fixture account-kind assumptions
  in P's `tests/notifications/test_support_m1b.py` used by M's existing push tests.
- **C**: make `tenant_migration/gate_runtime.py::boundary_tenant_write` reentrant
  for a tenant already in `_boundary_shared_locks` **before** opening another
  dedicated shared boundary; nested sends can otherwise deadlock behind an exclusive
  waiter. Test that race. Put M's cutover boundary outside HTTP/task tenant/User locks
  and through commit for config/consent/account/purge/native mutation paths. Exempt
  authenticated journal/protection from outer frozen-tenant rejection; subsequent
  optional tenant writes still use `tenant_write` and may remain held.
- **C**: classify all new models/fields, raw references, routing bindings and encrypted
  JSON in tenant catalog/field snapshots, user-row discovery, export/import, encryption,
  backup, audit and authority dispositions. Suppression/aliases/probes/provider refs
  remain global protection, not tenant-private deletion targets. Credentials/history
  import inert and cannot grant target authority. Update AUTHORIZATION_SOURCES for
  new modules and `notification_callbacks.py`; C alone updates the catalog digest.
- **C**: wire `notification_privacy.prepare_channel_purge(space, channel)` and
  `prepare_tenant_purge(space)` before deleting configurations/tenant graphs. Retain
  retired verifiers/receipts/protection; delete own consent under the existing delete
  hatch **before** deleting endpoints (the immutable endpoint FK is PROTECT).
  Expose PlatformWhatsAppSettings.app_id in C's platform settings serializers/API.
  Explicitly backfill the WA module for preexisting operational T installations while
  preserving enabled state/personal opt-outs; never enable a platform sender globally.
- **C/G**: classify retained canonical routes in `notification_contract_urls.py`,
  Meta/Twilio URL modules and all O compatibility URLs from `messaging/urls*.py`;
  preserve signature-only provider routes and exact native/delegated scope denial.
  Classify new command/recovery/dispatch tasks and moved source-guard paths. No new
  HTTP route was added. Regenerate G-owned schema/TypeScript from changed serializers.
- **A**: call `notification_privacy.scrub_account(user, makerspace_id=None)` under
  sorted tenant -> User lifecycle locks; final hard deletion uses
  `messaging.purge.purge_user(user, makerspace_id)` before endpoint graph deletion.
  Add `NotificationIngress.signed_user` and canonical envelope ownership to discovery.
  Match User IDs only; member/staff sharing contacts remain separate.
- **W/F**: emit source-backed canonical envelopes, retaining source predicates/renderers
  and deliberate legacy room/mail skips. Do not call addressed enqueue or create
  optional inbox rows to trigger sends. Core SMS cannot require inbox installation.
- **R**: report canonical NotificationDelivery plus legacy mappings, sender source,
  timestamps and segments. The old MessagingDelivery table is frozen inert history.
- **U**: use canonical channel/settings/proof/preferences/test endpoints; SMS explicit
  sender-bound consent, WA signed proof. Retired duplicate write APIs return 503/410.
  Account-only tenant ties are valid; membership alone cannot be the editor gate.
- **G**: review/remove `docs/INVARIANTS.md:5444` MERGE-RECON(M) note (G-owned prose).
  Owned M notes are removed. Add the explicit activated-cutover shared test fixture
  for other domain suites (M supplies an owned fixture only). Update provider mocks
  in `tests/p2_wa_twilio/test_approvals_guards.py` for authoritative Twilio Content
  GET validation, and run the retained `p2_wa_meta`, `p2_wa_twilio`,
  `notifications_contract`, `p3_wire` and account-split WA suites. Those directories
  are outside M's exclusive tests path. Transport the ignored delta.

## Verification and remaining work

Added conversion/restart/fingerprint, durable ingress/recovery, signed callbacks,
consent/tie/rotation, STOP/alias, privacy/shared-contact, quota/segment and duplicate
producer tests under `backend/tests/integrations/test_reconciliation_*.py` plus owned
helpers/conftest. Resolved that directory's bootstrap broadcast-retry conflict by
retaining O's superset Celery join-guard cases. Existing WA document/window/template
tests remain present. New tests have not been executed or collected.

Static AST parsing, production line ceilings, owned conflict-marker scan and
`git diff --check` pass; exact counts/commands and hashes are in the ignored handoff
manifest/log. Django is not installed in this host Python. Per instruction, no
Docker, pytest, Codex CLI/review, staging or Git mutation was attempted.

Runtime migration graph/upgrades/makemigrations, DB trigger/locking races, provider
mock suites, cross-lane integration and producer coverage remain Claude/G checks.
No assertion of passing runtime tests, verified rollout or safe retirement is made.
Compatible old schema remains and fresh deployments default to sending paused until
explicit reconciliation/activation. The destructive 0043 is the remaining dependent
checkpoint, not a reverse migration that could invent authority or resend history.
