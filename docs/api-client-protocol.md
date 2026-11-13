# SpaceWorks API client protocol (v1)

> Reference for anyone building a client against a SpaceWorks deployment's protected API
> surface. The rules here are enforced by `apps/inventory/middleware.py` and
> `apps/apiclients/scope_registry.py`; the invariants behind them are under **API client
> scopes and the protected-route registry** in `docs/INVARIANTS.md`.

## What is protected

Only paths under `HMAC_PROTECTED_PATH_PREFIXES` — by default `/api/public/` and
`/api/v1/public/`. Everything else (the staff API under `/api/v1/admin/`, the Telegram
webhook, the Django control plane) is outside this protocol and authenticates by other
means.

## The three credential shapes

| Shape | Headers | Use |
|---|---|---|
| **Signed server client** | `X-Client-Id` + `X-Timestamp` + `X-Signature` (+ optional `X-Nonce`) | Server-to-server. The only shape that earns a rate-limit tier. |
| **Browser client** | `X-Client-Id` + a registered `Origin` | A first-party web frontend. Identified, **not** trusted: both values are public frontend config and forgeable by a non-browser caller, so this shape never elevates rate limits. |
| **Publishable key** | `X-Publishable-Key` | A tenant's public site. Scoped to that makerspace. |

A server client has no browser origin, and none is required of it.

## Canonical signing string

```
message   = METHOD "\n" FULL_PATH "\n" TIMESTAMP [ "\n" NONCE ] "\n" BODY
signature = hex( HMAC-SHA256( client_secret, message ) )
```

- `METHOD` is upper-case; `FULL_PATH` is the path **including** the query string.
- `TIMESTAMP` is integer seconds since the epoch, and must be within
  `HMAC_MAX_CLOCK_SKEW_SECONDS` (default 300) of server time.
- `BODY` is the raw request body, empty for a bodyless request.
- The nonce part is present **only** when `X-Nonce` is sent.

### The nonce slot, and why a body can be refused

Because the nonce part is optional, a nonced request and a nonce-less request whose body is
`NONCE + "\n" + body` produce **identical** bytes — so the same signature would verify for
both readings, and only the nonced reading claims the nonce. A captured request could
otherwise be replayed for the whole skew window. A nonce-less request whose first line is
itself a well-formed nonce followed by a newline is therefore **rejected**. JSON bodies begin
with `{`, so real callers never hit this.

**Protocol v2 (planned)** removes the ambiguity properly by giving the message a fixed part
count — always signing a nonce slot, empty when absent. It is not v1 because it changes the
message for every existing nonce-less client.

### Nonce rules

- Charset `[A-Za-z0-9._~-]`, at most 128 characters.
- The namespace is `(client_id, nonce)`: two different clients may use the same nonce value.
- A nonce is claimed exactly once per request, atomically, **after** the signature verifies.
- Sending `X-Nonce` opts you in to replay protection immediately, whatever
  `APICLIENT_REQUIRE_NONCE` says: a replay is rejected even while enforcement is off.
- Nonces are never cleared by a secret rotation, so a replay stays rejected across one.

## Scopes

Authorization is per route, from a frozen registry keyed on the versioned view name. The
vocabulary is:

`public:read` · `public:write` · `public:*` · `legacy:v1`

