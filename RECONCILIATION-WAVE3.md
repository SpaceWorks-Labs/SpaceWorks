# Wave 3 cross-lane handoff

Stage 2 implementation on `merge/mobile-into-integration`. No Codex CLI, review gates, Docker, test execution, build, Git staging/commit/stash/reset/merge or deployment was performed. No activation or destructive integrations 0043 was added.

## Wiring completed

- **M/P hold contract:** native-push ambiguity and expired parent claims become held, suppress fallback, and cannot be downgraded by older uncertain retry/failure/skip results. A proved success from the same attempt may settle the hold.
- **M/P inbox:** the in-app adapter calls `write_envelope_inbox`; audience, scope, stable intent ID and live hint survive without starting push.
- **A/M/P privacy:** discovery includes canonical envelopes/deliveries/endpoints/challenges, signed ingress and inbox-independent push parents. M calls P cleanup before clearing envelope context, and before hard purge. Canonical proofs, original receipt mappings, private inbox/push data and sender-bound consent are scrubbed by account identity; shared sender protection/verifiers remain.
- **P/M preferences:** an explicit canonical enable lifts only the same account/category/channel legacy false row atomically. Conversion still preserves all opt-outs.
- **C boundaries:** same-tenant nested boundaries reuse the held shared lock before opening another connection. HTTP/task cutover boundaries precede tenant locks; direct account/tenant/module purge entry points are also fenced. Provider ingress remains outside outer tenant rejection. Canonical envelope tasks own their per-leg gates rather than entering a tenant gate before the cutover fence.
- **C classifiers:** expanded/new canonical models are classified as source-local DROP; imported consent loses sender/generation/endpoint authority. Push subject ownership follows its envelope parent; source verifiers, raw references and encrypted history remain deployment-local. Expanded account and M/P/W authorization modules and membership revision/provenance inputs are registered. DeviceGrant historical staff tenant/generation/method are explicit DROP inputs. Runtime ciphertext is deliberately outside scoped PII backfill to avoid double encryption. Audit target handling derives omitted-target provenance from the total model classification.
- **C routes/uniqueness:** all six compatibility messaging webhook names are in PROVIDER_ONLY_ROUTES. Native session markers refuse organization/resource delegation before fast paths. The global WhatsAppTemplateBinding messaging_platform_template constraint has DROP_ROW handling.
- **C purge:** tenant purge prepares the canonical privacy graph before deletion. Channel purge retires verifiers, deletes consent before PROTECT endpoints, then deletes that channel?s canonical deliveries/configurations; global sender/alias/probe/provider protection remains. Inbox-only purge retains push through SET_NULL. PlatformWhatsAppSettings.app_id was already exposed by the retained platform control form/service; no new platform route is needed.
- **R/M:** the retained communications entry point lazily delegates to R. R?s existing push reader discovers P?s canonical delivery FK and works without inbox. Push canceled outcomes are explicit telemetry; held/abandoned receipt counters are separate chart series. Receipt conversion times are repaired in a new forward using retained original timestamps (encrypted mapping fallback), without modifying 0042.
- **C/R/W projections:** core `integrations.notification_projection` now owns the reviewed scalar helper; W?s old import is a re-export. Fan-out projects independently per audience while retaining source-control metadata. Membership/member-request/term adapters supply allowlisted subject/request scalars, with separate staff contexts. Core SMS has no inbox import dependency.
- **W attribution:** malformed member IDs/non-datetime values fail as validation errors; the current User is locked and rechecked against member kind, active tenant membership, deletion/retirement/purge/stub fences and time requirements.
- **U/M staff SMS:** retained own-consent endpoints admit active local staff only in their fixed tenant, binding their own verified phone to the current sender/generation. The UI uses the staff request context and exposes SMS consent. Unverified staff cannot enter member phone linking; diagnostics remain unavailable until that separate staff account has its own verified phone. Platform accounts remain refused.
- **G notes/tests:** actionable reconciliation notes were replaced with the final contracts. Catalog comments explicitly retain the orchestrator re-pin task. Historical lane handoffs remain unchanged. Added the shared activated-deployment test fixture with cutover/migration opt-outs, rewrote the requested push payload test around separate principals/canonical envelopes, supplied authoritative Twilio Content mocks, corrected the frozen STOP assertion, and installed W?s proposed membership cases.

