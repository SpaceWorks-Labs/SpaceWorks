# Phase 2: Twilio WhatsApp lane

Historical implementation handoff. The current [personal contract](notification-contract.md),
[channel guide](messaging-channels.md) and [rollout checkpoints](notification-reconciliation-rollout.md)
supersede its old runtime/settings, ambiguity, inbox-coupling and readiness claims. SMS/WhatsApp
use canonical envelopes; duplicate addressed models/worker entry points are inert compatibility
history. Sending activation and destructive retirement remain held pending replay sign-off.

Implemented on `lane/p2-wa-twilio`, based on the frozen Phase 0+1 contract.
No models, migrations, frontend files, domain adapters or frozen contract files changed.
No Docker, Django, network integration tests, staging or commits were run in this lane.

## Behavior and setup

`IntegrationsConfig.ready()` registers `("whatsapp", "twilio")` without DB/network work.
Space Managers use the existing channel settings API. Its encrypted `credentials` map accepts:

| Field | Requirement |
| --- | --- |
| `account_sid` | `AC` plus 32 hexadecimal characters |
| `auth_token` | Account auth token, 32 hexadecimal characters; always required for webhook validation |
| `api_key_sid`, `api_key_secret` | Optional pair: `SK` plus 32 hexadecimal characters and 32 alphanumeric characters; used for REST Basic authentication instead of account/token |
| `whatsapp_sender` | E.164 number, optionally prefixed with `whatsapp:` |
| `messaging_service_sid` | `MG` plus 32 hexadecimal characters; sender or service is required, both allowed |
| `public_base_url` | Exact public HTTPS API origin, e.g. `https://api.example.org`; no path, userinfo, query or fragment |

An API key secret cannot verify Twilio webhooks: retain the account auth token even when
using API keys for REST. Credentials are validated before use, with fixed safe failures.
The frozen settings serializer accepts generic maps and cannot reject provider-specific
mistakes at PATCH time; see contract requests below. No credential is returned or logged.

Outside a verified inbound 24-hour window, `WhatsAppTemplate` must match the event,
audience and context locale (default `en`), be approved, and contain a Twilio `HX...`
Content SID in `template_name`. `variables` is the ordered list of safe envelope-context
keys, mapped to Twilio variables `1`, `2`, etc. Missing, nested, blank or oversized values
refuse with `template_required`; rendered bodies never supply template variables.
Inside the window only, bounded free-form `rendered.text` is allowed. Outbound messages
never open/extend a session. A future inbound timestamp also refuses free-form sending.
Phase 3 shares `notification_wa_window.in_session_window` with Meta, resolution and delivery;
exactly 24 hours is outside the window. Twilio timestamp parsing is unchanged.

Two reserved bindings support setup: `notification_opt_in/member/en`, with `variables=["code"]`,
and `notification_test/member/en`, with `variables=[]` (aligned with Meta in Phase 3).
Both need provider approval. Challenge codes
are sent to the encrypted E.164 candidate; only a matching signed inbound reply consumes
the challenge and creates the endpoint. The code is not returned to the browser.
Tests always use the test template, even inside a session, and require a verified,
consented endpoint for the current tenant/installation. STOP and UNSUBSCRIBE revoke
WhatsApp only, through the shared audited revocation service.

Register the generated inbound URL with the Twilio WhatsApp sender/Messaging Service.
Outbound sends provide a per-delivery status URL automatically. A service-only setup
requires the signed `MessagingServiceSid` on callbacks; configure the explicit sender
as well if the inbound webhook does not include it. Configure ingress to preserve the
request path/query. Host/forwarded-host headers do not select the signature origin.
After credentials/identity rotation, update the registered inbound URL's generation
and reconnect personal endpoints through the existing contract.

