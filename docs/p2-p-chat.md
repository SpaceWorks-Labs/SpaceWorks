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
of the configuration's persisted makerspace ID; request hosts/origins cannot select it.

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
Callbacks are throttled. OAuth callbacks accept GET and form POST; HEAD is refused so
link previews cannot consume a proof. Successful OAuth responses disable caching/referrers.

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
| GET, POST | `/slack/oauth/callback` | `{code, state}` in query or form; single-use signed state plus provider code proof; handles installation and personal linking | 200 `{verified:true}` |
| GET, POST | `/mattermost/oauth/callback` | `{code, state}`; signed state plus configured-server OAuth proof | 200 `{verified:true}` |
| GET, POST | `/discord/oauth/callback` | `{code, state}`; signed state plus Discord identify proof | 200 `{verified:true}` |
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
- Source-gate anonymous participants: `notification_slack_views.ChatOAuthCallbackView.post`
  and `notification_slack_views.ChatInboundView.post`. There is no quiescence exemption.
  Installation/endpoint writes acquire `tenant_write`; GET callbacks use those same services.
- Every route carries `makerspace_id`, so the existing authoritative origin/tenant target
  resolver handles it directly. Queries use the existing RBAC notification-policy scope.
- These integrations paths are **outside** the configured/default mandatory HMAC prefixes
  and `CLAIM_REACHABLE_PREFIXES`; adding API-client/claim registry entries would create
  stale entries under their guards. Tests assert the exclusion. JWT manager routes use
  ordinary session/RBAC authorization; public provider routes verify provider proofs.
- APIView supplies the existing DRF CSRF treatment for provider form callbacks; no new
  broad middleware bypass or manual csrf_exempt was introduced.

## Integrator requests

1. Wire four settings into `backend/config/settings.py` and the deployment environment
   documentation/settings surface (these are intentionally outside this lane):

   ```python
   NOTIFICATION_SLACK_REDIRECT_URI = env("NOTIFICATION_SLACK_REDIRECT_URI", default="")
   NOTIFICATION_MATTERMOST_REDIRECT_URI = env("NOTIFICATION_MATTERMOST_REDIRECT_URI", default="")
   NOTIFICATION_DISCORD_REDIRECT_URI = env("NOTIFICATION_DISCORD_REDIRECT_URI", default="")
   NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS = env.bool("NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS", default=False)
   ```

   Redirect examples:
   `https://api.example/api/v1/integrations/makerspace/{makerspace_id}/slack/oauth/callback`
   and corresponding `mattermost` / `discord` URLs. The placeholder is expanded from the
   persisted configuration, never request URL data. Register each concrete tenant URL in
   its app's provider console. Blank/malformed/non-HTTPS settings refuse linking.

2. Fix the Phase-1 member-session reachability gap in `accounts/authentication.py`.
   `_member_surface_path_allowed` currently permits claim prefixes and integrations/push only;
   the frozen `/integrations/makerspace/{id}/personal/...` APIs therefore reject ordinary
   member JWTs before their explicit-owner/RBAC checks. Add an exact path predicate for
   positive makerspace IDs and these frozen personal routes only: `endpoints` (list),
   `endpoints/start`, `endpoints/{positive_id}` (revoke),
   `challenges/{positive_id}/verify`, `preferences`, `deliveries`. Keep channel settings,
   test send and installations outside that member surface. Extend real-token session
   surface tests; do not use a broad `/integrations/` exemption. This is independent of
   all three provider implementations and affects every personal-channel lane.

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

Django/pytest, integrated schema generation, live-token member authentication regression
tests, the final module-variation matrix, frontend setup/linking UX and real provider
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
