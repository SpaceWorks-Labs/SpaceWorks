# Phase 2 p-chat implementation report

Worktree: `p2-p-chat`, branch `lane/p2-p-chat`. Nothing staged, committed, merged or pushed.
No Docker, Django, pytest or real-provider requests were run in this lane. The tests below
are written for Claude's isolated runner. Python AST parsing and `git diff --check` pass.

## Behavior and production choices

Slack, Mattermost and Discord register through `register_provider` at application startup.
Each implements the frozen `send`, `verify_callback`, `test` and `start_challenge` seams.
Each also exposes `send_room(text, destination=None)`, wrapping the existing `send_webhook`
transport, including its legacy makerspace URL fallback, trimming and DNS protection.
The existing room dispatcher and its staff audience/scoping logic were left intact.
Personal delivery never falls back to a room.

Personal OAuth uses the existing durable `NotificationEndpointChallenge`. Signed state
identifies the challenge; the row binds the account, tenant, installation identity,
generation, expiry, consent and secret-code digest. State stays below the frozen
512-character verification limit. Successful proof enters `verified_callback` and the
existing transactional `consume` service, which creates the verified endpoint exactly
once. Browser-submitted user/chat IDs are never proof. OAuth user tokens stay in memory.
The server selects every redirect URI from settings, including optional substitution
of persisted makerspace/challenge IDs and appended notify_challenge; request hosts/origins cannot select it.

Slack installation uses a separately purposed challenge, consumed under a configuration
row lock before token exchange. The live Space Manager authorization is checked again
on completion. Slack OAuth v2 installation uses S256 PKCE (enable PKCE on the Slack app).
Its PKCE exchange omits `client_secret`, as required by Slack. Team ID and bot token live
in encrypted credentials; the exposed installation identity is `slack:<SHA256(team_id)>`.
Personal linking uses Sign in with Slack, validates the RS256 ID token against Slack's
fixed JWKS endpoint, issuer, audience, expiry and nonce, then matches userInfo subject,
team and user to the ID token and installed team. DM delivery verifies the bot team with
`auth.test`, opens an IM, and posts the message. Slack OIDC uses confidential-client
authentication and nonce; Slack's documented PKCE flow applies to the separate OAuth v2
installation endpoint.

Mattermost registration validates an HTTPS server origin and bot identity. Authorization
and token exchange use S256 PKCE. Identity comes from that server's `/api/v4/users/me`;
deleted accounts and bots are refused as personal identities. Every credentialed call
re-resolves the server and connects to the validated IP while retaining TLS hostname
verification. Mixed public/private DNS answers and redirects are refused. The default
blocks private, loopback, link-local, reserved and non-global addresses. Only an explicit
server setting enables private self-host addresses. DM delivery checks live bot and
recipient accounts, creates the direct channel, and posts to it.

Discord registration verifies the bot's application ID, public key and access to the
configured guild before saving. Its installation identity is `<application_id>:<guild_id>`.
OAuth uses `identify` with confidential-client code exchange; `/users/@me` supplies the
proven user ID. Discord's documented confidential-client OAuth flow does not advertise
PKCE, so this adapter does not claim to use it. DM delivery opens the private channel
then posts with mentions disabled and a stable nonce.

Installation/credential changes advance the existing configuration generation. Adapters
reload configuration and endpoint standing before sending and refuse stale generations.
Slack and Discord use upstream deduplication IDs; Mattermost carries a stable
`pending_post_id` but its API does not promise exactly-once delivery. Timeouts explicitly
report ambiguity; the frozen dispatcher retains its bounded ambiguity/retry policy.
429 responses return bounded Retry-After metadata; revoked/deleted/blocked destinations
map to `invalid_endpoint`; 5xx responses are retryable. Raw response errors, bodies,
tokens and personal IDs never enter adapter logs or persisted error messages.

Slack inbound verifies v0 HMAC over timestamp and raw body with constant-time comparison
and five-minute skew. Discord verifies Ed25519 over timestamp and raw body with the same
skew **before parsing**. Mattermost outgoing/slash tokens use constant-time comparison.
Inbound routes acknowledge only: they cannot make workflow decisions, create endpoints
from typed IDs, or change delivery state. Discord ping and Slack URL verification work.
Callbacks are throttled. Legacy OAuth callback URLs require authentication and accept GET/form POST
only for Slack installation; personal completion uses authenticated POST challenge verification.
HEAD is refused so link previews cannot consume a proof. Successful OAuth responses disable caching/referrers.

