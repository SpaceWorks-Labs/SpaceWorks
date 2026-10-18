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

Delivery states include retrying, accepted, sent, delivered, read, failed, skipped and held.
Converted canceled queues are inert history (canonical parent state skipped with canceled disposition).
Acceptance is not proof of delivery. Claims release database locks before provider I/O.
Retries have exponential delay/jitter, bounded Retry-After, and four attempts maximum;
ambiguous SMS/WhatsApp outcomes and expired addressed leases are held without blind retry.
Push children also hold uncertain outcomes; other transports retain their bounded ambiguity policy.
Callbacks cannot regress successful acknowledgements or
cross an installation generation. Provider response text is never persisted as an error.

## Frozen HTTP surface

All paths below have prefix `/api/v1/integrations/makerspace/{makerspace_id}`.
JWT authentication and tenant-origin enforcement apply. Channel settings and test sends
require Space Manager identity (including authorized global superadmins). Personal actions
only affect the authenticated person's endpoints/preferences. Other managers and members
cannot configure channels. They see their own delivery metadata; a Space Manager can see
the tenant's metadata. No response contains credentials, destinations or message bodies.

`accounts/authentication.py` full-matches exactly six personal route shapes for member JWTs:
endpoints, endpoints/start, endpoints/{id}, challenges/{id}/verify, preferences and deliveries.
Tenant/challenge/endpoint IDs are numeric, with an optional final slash. This is not a broad
integrations-prefix grant: channel configuration, tests and installation routes remain outside it.
The views still enforce tenant/account standing and ownership.

| Method | Suffix | Request | Response |
|---|---|---|---|
| GET | `/channels?page=` | â€” | Page<Channel> |
| GET | `/channels/{channel}` | â€” | Channel |
| PATCH | `/channels/{channel}` | Any ChannelWrite fields | Channel |
| GET | `/personal/endpoints?page=` | â€” | Page<Endpoint> |
| POST | `/personal/endpoints/start` | channel, consent=true, consent_version, optional phone_number (WhatsApp candidate only) | challenge_id, expires_at, optional connect_url/instructions/oauth_state |
| POST | `/personal/challenges/{challenge_id}/verify` | Optional opaque provider code/state; provider verifies independently | Endpoint |
| DELETE | `/personal/endpoints/{id}` | â€” | revoked=true |
| GET | `/personal/preferences` | â€” | preferences: Selection[] |
| PUT | `/personal/preferences` | preferences: Selection[] (replace supplied categories) | preferences: Selection[] |
| GET | `/personal/deliveries?page=` | â€” | count, next, previous, results: Delivery[] |
| POST | `/channels-test` | channel; SMS omits target IDs, WhatsApp needs own endpoint_id; other channels choose endpoint_id or room_id; optional feature/event | accepted, provider_id, retryable, error_code, sanitized_error |

ChannelWrite = enabled, room_enabled, personal_enabled, email_fallback, provider,
integration_identity, credentials (write-only map), quotas, templates, use_platform_sender and
activation_hold. Imported sender conflicts require review before clearing activation_hold. Channel returns
channel, enabled, room_enabled, personal_enabled, email_fallback, provider,
integration_identity, generation, credentials_set, quotas, templates, use_platform_sender,
sender_key, credential_version, activation_hold and read-only callback_urls.
The callback map derives from saved configuration: SMS returns `inbound_url` and `status_url`
for the own or explicitly enabled platform sender; Twilio WhatsApp returns `inbound_url` and
`status_url_template` with `{delivery_id}` filled automatically per send; Meta WhatsApp returns
`webhook_url` bound to the current tenant, generation and phone-number ID. Incomplete setups
return an empty map. URLs contain no credentials; provider signatures remain required.
WhatsApp providers are exactly `twilio|meta`. Credentials/identity/provider updates advance
the generation; old consent never becomes valid for a new installation. Channel module removal also invalidates installation authority; a module reinstall never
restores old consent. The optional inbox is independent of core SMS/WhatsApp delivery. Quotas accept
daily_limit and recipient_daily_limit. Template bindings contain feature, event, audience, locale,
template_name, variables and needs_review; approved and needs_review are read-only and must be established by a provider.
SMS and WhatsApp have separate default-off module keys and no staff rooms. SMS uses Twilio;
WhatsApp supports Twilio or Meta. The former Meta missing-module readiness blocker is resolved. Telegram rooms prefer the contract bot token;
other existing room transports retain their destination credentials;
the new room enable switch gates them without changing their audience.

