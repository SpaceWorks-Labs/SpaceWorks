# SpaceWorks API guide

How another system talks to a SpaceWorks deployment: a university ERP, a script, a
community calendar, or another makerspace's backend. The interactive reference for
every route is on the deployment itself:

| Page | What it is |
| --- | --- |
| `/docs/` | Swagger UI: try calls, press **Authorize** to paste a bearer token |
| `/redoc/` | ReDoc: the same reference, grouped by area |
| `/schema/` | The OpenAPI 3 document (`?format=json` for JSON) |

The precise signing rules are in [`api-client-protocol.md`](api-client-protocol.md);
outbound events are in [`webhooks-v2.md`](webhooks-v2.md).

## Pick a credential

| You are | Use | Acts as |
| --- | --- | --- |
| A backend of your own (ERP, script, sync job) | **API client** (signed server client) | the client, on public routes and the signed integration reads |
| Another space's backend reading your public data | **API client, type "Another space"** (peer) | the client, read-only, your public catalogue, events and stats |
| A person automating their own work | **Personal access token** | that person, within the token's scopes |
| A third-party app people sign in to | **App connection** (OAuth 2.0 / OIDC) | each person who connects it, within the consented scopes |

None of them can do more than its owner may do at that moment.

## API clients

A Space Manager creates one under **Settings -> API access -> New API client** and picks:

* **Who will use it**: *Our own system* (a server client) or *Another space* (a peer client).
* **Scopes** (below). The secret is shown **once**. Rotate it from the client's menu: the old
  secret keeps working for 24 hours. **Revoke** stops it at once and keeps its history;
  **Delete** removes it. Every change is audited; the management routes are rate-limited.

A superadmin can do the same for any space, and alone may grant the operator-only scopes.

### Scopes

| Scope | Reaches |
| --- | --- |
| `public:read`, `public:write` | every registered public route of the space (read, or submit) |
| `public:<area>:read`, `public:<area>:write` | the public routes of one area only |
| `events:read`, `participants:read`, `orders:read`, `bookings:read`, ... | the signed integration reads (operator-only; see the protocol) |

Areas: `catalogue`, `events`, `stats`, `bookings`, `pages`, `requests`, `machine_service`,
`memberships`, `presence`, `shop`, `donations`, `pricing`, `id_programmes`, `repairs`,
`hosting`. The console shows each with its description.

Every route is deliberately either reachable by API clients or not (staff, member,
sign-in, provider-webhook and device routes are not); an unregistered route is always
refused, whatever the scopes say.

### Space to space

A **peer** client is created by space A for space B's backend. It may hold only
`public:catalogue:read`, `public:events:read` and `public:stats:read`, reaches only GET
and HEAD, and only space A's own routes. Nothing private crosses tenants: the peer reads
exactly what space A's public site already shows.

### Signing a request

Send `X-Client-Id`, `X-Timestamp` (Unix seconds), `X-Nonce` (fresh, `[A-Za-z0-9._~-]`,
up to 128) and `X-Signature = hex(HMAC-SHA256(secret, METHOD\nFULL_PATH\nTIMESTAMP\nNONCE\nBODY))`.
`FULL_PATH` includes the query string; `BODY` is the raw body (empty for GET).

Python:

```python
import hashlib, hmac, secrets, time, requests

def signed(method, base, path, client_id, secret, body=b""):
    ts, nonce = str(int(time.time())), secrets.token_urlsafe(24)
    message = b"\n".join([method.encode(), path.encode(), ts.encode(), nonce.encode(), body])
    signature = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    headers = {"X-Client-Id": client_id, "X-Timestamp": ts, "X-Nonce": nonce, "X-Signature": signature}
    if body:
        headers["Content-Type"] = "application/json"
    return requests.request(method, base + path, data=body or None, headers=headers, timeout=10)

r = signed("GET", "https://spaces.example.org", "/api/v1/public/lab/inventory/?page=1", CLIENT_ID, SECRET)
```

JavaScript (Node 18+):

```js
import { createHmac, randomBytes } from "node:crypto";

async function signed(method, base, path, clientId, secret, body = "") {
  const ts = String(Math.floor(Date.now() / 1000));
  const nonce = randomBytes(18).toString("base64url");
  const signature = createHmac("sha256", secret).update([method, path, ts, nonce, body].join("\n")).digest("hex");
  return fetch(base + path, { method, body: body || undefined, headers: {
    "X-Client-Id": clientId, "X-Timestamp": ts, "X-Nonce": nonce, "X-Signature": signature,
    ...(body ? { "Content-Type": "application/json" } : {}) } });
}
```

curl (with `openssl`):

```sh
PATH_Q='/api/v1/public/lab/stats/'; TS=$(date +%s); NONCE=$(openssl rand -hex 16)
SIG=$(printf 'GET\n%s\n%s\n%s\n' "$PATH_Q" "$TS" "$NONCE" | openssl dgst -sha256 -hmac "$SECRET" -hex | sed 's/^.* //')
curl -s "https://spaces.example.org$PATH_Q" -H "X-Client-Id: $CLIENT_ID" -H "X-Timestamp: $TS" \
  -H "X-Nonce: $NONCE" -H "X-Signature: $SIG"
```

## Personal access tokens

