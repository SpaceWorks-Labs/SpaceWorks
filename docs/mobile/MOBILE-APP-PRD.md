# Space Works mobile apps — PRD and build plan (Android + iOS)

Version 2 · 2026-10-17 · Owner: Shaan (Space Works) · Builder: app developer + Codex

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
| **Staff** (any role a makerspace gives them: Space Manager, Inventory Manager, Machine Manager, Handover and combinable fixed built-in roles) | Everything a member sees **plus** the staff tools their role allows: review requests (accept/reject), QR scan, issue/return with evidence photo, direct handout, booking approvals, event check-in |
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
  user has an active local membership for staff/member participation surfaces. Core own-charge
  history/payment access can admit an account-only borrower without a membership; use server visibility.
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
   authorization_code?,apple_name?}` -> `SocialLoginResponse` (device tokens or MFA challenge).
   OIDC provider keys use `oidc:{slug}` in the nonce request.
   Apple must use the configured native bundle audience. Supply the authorization code when
   available so the server can revoke Apple credentials on account deletion.
5. Phone OTP is available: `POST /auth/phone/login/start` with
   `{phone, delivery:"device", client_platform:"android"|"ios", challenge}` → `{detail}`;
   `/auth/phone/login/confirm` takes those fields plus six-digit `code` and `attestation`.
   Success is a `DeviceTokenResponse` or the schema's MFA challenge. Phone sign-in is member-only.
   `GET /config` publishes `native: {min_app_version:{android:string|null, ios:string|null},
   providers:{password:boolean, phone:boolean, google:{android_client_id,ios_client_id}|null,
   apple:{enabled:boolean}|null, oidc:[{key,display_name,client_id,issuer}]}}`.
   Read it on launch, show only enabled methods, and require an update below the platform minimum
   (compare dotted numeric components, not strings). Null means no minimum.
6. Staff device sessions are available. Password/social login snapshots staff capability for active
   local staff memberships; phone login never grants it. A member promoted after login must sign in again.
7. `POST /auth/device/refresh` rotates tokens. **Refresh is single-flight**: if two requests 401 at
   once, only one refresh runs and the others wait for it. **Re-using an old refresh token revokes the
   whole device session** (security feature). Persist the new pair atomically before retrying.
8. `POST /auth/device/logout` on sign-out. `GET /auth/device/grants` lists devices;
   `DELETE /auth/device/grants/{grant_id}` revokes one.
9. Superadmin accounts are refused (`code: device_superadmin_not_supported`): show
   "Use the web console".
10. `GET /auth/me` = the user payload: identity + per-makerspace memberships with `actions`. Drive the
   makerspace switcher and all staff-tool visibility from it, and refetch on app foreground.
   The payload includes `session_authority`. Show staff tools only when it is
   `native_staff` **and** the membership has the action. Phone sign-in never gets staff tools, and a member
   who was given a staff role after signing in must sign in again.
11. On staff screens, `X-Makerspace-Id` is **mandatory** and must equal any makerspace
    id in the URL. Without it, staff calls are refused.

Device request/response details: the attestation challenge takes
`{platform:"android"|"apple", app_id, environment:"development"|"production"}`.
Password login takes the same fields plus `{username,password,challenge,attestation}`;
success is `{access,refresh,user,device_grant}`. The grant is
`{id:UUID,platform,app_id,environment,status,attested_at,last_used_at,created_at}`.
MFA returns `{mfa_required,enrollment_required,challenge,expires_in}`; complete
`POST /auth/mfa/verify` with `{challenge,code}` (or enroll/confirm using the schema when
`enrollment_required`). `POST /auth/device/refresh` takes `{refresh}` and returns
`{access,refresh,device_grant}`. Logout takes no body and returns `{detail}`. Grant lists
are a bare array; individual revocation returns 204. All paths in §7 are relative to
`/api/v1` unless written in full. The schema's attestation operation description specifies
all three proof types above; its shared generated `type` enum currently collapses to
`play_integrity`. Use its open-object proof alternative for Apple/development rather
than changing their wire `type` to the Android value.

**Sign out everywhere — available**
`POST /auth/logout-all` takes no body and returns 200 `{web_sessions:number,devices:number}`.
It revokes browser sessions, device grants, refresh families and their push destinations across
this server. Clear all local tokens and session caches after success. This is separate from
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
- Payload `data` has string values: `v:"2"`, `event_id`, `makerspace_id`, `feature`, `event`,
  member-only `inbox_row_id`, and optional allowlisted `link`. The title is the makerspace name;
  iOS uses the makerspace thread ID. Ignore unknown keys and accept missing `v` as v1.
  Deduplicate by `event_id`; tapping selects the makerspace, then opens a supported link or its inbox.
- Member push follows personal member-audience inbox rows and respects membership, module,
  tenant channel matrix, requester selection and personal preferences. Account-only inbox readers
  without an active local membership do not receive push. Staff have their own operational push path.
  Push is best effort and may duplicate: always refetch the authoritative API after a tap/foreground.

**Payments — both native rails available**
The provider is selected per makerspace on the server; the app never chooses or receives secrets.
See §9 for operator provisioning. The server's current settings UI/API exposes Stripe setup only;
Razorpay backend/native support exists but needs operator provisioning before an app can use it.

- `GET /member/makerspaces/{makerspace_id}/payments` → paginated `MemberPayment` rows:
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
  existing checkout. 503 `payments_unavailable` means disabled/unconfigured/unreachable online
  payments; offer retry later or desk settlement. A non-pending/not-owned charge can return 404.
- Receipts: `GET /member/makerspaces/{makerspace_id}/payment-documents`, then
  `GET /member/makerspaces/{makerspace_id}/payment-documents/{document_id}/download-url`
  returns `{url,expires_in}` (five-minute user-bound grant). Document list rows are
  `{id,payment,number,kind,issued_at,money_at,amount:decimalString,currency}` in the page envelope.
  History and receipts survive an unavailable online rail.
- Payments are for real-world makerspace services; use the native payment SDKs.

**SMS / WhatsApp member consent and phone verification — available**
- Authenticated `POST /auth/phone/link/start` takes `{phone}` → `{detail}`.
  `POST /auth/phone/link/confirm` takes `{phone,code}` (six digits) →
  `{phone_e164,verified:boolean}`. This verifies the signed-in account's phone; it does not opt in.
- `GET /me/messaging?makerspace={id}` → `{sms:Channel,whatsapp:Channel}` where each Channel is
  `{available:boolean,consented:boolean,phone_verified:boolean,phone_masked:string,suppressed:boolean}`.
  `POST /me/messaging/consent` takes `{makerspace:id,channel:"sms"|"whatsapp",
  action:"opted_in"|"opted_out"}` and returns the same whole response. Send no extra fields.
- Show one consent switch per channel. Require verified phone and channel availability to opt in;
  allow opt-out. Verification, membership and personal notification preferences are separate
  from consent. Consent is specific to the current number and makerspace. Changing the number
  needs fresh verification/consent. Provider STOP suppression may also block delivery/re-consent;
  show the server's reason for 409/423/503 and refetch instead of assuming a toggle succeeded.
- These settings require an active local membership, but remain accessible when the optional
  `membership` or `notifications` module is off. `sms` and `whatsapp` are independent opt-in
  modules and do not fall through to push. Never expose staff sender credentials in member UI.

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
Deletion applies to the whole account on this server across all makerspaces, separately from leaving
one makerspace. `GET /auth/account/deletion` returns
`{deletable,restorable,restore_reason,blockers:[Blocker],reauth:{required,methods:string[]}}`.
Each Blocker contains `{code,makerspace_id:number|null,makerspace_slug:string|null,
makerspace_member_url:string|null,organization_id:number|null,organization_url:string|null,
count:number,detail:string}`. Display every blocker and its server message; use tenant IDs/slugs
for in-app fix navigation and offer the trusted deployment web console for organization fixes.
Codes currently include `unpaid_charges`, `refund_in_progress`, `deposit_held`, `active_loans`,
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

The dashboard response (`Dashboard`) has required `scope_mode:"full"|"machine"|"handover"`
and optional numeric counters: `upcoming_events`, `pending_event_registrations`, `pending_bookings`,
`upcoming_bookings`, `overdue_loans`, `pending_requests`, `awaiting_issue`, `open_problem_reports`,
`low_stock`, `pending_prints`, `active_prints`, `prints_awaiting_collection`, `failed_emails`,
`stocktakes_awaiting_approval`, `warranty_expiring`, `maintenance_overdue`, `pending_payments`;
optional `outstanding_by_currency:{[currency]:decimalString}`, `widgets` and `queue_tiles`.
Omitted counters are unavailable to this actor; do not turn them into zero-valued tiles.
Each widget's `kind` is `count|trend|top_n|heatmap|queue`; `chart_spec` may be null and `data`
is a report object. Requests to dashboard and my-usage are GETs with no body.

`MemberUsage` has required `usage_available:boolean` and optional sections:

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

**Staff analytics — available within native local-membership authority**
`GET /admin/makerspace/{makerspace_id}/reports/catalog` returns `{results:[ReportCatalogItem]}`
(no page envelope). Each entry is `{key,title,fields:string[],exportable,summary,
required_modules:string[],available:boolean|null,unavailable_reason:string|null,grains:string[],
chart_hint,chart_spec:ReportChartSpec|null,identity_bearing,aggregate_supported,
allowed_formats:("csv"|"xlsx"|"pdf")[],schedulable,previewable,condition_metrics:string[]}`.
Use this catalog for report visibility, chart fields, supported grains and exports. A null
availability is not a guarantee of access; handle 403/404 from the actual query.

`GET /admin/makerspace/{makerspace_id}/analytics/{report_key}` takes optional
`start=YYYY-MM-DD`, `end=YYYY-MM-DD`, `grain=day|week|month` (only catalog-supported values),
`limit`; dates are tenant-local and end-inclusive. Use the generated `AnalyticsReportResponse`
union for the selected key. Most reports expose `rows:[[header,...],[value,...],...]`, optional
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

## 8. Phases

Each phase ends with **tests green in CI, a commit (or a few small ones) per repo, and a short phase
note** in `docs/CHANGELOG.md`. No phase starts until the previous one is merged. All backend
dependencies below are available in the supplied 2026-10-17 schema; app implementation and deployment credentials still need verification.

| Phase | Content | Backend dependency |
|---|---|---|
| **A0 Base** | Repo scaffold, CI, brand theme from tokens, white-label config, generated API client, networking core (headers, errors, pagination, single-flight refresh skeleton), server-URL screen, app shell with empty tabs | none — **start now** |
| A1 Sign-in | Attestation, password + MFA, Google/Apple/OIDC, token storage, refresh, logout, makerspace switcher, `/auth/me`, superadmin refusal screen, min-version gate | available - password/social/phone, attestation, native config and staff authority |
| A2 Member — read | Inventory browse/search/detail, my requests & loans with due dates, bookings, events, member dashboard/activity + my-usage, membership card, inbox (read/unread) | none |
| A3 Member — act | Submit hardware request, renew loan, book, register/cancel event + ticket QR, profile edit, notification preferences, phone verification and SMS/WhatsApp consent | none |
| A4 Push + deep links | Device registration, notification tap routing, universal/app links | available - member/staff push and association files; owner configures hosts |
| A5 Payments | Payments list, Stripe PaymentSheet, Razorpay Checkout, receipts/documents | available - Stripe PaymentSheet and Razorpay Orders; provisioning limitation in §7 |
| A6 Staff | Pending requests accept/reject, QR scanner, issue (QR + photo), return (photo + remark), direct handout, booking approvals, event check-in, role dashboard and authorized analytics | available - native staff grants and scoped APIs |
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

Superadmin / control-plane features, organisation-only staff (staff must hold a membership of the
makerspace), kiosk and printer device protocols, offline mode beyond showing cached data read-only,
tablets-specific layouts, GitHub sign-in.
