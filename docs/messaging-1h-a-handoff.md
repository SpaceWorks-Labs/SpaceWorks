# Messaging 1h-A integration handoff

Foundation implementation for `lane/mobile-1h-a`. No staging, commits, CLI review,
Docker or pytest execution was performed. Python syntax, migration field-set coverage,
file ceilings and whitespace were checked statically. Django is not installed in the
host Python. The orchestrator must re-pin the catalog/field snapshot before running
catalog-dependent imports/checks and regenerate OpenAPI/client artifacts after integration.

## Contracts for B/C/D

- `messaging.resolver.resolve_sender(makerspace, channel) -> ResolvedSender | None`;
  `sender_key(channel, *, account_sid, from_number, business_account_id, phone_number_id)`;
  `webhook_urls(channel, makerspace_id=None)` emits canonical versioned API callback paths.
- `messaging.senders.reserve_sender(*, sender_key, channel, owner, makerspace=None,
  webhook_secret="", verify_token="", force_rotate=False) -> MessagingSenderIdentity`;
  `retire_sender(identity)`; `callback_credentials(*, channel, owner, makerspace_id=None)`;
  `wipe_retired_credentials()`. Cross-owner reuse is refused during the fourteen-day
  retired overlap; expired reservations transfer only after the old secrets are wiped.
  OTP ownership is never transferred. Migration seeds the existing OTP reservation.
- `messaging.locks.lock_whatsapp_sender(sender_key)` requires an atomic transaction and
  must precede row locks in STOP, probe claim, confirmation and blocked-row re-consent.
- `messaging.protections.recipient_hash(kind, value)` returns a deployment-keyed digest;
  `suppressed(channel, sender_key, phone_hash)` includes every mapped alias;
  `unmapped_alias_suppressions(sender_key)` is inspected under the sender advisory lock.
  Set suppression `recipient_kind="alias"` on alias-only STOPs (default is phone).
  Set delivery `recipient_phone_hash` at submission, so late callbacks never read a
  changed User phone as the original recipient. These two fields complete the section 15
  correlation contract without storing a phone on a delivery.
- `messaging.consent.live_consent(makerspace, user, channel)` and
  `grant_consent(*, user, makerspace_id, channel, action, source="member_settings")`.
  Re-consent lifts the phone plus mapped aliases and stores all lifted ids as a JSON
  list in `lifted_suppression_id`. It deletes a blocked correlation, permitting a new probe.
- `messaging.transport.send_message(sender, *, to, delivery_id, body="", template_name="",
  language="", parameters=(), status_callback=None) -> SendResult`; vendor-specific
  `twilio.send_message` and `whatsapp.send_message` share the same result contract.
  Ambiguous outcomes are marked explicitly; B must not retry an ambiguous probe.
  The original OTP `TwilioSmsProvider.send()` and `send_sms()` remain unchanged.
- `messaging.segments.count_segments(body)`; `prepare_sms(body) -> SmsBody(body,
  estimated_segments, encoding)`. Multipart accounting uses 152/66 and caps at three.
- `messaging.projections.PROJECTION_KEYS`, `EVENT_NAME_MAPPING`, `SMS_DEFAULT_TEXTS`;
  `project_context(feature, event, audience, context)` flattens reviewed scalar keys;
  `render_sms(feature, event, audience, context)` consumes that flat projection.
- `messaging.templates.binding_for(makerspace, sender, feature, event, audience)` picks
  platform/own bindings by the resolved source and current WABA. Saving bindings checks
  authoritative Meta approval and BODY-only positional shape (10-second timeout).
- `MessagingDelivery.Status`, `SkipReason`, `MessagingConsent.Action/Source`,
  `MessagingSenderIdentity.Owner`, `MessagingRecipientCorrelation.State`, and
  `MessagingWebhookEvent.State` define lane contracts. Progress/lease/quota/recovery
  behavior is B's responsibility. MessagingDelivery carries both legacy `segments`
  and explicit `estimated_segments` / nullable `billed_segments`.
- Existing account departure and purge call the foundation hooks; B must reuse these,
  not add duplicate archive opt-outs. Channel purge preserves sender-level suppressions,
  aliases and correlations. Portable consent is opted_out and imported templates need review.
- Consent PII maintenance uses the existing `app.pii_fence_operation` registered operation;
  `backfill_scoped_pii --fence-operation <uuid>` admits phone-only maintenance under a
  closed enable-transition fence. DELETE uses the existing immutable-delete GUC.
- Credential wiping is registered in Celery beat and the beatless scheduler.

