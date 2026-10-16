# Phase 2 wa-meta implementation handoff

Branch: `lane/p2-wa-meta`, based on `9cc3c9cc`. All changes are new files in this worktree.
Nothing was staged or committed. Frozen contracts, frontend, shared barrels and integrator-owned
documentation were left unchanged in that lane. Phase 3 registered/mounted Meta and wired its
gate/origin declarations and environment setting. Its readiness still requires an unregistered
whatsapp module, blocking ordinary send/start/test; wiring is not an operational delivery claim.

## Files changed

New production files, all under `backend/apps/integrations/`:

- `notification_wa_meta.py`: factory registration, send, challenge and diagnostic adapters.
- `notification_wa_meta_http.py`: credential validation, fixed-host Graph transport, safe errors.
- `notification_wa_meta_templates.py`: safe-context body parameters and provider approval refresh.
- `notification_wa_meta_callbacks.py`: raw HMAC verification, installation routing and event extraction.
- `notification_wa_meta_ingress.py`: tenant-gated, audited batch application and bounded callback retries.
- `notification_wa_meta_schema.py`: webhook OpenAPI request schemas.
- `notification_wa_meta_views.py`: GET verification and POST webhook APIView, throttling and typed errors.
- `notification_wa_meta_urls.py`: URL patterns for integrator composition.
- `notification_wa_window.py`: shared 24-hour-window and authenticated event timestamp helpers.

New ignored tests in `backend/tests/p2_wa_meta/`: `conftest.py`, `test_provider.py`, `test_webhook.py`.
This document is the only documentation edit. Copy the ignored tests separately when integrating:
ordinary Git diffs/merges do not carry them.

## Routes/APIs added

Mount prefix: `/api/v1/integrations/`.