## Files changed

New provider and route modules:

```text
backend/apps/integrations/notification_slack.py
backend/apps/integrations/notification_slack_http.py
backend/apps/integrations/notification_slack_installation.py
backend/apps/integrations/notification_slack_oauth.py
backend/apps/integrations/notification_slack_views.py
backend/apps/integrations/notification_slack_urls.py
backend/apps/integrations/notification_mattermost.py
backend/apps/integrations/notification_mattermost_http.py
backend/apps/integrations/notification_mattermost_urls.py
backend/apps/integrations/notification_discord.py
backend/apps/integrations/notification_discord_urls.py
```

Startup, mounts and additive registry composition:

```text
backend/apps/integrations/apps.py
backend/apps/integrations/urls.py
backend/apps/tenant_migration/gate_policy_p2_p_chat.py
backend/apps/tenant_migration/gate_policy_http.py
backend/apps/audit/presentation_catalog_p2_p_chat.py
backend/apps/audit/presentation_catalog.py
docs/p2-p-chat.md
```

Gitignored tests (must be preserved when handing this worktree to Claude):

```text
backend/tests/p2_chat/conftest.py
backend/tests/p2_chat/test_signatures.py
backend/tests/p2_chat/test_delivery.py
backend/tests/p2_chat/test_oauth.py
backend/tests/p2_chat/test_transport.py
backend/tests/p2_chat/test_routes.py
backend/tests/p2_chat/test_installation.py
```

## Routes / APIs added

Prefix: `/api/v1/integrations/makerspace/{makerspace_id}`. No trailing slash.
Every concrete route has drf-spectacular request/response/error annotations.

| Method | Suffix | Fields / authentication | Success |
| --- | --- | --- | --- |
| POST | `/slack/install/start` | No body; JWT, scoped Space Manager; existing Slack channel configuration must contain client_id/client_secret/signing_secret | 201 `{connect_url, expires_at}` |
| POST | `/mattermost/installation` | JWT, scoped Space Manager; `{server_url, bot_token, client_id, client_secret, webhook_token}`; complete replacement | 200 `{channel, generation, configured}` |
| POST | `/discord/installation` | JWT, scoped Space Manager; `{bot_token, application_id, public_key, guild_id, client_secret}`; complete replacement | 200 `{channel, generation, configured}` |
| GET, POST | `/slack/oauth/callback` | `{code, state}` in query or form; single-use signed state plus provider code proof; authenticated actor-bound Slack installation only; personal linking is refused | 200 `{verified:true}` |
| GET, POST | `/mattermost/oauth/callback` | `{code, state}`; authenticated legacy callback refuses personal completion; use POST personal/challenges/{id}/verify | 400 validation |
| GET, POST | `/discord/oauth/callback` | `{code, state}`; authenticated legacy callback refuses personal completion; use POST personal/challenges/{id}/verify | 400 validation |
| POST | `/slack/inbound` | Raw JSON/form body; X-Slack-Request-Timestamp + X-Slack-Signature | 200 `{ok:true}` or `{challenge}` |
| POST | `/mattermost/inbound` | JSON/form body containing configured token | 200 `{ok:true}` |
| POST | `/discord/inbound` | Raw JSON; X-Signature-Ed25519 + X-Signature-Timestamp | 200 Discord interaction acknowledgement |

Installation routes require modules `notifications` plus the channel and an existing
ChannelConfiguration. Create that row first through the frozen channel PATCH route with
personal delivery disabled, install the app, then enable personal delivery. Slack app
credentials are written through that frozen route. Mattermost/Discord use the validated
installation routes above. Frozen personal start/verify, preference, endpoint revoke,
delivery metadata and channel-test routes are reused without edits.

## Models / migrations

None. The actual integrations migration leaf remains `0036_notification_pii_fences`.
The frozen credential, endpoint and challenge graph supplies encryption, import DROP,
purge ordering and excluded export/User-edge classification. No field, signature,
schema digest, public-profile predicate or frontend file was changed.

## Registry entries and route guards

- Provider factories: `(slack, slack)`, `(mattermost, mattermost)`, `(discord, discord)`.
- Audit presentation: `notification.chat_install_started` and
  `notification.chat_install_state_consumed`, exposing only `channel`. Existing
  `notification.channel_configured` and endpoint audit actions remain in use.
