# Notification delivery source map

Continued from [SOURCE-MAP.md](SOURCE-MAP.md). Behaviour and incomplete integration are recorded in
[notification-contract.md](notification-contract.md) and [notification-coverage.md](notification-coverage.md).
Paths are repository-relative; filenames below are relative to each directory.

## Personal contract and providers

`integrations/models_contract.py` owns envelopes/outbox/deliveries, models_endpoints.py owns tenant
channel configuration/endpoints/challenges/WhatsApp templates, notifications/models_preferences.py
owns personal category selection. The older integrations.NotificationPreference is the tenant matrix.
notification_outbox.py owns durable emission/claims; notification_tasks.py the worker/sweeper;
notification_sources.py the domain registry; notification_resolution.py live target selection;
notification_availability.py the editor's tenant channel choices. notification_delivery.py owns
provider claims/retries/callback state, notification_quotas.py budgets, notification_digest.py
email-only summaries, notification_email_source.py legacy transport source revalidation,
notification_builtin.py email/inbox/native push. notification_legacy.py preserves old closures;
notification_fake.py is registered only by tests.

notification_api_access/channels/personal/delivery/errors/serializers and notification_contract_urls
own the scoped HTTP surface. notification_proofs.py owns challenge creation, single-use provider
proof consumption and revocation; notification_providers.py is the factory/result/proof seam.
accounts/authentication.py full-matches the six personal route shapes for member JWTs.
notification_oauth_verification.py binds authenticated actor/URL challenge/state before exchange
and serializes completion; notification_slack_views.py retains authenticated Slack installation only.
Migrations 0033–0036 and notifications/0004 own schema, PII fences and personal preferences.

notification_telegram.py owns provider/cache/generation/send checks; callbacks.py authenticates
private /start and transport.py bounds Bot API I/O. telegram.py selects the shared room sender and
views.py retains the secret-checked webhook, ignores decision callbacks and delegates account linking.

notification_slack.py owns Slack registration/OIDC/DM; notification_slack_http.py bounded/redacted
HTTP/JWT/signatures; notification_slack_oauth.py durable state/PKCE/redirect selection;
notification_slack_installation.py install validation; notification_slack_views.py shared OAuth and
acknowledge-only callbacks. notification_mattermost.py/http.py own configured-server OAuth/DM and
DNS/TLS policy. notification_discord.py owns identify/DM/signatures. Their *_urls.py mount surfaces;
IntegrationsConfig.ready registers these and Telegram/Twilio/Meta providers. OAuth redirect settings
are environment-backed fixed registered URLs. Signed state carries challenge identity; the frontend
resolves it through authenticated endpoints GET before verify. Placeholders/appended challenge IDs
are forbidden; authorization and exchange use identical redirects.

notification_wa_twilio.py owns the WhatsApp factory/proof/send; *_config/http/templates/callbacks
split credential/address/URL policy, REST/error mapping, approval/variables and signed events;
*_views/urls expose callbacks and approval diagnostics. notification_wa_meta.py and its
*_callbacks/http/ingress/schema/templates/views/urls implement the registered/mounted Meta source;
the independent default-off whatsapp module is registered, resolving the former readiness blocker. notification_wa_window.py owns bounded
replay/window helpers shared by both providers, resolution and delivery. Reserved bindings are
notification_opt_in / notification_test, member/en, for both providers.

## Domain sources and call sites

hardware_requests/notifications_p2.py owns equipment fan-out/savepoints; *_requests owns request
and staff-only charge summaries, *_reminders the loan ladder, *_reports problem reports,
*_rooms queued staff summaries and live source/scope checks. *_contact and *_email own verified
contact compatibility and email-policy/render helpers used by the shared resolver/mail transport. notifications.py and loan/reminder call sites use these adapters.
inventory/notifications_p2.py owns thresholds/watch-source invalidation; availability_stock.py
latches back-in-stock and notify_me.py reserves watch intents.

machines/notifications_p2_service.py owns printer/generic service sources, certifications.py
member/staff certification edges/digests, maintenance.py schedule/log sources, stock.py consumable/
procurement sources. service workflow/email barrels and low_stock.py call the wired adapters;
maintenance/notifications.py and procurement/notifications.py are explicit re-export barrels for
the source-backed maintenance/stock adapters.

