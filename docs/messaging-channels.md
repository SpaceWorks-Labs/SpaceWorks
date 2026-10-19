# SMS and WhatsApp notifications

SMS and WhatsApp use the canonical personal envelope delivery pipeline. SMS uses Twilio;
WhatsApp supports Twilio or Meta. Each has an independent default-off module and tenant
matrix cells. Delivery additionally requires current source authority, personal selection,
consent, sender configuration and no suppression. Enabling a module alone never starts sending.
The [reconciliation rollout checkpoints](notification-reconciliation-rollout.md) remain held:
no destructive integrations 0043 is supplied, and sending needs explicit activation after replay.

## Audience and account settings

A member account can opt in when it has a current tie to the makerspace: a non-revoked
membership or an owned hardware request/direct loan, booking, event registration,
machine-service request or charge. Account-only owners qualify without buying the membership
or inbox module. Restricted, suspended, inactive, deleting/retired/stub accounts and platform
accounts are excluded. A revoked membership defeats an old owned-row tie. Staff recipients
use their separate active local staff account and current role/source authority.

Account Channels contains connections, category selections, history and SMS consent. Staff
have My channels separately from inbox; old `section=messaging` links remain aliases.
`GET /api/v1/me/messaging?makerspace={id}` reads masked consent/availability for eligible
member accounts; `POST /api/v1/me/messaging/consent` records explicit changes. SMS opt-in
requires the current verified phone, sender and configuration generation. Phone verification
alone does not subscribe. Phone A -> B -> A needs fresh consent after verification.

WhatsApp uses the canonical signed account-link challenge, not an SMS-style toggle. Start at
`POST /api/v1/integrations/makerspace/{id}/personal/endpoints/start` and complete the provider
proof through `/personal/challenges/{challenge_id}/verify`. A submitted number is a candidate,
never proof. SMS login/phone linking cannot grant WhatsApp consent. Delayed proofs cannot lift
a newer STOP. Disconnect and opt-out remain available for invalidated connections.

Personal category choices use `/personal/preferences` under the same integrations tenant
prefix. Tenant matrix, canonical choices and retained legacy false preferences intersect.
Selections never grant a tenant tie or staff authority. START/UNSTOP/YES at a provider never
subscribe the person; current explicit in-app proof/consent is required.

## Canonical sender and template setup

Space Managers use Settings -> Communication channels, backed by
`GET/PATCH /api/v1/integrations/makerspace/{id}/channels/{sms|whatsapp}`. Credentials are
write-only/encrypted. Save only changed fields: provider/identity/credential changes advance
installation generation and invalidate queued authority. Channel responses expose effective
setup fields including `use_platform_sender`, `sender_key`, `credential_version` and
`activation_hold`, without secrets. Review imported conflicts before clearing the hold.

Own credentials take precedence. Partial, broken or unreadable own values refuse delivery
rather than falling back. Platform senders require operator enablement and explicit tenant
`use_platform_sender`, initially false. Shared platform senders share physical STOP and
WhatsApp correlation protection across tenants. Removing one tenant cannot delete that protection.

WhatsApp templates live with canonical channel configuration. Twilio uses approved Content
SIDs; Meta uses approved WABA templates. Provider refresh establishes approval; browser writes
cannot approve them. Feature/event/audience variables must match reviewed projections.
Imported bindings remain `needs_review`; changing sender/business identity requires review.
Lifecycle BODY variables exclude notes, contacts, remarks and bearer links. Canonical payment
PDF bindings keep their existing private short-lived document media contract.

The duplicate `messaging-settings`, `whatsapp-templates` and old test APIs are retired writes:
503 during routing reconciliation, then 410 directing clients to canonical endpoints. Their
models/history/import helpers remain pending destructive retirement; never use the old send loop.

## Deployment and provider provisioning

Set `MESSAGING_WEBHOOK_BASE_URL` to the exact publicly reachable origin (optional deployment
prefix, no `/api/v1`, query or fragment). Twilio signature validation uses this configured URL,
including query parameters, never forwarded host headers. Canonical Meta HTTP uses
`WHATSAPP_META_GRAPH_VERSION` (default `v25.0`), and the legacy compatibility/template helpers
read the same setting. The version setting does not enable a sender.
Preserve `API_CLIENT_ENC_KEY` for encrypted sender credentials and retired verifiers.

For Twilio SMS:

1. Provision an SMS-capable notification number and enter canonical `account_sid`, `auth_token`
   and E.164 `from_number`, or configure the platform notification sender in `/control/`.
2. Keep OTP on its separate platform number. Tenants may use neither the OTP Account SID nor
   its number. Never put notification and OTP numbers in the same Messaging Service: provider
   STOP must not disable login/recovery. Notification SMS submits an explicit From number.
