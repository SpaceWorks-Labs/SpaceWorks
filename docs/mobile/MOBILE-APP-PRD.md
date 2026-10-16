# Space Works mobile apps — PRD and build plan (Android + iOS)

Version 1 · 2026-10-16 · Owner: Shaan (Space Works) · Builder: app developer + Codex

This document is **self-contained**. The app developer has **no access to the backend repository**;
everything needed to build the apps is here, in the API schema file shipped with it, and in the public
design repository. Copy this file into both app repos as `docs/PRD.md` and keep the two copies identical.

| Repo | Purpose |
|---|---|
| https://github.com/SpaceWorks-HQ/SpaceWorks-Android | Android app — Kotlin |
| https://github.com/SpaceWorks-HQ/SpaceWorks-iOS | iOS app — Swift |
| https://github.com/SpaceWorks-HQ/SpaceWorks-Design | Brand + design system (public) |

---

## 1. What Space Works is

A multi-tenant system for lending hardware and running makerspaces. Each **makerspace** has its own
inventory, members, staff roles, bookings, events and payments. The core rule is **traceability of
physical handovers**: every issue and return of hardware produces evidence (QR scan + photo + remark),
and the server enforces it. The apps are **thin clients**: the server decides everything, and the
apps never compute availability, permissions or money.

## 2. Users and scope

| User | In the app |
|---|---|
| **Member** | Browse inventory, request hardware, see loans and due dates, renew, bookings, events (register, ticket QR), membership card, payments (pay dues/charges), notification inbox, profile |
| **Staff** (any role a makerspace gives them: Space Manager, Inventory Manager, Machine Manager, custom handover roles) | Everything a member sees **plus** the staff tools their role allows: review requests (accept/reject), QR scan, issue/return with evidence photo, direct handout, booking approvals, event check-in |
| **Superadmin** | **Not supported.** The server refuses to sign a superadmin in on a phone. Show "Use the web console" |

**One app** serves both. Staff tools appear only when the signed-in user's role in the **selected
makerspace** grants the action (from the `actions` list in the user payload). The server still
enforces every permission, so hiding a button is just UX; a 403 must always be handled gracefully.

A user can belong to several makerspaces. The app has a **makerspace switcher**, and every request is
made "as" the selected makerspace.

## 3. What you get, and what you do not

You get:
- `api/openapi.json` — the OpenAPI 3 schema of the backend (**the contract**). Generate the API client
  from it; never hand-write request/response models.
- A **staging server URL** and **test accounts** (one member, one staff with handover actions, one
  Space Manager) on a demo makerspace — supplied privately by the owner.
- The design repo (public).
- For push / attestation / payments: the owner configures the server side; you get the **app-side**
  identifiers (bundle IDs, Firebase config, Stripe/Razorpay publishable keys come from the server at runtime).

You do **not** get backend access. When you need an API change, open an issue in the app repo with the
label `backend-request` describing the screen, the data you need, and why. The owner ships it and sends
an updated `openapi.json`. Never work around a missing endpoint by scraping web pages or using a WebView.

## 4. Brand and design

Source of truth: **https://github.com/SpaceWorks-HQ/SpaceWorks-Design** — add it to each app repo as a git
submodule at `design/` and pin a commit.

| What | Where in the design repo |
|---|---|
| Brand guidelines (PDF) | `brand/space-works-brand-guidelines-v1.pdf` and `brand/guidelines/` |
| UI brand spec | `docs/ui-brand-spec.md` |
| UX specs (screens) | `docs/ux-yuyu-spec.md`, `docs/ux-screens-longtail.md` |
| Colour + theme tokens | `tokens/tokens.json` (light + dark), `tokens/tokens.css` |
| Logo lockups, symbol, app icon | `logo/` (`app-icon.svg`, `symbol-*`, `lockup-*`) |
| Icons | `icons/` |
| Fonts + licences | `fonts/` + `fonts/LICENSES/`, read `fonts/README.md` |

Rules:
- Generate the native theme **from `tokens/tokens.json`** with a small script (Compose `ColorScheme` +
  Kotlin constants; SwiftUI `Color` extension), not by copying hex values by hand. Light **and** dark.