- Source-gate anonymous participant: `notification_slack_views.ChatInboundView.post` only.
  Phase 3 removed the obsolete anonymous OAuth participant; callback completion is authenticated.
  There is no quiescence exemption. Installation/endpoint writes acquire `tenant_write`.
- Every route carries `makerspace_id`, so the existing authoritative origin/tenant target
  resolver handles it directly. Queries use the existing RBAC notification-policy scope.
- These integrations paths are **outside** the configured/default mandatory HMAC prefixes
  and `CLAIM_REACHABLE_PREFIXES`; adding API-client/claim registry entries would create
  stale entries under their guards. Tests assert the exclusion. JWT manager routes use
  ordinary session/RBAC authorization; public provider routes verify provider proofs.
- APIView supplies the existing DRF CSRF treatment for provider form callbacks; no new
  broad middleware bypass or manual csrf_exempt was introduced.

## Integrator requests

1. **DONE in Phase 3:** `config/settings.py` loads the three
   `NOTIFICATION_{SLACK,MATTERMOST,DISCORD}_REDIRECT_URI` values (blank default) and
   `NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS` (boolean false default) from the environment;
   deployment manifests forward them and backup classifies them as nonblocking value comparisons.
   Personal redirect URLs name the HTTPS frontend notification-settings page, optionally expand
   `{makerspace_id}` / `{challenge_id}` and append `notify_challenge=<id>`. Register the resulting
   return URI in the provider console; authorization and exchange use the identical URI. The UI
   receives `?notify_challenge=<id>&code=...&state=...` and calls authenticated personal verify.
   Blank/malformed/non-HTTPS settings refuse linking.

2. **DONE in Phase 3:** `accounts/authentication.py` full-matches six numeric-ID personal
   route shapes (optional final slash): endpoints, endpoints/start, endpoints/{id},
   challenges/{id}/verify, preferences and deliveries. No broad integrations exemption;
   channel settings/tests/installations remain outside member reach. Personal code/state
   completion requires the authenticated account and URL challenge to match signed state
   before provider I/O; configuration/challenge locks serialize single-use completion.
   Anonymous completion is gone. The callback class retains authenticated Slack installation only.

3. Regenerate OpenAPI with spectacular `--format openapi-json` and the frontend client
   on the merged Django graph. Frontend UI must call installation routes as documented,
   then the frozen personal challenge start route, and show an OAuth completion state.
   No provider destination ID input should be exposed.

4. Update integrator-owned `docs/INVARIANTS.md` / `docs/SOURCE-MAP.md` /
   `docs/PROJECT-HISTORY.md` with these provider seams, single-use/generation rules,
   encrypted Slack workspace identity, and default-off Mattermost private-host setting.
   No module key changed, so `docs/MODULES.md` needs no new registry entry.

5. Claude should run `./scripts/dev.sh test tests/p2_chat tests/notifications_contract`
   and the source-gate, audit-presentation, module/tombstone and schema guards against
   the merged graph. Test files are gitignored and have not been staged.

## Contract change requests

None. The member-session fix above changes authentication routing outside the frozen
contract; no provider/model/API signature or field change is needed. Provider-specific
installation validation is additive because the frozen generic credential PATCH has
no provider validation hook; adapters still validate installation identity/server safety
at use time. The integrator may later centralize that hook without changing field shapes.

## Deferred

Phase 3 resolves member admission, authenticated completion and frontend return handling; the
original lane validation above remains historical, with no new runtime pass claimed here.

Django/pytest, integrated schema generation, the final module-variation matrix and real provider
credential smoke tests belong to integration/Claude. Slack token-rotation-enabled apps
need token renewal before token expiry; this lane installs non-expiring server bot tokens
and refuses expired/revoked tokens rather than silently changing installation generation.

Provider references used to check protocol behavior:
[Slack Sign in](https://docs.slack.dev/authentication/sign-in-with-slack/),
[Slack PKCE](https://docs.slack.dev/authentication/using-pkce/),
[Slack request signing](https://docs.slack.dev/authentication/verifying-requests-from-slack/),
[Mattermost OAuth](https://docs.mattermost.com/developers/integrate/apps/authentication/oauth2),
[Discord OAuth](https://docs.discord.com/developers/topics/oauth2),
[Discord interactions](https://github.com/discord/discord-api-docs/blob/main/developers/interactions/overview.mdx).