operations/notifications_p2.py supplies explicit-owner/staff fan-out and safe source snapshots;
makerspaces/notifications_p2_members/terms/vouches/broadcasts/subdomains own membership/admission,
renewals, vouches, audience checks and subdomain outcomes. Membership barrels and reminders call
them; notifications/broadcasts.py calls notify_broadcast per selected account in its audited transaction.
payments/notifications_p2.py owns ledger/reminder/document notices independent of payment rail.
apiclients/notifications_p2.py owns API-access outcomes; devices/notifications_p2.py owns immutable
outage/recovery snapshots. operations/notifications_p2_alerts.py owns stocktake and first-email-failure
signal; notifications/emit.py and legacy_inbox.py share those source intents/UUID identities with
personal delivery to deduplicate retained legacy mirrors. notifications_p2_reports.py owns live
authorized report navigation notices. notification_catalog.py includes the landed adapter event strings;
notification_resolution.legacy_staff_email_allowed owns the operational-only staff mailbox allowance.
Event and Booking adapter ownership is in [SOURCE-MAP-COMMUNITY.md](SOURCE-MAP-COMMUNITY.md).

## Channel UI and registry composition

`features/notifications/channelsApi.ts` owns handwritten API types/query keys/mutations;
channelCatalog.ts owns providers/credential fields. ChannelSetupPanel/Form, WhatsAppTemplatesEditor,
ChannelTestSend and ChannelDeliveryLog compose tenant setup/diagnostics. PersonalChannels,
ConnectChannel and ChannelPreferences own account connection/category choices; MyNotificationSettings
composes them in the staff Inbox action/member Channels tab. Saves send changed fields only, avoiding
accidental generation rotation. MyNotificationSettings resolves signed OAuth code/state through endpoints GET and calls
authenticated personal verify; member JWT admission covers exactly the personal route shapes.
SmsConsent/smsConsentApi use retained core member consent, with current phone/sender binding.
Staff My channels is independent of inbox; account-only owners use server permission results.
Query keys include account/context/tenant and session switches clear private state. Duplicate
addressed settings/template/test components and their API client are retired.

Audit presentation and tenant-migration catalog/gate siblings below declare retained schema,
PII/export dispositions and callback participants. Existing encryption/registry.py,
data_export/classification.py/references.py, makerspaces/module_purge_plans.py and
module_purge_collectors.py compose the model registrations. Integrations apps.py/urls.py own runtime
provider/route mounting; provider source files alone do not imply a mounted integration.

## File inventory by owner

### `backend/apps/apiclients/`

`notifications_p2.py`.

### `backend/apps/audit/`

`presentation_catalog_p2_p_chat.py`, `presentation_catalog_p2_wa_twilio.py`,
`presentation_catalog_wa_meta.py`.

### `backend/apps/devices/`

`notifications_p2.py`.

### `backend/apps/hardware_requests/`

`notifications_p2.py`, `notifications_p2_contact.py`, `notifications_p2_email.py`,
`notifications_p2_reminders.py`, `notifications_p2_reports.py`, `notifications_p2_requests.py`,
`notifications_p2_rooms.py`.

### `backend/apps/integrations/migrations/`

`0033_notification_endpoints.py`, `0034_notification_contract.py`, `0035_whatsapp_channel.py`,
`0036_notification_pii_fences.py`.

### `backend/apps/integrations/`

`models_contract.py`, `models_endpoints.py`, `notification_api_access.py`,
`notification_api_channels.py`, `notification_api_delivery.py`, `notification_api_errors.py`,
`notification_api_personal.py`, `notification_api_serializers.py`, `notification_availability.py`,
`notification_oauth_verification.py`,
`notification_builtin.py`, `notification_catalog_p2_presence.py`, `notification_contract_urls.py`,
`notification_delivery.py`, `notification_digest.py`, `notification_discord.py`,
`notification_discord_urls.py`, `notification_email_source.py`, `notification_fake.py`,
`notification_legacy.py`, `notification_mattermost.py`, `notification_mattermost_http.py`,
`notification_mattermost_urls.py`, `notification_outbox.py`, `notification_proofs.py`,
`notification_providers.py`, `notification_quotas.py`, `notification_resolution.py`,
`notification_slack.py`, `notification_slack_http.py`, `notification_slack_installation.py`,
`notification_slack_oauth.py`, `notification_slack_urls.py`, `notification_slack_views.py`,
`notification_sources.py`, `notification_tasks.py`, `notification_telegram.py`,
`notification_telegram_callbacks.py`, `notification_telegram_transport.py`, `notification_wa_meta.py`,
`notification_wa_meta_callbacks.py`, `notification_wa_meta_http.py`, `notification_wa_meta_ingress.py`,
`notification_wa_meta_schema.py`, `notification_wa_meta_templates.py`, `notification_wa_meta_urls.py`,
`notification_wa_meta_views.py`, `notification_wa_twilio.py`, `notification_wa_twilio_callbacks.py`,
`notification_wa_twilio_config.py`, `notification_wa_twilio_http.py`,
`notification_wa_twilio_templates.py`, `notification_wa_twilio_urls.py`,
`notification_wa_twilio_views.py`, `notification_wa_window.py`.

