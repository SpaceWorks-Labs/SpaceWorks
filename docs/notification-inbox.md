# Personal notifications and delivery controls

The legacy `notifications.Notification` remains a makerspace-wide feed with its existing
shared read state. Personal inboxes use `NotificationInboxRow`, keyed by makerspace,
User and lifecycle event UUID. Reading one inbox never acknowledges another person's
message or a legacy row. The member dashboard's existing derived notices remain intact.

## Gates and recipients

Install the existing `notifications` module for staff inboxes. The matrix has an `in_app`
channel, on by default except hardware/printing, whose existing direct staff alerts are
mirrored while their matrix channel remains opt-in. Member delivery additionally requires
`notifications.member_inbox`; its default is off. The preference editor requires
`notifications.member_preferences`, also off by default. No new module is introduced.

Staff recipients use the existing action, explicit recipient selection and machine scope
resolver. Member recipients come from explicit authenticated domain-owner User IDs,
never submitted email/phone fields. Active account-only borrowers can read rows addressed
to them. Revoked memberships, restricted/inactive accounts and unavailable tenants cannot.
When an owner is also staff, their own summary wins and one event produces one row.
Requester selections, blanket member opt-outs and booking requester switches apply to
inbox delivery too. Explicit inbox summaries take precedence over email fallbacks, so
mail-only status tokens need not become inbox content. Printing and API-access inboxes
also work without an email address. Links reject controls, backslashes and external origins.
Member summaries are built independently of staff chat text; no email address is needed
for inbox delivery. Legacy-only staff alerts are mirrored for the old feed's eligible
staff audience; matrix-backed request/printing alerts are not mirrored a second time.

Titles and summaries use the existing scoped PII encryption boundary. Links are local
application paths. A private User SSE hint carries no text; clients refetch through the
scoped API. Personal TanStack query keys include recipient ID as well as makerspace
and surface, preventing cached inbox/preferences from crossing account switches. Inbox rows are snapshots; later staff-role changes do not rewrite history.

## API

