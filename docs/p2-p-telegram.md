# Phase 2: personal Telegram and contract provider

Implemented in `lane/p2-p-telegram`, based on the frozen Phase 1a notification seams.
No frontend files, frozen contract files, model fields or migration catalogs changed.
Nothing is staged or committed.

## Behavior and setup

The provider registers as `(channel="telegram", provider="telegram")` during
`IntegrationsConfig.ready()`, without database access or network I/O at startup.

Configure the existing channel endpoint with `enabled`, `personal_enabled`,
`room_enabled`, a nonempty `integration_identity`, and write-only
`credentials: {"bot_token": "<token>"}`. Personal delivery requires this explicit
credential: it cannot silently switch to a changed deployment or legacy token.
The same configured token becomes the sender for the existing staff rooms.
Without a contract token, rooms retain the makerspace-token / deployment-token
fallback, existing destinations, message trimming, plain text payload and bool/error
behavior. Room provider calls delegate to `telegram.send_message`.

The frozen channel PATCH already increments `generation` on credential, provider or
identity writes and records the configuration audit. Rotate through that API.
Old endpoints immediately fail generation checks and old challenges cannot link.
Direct ORM/database credential changes are not an alternative configuration API.

Connection starts call `getMe` and cache a validated bot username by configuration,
generation and an HMAC of the credential. A short cache lock limits concurrent lookup;
successful entries have no application TTL and are looked up again after eviction.
The connect URL is `https://t.me/<username>?start=<opaque-code>`. Lookup/cache failures
become sanitized DRF validation failures; the frozen proof wrapper returns its standard
`channel` validation error. Tokens and provider response bodies are never diagnostics.

The existing webhook verifies `X-Telegram-Bot-Api-Secret-Token` in constant time
against `TELEGRAM_WEBHOOK_SECRET`, failing closed when absent or incorrect.
Only an original private `/start <code>` message with matching positive `chat.id`
and `from.id` can reach `notification_proofs.verified_callback`. The opaque challenge
resolves account, tenant and integration; the shared service locks, validates consent,
generation, ownership, expiry and single use, then encrypts/stores the endpoint and
records its audit. Group/channel/edited/forwarded messages and every callback query
are ignored. Expired/replayed proofs and closed tenant gates are acknowledged without
linking, preventing webhook retry loops. The existing webhook throttle is retained;
no browser/JWT authentication is used for the provider callback.

DM sends use only `chat_id` and trimmed `text`, with no parse mode or keyboard.
Telegram message acceptance maps to `accepted`, not delivered/read. The adapter
returns bounded `retry_after` on 429, explicit retryable outages, and ambiguous send
timeouts; the frozen delivery service owns retry budgets and scheduling. A 403 returns
`invalid_endpoint` and revokes the endpoint once, under a tenant gate and row lock,
with `notification.endpoint_revoked` audit. Personal envelopes with missing endpoints
cannot fall through to any room, including envelopes addressed to staff.

## Files changed

Production:

- `backend/apps/integrations/apps.py`: provider registration.
- `backend/apps/integrations/telegram.py`: one configured bot for rooms and DMs;
  legacy room fallback preserved.
- `backend/apps/integrations/views.py`: authenticated proof routing and OpenAPI text.
- `backend/apps/integrations/serializers.py`: webhook `message` JSON field.
- `backend/apps/integrations/notification_telegram.py`: provider, cache, live endpoint
  checks, room wrapper and audited revocation.
- `backend/apps/integrations/notification_telegram_callbacks.py`: signature/secret
  verification, strict private proof parsing and shared proof dispatch.
- `backend/apps/integrations/notification_telegram_transport.py`: bounded, sanitized
  Bot API transport and typed outcomes.
- `backend/apps/tenant_migration/gate_policy_http.py`: accurate existing-webhook gate
  declaration and anonymous participant classification.
- `docs/p2-p-telegram.md`: this handoff.

Tests (gitignored as expected; include explicitly when the integrator stages):

- `backend/tests/p2_telegram/conftest.py`
- `backend/tests/p2_telegram/test_proofs.py`
- `backend/tests/p2_telegram/test_delivery.py`
- `backend/tests/p2_telegram/test_policy.py`
- `backend/tests/p2_telegram/test_outbox.py`

## Routes / APIs

No new routes. Existing `/api/v1/integrations` routes used or extended:

