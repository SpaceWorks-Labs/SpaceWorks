# Phase 1a notification contract

The new personal contract lives in `integrations/notification_*`, `models_contract.py`,
`models_endpoints.py` and `notifications/models_preferences.py`. The existing
`integrations.NotificationPreference` remains the tenant matrix. The new
`notifications.NotificationPreference` is the per-person, per-category channel selection.
These are different policies and neither can grant the other's authority.

Domain lanes call `notification_outbox.emit(...)` inside their domain transaction and
register `NotificationSource(eligible, render=None)` from app startup. `eligible(envelope)`
must reload the subject/source revision, explicit owner, resource state and original sender
authority. Campaigns must also re-evaluate their current audience. A missing source refuses
delivery. `render(envelope)`, when provided, rebuilds current private content.

`emit` accepts makerspace, explicit recipient, feature, stream, event, audience,
dedup_key, source_kind, source_id, revision, subject, scope, safe context, rendered
`{subject,text,html,link}`, timing_policy and available_at. The unique intent is committed
with the domain change; enqueue happens on commit. The periodic outbox sweeper recovers
broker failures and retries. Never put credentials or authentication proofs in rendered
content; existing synchronous/redacted authentication mail remains on its existing path.

At emission, an envelope snapshots personal integration identities and generations. A
later install/reconnect cannot acquire an old private message. At every send, retry,
release and digest rendering the shared layer reloads account standing, tenant servability,
source authority, staff machine/type/category scope, preference, module/configuration,
endpoint verification, consent and generation. Account-only owners remain supported.
Explicit opt-outs and suppression remain live even when their editor is disabled.

The five existing module exemptions and closed-with-issue opt-out exception remain
separate. Mandatory return-reminder/custody email accompanies selected chat; it is never
replaced by it. Suppression still wins. Custody may retain archived-space delivery.
Optional fallback needs both tenant and user permission and no deliverable selected
channel. Terminal channel failure can also release a single email fallback. Email-only
digests rebuild their constituent sources, and transport mail remains attached to envelope
authority even if somebody tries to retry its legacy EmailLog.

Delivery states are retrying, accepted, sent, delivered, read, failed and skipped.
Acceptance is not proof of delivery. Claims release database locks before provider I/O.
Retries have exponential delay/jitter, bounded Retry-After, and four attempts maximum;
ambiguous timeouts get one retry. Callbacks cannot regress successful acknowledgements or
cross an installation generation. Provider response text is never persisted as an error.

## Frozen HTTP surface

All paths below have prefix `/api/v1/integrations/makerspace/{makerspace_id}`.
JWT authentication and tenant-origin enforcement apply. Channel settings and test sends
require Space Manager identity (including authorized global superadmins). Personal actions
only affect the authenticated person's endpoints/preferences. Other managers and members
cannot configure channels. They see their own delivery metadata; a Space Manager can see
the tenant's metadata. No response contains credentials, destinations or message bodies.

| Method | Suffix | Request | Response |
|---|---|---|---|
| GET | `/channels?page=` | â€” | Page<Channel> |
| GET | `/channels/{channel}` | â€” | Channel |
| PATCH | `/channels/{channel}` | Any ChannelWrite fields | Channel |
| GET | `/personal/endpoints?page=` | â€” | Page<Endpoint> |
| POST | `/personal/endpoints/start` | channel, consent=true, consent_version, optional phone_number (WhatsApp candidate only) | challenge_id, expires_at, optional connect_url/instructions |
| POST | `/personal/challenges/{challenge_id}/verify` | Optional opaque provider code/state; provider verifies independently | Endpoint |
| DELETE | `/personal/endpoints/{id}` | â€” | revoked=true |
| GET | `/personal/preferences` | â€” | preferences: Selection[] |
| PUT | `/personal/preferences` | preferences: Selection[] (complete replacement) | preferences: Selection[] |
| GET | `/personal/deliveries?page=` | â€” | count, next, previous, results: Delivery[] |
| POST | `/channels-test` | channel and exactly one of endpoint_id/room_id | accepted, provider_id, retryable, error_code, sanitized_error |