3. Configure signed form-encoded inbound/status callbacks using the exact setup URLs. Enable
   Advanced Opt-Out so signed `OptOutType` reaches SpaceWorks. Twilio error 21610 and the
   complete STOP keyword list also enforce suppression. Use `#rc=5&rp=5xx,ct,rt` connection
   overrides where displayed; Twilio strips the fragment from signature calculation.

For canonical Twilio WhatsApp, configure its account/sender (or supported Messaging Service),
public callback base and approved Content bindings. Its inbound route is
`/api/v1/integrations/makerspace/{id}/whatsapp/twilio/{generation}/inbound`;
status is `/whatsapp/twilio/{generation}/status/{delivery_id}` under that tenant prefix.
Approval refresh is `POST /whatsapp/twilio/templates/refresh` under the same prefix.

For Meta WhatsApp:

1. Use one Meta app per sender configuration. Verify the business phone and retain App ID,
   Phone Number ID and WABA ID. Register the Cloud API number in Meta with
   `POST /{phone_number_id}/register` and its two-step PIN; saving settings does not register it.
2. Store a system-user token with `whatsapp_business_messaging` and
   `whatsapp_business_management`, App ID, app secret and webhook verify token. Keep PINs and
   tokens out of audit notes. Subscribe the WABA to the app and the app to `messages`.
3. Register the exact canonical callback
   `/api/v1/integrations/makerspace/{id}/whatsapp/meta/{generation}/{phone_number_id}/webhook`.
   GET verifies the challenge; POST verifies `X-Hub-Signature-256` over raw bytes.
4. Refresh provider template approval and review imported bindings before activation.

Both WhatsApp providers are registered/mounted and the `whatsapp` module exists. The former
missing-module Meta blocker is resolved; credentials, module, consent, proof, template,
cutover and provider readiness still apply. Only authenticated inbound opens the 24-hour
session window; outside it an approved event/audience/locale binding is required. Exactly
24 hours and future timestamps are outside the window.

## Compatibility callbacks, recovery and diagnostics

Retain old registered callback URLs throughout the compatibility period described in
[the rollout guide](notification-reconciliation-rollout.md). They now journal into canonical
ingress and never run the duplicate sender:

```text
/api/v1/integrations/messaging/twilio/platform/inbound
/api/v1/integrations/messaging/twilio/platform/status
/api/v1/integrations/messaging/twilio/m/{id}/inbound
/api/v1/integrations/messaging/twilio/m/{id}/status
/api/v1/integrations/messaging/whatsapp/platform
/api/v1/integrations/messaging/whatsapp/m/{id}
```

Authenticated callbacks are encrypted/deduplicated before acknowledgement. STOP/provider
opt-out protection commits even when a tenant is frozen or a channel disabled; storage failure
returns an error for provider retry. Missing exact correlation creates a sender-wide hold.
Replay uses original receipt time and exact sender/provider/tenant/generation/attempt identity.
Retired credentials verify for fourteen days, then secrets are wiped while history survives.
Both Celery beat and `run_scheduled_tasks --due-only` run receipt recovery every five minutes.
`messaging-recovery` does not restart old addressed sends. Both schedulers also run
`canonical-messaging-retention` hourly: terminal addressed legs expire after 90 days (365 when
failed) and processed receipts after 30; held, in-flight and still-correlated rows are kept.

One WhatsApp sender/phone probe may be submitted before verified BSUID/phone correlation.
Other deliveries defer without spending attempts and skip after 72 hours without confirmation.
Unmapped alias STOP blocks unknown-alias pairs across shared senders. Explicit re-consent may
reset a blocked pair. Ambiguous provider outcomes and expired addressed leases become held;
they are never blindly resent, including after probe timeout. Definitive provider rejections
may retry within four attempts. Accepted is not proof of delivery; delivered/read evidence
survives late failure callbacks.

`POST /api/v1/integrations/makerspace/{id}/channels-test` is the canonical Space Manager
caller-only diagnostic. It retains source/matrix/consent/sender/quota checks; WhatsApp needs
the caller's proved endpoint. Staff SMS diagnostics currently lack a staff-safe SMS-consent
write path because retained SMS consent admits member accounts only. Show the refusal; do
not reuse a member's consent or claim that staff can subscribe through member APIs.
Managed defaults allow 100 logical SMS and 100 WhatsApp messages per tenant/day (self-host
bypasses those quotas). Eligible diagnostics spend quota once. SMS may bill multiple segments;
local GSM-7/UCS-2 estimates cap at three and remain distinct from provider bills, including zero.
Reports read canonical delivery/history records; see [measurement notes](report-builders-messaging.md).