Endpoint = id, channel, provider, integration_generation, verification_state,
verified_at, consented_at, consent_version, revoked_at, created_at, effective_valid.
The read-only effective_valid includes the current configuration generation, provider/identity,
verification, consent, revocation and personal-delivery switches. Invalidated endpoints are
disconnected in both the connection list and channel choices.
Endpoints GET accepts optional `oauth_state`; its optional `oauth_return` contains the authenticated
account's live signed-state-bound challenge_id and expires_at. It performs no token exchange.
Selection = category, channels[] and email_fallback, plus read-only available_channels[]
in responses. The tenant's enabled choices are exposed to personal clients; selecting
a disabled channel is rejected. Duplicate categories/channels and
unknown fields are rejected. Legacy email unsubscribes still defeat optional email fallback.
PUT replaces each supplied category's selection, including an explicit empty channels list.
Categories absent from the request keep their existing rows; if no row exists, they keep
resolving product defaults. Clients submit only edited, available categories, so saving
another category never turns a disabled module into a durable opt-out.
Manager defaults are Telegram when personal Telegram is enabled and verified; otherwise
email. Members default email plus in-app. Current explicitly consented addressed channels may
join these defaults; consent never bypasses matrix/module/standing gates. Availability gates still apply.
Presence defaults to in-app/native push with no email fallback for every audience, before
any expiry or preference write. Explicit personal selections still win.
Delivery = id, envelope_id, channel, state, attempt_count, next_attempt_at, last_error,
retryable, event, feature, created_at, updated_at. Held outcomes need evidence/reconciliation;
clients must not offer a resend that could duplicate an uncertain send. All list endpoints use the standard
page size 24 and return count, next, previous and results.

Errors document 400 validation (field errors or detail/code), 401, 403 and 404; retired
duplicate settings/template writes return 503 before canonical routing, then 410. Mutations
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

`CallbackEvent` carries provider_id/state, optional signed delivery_id/delivery_attempt correlation,
optional provider_timestamp (never substituted with processing time),
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
pattern. Canonical envelopes, endpoints, configuration, ingress, credential history and legacy mappings
have explicit export/tenant-migration/privacy classifications. Imported credentials, endpoints,
consent and live delivery rules cannot grant target authority. Account cleanup uses account IDs,
not shared contacts. Channel/tenant purge preserves retired verification and global physical
STOP/alias/provider-reference protection; optional inbox purge retains push children through
their canonical parent. See the catalog/source map for model-specific dispositions.

## Provider connection and deployment

Settings PATCH validates replacement credentials against the provider contract and returns
`400 {detail, code: "invalid_credentials"}` for incomplete credentials or mismatched identities.
Slack accepts app-only `client_id`, `client_secret`, `signing_secret` as an installation bootstrap
with personal delivery off. The manager starts `/slack/install/start` and completes its authenticated
`/slack/oauth/callback`; the installation supplies `bot_token`, `team_id` and the opaque
`workspace_identity(team_id)`. Mattermost setup requires `server_url`, `bot_token`, `client_id`,
`client_secret`, `webhook_token`; identity is the validated HTTPS server origin. Discord requires
`application_id`, `guild_id`, `bot_token`, `client_secret`, `public_key`; identity is
`application_id:guild_id`. Both setup forms complete their provider installation endpoint after saving
credentials. Twilio additionally requires `public_base_url`, an HTTPS API origin without a path.
Unrelated switch changes do not resend credentials or advance installation generation.

Envelope navigation uses tenant-bound local `/m/<slug>/...` paths so in-app delivery retains its
Open action. External delivery converts those paths to the verified tenant domain or central
canonical origin; inbox navigation never receives an absolute URL.

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
  `?code=...&state=...`. It first asks the authenticated endpoints GET to resolve `oauth_state`,
  then uses the returned challenge ID on the existing verify route. No browser storage or
  untrusted challenge query selects the challenge. Slack installation uses S256 PKCE (enable it on the
  provider app); installation is distinct from personal OIDC. No submitted user/chat ID is proof.
  Signed inbound chat hooks acknowledge only, with no decisions or destination assignment.
