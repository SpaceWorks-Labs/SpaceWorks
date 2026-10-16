# Notifications v2 personal delivery contract

The personal contract lives in `integrations/notification_*`, `models_contract.py`,
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
WhatsApp has no staff rooms or registered module key. Telegram rooms prefer the contract bot token;
other existing room transports retain their destination credentials;
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

## Provider connection and deployment

- **Telegram:** encrypted `credentials.bot_token` and a nonempty installation identity are required
  for personal delivery. Start returns `https://t.me/<bot>?start=<opaque-code>`; only an original
  private human `/start` with equal positive chat/from IDs and the secret-token header proves it.
  `TELEGRAM_WEBHOOK_SECRET` is environment-backed and must match `setWebhook.secret_token`;
  `allowed_updates` must include `message`. Every `callback_query` is acknowledged and ignored,
  and no send has a keyboard. Rooms use the configured contract token, then legacy tenant/platform
  fallback. Personal sends cannot fall through to rooms. Bot acceptance is `accepted`, not delivered.
- **Slack / Mattermost / Discord:** provider OAuth proves identity; Slack binds workspace OIDC,
  Mattermost binds configured-server `/users/me`, Discord uses identify. The authenticated
  `/personal/challenges/{id}/verify` consumes code/state for the current account; the UI handles
  `?notify_challenge=<id>&code=...&state=...`. Slack installation uses S256 PKCE (enable it on the
  provider app); installation is distinct from personal OIDC. No submitted user/chat ID is proof.
  Signed inbound chat hooks acknowledge only, with no decisions or destination assignment.
- **WhatsApp:** Twilio signed inbound/status routes are mounted and its provider is registered.
  A candidate E.164 number is not proof: a signed matching inbound opt-in code establishes consent.
  STOP revokes. Only authenticated inbound starts the 24 h free-text window; otherwise an approved
  event/audience/locale template binding is required. Twilio uses Content SIDs with reserved
  `opt_in` and `test` member/en bindings; Meta source uses `notification_opt_in` and
  `notification_test` member/en bindings. SMS-login consent grants no WhatsApp consent.
  Browser PATCH cannot self-approve templates; provider refresh owns approval. Status callbacks
  correlate installation/message and advance monotonically. Ambiguous retries may duplicate sends.

Provider setting lookups are deployment-wide, never derived from the request host:

| Django setting | Adapter behaviour |
| --- | --- |
| `NOTIFICATION_SLACK_REDIRECT_URI` | HTTPS required; blank refuses; optional `{makerspace_id}` substitution |
| `NOTIFICATION_MATTERMOST_REDIRECT_URI` | Same server-selected redirect policy |
| `NOTIFICATION_DISCORD_REDIRECT_URI` | Same server-selected redirect policy |
| `NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS` | Defaults false; only boolean true allows private self-host addresses |
| `WHATSAPP_META_GRAPH_VERSION` | Defaults `v25.0` in the Meta HTTP adapter |

These five names are `getattr(settings, ...)` lookups only in this tree. They are **not loaded
from environment variables by `config/settings.py`**. Setting them in dotenv alone does not
configure OAuth/private Mattermost/Meta. `TELEGRAM_WEBHOOK_SECRET` has its existing env loader.

## Domain delivery ownership

Events and Bookings now use source-backed personal envelopes for lifecycle, reminders and campaigns.
Event delegates use `events.grant_staff`; booking delegates use `bookings.grant_alert`, both audience
`member` with live resource authority. Event staff envelopes pre-skip in-app/native push because the
legacy matrix still owns those legs. Event campaigns pre-skip email because the campaign worker owns
it; the extra channel task has no periodic lost-task resume. Booking campaigns with a saved category
selection use envelopes and skip batch email; others keep the existing batch-email path.
Account-addressed staff and booking email requires `email_verified_at`; account-less booking guests
retain contact email. Requester booking notifications default on, with audit-aware backfill of only
untouched false tenant settings; per-resource overrides still win.

Hardware/machine/watch/certification and membership/payment/device/operations adapters register live
sources. Equipment room delivery now consults `notifications_p2_rooms.eligible_room` before timing/
provider delivery. Loan financial owner notices belong to the Payment adapter; hardware charge
summaries are staff-only, avoiding a second owner charge notice. Existing authentication mail stays
synchronous/redacted email; custody and mandatory reminders retain their independent policy.
The [coverage inventory](notification-coverage.md) records which producers actually call the adapters.

## Integration limits in this tree

Verified against `6d083b29` code; these are implementation limits, not completed lane requests:

- `accounts/authentication.py` admits member prefixes and push routes, but not the six personal
  notification route shapes. The member Channels UI exists; MEMBER JWT calls are refused before
  the personal view. Staff access still uses the view's account/tenant policy.
- `ChatOAuthCallbackView` still allows anonymous GET/POST completion. Authenticated verification
  exists, but it is not the only completion path; the requested authenticated-only OAuth return
  flow and the deployment setting loaders above are absent.
- Meta files exist, but `IntegrationsConfig.ready` does not register their factory and
  `integrations/urls.py` does not mount their webhook URL list. `_ready` additionally requires
  an unregistered `whatsapp` module. `provider=meta` is accepted as configuration, not operational
  delivery. Do not describe both WhatsApp providers as wired.
- Maintenance and procurement entry points still call legacy dispatch; their new machine adapters
  are not delegated from those barrels. Member broadcasts still call `notify_lifecycle`, not
  `notifications_p2_broadcasts.notify_broadcast`.
- `notification_resolution` retains category `printing`→module `printing` for generic machine jobs,
  and `stock`→`procurement` for stocktake. Their requested source-specific module overrides are
  absent. A producer being wired does not guarantee delivery in a machine-service-only or
  stocktake-without-procurement install.
- Equipment email policy/proven-address/render helpers exist but are not called by the shared
  resolver/builtin mail transport. The resolver requires verified account email and does not
  implement those legacy email-only exceptions. `source_ready` conservatively refuses affected
  owner intents when an email mute would otherwise leak through; selected chat can be suppressed too.
- Presence expiry is catalogued with default in-app/push, but `NotificationFeature` omits presence
  from the personal editor. Stocktake/first-email-failure legacy inbox mirrors remain alongside
  envelope delivery. Room live-source enforcement covers equipment; other converted room summaries
  retain legacy retry semantics. Scheduled-report legacy status is not provider acknowledgement.
  `notification_catalog.py` omits several literal adapter events (membership joined/verified/
  invitation/vouched, document_issued, problem reports, subdomain/report/email-failure and stocktake),
  so those event/template editors are incomplete.

The historical lane notes under `docs/p2-*.md` retain integration/test requests. No runtime test
result is asserted by this documentation pass. Model/API/provider ownership is indexed in
[SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md); run changed-code tests and their registry
checks through the isolated runner in the final integration pass.