| Method | Path | Request fields | Response |
| --- | --- | --- | --- |
| GET | `makerspace/{makerspace_id}/whatsapp/meta/{generation}/{phone_number_id}/webhook` | Query: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge` | 200 `text/plain`, unmodified challenge |
| POST | Same path | `X-Hub-Signature-256`; raw JSON `object=whatsapp_business_account`, `entry[].id` (WABA), `changes[].field`, `value.messaging_product`, `value.metadata.phone_number_id`; `statuses[]`, `messages[]` or `user_preferences[]` | 200 `{accepted:true}` |

Statuses use `id`, `status`, optional `recipient_id`, `errors[].code`. Messages use `id`, `from`,
`timestamp`, `type`, `text.body` or `button.payload/text`. Preferences use `wa_id`, `value=stop`.
Errors are typed `{detail,code}` for invalid verification/payload (400/403), closed tenant writes
(423) and processing dependency failures (503); DRF supplies 404/429. GET is read-only.
The callback API uses provider authentication, with no JWT/session authentication.
The view inherits DRF's CSRF exemption, appropriate for Meta's server POST; no broader exemption is added.

The URL pins the tenant and generation. Only the configured phone ID and WABA ID in a signed body
are processed. Other tenants' entries in a shared-app batch are ignored. A body never selects a tenant.
The view checks tenant servability, rate limits at 120 requests/minute per tenant/IP, bounds raw bodies
to 256 KiB and matching batches to 200 events, and verifies HMAC before parsing webhook JSON.

Existing frozen settings/proof/preferences/test APIs remain the management surface. Set channel
`whatsapp`, provider `meta`, a nonempty `integration_identity`, and the following write-only credentials:

```json
{
  "app_id": "<Meta app ID>",
  "app_secret": "<Meta app secret>",
  "business_account_id": "<WhatsApp Business Account ID>",
  "phone_number_id": "<business phone number ID>",
  "access_token": "<permanent access token>",
  "webhook_verify_token": "<random webhook verification secret>"
}
```

Credentials use `ChannelConfiguration.set_credentials()` encryption; no second credential store is added.
Use the new generation in Meta's callback URL after every credential/identity/provider rotation.
Subscribe to `messages` and `user_preferences`. The token needs messaging and template-management read access.
The Graph host is fixed, redirects are disabled, and the default version is `v25.0` (optional Django
setting `WHATSAPP_META_GRAPH_VERSION`). Provider response text and exceptions never enter diagnostics.

## Models/migrations and registry entries

No new models, fields, migrations, module keys, export datasets, PII mappings, tenant-import dispositions,
tasks or schema-digest changes. Existing encrypted endpoint/challenge/configuration models are reused.
Provider registration is `register_provider("whatsapp", "meta", MetaWhatsAppProvider)`.
Two new audit actions require presentation entries below; existing configuration/proof/revoke actions are reused.

## Behaviour and production tradeoffs

Free text is allowed only for a verified endpoint whose last authenticated inbound event is within
24 hours. At the boundary or for future/missing timestamps, an approved binding is required. Body
parameters come only from the binding's named scalar keys in `envelope.context`; rendered private text
and caller-supplied template dictionaries cannot substitute for a binding. Template approval is read
from Meta's WABA template listing and audited, never accepted from the browser. Approval refresh follows
bounded cursors on the fixed Graph host, not upstream next URLs, and fails closed on an incomplete scan.

Use an opt-in binding `event=notification_opt_in`, `audience=member`, `locale=en`, `variables=["code"]`.
`start_challenge` refreshes approval before sending its code template. Without a candidate number,
the user instead receives instructions to message the business number with the code; that path needs
no outbound request. Only a signed matching inbound reply consumes the single-use challenge and creates
the endpoint. User-initiated proof can bootstrap linking before a diagnostic approval refresh.
For diagnostics outside the session window, bind `notification_test/member/en` with no variables.
The adapter requires notifications plus module_enabled(..., "whatsapp") for proof/send/test.
There is no registered whatsapp module key; this remains a blocking readiness limit after Phase 3.

Sent/delivered/read/terminal-failed updates use the frozen monotonic callback service. Transient error
callbacks are authenticated through `verified_callback` with state `retrying`, then a small tenant-locked
helper schedules retries within the same four-attempt budget. Duplicate callbacks cannot postpone retries,
and delivered/read never regress. This avoids the frozen terminal-failure handler prematurely creating
email fallback. Terminal errors release the existing fallback; no separate fallback implementation exists.
Send-side rate limits and 5xx are retryable; timeouts/connection ambiguity consume the frozen ambiguity
budget. Re-engagement 131047 maps to `template_required`; invalid recipient errors to `invalid_endpoint`.

The single-event callback seam is preserved by applying each signed batch item separately. `inbound`
is intentionally false in adapter events: the frozen handler substitutes receipt time when it is true.
The ingress service instead advances `last_inbound_at` monotonically using the signed provider timestamp.
Delayed/replayed callbacks therefore cannot create a fresh 24-hour window. Each actual advancement is audited.
The adapter also reloads endpoint consent/account standing and integration generation after blocking
approval lookups, so a withdrawal or credential rotation during that I/O prevents the subsequent send.

STOP/UNSUBSCRIBE/CANCEL/END/QUIT/STOPALL/OPT OUT/OPT-OUT/BLOCK revoke a known endpoint. Explicit provider
preference `stop` and error 131050 also revoke. Resume never restores consent automatically. Revocation
continues to work while delivery switches are off; proofs still require the modules and live configuration.

## Integrator requests

Phase 3 status (2026-10-17), verified in the merged code:

1. **DONE:** `IntegrationsConfig.ready()` calls `register_meta_provider()`.
2. **DONE:** `integrations/urls.py` composes `notification_wa_meta_urls.urlpatterns`.
3. **DONE:** `gate_policy_http.HTTP_ANONYMOUS_PARTICIPANTS` declares `MetaWebhookView.post`
   with the signed tenant/batch/tenant_write rationale; it is not a quiescence exemption.
4. **DONE:** `origin_scope_routes.MAKERSPACE_KWARG_ROUTES` binds whatsapp-meta-webhook to
   makerspace_id. No API-client HMAC/claim registry widening is introduced.

5. Audit presentation (done in-lane by the Claude verifier): `apps/audit/presentation_catalog_wa_meta.py`
   holds `notification.whatsapp_inbound` and `notification.whatsapp_delivery_updated`, composed by one
   import plus `_WA_META` in `presentation_catalog.py`. Keep that line when merging other lanes' fragments.
   No destination, message body, message ID, challenge code or secret is audit metadata.

6. Tell NOTIFY-UI the exact credential keys and reserved opt-in/test template binding events above.
   The frozen resolver refuses unapproved outside-window sends before invoking a provider: configure
   bindings before starting a candidate-number challenge, or use user-initiated inbound proof followed
   by a diagnostic test. Diagnostics and outbound challenges refresh all configured Meta approvals.

7. **Shared window DONE:** both providers, resolver and delivery use
   `notification_wa_window.in_session_window`; exactly 24 h and future timestamps refuse.
   Twilio timestamp parsing is unchanged; Meta retains bounded signed inbound event-time parsing.
   Both providers use notification_opt_in/notification_test member/en bindings.
   `WHATSAPP_META_GRAPH_VERSION` is environment-backed, default v25.0.

8. Regenerate the merged OpenAPI snapshot/client on the Django host; this lane adds spectacular
   annotations only and does not edit frontend artifacts. Run the tests below plus notification contract,
   audit presentation, source-gate, claim-route and API-client registry guards before integration approval.
   Update integrator-owned SOURCE-MAP/INVARIANTS/history as appropriate. Do not re-pin the portable schema
   digest for this lane: its model graph is unchanged.

## Contract change requests

None required. Batch iteration, signed inbound timestamps and retryable callback failures are handled
in lane siblings without modifying frozen signatures or fields. A future shared callback error/timestamp
extension could remove these workarounds, but it is not required for this implementation.

## Verifier fixes (Claude, 2026-10-17)

- A signed STOP/opt-out keyword is honoured even when the message timestamp is missing or skewed
  (it was previously dropped by the timestamp check, losing a consent withdrawal).
- `inbound_time` tolerates up to 300 s of provider clock skew, clamped to now, so a proof reply from a
  slightly-ahead Meta clock is not discarded; a far-future time still never opens a window.
- The webhook view refuses `makerspace_id < 1` with 403 instead of a 500 from `scope_notification_policy`.

## Validation and deferred items

Local Python AST parsing succeeded for every new Python file; production files remain below 200 lines.
Whitespace and ownership checks were performed. No Django, Docker, pytest, real Meta requests or
runtime schema generation were run in this lane, as instructed. The tests mock HTTP and deny unmocked
provider calls. They cover handshake, raw signatures, batches, tenant/generation routing, status ordering,
retry budgets, proofs, consent withdrawal, sessions, templates, safe errors and diagnostics.

Run on the test host after wiring and copying the ignored tests:

```bash
./scripts/dev.sh test tests/p2_wa_meta tests/notifications_contract
```

Real Meta app setup, business/template approval, subscription registration and credential smoke tests
remain operator work. Only phone-number endpoints and text/body-parameter templates are implemented;
BSUID-only senders and media/header/dynamic-URL template components are outside the frozen binding shape.
A dependable generic user-block payload was not established from the available provider contract.
Explicit BLOCK/stop/131050 revoke; ambiguous 131026 undeliverable errors map to invalid_endpoint rather
than inventing a block assertion. Confirm preference/error callback shapes against the configured
Meta version during operator smoke tests.

Reference shapes were checked against Meta's [template payload example](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/messages/template/)
and [raw-signature/verification reference](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/).
The developer-site pages returned throttling errors during this lane; no third-party documentation is
treated as the authority for additional webhook fields.