Since 0.12.0 there are also **area scopes** `public:<area>:read` / `public:<area>:write`: each
public registry entry belongs to exactly one area (`apps/apiclients/scope_registry_areas.py`)
and also accepts its area scope, so a client can hold, say, `public:catalogue:read` alone.
`public:read`, `public:write` and `public:*` keep their meaning. Area scopes are tenant
grantable. A **peer** client (`client_type="peer"`, another space's backend) signs like a
server client but may hold only `public:catalogue:read`, `public:events:read` and
`public:stats:read`, reaches GET/HEAD only, and only its own space's routes -- enforced at
grant time and again on every request (`scope_registry_verdicts.peer_may_reach`).
Every URL route outside the protected prefixes is listed with the credential that serves it
in `scope_registry_coverage.py`; `apiclients.E003` refuses startup on an unlisted one.

`admin:read`, `admin:write`, `admin:*` and `reports:read` are retired: no protected route
ever used them. They are absent from the grant catalog and new grants are rejected.
Existing stored values confer no access and are reported as outside the vocabulary by
the enforcement report. Replace them explicitly with the intended public scopes;
they are never automatically converted to `legacy:v1`. Staff and reporting routes
continue to require their existing user authentication and permissions.

Rules that are easy to get wrong:

- **An unregistered route is denied before any wildcard is considered.** `public:*` cannot
  authorize a route the registry does not know, and neither can `legacy:v1`.
- **`legacy:v1` is frozen.** It authorizes exactly the routes it covered at cutover. Routes
  added later are never absorbed into it.
- Tenant staff may grant exactly `public:read` and `public:write`. Public wildcards
  and `legacy:v1` require a global superadmin; a
  superadmin acting through membership in a makerspace hidden from global access is
  tenant-limited.
- **A browser client may hold only read/public scopes** (plus `legacy:v1`).
- A client bound to a makerspace may only reach that makerspace's routes; a route that
  addresses no makerspace admits a tenant-bound client only if it explicitly says so.
- A tenant route whose makerspace cannot be resolved is denied — an unresolvable tenant is
  never treated as "no tenant".

## Secret rotation

`POST /api/v1/admin/api-clients/<pk>/rotate-secret` returns a new secret and keeps the
previous one valid for a grace window (24 hours). During it, either secret authenticates;
after it, only the new one does. A second rotation replaces the single retained previous
secret rather than adding to it, so rotating twice inside the window invalidates the oldest
immediately. There is no way for a client to ask for the old secret to be used — switch when
convenient inside the window.

## Enforcement staging

Two settings gate this, and both default to **False**:

- `API_CLIENT_AUTH_REQUIRED` — when False, an unsigned request to a protected path falls
  through as anonymous and DRF authorization still applies. Every request that *would* have
  been rejected is logged once with its route, method, client id and reason, so a deployment
  can see what would break before turning it on.
- `APICLIENT_REQUIRE_NONCE` — when False, a nonce is optional (but honoured if sent).

`manage.py api_client_enforcement_report` lists what stands in the way of flipping them:
clients still on `legacy:v1`, clients with no allowed origins, and clients whose scopes fall
outside the vocabulary.

## Errors

| Status | Body | Meaning |
|---|---|---|
| 401 | `{"detail": "Invalid client signature."}` | Any credential failure: unknown client, bad signature, skew, nonce replay, scope denied, unresolved or mismatched tenant. Deliberately uniform — it does not tell an attacker which check failed. The server log records the specific reason. |
| 429 | throttled | Rate limit for the client's tier. |
| 403 | `{"code": "full_session_required"}` | Payee/payout money is session-only (`payments/payout_session.py`). Signed clients, personal access tokens and OAuth app connections are refused payout reports (`prizes-owed`, `event-finance`, any report with a payout column), the event finance view and the reimbursement routes. Finance summaries and the linked event-finance view answer without `payouts`, `money_out`, `net` and `budget_left`. |

A misconfigured deployment fails at startup rather than at runtime: if
`HMAC_PROTECTED_PATH_PREFIXES` is widened to a prefix whose routes are not registered,
`manage.py check` reports it as an error instead of the deployment silently 401-ing that
whole prefix.

## Outbound webhooks

The inbound protocol above lets your system call SpaceWorks. The `webhook` notification module is the
other direction: SpaceWorks calls **your** HTTPS endpoint whenever the notification matrix routes an event
to a signed-webhook destination.

Destinations default to `payload_version=1`, preserving the envelope below. Opting a
destination into version 2 sends the bounded event envelope and per-event schemas in
[Signed webhook v2](webhooks-v2.md). In version 2 the event header is qualified, for
example `hardware_requests.accepted`, and User-Agent is `SpaceWorks-Webhook/2`.
The HMAC signature contract is the same for both payload versions.

**Version 1 request.** `POST` with `Content-Type: application/json`, `User-Agent: SpaceWorks-Webhook/1`, and:

| Header | Value |
|---|---|
| `X-SpaceWorks-Event` | the bare matrix event key, e.g. `accepted` |
| `X-SpaceWorks-Delivery` | the delivery id (stable across retries — use it to de-duplicate) |
| `X-SpaceWorks-Signature` | `t=<unix seconds>,v1=<hex>` |

**Body.** The existing fields `id`, `event`, `feature`, `makerspace_id`, `text`, `data` and
`created_at` remain. `event` matches the bare header key; `text` is the same staff message a
Slack or Telegram room would receive. `data` carries explicit domain IDs, `occurred_at`
and optional routing `scope`. A new `structured` object provides a versioned contract
alongside those fields, so existing receivers can continue reading the original envelope:

```json
{
  "id": 42,
  "event": "accepted",
  "feature": "hardware_requests",
  "makerspace_id": 7,
  "text": "Hardware request #12 has been accepted.",
  "data": {"request_id": 12, "occurred_at": "2026-10-10T01:02:03+00:00"},
  "created_at": "2026-10-10T01:02:04+00:00",
  "structured": {
    "version": 1,
    "event": "hardware_requests.accepted",
    "ids": {"request_id": 12},
    "makerspace": {"id": 7},
    "occurred_at": "2026-10-10T01:02:03+00:00"
  }
}
```

`structured.version` versions this new object independently of the inbound API protocol
and the `v1` HMAC signature. Its event names are exactly `<feature>.<event key>`;
for example `bookings.confirmed`, `events.registration_approved`,
`maintenance.schedule_completed` and `api_access.api_key_request_resolved`.
The lifecycle event catalog is `apps/integrations/notification_catalog.py::FEATURE_EVENTS`,
also exposed by the staff notification-rules API. Scheduled reports deliver directly to
their selected destination and emit `reports.scheduled_report`. `request.accepted` is not emitted.

| Feature | IDs when applicable |
|---|---|
| `hardware_requests` | `request_id`; `payment_id` on deposit/late-fee events |
| `printing` | `machine_service_request_id` (the kernel printer request) |
| `bookings` | `booking_id`, `space_id` |
| `events` | `event_id`; `series_id` for a series occurrence; `registration_id` for a registration |
| `maintenance` | `machine_id`; `schedule_id` and/or `maintenance_log_id` |
| `members` | `membership_request_id` or `membership_id` |
| `api_access` | `api_key_request_id` |
| `reports` | `schedule_id` for a scheduled report |

IDs are positive integers; absent IDs are omitted. No contact fields, secrets or template
context enter the structured object. `occurred_at` is captured when the notification is
scheduled, before transaction commit and queue delay, and stays stable across rooms and
retries. Direct destination sends use `created_at`; rows queued before this change also
fall back to their `created_at`, and can have empty
`ids` because historical subject IDs cannot be reconstructed safely. The text remains the
existing staff message; consumers should use `structured.event` and `structured.ids` for
automation. Version 2 is a deliberate per-destination opt-in; the version 1 envelope remains available.

API-access resolution now follows the `api_access` matrix row: email and Telegram default
on to preserve existing delivery; the other channels default off. Channel preferences,
module gates, per-room quota and delivery logs apply. The staff-notifications switch stops
rooms/push while requester email remains controlled by the email matrix cell. The
requester-only resolution note is never copied into room text or structured data.

**Verify.** Compute `HMAC-SHA256(secret, "<t>." + raw_body_bytes)` with the signing secret you entered
when creating the destination, compare it to `v1` with a constant-time comparison, and reject if `t` is
older than your tolerance (five minutes is reasonable):

```python
import hashlib, hmac, time

def verify(headers, raw_body: bytes, secret: str, tolerance=300) -> bool:
    parts = dict(item.split("=", 1) for item in headers["X-SpaceWorks-Signature"].split(","))
    if abs(time.time() - int(parts["t"])) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{parts['t']}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts["v1"])
```

Respond with any 2xx. Anything else, or a timeout, is retried by the delivery worker; after the retries a
space manager can retry from Delivery logs, or a superadmin from `/control/`. Endpoints must be public HTTPS — private and
loopback addresses are refused when the destination is saved and again at send time.

## Signed staff-data reads

GET and HEAD routes require a server client bound to exactly one makerspace,
Events installed and `events.api_read` enabled:

| Route | Required scopes |
| --- | --- |
| `/api/v1/events/` | `events:read` |
| `/api/v1/events/<id>/` | `events:read` |
| `/api/v1/events/<id>/participants/` | `events:read` AND `participants:read` |
| `/api/v1/events/orders/` | `orders:read` (also needs `events.orders`) |
| `/api/v1/events/orders/<id>/` | `orders:read` |

Only a platform superadmin grants these scopes. Browser/publishable keys, global
clients, JWT sessions, `public:*` and frozen `legacy:v1` never authorize these
routes. The prefix remains mandatory even if removed from an operator override
or public-API enforcement is off. Sign the full path including its query string
using the existing protocol above. Nonce, clock and rotation policies are unchanged.

Events allow only ID, title, status, start/end, location, `is_public` and `listing` (the tenant credential still reads every event, private and unlisted included, and filters on these
fields itself). Participants allow
registration ID, display name and registration date. With both prerequisite
scopes, `participants:attendance:read` adds the current attendance date (null when
no longer attended). Contacts, answers, ticket/check-in credentials and money are
excluded. Participant reads audit an opaque client fingerprint and row count.

Ticket orders (`orders:read`) allow the order ID, event or series ID, kind, status,
currency, subtotal, discount, fee and total, created and paid dates, the frozen lines (kind, label,
quantity, unit amount, discount, line total, ticket type and add-on IDs) and seat counts (live and
claimed). Buyer and attendee names, emails, claim tokens and provider handles are excluded. A space
with `events.orders` off answers 404, like any unknown route.

Lists return `{ "next_cursor": string|null, "results": [...] }`. Use `page_size`
1-200 (default 100) and return the cursor unchanged. Signed cursors expire after
24 hours and bind client, tenant, subject and attendance projection. Ascending
immutable IDs prevent inserts from duplicating earlier rows; this is live
pagination, not a frozen export. Responses are private/no-store. Foreign IDs,
hidden/unservable tenants and unknown targets fail closed. Client, scope, module
and feature revocations apply on the next request.

`apiclients/read_contract.py` is core infrastructure: domain live startup registers
typed `ReadTarget` adapters. Add explicit GET/HEAD registry entries, dedicated
server-only scopes and a mandatory prefix for a new domain; never import Events
to reuse authentication, target resolution, throttles or signed keyset pagination.

## Signed booking reads

These GET/HEAD routes require Bookings and opt-in `bookings.api_read`, with the
same mandatory HMAC, tenant-bound server principal, operator-only grants, signed
keyset pagination, nonce policy, throttling and private/no-store responses above.
No browser, global, user session, public wildcard or legacy client is upgraded.

| Route under `/api/v1/booking-integration/` | Required scope |
| --- | --- |
| `resources/` | `booking_resources:read` |
| `resources/<id>/` | `booking_resources:read` |
| `bookings/` | `bookings:read` |
| `bookings/<id>/` | `bookings:read` |
| `resources/<id>/bookings/` | `bookings:read` |

Resource reads contain only integer ID, name, kind, description, capacity,
location, active and public flags. Signed staff integrations may read private or
inactive resources; these scopes never confer public website visibility.
Reservation reads contain only integer ID, resource ID, window, status and display
name. Resource and reservation read scopes are independent; reading reservations
does not require resource-read authority. `bookings:attendance:read` additionally
requires `bookings:read` at grant time and never authorizes a route alone. It adds
only current unreversed `arrived_at` (nullable), including arrivals retained after
completion. Reversed arrivals return null. No contact, note, answer, credential,
machine link, form, grant, booking rule or payment field appears.

Reservation GET and HEAD append `api_client.bookings_read` with an opaque client
fingerprint, row count and attendance projection, through the source write fence;
frozen sources refuse that audited read. Foreign/missing targets fail closed before
the view. Cursors bind the client, tenant, resource/list subject and attendance
projection; changing scopes cannot reuse an earlier projection's cursor. Lists
are live ID-ordered reads, not snapshots. Scopes/features/revocation are rechecked
on each request, without consulting user RBAC or resource staff grants.

Website sections and assets are not part of this initial projection. To add them, extend
only approved public page fields through the release/visibility adapter, never through
unrestricted model serialization.