## Integration-only work

The four prohibited hot spots were left untouched. Re-pin
`tenant_dump_field_snapshot.py` and `tenant_dump_catalog.py` once all lanes are integrated,
then regenerate `frontend/openapi-schema.json` and `frontend/src/generated/api.ts`.
B owns tenant origin/native-target, API-client denial and source-gate HTTP/task/fan-out
registry declarations for these new routes. The member JWT path allowlist is already
updated with the exact two personal paths. No test-send route is implemented in A.

## Exact new and changed model fields

All fields below use Django field names (relations, not `_id` attnames). Every new
model includes its auto BigAutoField `id`. No fields on the abstract secret mixin.

- `integrations.PlatformWhatsAppSettings`: `id, is_enabled, phone_number_id, business_account_id, access_token, app_secret, webhook_verify_token, updated_at`.
- `integrations.MakerspaceMessagingSettings`: `id, makerspace, use_platform_sender, sms_account_sid, sms_auth_token, sms_from_number, sms_sender_key, whatsapp_phone_number_id, whatsapp_business_account_id, whatsapp_access_token, whatsapp_app_secret, whatsapp_webhook_verify_token, whatsapp_sender_key, updated_at`.
- `integrations.MessagingSenderIdentity`: `id, sender_key, channel, owner, makerspace, active, retired_at`.
- `integrations.MessagingSenderCredential`: `id, identity, version, webhook_secret, verify_token, created_at, retired_at, wiped_at`.
- `integrations.WhatsAppTemplateBinding`: `id, makerspace, feature, event, audience, business_account_id, template_name, language, parameters, is_active, needs_review`.
- `integrations.MessagingConsent`: `id, makerspace, user, channel, action, phone_e164, phone_verified_at, source, lifted_suppression_id, created_at`.
- `integrations.MessagingSuppression`: `id, channel, sender_key, recipient_hash, recipient_kind, reason, created_at, provider_at, lifted_at, lifted_provider_at`.
- `integrations.MessagingRecipientAlias`: `id, channel, sender_key, alias_hash, phone_hash, first_seen_at`.
- `integrations.MessagingRecipientCorrelation`: `id, channel, sender_key, phone_hash, state, alias_known, probe_delivery, probe_started_at, confirmed_at`.
- `integrations.MessagingDelivery`: `id, makerspace, channel, user, audience, feature, event, event_key, context, scope, source_type, source_id, sender_key, provider, provider_source, provider_message_id, recipient_alias_hash, recipient_phone_hash, template_name, segments, estimated_segments, billed_segments, status, progress_rank, skip_reason, error_code, attempts, max_attempts, next_attempt_at, lease_token, lease_until, quota_reserved_at, created_at, accepted_at, sent_at, delivered_at, read_at, failed_at`.
- `integrations.MessagingWebhookEvent`: `id, makerspace, channel, provider, sender_key, dedupe_id, kind, payload, state, received_at, processed_at, attempts, next_attempt_at`.
- `integrations.PlatformSmsSettings` changed: `notifications_enabled, notifications_from_number`.
- `integrations.NotificationPreference` changed: `channel (choices add sms/whatsapp)`.
- `integrations.NotificationDeliveryLog` changed: `channel (choices add sms/whatsapp)`.
- `integrations.DailyNotificationCounter` changed: `channel (choices add sms/whatsapp)`.
- `notifications.MemberNotificationPreference` changed: `channel (choices add sms/whatsapp)`.

## Exact new API routes

- `GET, PATCH /api/v1/admin/makerspace/{makerspace_id}/messaging-settings`
- `GET, POST /api/v1/admin/makerspace/{makerspace_id}/whatsapp-templates`
- `PATCH, DELETE /api/v1/admin/makerspace/{makerspace_id}/whatsapp-templates/{id} (Django kwarg: pk)`
- `GET /api/v1/admin/makerspace/{makerspace_id}/whatsapp-templates/catalog`
- `GET /api/v1/me/messaging?makerspace={makerspace_id}`
- `POST /api/v1/me/messaging/consent`

## Changed existing API contracts

- GET /api/v1/bootstrap - messaging.sms/whatsapp availability in response.
- GET, PATCH /api/v1/admin/makerspace/{makerspace_id}/notification-rules - SMS/WhatsApp channel choices and module-filtered columns.
- GET, PATCH /api/v1/notifications/preferences/{makerspace_id} - SMS/WhatsApp personal choices.
- GET, PATCH /api/v1/integrations/makerspace/{makerspace_id}/timing-policy - channel list accepts SMS/WhatsApp.
- GET /api/v1/integrations/makerspace/{makerspace_id}/delivery-logs - channel filter enum gains SMS/WhatsApp; addressed history rendering belongs to B/C.