## Forward migrations

- `integrations/0044_restore_receipt_received_at.py` depends on actual integrations leaf `0042_notification_history_conversion`. Data-only, restartable timestamp repair. Apply 0044 after the 0042 copy and before canonical route/replay on populated installations so replay sees original inbound time. 0043 remains reserved/absent.
- `makerspaces/0098_enabled_modules_choices.py` depends on actual makerspaces leaf `0097_reconcile_enabled_modules`. Explicitly pins the final JSONField declaration. Inspection found 0097 and the live model already use registry validation without scalar choices, so this is schema-neutral; scalar Django choices would reject valid module lists. Claude must verify the reported pending autodetector delta with `makemigrations --check --dry-run` in Django.

## Complete lane model/field inventory for re-pin

Exact evaluated forward-operation specifications, including constraints/indexes and field definitions, are in `backend/apps/tenant_migration/RECONCILIATION-FIELDS.json`. Baseline is bootstrap `3fded220`; all A/M/C/P forwards plus Wave 3 are included. The schema digest and tenant_dump_field_snapshot literal lists were not edited (only their pending-work comments changed).

| Model | Added fields | Altered fields / other schema changes |
| --- | --- | --- |
| `accounts.DeviceGrant` | staff_makerspace_id, credential_generation, login_method | ?; 1 constraint/index operation(s), exact definitions in JSON |
| `accounts.PasswordResetEnvelope` | ? | ?; 1 constraint/index operation(s), exact definitions in JSON |
| `accounts.User` | ? | ?; 1 constraint/index operation(s), exact definitions in JSON |
| `integrations.ChannelConfiguration` | use_platform_sender, sender_key, credential_version, activation_hold | channel |
| `integrations.ChatTemplate` | ? | feature |
| `integrations.DailyNotificationCounter` | ? | channel |
| `integrations.MessagingConsent` | sender_key, configuration_generation, endpoint | ? |
| `integrations.MessagingRecipientCorrelation` | probe_notification_delivery | ? |
| `integrations.MessagingSenderIdentity` | tenant_reference | makerspace |
| `integrations.MessagingSuppression` | ? | recipient_kind |
| `integrations.NotificationCredentialVersion` | **New model:** id, configuration, configuration_reference, makerspace_reference, generation, provider, integration_identity, sender_key, credentials, retired_at, wiped_at | ? |
| `integrations.NotificationCutover` | **New model:** id, route, sending_enabled, barrier_at, receipt_watermark, replay_watermark, snapshot, copied_at, reconciled_at, activated_at | ? |
| `integrations.NotificationDelivery` | sender_key, provider_source, credential_version, recipient_phone_hash, recipient_alias_hash, estimated_segments, billed_segments, quota_reserved_at, historical, accepted_at, sent_at, delivered_at, read_at, failed_at | state, channel |
| `integrations.NotificationDeliveryLog` | ? | channel, feature |
| `integrations.NotificationIngress` | **New model:** id, signed_user, configuration, makerspace, makerspace_reference, configuration_reference, channel, provider, transport, sender_key, generation, credential_version, integration_identity, dedupe_key, payload, protection_applied, state, attempts, next_attempt_at, last_error, received_at, processed_at | ? |
| `integrations.NotificationLegacyMapping` | **New model:** id, legacy_model, legacy_id, canonical_model, canonical_id, makerspace, disposition, snapshot, created_at | ? |
| `integrations.NotificationPreference` | ? | channel, feature |
| `integrations.NotificationProviderReference` | **New model:** id, provider, sender_key, provider_id, phone_hash, delivery_reference, makerspace_reference, generation, attempt, ambiguous, created_at | ? |
| `integrations.NotificationRecipient` | ? | feature |
| `integrations.PlatformWhatsAppSettings` | app_id | ? |
| `integrations.WhatsAppTemplate` | feature, provider_identity, validation_schema, needs_review | configuration, template_name; 1 constraint/index operation(s), exact definitions in JSON |
| `makerspaces.Makerspace` | ? | enabled_modules |
| `notifications.MemberPushDelivery` | envelope_delivery, retryable | inbox_row, status, envelope_delivery; 2 constraint/index operation(s), exact definitions in JSON |