### `backend/apps/inventory/migrations/`

`0015_watch_pending_index.py`.

### `backend/apps/inventory/`

`notifications_p2.py`.

### `backend/apps/machines/`

`notifications_p2_certifications.py`, `notifications_p2_maintenance.py`, `notifications_p2_service.py`,
`notifications_p2_stock.py`.

### `backend/apps/makerspaces/`

`notifications_p2_broadcasts.py`, `notifications_p2_members.py`, `notifications_p2_subdomains.py`,
`notifications_p2_terms.py`, `notifications_p2_vouches.py`.

### `backend/apps/notifications/migrations/`

`0004_notification_preferences.py`.

### `backend/apps/notifications/`

`models_preferences.py`.

### `backend/apps/operations/`

`notifications_p2.py`, `notifications_p2_alerts.py`, `notifications_p2_reports.py`.

### `backend/apps/payments/`

`notifications_p2.py`.

### `backend/apps/tenant_migration/`

`catalog_notifications_contract.py`, `gate_policy_p2_p_chat.py`, `gate_policy_p2_wa_twilio.py`.

### `frontend/src/features/notifications/`

`ChannelDeliveryLog.tsx`, `ChannelPreferences.tsx`, `ChannelSetupForm.tsx`, `ChannelSetupPanel.tsx`,
`ChannelTestSend.tsx`, `ConnectChannel.tsx`, `MyNotificationSettings.tsx`, `PersonalChannels.tsx`,
`WhatsAppTemplatesEditor.tsx`, `channelCatalog.ts`, `channelsApi.ts`.


## Reconciled history, privacy and reporting (2026-10-18)

The [main source map](SOURCE-MAP.md) details canonical sender/consent/ingress/cutover modules,
per-device envelope push and analytics ownership. `integrations/models_cutover.py` stores the
closed-by-default cutover, encrypted receipt journal/legacy mappings/credential versions and
physical provider references. `notification_cutover.py` owns the processing fence and operator
checkpoints; `notification_ingress.py` commits protection before optional tenant writes.
`notification_sender.py` and `notification_addressed.py` integrate SMS and sender safeguards;
`notification_personal_policy.py` retains core opt-out checks without inbox installation.
`notification_retention.py` is the bounded canonical leg/receipt retention sweep
(`tasks_messaging.canonical_retention_task`, hourly in both schedulers).
Integrations `0041`/`0042` expand/convert; `0043` retirement remains unsupplied.

`notifications/apps.py` registers `member_push` using
`notification_builtin.register_native_push_sender`. `notifications/models_push.py`,
`envelope_push_leases.py` and `envelope_push_transport.py` own per-device children, claims and
fenced completion beneath the canonical envelope parent. Notifications `0008`/`0009`/`0010`
expand/map/constrain those children. `inbox.write_envelope_inbox` never enqueues push.
`integrations/notification_privacy.py` calls `notifications/privacy.py` for cleanup before
clearing envelope context. Account discovery and push reports use the canonical envelope parent.
`integrations/notification_projection.py` projects allowlisted scalar template keys;
workflow adapters retain independent source/revision and audience checks.

`operations/reports_communications.py::build_communications_health` is the registered
communications-health builder v4; `integrations/reports_communications.py` is its lazy
compatibility delegate. `reports_notification_facts.py` reads inert mapping history without
counting a second send; `reports_push_facts.py` reads device children through their delivery
parent. Platform services/module health reports are v3; mobile device/auth reports are v2.
Frontend `MyNotificationSettings` composes canonical settings, proofs, preferences, SMS consent
and diagnostics for separate staff/member contexts. Deployment holds and callback compatibility
are in [the rollout guide](notification-reconciliation-rollout.md).