Paths below are relative to `/api/v1`; lists use `{count,next,previous,results}` and 24 rows.
All personal authenticated routes constrain rows to the current User and makerspace.
Module/feature-off responses are 400, denied access is 403, foreign row IDs are 404.
Writes emit audit entries with a User actor.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/notifications/inbox/{makerspace_id}` | Personal inbox; `unread`, `feature`, `page` filters |
| GET | `/notifications/inbox/{makerspace_id}/unread-count` | Own unread count |
| POST | `/notifications/inbox/{makerspace_id}/{id}/read` | Idempotent acknowledgement |
| POST | `/notifications/inbox/{makerspace_id}/read-all` | Own unread rows only |
| GET/PATCH | `/notifications/preferences/{makerspace_id}` | Family/channel cells; PATCH `{feature,channel,enabled}` |
| POST | `/notifications/unsubscribe/{token}` | Signed, login-free one-click email opt-out |
| GET | `/notifications/unsubscribe/{token}` | No-write browser landing: 302 to `/unsubscribe/{token}`, or an HTML confirm form |
| GET | `/integrations/makerspace/{makerspace_id}/delivery-logs` | Staff unified email/channel history |
| POST | `/integrations/makerspace/{makerspace_id}/delivery-logs/{kind}/{id}/retry` | Failed row retry; `{generation}` |
| POST | `/integrations/makerspace/{makerspace_id}/delivery-test` | Email to current User; optional `{destination_id}` tests an explicitly selected room |
| GET/POST | `/integrations/makerspace/{makerspace_id}/email-suppressions` | List hashes or add `{address,reason}` |
| DELETE | `/integrations/makerspace/{makerspace_id}/email-suppressions/{id}` | Remove a scoped suppression |

Delivery controls require `MANAGE_MAKERSPACE`, including organization-derived action grants; local roles are fixed built-ins.
Log filters: `channel`, `status`, `feature`, `event`, `destination`, `page`. Responses
exclude rendered bodies, addresses, credentials and destination URLs. Retry locks the
row, checks the submitted generation, advances it once and enqueues after commit. A
repeated request with the old generation cannot enqueue again even if enqueue failed.
Workers still provide at-least-once transport: a crash after provider acceptance and
before SENT commits can resend. Send-test cannot name an arbitrary email recipient.

## Preferences and deliverability

Personal opt-outs are checked both when mail is queued and immediately before send.
They cannot turn on a channel the makerspace disabled. Existing staff receives-notification
and recipient rules remain authoritative. Turning off the editor does not discard saved
opt-outs, including after a deployment tombstones notifications. Email, inbox and device
push preferences are independent. Member native push does not depend on an inbox row: it is a
channel delivery under the personal envelope (see Native push beneath personal envelopes below),
so the `in_app` switches govern only inbox rows.

Account recovery, verification, overdue return reminders and loan
closure-with-issue emails bypass personal opt-outs. Suppression still blocks known bad
addresses, including transactional mail. Suppression stores a tenant-keyed HMAC of the
normalized address, a reason (`bounce` or `complaint`) and the staff User who recorded it.
It is checked for every tenant email, independently of the inbox feature switch.

SMTP is the only current mail transport, so suppression is manual in Delivery logs.
Superadmins can suppress platform mail separately in `/control/` under Email
suppressions. Tenant hashes affect that tenant's mail; platform hashes affect
platform mail only. Both controls audit changes and retain no plaintext address.
There is no provider webhook to authenticate. API email providers and automatic bounce
callbacks are deferred. Suppression is intrinsic delivery hygiene rather than an opt-in
switch that could resend to a known complaining address.

Optional family emails addressed to a known User include `List-Unsubscribe` and
`List-Unsubscribe-Post: List-Unsubscribe=One-Click` when the preference editor is enabled
and `PUBLIC_APP_BASE_URL` is HTTPS. The token binds tenant, User and family, uses Django's
salted timestamp signature and expires after 365 days. POST accepts URL-encoded form or
JSON with `List-Unsubscribe=One-Click`. GET changes nothing (mail scanners prefetch links): a
valid token 302-redirects to the website's `/unsubscribe/{token}` confirm page at
`PUBLIC_APP_BASE_URL`, or, with no website origin configured, renders a minimal HTML form that
POSTs the one-click body back; an invalid token gets a 400 HTML page. The same mail carries a
visible "Unsubscribe from these emails" footer link to the website page, added at send time
and never persisted. Forged/expired tokens return 400. The late tenant write gate refuses frozen tenants with 423. No login, cookies or
CSRF session are required. Configure the SMTP provider to DKIM-sign both unsubscribe
headers as required by RFC 8058; the application cannot enforce provider signing.

## Native push beneath personal envelopes

Canonical native push is a channel delivery under `NotificationEnvelope`, with one
`MemberPushDelivery` child per `(envelope_delivery, push_device)`. The required parent is
`integrations.NotificationDelivery`; optional `inbox_row` uses SET_NULL. Creating or reading
an inbox row never starts a push and deleting inbox rows cannot cascade delivery history.
Old enqueue/deliver-row/Celery identifiers remain inert compatibility shims.

Current member/requester owners with a proved source tie qualify without an active membership
or inbox installation. Revoked memberships and account/source restrictions still refuse.
Staff require a separate staff-kind password/MFA/attested grant fixed to their tenant; native
platform grants do not exist. Each attempt rechecks source revision, account/generation, module,
tenant matrix, intersected personal choices, registration, grant and current device identity.
The notifications app registers the adapter: disabling the inbox module is supported, whereas
tombstoning the entire app removes that adapter.

Atomic UUID claims fence provider completions. Definitive transport rejections can retry within
the parent's four-attempt budget; unknown outcomes and expired leases are held without blind
resend. A late actual response can settle only its original token; rotation cannot invalidate
a replacement push token. The five-minute sweep re-enters the envelope dispatcher and respects
parent backoff and inert historical records. Provider I/O runs outside application transactions.

Payload v2 has string values `v`, `event_id`, `makerspace_id`, `feature`, `event`, optional
`inbox_row_id` and allowlisted local `link`. Canonical `event_id` is
`uuid5(NAMESPACE_URL, envelope.dedup_key)`. Content is rendered for the personal recipient,
not copied from a room. Titles name the makerspace; APNs groups by its thread ID. Retained
legacy staff matrix legs preserve their stable identities and matching envelope pre-skips.
Apps deduplicate, refetch source APIs on foreground/tap and fall back to inbox when available
or makerspace home when it is absent.

Notifications 0008 expands nullable parents before the shared barrier; 0009 maps every old
push row and creates inert historical parents; 0010 verifies original fingerprints and makes
the parent required. Terminal rows stay inert, untouched pending rows become canceled and
uncertain attempts held. Conversion never sends. Follow the separate
[deployment checkpoints](notification-reconciliation-rollout.md) before activation or retirement.

## Retention and data hygiene

The F1 reminder sweeper runs bounded cleanup even with no reminder sources registered.
Platform email logs use the same bounded terminal-delivery cleanup.
Each tenant holds its migration boundary, skips frozen/not-restored tenants and isolates
failures. Row locks with skip-locked protect cleanup against concurrent retry claims.

| Rows | Default cutoff |
| --- | --- |
| Read inbox | 90 days after `read_at` |
| Sent email/channel delivery | 90 days after `sent_at` |
| Failed delivery | 365 days after last `updated_at` |
| Skipped delivery | 90 days after last `updated_at` |
| Unread inbox, pending/sending delivery | Kept |

These are the research proposal's fixed defaults. Per-space retention overrides and
longer retention need a separate owner decision. Suppression and preference rows are
not delivery telemetry and are retained until removed or the tenant/module is purged.
Notification-module purge deletes legacy rows, personal rows and personal preferences.

Export/model/User-edge and tenant field catalogues declare all new models. Inbox text
and deployment-keyed suppressions are omitted from portable artifacts. Preferences
are included in manager datasets but dropped at target import, following the existing
target-owned notification policy; target Users must re-establish them before optional
communications are enabled. Tenant backups preserve source data normally. The reconciled catalog and concrete field snapshot define the target schema digest;
regenerate/verify it with the owning registry workflow rather than retaining either parent pin.

## Structured webhooks

Signed destinations keep `payload_version=1` by default, including old clients editing
an existing destination. Choosing 2 emits the contract in
[webhooks-v2.md](webhooks-v2.md) and [the JSON Schema catalogue](webhooks-v2.schema.json).
Editable templates cannot alter v2 field names or inject contact/credential fields.

For which notices each module sends (inventory, events, bookings, membership, shop, repairs) see
[notification-coverage.md](notification-coverage.md#release-0120-coverage-by-module-decision-221f).