## Files changed

- `backend/apps/accounts/account_deletion.py`
- `backend/apps/accounts/account_deletion_discovery.py`
- `backend/apps/accounts/account_purge_scrub.py`
- `backend/apps/accounts/authentication.py`
- `backend/apps/data_export/classification.py`
- `backend/apps/data_export/classification_messaging.py`
- `backend/apps/data_export/datasets.py`
- `backend/apps/data_export/fields.py`
- `backend/apps/data_export/references.py`
- `backend/apps/data_export/references_json_fields.py`
- `backend/apps/data_export/subject_runtime.py`
- `backend/apps/data_export/subject_selectors.py`
- `backend/apps/encryption/management/commands/backfill_scoped_pii.py`
- `backend/apps/encryption/management/commands/decrypt_scoped_pii.py`
- `backend/apps/encryption/registry.py`
- `backend/apps/integrations/admin.py`
- `backend/apps/integrations/admin_messaging.py`
- `backend/apps/integrations/admin_sms.py`
- `backend/apps/integrations/dispatch_channels.py`
- `backend/apps/integrations/messaging/__init__.py`
- `backend/apps/integrations/messaging/consent.py`
- `backend/apps/integrations/messaging/locks.py`
- `backend/apps/integrations/messaging/pii_maintenance.py`
- `backend/apps/integrations/messaging/projections.py`
- `backend/apps/integrations/messaging/protections.py`
- `backend/apps/integrations/messaging/purge.py`
- `backend/apps/integrations/messaging/resolver.py`
- `backend/apps/integrations/messaging/segments.py`
- `backend/apps/integrations/messaging/senders.py`
- `backend/apps/integrations/messaging/serializers.py`
- `backend/apps/integrations/messaging/settings_service.py`
- `backend/apps/integrations/messaging/templates.py`
- `backend/apps/integrations/messaging/templates_provider.py`
- `backend/apps/integrations/messaging/transport.py`
- `backend/apps/integrations/messaging/twilio.py`
- `backend/apps/integrations/messaging/urls.py`
- `backend/apps/integrations/messaging/views_member.py`
- `backend/apps/integrations/messaging/views_settings.py`
- `backend/apps/integrations/messaging/views_templates.py`
- `backend/apps/integrations/messaging/whatsapp.py`
- `backend/apps/integrations/migrations/0034_messaging_m1h.py`
- `backend/apps/integrations/migrations/_messaging_m1h_guards.py`
- `backend/apps/integrations/models.py`
- `backend/apps/integrations/models_messaging_consent.py`
- `backend/apps/integrations/models_messaging_delivery.py`
- `backend/apps/integrations/models_messaging_settings.py`
- `backend/apps/integrations/models_sms.py`
- `backend/apps/integrations/notification_catalog.py`
- `backend/apps/integrations/notification_enums.py`
- `backend/apps/integrations/notification_scope_contract.py`
- `backend/apps/integrations/serializers_timing.py`
- `backend/apps/integrations/tasks.py`
- `backend/apps/integrations/tasks_messaging_settings.py`
- `backend/apps/makerspaces/admin.py`
- `backend/apps/makerspaces/lifecycle_purge.py`
- `backend/apps/makerspaces/module_purge_plans.py`
- `backend/apps/makerspaces/module_registry_catalog.py`
- `backend/apps/makerspaces/module_registry_definitions.py`
- `backend/apps/makerspaces/platform.py`
- `backend/apps/makerspaces/views.py`
- `backend/apps/notifications/inbox_scope.py`
- `backend/apps/notifications/migrations/0006_messaging_m1h.py`
- `backend/apps/notifications/models_inbox.py`
- `backend/apps/notifications/preferences.py`
- `backend/apps/operations/management/commands/run_scheduled_tasks.py`
- `backend/apps/tenant_migration/catalog_messaging.py`
- `backend/apps/tenant_migration/target_projection_fields.py`
- `backend/apps/tenant_migration/tenant_dump_authority.py`
- `backend/apps/tenant_migration/tenant_dump_model_catalog.py`
- `backend/config/settings.py`
- `backend/config/urls.py`
- `docs/INVARIANTS.md`
- `docs/MODULES-PLATFORM.md`
- `docs/MODULES.md`
- `docs/SOURCE-MAP.md`
- `docs/environment-reference.md`
- `docs/messaging-1h-a-handoff.md`
