# Notification reconciliation deployment checkpoints

This is an operational hold, not a deployment approval or a record of successful execution.
The 2026-10-18 reconciliation uses canonical `NotificationEnvelope`, `NotificationDelivery`
and `ChannelConfiguration` for personal delivery. SMS, Twilio/Meta WhatsApp and per-device
push feed that pipeline. Legacy room/mail legs retain deliberate pre-skips to avoid duplicates.
The duplicate addressed sender loop and inbox-triggered push entry points are inert shims.

## Expand, stop old writers, convert and replay

On populated installations, do not run expand/convert/retire unattended. Preserve backups,
original fingerprints and the historical migration/import helpers.

1. Apply accounts `0041_reconcile_native_account_context`, integrations
   `0041_notification_cutover_expansion`, and notifications `0008_envelope_push_expansion`.
   The push expansion depends on integrations 0041, not 0042, and must precede the barrier.
   Deploy compatible authenticated HTTP ingress. Drain every old application instance,
   inline processor and provider call; record uncertain leases and provider outcomes.
2. Record the processing barrier only after that drain:
   `python manage.py notification_cutover barrier --old-instances-drained`.
   Receipt-only mode journals signed callbacks/STOP while sending stays disabled.
3. Apply integrations `0042_notification_history_conversion`, then notifications
   `0009_envelope_push_conversion` and `0010_envelope_push_constraints`. Conversion is
   restartable and irreversible; each target and encrypted unique legacy mapping commit
   together. It verifies original schema/row fingerprints and sends nothing. Untouched
   old queues become canceled history, uncertain attempts become held, and terminal
   outcomes stay inert. Every old device row gets an inert parent and original snapshot.
   An empty fresh database may use the supported empty-graph ordering; this is not permission
   to use that shortcut on populated data.
4. Select canonical routing: `python manage.py notification_cutover route`.
   Routing does not enable sending. Review conflicting imported configurations under
   `activation_hold`; imported templates remain `needs_review` until provider validation.
5. Repeat `python manage.py notification_cutover replay --limit 200` through the captured
   watermark and continuing receipt tail. Original receipt times govern proof/session
   windows. Exact sender/provider/tenant/generation/attempt mappings constrain correlation.
   Resolve holds with evidence/manual review; do not resend a held attempt to discover
   its outcome. STOP/suppression protection commits even for frozen/disabled tenants.
6. After producer, push and registry checks, run
   `python manage.py notification_cutover verify --producer-coverage-reviewed --push-reviewed --registries-reviewed`.
   Verification refuses unresolved receipts, held attempts or ambiguous provider references,
   and checks mapping fingerprints/counts, canceled queues, device mappings and suppression
   identities. Required A/M/P/C interfaces, migration/runtime checks and replay evidence must
   be reconciled before operator sign-off. A successful documentation or static check is
   not evidence that these operational conditions passed.

## Retirement and sending are separate holds

Barrier establishment, canonical routing, sign-offs, successful verification and activation
append audit entries in the same database transaction as their checkpoints. Pass
`--operator-id <active-platform-superadmin-id>` to attribute a command to that operator;
omitting it records system attribution. Metadata contains only routing state, watermarks,
counts and review flags, never snapshot contents or verifier credentials. An audit failure
rolls back its checkpoint.

Integrations **0043 is deliberately not supplied**. A separate destructive retirement forward
must be prepared and tested only after replay and cross-lane reconciliation sign-off.
Retain `MakerspaceMessagingSettings`, `WhatsAppTemplateBinding`, `MessagingDelivery`, historical
migrations/import helpers and compatibility verifiers until then; they provide no send authority.

Sending additionally requires `python manage.py notification_cutover activate`. The singleton
cutover defaults closed, including on fresh databases. Neither schema migration nor canonical
routing activates it. Platform SMS/WhatsApp sending also needs explicit operator enablement
and each tenant's `use_platform_sender`; both remain off until enabled. Existing operational
WhatsApp installations use explicit conversion preserving enablement and personal opt-outs.

## Callback compatibility period

Keep the old `/api/v1/integrations/messaging/` callback URLs mounted during conversion,
replay and the provider callback tail. They are signature-authenticated compatibility ingress
into the canonical encrypted journal, never a second delivery loop. Keep canonical WhatsApp
callback routes mounted too. Do not redirect callbacks or break the exact public URL used
for Twilio signature verification. Old broker/import identifiers remain inert.

The retained routes include Twilio `twilio/platform/{inbound|status}` and
`twilio/m/{makerspace_id}/{inbound|status}`, and Meta `whatsapp/platform` and
`whatsapp/m/{makerspace_id}`, under that compatibility prefix. Configure new provider routes
from the canonical channel setup; preserve old registered routes while callbacks can still arrive.
There is no calendar removal date authorized by this reconciliation. End the compatibility
period only with recorded provider cutover, replay/tail and suppression evidence plus a
separately reviewed removal. Retired verifier secrets have a fourteen-day acceptance window;
secret wiping does not erase the permanent sender/provider correlation and protection records.

## Account migration is development-data only

Accounts `0032_account_context` retains the approved development role reset. D3 does not
authorize applying it to live staff authority data or claiming an authority-preserving
production transition. Member/staff/platform kinds and staff tenant are immutable. Native
staff use staff accounts, password, MFA and attestation; phone/social/OIDC and self-deletion/
identity-only restore stay member-only. Platform native grants are forbidden.

See [notification contract](notification-contract.md), [channel setup](messaging-channels.md)
and [mobile builder PRD](mobile/MOBILE-APP-PRD.md). OpenAPI is regenerated from the reconciled
server by the orchestrator; generated files do not establish rollout completion.