A person creates one at **`/account/api-access`** after a fresh sign-in check (MFA when
enrolled): a name, scopes and an expiry (90 days by default, at most a year). The token
(`swpat_...`) is shown once and stored only as a digest. Last use is shown; revoke any time.

| Scope | Reaches |
| --- | --- |
| `account:read`, `account:write` | your own member routes (`/api/v1/member/`, `/api/v1/me`, notifications) |
| `public:read`, `public:write`, `public:<area>:*` | the public API, as you |
| `staff:read`, `staff:write` | staff console routes of **one** space where you hold a staff role |

Every request replays your live checks: account state, staff roles, staff MFA (a factor
reset ends the token), the space's modules, the view's own permissions. Tokens never
reach sign-in, MFA, passkeys, credential and security settings, API clients, backups,
superadmin routes or `/control/`.

**Payee and payout money needs an interactive session.** Personal access
tokens, OAuth app connections and signed API clients never read what was paid to a person.
Payout reports (`prizes-owed`, `event-finance`, any report with a payout column), the event
finance view and the reimbursement routes answer `403 {"code": "full_session_required"}`.
Finance summaries and the linked event-finance view answer without the `payouts`, `money_out`,
`net` and `budget_left` fields. Other reports still follow the staff role's area: a token only
reads the reports its holder's role manages.

```sh
curl -s https://spaces.example.org/api/v1/member/makerspaces/7/activity -H "Authorization: Bearer $SWPAT"
```

```python
requests.get(f"{BASE}/api/v1/member/makerspaces/7/activity", headers={"Authorization": f"Bearer {token}"})
```

```js
await fetch(`${BASE}/api/v1/member/makerspaces/7/activity`, { headers: { Authorization: `Bearer ${token}` } });
```

## App connections (OAuth 2.0 / OIDC)

A Space Manager (or the superadmin) registers the app under **API access -> App
connections**: name, redirect URIs (`https://`), type (*has a server*: confidential, with a
client secret shown once; *phone or browser*: public, PKCE only) and the scopes it may ask
for (the personal-token vocabulary above; staff scopes apply to the registering space).

The flow is authorization code with **PKCE (S256, required)**:

1. Send the person's browser to `/api/v1/oauth/authorize/?response_type=code&client_id=...&redirect_uri=...&scope=account:read&state=...&code_challenge=...&code_challenge_method=S256`.
   They see the consent screen (app, space, scopes) and allow after a fresh sign-in check.
2. Exchange the code at `POST /api/v1/oauth/token/` (`grant_type=authorization_code`,
   `code`, `redirect_uri`, `client_id`, `code_verifier`, and the secret for confidential apps).
3. Call the API with `Authorization: Bearer swoa_...` (1 hour). Refresh with
   `grant_type=refresh_token`; each refresh returns a **new** refresh token and a reused one
   ends the whole chain. Revoke with `POST /api/v1/oauth/revoke/`.

```python
r = requests.post(f"{BASE}/api/v1/oauth/token/", data={
    "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
    "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code_verifier": verifier}, timeout=10)
access, refresh = r.json()["access_token"], r.json()["refresh_token"]
```

```sh
curl -s -X POST https://spaces.example.org/api/v1/oauth/token/ -d grant_type=refresh_token \
  -d refresh_token="$REFRESH" -d client_id="$CLIENT_ID" -d client_secret="$CLIENT_SECRET"
```

```js
const body = new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri, client_id, code_verifier });
const tokens = await (await fetch(`${BASE}/api/v1/oauth/token/`, { method: "POST", body })).json();
```

With `OAUTH_OIDC_RSA_PRIVATE_KEY` configured the deployment is also an OpenID Provider
(`/api/v1/oauth/.well-known/openid-configuration`, `jwks.json`, `userinfo/`; ask for `openid`).
People see and disconnect their apps at `/account/api-access`; deleting or switching off an
app ends every connection to it.

## Pagination

Lists answer `{"count", "next", "previous", "results"}` with 24 rows a page (`?page=2`).
Signed integration reads use `{"next_cursor", "results"}`: pass `?cursor=` back unchanged
(`page_size` 1-200).

## Errors

`{"detail": "...", "code": "..."}` with the HTTP status; validation errors map each field to
its messages. API-client credential failures are a uniform `401 {"detail": "Invalid client
signature."}`. `423` means the space is frozen for a migration; `503` a dependency is down.

## Rate limits

`429` with `Retry-After`. Signed clients are limited per client by tier (public 30/min,
standard 120/min, trusted 600/min by default); tokens and app connections per credential
(120/min); credential management and consent per person.

## Webhooks

SpaceWorks can call your HTTPS endpoint on events (bookings, events, requests, payments...),
signed `X-SpaceWorks-Signature: t=...,v1=...`. Version 2 envelopes are described in
[`webhooks-v2.md`](webhooks-v2.md); version 1 and verification code are in
[`api-client-protocol.md`](api-client-protocol.md#outbound-webhooks).

## Versioning

Everything is under `/api/v1/`. `/api/public/` is the frozen pre-v1 alias of the public
catalogue. Additive changes (new fields, routes, scopes) land in v1; a breaking change gets a
new prefix, with the old one kept for at least one release. The schema at `/schema/` always
matches the running version.