ChannelWrite = enabled, room_enabled, personal_enabled, email_fallback, provider,
integration_identity, credentials (write-only map), quotas and templates. Channel returns
channel, enabled, room_enabled, personal_enabled, email_fallback, provider,
integration_identity, generation, credentials_set, quotas and templates.
WhatsApp providers are exactly `twilio|meta`. Credentials/identity/provider updates advance
the generation; old consent never becomes valid for a new installation. A database trigger also revokes personal endpoints
and advances the generation when their channel module or notifications is removed, so a
module reinstall never restores consent. Quotas accept
daily_limit and recipient_daily_limit. Template bindings contain event, audience, locale,
template_name and variables; approved is read-only and must be established by a provider.
WhatsApp has no staff rooms. Existing room transports retain their destination credentials;
the new room enable switch gates them without changing their audience.

Endpoint = id, channel, provider, integration_generation, verification_state,
verified_at, consented_at, consent_version, revoked_at, created_at.
Selection = category, channels[] and email_fallback, plus read-only available_channels[]
in responses. The tenant's enabled choices are exposed to personal clients; selecting
a disabled channel is rejected. Duplicate categories/channels and
unknown fields are rejected. Legacy email unsubscribes still defeat optional email fallback.
Manager defaults are Telegram when personal Telegram is enabled and verified; otherwise
email. Members default email plus in-app. Availability gates still apply.
Delivery = id, envelope_id, channel, state, attempt_count, next_attempt_at, last_error,
retryable, event, feature, created_at, updated_at. All list endpoints use the standard
page size 24 and return count, next, previous and results.

Errors document 400 validation (field errors or detail/code), 401, 403 and 404; mutations
also document 423/503 and proof/test routes document 429. Connection starts have a durable
5/hour/account/tenant limit plus a 60-second cooldown and API throttling. Proofs expire in
10 minutes and consume once, with at most five matching attempts.

## Frozen provider seam

```python
send(delivery, rendered: dict) -> ProviderResult
verify_callback(request) -> CallbackEvent | None
test(endpoint_or_room) -> ProviderResult
ProviderResult(accepted, provider_id="", retryable=False,
               error_code="", sanitized_error="",
               ambiguous=False, retry_after=None)
```

Factories register with `register_provider(channel, provider, factory)`; factory(config)
returns the adapter. Proof-capable adapters additionally implement
`start_challenge(challenge, code) -> {connect_url?, instructions?}`. A WhatsApp outbound
challenge reads the encrypted candidate_destination; a verified reply must match it.
No submitted candidate becomes an endpoint before provider proof.
Providers use the stable delivery identity as their idempotency key wherever the upstream
API supports one, and report ambiguous timeouts explicitly. Callback correlation must not
replace a different provider message ID already bound to the delivery.

`CallbackEvent` carries provider_id/state, optional signed delivery_id correlation,
EndpointProof, endpoint_id, opt_out and inbound. EndpointProof contains code, destination,
integration_identity, subject and explicit private=True. Signature/authentication checks
happen in the adapter before returning an event; the shared handler never trusts raw
browser destination IDs. Call `verified_callback(config, request)` from provider callbacks.
Telegram must prove private chat.id and from.id and verify its secret header; decision
callback_query remains ignored and inline keyboards remain prohibited. Slack requires
workspace OIDC; Mattermost requires configured-server OAuth; Discord requires identify
OAuth; WhatsApp requires signed matching inbound proof. STOP revokes. Only authenticated
inbound messages update last_inbound_at. Outside 24 hours, sending requires an approved
event/audience template. SMS-login proof/consent does not establish WhatsApp consent.

`notification_fake.FakeProvider` is available only through explicit test registration.
Production startup never registers it. All private bodies/destinations/candidate numbers
use the scoped PII registry; integration credentials always use the existing Fernet secret
pattern. All seven new model types are omitted from readable exports and DROP on import,
so there are no new export datasets, JSON remaps or subject selectors. Their User edges
are explicitly classified as excluded. Module purge removes the graph in dependency order.

## Integration verification

Migrations: integrations 0033 â†’ 0034 â†’ 0035 â†’ 0036, notifications 0004; actual parents
are integrations 0032, notifications 0003, makerspaces 0093 and encryption 0007.
Tests live in the gitignored `backend/tests/notifications_contract/` directory.
Run these plus the existing notification/email/timing/tenant-export suites with the isolated
test runner. No Docker/tests were run in this implementation lane.

Local syntax and static checks plus the dependency-free API client generator are available.
The OpenAPI snapshot has an additive contract projection; regenerate it with spectacular
`--format openapi-json` on the Django host, then rerun the client generator. Django was not
installed locally and dependency downloads were blocked.

