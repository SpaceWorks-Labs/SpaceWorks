# Space Works mobile apps — PRD and build plan (Android + iOS)

Version 4 | 2026-11-09 · Owner: Shaan (Space Works) · Builder: app developer

Version 4 adds the release 0.12.0 surfaces (§7 "Release 0.12.0 additions"): contextual
equipment requests and kits, loan context, staff booking price confirmation and readiness,
event venue booking links, related facts, linked event finance, loan repair handoff, shop
pickup moves, personal calendar feeds, member-eligibility refusal copy and the web-only browser
push routes. It also corrects the `X-Makerspace-Id` rule in §7 "Transport". Generate against the
0.12.0 schema: it renames five operation IDs and two enums (listed in that section).

Version 4 changelog (2026-11-09, native-client contract fixes): routes that name the space by
slug now accept a matching `X-Makerspace-Id` (no more "omit it on slug routes" rule); the
member shop order list is typed as the page envelope and the shop order POST is typed as
optional bearer auth, so the hand-decoding workarounds are gone; browser Firebase routes now
answer 403 to a native device token.

This document is **self-contained**. The app developer has **no access to the backend repository**;
everything needed to build the apps is here, in the API schema file shipped with it, and in the public
design repository. Copy this file into both app repos as `docs/PRD.md` and keep the two copies identical.
The owner will supply OpenAPI regenerated after backend reconciliation. Until then, review
endpoint paths and wire fields below; old generated type names/schema may be stale. No rollout
sign-off is implied: notification sending remains held pending conversion/replay verification.

| Repo | Purpose |
|---|---|
| https://github.com/SpaceWorks-Labs/SpaceWorks-Android | Android app — Kotlin |
| https://github.com/SpaceWorks-Labs/SpaceWorks-iOS | iOS app — Swift |
| https://github.com/SpaceWorks-Labs/SpaceWorks-Design | Brand + design system (public) |

---

## 1. What Space Works is

A multi-tenant system for loaning out hardware and running makerspaces. Each **makerspace** has its own
inventory, members, staff roles, bookings, events and payments. The core rule is **traceability of
physical handovers**: every issue and return of hardware produces evidence (QR scan + photo + remark),
and the server enforces it. The apps are **thin clients**: the server decides everything, and the
apps never compute availability, permissions or money.

## 2. Users and scope

| User | In the app |
|---|---|
| **Member** | Browse inventory, request hardware, see loans and due dates, renew, bookings, events (register, ticket QR), membership card, payments (pay dues/charges), notification inbox, profile |
| **Staff** (fixed built-in staff roles) | The SAME person account holding a staff role in a makerspace (release 2); after a staff step-up grant fixed to that makerspace: review, issue/return, direct handout, booking approvals, event check-in and dashboards only when current actions allow |
| **Platform / superadmin** | No native grants. Show "Use the web console" on refusal |

**Release 2: one account per person (clean break, see §7 "Release 2 clean break").** Every
person has ONE account (`kind: "person"`); staff roles are granted to it per makerspace. The
superadmin is a separate `platform` account with no native grants. A person signs in once
(member grant) and, to use staff tools, **steps up** to a staff grant fixed to one makerspace
where they hold a staff role (authenticator + fresh attestation). A member grant never carries
staff authority. A person can participate in several spaces and has a makerspace switcher.
Switching accounts clears tokens, private caches, pending navigation and prior-account push
registrations.

