"""OpenAPI and API-client settings for release 2 (#193), applied at the end of settings.py.

Kept out of settings.py (the accepted size exception) so the schema contract has one home:
the project schema class, the tag-group hook, the security schemes Swagger UI's
"Authorize" dialog offers, a same-origin server so "Try it out" reaches THIS deployment on
self-host and managed alike, and the credential-management throttle.
"""

DESCRIPTION = """\
The SpaceWorks API: one deployment, many makerspaces. Full guide: `docs/api-guide.md`
in the repository (getting a client, scopes, signing in Python/JS/curl, pagination,
errors, webhooks, rate limits and versioning).

## Authorise

* **People (staff and members)** send `Authorization: Bearer <access>`. Get an access
  token from `POST /api/v1/auth/login` (or a social/passkey/phone sign-in), refresh it
  with `POST /api/v1/auth/refresh`. Staff routes also need staff MFA. In this page, press
  **Authorize** and paste the access token under `jwtAuth`.
* **API clients** (another system: a university ERP, a script, another space's backend)
  are created by a Space Manager under *Settings -> API access*, with chosen scopes. A
  server client signs every request: `X-Client-Id`, `X-Timestamp`, `X-Nonce` and
  `X-Signature = hex(HMAC-SHA256(secret, METHOD\\nFULL_PATH\\nTIMESTAMP\\nNONCE\\nBODY))`.
  Swagger UI cannot compute a signature, so use the guide's snippets for signed calls.
  A browser client sends `X-Client-Id` from a registered `Origin`; a public site can
  send `X-Publishable-Key`.
* **Personal access tokens** (#196): a person creates one at `/account/api-access` (MFA
  re-auth, scopes no wider than their own permissions, 90-day default expiry) and sends
  `Authorization: Bearer swpat_...`. Never accepted on sign-in, credential or platform routes.
* **App connections** (OAuth 2.0 authorization code + PKCE, under `/api/v1/oauth/`): an app a
  Space Manager registered under *API access* asks the person to consent, then sends its
  access token as `Authorization: Bearer <token>`; refresh tokens rotate on every use.
* Public routes under `/api/v1/public/` answer anonymously until the operator turns on
  `API_CLIENT_AUTH_REQUIRED`.

## Conventions

* **Versioning:** everything lives under `/api/v1/`; `/api/public/` is the frozen
  pre-v1 alias of the public catalogue. Breaking changes get a new version prefix.
* **Pagination:** lists answer `{count, next, previous, results}` (page size 24, `?page=`);
  signed integration reads use `{next_cursor, results}` with `?cursor=`.
* **Errors:** `{"detail": "...", "code": "..."}` with the HTTP status; validation errors
  map each field to its messages.
* **Rate limits:** `429` with `Retry-After`. API clients are limited per client by tier.
"""

SECURITY_SCHEMES = {
    "ServerHMAC": {
        "type": "apiKey", "in": "header", "name": "X-Signature",
        "description": "Signed server or peer API client: HMAC-SHA256 over METHOD, full path, "
                       "timestamp, nonce (when sent) and raw body, with X-Client-Id, X-Timestamp "
                       "and X-Nonce. See docs/api-client-protocol.md.",
    },
    "BrowserClient": {
        "type": "apiKey", "in": "header", "name": "X-Client-Id",
        "description": "Browser API client: its client id, sent from one of its registered Origins. "
                       "Identifies the frontend; never raises a rate tier.",
    },
    "PublishableKey": {
        "type": "apiKey", "in": "header", "name": "X-Publishable-Key",
        "description": "A space's publishable key for its own public site.",
    },
}

TAGS = [
    {"name": "Event roles", "description": "Volunteer, crew and contributor roles, shifts and sign-ups."},
    {"name": "Evidence", "description": "Private evidence photos: upload URLs and detail."},
]


def apply(rest_framework, spectacular, env):
    rest_framework["DEFAULT_SCHEMA_CLASS"] = "apps.openapi_contract.schema.SpaceWorksAutoSchema"
    rest_framework["DEFAULT_THROTTLE_RATES"]["api_client_manage"] = env(
        "THROTTLE_API_CLIENT_MANAGE", default="120/hour")
    spectacular["DESCRIPTION"] = DESCRIPTION
    spectacular["SERVERS"] = [{"url": "/", "description": "This deployment (same origin as these docs)"}]
    spectacular["SWAGGER_UI_SETTINGS"] = {
        "persistAuthorization": True, "filter": True, "displayRequestDuration": True,
    }
    spectacular["APPEND_COMPONENTS"].setdefault("securitySchemes", {}).update(SECURITY_SCHEMES)
    spectacular["TAGS"] = [*spectacular.get("TAGS", []), *TAGS]
    spectacular["POSTPROCESSING_HOOKS"] = [
        *spectacular["POSTPROCESSING_HOOKS"], "apps.openapi_contract.tags.add_tag_groups",
    ]