- **WhatsApp:** Twilio signed inbound/status routes are mounted and its provider is registered.
  A candidate E.164 number is not proof: a signed matching inbound opt-in code establishes consent.
  STOP revokes. Only authenticated inbound starts the 24 h free-text window; otherwise an approved
  event/audience/locale template binding is required. Twilio uses Content SIDs with reserved
  `notification_opt_in` (code variable) and `notification_test` (no variables), both member/en;
  Meta uses the same bindings and is registered with its webhook mounted. The shared
  `notification_wa_window.in_session_window` governs both providers, resolution and delivery:
  exactly 24 h and future inbound timestamps are outside the window. SMS-login consent grants
  no WhatsApp consent. Both providers use the independent registered whatsapp module.
  Browser PATCH cannot self-approve templates; provider refresh owns approval.
  The Twilio setup form exposes Refresh approval for saved bindings and reads back the provider's
  approval states; unsaved credentials or binding edits must be saved first.
  Status callbacks correlate installation/message and advance monotonically. Ambiguous addressed
  outcomes are held without resend; STOP and suppression apply before acknowledgement.
  Meta sends a signed `biz_opaque_callback_data` reference with the delivery, installation generation
  and attempt. Early status webhooks bind through that reference before the REST response stores its
  provider message ID. Callback transitions win over the later response; transient failures retain
  bounded retries and terminal failures release email fallback. A new attempt clears the old Meta
  message binding and rejects previous-attempt references.

Provider setting lookups are deployment-wide, never derived from the request host:

| Django setting | Adapter behaviour |
| --- | --- |
| `NOTIFICATION_SLACK_REDIRECT_URI` | Exact registered HTTPS frontend notification-settings URL; blank or placeholders refuse |
| `NOTIFICATION_MATTERMOST_REDIRECT_URI` | Same server-selected redirect policy |
| `NOTIFICATION_DISCORD_REDIRECT_URI` | Same server-selected redirect policy |
| `NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS` | Defaults false; only boolean true allows private self-host addresses |
| `WHATSAPP_META_GRAPH_VERSION` | Defaults `v25.0` in the Meta HTTP adapter |

All five are environment-backed in `config/settings.py`, included in deployment examples/manifests
and classified as nonblocking value-comparison settings for backup. Redirect defaults are blank;
private Mattermost hosts default false. Authorization and token exchange use the setting value
byte for byte, including its fixed query; dynamic challenge IDs belong only in signed state.
Register that exact frontend return URI with the provider. The frontend relays code/state through authenticated
`POST /personal/challenges/{id}/verify`; signed state must match both the account and URL challenge
before provider I/O. Completion locks configuration/challenge and consumes once. Anonymous
completion is gone; `ChatOAuthCallbackView` retains only authenticated, actor-bound Slack installation.
`TELEGRAM_WEBHOOK_SECRET` retains its existing env loader.

## Domain delivery ownership

Events and Bookings now use source-backed personal envelopes for lifecycle, reminders and campaigns.
Event delegates use `events.grant_staff`; booking delegates use `bookings.grant_alert`, both audience
`member` with live resource authority. Event staff envelopes pre-skip in-app/native push because the
legacy matrix still owns those legs. Event campaigns pre-skip email because the campaign worker owns
it; the extra channel task has no periodic lost-task resume. Booking campaigns with a saved category
selection use envelopes and skip batch email; others keep the existing batch-email path.
Booking lifecycle/reminder mail preserves an unverified owner's same booking contact mailbox through
the email-only `bookings.owner_mailbox` source. It proves explicit ownership and equal decrypted
`Booking.email`, then rechecks revision, standing, selection, module/matrix/configuration, personal
choice, suppression and consent at send/retry. It never uses another person's contact address or a
campaign audience. Its reserved email leg prevents a parallel envelope email when account verification
changes; a skipped leg releases recoverable envelope delivery. Account-less guests retain contact mail.
`notification_resolution.legacy_staff_email_allowed` preserves unverified active staff mail only for
whitelisted operational sources with live tenant membership/RBAC and recipient scope, never campaigns
or member/requester audiences. Other delivery gates remain. Requester booking notifications default on,
with audit-aware backfill of only untouched false tenant settings; per-resource overrides still win.