User lifecycle fields moved into `models_user.py` without adding columns. F, W, R and U added no model columns. Wave 3 adds no model columns. The report response allowlist additionally includes `held_count`, `held_webhook_count` and `canceled_count`; generated OpenAPI/TypeScript remain untouched.

## Files changed

- `RECONCILIATION-WAVE3.md`
- `backend/apps/accounts/account_deletion.py`
- `backend/apps/accounts/account_deletion_discovery.py`
- `backend/apps/accounts/account_purge.py`
- `backend/apps/accounts/delegated_route_catalog.py`
- `backend/apps/accounts/route_exemptions.py`
- `backend/apps/accounts/surface_policy.py`
- `backend/apps/data_export/classification_messaging.py`
- `backend/apps/data_export/classification_platform.py`
- `backend/apps/data_export/fields.py`
- `backend/apps/data_export/references_json_fields.py`
- `backend/apps/data_export/subject_runtime.py`
- `backend/apps/data_export/subject_selectors.py`
- `backend/apps/encryption/registry.py`
- `backend/apps/hardware_requests/notification_projection.py`
- `backend/apps/integrations/messaging/consent.py`
- `backend/apps/integrations/messaging/purge.py`
- `backend/apps/integrations/messaging/views_member.py`
- `backend/apps/integrations/migrations/0044_restore_receipt_received_at.py`
- `backend/apps/integrations/notification_api_personal.py`
- `backend/apps/integrations/notification_builtin.py`
- `backend/apps/integrations/notification_delivery.py`
- `backend/apps/integrations/notification_privacy.py`
- `backend/apps/integrations/notification_projection.py`
- `backend/apps/integrations/reports_communications.py`
- `backend/apps/machines/usage_attribution.py`
- `backend/apps/makerspaces/lifecycle_purge.py`
- `backend/apps/makerspaces/lifecycle_purge_graph.py`
- `backend/apps/makerspaces/migrations/0098_enabled_modules_choices.py`
- `backend/apps/makerspaces/module_purge.py`
- `backend/apps/makerspaces/module_purge_collectors_addressed.py`
- `backend/apps/makerspaces/notifications_p2_members.py`
- `backend/apps/makerspaces/notifications_p2_terms.py`
- `backend/apps/operations/metrics_push.py`
- `backend/apps/operations/notifications_p2.py`
- `backend/apps/operations/report_definitions_hi.py`
- `backend/apps/operations/report_fields_hi.py`
- `backend/apps/operations/reports_communications.py`
- `backend/apps/tenant_migration/RECONCILIATION-FIELDS.json`
- `backend/apps/tenant_migration/authority_guards.py`
- `backend/apps/tenant_migration/authority_reconciliation.py`
- `backend/apps/tenant_migration/catalog_account_context.py`
- `backend/apps/tenant_migration/catalog_messaging.py`
- `backend/apps/tenant_migration/catalog_notifications_contract.py`
- `backend/apps/tenant_migration/gate_policy_tasks.py`
- `backend/apps/tenant_migration/gate_runtime.py`
- `backend/apps/tenant_migration/middleware.py`
- `backend/apps/tenant_migration/task_gate.py`
- `backend/apps/tenant_migration/tenant_dump_catalog.py`
- `backend/apps/tenant_migration/tenant_dump_field_snapshot.py`
- `backend/apps/tenant_migration/unique_values.py`
- `backend/config/settings.py`
- `docs/INVARIANTS.md`
- `docs/MODULES.md`
- `docs/SOURCE-MAP-NOTIFICATIONS.md`
- `docs/SOURCE-MAP.md`
- `docs/environment-reference.md`
- `frontend/src/features/notifications/MyNotificationSettings.tsx`
- `frontend/src/features/notifications/SmsConsent.tsx`
- `frontend/src/features/notifications/smsConsentApi.ts`
- `frontend/src/features/staff/panels/DashboardStats.ts`