| Method | Path suffix | Fields / behavior |
|---|---|---|
| POST | `/telegram/webhook` | Secret-token header; optional `update_id`, `callback_query`, `message`; private message `text`, `chat.{id,type}`, `from.{id,is_bot}` prove a link; returns the existing acknowledgement. Wrong/unset secret: 403; invalid JSON/schema: 400; throttle: 429. |
| PATCH | `/makerspace/{id}/channels/telegram` | Frozen channel fields; `credentials.bot_token`, integration identity and generation apply to this provider. |
| POST | `/makerspace/{id}/personal/endpoints/start` | Frozen `channel=telegram`, `consent=true`, `consent_version`; returns challenge ID, expiry and deep-link `connect_url`. |
| POST | `/makerspace/{id}/personal/challenges/{id}/verify` | Frozen proof/poll surface acknowledges this user's already-consumed challenge; a browser cannot supply a destination. |
| POST | `/makerspace/{id}/channels-test` | Frozen `channel=telegram` and exactly one of `endpoint_id` / `room_id`; typed provider result. |

The webhook stays outside both the default HMAC-protected API-client prefixes and
claim-reachable prefixes; adding entries there would create stale registry entries.
No URLs changed. DRF already exempts APIViews from CSRF; this callback uses only its
provider secret. The source-gate route boundary exemption remains because its tenant
is resolved from an opaque proof; mutations participate through the shared service's
`tenant_write`, and the anonymous method is now declared a participant.

## Models / migrations / registry entries

No models or migrations. The actual integrations leaf remains
`0036_notification_pii_fences`. Existing endpoint/challenge/delivery PII mappings,
export exclusions and tenant-import DROP policies apply unchanged. No new tasks,
PII mappings, export datasets, claim routes or API-client scope entries are needed.

Added provider key: `("telegram", "telegram")`. Updated source-gate declarations:
`telegram-webhook` and `apps.integrations.views.TelegramWebhookView.post`.
Audit actions reuse `notification.endpoint_challenge_started`,
`notification.endpoint_verified`, `notification.endpoint_revoked` and the frozen
channel-configuration/test actions; no audit catalog additions are required.

## Verification

All changed/new Python files, including ignored tests, passed `ast.parse` syntax
checks. `git diff --check` passed. No Docker, Django, pytest or real network calls
were run, as required by the lane brief. Runtime behavior remains for Claude to verify.

Run on the Django/Docker host:

```bash
./scripts/dev.sh test tests/p2_telegram tests/test_telegram_integration.py tests/test_telegram_failure_privacy.py tests/notifications_contract tests/test_notification_fanout.py
```

The new tests cover deep links/cache generations, private proof ownership, disabled
modules, replay/expiry/attempt limits, secret rejection, ignored callbacks/groups,
browser forgery, DM plain text/trimming, 429/403/timeouts, room compatibility,
manager defaults, API token rotation and the real provider through the shared outbox.

## Integrator requests

1. Run the tests above and source-gate/servability coverage guards on the merged tree.
   Keep the new ignored `backend/tests/p2_telegram/` files when collecting this lane.
2. Regenerate `frontend/openapi-schema.json` using spectacular `--format openapi-json`
   and then `frontend/src/generated/api.ts` on the integrated Django host. This lane
   updates the backend webhook schema only; frontend writes are forbidden here.
3. In `docs/INVARIANTS.md`, update the existing Telegram outbound-only paragraph to
   permit verified private account-link proofs while preserving the prohibition on
   decision callbacks/keyboards. In the notifications-v2 paragraph, document explicit
   contract bot credentials and generation rotation through the channel API.
4. In `docs/SOURCE-MAP.md`, add the three `notification_telegram*.py` siblings under
   integrations. Add a matching entry to `docs/PROJECT-HISTORY.md` after runtime
   verification. `MODULES`, `README`, `CLAUDE.md` and `AGENTS.md` need no lane-specific
   behavioral edits beyond any integrator-wide documentation reconciliation.
5. Deployment/setup must register the retained webhook URL with the same
   `TELEGRAM_WEBHOOK_SECRET` and allow `message` updates. An old registration that only
   requests `callback_query` updates cannot deliver private `/start` proofs.

## Contract change requests

None. All frozen signatures, fields, serializers and profile predicates are unchanged.

## Deferred

Runtime test execution, generated frontend schema/client refresh and integrator-owned
documentation edits listed above. UI work and real Telegram setup are owned outside
this implementation lane.
