# Lane P implementation handoff

Branch: lane/recon-P. Implementation is uncommitted; no staging, commits, merges,
Codex CLI, review gates, Docker or pytest were run. Only notifications implementation
and notifications-owned ignored tests/artifacts were written.

## Result

The canonical NotificationDelivery(native_push) owns per-device MemberPushDelivery
children. NotificationsConfig.ready registers the query-free M callback. Device calls
retain cutover -> tenant boundaries through completion, use atomic UUID claims and
recheck current source, account kind/generation, tenant, registration, device and
intersected personal/matrix policy before I/O. Member/requester accounts with a proved
source tie do not need membership or inbox installation. Staff use their separate
account and fixed-tenant staff grant. There is no platform grant path.

Payload v2 uses uuid5(NAMESPACE_URL, envelope.dedup_key), tenant, feature/event,
optional inbox_row_id and supported local links. It uses rendered personal content,
not a room body. Invalid FCM/APNs tokens invalidate only the attempted destination
identity; rotation/reassignment during I/O cannot invalidate a replacement token.

Inbox creation no longer enqueues push. Old enqueue_member_push, deliver_row and
Celery deliver_member_push identifiers remain inert import/broker compatibility
shims. The five-minute sweep re-enters M's deliver_envelope(envelope_id), respects
parent backoff and never schedules historical parents. The legacy staff transport's
imports of member_push_leases are unchanged; new children use envelope_push_leases.

Lease expiry is not retried: it becomes held with the original token retained for
an actual completion of that same provider call. Explicit transport rejections can
retry within the parent's four-attempt budget. Network/unknown outcomes remain held.
Account cleanup fences late completions. A valid late in-flight provider response
can settle its own token; out-of-band child facts alone do not release the parent.

write_envelope_inbox(envelope, rendered) is supplied for M's in-app adapter: stable
intent identity, persisted audience/scope, local link and one post-commit live hint.
It never starts a push. Its M call site is requested below.

## Changed implementation files

- apps.py, inbox.py, member_push.py, member_push_policy.py, models_push.py,
  preferences.py, tasks.py.
- New envelope_push_leases.py, envelope_push_transport.py, privacy.py.
- New migrations/0008_envelope_push_expansion.py,
  migrations/0009_envelope_push_conversion.py,
  migrations/0010_envelope_push_constraints.py,
  migrations/_push_conversion_v1.py.
- This handoff. All paths are below backend/apps/notifications/.

## Migrations and field contract

Actual listed leaves before P: notifications/0007_merge_mobile_preferences,
integrations/0042_notification_history_conversion, accounts/0041_reconcile_native_account_context.
No historical migration is edited.

0008 depends on notifications0007, integrations0041 expansion and accounts0041.
It expands nullable envelope_delivery, nullable SET_NULL inbox_row, retryable and
held/canceled statuses. Deploy this expansion BEFORE recording M's barrier, while
all old writers/instances are drained. No M0042 dependency is imposed on expansion.

On a populated installation, run M0042 after that barrier and before P0009. P0009
requires receipt_only, sending disabled, barrier_at, copied_at and the exact original
_push fingerprint. It holds the frozen shared cutover lock exclusively across
restartable per-row transactions. Each original child, inert parent and encrypted
NotificationLegacyMapping commit together. Canonical_model is MemberPushDelivery,
canonical_id is the original child ID; its parent is child.envelope_delivery_id.
Every original physical _push column is preserved in the encrypted snapshot.

An inbox cannot prove current source/revision authority, so every old row receives
its own explicitly historical migration.history envelope/native-push parent. Terminal
sent/skipped/failed rows stay inert, including failed rows below the old retry budget.
Untouched pending rows become canceled; attempted pending and all sending/expired
leases become held. Original counters, errors, lease data and timestamps stay on
the child and in its snapshot. No canceled old row automatically creates new work.
Fresh source-backed producers may create independently authorized canonical intents.
Distinct inert parents preserve all old attempts without parent/device collisions.

