# Decisions: Mobile apps and API

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-358 — Mobile auth follow-ups
- **Area:** mobile-api
- **Date:** 12 November
- **Decision:** Native GitHub sign-in uses authorization code with PKCE and an HTTPS universal link/App Link callback on the deployment domain, with a single-use state bound to device attestation. Native passkeys use the deployment's public web domain as RP id. Restricted/suspended accounts reach only own-charge routes and sign-out, everything else keeping typed `account_restricted` / `account_suspended` 401s.
- **Why:** Avoid custom-scheme callbacks, and let restricted members still see and pay their debt.
- **Status:** partly superseded by D-361

### D-356 — Platform screens stay web-only
- **Area:** mobile-api
- **Date:** 12 November
- **Decision:** Superadmin/platform screens remain web-only: native device grants refuse superadmin accounts and the platform surface keeps its browser-origin allow-list. The operations are listed as web-only with reasons.
- **Why:** Reduce the attack surface of the highest-privilege role.
- **Status:** current
- **Implemented in:** `docs/mobile/MOBILE-API-0.12.0.md`

### D-355 — Mobile auth parity first
- **Area:** mobile-api
- **Date:** 12 November
- **Decision:** Native auth covers every enabled sign-in method (password, email code, phone OTP, passkeys, social via PKCE or ID-token exchange), signup and reset, MFA with step-up, refresh rotation with reuse detection, device grants, account deletion and export, and typed restricted/suspended and 429 responses with no enumeration.
- **Why:** Every parity fix sits on the shared auth path, so it comes first.
- **Status:** current

### D-353 — Web and native API parity
- **Area:** mobile-api
- **Date:** 12 November
- **Decision:** Every API operation the web app calls must be callable with a native device token under the same authority checks (role, scope, MFA/step-up, device grant). Exceptions are only inherently browser-only mechanics, each listed with its reason, and a parametrised test walks the inventory.
- **Why:** Mobile should not be a second-class client.
- **Status:** current
- **Implemented in:** `docs/mobile/MOBILE-API-0.12.0.md`

### D-352 — Mobile API completeness for 0.12.0
- **Area:** mobile-api
- **Date:** 12 November
- **Decision:** Every 0.12.0 member and staff feature a phone app should offer has a typed OpenAPI route that a native device token can call without widening authority (native sessions stay membership-only for organization authority). The mobile PRD and integration doc list the additions.
- **Why:** Native apps are built against the API contract alone.
- **Status:** current
- **Implemented in:** `docs/mobile/MOBILE-API-0.12.0.md`

### D-346 — Native apps are released via GitHub Releases
- **Area:** mobile-api
- **Date:** 12 November
- **Decision:** The native Android and iOS apps are described as released and are distributed through GitHub Releases only (landing links go to each repository's latest release), with no store buttons.
- **Why:** The maintainer chose GitHub Releases rather than app-store distribution.
- **Status:** current

### D-196 — Personal access tokens and OAuth app connections
- **Area:** mobile-api
- **Date:** 5 November
- **Decision:** People create named personal tokens with scopes limited to what they may do (default 90-day expiry, max one year, shown once, stored hashed, MFA re-auth to create). A Space Manager or superadmin can register OAuth 2.0/OIDC apps (authorization code with PKCE, refresh rotation, consent screen, connected-apps list), using a maintained library and the same scope vocabulary as API clients. Per-space HMAC API clients stay for server-to-server use. Only backend support was built, no third-party apps. Platform/superadmin accounts cannot hold personal tokens or connect OAuth apps, a deliberate security exception to D-190.
- **Why:** A leaked superadmin token would be platform-wide.
- **Status:** current
- **Implemented in:** `backend/apps/apiclients/models_tokens.py`, `backend/apps/apiclients/oauth_provider.py`, `docs/api-guide.md`

### D-193 — Complete OpenAPI and API clients
- **Area:** mobile-api
- **Date:** 5 November
- **Decision:** Every route has documented request, response, auth and error schemas guarded by a test, with Swagger, ReDoc and the schema working on every deployment. Every route is deliberately in or out of the API-client scope registry (unknown routes stay denied), Space Managers manage their own HMAC API clients with chosen scopes (audited, rate-limited), and a space may expose public catalogue, events and stats read-only to another space's system. An API guide documents it all.
- **Why:** Other makerspaces' backends and scripts need a finished, safe API surface.
- **Status:** current
- **Implemented in:** `backend/apps/apiclients/scope_registry.py`, `docs/api-guide.md`, `docs/api-client-protocol.md`

### D-173 — Event-role holders and native apps
- **Area:** mobile-api
- **Date:** 2 November
- **Decision:** People holding only event roles (judge, mentor, volunteer, crew) cannot use their desks in native apps because member grants refuse delegated authority. The planned contract is an event-scoped step-up grant limited to that event's programme routes, with `event_grants` in the native payload; until then those desks are web-only.
- **Why:** Member grants refusing delegated authority is deliberate (D-162).
- **Status:** current

### D-116 — Watch-friendly push notifications
- **Area:** mobile-api
- **Date:** 27 October
- **Decision:** There is no separate watch app. Push notifications are made watch-friendly with short titles and bodies, a category with safe action buttons (Open, Mark seen; never money or evidence actions) and iOS thread grouping, documented for the app builder.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `docs/mobile`