The implementation follows Twilio's [signature protocol](https://www.twilio.com/docs/usage/security),
[WhatsApp session/template rules](https://www.twilio.com/docs/whatsapp/api), and
[Content approval response](https://www.twilio.com/docs/content/create-and-send-your-first-content-api-template).
GET approval checks use `/v1/Content/{ContentSid}/ApprovalRequests` and require matching
account/SID plus `whatsapp.status=approved`; REST failures never establish approval.

## Added routes

Prefix: `/api/v1/integrations/makerspace/{makerspace_id}/whatsapp/twilio/`.
All routes have drf-spectacular request, authentication and error declarations.

| Method / suffix | Input / response |
| --- | --- |
| POST `{generation}/inbound` | Twilio form, `X-Twilio-Signature`; `AccountSid`, `MessageSid`, `From`, `To`, optional `Body`, `MessagingServiceSid`; empty `<Response/>` TwiML |
| POST `{generation}/status/{delivery_id}` | Same signed form identifiers plus `MessageStatus` (or `SmsStatus`); empty TwiML |
| POST `templates/refresh` | JWT Space Manager; optional `content_sids: ["HX..."]`, 1–5; response `{checked, approved, unavailable}` |

Approval refresh with an empty body checks all bindings if there are at most five unique
valid Content SIDs; larger sets require explicit batches. Repeated bindings sharing a SID
make one HTTP request. This bounds a request to five 10-second provider calls. Unverified,
rejected or unavailable approvals are disabled. The integration generation is checked
again when committing, so a credential rotation cannot approve the next installation.

All callback fields, including unknown future Twilio fields, participate in HMAC-SHA1.
Comparison is constant-time. Only form POSTs are accepted; body/field sizes are bounded.
Sensitive duplicate fields are refused. Signature validation precedes proof/status use,
then account, business sender, tenant, generation and destination correlation are checked.
The signature-only APIView has no session authentication; DRF supplies its CSRF exemption.
Callbacks are throttled per tenant/IP; approval refresh is limited to five/hour/user.

Delivery mapping: queued→accepted, sent→sent, delivered→delivered, read→read,
failed/undelivered→failed. The shared monotonic handler refuses regressions, foreign
installations and provider-ID replacement. A failure arriving before the REST response
first acknowledges acceptance through that same handler, then applies failure. Callback
proof/consent/window changes hold the tenant gate, PII fence and configuration lock;
failed proof attempt counts commit before returning a validation error.

Inbound MessageSid retries use a 24-hour hashed cache reservation to avoid repeatedly
extending the service window. This is bounded retry suppression, not a permanent replay
ledger; cache loss/expiry loses the marker. No durable inbound-message store was added.

429, provider rate limits, 5xx and network failures return fixed retryable errors.
Timeouts and dropped connections after a POST are marked ambiguous. Retry-After is bounded
to one hour. The shared worker owns retry budgets/fallback. Twilio Message creation has
no supported idempotency parameter here; ambiguous retries can duplicate an outbound
message. HTTP redirects are refused to prevent forwarding Basic credentials.

## Files changed

New production modules:

- `backend/apps/integrations/notification_wa_twilio.py`: provider, challenges, tests, registration.
- `notification_wa_twilio_config.py`: credentials, E.164/SID validation, canonical callback URLs.
- `notification_wa_twilio_http.py`: bounded REST calls, redaction and error mapping.
- `notification_wa_twilio_templates.py`: approved bindings, safe variables, approval refresh.
- `notification_wa_twilio_callbacks.py`: signatures, account/business correlation, callback events.
- `notification_wa_twilio_views.py`: signature ingress, locking/audit, replay throttle, approval API.
- `notification_wa_twilio_urls.py`: three routes.
- `backend/apps/audit/presentation_catalog_p2_wa_twilio.py`: three safe audit presentations.
- `backend/apps/tenant_migration/gate_policy_p2_wa_twilio.py`: anonymous source-gate participant.

Small composition edits: `integrations/apps.py`, `integrations/urls.py`,
`audit/presentation_catalog.py`, `tenant_migration/gate_policy_http.py`.
This document is the only lane-owned documentation addition.

Tests (gitignored as expected): `backend/tests/p2_wa_twilio/{__init__,conftest,test_send,
test_callbacks,test_transport_config,test_approvals_guards}.py`.
They mock the HTTP opener throughout; no test may contact Twilio.

## Models / migrations / registries

No new models/fields/migrations, data-export datasets, encryption registrations, import
dispositions, purge entries or tasks. Existing encrypted ChannelConfiguration, scoped-PII
endpoints/challenges, templates and deliveries carry all state. The tenant catalog digest
was not touched.

Registry additions: provider `whatsapp/twilio`; source-gate anonymous participant
`apps.integrations.notification_wa_twilio_views.TwilioWhatsAppWebhookView.post`;
audit actions `notification.whatsapp_callback_applied` (kind/state) and
`notification.whatsapp_templates_refreshed` (changed/unavailable), plus
`notification.whatsapp_proof_rejected` (no public metadata).

All routes carry `makerspace_id`, already recognized by the origin/source-gate resolver.
They are outside API-client HMAC and claim-reachable prefixes. API-client scope lookup
therefore stays absent/denied and claim policy stays Refused; adding entries would create
stale-registry failures. Tests pin those classifications and tenant target resolution.
No authentication or source-gate exemptions were added.

## Integrator requests

1. Apply/retain the four small composition edits listed above when merging. No integrator-owned
   documentation, frontend, model barrel or migration was edited in this lane.
2. Regenerate the OpenAPI snapshot on the Django host using spectacular `--format openapi-json`,
   then regenerate the frontend client. Include the three routes above; lane rules forbid
   editing `frontend/openapi-schema.json` and `frontend/src/generated/api.ts` here.
3. Document the provider setup/rotation and reserved opt-in/test template bindings in
   `docs/INVARIANTS.md` (notifications), `docs/SOURCE-MAP.md` (integration modules), and
   `docs/PROJECT-HISTORY.md` as appropriate. No module key or README change is required.
4. Run `./scripts/dev.sh test tests/p2_wa_twilio tests/notifications_contract` plus the existing
   audit-presentation, route/scope/claim, source-gate and separability drift guards. Preserve
   this gitignored test directory in the merge/test handoff. Full review/QA gates belong
   to Claude's orchestration lane; this lane ran syntax/whitespace checks only.

## Contract change requests

- Add an optional provider credential-validation hook invoked by frozen
  `notification_api_channels.ChannelSettingsView.patch` before storing credentials,
  using `notification_wa_twilio_config.validate_credentials`. Existing behavior remains
  fail-closed before use; PATCH currently cannot report provider-specific field mistakes.
- Allow `notification_delivery.apply_callback` to apply a signed terminal failure directly
  from `retrying`. Its current accepted/sent-only branch misses callback-before-REST-response
  failures. This lane's acceptance-then-failure bridge makes it work without changing the contract.

No contract signature/field change is required for last inbound time, proof, STOP,
template variables, delivery correlation or encrypted credentials.

## Deferred / validation

Runtime Django/pytest, provider-account setup and approved real templates require the
integration environment. No real Twilio messages were sent. Python AST parsing and
`git diff --check` passed; production modules remain below 300 lines. Nothing staged
or committed. Durable replay storage and upstream message idempotency are not introduced.