P0009 intersects existing canonical selections with legacy false values, preserves
email opt-outs/fallback refusal and never creates broader positive selections.
Empty fresh graphs may apply P before M0042: P leaves the shared snapshot empty so
M can initialize its complete fingerprints. This is covered by an owned test.

0010 verifies every populated row's inert parent/mapping and original fingerprint,
then makes envelope_delivery non-null, removes uniq_member_push_delivery and adds
uniq_envelope_push_device(envelope_delivery, push_device). inbox_row is optional
SET_NULL, so reading/retaining/deleting inbox rows cannot delete delivery history.
All conversion forwards are deliberately irreversible; there is no reverse that
would restore queued authority. No external send occurs in any migration.

Final model changes (for C/G):
- MemberPushDelivery.envelope_delivery: required FK to integrations.NotificationDelivery,
  CASCADE, related_name=push_children. Tenant/account ownership flows through
  envelope_delivery.makerspace / envelope_delivery.envelope.recipient.
- inbox_row: nullable/blank FK, SET_NULL instead of CASCADE.
- retryable: BooleanField(default=False).
- status adds held and canceled, still max_length=8.
- Unique constraint changes from inbox/device to envelope_delivery/device.
No HTTP routes or serializer shapes were added; generated schema files were not touched.

## Exact interface requests (other lanes' files were not edited)

1. **M: integrations/notification_delivery.py::record_result** must treat ambiguous
   native_push results as HELD, like SMS/WhatsApp; do not convert them to terminal
   failed or create email fallback while child outcomes are unknown. P returns
   ProviderResult(False, ambiguous=True, error_code=ambiguous_timeout). Preserve a
   sweep-established hold against an older uncertain failure/retry result. A proved
   success from the original fenced worker may settle its own held attempt. M's
   current code limits addressed_hold to sms/whatsapp, so this wiring is REQUIRED.
   Keep claim retrying held parents disabled; evidence must resolve the child and
   parent together before activation. P's sweep also quarantines expired children.
2. **M: integrations/notification_builtin.py::send_builtin**, in_app branch: replace
   the inline row creation with notifications.inbox.write_envelope_inbox(envelope,
   rendered), and keep returning ProviderResult(True, f"inbox:{row.pk}"). The old
   branch drops audience/scope and defaults member rows to staff.
3. **M: integrations/notification_privacy.py::scrub_account**: call
   notifications.privacy.scrub_account(user, makerspace_id) at the START, before
   clearing envelope.context (it proves ownership of mappings after device cascade).
   Guard optional app imports with apps.is_installed('apps.notifications'). Keep
   the existing cutover -> sorted tenant -> User lifecycle locks and include inbox,
   push children/mapping redaction in the existing audit metadata. **M:
   integrations/messaging/purge.py::purge_user** must additionally call the same P
   helper with purge=True before deleting devices/endpoints. P uses account PK and
   parent tenant, never contacts, and preserves other accounts' rows/shared STOP.
   The P-owned helper is complete; these M-owned call sites remain REQUIRED.
4. **M/U: canonical personal selection writes** must coordinate explicit re-opt-in
   with any existing MemberNotificationPreference false row in the same transaction
   (or deliberately keep its veto and expose the legacy preference editor). An
   explicit user enable must update both stores; conversion never clears opt-outs.
   Reads now intersect both stores even for legacy room/native transports.
5. **M: tests/integrations/test_push_payload_m1b.py** still assumes inbox-triggered
   delivery, deliver_row and promotion of a member account into staff. Update it to
   canonical envelopes and separate staff/member principals. P fixed the shared
   test_support_m1b fixture to create a real member-kind, generation-bound attested
   grant and explicitly installed modules; case.prepare now provides canonical
   source-backed envelopes alongside the retained legacy case.enqueue helper.