- Brand palette: deep ink `#142C2A`, maker teal `#006E63`, workshop orange `#FF7447`, citron, sky blue,
  warm yellow, warm cream `#FFF4E8` — use the semantic roles from the tokens (bg, surface, panel, ink,
  muted, accent, emphasis…), not raw brand colours.
- Typography: Gilroy (400–700) for UI and display; Unbounded (500–600) for **one short accent phrase per
  screen** at most. Fonts in the repo are `.woff/.woff2` — **mobile needs `.ttf/.otf`**: convert, and
  **check the Gilroy licence permits app embedding before shipping** (raise it with the owner). Until
  cleared, fall back to the platform font.
- Accessibility floor: dynamic type / font scaling, ≥ 4.5:1 text contrast, 44pt / 48dp touch targets,
  TalkBack/VoiceOver labels on every control, no colour-only status.

## 5. White-label (self-hosters rebrand the app)

Self-hosted Space Works deployments publish **their own branded build**. One build = one deployment.
Everything brand-specific lives in one file, `branding/brand.json`, plus asset files next to it:

```json
{
  "app_name": "Space Works",
  "android_application_id": "org.spaceworks.app",
  "ios_bundle_id": "org.spaceworks.app",
  "ios_team_id": "XXXXXXXXXX",
  "server_url": null,
  "support_url": "https://…",
  "privacy_url": "https://…",
  "theme_tokens": "design/tokens/tokens.json",
  "app_icon": "branding/app-icon.svg"
}
```

- `server_url: null` → the app asks for the server URL on first launch (official build). A URL → the
  app is locked to that server (white-label build).
- Android: Gradle reads `brand.json` → `applicationId`, `app_name` resource, icon. iOS: a script writes
  `Brand.xcconfig` (bundle ID, display name, team) consumed by the project.
- **Never commit** `google-services.json`, signing keys or `.p8` keys. CI injects them from secrets.
- A `docs/WHITE-LABEL.md` in each repo explains, step by step, how a self-hoster rebrands, signs and
  publishes (their own Apple/Google accounts, Firebase project, APNs key).

## 6. Tech stack

**Android (Kotlin)** — min SDK 26, target the SDK level Google Play currently requires.
Jetpack Compose + Material 3 (custom theme from tokens), Navigation Compose, Kotlin coroutines/Flow,
Retrofit + OkHttp + kotlinx.serialization with a client generated by **openapi-generator**
(`kotlin`, `jvm-retrofit2`, `kotlinx_serialization`), token storage encrypted with an Android Keystore key,
Play Integrity API, Firebase Cloud Messaging, CameraX + ML Kit barcode scanning, Stripe Android SDK
(PaymentSheet), Razorpay Android Checkout SDK. Tests: JUnit, MockWebServer, Compose UI tests.
Keep dependencies to this list unless a phase needs more. Write down why in the PR.

**iOS (Swift)** — iOS 17+. SwiftUI, Swift concurrency, Swift Package Manager, Apple
**swift-openapi-generator** + URLSession transport, Keychain token storage, App Attest
(`DCAppAttestService`), **APNs directly** (no Firebase on iOS), VisionKit `DataScannerViewController`
(AVFoundation fallback), Stripe iOS SDK (PaymentSheet), Razorpay iOS SDK. Tests: Swift Testing / XCTest.
**The Xcode project is generated by XcodeGen from `project.yml`**, so it is reviewable text, and CI
runs `xcodegen generate`. Never commit a hand-edited `.xcodeproj`.

**CI (GitHub Actions)** — Android: ubuntu runner, `./gradlew lint test assembleDebug` on every push.
iOS: **macOS runner**, `xcodegen generate` + `xcodebuild test` on a simulator on every push. If the iOS
developer has no Mac, CI is the compiler: no iOS phase is done until CI is green.

## 7. API contract essentials

Base URL = server URL + `/api/v1/` (a few public catalogue routes are under `/api/`). The schema file
is authoritative. These are the rules the schema cannot express:

**Transport**
- HTTPS only (allow `http://10.0.2.2` / `localhost` in debug builds only).
- **Never send `Cookie`, `Origin` or `Referer` headers.** Device routes reject them. iOS: set
  `httpCookieStorage = nil` and `httpShouldSetCookies = false` on the URLSession configuration. Android:
  no `CookieJar`. No WebViews for anything authenticated.
- `Authorization: Bearer <access token>` on every authenticated call.
- `X-Makerspace-Id: <id>` selects the makerspace for makerspace-scoped calls. It must be one where the
  user has an active membership (from the user payload).
- Errors: usually `{ "detail": "...", "code": "..." }`, but not always. Validation errors (400) can be a
  **field dictionary** (`{"field": ["message"]}`), and some framework errors carry only `detail`.
  Parse in this order: `code` → `detail` → field dictionary → generic message by status. 401 auth,
  403 not allowed, 404 not found / not yours, 409 conflict, 429 throttled (respect `Retry-After`),
  503 a dependency is unavailable (retry later, don't crash).
- Lists are paginated: `{ count, next, previous, results }`, 24 per page. Use `next` for infinite scroll.

**Sign-in (device auth)**
1. `POST /auth/device/attestation-challenge` with `{platform, app_id, environment, ...}` → `{challenge, expires_in}`.
2. Produce an attestation over the challenge (exact payload shape lands with backend 1a):
   - Android: Play Integrity **Standard** request with `requestHash = base64url(SHA-256(challenge))`;
     send the integrity token.
   - iOS: App Attest with a **fresh key per sign-in**: `generateKey`, then
     `attestKey(keyId, clientDataHash: SHA-256(challenge))`; send `{key_id, attestation}` (base64).
   - Debug builds use `environment: "development"`. Emulators/simulators send `{"type": "development"}`,
     which only a development server accepts. App Attest needs a real iPhone.
3. `POST /auth/device/login` with credentials + `challenge` + `attestation` → either tokens
   (`access`, `refresh`, grant id, user payload) **or** an MFA challenge → complete MFA via the MFA
   route in the schema.
4. Google and OIDC providers **already work on devices**: the social login routes take
   `delivery=device` plus the attestation challenge (see the schema). Google uses the Android / iOS client
   ids the server publishes. **Native Sign in with Apple has a server bug that backend 1a fixes**. Build
   it, but expect it to fail against the server until then.
5. **Planned (backend 1a):** phone OTP with `delivery=device` (member-only, never staff), and a `native`
   block in the public `GET /config` with `min_app_version` per platform and the sign-in providers and
   client ids. Read `/config` on launch: render only the sign-in methods it lists and block the app with
   an "update required" screen when below `min_app_version`.
6. **Staff tools need a staff device session (planned, backend 1a).** A grant created by password or
   social sign-in for a user who holds a staff role becomes staff-capable. Phone sign-in never does.
   Until 1a ships, staff endpoints answer 403 to the app.
7. `POST /auth/device/refresh` rotates tokens. **Refresh is single-flight**: if two requests 401 at
   once, only one refresh runs and the others wait for it. **Re-using an old refresh token revokes the
   whole device session** (security feature). Persist the new pair atomically before retrying.
8. `POST /auth/device/logout` on sign-out. `GET /auth/device/grants` lists devices;
   `DELETE /auth/device/grants/{grant_id}` revokes one.
9. Superadmin accounts are refused (`code: device_superadmin_not_supported`, planned): show
   "Use the web console".
10. `GET /auth/me` = the user payload: identity + per-makerspace memberships with `actions`. Drive the
   makerspace switcher and all staff-tool visibility from it, and refetch on app foreground.
   **Planned (1a):** a `session_authority` field. Show staff tools only when `session_authority` is
   `native_staff` **and** the membership has the action. Phone sign-in never gets staff tools, and a member
   who was given a staff role after signing in must sign in again.
11. **Planned (1a):** on staff screens, `X-Makerspace-Id` is **mandatory** and must equal any makerspace
    id in the URL. Without it, staff calls are refused.

**Push notifications**
- Registration is **per makerspace**: after sign-in, for **each** makerspace the user is an active member
  of (and again whenever the OS token changes or a membership is added),
  `POST /integrations/push/devices` with that makerspace selected, the token, the provider (**Android =
  FCM, iOS = APNs**) and the environment (debug builds = development). Keep the returned ids. On logout or
  leaving a makerspace: `DELETE /integrations/push/devices/{id}`.
- Members' inbox and preferences (`/notifications/inbox/…`, `/notifications/preferences/…`) become
  reachable from a member phone session in backend 1a. Until then they answer 403.
- Payload `data` today: `feature`, `event`, `makerspace_id`. **Planned, backend 1b (v2):**
  `v: "2"`, `event_id`, `makerspace_id`, `feature`, `event`, optional `inbox_row_id`, optional `link`
  (an in-app path). The title becomes the makerspace name. iOS notifications are grouped per makerspace
  (`thread-id`). Tapping opens `link`, else the makerspace inbox. Ignore unknown keys. Handle a missing `v`
  as version 1.
- Push is a **hint**: always refetch from the API (inbox: `/notifications/inbox/{makerspace_id}`).
- Members will receive push for their own events (loan approved, due soon, booking confirmed…) once
  backend 1b ships. Staff already receive operational alerts.

**Payments** (Stripe **or** Razorpay — the makerspace's Space Manager chooses; the app never decides)
- Member payments: `GET /member/makerspaces/{id}/payments`.
- To pay: `POST /member/makerspaces/{id}/payments/{payment_id}/mobile-intent`. The response has
  `vendor` (**planned, backend 1c**; today Stripe only):
  - `stripe` → present Stripe **PaymentSheet** with the returned client secret / publishable key.
  - `razorpay` → open Razorpay Checkout with `key_id`, `order_id`, amount, currency.
- The app **never** marks anything paid. After the sheet closes, poll the payment until its status
  leaves `pending`. `paid_online` and `paid_offline` are both paid. Treat any other non-pending
  status (waived, refunded, cancelled… per the schema enum) as "no longer payable" and show it as-is.
  While still pending, show "processing".
- 409 `payment_rail_conflict` → the charge was started on the web. Tell the member to finish it there.
  503 `payments_unavailable` → online payment can't be used right now (switched off **or** the provider is
  unreachable). Offer "try again later" and "pay at the desk".
- Card payments for makerspace services are real-world services, so no Apple/Google in-app purchase.

**Evidence photos (staff issue/return)**
- Request an upload (`/admin/makerspaces/{id}/uploads/evidence-url`), then upload exactly as the
  response says:
  - **`method` absent (the usual case):** multipart **POST** to the returned URL with **every** returned
    `fields` entry, then the file as the last part.
  - **`method: "PUT"`:** PUT the raw bytes to the URL with every returned header.
  
  Servers differ, so never hard-code either one. Then pass the returned evidence id to the issue/return call.
- **Upload JPEG only** (convert HEIC on iOS), resize to ≤ 2048 px long edge, strip location EXIF.
  Allowed types: jpeg, png, webp. Keep files under 10 MB. The response doesn't state the limit yet, and an
  oversized upload is rejected by storage.
- Issue needs a **box/tool QR scan + photo**. Return needs a **photo + remark**. The server enforces it,
  and the UI should make it impossible to submit without them.

**Request lifecycle** (show these states and only the actions the schema offers):
`draft → pending_approval → rejected | accepted → issued → partially_returned | returned | closed_with_issue`.

**Account deletion** (planned, backend 1d — required by both stores; the blocker list below is the
intended shape, final codes ship with 1d)
- Deletes the **whole Space Works account on this server, across every makerspace**. It is not
  "leave this makerspace" (that already exists per makerspace).
- `GET /auth/account/deletion` → `{deletable, blockers: [{code, makerspace_id, count, detail}]}`.
  Show every blocker with a button that takes the user to the screen that fixes it. Codes:
  `unpaid_charges` (pay everything first), `refund_in_progress`, `deposit_held`, `active_loans` (return all
  hardware), `open_requests`, `accountability_open`, `open_service_jobs`, `upcoming_bookings`,
  `upcoming_registrations`, `last_manager` (hand the makerspace to another manager), `organization_owner`,
  `superadmin`. Unknown codes: show `detail` as-is.
- Only when `deletable` is true: re-authenticate (password, or OTP/MFA for passwordless accounts),
  type a confirmation, `POST /auth/account/deletion`. On success wipe tokens and local data and return
  to the start screen. The server re-checks the blockers and may still answer 409 with a fresh list.
- Explain on the screen: payment and loan history is kept anonymised (legal and accounting records).

**Deep links** — universal links / app links on the server domain (planned with push, phase A4) and a
custom scheme fallback `spaceworks://`. All links are **in-app paths**. Never open arbitrary external
URLs from a push or a link.

## 8. Phases

Each phase ends with **tests green in CI, a commit (or a few small ones) per repo, and a short phase
note** in `docs/CHANGELOG.md`. No phase starts until the previous one is merged. Phases marked
**⏳ backend** wait for the owner to ship that backend phase and send a new `openapi.json`.

| Phase | Content | Backend dependency |
|---|---|---|
| **A0 Base** | Repo scaffold, CI, brand theme from tokens, white-label config, generated API client, networking core (headers, errors, pagination, single-flight refresh skeleton), server-URL screen, app shell with empty tabs | none — **start now** |
| A1 Sign-in | Attestation, password + MFA, Google/Apple/OIDC, token storage, refresh, logout, makerspace switcher, `/auth/me`, superadmin refusal screen, min-version gate | password + social: none (attestation in production needs 1a). Phone, `/config` native block: ⏳ 1a |
| A2 Member — read | Inventory browse/search/detail, my requests & loans with due dates, bookings, events, member dashboard/activity, membership card, inbox (read/unread) | none |
| A3 Member — act | Submit hardware request, renew loan, book, register/cancel event + ticket QR, profile edit, notification preferences | none |
| A4 Push + deep links | Device registration, notification tap routing, universal/app links | ⏳ 1b (+ link files on server) |
| A5 Payments | Payments list, Stripe PaymentSheet, Razorpay Checkout, receipts/documents | Razorpay: ⏳ 1c |
| A6 Staff | Pending requests accept/reject, QR scanner, issue (QR + photo), return (photo + remark), direct handout, booking approvals, event check-in | ⏳ 1a (staff device session) |
| A7 Account + store readiness | Device sessions list/revoke, leave/cancel membership, **delete account** (blocker list → fix links → re-auth → confirm, §7), privacy labels, accessibility pass, localisation-ready strings | deletion: ⏳ 1d |
| A8 Release | White-label guide, TestFlight + Play closed test, store listings, reviewer demo account | — |

### A0 Base — detail (the first thing to build)

Done when, in **each** repo:
1. Project builds in CI (Android ubuntu, iOS macOS), with lint and unit tests running.
2. `design/` submodule added. A theme generator script turns `tokens/tokens.json` into native theme
   code (light + dark), with a unit test asserting a few token values.
3. `branding/brand.json` drives app name, bundle/application ID and icon. A test checks the build reads it.
4. `api/openapi.json` committed, the client generated at build time (not committed), and a script to
   re-generate it.
5. Networking core: base URL from settings/brand, `Authorization` and `X-Makerspace-Id` injection,
   cookies disabled, `{detail, code}` error mapping, pagination helper, a single-flight refresh
   coordinator (unit-tested with a fake server: N concurrent 401s → exactly 1 refresh call).
6. Screens: server-URL entry (validates by calling `/api/v1/health/`), sign-in placeholder, tab shell
   (Home, Inventory, Activity, Inbox, Profile; a Staff tab hidden by default), light/dark, font scaling.
7. `AGENTS.md` in the repo (copy §10 below) and `docs/WHITE-LABEL.md` skeleton.

## 9. Things the owner provides or manages (not the developer)

- Apple Developer Program (organisation, needs a D-U-N-S number) and Google Play Console accounts.
- Bundle IDs, App Attest + Push capabilities, APNs key, Firebase project (Android FCM), Play Integrity
  API enabled and linked, signing keys (Play App Signing upload key, Apple certificates). All held as CI
  secrets, never in the repo.
- Staging server, test accounts, demo makerspace (also used as the store reviewers' demo account).
- Privacy policy URL, App Store privacy labels, Play Data safety answers (camera, photos, push token,
  location if presence check-in is added, payments).
- Stripe / Razorpay accounts live on the **server**, per makerspace. The app needs no secrets.

## 10. How to run this with Codex — two agents

Run **two Codex agents in parallel**, one per repo. They never edit each other's repo.

| | Agent A — Android | Agent B — iOS |
|---|---|---|
| Repo | `SpaceWorks-Android` | `SpaceWorks-iOS` |
| Owns | everything in that repo | everything in that repo |
| Verifies with | `./gradlew lint test assembleDebug` locally + CI | CI (macOS) — `xcodegen generate && xcodebuild test` |

Rules for both agents (put this in each repo's `AGENTS.md`):
1. `docs/PRD.md` is the spec. If it and the code disagree, the PRD wins. If the PRD is unclear,
   **stop and ask**. Don't invent API fields.
2. Only the generated client talks to the server. Never hand-write models. Never call an endpoint that
   is not in `api/openapi.json`.
3. Work one phase at a time. For each phase: plan → implement → tests → CI green → commit(s) → phase
   note in `docs/CHANGELOG.md`. Small commits, imperative one-line messages, e.g.
   `feat(a0): theme generated from design tokens`. Add `Co-Authored-By: Codex <noreply@openai.com>` to
   commits Codex wrote.
4. **Parity**: same screens, same names, same flows, same error copy on both platforms. At the end of
   each phase, each agent writes a parity checklist (screens and states covered) into the phase note.
   The human compares the two.
5. Tests per phase: unit tests for every view model / state holder and the networking core, a
   MockWebServer / URLProtocol stub test for every API call used, and UI tests for the phase's main flow.
   A phase with failing or skipped tests is not done.
6. Secrets: none in the repo, ever. No analytics or third-party SDKs beyond §6 without asking.
7. Accessibility and dark mode are part of "done" in every phase, not a final polish pass.

### Kick-off prompt — Agent A (Android)

> You are building the Space Works Android app in this repo (`SpaceWorks-Android`). Read `docs/PRD.md`
> fully. Implement **phase A0 Base** exactly as specified in §8 "A0 Base — detail", using the Android
> stack in §6 and the rules in §10. Add the design repo as a submodule at `design/`, generate the theme
> from `design/tokens/tokens.json`, wire `branding/brand.json`, generate the API client from
> `api/openapi.json`, build the networking core with a tested single-flight refresh coordinator, the
> server-URL screen and the tab shell, and a GitHub Actions workflow running lint, unit tests and a debug
> build. Commit per logical step, finish with all tests green, write the A0 phase note with a parity
> checklist, and list anything in the PRD you found ambiguous.

### Kick-off prompt — Agent B (iOS)

> You are building the Space Works iOS app in this repo (`SpaceWorks-iOS`). Read `docs/PRD.md` fully.
> Implement **phase A0 Base** exactly as specified in §8 "A0 Base — detail", using the iOS stack in §6
> and the rules in §10. Use XcodeGen (`project.yml`). Add the design repo as a submodule at `design/`,
> generate the SwiftUI theme from `design/tokens/tokens.json`, wire `branding/brand.json` through a
> generated `Brand.xcconfig`, generate the API client with swift-openapi-generator from
> `api/openapi.json`, build the networking core (cookies disabled) with a tested single-flight refresh
> coordinator, the server-URL screen and the tab shell, and a GitHub Actions macOS workflow running
> `xcodegen generate` and `xcodebuild test`. Commit per logical step, finish with CI green, write the A0
> phase note with a parity checklist, and list anything in the PRD you found ambiguous.

For later phases, reuse the same prompt with the phase name, e.g. "Implement **phase A2 Member — read**".

## 11. Out of scope (v1)

Superadmin / control-plane features, organisation-only staff (staff must hold a membership of the
makerspace), kiosk and printer device protocols, offline mode beyond showing cached data read-only,
tablets-specific layouts, GitHub sign-in.