The portable field/model dispositions are complete. The schema-digest pin still needs
runtime recomputation: a literal reconstruction did not reproduce the Phase-0 pin, so this
lane does not bless an unverified digest. Verify the base discrepancy and recompute
`tenant_dump_catalog.schema_digest()` on the integrated Django model graph before running
the portable catalog guard.
The current Phase-0 pin is `7a7132b9cf5e6f6883e4c8c868cbb35219fcf86f8fbb8cfc46329c484e7e9dc2`.
Do not bypass that guard or derive the pin from a changed graph without checking the
runtime field/model universe first.

Legacy `notify_lifecycle` reserves an envelope in the domain transaction and keeps its
existing post-commit builder timing. After materialization it stores the encrypted replay
snapshot and dispatches through that envelope. A crash before a legacy closure runs cannot
reconstruct that closure; Phase 2 replaces these reservations with source-backed `emit`
calls. Full transactional content persistence applies to the new contract immediately.
Concrete provider implementations and domain adapter conversions remain Phase 2 work;
the complete audience/channel target is [notification-coverage.md](notification-coverage.md).

## Files changed

```text
backend/apps/audit/presentation_catalog_platform.py
backend/apps/data_export/classification.py
backend/apps/data_export/references.py
backend/apps/encryption/management/commands/backfill_scoped_pii.py
backend/apps/encryption/management/commands/decrypt_scoped_pii.py
backend/apps/encryption/registry.py
backend/apps/integrations/apps.py
backend/apps/integrations/delivery_sources.py
backend/apps/integrations/dispatch_channels.py
backend/apps/integrations/dispatch_channels_delivery.py
backend/apps/integrations/migrations/0033_notification_endpoints.py
backend/apps/integrations/migrations/0034_notification_contract.py
backend/apps/integrations/migrations/0035_whatsapp_channel.py
backend/apps/integrations/migrations/0036_notification_pii_fences.py
backend/apps/integrations/models.py
backend/apps/integrations/models_contract.py
backend/apps/integrations/models_endpoints.py
backend/apps/integrations/notification_api_access.py
backend/apps/integrations/notification_api_channels.py
backend/apps/integrations/notification_api_delivery.py
backend/apps/integrations/notification_api_errors.py
backend/apps/integrations/notification_api_personal.py
backend/apps/integrations/notification_api_serializers.py
backend/apps/integrations/notification_availability.py
backend/apps/integrations/notification_builtin.py
backend/apps/integrations/notification_catalog.py
backend/apps/integrations/notification_contract_urls.py
backend/apps/integrations/notification_delivery.py
backend/apps/integrations/notification_digest.py
backend/apps/integrations/notification_email_source.py
backend/apps/integrations/notification_enums.py
backend/apps/integrations/notification_fake.py
backend/apps/integrations/notification_legacy.py
backend/apps/integrations/notification_outbox.py
backend/apps/integrations/notification_proofs.py
backend/apps/integrations/notification_providers.py
backend/apps/integrations/notification_quotas.py
backend/apps/integrations/notification_resolution.py
backend/apps/integrations/notification_sources.py
backend/apps/integrations/notification_tasks.py
backend/apps/integrations/notify.py
backend/apps/integrations/tasks.py
backend/apps/integrations/urls.py
backend/apps/makerspaces/module_purge_collectors.py
backend/apps/makerspaces/module_purge_plans.py
backend/apps/makerspaces/origin_scope_routes.py
backend/apps/notifications/migrations/0004_notification_preferences.py
backend/apps/notifications/models.py
backend/apps/notifications/models_preferences.py
backend/apps/operations/management/commands/run_scheduled_tasks.py
backend/apps/tenant_migration/catalog_notifications_contract.py
backend/apps/tenant_migration/tenant_dump_field_snapshot.py
backend/config/settings.py
backend/tests/notifications_contract/conftest.py
backend/tests/notifications_contract/test_api.py
backend/tests/notifications_contract/test_delivery.py
backend/tests/notifications_contract/test_outbox_models.py
backend/tests/notifications_contract/test_proofs.py
backend/tests/notifications_contract/test_resolution.py
backend/tests/notifications_contract/test_timing_whatsapp.py
backend/tests/test_notification_fanout.py
docs/INVARIANTS.md
docs/SOURCE-MAP.md
docs/notification-contract.md
docs/notification-coverage.md
frontend/openapi-schema.json
frontend/src/generated/api.ts
```