6. **A: accounts/account_deletion_discovery.py** add MemberPushDelivery ownership via
   ('envelope_delivery__envelope__recipient', 'envelope_delivery__makerspace'). The
   current inbox-only paths lose tenant/account discovery for optional-inbox children.
   Keep the existing archive_consents/purge_user contracts; M must wire request 3.
7. **C: tenant_migration/tenant_dump_field_snapshot.py, model/user/FK policies,
   data_export/subject_selectors.py, makerspaces lifecycle/module purge collectors**:
   classify the fields above and replace inbox-only tenant/recipient selectors with
   the canonical parent path. Push remains telemetry omitted/inert on import, not
   target authority. Inbox-only purge must retain children; tenant/account purge
   must find inbox-independent children. Include new P authorization modules in
   authority_guards.AUTHORIZATION_SOURCES and recompute the digest only in C.
8. **C: tenant_migration/gate_runtime.py::boundary_tenant_write** still needs M's
   requested same-tenant reentrant branch BEFORE opening another shared_boundary.
   M -> P nested boundaries can otherwise deadlock behind an exclusive waiter.
   P retains the required cutover boundary outside claims/provider I/O.
9. **R:** use envelope_delivery for tenant/recipient/source/audience identity in push
   analytics. held/canceled and retryable are explicit; original attempt mappings
   and historical parents must not be counted twice as current live sends.
10. **G:** replace/remove docs/INVARIANTS.md's MERGE-RECON(P) note and its obsolete
    inbox-coupling paragraph using the final contract above. That is the ONLY P
    bootstrap note found; docs are G-owned and were intentionally not edited.
    Update core source/field documentation and regenerate schemas after integration.
    The inbox module can be disabled without affecting canonical push; a deployment
    tombstoning the entire notifications app also removes its registered adapter,
    so do not advertise core push under app tombstoning without a reviewed relocation.

## Verification and ignored tests

Updated test_delivery_m1b.py, test_policy_m1b.py, test_leases_m1b.py,
test_support_m1b.py. Added conftest.py, push_envelope_helpers.py,
test_reconciliation_conversion.py, test_reconciliation_preferences.py and
test_reconciliation_privacy.py under backend/tests/notifications/.
Retained broadcast, portability, scheduler and route-guard tests. No owned conflict
markers were present. Tests cover optional inbox/module, canonical parent uniqueness,
FCM/APNs payloads/token invalidation and rotation, known rejection budgets, unknown
outcome holds, account-only audiences, source/matrix/device revocation, fixed-tenant
staff, scope selection, privacy/shared contacts, lease races, all old-row dispositions,
original fingerprints, restart/collision handling and conservative preference union.

The conversion fixture exposes the expanded nullable column and invokes frozen
historical-model helpers on real rows; it never reverses an irreversible migration.
Full MigrationExecutor fresh/O/T/sibling ordering, Django checks, schema drift and
actual DB/provider/race execution remain orchestrator/G verification, not a claimed pass.
Suggested owned command: ./scripts/dev.sh test tests/notifications
Also rerun M's push payload suite after its owner updates request 5, plus account
privacy/discovery, catalog/export/purge and native/source-gate integration consumers.

Static AST parsing of all owned source/tests, source line ceilings, owned marker
scan and git diff --check passed. No collection or runtime tests were attempted.
The ignored _reconciliation_artifacts/lane_P_handoff.json records exact file hashes,
base manifest/archive hashes, test delta archive, static commands, implementation HEAD
and the explicit absence of collection/runtime results. Claude/G must transport that
ignored delta; implementation commits alone do not carry it.

## Remaining operational hold

No activation, retirement or sign-off is asserted. Keep sending paused until the
required M/A/C interfaces, original mappings/fingerprints, unresolved held outcomes,
full migration checks and execution evidence are reconciled. An unresolved legacy
held attempt remains explicit history; it is never resent to discover an outcome.