Drive staff UI from `session_authority=native_staff`, grant `authority=staff`, the payload's
`staff_roles` (only the grant's makerspace) and the current action list. The API rechecks every
permission; handle 403. Organization delegates gain no native staff or organization-derived
authority.

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

Source of truth: **https://github.com/SpaceWorks-Labs/SpaceWorks-Design** — add it to each app repo as a git
submodule at `design/` and pin a commit.

| What | Where in the design repo |
|---|---|
| Brand guidelines (PDF) | `brand/space-works-brand-guidelines-v1.pdf` and `brand/guidelines/` |
| UI brand spec | `docs/ui-brand-spec.md` |
| UX specs (screens) | `docs/ux-spec.md`, `docs/ux-screens-longtail.md` |
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
- Typography: Gilroy ExtraBold (800) for display/headings and Outfit (OFL, 400–700) for UI text — only the free Gilroy Light/ExtraBold may ship (owner decision 2026-11-09); Unbounded (500–600) for **one short accent phrase per
  screen** at most. Fonts in the repo are `.woff/.woff2` — **mobile needs `.ttf/.otf`**: convert, and
  **check the Gilroy free EULA (see `frontend/public/fonts/README.md`) before shipping** (raise it with the owner). Until
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

**Release 2 clean break (one account per person, #63; U-A2)** -- apps built for release 1 must
update:
- Removed: the `context` and `makerspace` parameters of password and device login (device login
  now takes `authority` + `makerspace` for a staff grant), the `staff` recovery context, the
  `refresh_token_staff_<slug>` browser cookies, payload `staff_makerspace`.
- Tokens: `kind` is `person` or `platform`; no token carries `makerspace`. Payload: `kind`,
  `is_platform`, `has_staff_role`, `has_elevated_authority`, `staff_roles`, `mfa_grace_ends_at`
  (item 10). The `account_kind` alias was removed from the payload in release 2; read `kind`.
- Staff grants are step-ups on the person (item 6): `POST /auth/device/staff-grant`.
- Every device grant was revoked at the cutover, member grants included (#66): every user signs
  in again; an old refresh gets 401 `session_revoked`.
- Account merges (a person proving a former staff account): `auth-account-merge-start`, `-prove`,
  `-resend`, `-preview`, `-confirm`, `-cancel` (U-C ships them; the route names are fixed).
- `MIN_NATIVE_APP_VERSION_IOS` / `_ANDROID` (x.y.z, numeric per platform): 426
  `native_app_update_required` at device login, the staff step-up and refresh; send `app_version`.
- Remembered devices: every completed device sign-in returns `device_trust`. Store it and send it back
  in the `X-Device-Trust` header on later sign-ins so the unusual-sign-in check knows the device. A
  remembered device never skips the second factor; staff still pass it at every sign-in.
- Event-role desks (judge, mentor, volunteer, crew) open natively through an event grant
  (`POST /auth/device/event-grant`, `session_authority: "native_event"`); see "Event-role desks
  natively" near the end of this document.

### Watch-friendly notifications

There is no separate watch app (#116). Phone notifications are written so they read well when
Apple Watch and Wear OS mirror them, and they carry a few safe action buttons. Push payload **v3**
(release 2, lane L19) adds this on top of v2 without changing any v2 key.

**What a push carries (payload v3).** `data` has string values only:
- the v2 keys, with the same names and meanings: `v` (now `"3"`), `event_id`, `makerspace_id`,
  `feature`, `event`, optional `inbox_row_id`, optional `link`;
- `channel`: the topic, always present (table below);
- `category`: the action set, present only when buttons are allowed (rules below).

Ignore keys you do not know. A missing `v` is v1, `"2"` is v2 and `"3"` is v3. An app built
for v2 keeps working unchanged: it ignores `channel` and `category`. The visible text is:
- **title**: the notice's own subject, at most **40 characters**;
- **body**: at most **120 characters**, cut at a word boundary with an ellipsis;
- staff room alerts keep the space name as their title.

The space is shown through grouping, not the title (thread rules below).

**Categories and actions.** Register these three categories at launch: on iOS as
`UNNotificationCategory` identifiers, on Android as a map you look up `data.category` in. Show
the buttons in this order.

| `category` | Buttons (action identifiers) | When the server sends it |
|---|---|---|
| `sw.open` | `open` | The notice has no inbox row (staff room alerts, or the inbox is off) |
| `sw.inbox` | `open`, `mark_seen` | The notice has an `inbox_row_id` |
| `sw.inbox.snooze` | `open`, `mark_seen`, `snooze` | As above, and the space has inbox snooze (`notifications.inbox_snooze`) on |
| *(absent)* | none; a tap still opens the app | Money and evidence notices (below), unknown events, or the space turned `mobile.watch_actions` off |

What each action calls:
- **`open`** is a foreground action. It does exactly what a tap does: select the makerspace,
  open the supported `link`, else the inbox, else home. It never takes a decision.
- **`mark_seen`** is a background action, so the app does not open. It calls
  `POST /api/v1/notifications/inbox/{makerspace_id}/{inbox_row_id}/read` with the device grant's
  bearer token. That is the same route and audit row as marking the message read in the app.
  - If it fails, fall back to opening the app. Never retry it in a loop.
  - 400 `feature` means the space has the inbox switched off for members. 404 means the row is
    gone.
- **`snooze`** is a background action. It calls
  `POST /api/v1/notifications/inbox/{makerspace_id}/{inbox_row_id}/snooze` with
  `{"until": <now + 1 hour, ISO 8601>}`, the same route the inbox's snooze uses.
  - The server allows any time up to 30 days ahead. The app picks the hour, with no picker on a
    watch.
  - 404 means snooze was switched off since the push left: fall back to opening the app.

Push is not a decision surface, exactly like chat. **No push action approves, rejects, pays,
refunds, issues, returns or hands anything over.** Never add such a button on the app side
either, even when a notice is about one of those things.
- **Money notices** carry no `category`: every `payments` event, the loan charge events
  (`deposit_raised`, `late_fee_raised`, `rental_raised`, `damage_charged`, `lost_charged`,
  `fees_waived`) and the membership payment events (`renewal_due`, `renewal_failed`,
  `awaiting_payment`, `payment_due`, `renewed`).
- **Evidence notices** carry no `category` either: loan `issued`, `partially_returned`,
  `returned`, `closed_with_issue`, `problem_report.filed`, and print `collected`.

**Channels (Android) and threads (iOS).**

| `channel` (Android `channel_id`) | Name to show | Features | iOS `thread-id` |
|---|---|---|---|
| `sw_loans` | Loans | `hardware_requests` | `<makerspace_id>` |
| `sw_bookings` | Bookings | `bookings` | `<makerspace_id>` |
| `sw_events` | Events | `events` | `<makerspace_id>.events` |
| `sw_machines` | Machines and jobs | `printing`, `maintenance`, `devices` | `<makerspace_id>` |
| `sw_membership` | Membership | `members`, `certifications`, `presence` | `<makerspace_id>` |
| `sw_money` | Payments | `payments`, plus the money events above from any feature | `<makerspace_id>` |
| `sw_space` | Space operations | `stock`, `api_access`, anything else | `<makerspace_id>` |

- **iOS:** the server sets `aps.thread-id` and `aps.category`, so the system groups and draws
  the buttons; Apple Watch mirrors both with no watch target. Events get their own subthread
  because an event day can send dozens of notices that would bury loan and booking notices.
- **Android:**
  - Create the seven channels on first launch, with the names above. People mute a topic per
    channel. An unknown or not-yet-created channel falls back to the manifest's default channel.
  - The server sets `android.notification.channel_id` and `tag` = `sw-<event_id>`, so a
    duplicate delivery replaces itself instead of stacking.
  - The server does **not** set `click_action`: a tap opens the launcher activity exactly as in
    v2.
  - FCM notification messages cannot carry buttons. When the app is in the background, the
    system draws the notice without buttons and Wear OS bridges it as is (no app code). When the
    app receives the message itself, build the notification with the `category` buttons and
    `setGroup("sw.<makerspace_id>")`. Wear OS bridges those buttons automatically.
- Deduplicate by `event_id` and refetch the source APIs after any tap or action, exactly as in v2.

**Switch.** `mobile.watch_actions` (under the `mobile` module, **on by default**, #128 C-27)
decides only whether `category` is sent. Off: pushes still arrive, with the same channel,
thread and short text, but no buttons. It is in the space's `enabled_features`, but the app
never has to read it: the server simply omits `category`.

**Minimum app version (C-6a).** `MIN_NATIVE_APP_VERSION_IOS` and `MIN_NATIVE_APP_VERSION_ANDROID`
are `x.y.z` with numeric parts, compared part by part (`1.10.0` is newer than `1.9.3`; never
compare as strings). They are published in `GET /config` as `native.min_app_version`. Below the
minimum, device login, the staff step-up and refresh answer 426 `native_app_update_required`.
Payload v3 does not depend on a minimum: v2 apps keep receiving every push. An operator who
wants every device to show buttons raises the minimum to the first build that registers the
categories.

**Transport**
- HTTPS only (allow `http://10.0.2.2` / `localhost` in debug builds only).
- **Never send `Cookie`, `Origin` or `Referer` headers.** Device routes reject them. iOS: set
  `httpCookieStorage = nil` and `httpShouldSetCookies = false` on the URLSession configuration. Android:
  no `CookieJar`. No WebViews for anything authenticated.
- `Authorization: Bearer <access token>` on every authenticated call.
- `X-Makerspace-Id: <id>` selects the makerspace for makerspace-scoped calls. It must be one where the
  user has an active local membership for staff/member participation surfaces. Core own-charge
  history/payment access can admit an account-only borrower without a membership; use server visibility.
  **Send it only where the server can check it against the route** (a header the server cannot
  match to the route answers 403 "Makerspace target could not be resolved"):
  - **required** on every staff route with a staff grant (it must equal the grant's makerspace and
    any makerspace in the URL), on push registration and on the payment `mobile-intent` call;
  - **allowed** on member routes whose path carries the makerspace
    (`/member/makerspaces/{makerspace_id}/...`); it must then equal that id;
  - **allowed** on routes that name the space by slug: `/public/{makerspace_slug}/...`
    (request submission, contextual requests, kits, member bookings, ...) and
    `/public/m/{makerspace_slug}/shop/...`; it must then be the id of the space that slug
    names, otherwise 403 ("does not match the selected makerspace"). An unknown slug with the
    header answers 403 rather than 404;
  - **omit it** on routes that name no space at all, for example `/member/shop/orders/...`
    (filter with `?makerspace_id=` instead). Member routes never require it unless this
    document says so, so omitting it is always safe there.
- Errors: usually `{ "detail": "...", "code": "..." }`, but not always. Validation errors (400) can be a
  **field dictionary** (`{"field": ["message"]}`), and some framework errors carry only `detail`.
  Parse in this order: `code` → `detail` → field dictionary → generic message by status. 401 auth,
  403 not allowed, 404 not found / not yours, 409 conflict, 429 throttled (respect `Retry-After`),
  503 a dependency is unavailable (retry later, don't crash).
- Lists are paginated: `{ count, next, previous, results }`, 24 per page. Use `next` for infinite scroll.

**Sign-in (device auth)**
1. `POST /auth/device/attestation-challenge` with `{platform, app_id, environment}` → `{challenge, expires_in}`.
2. Produce an attestation over the challenge (available now):
   - Android: Play Integrity **Standard** request with `requestHash = base64url(SHA-256(challenge))`;
     send `{"type":"play_integrity","token":"..."}`.
   - iOS: App Attest with a **fresh key per sign-in**: `generateKey`, then
     `attestKey(keyId, clientDataHash: SHA-256(challenge))`; send `{"type":"app_attest","key_id":"...","attestation":"..."}` (base64 key ID and CBOR attestation).
   - Debug builds use `environment: "development"`. Emulators/simulators send `{"type": "development"}`,
     which only a development server accepts. App Attest needs a real iPhone.
3. `POST /auth/device/login` with credentials + `challenge` + `attestation` → either tokens
   (`access`, `refresh`, grant id, user payload) **or** an MFA challenge → complete MFA via the MFA
   route in the schema.
4. Native Google, Apple and configured OIDC sign-in are available. Use
   `POST /auth/social/nonce` then `/auth/social/google`, `/auth/social/apple` or
   `/auth/social/oidc/{slug}` with `delivery: "device"`, `client_platform: "android" | "ios"`,
   the challenge and attestation. Nonce request: `{provider,surface:"member",delivery:"device",
   client_platform,challenge}` -> `{nonce,expires_in}`. Login request:
   `{id_token,nonce,surface:"member",delivery:"device",client_platform,challenge,attestation,
   authorization_code?,apple_name?}` -> device tokens `{access,refresh,user,device_grant,outcome}`.
   Social sign-in never returns an MFA challenge: the provider's own authentication is the
   proof. Social sign-in issues a member grant; staff tools need the staff step-up (item 6).
   OIDC provider keys use `oidc:{slug}` in the nonce request.
   Apple must use the configured native bundle audience. Supply the authorization code when
   available so the server can revoke Apple credentials on account deletion.
5. Phone OTP is available: `POST /auth/phone/login/start` with
   `{phone, delivery:"device", client_platform:"android"|"ios", challenge}` → `{detail}`;
   `/auth/phone/login/confirm` takes those fields plus six-digit `code` and `attestation`.
   Success is a device-token response or an MFA challenge. Phone sign-in issues a member grant.
   `GET /config` publishes `native: {min_app_version:{android:string|null, ios:string|null},
   providers:{password:boolean, phone:boolean, google:{android_client_id,ios_client_id}|null,
   apple:{enabled:boolean}|null, oidc:[{key,display_name,client_id,issuer}]}}`.
   The native object also contains `app_display_name: string` (deployment-owned, default `SpaceWorks`)
   and `app_identity: {android: {app_id:string, signing_identities:string[]}|null,
   ios: {app_id:string, signing_identities:string[]}|null}`. The Android package and Apple bundle
   come only from approved global production registrations, one per platform/environment; absent
   or invalid configuration yields null. Signers are public normalized Android distribution SHA-256
   digests (1–5 for rotation) or one Apple App ID Prefix. Operators edit the display name in
   `/control/` Platform attestation settings and identity/signers in Native app registrations.
   This is one logical deployment app, independent of tenant branding. Update Android signers on
   the same registration during rotation; revoke an old package/bundle registration before approving
   its replacement. Credential inputs remain write-only, blank preserves the encrypted value, and
   the public contract never includes credentials or verifier configuration keys.
   Read it on launch, show only enabled methods, and require an update below the platform minimum
   (compare dotted numeric components, not strings). Null means no minimum.
6. **Staff grant = a step-up on the person** (release 2). Either sign in with
   `/auth/device/login` sending `authority:"staff"` and `makerspace:"<slug>"` (password +
   authenticator, always an MFA challenge, enrolment when requested), or, from ANY active device
   session (password, Google, Apple, OIDC or phone), call `POST /auth/device/staff-grant` with
   `{makerspace:"<slug>", challenge, attestation, app_version}` (a fresh attestation challenge) and
   finish the returned MFA challenge with `POST /auth/mfa/verify` (no Authorization header). The
   result is a NEW grant with `authority:"staff"` fixed to that makerspace; keep the member grant
   for member screens or sign it out. No staff role there: 403 `staff_access_required` (step-up)
   or a generic 401 (login). Losing the staff role revokes the staff grant (the next call or
   refresh returns 401). Platform accounts cannot hold device grants.
7. `POST /auth/device/refresh` rotates tokens; send `{refresh, app_version}`. **Refresh is
   single-flight**: if two requests 401 at once, only one refresh runs and the others wait for it.
   **Re-using an old refresh token revokes the whole device session** (security feature). Persist the
   new pair atomically before retrying. 401 `session_revoked` means the server's authentication
   generation changed (for example the release-2 cutover): sign in again. 426
   `native_app_update_required` (body has `minimum_version`) means this app is older than
   `MIN_NATIVE_APP_VERSION_IOS`/`_ANDROID`: show the update screen; nothing was rotated.
8. `POST /auth/device/logout` on sign-out. `GET /auth/device/grants` lists devices;
   `DELETE /auth/device/grants/{grant_id}` revokes one.
9. Superadmin accounts are refused (`code: device_superadmin_not_supported`): show
   "Use the web console".
10. `GET /auth/me` = the user payload: `kind:"person"|"platform"`, `is_platform`, `has_staff_role`,
   `has_elevated_authority`, `staff_roles:[{makerspace:{id,slug,name},roles:[{id,slug,name}],actions}]`
   (what THIS session may use: none on a member grant, the fixed makerspace on a staff grant),
   `makerspaces` (one entry per space with `actions` and `tracks: ["community","staff"]`),
   `superadmin_actions`, `mfa_grace_ends_at`, `event_grants` and `session_authority` (`member` |
   `native_staff` | `native_event`).
   Drive the switcher and staff-tool visibility from it, and refetch on app foreground. Show staff
   tools only when `session_authority` is `native_staff` and the action is listed. `account_kind`
   and `staff_makerspace` are gone. Use `has_staff_role` to offer
   the step-up. Refresh never changes grant authority or the fixed staff makerspace.
11. On staff screens, `X-Makerspace-Id` is **mandatory** and must equal any makerspace
    id in the URL. Without it, staff calls are refused.

Device request/response details: the attestation challenge takes
`{platform:"android"|"apple", app_id, environment:"development"|"production"}`.
Password login takes the same fields plus `{username,password,challenge,attestation,
authority?:"member"|"staff",makerspace?:slug,app_version?}` (makerspace required only for staff;
`context` was removed in release 2);
success is `{access,refresh,user,device_grant}`. The grant is
`{id:UUID,platform,app_id,environment,status,authority:"member"|"staff",
staff_makerspace_id:number|null,login_method,attested_at,last_used_at,created_at}`.
MFA returns `{mfa_required,enrollment_required,challenge,expires_in}`; complete
`POST /auth/mfa/verify` with `{challenge,code}` (or enroll/confirm using the schema when
`enrollment_required`). `POST /auth/device/refresh` takes `{refresh}` and returns
`{access,refresh,device_grant}`. Logout takes no body and returns `{detail}`. `GET /auth/device/grants`
is paged like every other list (`{count,next,previous,results}`, 24 per page, `?page=N`);
individual revocation returns 204. All paths in §7 are relative to
`/api/v1` unless written in full. The schema's attestation operation description specifies
the supported proof shapes above. Generate against the reconciled schema; never change Apple
`type:app_attest` or development `type:development` to Android proof to fit an older client.
`DeviceAttestationPayload` is an `anyOf` with one branch per proof (`PlayIntegrityAttestationTypeEnum`,
`AppAttestAttestationTypeEnum`, `DevelopmentAttestationTypeEnum`) plus an open object for
deployment-specific verifiers. Generators that collapse `anyOf` to its first branch make it look
Android-only; model it as a sealed type by hand rather than sending App Attest through the open branch.

**Account settings lists.** `GET /member/makerspaces/{id}/account/sessions` (browser and device
sessions) and `GET /member/makerspaces/{id}/account/exports` (personal data exports) are paged:
pass `?page=N` or follow `next` until it is null.

**Authenticator setup from account settings (members).** `POST /auth/mfa` with `{password}` (or,
for passwordless members, after a fresh linked-social proof or, phone-only, a fresh phone reauth OTP
on this device) returns `{challenge,...}`. Then `POST /auth/mfa/enroll {challenge}` (secret, QR) and
`POST /auth/mfa/confirm {challenge,code}`. Send those two **without** the Authorization header:
starting enrollment invalidates the current tokens, and the challenge is the credential, as on the
web. The result is issued only on the grant that started it, and only to a native caller. Success returns
`{access,refresh,device_grant,user,recovery_codes}` on the **same** grant id; replace the stored
token pair at once. Every other browser session and device is signed out, as on the web. A staff
grant gets 403 `native_staff_mfa_managed` (it is only ever issued behind an enrolled factor). Regenerating recovery codes
or turning MFA off still signs this device out; sign in again afterwards.

**Linking a sign-in provider (members).** Get recent reauth first (`/auth/reauth*`, ten minutes).
Then `POST /auth/social/nonce` with `{provider,surface:"member",delivery:"device",client_platform}`
and **no** challenge (the nonce binds to this grant), sign in with the native provider SDK, and
`POST /auth/social/providers` with `{provider,id_token,nonce,client_platform:"android"|"ios",
apple_name?}`. 403 `recent_reauth_required` means reauthenticate and retry (the nonce is not spent);
401 `social_invalid` means get a new nonce; 409 means the identity belongs to another account; 429
after 10 attempts an hour. One reauth allows one link. GitHub linking stays browser-only. Staff
accounts cannot link providers. Unlinking is `DELETE /auth/social/providers/{provider}`.

**Sign out everywhere — available**
`POST /auth/logout-all` takes no body and returns 200 `{web_sessions:number,devices:number}`.
It revokes browser sessions, device grants, refresh families and their push destinations across
this account on this server and clears its selected context. Other accounts held by the same
person remain independent. Clear all local tokens and session caches after success. This is separate from
single-device logout and needs no selected makerspace or optional module.

**Push notifications — available for members and staff**
- For each active local membership, `POST /integrations/push/devices` with the selected
  `X-Makerspace-Id` and `{token,provider:"fcm"|"apns",environment:"development"|"production"}`.
  Android uses FCM; iOS uses APNs. Success (200 reused / 201 created) returns
  `{id,provider,environment,makerspace_id,active,created_at,updated_at}`; it never returns the token.
  Re-register on OS token changes or new memberships. `DELETE /integrations/push/devices/{device_id}`
  returns 204; leaving a makerspace disables only that makerspace's push subscriptions.
- Member device sessions can read `GET /notifications/inbox/{makerspace_id}` (paginated),
  `/unread-count` → `{count}`, and POST `/{id}/read` → the updated inbox row or
  `/read-all` → `{updated}`. `GET` / `PATCH /notifications/preferences/{makerspace_id}`
  returns `{cells:[{feature,channel,enabled,daily_digest?,available,mandatory_events:string[]}]}`;
  PATCH takes `{feature,channel,enabled,daily_digest?}` and returns the same cells. Inbox rows are
  `{id,feature,event,title,summary,link,read_at:datetime|null,created_at}`.
- Payload `data` has string values: `v:"3"`, `event_id`, `makerspace_id`, `feature`, `event`,
  optional `inbox_row_id`, optional allowlisted `link`, plus v3's `channel` and optional
  `category` (see "Watch-friendly notifications" above for titles, threads, channels and the
  safe actions). Ignore unknown keys and accept missing `v` as v1.
  Canonical `event_id` is stable for the envelope intent; inbox ID is optional. Deduplicate by
  `event_id`; tapping selects an authorized makerspace and opens the supported link, inbox if
  available, or home. Never navigate a staff grant into another tenant.
- Canonical push is an envelope channel with per-device children, independent of inbox creation.
  Recipient policy admits current source-tied member/requester accounts, including account-only
  owners, without the inbox module. Registration still requires an active local membership through
  `X-Makerspace-Id`; do not promise new registration to account-only owners until the owner supplies
  a widened backend/schema contract. Staff use fixed-tenant staff grants. Handle unavailable inbox
  routes separately from push. Disabling the inbox module preserves the canonical adapter;
  tombstoning the whole notifications app removes it.
- Unknown outcomes/expired leases are held without blind resend; definitive rejections may retry
  within the server budget. Apps never retry a notification send. Push is best effort: deduplicate
  by `event_id` and refetch authoritative APIs after tap/foreground.

**Payments — both native rails available**
The provider is selected per makerspace on the server; the app never chooses or receives secrets.
See the operator provisioning section. The Space Manager's web payment settings support both
Stripe and Razorpay, write-only credentials and exact webhook URLs. The native app consumes
the selected rail and public values at runtime.

- `GET /member/makerspaces/{makerspace_id}/payments` -> paginated payment rows:
  `{id,subject_type,subject_label,status,amount:string,currency,due_at:datetime|null,
  due_date:string|null,due_state,checkout_url,online_payment_available,settlement,
  refunded_amount,refunds,created_at}`. Use `online_payment_available` before offering online pay.
  Money is decimal major-unit strings here; keep currencies separate.
- `POST /member/makerspaces/{makerspace_id}/payments/{payment_id}/mobile-intent` takes no body,
  requires an attested device bearer plus matching `X-Makerspace-Id`, and returns 200 with a
  `vendor` discriminator and `payment_id`:
  - `stripe`: `{vendor:"stripe",payment_id,client_secret,publishable_key,customer_id?:string|null,
    ephemeral_key?:string|null}`. Configure PaymentSheet from the returned values; the current
    server returns the two required key/secret fields without customer/ephemeral-key fields.
  - `razorpay`: `{vendor:"razorpay",payment_id,key_id,order_id,amount_minor:number,currency,name,description}`.
    Feed `key_id` as SDK key, `order_id` as Order, and `amount_minor` as the SDK amount;
    do not multiply it again. Currency exponent conversion is server-owned.
- SDK success is a hint. Refetch the payment list and find the same ID until status leaves
  `pending`; there is no member payment-detail or client "mark paid" endpoint.
  `paid_online` / `paid_offline` are settled; `waived` / `canceled` are no longer payable.
  Refunds are separate rows/amounts, not a `refunded` Payment status. A failed attempt can remain
  pending. Keep a processing/retry state and refresh on foreground rather than polling indefinitely.
- 409 `payment_rail_conflict` means a different online rail already owns the charge; finish the
  existing checkout. A charge whose hosted page was created when it was raised is already on the
  hosted rail, so open its `checkout_url` in the system browser rather than the native sheet. 503 `payments_unavailable` means disabled/unconfigured/unreachable online
  payments; offer retry later or desk settlement. A non-pending/not-owned charge can return 404.
- Receipts: `GET /member/makerspaces/{makerspace_id}/payment-documents`, then
  `GET /member/makerspaces/{makerspace_id}/payment-documents/{document_id}/download-url`
  returns `{url,expires_in}` (five-minute user-bound grant). Document list rows are
  `{id,payment,number,kind,issued_at,money_at,amount:decimalString,currency}` in the page envelope.
  History and receipts survive an unavailable online rail.
- Payments are for real-world makerspace services; use the native payment SDKs.

**Personal notification channels and messaging consent**
Paths below are relative to `/api/v1`. Core personal APIs are independent of membership and
optional inbox installation; the account still needs a current tenant tie: membership or owned
loan/request, booking, event registration, machine-service request or charge. Revoked membership
wins over old ownership; restricted, inactive, deleting/retired accounts are refused. Staff use
their person account; staff pushes reach a staff grant only for its fixed makerspace. No
preference grants staff authority. Native
`X-Makerspace-Id` selection currently requires active local membership: do not invent a bypass
for account-only personal APIs if refused. Request a backend update for that app flow.

- Phone verification: `POST /auth/phone/link/start` with `{phone}`, then
  `POST /auth/phone/link/confirm` with `{phone,code}` -> `{phone_e164,verified}`. This is not consent.
- SMS: `GET /me/messaging?makerspace={id}` returns `{sms,whatsapp}`; each contains
  `{available,consented,phone_verified,phone_masked,suppressed}`. The member-only consent write is
  `POST /me/messaging/consent` with `{makerspace:id,channel:"sms",action:"opted_in"|"opted_out"}`
  -> the same whole response. Send no extra fields. Consent binds current phone verification
  instance, sender and configuration generation. Phone A -> B -> A needs fresh consent after
  verification. Opt-out remains available. Staff cannot use this member-only write: never borrow
  a member's phone/consent to show staff an SMS-subscribe control.
- WhatsApp: `POST /integrations/makerspace/{id}/personal/endpoints/start` with
  `{channel:"whatsapp",consent:true,consent_version:"<app consent version>",phone_number?:E164}`
  returns `{challenge_id,expires_at,connect_url?,instructions?,oauth_state?}`. Follow provider
  instructions: only a signed matching inbound code proves the endpoint. Typed numbers, SMS OTP
  and phone login never prove WhatsApp consent. Complete through
  `POST /integrations/makerspace/{id}/personal/challenges/{challenge_id}/verify` using only the
  proof fields in the supplied schema, never destination IDs. Proofs expire in ten minutes and
  consume once. Do not present WhatsApp as an SMS-style toggle.
- `GET /integrations/makerspace/{id}/personal/endpoints` is paginated; endpoint rows include
  `id,channel,provider,integration_generation,verification_state,verified_at,consented_at,
  consent_version,revoked_at,created_at,effective_valid`. Use `effective_valid` for current state.
  `DELETE /personal/endpoints/{endpoint_id}` under that tenant prefix returns `{revoked:true}`.
  Invalidated endpoints can still be disconnected.
- Category choices: `GET/PUT /integrations/makerspace/{id}/personal/preferences`.
  Response `{preferences:[{category,channels:[],email_fallback,available_channels:[]}]}`;
  PUT `{preferences:[{category,channels:[],email_fallback}]}` replaces supplied categories only.
  Submit only edited available categories; empty channels is explicit. Matrix/module, current
  connection/consent and retained legacy false preferences constrain availability. This differs
  from the legacy feature-cell `/notifications/preferences/{id}` inbox editor.
- `GET /integrations/makerspace/{id}/personal/deliveries` is paginated. Rows contain metadata:
  `id,envelope_id,channel,state,attempt_count,next_attempt_at,last_error,retryable,event,feature,
  created_at,updated_at`. Show held outcomes as awaiting reconciliation, never delivered or
  with an app-side resend. No bodies, destinations or credentials are returned.
- Telegram/Slack/Mattermost/Discord use the same start/verify/endpoints routes. OAuth returns
  signed code/state; resolve state with endpoints GET `?oauth_state=...`, then verify the returned
  `oauth_return.challenge_id` for this account. Untrusted query parameters never choose the
  challenge. No browser token/WebView replaces device auth.

STOP suppresses a physical sender/phone or provider alias, including across tenants sharing
one sender. START never subscribes; explicit current proof/consent is required. A delayed proof
cannot lift a newer STOP. Changing accounts must not reuse another account's endpoints. SMS and
WhatsApp modules start off; platform sending also needs operator and tenant opt-in. Neither falls
through to push. Handle 409 conflicts, 410 retired APIs, 423 tenant holds, 429 throttling and 503
cutover/dependency failures with server copy and a fresh read. Sending activation is held until
replay/sign-off. Never expose credentials or use retired messaging-settings/whatsapp-templates APIs.

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

**Account deletion and restore — available**
Self-deletion/90-day archive, restore, purge and Apple revocation are **member-only**. Hide
these controls for staff/platform; staff retirement is an administrator workflow. Member
deletion applies to the whole member account across all makerspaces, separately from leaving
one makerspace. `GET /auth/account/deletion` returns
`{deletable,restorable,restore_reason,blockers:[Blocker],reauth:{required,methods:string[]}}`.
Each Blocker contains `{code,makerspace_id:number|null,makerspace_slug:string|null,
makerspace_member_url:string|null,organization_id:number|null,organization_url:string|null,
count:number,detail:string}`. Display every blocker and its server message; use tenant IDs/slugs
for in-app fix navigation and offer the trusted deployment web console for organization fixes.
Codes currently include `unpaid_charges`, `refund_in_progress`, `refund_under_review`, `deposit_held`, `active_loans`,
`open_requests`, `problem_report_open`, `access_restricted`, `open_service_jobs`,
`upcoming_bookings`, `upcoming_registrations`, `last_manager`, `last_org_governor`,
`makerspace_gated`, `superadmin`. Unknown codes still display `detail`.

Before confirming, show `restorable` and `restore_reason`; do not promise recovery where the server
says none. Deletion immediately archives the account and revokes sessions, memberships and push.
Mutable identity is purged after the retention period (default 90 days); immutable audit, evidence
metadata, loan and financial history remain under the retention/anonymisation policy. It is not an
immediate erasure of every historical record.

- Obtain recent server-owned proof on the current session. `GET /auth/reauth` returns
  `{verified,password_available,mfa_enabled,providers:string[]}`. `POST /auth/reauth`
  takes `{password,code?}`; use the six-digit MFA code when required. Proof lasts ten minutes,
  survives refresh without extending its age, and must be renewed when expired.
- Phone-only accounts: `POST /auth/reauth/phone/start` (no body) → `{sent,token}`, then
  `/auth/reauth/phone/confirm` with `{token,code}`. This is a separate reauthentication OTP,
  not phone-link/login verification.
- Linked social proof: `POST /auth/reauth/social/start` with `{provider,redirect_uri?}` →
  `{authorization_url,state,nonce,expires_in}`; complete `/auth/reauth/social/complete` with
  `{state,nonce,id_token?,code?,totp?}`. Use native provider auth with the returned nonce.
  All proof completions return `{verified,expires_in,mfa_required?,factor_required?,factor_token?}`.
  If a second factor is requested, `POST /auth/reauth/social/factor` with
  `{token:factor_token,code}`. Do not treat email enrollment confirmation as deletion proof.
- When deletable and verified, require the literal confirmation `DELETE` and
  `POST /auth/account/deletion` with `{"confirm":"DELETE"}`. 202 returns `{deleted_at,purge_after}`;
  wipe local tokens/caches and go to sign-in. The server rechecks blockers: 409 returns
  `{blockers:[Blocker]}`. Refetch preview on conflict; handle reauthentication expiry by verifying again.
  A 503 `deletion_retry` means participation changed during locking; retry the preview.

Restore is anonymous and never returns a session. It restores identity only; revoked memberships,
organization roles, sessions and push stay revoked. It refuses at the purge deadline or once any
purge work has started. Always sign in afresh after `{restored:true,detail}` (200).

- Email recovery: `POST /auth/forgot-password` with `{email}` returns `{detail}` uniformly.
  Eligible archived accounts receive a single-use 24-hour restore link. The landing URL is
  `/account/restore#email=...&token=...`; submit `POST /auth/account/restore/email` with
  `{email,token,new_password}`. This landing page stays in the browser (outside verified app-link paths).
- Phone-only recovery: request a new device attestation challenge, then
  `POST /auth/phone/login/start` with `{phone,delivery:"device",client_platform,challenge}`.
  For the restore OTP, `POST /auth/account/restore/phone` takes those fields plus
  `{code,attestation,new_password}`. Uniform start responses never disclose account existence.
- Social-only accounts (no email or phone): `POST /auth/account/restore/social/start` with
  `{username,provider,delivery:"device",client_platform,challenge}` →
  `{authorization_url,state,nonce,expires_in}`. Native restore supports already-linked Apple/Google.
  Obtain fresh provider authentication with that nonce, then POST
  `/auth/account/restore/social/complete` with `{state,nonce,id_token,challenge,attestation}`.
  The proof must show fresh `auth_time` within five minutes. OIDC restore is supported on the web;
  it is not a native restore provider. Invalid/expired/used proofs must start again.

**Deep links — association publishing and push links are available**
Use verified HTTPS universal/app links on the deployment's eligible primary/custom hosts.
Shared-host paths: `/m/{slug}/member`, `/m/{slug}/member/{tab}` (including account),
`/m/{slug}/member/events/{registration}/ticket`, `/m/{slug}/events/{token}`,
`/m/{slug}/bookings/{token}`, `/m/{slug}/items/{item}`. Custom-domain equivalents omit
`/m/{slug}`; the verified host selects the makerspace. Reject staff/admin/control/API paths,
unknown hosts and unsupported destinations. Push `link` must be a local path with no query,
fragment, backslash or scheme; unsupported links open the inbox. The custom scheme
`spaceworks://` is an app fallback, not a server association. Never follow arbitrary push URLs.

**Dashboard and personal usage — available.** Build native Home panels from these contracts;
the web chart panels already use the same services. Staff Home reads
`GET /api/v1/admin/makerspace/{id}/dashboard` with the native staff bearer and matching
`X-Makerspace-Id`. Existing count fields remain; `widgets` contains only authorized
report-backed entries (`key`, `title`, `kind`, `required_action`, `required_modules`,
`report_keys`, `default_period` in local days, `data`, `chart_spec`). Use this server
list rather than mapping roles in the app. Machine data follows assigned machine types;
native sessions gain no organization-derived authority. Handover-only staff receive
`scope_mode: handover`, empty `widgets` and three `queue_tiles`: `ready_to_issue`,
`due_returns`, `pickups`. The app should show this queue home without analytics panels.

Member Home may read `GET /api/v1/member/makerspaces/{id}/my-usage` using the member
bearer. It returns only the caller's loans (count, returned count, currently out and
monthly trend), attributed machine hours (monthly and top machines), bookings (count
and monthly trend), attended events, and payment totals. Each series carries `rows`
and `chart_spec`; money stays grouped by currency. Non-payment sections require an
active membership, the `membership` module and the relevant source modules. When that
gate is off, eligible borrowers still receive `payments` with `usage_available: false`,
even without a membership or online payment rail. Revoked members are refused. There
is no target-member parameter, and this response must be cached only within the current
session/makerspace and cleared on sign-out or makerspace switch. The existing
membership-gated `/activity` contract remains unchanged.

The dashboard endpoint response has required `scope_mode:"full"|"machine"|"handover"`
and optional numeric counters: `upcoming_events`, `pending_event_registrations`, `pending_bookings`,
`upcoming_bookings`, `overdue_loans`, `pending_requests`, `awaiting_issue`, `open_problem_reports`,
`low_stock`, `pending_prints`, `active_prints`, `prints_awaiting_collection`, `failed_emails`,
`stocktakes_awaiting_approval`, `warranty_expiring`, `maintenance_overdue`, `pending_payments`;
optional `outstanding_by_currency:{[currency]:decimalString}`, `widgets` and `queue_tiles`.
Omitted counters are unavailable to this actor; do not turn them into zero-valued tiles.
Each widget's `kind` is `count|trend|top_n|heatmap|queue`; `chart_spec` may be null and `data`
is a report object. Requests to dashboard and my-usage are GETs with no body.

The `/member/makerspaces/{id}/my-usage` response has required `usage_available:boolean`
and optional sections:

| Section | Shape |
|---|---|
| `loans` | `{count,returned_count,currently_out,monthly:Series}` |
| `machines` | `{hours:decimalString,monthly:Series,top_machines:Series}` |
| `bookings` | `{count,monthly:Series}` |
| `events` | `{attended_count,chart:Series}` |
| `payments` | `{paid_by_currency:{[currency]:decimalString},outstanding_by_currency:{[currency]:decimalString},totals:Series}` |

A `Series` is `{rows:[{[field]:value}],chart_spec:ReportChartSpec}`. Monthly loan rows have
`period,issued_count,return_events`; machine monthly rows `period,hours`, top-machine rows
`machine_id,machine,hours`; booking rows `period,count`; event rows `metric,count`; payment rows
`currency,paid_total,outstanding_total`. Missing sections mean gated/unavailable, not zero usage.

**Staff analytics — available within native fixed-tenant staff authority**
`GET /admin/makerspace/{makerspace_id}/reports/catalog` returns `{results:[catalog entry]}`
(no page envelope). Each entry is `{key,title,fields:string[],exportable,summary,
required_modules:string[],available:boolean|null,unavailable_reason:string|null,grains:string[],
chart_hint,chart_spec:ReportChartSpec|null,identity_bearing,aggregate_supported,
allowed_formats:("csv"|"xlsx"|"pdf")[],schedulable,previewable,condition_metrics:string[]}`.
Use this catalog for report visibility, chart fields, supported grains and exports. A null
availability is not a guarantee of access; handle 403/404 from the actual query.

`GET /admin/makerspace/{makerspace_id}/analytics/{report_key}` takes optional
`start=YYYY-MM-DD`, `end=YYYY-MM-DD`, `grain=day|week|month` (only catalog-supported values),
`limit`; dates are tenant-local and end-inclusive. Use the response schema for that endpoint and selected report key.
Most reports expose `rows:[[header,...],[value,...],...]`, optional
`typed_rows:[{field:value,?}]` and optional `meta:{?}`; summary reports can return a flat
object instead. Prefer typed rows, preserve table fallback, and show metadata limitations.
Subject reports use the schema's paired `subject_kind` / `subject_id` only for supported keys.
Reports require the reports module and report/domain actions; identity-bearing detail needs
its additional audit authority. Do not hard-code a role-to-report mapping.

`ReportChartSpec` is `{series:string[],x:{field,kind:"time"|"category"},
values:[{field,unit,kind?:"line"|"stacked_bar"}],currency_field:string|null,
partition:"tenant"|"currency"|"unit"|null,negatives:"allow"|"clip",
truncation:{top_n,other_label}|null,alt_template}`. Use the server fields; partition tenants,
currencies and measurement units as declared. Empty values/null spec means a table, not a
made-up aggregate. Keep negative corrections when `negatives:"allow"`, supply accessible chart
summaries and a full table, and never add currency totals together.

Other built backend analytics surfaces are listed for scope clarity:
`GET /admin/organizations/{organization_id}/analytics/{report_key}` returns
`{report_key,strategy,breakdown:[{makerspace_id,rows:[record]}],total:{rows:[record]},chart_spec?}`;
strategy is `sum|group_sum|row_union|weighted_rate|global_rank|distinct_person`.
Always keep breakdown beside total. Native sessions gain no organization-derived authority;
organization-only staff and organization screens remain outside v1. Superadmin-only
`GET /admin/platform/analytics/{report_key}` (`platform-services|platform-usage`) returns
`{rows,typed_rows?,meta?,report_key?,chart_spec}`; `/admin/platform/analytics/makerspaces`
is a paginated `{id,name,slug}` picker with `report_key` and `page` parameters. These platform
surfaces are web-only because native superadmin sign-in is refused. Hidden service counts
are anonymous; do not try to identify hidden tenants.

### Release 0.12.0 additions

Every route below is under `/api/v1`. "Member" means any device grant of a person
(`X-Makerspace-Id` is optional and must match the space in the path or slug, see
Transport). "Staff" means a native **staff grant** with a matching `X-Makerspace-Id`, **and** the action named; a member grant gets 403 on every staff route
here even if the person holds a staff role, so offer the staff step-up. Event-role grants
(`native_event`) reach none of these routes. The server rechecks every permission, module and
record on each call; a 404 usually means "not available to you" rather than "never existed", so
show a neutral "not available" state. Schema type names are given in brackets.

**Schema renames in 0.12.0 (regenerate).** Five operation IDs were made explicit so they no
longer collide with a numeric suffix, and two hashed enum names were made stable:

| Route | Old operation ID | New operation ID |
|---|---|---|
| GET `/admin/makerspace/{makerspace_id}/equipment-kits` | `api_v1_admin_makerspace_equipment_kits_retrieve` | `api_v1_admin_makerspace_equipment_kits_list` |
| GET `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}` | `api_v1_admin_makerspace_equipment_kits_retrieve_2` | `api_v1_admin_makerspace_equipment_kit_retrieve` |
| GET `/public/{makerspace_slug}/equipment-kits/` | `api_v1_public_equipment_kits_retrieve` | `api_v1_public_equipment_kits_list` |
| GET `/public/{makerspace_slug}/equipment-kits/{kit_id}/` | `api_v1_public_equipment_kits_retrieve_2` | `api_v1_public_equipment_kit_retrieve` |
| POST `/notifications/browser-firebase/{makerspace_id}/may-resume` | `..._may_resume_create_2` | `api_v1_notifications_browser_firebase_space_may_resume_create` (web only) |

`Kind5faEnum` is now `KitLineKindEnum` (`returnable|consumable`) and `Kind47fEnum` is now
`ContextualRequestOutcomeEnum` (`request|consumable_plan`). Other hash-suffixed enum names
(for example `Status219Enum`, `State9e8Enum`) can still change between releases: map them by
their values in a hand-written wrapper, never by the generated type name, and treat an unknown
enum value as "other" instead of failing to decode.

#### Contextual equipment requests and kits (member + staff)

User stories:
- As a member registered for an event (or holding a booking), I ask for the equipment I need
  **for that event or booking**, either item by item or by picking a kit the space published.
- As staff, I raise the same request on behalf of a participant from the event or booking.
- As staff with inventory rights, I maintain kits (named sets of products per person).

| Method + path | Who | Notes |
|---|---|---|
| GET `/public/{makerspace_slug}/equipment-kits/?page=` | Member | Published kits `[PublicKitPage]` |
| GET `/public/{makerspace_slug}/equipment-kits/{kit_id}/` | Member | One kit `[PublicKit]` |
| POST `/public/{makerspace_slug}/requests/contextual` | Member | Submit for yourself `[ContextualSelf]` |
| GET `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-request-products?page=` | Staff | Requestable products for an event `[RequestableProductPage]` |
| GET `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-kits?page=` | Staff | Kits usable for an event `[PublicKitPage]` |
| GET `/admin/makerspace/{makerspace_id}/spaces/{space_id}/equipment-request-products?page=` | Staff | Same for a bookable space |
| GET `/admin/makerspace/{makerspace_id}/spaces/{space_id}/equipment-kits?page=` | Staff | Same for a bookable space |
| POST `/admin/makerspace/{makerspace_id}/equipment-requests/contextual` | Staff | Submit for a participant `[ContextualStaff]` |
| GET/POST `/admin/makerspace/{makerspace_id}/equipment-kits` | Staff, `view_inventory` / `edit_inventory` | List (`?include_archived=true` needs edit) / create |
| GET `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}` | Staff, `view_inventory` | Detail `[KitDetail]` |
| POST `.../equipment-kits/{kit_id}/versions` · `/publication` · `/archive` | Staff, `edit_inventory` | New version / publish for contexts / archive |

Fields:
- `PublicKit {id, name, version, lines:[{product_id, display_name, quantity_per_person,
  kind:"returnable"|"consumable"}]}`. `RequestableProduct {id, name, image_url|null}`.
- Submit body (self): `operation_id` (UUID you generate once per submission and **reuse on
  retry**), `requested_for` (text), exactly **one** of `items:[{product_id, quantity}]` (1–20,
  no duplicates) or `kit:{id, version}`, plus the context: `event_registration_id` (your own
  registration) and/or `booking_token` (your booking's public token), optional
  `pickup_from`/`pickup_until` (ISO datetimes), `waitlist_entry_id`. Send no `website` field
  (it is a bot trap; a filled value gets a fake success).
- Submit body (staff): the same, but `booking_id` instead of `booking_token`, optional
  `borrower_id`, and at least one of `event_registration_id`/`booking_id`. The borrower is the
  registration's or booking's own member.
- Response 201 (new) or 200 (replay of the same `operation_id`):
  `{kind:"request"|"consumable_plan", replayed, public_token?|request_id?, status?, plan_id?}`.
  `kind:"request"` is an ordinary hardware request (it then follows the normal request
  lifecycle in "Request lifecycle"); `consumable_plan` is a consumables-only kit plan.
- Kit bodies: create `{name, lines:[{product_id, quantity_per_person, kind}]}`; version
  `{name, lines, expected_revision}`; publication `{expected_revision, published_for_contexts}`;
  archive `{expected_revision, archived}`. `KitSummary {id, name, revision, current_version,
  published_for_contexts, archived}`. A stale `expected_revision` answers 409: refetch and let
  the user redo the change.

Refusals: 403 with an eligibility `code` (table below), 404 when the space, kit version,
product, registration or booking is not available to you, 409 `{code:"operation_conflict"}`
(the same `operation_id` was used with different content: generate a new one only if the user
changed the request) or `{code:"lock_busy"}` (retry shortly), 423 tenant frozen for migration,
429 throttled, 503 intake temporarily unavailable.

Gating: public inventory (`public_inventory` module plus the space's public site and public
inventory switches) for member routes; returnable lines need the `request_workflow` module and
`loans.enabled`; consumable lines need `inventory.consumables`; event context needs the
`events` module, booking context the `bookings` module; with the `membership` module on the
member needs a current membership term (and presence, waiver, etc. where the space requires
them). Kit management needs the `staff_admin` module.

#### Loan context (staff)

Story: as staff, I link an existing request or direct handout to the event and/or booking it is
for, or remove that link. A context explains purpose only: it never issues, returns, reserves or
changes the borrower.

| Method + path | Notes |
|---|---|
| GET/PUT/DELETE `/admin/makerspace/{makerspace_id}/requests/{request_id}/event-context` | GET takes optional `?intended_event_id=` |
| GET/PUT/DELETE `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/event-context` | Same for a direct handout |
| GET/PUT/DELETE `/admin/makerspace/{makerspace_id}/requests/{request_id}/booking-context` | GET takes optional `?intended_booking_id=` |
| GET/PUT/DELETE `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/booking-context` | Same for a direct handout |

Responses: `EventContextResponse {active, generation:UUID, revision, can_write, event_id?,
may_view_participant?, participant_registration_id?|null}`; `BookingContextResponse {active,
generation, revision, can_write, booking_id?}`. PUT body: `{expected_generation,
expected_revision, event_id, participant_registration_id|null}` or `{expected_generation,
expected_revision, booking_id}`; DELETE body: `{expected_generation, expected_revision}`.
Always send the generation/revision you last read. 409 means someone else changed it, or the
data was restored/imported: show "Review latest state", refetch, and never replay the write
automatically. Hide the editor when `can_write` is false. The participant is omitted unless
`may_view_participant`. Gating: `request_workflow` + `loans.enabled` (self-checkout loans
also `inventory.self_checkout`), plus `events` / `bookings` for each panel; the actor needs the
loan's own action and the event's registration-management or the room's reservation-management
right, for both the old and the new target.

#### Bookings: staff price confirmation, readiness, venue link (staff)

Stories: as staff booking a room for a member, I see the exact price before I confirm and the
booking is refused if the price moved; I see why a booking would be blocked (outage, machine
repair or lockout, missing certification) before I submit; as event staff, I link the event to
its venue booking and replace that booking when the room or time changes.

| Method + path | Who | Notes |
|---|---|---|
| POST `/admin/spaces/{id}/bookings/quote/` | Staff, `manage_reservations` | `{member_id, starts_at, ends_at}` → `StaffBookingQuote` |
| GET `/admin/spaces/{id}/bookings/readiness/?member_id=&starts_at=&ends_at=` | Staff | Before creating → `BookingReadiness` |
| GET `/admin/bookings/{id}/readiness/` | Staff | For an existing booking |
| POST `/admin/spaces/{id}/bookings/` | Staff | Create; send `price_confirmation` from the quote |
| GET/POST `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link` | Staff (events + bookings roles) | Read / link an existing booking |
| POST `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link/replacement` | Staff | Replace the linked booking |

Fields:
- `StaffBookingQuote {charges:"tracked"|"off", quote:PricingQuote|null, price_confirmation:
  64-hex string}`. `PricingQuote` has `currency`, `lines`, `subtotal`, `discount_total`,
  `total` (decimal strings) and `notes`. Show the total and currency; `charges:"off"` means the
  space charges nothing for rooms. Create with the same member, room and window and the
  `price_confirmation`. A moved price answers **409 `price_changed`** with
  `{detail, code, confirmation:{charges, quote, price_confirmation}}`: show the new price and ask
  again; nothing was created and nothing was charged.
- `BookingReadiness {ready, checks:[{code:"room_outage"|"machine_repair"|"machine_lockout"|
  "certification", state:"ok"|"warning"|"blocked", detail, certifications?:[string]}],
  maintenance_link:{machine_id}|null}`. Show `detail` per check; disable confirm while any
  check is `blocked`. Readiness is advisory; the create rechecks.
- Booking link: GET → `DecisionOutput {generation|null, revision, events_epoch, bookings_epoch,
  state:"absent"|"linked"|"booking_unavailable", booking_id|null, billing_owner:"booking"|null,
  event_window?, booking_window?, reservation_state?:"pending"|"confirmed"|"historical"|
  "unavailable", sync?:"matched"|"different"|"unavailable", fee_state?:"none"|"free_no_debt"|
  "configured"|"historical_debt", current_booking_id?, current_status?, replaceable?,
  history?:[{booking_id, status}]}`. POST `{operation_id, expected_generation|null,
  expected_revision, expected_events_epoch, expected_bookings_epoch,
  confirm_billing_owner:"booking", existing_booking_id}` (all copied from your last GET; the
  user must explicitly confirm that the booking, not the event, bills the room). Replacement
  `{expected_booking_id, space_id, member_id, starts_at, ends_at, note?, price_confirmation}` →
  201 `{booking_id, replaces_booking_id, status:"pending"|"confirmed"}`; get the
  `price_confirmation` from the quote route for the new room. The original booking is never
  edited.
- Refusals: 400 validation, 403, 404, 409 (stale revision/epochs or `price_changed`), 423, 429, 503.

Gating: `bookings` module (and `events` for the link); readiness machine checks need
`machines.maintenance`; prices exist only when booking charges are tracked.

#### Related facts and linked event finance (staff, read-only)

| Method + path | Notes |
|---|---|
| GET `/admin/makerspace/{makerspace_id}/related-facts/events/{event_id}` | `{subject, registrations?, attendance?, presence?}` |
| GET `/admin/makerspace/{makerspace_id}/related-facts/bookings/{booking_id}` | `{subject, arrival?, presence?, machine_sessions?}` |
| GET `/admin/makerspace/{makerspace_id}/finance/events/{event_id}/linked` | `{event_id, sections}` |

Story: as event or booking staff, I see the counts around a subject (registrations by status,
check-ins, arrivals, overlapping presence and machine sessions) and the event's money in one
place (registration charges, venue fee, the booking's room charge, reimbursements, payouts,
budget). Every section is **omitted** when its module/capability is off or I lack its authority:
absent means "not shown", never zero. Money is per currency (`currencies:[...]`); never add
currencies, and never add the booking room charge (`read_only:true`, owned by bookings) to the
event's own totals. Finance needs `finance.ledger`; sections also need `events.venue_fees`,
`bookings`, `event_reimbursements` or event charge tracking as applicable. Presence and machine
sections need their own modules (`bookings.checkin`, `machines` + `machines.sessions`).

#### Loan repair handoff (staff)

| Method + path | Notes |
|---|---|
| GET `/admin/makerspaces/{makerspace_id}/requests/{request_id}/repairs` | `{request_id, lines:[LoanRepairLine]}` |
| POST same path | `{accountability_id, note?}` → 201 (new) / 200 (already handed off) `{created, issue_id, line}` |

Story: after a return recorded damage, the area manager (Inventory Manager or Space Manager)
hands each damaged line to repairs once. Needs `inventory.repairs`; with it off there is no
handoff and the route is refused (hide the panel).
`LoanRepairLine {accountability_id, request_item_id|null, product_name, quantity, asset_id|null,
asset_tag, remark, evidence_id|null, issue:{id, state, title, priority, quote_state,
quote_amount|null, quote_currency, parts, to_buy_items, created_at, fixed_at, closed_at,...}|null}`.
The POST is idempotent per line. It never changes the loan, its evidence or any charge.

#### Shop: event pickup moved to the space

POST `/admin/shop/orders/{id}/move-pickup-to-space/` (staff with shop sell rights, no body) moves
an event-pickup order whose event can no longer hand it over to the makerspace counter and
returns `ShopStaffOrder` (`pickup_at:"space"|"event"`, `pickup_event`, `status`, totals...).
Members see the change in `GET /member/shop/orders/` (optional `?makerspace_id=`, `?page=`) and
`/member/shop/orders/{id}/`. Members place orders with `POST /public/m/{makerspace_slug}/shop/orders/`:
**send the bearer token** so the order belongs to the account (the schema marks the route's
auth as optional bearer because guests may also order with an emailed code; a signed-in person
is always the buyer when the token is present). Order status values: `held, awaiting_payment,
paid, ready, collected, cancelled, unfulfilled, refunded`. The order list answers the standard
page envelope `[ShopBuyerOrderPage] {count, next, previous, results:[ShopBuyerOrder]}`, and the
schema types it that way.

#### Personal calendar feeds (member)

| Method + path | Notes |
|---|---|
| GET/POST/DELETE `/member/makerspaces/{makerspace_id}/calendar-feeds/{kind}/` | `kind` = `shifts` or `combined` |
| GET/POST/DELETE `/member/makerspaces/{makerspace_id}/event-calendar-feed/` | POST body `{confirm_bearer_risk:true}` |
| GET/POST/DELETE `/public/{makerspace_slug}/my-bookings/calendar/` | Bookings feed |

Story: I subscribe my phone calendar to my shifts, my events or my bookings. GET returns
`{enabled, token_hint|null, created_at?, rotated_at?}`; POST issues (or rotates) and returns
`{feed_url, token_hint}` **once**; DELETE revokes it. The `feed_url` is a secret: show it
only right after POST, hand it to the OS calendar subscription (`webcal://` or the calendar
intent), never store, log or share it, and drop it when the account or makerspace changes.
Rotating invalidates the old URL. The user must accept the "anyone with this link can see
these entries" warning before POST.

#### Eligibility refusal codes and copy (member)

The server's 403 member-eligibility refusals carry a `code`, sometimes as a one-element list
(`{"code":["membership_required"]}`); read the first string in that case. Show this copy (the
same as the web app), and fall back to `detail` for unknown codes:

| `code` | Show |
|---|---|
| `membership_required` | This needs an active membership of this space. Join or renew from your member area, or ask space staff if you think your membership should be active. |
| `membership_inactive` | Your membership of this space is not active. Ask space staff to review it. |
| `membership_lapsed` | Your membership term has ended. Renew your membership from your member area, then try again. |
| `waiver_acceptance_required` | Accept the space's current waiver in your member area, then try again. |
| `presence_required` | Check in at the space first (in your member area or at the front desk), then try again. |
| `borrower_restricted`, `member_restricted` | Your account is restricted at this space. Talk to space staff to resolve it. |
| `certification_required` | You need machine training or certification first (*names from `certifications`*). Ask space staff how to qualify, then try again. (Omit the brackets when `certifications` is empty.) |
| `machine_intake_unavailable` | Online machine requests aren't available here. Ask space staff for help. |
| `organization_audience_required` | This event is open to members of its participating organizations. Ask your organization to confirm your membership, or contact the organizers. |
| `organization_audience_not_ready` | Staff must review this event's audience before registration opens. Try again later or contact the organizers. |
| `organization_audience_disabled` | This event isn't taking organization registrations right now. Contact the organizers. |
| `organization_audience_changed` | This event's audience changed. Reload the page to check whether you can still register. |
| `invitation_expired` | This invitation has expired. Ask an organization governor to send a new one. |
| `invitation_revoked` | This invitation was withdrawn. Ask an organization governor if you should still have access. |
| `invitation_redeemed` | This invitation has already been used. If that wasn't you, tell an organization governor. |
| `invitation_grant_changed` | The person who invited you no longer holds all of the access they offered. Ask an organization governor to send a new invitation. |
| `organization_membership_suspended` | Your membership of this organization is suspended. Ask an organization governor to reactivate it. |

These apply on every member action that checks eligibility (requests, contextual requests and
kits, bookings, event registration and ticket orders, machine requests). Organization invitation
redemption itself stays web-only (native member grants are refused there).

#### Event-desk issue and return (staff evidence rules)

Equipment handed out at an event desk uses the **same** issue/return routes and evidence rules
as any loan; a loan context never relaxes them. With a staff grant holding the handout actions:
1. Upload the issue photo: `POST /admin/makerspaces/{makerspace_id}/uploads/evidence-url` with
   `{evidence_type, content_type, size_bytes?}`, upload as described in "Evidence photos", keep
   `evidence_id`.
2. Reviewed request: once accepted (by staff holding the review action), assign the box by
   scanning its QR (`POST /admin/requests/{id}/assign-box` `{box_code}`), then
   `POST /admin/requests/{id}/issue` with `{evidence_id, asset_qr_payloads?, kit_checklist?,
   remark?}`. Direct handout at the desk: `POST
   /admin/makerspace/{makerspace_id}/direct-loans` with `{borrower_id, evidence_id, qr_payloads
   or container_id, items?, kit_checklist?, remark?}`, then link it to the event with the
   direct-loan `event-context` PUT above.
3. Return: a new return photo plus a non-empty remark: `POST /admin/requests/{id}/return` (or the
   handover-only `/guest-admin/requests/{id}/return`) with `{evidence_id, box_code, remark,
   resolutions:[...], kit_checklist?}`.
No photo, no scan or no remark means no submit: the UI must block it, and the server refuses it
anyway. Evidence notices (`issued`, `returned`, ...) carry no push action buttons. An event-role
grant (`native_event`, judges/crew/volunteers) cannot issue or return; the person must step up
to a staff grant.

#### Notifications: browser push is web-only

`/notifications/browser-firebase/*` (config, challenge, confirm, may-resume) and
`/notifications/browser-alerts/*` are the **web** browser-push enrolment and must not be called
by the apps; the browser-firebase routes answer 403 to any native device token. Native push
stays `POST /integrations/push/devices` (FCM on Android, APNs on iOS) as described in "Push notifications". A person can have both; the server delivers to each
channel independently and the apps deduplicate by `event_id` as before.

#### Polling and caching guidance for these screens

None of these routes return `ETag` or `Last-Modified`; do not send conditional requests.
Context, kit and booking-link reads carry `revision`/`generation`/epochs: use them as the change
marker and for every write. Related facts, linked finance, readiness and repairs have no change
marker: refetch on screen open, pull-to-refresh and app foreground, never on a timer. All lists
here use the standard page envelope except `checks`, `lines` and `history`, which are bounded
arrays inside one object.

## 8. Phases

Each phase ends with **tests green in CI, a commit (or a few small ones) per repo, and a short phase
note** in `docs/CHANGELOG.md`. No phase starts until the previous one is merged.
Use the owner-supplied regenerated reconciliation schema before dependent phases. Deployment
credentials, provider round trips and notification replay/activation remain operator checks;
an older 2026-10-17 schema is not the reconciled contract.

| Phase | Content | Backend dependency |
|---|---|---|
| **A0 Base** | Repo scaffold, CI, brand theme from tokens, white-label config, generated API client, networking core (headers, errors, pagination, single-flight refresh skeleton), server-URL screen, app shell with empty tabs | none — **start now** |
| A1 Sign-in | Attestation, password + MFA, Google/Apple/OIDC, token storage, refresh, logout, makerspace switcher, `/auth/me`, superadmin refusal screen, min-version gate | available - password/social/phone, attestation, native config and staff authority |
| A2 Member — read | Inventory browse/search/detail, my requests & loans with due dates, bookings, events, member dashboard/activity + my-usage, membership card, inbox (read/unread) | none |
| A3 Member — act | Submit hardware request, renew loan, book, register/cancel event + ticket QR, profile edit, notification preferences, phone verification and SMS/WhatsApp consent; 0.12.0: equipment for an event/booking (items or kit), calendar feeds, eligibility refusal copy (§7 "Release 0.12.0 additions") | none |
| A4 Push + deep links | Device registration, notification tap routing, universal/app links, watch-friendly categories and channels (payload v3, §7) | available - member/staff push and association files; owner configures hosts |
| A5 Payments | Payments list, Stripe PaymentSheet, Razorpay Checkout, receipts/documents | available - Stripe PaymentSheet and Razorpay Orders; server provisioning in §7 |
| A6 Staff | Pending requests accept/reject, QR scanner, issue (QR + photo), return (photo + remark), direct handout, booking approvals, event check-in, role dashboard and authorized analytics; 0.12.0: event-desk issue/return with loan context, contextual requests for participants, staff booking quote/readiness, read-only related facts and linked finance, repair handoff, shop pickup move (kit editing and booking-link/replacement are optional) | available - native staff grants and scoped APIs |
| A7 Account + store readiness | Device sessions list/revoke, leave/cancel membership, **delete account** (blocker list → fix links → re-auth → confirm, §7), privacy labels, accessibility pass, localisation-ready strings | available - deletion, identity-only restore and logout-all |
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

Follow the [native mobile integration operator guide](../mobile-integration.md) for every server-side
/control/ value and the separate build-input handoff (Cloud project number, Firebase file, entitlements
and link-contract manifest paths).

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

Superadmin/control-plane features, organization-derived native staff authority (staff use a
staff step-up grant of their own person account, fixed to one makerspace where they hold a staff role), kiosk and printer device protocols, offline mode beyond showing cached data read-only,
tablets-specific layouts, GitHub sign-in. A member's own attendance reply
(`/events/{id}/attendance/`) and crew sign-up (`/events/{id}/crew-signup/`) work natively.

**Event-role desks natively (#173, L21b).** A person with an active event role (judge, mentor,
volunteer or crew lead: a live event staff grant) steps a device session up with
`POST /api/v1/auth/device/event-grant` (`event_id`, a fresh attestation `challenge`, `attestation`,
`app_version`) and finishes through `auth/mfa/verify`, exactly like the staff step-up. The new grant
has `authority: "event"`, `event_id`, and `session_authority: "native_event"`; it reaches only that
event's admin programme routes (`/api/v1/admin/events/{event_id}/...`: judging, score next, crew desk,
review stages, mentor and volunteer tools) and never a staff route. Send no `X-Makerspace-Id` on those
routes. `/auth/me` lists `event_grants` on every native session (an event grant: only its event), so
the app can offer the step-up. The grant is revoked when the role ends (expect 401 and fall back to the
member grant). The cross-event "my application reviews" list stays web-only. A native member grant may
redeem an event staff invite (`/api/v1/admin/event-staff-invites/redeem/`).