Hardware/machine/watch/certification and membership/payment/device/operations adapters register live
sources. Equipment room delivery now consults `notifications_p2_rooms.eligible_room` before timing/
provider delivery. Loan financial owner notices belong to the Payment adapter; hardware charge
summaries are staff-only, avoiding a second owner charge notice. Existing authentication mail stays
synchronous/redacted email; custody and mandatory reminders retain their independent policy.
The [coverage inventory](notification-coverage.md) records which producers actually call the adapters.

## Reconciled SMS, consent and push ownership

Canonical SMS uses `ChannelConfiguration(channel=sms, provider=twilio)` and the reviewed
scalar source projection. Its consent read/write remains `GET /api/v1/me/messaging?makerspace={id}`
and `POST /api/v1/me/messaging/consent`, with `{makerspace,channel,action}`. SMS live consent
matches current phone verification instance, sender and generation. WhatsApp uses the signed
endpoint flow above; SMS phone/login consent is unrelated. Current member accounts with an
owned booking/event/charge/loan/service tie qualify without membership or inbox installation.
Revoked membership, restricted/deleting account, source invalidation and explicit opt-outs win.
Staff use their own active fixed-tenant account; personal choices never grant staff authority.
The retained member-only SMS-consent API does not support staff SMS diagnostics yet; expose
its refusal rather than borrowing member consent. WhatsApp diagnostics use the staff account's
own proved endpoint.

Own credentials take precedence, even if incomplete. Platform senders need operator enablement
and tenant `use_platform_sender`, default false. Sender identity/credential history, durable STOP,
BSUID correlation barrier, billed/estimated segments and once-only quotas are canonical. Signed
callbacks and compatibility URLs feed encrypted deduplicated `NotificationIngress`; STOP commits
before acknowledgement even when a tenant is frozen. Correlation uses exact sender/provider/
tenant/generation/attempt mappings. Replay uses original inbound time; START grants no consent.

`NotificationDelivery(native_push)` owns per-device `MemberPushDelivery` children unique per
parent/device. Optional `inbox_row` uses SET_NULL. Inbox insertion never initiates push. Current
source-tied account-only recipients can receive it, independent of the inbox module; fixed-tenant
staff grants are separate and platform grants forbidden. Native selection/new device registration
still require active local membership; recipient eligibility alone does not widen that route. The notifications app registers the
push adapter, so tombstoning that entire app removes it even though disabling the inbox module
does not. Device claims recheck source, grant/account generation, matrix and personal selections;
explicit rejections may retry within four parent attempts, while unknown outcomes/expired leases
are held. Payload v2 uses `uuid5(NAMESPACE_URL, envelope.dedup_key)` and optional inbox ID/local
link, with rendered personal content. See [inbox/push contract](notification-inbox.md).

## Integration limits in this tree

The reconciliation removes Meta's former missing-module blocker and the duplicate addressed
send loop/UI. Both WhatsApp providers and the Twilio SMS path are present; configuration is not
proof of a successful provider round trip. Integrations 0043 destructive retirement and sending
activation remain held. Follow [deployment checkpoints](notification-reconciliation-rollout.md)
for expansion, original mapping fingerprints, push conversion, callback compatibility and replay
sign-off. Legacy settings/templates/delivery models and import helpers remain inert until then.

Equipment email rendering/policy hooks now participate in the shared mail/resolver path;
`hardware.owner_mailbox` and `bookings.owner_mailbox` preserve narrow same-owner contact
compatibility. Source-backed equipment, booking, event, machine, membership, payment and device
adapters reserve one canonical intent per source/revision/audience and recheck current ownership.
Existing staff matrix/inbox and campaign-email pre-skips prevent duplicate legs.

Remaining limits include event campaign channel tasks without periodic lost-task resume,
optional account-linked invitation notices not added for every invitation family, and legacy
room retry policies outside the equipment source/scope checks. Presence expiry has no staff
room and defaults to personal in-app/native push without email fallback. Scheduled-report legacy
status is not provider acknowledgement. Source-specific module overrides now map machines.service to machine_service,
operations.stocktake to stocktake, inventory.watch to request_workflow and inventory.threshold
to core inventory; these avoid the former generic printing/procurement gates.

The [coverage inventory](notification-coverage.md) distinguishes producers and intentional legacy
paths; it is not runtime test evidence. Source ownership is indexed in
[SOURCE-MAP-NOTIFICATIONS.md](SOURCE-MAP-NOTIFICATIONS.md). OpenAPI/TypeScript regeneration,
runtime checks, provider tests and rollout sign-offs belong to the orchestrator/operator.