## Ignored verification files to transport

These files are outside normal Git transport. Claude must include them in the final frozen verification bundle; this handoff makes no collection or passing-test claim.

- `backend/tests/conftest.py` - SHA-256 `bd1d2dcdba3fc4bc00c9cdb876dc23f798216c5971284aa9cbe3ac825f6ee2b7`
- `backend/tests/integrations/test_push_payload_m1b.py` - SHA-256 `54d82b308f366d5e3cbf0dc140dfcb607422c65204f894ac4d07547570f9e325`
- `backend/tests/integrations/test_reconciliation_cross_lane.py` - SHA-256 `ac88cd19e3d6c893f1fa96b8cf1ee26c876f287de2f256c6ded991f270881153`
- `backend/tests/notifications/test_reconciliation_privacy.py` - SHA-256 `7ff5d8ad6d3a70fbb3c180ee5e203c9f6ee4aa78799d38e85eb83d55c6bd0d05`
- `backend/tests/tenant_migration/test_reconciliation_nested_boundary.py` - SHA-256 `1a01019e9d4469e12114fa4390befab8cc0bd81680ac54c3cc73140ece1f597d`
- `backend/tests/makerspaces/test_reconciliation_w.py` - SHA-256 `c98fd1598856572e00cccaf38d8a6e352f66dcfb78e6a8bfa514fd85f38e1d89`
- `backend/tests/machines/test_reconciliation_attribution.py` - SHA-256 `2cd9f04f366e686159ad9970b419da95d91aec501dc9549da67116fd6bfa5c70`
- `backend/tests/p2_wa_twilio/conftest.py` - SHA-256 `735dbb4f516115be14a50852a12173afd337a802ec259743317b1f8d88b49bc0`
- `backend/tests/p2_wa_twilio/test_approvals_guards.py` - SHA-256 `466436ee1ce03b46494ef346c9878e18842690f1c22833a9d636a23d5d14dcb3`
- `frontend/src/features/notifications/SmsConsent.test.tsx` - SHA-256 `7ee4e9d7ccc608455ac780ae6f5479db1629ab2cc35113cefae3491f3cdd04b7`

## Verification and open checkpoints

- Python AST parsing passed for 59 changed/new Python source/test files; touched production files meet the 300-line ceiling except the accepted settings.py exception. Git whitespace checks passed. Static same-app migration leaves: accounts/0041_reconcile_native_account_context, integrations/0044_restore_receipt_received_at, makerspaces/0098_enabled_modules_choices, notifications/0010_envelope_push_constraints. This is not a Django MigrationLoader/runtime upgrade check. Catalog/snapshot Python ASTs were compared to HEAD and remain identical. Root CLAUDE.md/AGENTS.md remain byte-identical. No actionable MERGE-RECON markers remain outside historical handoff prose.
- Django is absent in host Python, and frontend TypeScript dependencies are absent in this worktree. Runtime imports, migration graph/upgrades, `makemigrations`, tests and frontend syntax/type/build checks remain unexecuted. Docker/tests/review gates/commits remain with Claude as requested.
- Claude must re-pin the live schema catalog and literal field snapshot; regenerate both API artifacts; freeze/transport the ignored verification files; collect and run the changed-area and cross-lane suites plus migration checks/review.
- Destructive integrations 0043, actual deployment barrier/copy/replay/watermark verification and sending activation remain held. No runtime reconciliation/activation success is claimed.
