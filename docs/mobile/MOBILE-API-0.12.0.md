# Mobile API parity, Release 0.12.0

Audience: the Android and iOS app developers, and whoever continues this audit. Companion to
[the mobile PRD](MOBILE-APP-PRD.md) ("Release 0.12.0 additions", "Sign-in on mobile",
"Payments on mobile") and [the integration notes](../mobile-integration.md).

Scope (owner decisions 353 to 355): every API operation the web app calls must be callable by a native
device token with exactly the same checks as the web session (member, staff, space manager, platform),
with payments and sign-in covered end to end. This file is the working record: what was verified, what was
fixed, what is still open. The two generated tables at the end are rebuilt by the scripts in
`handover/reports/mobile-parity/` (see "How to regenerate").

## How native tokens are admitted (verified in code)

- Every view uses the one default authenticator (`SpaceWorksJWTAuthentication`). No view relies on
  session cookies, CSRF or `request.session`, so a bearer token is never refused for a cookie reason. Views
  that set `authentication_classes = []` (username check, public discovery, signed device protocols) ignore
  the bearer entirely.
- Route gate (`accounts/surface_policy.enforce_request`): a native **member** grant reaches the member
  surface (`/member/`, `/public/`, `/auth/`, `/memberships/`, `/integrations/push/`, the personal
  `/notifications/inbox|preferences|announcements/`) and routes classed member-only. It never reaches a
  delegable route (organization or resource-grant authority is web-only).
- A native **staff** grant is fixed to one makerspace. Every staff route (`/admin/...`, classed
  membership-only or delegable) needs `X-Makerspace-Id` equal to that space, MFA verified at sign-in, and the
  route's own role and module checks. The server must also be able to *resolve the route's makerspace*
  (path `makerspace_id`, an object lookup, a body field or a token). A staff route whose space cannot be
  resolved answers 403 "Makerspace target could not be resolved". This is where native access was actually
  missing, and where the fixes below sit.
- Send `X-Makerspace-Id` only on space-scoped routes. On global routes (`/member/profile`, `/auth/...`,
  `/handles/check`) leave it out.
- Native sessions never carry organization-derived authority. Platform (superadmin) screens are **web-only by
  owner decision 356**: a superadmin never holds a phone token (`DeviceSuperadminNotSupported` and the platform
  browser-origin allow-list stay as they are), so the superadmin's optional MFA and any platform step-up are
  web-only too. The 71 platform operations in the table below are marked web-only for that reason.

## Fixes made in this pass

| Fix | Files | Effect |
|---|---|---|
| Object-id staff routes made resolvable for a native header | `backend/apps/makerspaces/origin_scope_model_lookups.py` | consumable pool detail and adjustments, asset QR / fix-status / QR history, product QR history and asset list, membership extend / record / terms / consents / history / titles / waiver witness / verify, term cancel, plan detail and archive, title detail, invite-link revoke, invitation-request invite and decline, report schedules, asset warranty, asset generation now work for native staff (same RBAC; the header must match the object's space) |
| Scanned member-card check link resolves its space from the link token | `origin_scope_routes_catalog.py`, `origin_scope_routes.py` | `GET /admin/card-verifications/{token}/staff` works for a native staff scan; an unknown token still answers the view's uniform 404 |
| Lookup honours `product_pk` | `origin_scope_routes.py` | `GET /admin/inventory/{product_pk}/assets` resolves its product |
| Event programme staff routes resolve their event's space (MOB-STAFF) | `origin_scope_routes_mobstaff.py` (`PROGRAMME_MODEL_LOOKUPS`, merged into `MODEL_LOOKUPS`) | every `events-programme-admin-*` route (judging, tracks, teams, submissions, badges, certificates, broadcasts, forms, gallery, peoples-choice, mentor alerts, reaccept, sponsors ...) and the series guest list take the event's (or series') hosting makerspace from its `pk`. The same lookup now scopes the web custom origin, the tenant source gate and RLS; an unknown id or another space is refused 403 |
| API clients, OAuth apps, event image, organization bookings, bulk decisions, Telegram test, pickers (MOB-STAFF) | `origin_scope_routes_mobstaff.py` (merged by `origin_scope_routes_catalog.py`) | API client by id (nullable owner, native-only lookup in `origin_scope_native_staff.py`); OAuth app by application id (`TARGET_SET_LOOKUPS`); `POST /admin/events/{id}/image`, `/admin/spaces/{id}/organization-bookings/` by object; `POST /integrations/telegram/test-alert` from its body `makerspace_id`; `GET /admin/events/insights/` from `?makerspace=`; the space switcher, event host options and the three bulk-decision routes are space-neutral (RBAC already narrowed to the grant's one space, bulk rows authorised one by one) |
| Native member grant may redeem an event staff invite | `accounts/surface_policy.py` (`_NATIVE_MEMBER_MAY_USE`) | the route was classed delegable, so the native-member gate refused it despite decision 173; it now reaches the view, which checks the invite token (no header sent) |
| An account-only borrower selects the space for their own charges (MOB-AUTHPAY) | `makerspaces/origin_scope_own_charges.py`, `origin_scope.py`, `payments_rail/views_member_mobile.py` | `X-Makerspace-Id` is admitted without a membership only on the eight own-charge routes and only when `member_may_see_own_charges` admits the caller, so the web's borrower checkout now also works from the phone |
| Typed account-state refusals (MOB-AUTHPAY) | `accounts/account_status_refusal.py`, `authentication_device.py`, `surface_policy.py`, `authentication.py` | `401 account_suspended` / `account_restricted` on web and native sessions; `403 email_verification_required` for a verification-only session |
| Android credential sharing (MOB-AUTHPAY) | `accounts/mobile_associations.py` | `assetlinks.json` adds `common.get_login_creds`, the Android twin of the iOS `webcredentials` entry |
| Native GitHub sign-in (MOB-AUTH2, 358 A) | `accounts/github_native.py`, `views_github_native.py`, `serializers_github_native.py`, `social_nonces.py` (`device_anchor`), `integrations/mobile_link_contract.py`, `accounts/mobile_associations.py` | PKCE code exchange on the social nonce ledger; the AASA claims `/app/auth/github/callback` on the primary host |
| Native passkeys (MOB-AUTH2, 358 B) | `accounts/passkeys/native.py`, `passkeys/native_login.py`, `views_device_passkey.py`, `passkeys/services.py`, `passkeys/assertion.py`, `passkeys/views.py`, migration `accounts/0062_device_grant_passkey_login` | device passkey sign-in; registration, rename, remove and re-authentication from a device session |
| Decision 260 at the session boundary (MOB-AUTH2, 358 C) | `accounts/restricted_admission.py`, `authentication.py`, `authentication_device.py`, `surface_policy.py`, `session_issuance.py`, `services_browser_logout.py`, `credential_revocation.py`, `makerspaces/member_usage_views.py` | restricted/suspended accounts reach their own charges and sign-out, nothing else |

Authority is unchanged: no role, scope, MFA or module check was loosened, and a mismatch between the header
and the object's makerspace still answers 403.

## Auth: sign-in on mobile (progress record)

Verified in the schema and code:
- Native sign-in is the device family: `POST /auth/device/attestation-challenge`, `POST /auth/device/login`
  (password, phone, social with an attested device; `authority=member|staff|event`), `POST /auth/device/refresh`
  (30/min), `POST /auth/device/logout`, `GET /auth/device/grants`, `DELETE /auth/device/grants/{grant_id}`,
  `POST /auth/device/staff-grant`, `POST /auth/device/event-grant`, `GET|DELETE /auth/devices[/{device_id}]`.
  Throttles: attestation 5/min, login 5/min per client and 10/hour per user, refresh 30/min, push device
  registration 10/min. Throttled calls answer 429 with `Retry-After`.
- Staff and event grants require MFA verified at sign-in (`mfa_source=verified`). MFA routes: `GET|POST
  /auth/mfa`, `/auth/mfa/enroll`, `/confirm`, `/verify`, `/recovery`, `/disable`, `/passkey/options`.
- Username rule: an account without a handle gets `403 {"code":"handle_required"}` on any
  state-changing call except sign-out, refresh, handle choice, `GET /handles/check`, email verification, password
  change/reset, MFA, passkeys, re-authentication and account deletion. `GET /auth/me` carries `handle`,
  `handle_required`, `handle_suggestion`.
- The browser push routes under `/notifications/browser-firebase/` refuse native grants; push for apps is
  `POST /integrations/push/devices` (register) and the device detail route (unregister).
- Cookie refresh and `GET /auth/browser-state` are browser-only; the native equivalent is the device refresh
  token.

Status per item (lane MOB-AUTHPAY, 2026-11-12). "ok" = already worked natively, now proven by a test through a
native token; "fixed" = changed in this pass; "exception" = deliberately not native; "open" = not done, reason
given. New tests: `backend/tests/api_r2/test_native_auth_0120.py`.

| Item | Status | Native contract and proof |
|---|---|---|
| Email + password | ok | `device/attestation-challenge` then `device/login` (`username` or email, `password`, `authority`). Gated by the password switch (staff exempt). Tests: `tests/accounts/test_device_auth.py`, `test_login_methods_p10.py::test_password_off_also_blocks_device_login`. |
| Email code for an unusual sign-in (login code) | ok | A new device or network on an account with email gets `200 {mfa_required:true, purpose:"risk", factors:["email_code"], challenge}` instead of tokens; finish at `POST /auth/mfa/verify {challenge, code, factor:"email_code"}`, which returns device tokens. Resend: `POST /auth/login-code/resend`. There is no standalone magic-link sign-in on web or native. Test: `test_unusual_native_sign_in_is_finished_by_the_emailed_code`. |
| Phone OTP | ok | `POST /auth/phone/login/start` and `/confirm` with `delivery:"device"` plus challenge and attestation; always a member grant. Gated by the phone switch. Tests: `tests/accounts/test_phone_device_login_m1a.py`. |
| Google, Apple, OIDC | ok | Native ID-token exchange: `GET /auth/social/nonce`, then `POST /auth/social/google`, `/social/apple` or `/social/oidc/{slug}` with `id_token`, `nonce`, `delivery:"device"`, `client_platform`, and challenge plus attestation for a first grant. Same switches and account-linking rules as web. Tests: `tests/accounts/test_social_first_grant.py`, `test_social_auth.py::test_device_social_login_reuses_attested_device_grant_format`, `test_native_config_m1a.py`. |
| GitHub | built (MOB-AUTH2) | Native authorization code + PKCE, decision 358 A. 1) The app makes a PKCE pair (`code_verifier` 43-128 chars, `code_challenge` = base64url(SHA-256), no padding). 2) `POST /auth/social/github/device/authorize {client_platform, code_challenge, code_challenge_method:"S256", challenge?}` (no `Origin`/cookies; `challenge` = an unspent attestation challenge for a first grant, omitted when the request carries the device bearer) returns `{authorization_url, state, redirect_uri, expires_in}`. 3) Open `authorization_url` in `ASWebAuthenticationSession` / Custom Tabs; GitHub redirects to `redirect_uri` = `https://<PUBLIC_APP_BASE_URL host>/app/auth/github/callback?code=...&state=...`, an HTTPS universal link / Android App Link (never a custom scheme). 4) `POST /auth/social/github/device {code, state, code_verifier, client_platform, challenge?, attestation?, app_version?}` answers like the Google/Apple device exchange: tokens + `device_grant` + `device_trust`, or the MFA challenge shape for a person MFA is mandatory for. The state is a one-time row in the social nonce ledger bound to the device (grant or attestation challenge) and to the code challenge: a replay or another device's state is refused (401 `social_invalid`, or 409 `social_device_restart_required` once a first-grant challenge is burned); a wrong verifier is refused 401 without spending the state. Switch off or unconfigured: 404 `social_unavailable`. Same account linking, verified-primary-email rule and audits as web. Throttles `social_nonce` 10/min (start), `social_login` 10/min (exchange). Tests: `tests/accounts/test_native_github_0120.py`. If the app link does not open the app, the browser shows a fallback page at that path ("Open in the Space Works app", a retry that re-opens the same link, and web sign-in); it never shows or sends the code and loads no analytics. Owner action: the GitHub OAuth App's callback URL must cover `https://<host>/app/auth/github/callback` (registering the host root `https://<host>/` covers web and native). |
| Passkeys (WebAuthn) | built (MOB-AUTH2) | Decision 358 B. The RP ID of every native ceremony is the deployment's public web domain (`PUBLIC_APP_BASE_URL` host, or `PLATFORM_DOMAIN_SUFFIX` under managed hosting), never a request header; the expected origin comes from the attested app: iOS `https://<rp id>`, Android `android:apk-key-hash:<base64url SHA-256 of the signing cert>`. The association files bind it: `/.well-known/apple-app-site-association` (`webcredentials`) and `/.well-known/assetlinks.json` (`common.get_login_creds`). Sign-in: `POST /auth/device/attestation-challenge`, then `POST /auth/device/passkey/options {platform, app_id, environment, challenge}` (challenge not spent) returns `{ceremony, options}` (WebAuthn request options, discoverable credentials, `userVerification: required`); then `POST /auth/device/passkey/login {platform, app_id, environment, challenge, attestation, ceremony, credential, app_version?}` returns `{access, refresh, user, device_grant, device_trust}`: a member grant (`login_method:"passkey"`) whose session is MFA-verified (`mfa_method:"passkey"`), so a staff step-up can follow. Registration, rename, remove, list and passkey re-authentication use the web routes (`/auth/passkeys/...`, `/auth/reauth/passkey[/options]`) with the device bearer; adding or removing still needs `recent_reauth` and ends every other session, but the phone keeps its grant and gets `{access, refresh, device_grant}` in the body (no cookie). Errors: 400 `passkey_failed` / `rp_id_unavailable`, 403 `passkeys_unavailable` / `recent_reauth_required`, 401 bad attestation challenge, 426, 429 (`passkey_options` 30/min, `device_login` 5/min). The second factor of a native PASSWORD sign-in offers `passkey` too (decision 361): `POST /auth/mfa/passkey/options {challenge}` (no `Origin`) then `POST /auth/mfa/verify {challenge, factor:"passkey", webauthn:{ceremony, credential}}`. Android accepts every active signer on the approved registration (key rotation safe). Under managed hosting the RP ID is the platform suffix, whose host also serves the association files. Tests: `tests/accounts/test_native_passkeys_0120.py`. |
| Sign-up, email verification | ok + fixed | `POST /auth/member-sign-up` (generic answer, no tokens), then device login; the session is verification-only until `POST /auth/email-verification/confirm {code}` with the device bearer, after which the same session is a full member session. A member API before that now answers `403 {code:"email_verification_required"}` (fixed: was untyped). Test: `test_sign_up_and_email_verification_complete_without_a_browser`. |
| Username check | ok | `GET /handles/check` is anonymous (no bearer, no header). |
| Password reset | ok | `POST /auth/forgot-password {email}` (uniform acknowledgement; 503 `recovery_unavailable` when email is off), then `POST /auth/reset-password {email, code, new_password}`; no browser or cookie. |
| Change password | ok | `POST /auth/change-password` with the bearer; it ends every session, the phone's included (same as web), so sign in again with the new password. Test: `test_change_password_from_the_phone_signs_every_session_out`. |
| Change email | exception | No change-email route exists on web either (`PATCH /auth/me` takes only `preferred_locale`). Not a parity gap; a product feature for later. |
| MFA enrolment, recovery codes | ok | `/auth/mfa/enroll`, `/confirm`, `/recovery`, `/disable` work on the device grant. Test: `test_native_settings_mfa_link.py::test_member_enrolls_authenticator_on_the_same_device_grant`. |
| MFA at sign-in | ok | `200 {mfa_required:true, enrollment_required, challenge, expires_in, purpose, factors}`; finish at `/auth/mfa/verify` with a TOTP or recovery code. Tests: `test_mfa_login_protocols.py::test_native_login_waits_for_mfa_then_preserves_device_delivery`, `test_recovery_code_finishes_a_native_mfa_sign_in`. Staff and event grants refuse a session without verified MFA. |
| Step-up for sensitive actions | ok | Sensitive actions answer `403 {code:"recent_reauth_required"}`; prove it at `POST /auth/reauth` (or the phone and provider variants under `/auth/reauth/...`) and retry. There is no separate `step_up_required` code. Test: `test_native_settings_mfa_link.py::test_member_links_provider_from_device_after_reauth`. |
| Refresh, rotation, reuse detection | ok | `POST /auth/device/refresh`; replaying an old refresh token revokes the whole grant. Test: `test_device_auth.py::test_refresh_reuse_revokes_entire_device_grant`. |
| Logout this device, sessions, revoke one | ok | `POST /auth/device/logout`, `GET /auth/device/grants`, `DELETE /auth/device/grants/{id}` (204), `POST /auth/logout-all`. Tests: `tests/stage4/test_s4c_logout.py`, `test_logout_all_m1g.py`, `test_revoking_one_device_ends_only_that_device`. |
| Revocation on password change, suspension, restriction | ok + fixed | Every request re-checks the grant, the credential generation and `access_status`. A restricted or suspended account now gets `401 {code:"account_restricted"}` or `401 {code:"account_suspended"}` (fixed: was an untyped 401 indistinguishable from an expired session); web sessions get the same codes. Tests: `test_suspended_or_restricted_account_gets_a_typed_401`, `test_device_auth.py::test_password_invalidation_revokes_native_access`. |
| Restricted or suspended account pays its own charges (decision 260) | built (MOB-AUTH2) | Decision 358 C, web and native alike. A restricted or suspended account's browser session or native MEMBER grant still reaches exactly: the eight own-charge routes (`GET .../payments`, `POST .../checkout`, `POST .../mobile-intent`, `paid-claim`, `refund-request`, `refund-requests/{id}/withdraw`, `GET .../payment-documents`, `.../download-url`), the receipt download (`GET /payment-documents/{id}/download`), the outstanding summary `GET /member/makerspaces/{id}/my-usage` (answers `{usage_available:false, payments}`) and sign-out (`/auth/logout`, `/auth/logout-all`, `/auth/device/logout`). Everything else keeps `401 account_restricted` / `account_suspended`, including `/auth/me`: show a "your account is restricted; you can still pay what you owe" screen with the charges list. A staff or event grant of such an account reaches nothing; a REVOKED member stays refused (403). Since decision 361 such a person may also sign in (every door, every factor rule unchanged) and refresh, always as a MEMBER grant; the sign-in and refresh payloads carry `user.account_status` (`active|restricted|suspended`), so route to the pay-what-you-owe screen when it is not `active`. A staff step-up (`authority=staff`, `device/staff-grant`, `device/event-grant`) is refused. Code: `apps/accounts/restricted_admission.py`, migration `accounts/0063_restricted_member_device_grants`. Tests also in `tests/api_r2/test_restricted_sign_in_0120.py`. Tests: `tests/api_r2/test_restricted_own_charges_0120.py`. |
| Push device register / unregister | ok | `POST /integrations/push/devices`, `DELETE /integrations/push/devices/{id}`. Tests: `tests/test_native_push.py`. |
| Account export, deletion | ok | Export is per makerspace on web and native: `member/makerspaces/{id}/account/exports[/{uuid}[/download]]`. Deletion: `POST /auth/account/deletion` after `recent_reauth`. Test: `test_reauth_proof_m1d.py::test_attested_device_proof_is_family_bound_and_revoked_on_deletion`. |
| 429 and enumeration | ok | Sign-in doors throttle with `429` + `Retry-After`; an unknown account and a wrong password get the same `401`. Tests: `test_native_sign_in_door_answers_429_with_retry_after`, `test_unknown_account_and_wrong_password_get_the_same_refusal`, `test_phone_device_login_m1a.py::test_device_start_ack_is_uniform_for_invalid_challenges_and_unknown_numbers`. |
| Platform (superadmin) | exception | Web-only by owner decision 356; the superadmin's optional MFA and any platform step-up are web-only too. |

Read the login-method switches (`GET /admin/platform/login-methods`) to see which doors a deployment enables.

## Payments on mobile (progress record)

Verified:
- `POST /member/makerspaces/{makerspace_id}/payments/{payment_id}/mobile-intent` (operationId
  `api_v1_member_makerspaces_payments_mobile_intent_create`) is native-only (attested device token, selected
  makerspace). Response `MobilePaymentIntentResponse`, discriminated by `vendor`:
  Stripe `{vendor:"stripe", payment_id, client_secret, publishable_key, customer_id?, ephemeral_key?}` for the
  PaymentSheet; Razorpay `{vendor:"razorpay", payment_id, key_id, order_id, amount_minor, currency, name,
  description}` for the native checkout. Only the publishable key or key id is returned, never a secret key
  (covered by a test).
- Refusals the app can render: 404 not your pending charge; 503 `{code:"payments_unavailable"}` when the
  charge has no live online rail or the provider is down (pay at the desk instead); 409
  `payment_rail_conflict` (a hosted checkout already exists), `payment_settlement_pending` (your offline payment awaits
  staff), or the platform rail-limit code; 429 throttled. No path raises a 500.
- Own charges: `GET /member/makerspaces/{id}/payments` (`MemberPayment`: `status`, `due_state`,
  `online_payment_available`, `offline_collection`, `settlement`). Poll it after the sheet closes: the status
  flips when the provider webhook lands (webhooks are server to server and not for the app). Offline claims:
  `POST .../payments/{id}/paid-claim`; refunds: `refund-request`, `refund-suggestion`, `refund-requests/{id}/withdraw`.
  Documents and receipts: `GET .../payment-documents` and `.../{document_id}/download-url` (short-lived URL).
  Hosted checkout (`.../checkout`, `/public/pay/{token}/checkout`) returns a URL to open in the system browser.
- Staff on a phone (native staff grant): record a manual settlement (`POST .../payments/{id}/mark-offline`,
  `amend-settlement`, body `PaymentOffline.settlement` with method, reference, received date), refunds (`refund`,
  `refund-offline`, `release-deposit`, refund cases), ledger and reconciliation (`/admin/makerspace/{id}/ledger`,
  `/payments`), pay links. All keep the web authority checks. Stripe Connect onboarding
  (`POST .../payment-settings/connect/onboard`) returns `{authorize_url}`, a Stripe OAuth URL that must open in a
  browser; its callback is a browser redirect.
- The platform has no stored-value wallet or top-up. "Wallet" in the API means Apple/Google pass files.

Status per item (lane MOB-AUTHPAY, 2026-11-12). New tests: `backend/tests/api_r2/test_native_payments_0120.py`.

| Item | Status | Native contract and proof |
|---|---|---|
| `mobile-intent` idempotency | ok | A repeat call for the same charge returns the same intent; the provider create runs once with key `payment-mobile-intent-{id}`, then the stored intent id (Razorpay: the stored order or a receipt lookup) is reused. Tests: `test_repeat_mobile_intent_returns_the_same_intent_and_creates_it_once`, `tests/payments/test_native_contract_m1c.py`, `test_mobile_razorpay_orders.py`. |
| SCA / `requires_action` | ok (client side) | 3-D Secure runs inside the Stripe PaymentSheet or Razorpay checkout; the server keeps no SCA state. After the sheet closes, poll `GET /member/makerspaces/{id}/payments` until the row's `status` leaves `pending` (`paid_online` once the provider webhook lands; `gateway_poll` is the fallback). Test: `test_webhook_settles_the_native_intent_and_the_member_list_shows_it_paid`. |
| `customer_id`, `ephemeral_key` | note | Declared optional in `MobilePaymentIntentResponse` but not returned today (no saved Stripe customers); build the PaymentSheet without them. |
| Account-only borrower | fixed | A borrower with no membership can now select the space with `X-Makerspace-Id` for the eight own-charge routes only (history, checkout, mobile-intent, paid-claim, refund request and withdraw, documents, document URL), exactly when `member_may_see_own_charges` admits them. Before, the header was refused and `mobile-intent` was unreachable for them although the web checkout worked. Every other member route still answers 403. Code: `apps/makerspaces/origin_scope_own_charges.py`. Tests: `test_account_only_borrower_reads_and_is_told_to_pay_an_unclaimed_charge_at_the_desk`, `test_borrower_selection_stays_narrow`. |
| REVOKED member | ok | Still refused on the phone (403), bar their own rejoin admission charge, as on web. Test: `test_revoked_member_is_still_refused_on_the_phone`. |
| Outstanding per currency, history | ok | `membership_dues.outstanding_by_currency` on `GET /member/makerspaces/{id}/activity` (membership module) and `/my-usage`; the full list at `/payments`. |
| Receipts | ok | `GET .../payment-documents/{id}/download-url` returns `{url, expires_in:300}`; `GET` that relative URL with the bearer (no header) streams the PDF. The link is bound to the user. Test: `test_receipt_downloads_with_the_bearer_token_alone`. |
| Wallet | note | No stored-value wallet; "wallet" means Apple/Google pass files. |
| Membership fee, renewal, prepaid jobs, event fees | ok | All are ordinary `Payment` rows paid through the same routes. Membership: `GET .../account/membership`, `POST .../account/cancel`; renewals are raised by the renewal sweep; prepaid jobs by `POST /member/machine-jobs/{id}/approve-quote`; event fees by the ticketing order routes. |
| Unclaimed provider (no gateway) | ok | The row shows `online_payment_available:false`, `checkout_url:""` and `offline_collection`; `mobile-intent` answers `503 {code:"payments_unavailable"}`: show "pay at the desk". Test: the borrower test above. |
| Rail off or tombstoned | ok | Module or rail off at runtime: `mobile-intent` answers `503 payments_unavailable` and the list still reads. Rail tombstoned at deploy: the pay routes do not exist (404, no code) and the list shows `online_payment_available:false`; treat a 404 on `mobile-intent` as "pay at the desk". No 500 path. Tests: `test_rail_switched_off_answers_typed_503_not_500`, `tests/tombstone/test_payments_removed_surfaces.py`. |
| Staff: manual settlement, ledger, refunds | ok | Native staff grant + `X-Makerspace-Id`: `GET /admin/makerspace/{id}/payments`, `POST .../payments/{id}/mark-offline` and `amend-settlement` (`{settlement:{method, reference, received_at}}`; each amendment is a new `ManualSettlement` row linked by `amends`), `refund`, `refund-offline`, `release-deposit`; the same actions as web (`RECORD_PAYMENT`, `VIEW_FINANCE` or the subject action). Member grants and header-less staff grants are refused. Tests: `test_native_staff_records_and_amends_a_manual_settlement_with_web_authority`, `test_staff_payment_routes_refuse_member_grants_and_headerless_staff_grants`. |
| Stripe Connect onboarding | exception | `POST /admin/makerspace/{id}/payment-settings/connect/onboard` (space manager, `payments` module, only where the platform hosts other spaces) returns `{authorize_url}`, a Stripe OAuth URL the app opens in the system browser; the callback is a browser redirect. |
| Secrets | ok | Only the publishable key or Razorpay key id is returned. Tests: `test_native_contract_m1c.py::test_razorpay_native_response_has_checkout_parameters_without_secrets`, `test_repeat_mobile_intent_returns_the_same_intent_and_creates_it_once`. |

## Progress, open items and how to continue

Done: SPA call inventory (1206 operations of 2791); native admission analysis; the route-resolution fixes
above; tests in `backend/tests/api_r2/test_native_mobile_0120.py`; the generated tables below; PRD sections.

Open, in priority order:
1. ~~The "CHECK" rows in the staff table~~ Resolved (MOB-STAFF): none remain. 803 staff operations are `ok`; 34 are
   `web-only` on purpose and stay refused for a native staff grant (the table notes say why): organization
   governance consoles (organization-derived authority is cut for native sessions: `_delegated` returns False and
   RBAC drops organization grants, so there is no makerspace to select), superadmin-only routes (backup download,
   machine-service report, space-pack profiles, restrict / restore access, deployment report catalog) and the
   booking staff invite redeem (native member sessions refuse it). Parity is regenerated from the repo with
   `handover/reports/mobile-parity/` (`spa_inventory.py` -> `url_names.py` -> `parity_table.py` -> `gen_doc.py`) and
   guarded by `backend/tests/api_r2/test_native_staff_registry_0120.py`, which reads the SPA sources and fails the
   build when a staff route the SPA calls has no lookup and is not declared in `NATIVE_STAFF_WEB_ONLY`.
2. ~~The auth items marked "open" above~~ Resolved (MOB-AUTH2, decision 358): native GitHub sign-in and native
   passkeys are built, and decision 260 (restricted/suspended accounts pay their own charges) is enforced at the
   session boundary on web and native. Decision 361 closed the follow-ups: restricted sign-in and refresh, the
   GitHub fallback page, rotation-safe Android passkey origins, the passkey second factor on native password
   sign-in, and association files on the managed-hosting suffix host.
3. Operation ids ending in `_2` (profile timeline detail, shop order detail, and others in the diff table) are
   unstable names; fixing them needs a schema regeneration, so map them by path in a hand-written wrapper.
4. Replace the static analysis with a runtime walk: for each inventory row, call it with a native staff grant
   (and header) and assert the response is not a 401 or an auth-reason 403 ("Makerspace target could not be
   resolved", "delegated authority source is required").

How to regenerate: from the repo root `python handover/reports/mobile-parity/spa_inventory.py`, then the
matching scripts in that folder (`parity_table.py`, `gen_doc.py`) as described in their docstrings.

## Full parity table: every operation the web SPA references

Status: ok = reachable by a native token with the same checks as the web session; CHECK = tenant target not provably recognized, verify (none left); web-only = browser-only, or deliberately not reachable by a native grant (reason in the note); platform (superadmin) operations are web-only by owner decision 356 — superadmin never holds a phone token.


### Member and public (284)

| Method | Path | operationId | Status | Note |
|---|---|---|---|---|
| GET | `/auth/access-token-scopes` | `api_v1_auth_access_token_scopes_retrieve` | ok | member surface |
| GET | `/auth/access-tokens` | `api_v1_auth_access_tokens_list` | ok | member surface |
| POST | `/auth/access-tokens` | `api_v1_auth_access_tokens_create` | ok | member surface |
| DELETE | `/auth/access-tokens/{id}` | `api_v1_auth_access_tokens_destroy` | ok | member surface |
| GET | `/auth/account/deletion` | `api_v1_auth_account_deletion_retrieve` | ok | member surface |
| POST | `/auth/account/deletion` | `api_v1_auth_account_deletion_create` | ok | member surface |
| POST | `/auth/account/restore/email` | `api_v1_auth_account_restore_email_create` | ok | member surface |
| POST | `/auth/change-password` | `api_v1_auth_change_password_create` | ok | member surface |
| POST | `/auth/claim/redeem` | `api_v1_auth_claim_redeem_create` | ok | member surface |
| GET | `/auth/connected-apps` | `api_v1_auth_connected_apps_list` | ok | member surface |
| DELETE | `/auth/connected-apps/{application_id}` | `api_v1_auth_connected_apps_destroy` | ok | member surface |
| GET | `/auth/devices` | `api_v1_auth_devices_retrieve` | ok | member surface |
| DELETE | `/auth/devices/{device_id}` | `api_v1_auth_devices_destroy` | ok | member surface |
| POST | `/auth/email-verification/confirm` | `api_v1_auth_email_verification_confirm_create` | ok | member surface |
| POST | `/auth/email-verification/resend` | `api_v1_auth_email_verification_resend_create` | ok | member surface |
| POST | `/auth/forgot-password` | `api_v1_auth_forgot_password_create` | ok | member surface |
| POST | `/auth/login` | `api_v1_auth_login_create` | ok | member surface |
| POST | `/auth/login-code/resend` | `api_v1_auth_login_code_resend_create` | ok | member surface |
| POST | `/auth/logout` | `api_v1_auth_logout_create` | ok | member surface |
| POST | `/auth/logout-all` | `api_v1_auth_logout_all_create` | ok | member surface |
| GET | `/auth/me` | `api_v1_auth_me_retrieve` | ok | member surface |
| PATCH | `/auth/me` | `api_v1_auth_me_partial_update` | ok | member surface |
| POST | `/auth/member-sign-up` | `api_v1_auth_member_sign_up_create` | ok | member surface |
| GET | `/auth/mfa` | `api_v1_auth_mfa_retrieve` | ok | member surface |
| POST | `/auth/mfa` | `api_v1_auth_mfa_create` | ok | member surface |
| POST | `/auth/mfa/confirm` | `api_v1_auth_mfa_confirm_create` | ok | member surface |
| POST | `/auth/mfa/enroll` | `api_v1_auth_mfa_enroll_create` | ok | member surface |
| POST | `/auth/mfa/passkey/options` | `api_v1_auth_mfa_passkey_options_create` | ok | member surface |
| POST | `/auth/mfa/verify` | `api_v1_auth_mfa_verify_create` | ok | member surface |
| GET | `/auth/oauth/authorize` | `api_v1_auth_oauth_authorize_retrieve` | ok | member surface |
| POST | `/auth/oauth/authorize` | `api_v1_auth_oauth_authorize_create` | ok | member surface |
| POST | `/auth/organization-invitations/redeem/` | `api_v1_auth_organization_invitations_redeem_create` | ok | member surface |
| GET | `/auth/organizations/self-service/` | `api_v1_auth_organizations_self_service_retrieve` | ok | member surface |
| POST | `/auth/organizations/self-service/` | `api_v1_auth_organizations_self_service_create` | ok | member surface |
| GET | `/auth/passkeys` | `api_v1_auth_passkeys_retrieve` | ok | member surface |
| POST | `/auth/passkeys/authenticate/options` | `api_v1_auth_passkeys_authenticate_options_create` | ok | member surface |
| POST | `/auth/passkeys/authenticate/verify` | `api_v1_auth_passkeys_authenticate_verify_create` | ok | member surface |
| POST | `/auth/passkeys/register/options` | `api_v1_auth_passkeys_register_options_create` | ok | member surface |
| POST | `/auth/passkeys/register/verify` | `api_v1_auth_passkeys_register_verify_create` | ok | member surface |
| DELETE | `/auth/passkeys/{passkey_id}` | `api_v1_auth_passkeys_destroy` | ok | member surface |
| PATCH | `/auth/passkeys/{passkey_id}` | `api_v1_auth_passkeys_partial_update` | ok | member surface |
| POST | `/auth/phone/link/confirm` | `api_v1_auth_phone_link_confirm_create` | ok | member surface |
| POST | `/auth/phone/link/start` | `api_v1_auth_phone_link_start_create` | ok | member surface |
| GET | `/auth/reauth` | `api_v1_auth_reauth_retrieve` | ok | member surface |
| POST | `/auth/reauth` | `api_v1_auth_reauth_create` | ok | member surface |
| POST | `/auth/reauth/enrollment/confirm` | `api_v1_auth_reauth_enrollment_confirm_create` | ok | member surface |
| POST | `/auth/reauth/enrollment/email` | `api_v1_auth_reauth_enrollment_email_create` | ok | member surface |
| POST | `/auth/reauth/passkey` | `api_v1_auth_reauth_passkey_create` | ok | member surface |
| POST | `/auth/reauth/passkey/options` | `api_v1_auth_reauth_passkey_options_create` | ok | member surface |
| POST | `/auth/reauth/social/complete` | `api_v1_auth_reauth_social_complete_create` | ok | member surface |
| POST | `/auth/reauth/social/start` | `api_v1_auth_reauth_social_start_create` | ok | member surface |
| POST | `/auth/refresh` | `api_v1_auth_refresh_create` | web-only | cookie refresh -> POST /auth/device/refresh |
| POST | `/auth/reset-password` | `api_v1_auth_reset_password_create` | ok | member surface |
| POST | `/auth/security-alerts/not-me` | `api_v1_auth_security_alerts_not_me_create` | ok | member surface |
| POST | `/auth/social/github/authorize` | `api_v1_auth_social_github_authorize_create` | ok | member surface |
| POST | `/auth/social/github/link/authorize` | `api_v1_auth_social_github_link_authorize_create` | ok | member surface |
| POST | `/auth/social/link/callback` | `api_v1_auth_social_link_callback_create` | ok | member surface |
| POST | `/auth/social/nonce` | `api_v1_auth_social_nonce_create` | ok | member surface |
| POST | `/auth/social/oidc/{slug}/authorize` | `api_v1_auth_social_oidc_authorize_create` | ok | member surface |
| POST | `/auth/social/oidc/{slug}/link/authorize` | `api_v1_auth_social_oidc_link_authorize_create` | ok | member surface |
| GET | `/auth/social/providers` | `api_v1_auth_social_providers_list` | ok | member surface |
| POST | `/auth/social/providers` | `api_v1_auth_social_providers_create` | ok | member surface |
| DELETE | `/auth/social/providers/{provider}` | `api_v1_auth_social_providers_destroy` | ok | member surface |
| POST | `/auth/staff-invitations/accept` | `api_v1_auth_staff_invitations_accept_create` | ok | member surface |
| GET | `/me/messaging` | `api_v1_me_messaging_retrieve` | ok | member surface |
| POST | `/me/messaging/consent` | `api_v1_me_messaging_consent_create` | ok | member surface |
| GET | `/member/adapter-artifacts/requests/{request_id}` | `api_v1_member_adapter_artifacts_requests_retrieve` | ok | member surface |
| GET | `/member/adapter-artifacts/{id}/url` | `api_v1_member_adapter_artifacts_url_retrieve` | ok | member surface |
| GET | `/member/adapter-detections/requests/{request_id}` | `api_v1_member_adapter_detections_requests_retrieve` | ok | member surface |
| POST | `/member/adapter-watch/requests/{request_id}` | `api_v1_member_adapter_watch_requests_create` | ok | member surface |
| DELETE | `/member/adapter-watch/{id}` | `api_v1_member_adapter_watch_destroy` | ok | member surface |
| GET | `/member/adapter-watch/{id}/frame` | `api_v1_member_adapter_watch_frame_retrieve` | ok | member surface |
| GET | `/member/adapter-watch/{id}/signal` | `api_v1_member_adapter_watch_signal_retrieve` | ok | member surface |
| POST | `/member/adapter-watch/{id}/signal` | `api_v1_member_adapter_watch_signal_create` | ok | member surface |
| POST | `/member/adapter-watch/{id}/talk` | `api_v1_member_adapter_watch_talk_create` | ok | member surface |
| GET | `/member/archived-payments` | `api_v1_member_archived_payments_list` | ok | member surface |
| GET | `/member/card-jobs/{id}` | `api_v1_member_card_jobs_retrieve` | ok | member surface |
| GET | `/member/card-jobs/{id}/result` | `api_v1_member_card_jobs_result_retrieve` | ok | member surface |
| GET | `/member/cards` | `api_v1_member_cards_list` | ok | member surface |
| GET | `/member/event-payouts/` | `api_v1_member_event_payouts_retrieve` | ok | member surface |
| GET | `/member/event-payouts/{obligation_id}/` | `api_v1_member_event_payouts_retrieve_2` | ok | member surface |
| GET | `/member/event-registrations/{id}/ticket` | `api_v1_member_event_registrations_ticket_retrieve` | ok | member surface |
| POST | `/member/event-speaker-claims/` | `api_v1_member_event_speaker_claims_create` | ok | member surface |
| POST | `/member/id-programme-invites/accept` | `api_v1_member_id_programme_invites_accept_create` | ok | member surface |
| GET | `/member/issues` | `api_v1_member_issues_list` | ok | member surface |
| POST | `/member/issues` | `api_v1_member_issues_create` | ok | member surface |
| GET | `/member/issues/loan-items` | `api_v1_member_issues_loan_items_list` | ok | member surface |
| POST | `/member/issues/photos` | `api_v1_member_issues_photos_create` | ok | member surface |
| GET | `/member/machine-jobs` | `api_v1_member_machine_jobs_list` | ok | member surface |
| GET | `/member/machine-jobs/{id}` | `api_v1_member_machine_jobs_retrieve` | ok | member surface |
| POST | `/member/machine-jobs/{id}/approve-quote` | `api_v1_member_machine_jobs_approve_quote_create` | ok | member surface |
| POST | `/member/machine-jobs/{id}/consumables` | `api_v1_member_machine_jobs_consumables_create` | ok | member surface |
| POST | `/member/machine-jobs/{id}/decline-quote` | `api_v1_member_machine_jobs_decline_quote_create` | ok | member surface |
| POST | `/member/machine-jobs/{id}/resubmit` | `api_v1_member_machine_jobs_resubmit_create` | ok | member surface |
| GET | `/member/machine-service/requests/by-token/{public_token}/owner` | `api_v1_member_machine_service_requests_by_token_owner_retrieve` | ok | member surface |
| POST | `/member/machine-service/requests/{id}/cancel` | `api_v1_member_machine_service_requests_cancel_create` | ok | member surface |
| GET | `/member/machine-sessions` | `api_v1_member_machine_sessions_list` | ok | member surface |
| POST | `/member/machine-sessions/{id}/stop` | `api_v1_member_machine_sessions_stop_create` | ok | member surface |
| GET | `/member/machine-type-documents/{id}/url` | `api_v1_member_machine_type_documents_url_retrieve` | ok | member surface |
| GET | `/member/machines/{machine_id}/session` | `api_v1_member_machines_session_retrieve` | ok | member surface |
| POST | `/member/machines/{machine_id}/sessions/start` | `api_v1_member_machines_sessions_start_create` | ok | member surface |
| POST | `/member/machines/{machine_id}/supervised-sessions` | `api_v1_member_machines_supervised_sessions_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/activity` | `api_v1_member_makerspaces_activity_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/admission` | `api_v1_member_makerspaces_admission_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/admission/export` | `api_v1_member_makerspaces_admission_export_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/admission/photo` | `api_v1_member_makerspaces_admission_photo_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/admission/{request_id}/cancel` | `api_v1_member_makerspaces_admission_cancel_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/admission/{request_id}/vouch` | `api_v1_member_makerspaces_admission_vouch_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/allowances` | `api_v1_member_makerspaces_allowances_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/borrowing-history` | `api_v1_member_makerspaces_borrowing_history_list` | ok | member surface |
| DELETE | `/member/makerspaces/{makerspace_id}/calendar-feeds/{kind}/` | `api_v1_member_makerspaces_calendar_feeds_destroy` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/calendar-feeds/{kind}/` | `api_v1_member_makerspaces_calendar_feeds_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/calendar-feeds/{kind}/` | `api_v1_member_makerspaces_calendar_feeds_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/certificate-approvals/` | `api_v1_member_makerspaces_certificate_approvals_list` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/certificates/` | `api_v1_member_makerspaces_certificates_list` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/certifications` | `api_v1_member_makerspaces_certifications_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/collaborative-events/` | `api_v1_member_makerspaces_collaborative_events_list` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/collaborative-events/{id}/register/` | `api_v1_member_makerspaces_collaborative_events_register_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/directory` | `api_v1_member_makerspaces_directory_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/donations` | `api_v1_member_makerspaces_donations_list` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/donations/{id}/tax-receipt.pdf` | `api_v1_member_makerspaces_donations_tax_receipt.pdf_retrieve` | ok | member surface |
| DELETE | `/member/makerspaces/{makerspace_id}/event-calendar-feed/` | `api_v1_member_makerspaces_event_calendar_feed_destroy` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-calendar-feed/` | `api_v1_member_makerspaces_event_calendar_feed_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/event-calendar-feed/` | `api_v1_member_makerspaces_event_calendar_feed_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-certificates/{id}/download/` | `api_v1_member_makerspaces_event_certificates_download_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-history/` | `api_v1_member_makerspaces_event_history_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-registrations/calendar.ics` | `api_v1_member_makerspaces_event_registrations_calendar.ics_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/event-registrations/{id}/cancel/` | `api_v1_member_makerspaces_event_registrations_cancel_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-registrations/{id}/equipment/` | `api_v1_member_makerspaces_event_registrations_equipment_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-registrations/{id}/qr` | `api_v1_member_makerspaces_event_registrations_qr_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/event-series/{series_id}/passes/` | `api_v1_member_makerspaces_event_series_passes_list` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/event-series/{series_id}/passes/` | `api_v1_member_makerspaces_event_series_passes_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/events/{event_id}/orders/` | `api_v1_member_makerspaces_events_orders_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/events/{event_id}/orders/quote/` | `api_v1_member_makerspaces_events_orders_quote_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/events/{id}/help-topics/` | `api_v1_member_makerspaces_events_help_topics_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/events/{id}/participant-resumes/` | `api_v1_member_makerspaces_events_participant_resumes_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/events/{id}/participant-resumes/` | `api_v1_member_makerspaces_events_participant_resumes_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/events/{id}/peoples-choice/` | `api_v1_member_makerspaces_events_peoples_choice_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/incidents` | `api_v1_member_makerspaces_incidents_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/incidents` | `api_v1_member_makerspaces_incidents_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/loans/{id}/renew` | `api_v1_member_makerspaces_loans_renew_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/machine-access` | `api_v1_member_makerspaces_machine_access_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/machine-types/{type_id}/guide` | `api_v1_member_makerspaces_machine_types_guide_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/machine-use/events/` | `api_v1_member_makerspaces_machine_use_events_list` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/machines` | `api_v1_member_makerspaces_machines_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/member-card` | `api_v1_member_makerspaces_member_card_retrieve` | ok | member surface |
| PATCH | `/member/makerspaces/{makerspace_id}/member-card` | `api_v1_member_makerspaces_member_card_partial_update` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/my-usage` | `api_v1_member_makerspaces_my_usage_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/orders/` | `api_v1_member_makerspaces_orders_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/orders/{order_id}/` | `api_v1_member_makerspaces_orders_retrieve_2` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/orders/{order_id}/seats/{seat_id}/claim/` | `api_v1_member_makerspaces_orders_seats_claim_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/payments` | `api_v1_member_makerspaces_payments_list` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/payments/{payment_id}/checkout` | `api_v1_member_makerspaces_payments_checkout_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/payments/{payment_id}/paid-claim` | `api_v1_member_makerspaces_payments_paid_claim_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/payments/{payment_id}/refund-request` | `api_v1_member_makerspaces_payments_refund_request_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/payments/{payment_id}/refund-suggestion` | `api_v1_member_makerspaces_payments_refund_suggestion_retrieve` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/pledges` | `api_v1_member_makerspaces_pledges_list` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/pledges/{id}` | `api_v1_member_makerspaces_pledges_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/prizes/` | `api_v1_member_makerspaces_prizes_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/referrals` | `api_v1_member_makerspaces_referrals_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/refund-requests/{case_id}/withdraw` | `api_v1_member_makerspaces_refund_requests_withdraw_create` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/requests/{id}/withdraw` | `api_v1_member_makerspaces_requests_withdraw_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/supervised-sessions` | `api_v1_member_makerspaces_supervised_sessions_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/verification` | `api_v1_member_makerspaces_verification_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/waitlist` | `api_v1_member_makerspaces_waitlist_list` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/waitlist` | `api_v1_member_makerspaces_waitlist_create` | ok | member surface |
| GET | `/member/makerspaces/{makerspace_id}/waiver` | `api_v1_member_makerspaces_waiver_retrieve` | ok | member surface |
| POST | `/member/makerspaces/{makerspace_id}/waiver/accept` | `api_v1_member_makerspaces_waiver_accept_create` | ok | member surface |
| GET | `/member/organizations/` | `api_v1_member_organizations_retrieve` | ok | member surface |
| GET | `/member/organizations/{id}/leave/` | `api_v1_member_organizations_leave_retrieve` | ok | member surface |
| POST | `/member/organizations/{id}/leave/` | `api_v1_member_organizations_leave_create` | ok | member surface |
| GET | `/member/profile` | `api_v1_member_profile_retrieve` | ok | member surface |
| PATCH | `/member/profile` | `api_v1_member_profile_partial_update` | ok | member surface |
| PUT | `/member/profile` | `api_v1_member_profile_update` | ok | member surface |
| DELETE | `/member/profile/handle` | `api_v1_member_profile_handle_destroy` | ok | member surface |
| POST | `/member/profile/handle` | `api_v1_member_profile_handle_create` | ok | member surface |
| DELETE | `/member/profile/image` | `api_v1_member_profile_image_destroy` | ok | member surface |
| POST | `/member/profile/image` | `api_v1_member_profile_image_create` | ok | member surface |
| PUT | `/member/profile/image` | `api_v1_member_profile_image_update` | ok | member surface |
| GET | `/member/saved-details/` | `api_v1_member_saved_details_retrieve` | ok | member surface |
| GET | `/member/security-activity/` | `api_v1_member_security_activity_retrieve` | ok | member surface |
| GET | `/member/shop/orders/` | `api_v1_member_shop_orders_retrieve` | ok | member surface |
| GET | `/member/shop/orders/{id}/` | `api_v1_member_shop_orders_retrieve_2` | ok | member surface |
| POST | `/member/shop/orders/{id}/cancel/` | `api_v1_member_shop_orders_cancel_create` | ok | member surface |
| GET | `/member/supervised-sessions/{id}` | `api_v1_member_supervised_sessions_retrieve` | ok | member surface |
| POST | `/member/supervised-uses/{id}/end` | `api_v1_member_supervised_uses_end_create` | ok | member surface |
| GET | `/memberships/invitations` | `api_v1_memberships_invitations_retrieve` | ok | member surface |
| POST | `/memberships/invitations/{id}/claim` | `api_v1_memberships_invitations_claim_create` | ok | member surface |
| GET | `/memberships/me` | `api_v1_memberships_me_retrieve` | ok | member surface |
| PATCH | `/memberships/requests/{id}` | `api_v1_memberships_requests_partial_update` | ok | member surface |
| GET | `/notifications/browser-alerts/key` | `api_v1_notifications_browser_alerts_key_retrieve` | ok | member surface |
| DELETE | `/notifications/browser-alerts/{makerspace_id}` | `api_v1_notifications_browser_alerts_destroy` | ok | member surface |
| GET | `/notifications/browser-alerts/{makerspace_id}` | `api_v1_notifications_browser_alerts_retrieve` | ok | member surface |
| POST | `/notifications/browser-alerts/{makerspace_id}` | `api_v1_notifications_browser_alerts_create` | ok | member surface |
| DELETE | `/notifications/browser-firebase/{makerspace_id}/challenge` | `api_v1_notifications_browser_firebase_challenge_destroy` | web-only | browser web push; native equivalent POST /integrations/push/devices |
| POST | `/notifications/browser-firebase/{makerspace_id}/challenge` | `api_v1_notifications_browser_firebase_challenge_create` | web-only | browser web push; native equivalent POST /integrations/push/devices |
| GET | `/notifications/browser-firebase/{makerspace_id}/config` | `api_v1_notifications_browser_firebase_config_retrieve` | web-only | browser web push; native equivalent POST /integrations/push/devices |
| POST | `/notifications/browser-firebase/{makerspace_id}/confirm` | `api_v1_notifications_browser_firebase_confirm_create` | web-only | browser web push; native equivalent POST /integrations/push/devices |
| GET | `/notifications/inbox/{makerspace_id}` | `api_v1_notifications_inbox_retrieve` | ok | member surface |
| GET | `/notifications/inbox/{makerspace_id}/unread-count` | `api_v1_notifications_inbox_unread_count_retrieve` | ok | member surface |
| GET | `/notifications/preferences/{makerspace_id}` | `api_v1_notifications_preferences_retrieve` | ok | member surface |
| PATCH | `/notifications/preferences/{makerspace_id}` | `api_v1_notifications_preferences_partial_update` | ok | member surface |
| GET | `/profiles/by-account/{user_id}/` | `api_v1_profiles_by_account_retrieve` | ok | member surface |
| GET | `/public/card-verifications/{token}` | `api_v1_public_card_verifications_retrieve` | ok | member surface |
| GET | `/public/donation-links/{token}` | `api_v1_public_donation_links_retrieve` | ok | member surface |
| POST | `/public/donation-links/{token}/checkout` | `api_v1_public_donation_links_checkout_create` | ok | member surface |
| POST | `/public/donation-links/{token}/claim` | `api_v1_public_donation_links_claim_create` | ok | member surface |
| GET | `/public/event-certificates/{verification_id}/verify/` | `api_v1_public_event_certificates_verify_retrieve` | ok | member surface |
| GET | `/public/event-codes/{code}/` | `api_v1_public_event_codes_retrieve` | ok | member surface |
| GET | `/public/event-codes/{public_token}/` | `api_v1_public_event_codes_retrieve_2` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/context/` | `api_v1_public_event_programmes_context_retrieve` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/crew/` | `api_v1_public_event_programmes_crew_list` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/gallery/` | `api_v1_public_event_programmes_gallery_retrieve` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/gallery/assets/{public_asset_id}/` | `api_v1_public_event_programmes_gallery_assets_retrieve` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/peoples-choice/` | `api_v1_public_event_programmes_peoples_choice_retrieve` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/prizes/` | `api_v1_public_event_programmes_prizes_list` | ok | member surface |
| GET | `/public/event-programmes/{public_token}/volunteer-postings/` | `api_v1_public_event_programmes_volunteer_postings_retrieve` | ok | member surface |
| POST | `/public/hosting/invitations/resolve` | `api_v1_public_hosting_invitations_resolve_create` | ok | member surface |
| POST | `/public/hosting/invitations/submit` | `api_v1_public_hosting_invitations_submit_create` | ok | member surface |
| POST | `/public/hosting/requests` | `api_v1_public_hosting_requests_create` | ok | member surface |
| POST | `/public/hosting/requests/open` | `api_v1_public_hosting_requests_open_create` | ok | member surface |
| POST | `/public/hosting/requests/resubmit` | `api_v1_public_hosting_requests_resubmit_create` | ok | member surface |
| GET | `/public/m/{makerspace_slug}/shop/` | `api_v1_public_m_shop_retrieve` | ok | member surface |
| GET | `/public/machine-service/3d-printer/requests/{public_token}/status` | `api_v1_public_machine_service_3d_printer_requests_status_retrieve` | ok | member surface |
| GET | `/public/machine-service/requests/{public_token}/status` | `api_v1_public_machine_service_requests_status_retrieve` | ok | member surface |
| GET | `/public/makerspaces/` | `api_v1_public_makerspaces_list` | ok | member surface |
| GET | `/public/makerspaces/{makerspace_slug}/availability` | `api_v1_public_makerspaces_availability_retrieve` | ok | member surface |
| GET | `/public/makerspaces/{makerspace_slug}/presence/now-config/` | `api_v1_public_makerspaces_presence_now_config_retrieve` | ok | member surface |
| GET | `/public/makerspaces/{makerspace_slug}/presence/now/` | `api_v1_public_makerspaces_presence_now_list` | ok | member surface |
| GET | `/public/organizations/{slug}/` | `api_v1_public_organizations_retrieve_2` | ok | member surface |
| GET | `/public/organizations/{slug}/events/` | `api_v1_public_organizations_events_retrieve` | ok | member surface |
| GET | `/public/organizations/{slug}/id-programmes/{programme_slug}` | `api_v1_public_organizations_id_programmes_retrieve` | ok | member surface |
| GET | `/public/organizations/{slug}/makerspaces/` | `api_v1_public_organizations_makerspaces_retrieve` | ok | member surface |
| GET | `/public/organizations/{slug}/page/` | `api_v1_public_organizations_page_retrieve` | ok | member surface |
| GET | `/public/page-handles/{handle}/` | `api_v1_public_page_handles_retrieve` | ok | member surface |
| GET | `/public/pledge-links/{token}` | `api_v1_public_pledge_links_retrieve` | ok | member surface |
| POST | `/public/pledge-links/{token}` | `api_v1_public_pledge_links_create` | ok | member surface |
| GET | `/public/profiles/{handle}/` | `api_v1_public_profiles_retrieve` | ok | member surface |
| GET | `/public/technician-opt-in/{token}` | `api_v1_public_technician_opt_in_retrieve` | ok | member surface |
| POST | `/public/technician-opt-in/{token}` | `api_v1_public_technician_opt_in_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/day-passes` | `api_v1_public_day_passes_list` | ok | member surface |
| GET | `/public/{makerspace_slug}/equipment-kits/` | `api_v1_public_equipment_kits_list` | ok | member surface |
| GET | `/public/{makerspace_slug}/events/{public_token}/` | `api_v1_public_events_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/events/{public_token}/calendar.ics` | `api_v1_public_events_calendar.ics_retrieve_2` | ok | member surface |
| GET | `/public/{makerspace_slug}/events/{public_token}/eligibility/` | `api_v1_public_events_eligibility_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/events/{public_token}/feedback/` | `api_v1_public_events_feedback_retrieve` | ok | member surface |
| POST | `/public/{makerspace_slug}/events/{public_token}/feedback/` | `api_v1_public_events_feedback_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/events/{public_token}/register/` | `api_v1_public_events_register_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/events/{public_token}/tickets/` | `api_v1_public_events_tickets_retrieve` | ok | member surface |
| POST | `/public/{makerspace_slug}/events/{public_token}/tickets/` | `api_v1_public_events_tickets_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/events/{public_token}/website/` | `api_v1_public_events_website_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/inventory/categories/` | `api_v1_public_inventory_categories_list` | ok | member surface |
| GET | `/public/{makerspace_slug}/inventory/{id}/` | `api_v1_public_inventory_retrieve` | ok | member surface |
| DELETE | `/public/{makerspace_slug}/inventory/{id}/watch/` | `api_v1_public_inventory_watch_destroy` | ok | member surface |
| POST | `/public/{makerspace_slug}/inventory/{id}/watch/` | `api_v1_public_inventory_watch_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/invitation-requests` | `api_v1_public_invitation_requests_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/machine-jobs` | `api_v1_public_machine_jobs_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/machine-service-requests` | `api_v1_public_machine_service_requests_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/machine-service/3d-printer/consumable-pools` | `api_v1_public_machine_service_3d_printer_consumable_pools_list` | ok | member surface |
| GET | `/public/{makerspace_slug}/machine-service/3d-printer/queues` | `api_v1_public_machine_service_3d_printer_queues_list` | ok | member surface |
| POST | `/public/{makerspace_slug}/machine-service/3d-printer/requests` | `api_v1_public_machine_service_3d_printer_requests_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/machine-service/3d-printer/uploads` | `api_v1_public_machine_service_3d_printer_uploads_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/machine-types/{type_id}/intake` | `api_v1_public_machine_types_intake_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/membership-admission` | `api_v1_public_membership_admission_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/membership-invites/{code}` | `api_v1_public_membership_invites_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/membership-plans` | `api_v1_public_membership_plans_list` | ok | member surface |
| POST | `/public/{makerspace_slug}/membership-requests` | `api_v1_public_membership_requests_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/my-bookings/` | `api_v1_public_my_bookings_retrieve` | ok | member surface |
| DELETE | `/public/{makerspace_slug}/my-bookings/calendar/` | `api_v1_public_my_bookings_calendar_destroy` | ok | member surface |
| GET | `/public/{makerspace_slug}/my-bookings/calendar/` | `api_v1_public_my_bookings_calendar_retrieve` | ok | member surface |
| POST | `/public/{makerspace_slug}/my-bookings/calendar/` | `api_v1_public_my_bookings_calendar_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/my-bookings/{public_token}/reschedule/` | `api_v1_public_my_bookings_reschedule_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/page/` | `api_v1_public_page_retrieve` | ok | member surface |
| POST | `/public/{makerspace_slug}/presence-sessions` | `api_v1_public_presence_sessions_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/pricing/quote` | `api_v1_public_pricing_quote_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/requests` | `api_v1_public_requests_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/requests/contextual` | `api_v1_public_requests_contextual_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/requests/email-code` | `api_v1_public_requests_email_code_create` | ok | member surface |
| GET | `/public/{makerspace_slug}/spaces/{public_token}/` | `api_v1_public_spaces_retrieve` | ok | member surface |
| GET | `/public/{makerspace_slug}/stats/` | `api_v1_public_stats_retrieve` | ok | member surface |
| POST | `/public/{makerspace_slug}/tools/checklist` | `api_v1_public_tools_checklist_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/tools/checkout` | `api_v1_public_tools_checkout_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/tools/evidence-url` | `api_v1_public_tools_evidence_url_create` | ok | member surface |
| POST | `/public/{makerspace_slug}/tools/return` | `api_v1_public_tools_return_create` | ok | member surface |

### Staff and space manager (837)

| Method | Path | operationId | Status | Note |
|---|---|---|---|---|
| GET | `/admin/accessible-events/` | `api_v1_admin_accessible_events_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/adapter-artifacts/{id}/url` | `api_v1_admin_adapter_artifacts_url_retrieve` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/adapter-bindings/{id}` | `api_v1_admin_adapter_bindings_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapter-bindings/{id}` | `api_v1_admin_adapter_bindings_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/aim` | `api_v1_admin_adapter_bindings_aim_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/commands` | `api_v1_admin_adapter_bindings_commands_create` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/adapter-bindings/{id}/config` | `api_v1_admin_adapter_bindings_config_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapter-bindings/{id}/detections` | `api_v1_admin_adapter_bindings_detections_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/indicate` | `api_v1_admin_adapter_bindings_indicate_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapter-bindings/{id}/jobs` | `api_v1_admin_adapter_bindings_jobs_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/jobs` | `api_v1_admin_adapter_bindings_jobs_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/jog` | `api_v1_admin_adapter_bindings_jog_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/log-bundle` | `api_v1_admin_adapter_bindings_log_bundle_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/adapter-bindings/{id}/poses` | `api_v1_admin_adapter_bindings_poses_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapter-bindings/{id}/poses` | `api_v1_admin_adapter_bindings_poses_list` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/adapter-bindings/{id}/poses` | `api_v1_admin_adapter_bindings_poses_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapter-bindings/{id}/position` | `api_v1_admin_adapter_bindings_position_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-bindings/{id}/watch` | `api_v1_admin_adapter_bindings_watch_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/adapter-credentials/{id}` | `api_v1_admin_adapter_credentials_destroy` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/adapter-watches/{id}` | `api_v1_admin_adapter_watches_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapter-watches/{id}/snapshot` | `api_v1_admin_adapter_watches_snapshot_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}` | `api_v1_admin_adapters_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/access-decisions` | `api_v1_admin_adapters_access_decisions_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapters/{id}/bindings` | `api_v1_admin_adapters_bindings_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/commands` | `api_v1_admin_adapters_commands_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/config-versions` | `api_v1_admin_adapters_config_versions_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapters/{id}/config-versions` | `api_v1_admin_adapters_config_versions_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/events` | `api_v1_admin_adapters_events_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/usage` | `api_v1_admin_adapters_usage_retrieve` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/adapters/{id}/webhook` | `api_v1_admin_adapters_webhook_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/webhook` | `api_v1_admin_adapters_webhook_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/adapters/{id}/webhook` | `api_v1_admin_adapters_webhook_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/adapters/{id}/webhook/deliveries` | `api_v1_admin_adapters_webhook_deliveries_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/adapters/{id}/webhook/rotate` | `api_v1_admin_adapters_webhook_rotate_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/api-clients/{id}` | `api_v1_admin_api_clients_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/api-clients/{id}` | `api_v1_admin_api_clients_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/api-clients/{id}` | `api_v1_admin_api_clients_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/api-clients/{id}/rotate-secret` | `api_v1_admin_api_clients_rotate_secret_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/api-key-requests` | `api_v1_admin_api_key_requests_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/api-key-requests` | `api_v1_admin_api_key_requests_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/assets/{id}` | `api_v1_admin_assets_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/assets/{id}/fix-status` | `api_v1_admin_assets_fix_status_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/assets/{id}/qr` | `api_v1_admin_assets_qr_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/assets/{id}/qr-history` | `api_v1_admin_assets_qr_history_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/assets/{id}/warranty` | `api_v1_admin_assets_warranty_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/assets/{id}/warranty` | `api_v1_admin_assets_warranty_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/audit-logs` | `api_v1_admin_audit_logs_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/backups/{archive_id}/download-url` | `api_v1_admin_backups_download_url_create` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| POST | `/admin/booking-issues/{id}/resolve/` | `api_v1_admin_booking_issues_resolve_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/booking-staff-grants/{id}/` | `api_v1_admin_booking_staff_grants_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/booking-staff-grants/{id}/revoke/` | `api_v1_admin_booking_staff_grants_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/booking-staff-invites/redeem/` | `api_v1_admin_booking_staff_invites_redeem_create` | web-only | native member sessions never redeem booking staff invites (surface_policy) |
| POST | `/admin/booking-staff-invites/{id}/revoke/` | `api_v1_admin_booking_staff_invites_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/bookings/{id}/cancel/` | `api_v1_admin_bookings_cancel_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/bookings/{id}/readiness/` | `api_v1_admin_bookings_readiness_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/bookings/{id}/time/` | `api_v1_admin_bookings_time_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/bulk/bookings/{decision}` | `api_v1_admin_bulk_bookings_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/bulk/event-registrations/{decision}` | `api_v1_admin_bulk_event_registrations_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/bulk/requests/{decision}` | `api_v1_admin_bulk_requests_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/card-designs/{id}` | `api_v1_admin_card_designs_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-designs/{id}` | `api_v1_admin_card_designs_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/card-designs/{id}` | `api_v1_admin_card_designs_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-designs/{id}/apply-template` | `api_v1_admin_card_designs_apply_template_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-designs/{id}/asset-library` | `api_v1_admin_card_designs_asset_library_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/card-designs/{id}/asset-library/{asset_id}` | `api_v1_admin_card_designs_asset_library_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-designs/{id}/badge-import` | `api_v1_admin_card_designs_badge_import_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-designs/{id}/barcode` | `api_v1_admin_card_designs_barcode_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-designs/{id}/brand-kit` | `api_v1_admin_card_designs_brand_kit_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-designs/{id}/convert-to-free-canvas` | `api_v1_admin_card_designs_convert_to_free_canvas_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-designs/{id}/csv-merge` | `api_v1_admin_card_designs_csv_merge_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-designs/{id}/fonts/{family_slug}/{weight}` | `admin_card_design_font_file` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-jobs/{id}/cancel` | `api_v1_admin_card_jobs_cancel_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-jobs/{id}/result` | `api_v1_admin_card_jobs_result_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/card-templates/{id}` | `api_v1_admin_card_templates_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-templates/{id}` | `api_v1_admin_card_templates_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/card-templates/{id}` | `api_v1_admin_card_templates_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/card-templates/{id}/duplicate` | `api_v1_admin_card_templates_duplicate_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-templates/{id}/export` | `api_v1_admin_card_templates_export_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/card-verifications/{token}/staff` | `api_v1_admin_card_verifications_staff_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/categories/{id}` | `api_v1_admin_categories_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/categories/{id}` | `api_v1_admin_categories_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/categories/{id}` | `api_v1_admin_categories_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/certification-grants/{id}/renew` | `api_v1_admin_certification_grants_renew_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/certification-grants/{id}/revoke` | `api_v1_admin_certification_grants_revoke_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/certification-types/{id}` | `api_v1_admin_certification_types_destroy` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/certification-types/{id}` | `api_v1_admin_certification_types_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/certification-types/{id}/grants` | `api_v1_admin_certification_types_grants_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/certification-types/{id}/grants` | `api_v1_admin_certification_types_grants_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/certification-types/{id}/members` | `api_v1_admin_certification_types_members_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/containers/{id}/contents` | `api_v1_admin_containers_contents_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/containers/{id}/history` | `api_v1_admin_containers_history_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/containers/{id}/move` | `api_v1_admin_containers_move_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/device-printer-bindings/{id}` | `api_v1_admin_device_printer_bindings_destroy` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/device-printer-bindings/{id}` | `api_v1_admin_device_printer_bindings_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/devices/{id}` | `api_v1_admin_devices_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/devices/{id}` | `api_v1_admin_devices_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/devices/{id}/enrollments` | `api_v1_admin_devices_enrollments_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/devices/{id}/revoke` | `api_v1_admin_devices_revoke_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/direct-loans/{id}/return` | `api_v1_admin_direct_loans_return_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/event-addons/{id}/` | `api_v1_admin_event_addons_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/event-addons/{id}/` | `api_v1_admin_event_addons_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-certificates/{id}/download/` | `api_v1_admin_event_certificates_download_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/event-id-cards/{id}` | `api_v1_admin_event_id_cards_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-id-cards/{id}/download` | `api_v1_admin_event_id_cards_download_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-id-cards/{id}/revoke` | `api_v1_admin_event_id_cards_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-orders/{id}/` | `api_v1_admin_event_orders_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/event-pass-types/{id}/` | `api_v1_admin_event_pass_types_partial_update` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/event-registrations/{id}/answers/` | `api_v1_admin_event_registrations_answers_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-registrations/{id}/collect-payment/` | `api_v1_admin_event_registrations_collect_payment_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-registrations/{id}/correct-attendance/` | `api_v1_admin_event_registrations_correct_attendance_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-registrations/{id}/pay-link/` | `api_v1_admin_event_registrations_pay_link_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-registrations/{id}/restore/` | `api_v1_admin_event_registrations_restore_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-series-collaborations/{id}/remove/` | `api_v1_admin_event_series_collaborations_remove_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-series-collaborations/{id}/respond/` | `api_v1_admin_event_series_collaborations_respond_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-series-invites/{id}/revoke/` | `api_v1_admin_event_series_invites_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-series/{id}/` | `api_v1_admin_event_series_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/event-series/{id}/` | `api_v1_admin_event_series_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-series/{id}/collaborators/` | `api_v1_admin_event_series_collaborators_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/event-series/{id}/collaborators/` | `api_v1_admin_event_series_collaborators_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-series/{id}/guests/` | `api_v1_admin_event_series_guests_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/event-series/{id}/image` | `api_v1_admin_event_series_image_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-series/{id}/image` | `api_v1_admin_event_series_image_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/event-series/{id}/image` | `api_v1_admin_event_series_image_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-series/{id}/invites/` | `api_v1_admin_event_series_invites_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-series/{id}/invites/` | `api_v1_admin_event_series_invites_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/event-series/{id}/pass-types/` | `api_v1_admin_event_series_pass_types_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/event-series/{id}/pass-types/` | `api_v1_admin_event_series_pass_types_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/event-speakers/{id}/remove/` | `api_v1_admin_event_speakers_remove_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/event-staff-grants/{id}/` | `api_v1_admin_event_staff_grants_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-staff-grants/{id}/revoke/` | `api_v1_admin_event_staff_grants_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/event-staff-invites/redeem/` | `api_v1_admin_event_staff_invites_redeem_create` | ok | invite token redeemed by a native MEMBER grant, no X-Makerspace-Id (surface_policy _NATIVE_MEMBER_MAY_USE) |
| POST | `/admin/event-staff-invites/{id}/revoke/` | `api_v1_admin_event_staff_invites_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/event-ticket-types/{id}/` | `api_v1_admin_event_ticket_types_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/event-ticket-types/{id}/` | `api_v1_admin_event_ticket_types_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/host-options/` | `api_v1_admin_events_host_options_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/insights/` | `api_v1_admin_events_insights_retrieve` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/events/{id}/` | `api_v1_admin_events_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/` | `api_v1_admin_events_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/events/{id}/` | `api_v1_admin_events_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/addons/` | `api_v1_admin_events_addons_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/addons/` | `api_v1_admin_events_addons_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/analytics/extras/` | `api_v1_admin_events_analytics_extras_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/application-stages/{stage_id}/my-reviews/` | `api_v1_admin_events_application_stages_my_reviews_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/assets/{asset_id}/download/` | `api_v1_admin_events_assets_download_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/assigned-sponsors/` | `api_v1_admin_events_assigned_sponsors_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/badge-designs` | `api_v1_admin_events_badge_designs_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/badge-designs/{role}` | `api_v1_admin_events_badge_designs_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/badge-template/` | `api_v1_admin_events_badge_template_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/badge-template/` | `api_v1_admin_events_badge_template_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/badges.pdf` | `api_v1_admin_events_badges.pdf_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/badges/design-preview.pdf` | `api_v1_admin_events_badges_design_preview.pdf_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/badges/designs/` | `api_v1_admin_events_badges_designs_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/badges/designs/` | `api_v1_admin_events_badges_designs_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/badges/desk-design/` | `api_v1_admin_events_badges_desk_design_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/badges/print-jobs/` | `api_v1_admin_events_badges_print_jobs_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/badges/print-jobs/{job_id}/` | `api_v1_admin_events_badges_print_jobs_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/badges/print-jobs/{job_id}/download/` | `api_v1_admin_events_badges_print_jobs_download_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/badges/print-receipts` | `api_v1_admin_events_badges_print_receipts_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/broadcast-templates/` | `api_v1_admin_events_broadcast_templates_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/broadcasts/` | `api_v1_admin_events_broadcasts_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/broadcasts/` | `api_v1_admin_events_broadcasts_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/events/{id}/broadcasts/{campaign_id}/` | `api_v1_admin_events_broadcasts_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/broadcasts/{campaign_id}/` | `api_v1_admin_events_broadcasts_retrieve_2` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/events/{id}/broadcasts/{campaign_id}/` | `api_v1_admin_events_broadcasts_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/broadcasts/{campaign_id}/tallies/` | `api_v1_admin_events_broadcasts_tallies_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/card-designs` | `api_v1_admin_events_card_designs_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/card-jobs` | `api_v1_admin_events_card_jobs_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/card-jobs` | `api_v1_admin_events_card_jobs_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/card-settings` | `api_v1_admin_events_card_settings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/card-settings` | `api_v1_admin_events_card_settings_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificate-artwork/` | `api_v1_admin_events_certificate_artwork_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/certificate-artwork/by-resource/{resource_id}/` | `api_v1_admin_events_certificate_artwork_by_resource_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/certificate-artwork/{artwork_id}/` | `api_v1_admin_events_certificate_artwork_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificate-artwork/{artwork_id}/finalize/` | `api_v1_admin_events_certificate_artwork_finalize_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/certificate-template/` | `api_v1_admin_events_certificate_template_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificate-template/` | `api_v1_admin_events_certificate_template_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/certificate-template/` | `api_v1_admin_events_certificate_template_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificate-template/preview.pdf` | `api_v1_admin_events_certificate_template_preview.pdf_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificates/bulk/` | `api_v1_admin_events_certificates_bulk_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/certificates/eligibility/` | `api_v1_admin_events_certificates_eligibility_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/certificates/signatories/` | `api_v1_admin_events_certificates_signatories_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificates/signatories/` | `api_v1_admin_events_certificates_signatories_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/certificates/verification-policy/` | `api_v1_admin_events_certificates_verification_policy_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/certificates/verification-policy/` | `api_v1_admin_events_certificates_verification_policy_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/check-in/card-scan` | `api_v1_admin_events_check_in_card_scan_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/check-in/offline-roster/` | `api_v1_admin_events_check_in_offline_roster_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/check-in/offline-sync/` | `api_v1_admin_events_check_in_offline_sync_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/events/{id}/check-in/station/` | `api_v1_admin_events_check_in_station_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/check-in/station/` | `api_v1_admin_events_check_in_station_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/check-in/station/reveal/` | `api_v1_admin_events_check_in_station_reveal_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/check-in/station/rotate/` | `api_v1_admin_events_check_in_station_rotate_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/design-seeds/preview.pdf` | `api_v1_admin_events_design_seeds_preview.pdf_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/duplicate/` | `api_v1_admin_events_duplicate_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/feedback-responses/` | `api_v1_admin_events_feedback_responses_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/feedback-survey/` | `api_v1_admin_events_feedback_survey_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/feedback-survey/` | `api_v1_admin_events_feedback_survey_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/feedback-survey/templates/` | `api_v1_admin_events_feedback_survey_templates_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/forms/{form_key}/` | `api_v1_admin_events_forms_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/forms/{form_key}/` | `api_v1_admin_events_forms_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/gallery/` | `api_v1_admin_events_gallery_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/id-cards` | `api_v1_admin_events_id_cards_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/id-cards` | `api_v1_admin_events_id_cards_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/id-cards/extras` | `api_v1_admin_events_id_cards_extras_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/events/{id}/image` | `api_v1_admin_events_image_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/image` | `api_v1_admin_events_image_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/image` | `api_v1_admin_events_image_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/invites/bulk/` | `api_v1_admin_events_invites_bulk_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/judging-rounds/` | `api_v1_admin_events_judging_rounds_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/judging-rounds/` | `api_v1_admin_events_judging_rounds_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/judging-signals/` | `api_v1_admin_events_judging_signals_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/lists/{list_key}/presets/` | `api_v1_admin_events_lists_presets_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/mentor-alert-routes/` | `api_v1_admin_events_mentor_alert_routes_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/mentor-alert-routes/` | `api_v1_admin_events_mentor_alert_routes_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/peoples-choice/` | `api_v1_admin_events_peoples_choice_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/events/{id}/peoples-choice/` | `api_v1_admin_events_peoples_choice_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/registrations/` | `api_v1_admin_events_registrations_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/registrations/` | `api_v1_admin_events_registrations_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/registrations/{registration_id}/reaccept/` | `api_v1_admin_events_registrations_reaccept_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/short-link/` | `api_v1_admin_events_short_link_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/short-link/` | `api_v1_admin_events_short_link_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/speakers/` | `api_v1_admin_events_speakers_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/speakers/` | `api_v1_admin_events_speakers_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/speakers/invite/` | `api_v1_admin_events_speakers_invite_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/sponsors/{sponsor_id}/resumes/{participant_asset_id}/` | `api_v1_admin_events_sponsors_resumes_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/sponsors/{sponsor_id}/submissions/` | `api_v1_admin_events_sponsors_submissions_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/submission-stages/` | `api_v1_admin_events_submission_stages_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/events/{id}/submission-stages/` | `api_v1_admin_events_submission_stages_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/submissions/` | `api_v1_admin_events_submissions_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/submissions/integrity/` | `api_v1_admin_events_submissions_integrity_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/teams/` | `api_v1_admin_events_teams_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/teams/{team_id}/` | `api_v1_admin_events_teams_retrieve_2` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/ticket-types/` | `api_v1_admin_events_ticket_types_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/ticket-types/` | `api_v1_admin_events_ticket_types_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/events/{id}/tracks/` | `api_v1_admin_events_tracks_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/tracks/` | `api_v1_admin_events_tracks_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/events/{id}/venue-fee/charge/` | `api_v1_admin_events_venue_fee_charge_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/evidence/{id}` | `api_v1_admin_evidence_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/guest-certification-grants/{id}/revoke` | `api_v1_admin_guest_certification_grants_revoke_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/id-programme-cards/{id}` | `api_v1_admin_id_programme_cards_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programme-cards/{id}` | `api_v1_admin_id_programme_cards_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/id-programme-cards/{id}` | `api_v1_admin_id_programme_cards_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programme-cards/{id}/download` | `api_v1_admin_id_programme_cards_download_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/id-programmes/{id}` | `api_v1_admin_id_programmes_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programmes/{id}` | `api_v1_admin_id_programmes_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/id-programmes/{id}` | `api_v1_admin_id_programmes_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programmes/{id}/approval` | `api_v1_admin_id_programmes_approval_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/id-programmes/{id}/approval` | `api_v1_admin_id_programmes_approval_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programmes/{id}/card-jobs` | `api_v1_admin_id_programmes_card_jobs_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/id-programmes/{id}/card-jobs` | `api_v1_admin_id_programmes_card_jobs_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programmes/{id}/cards` | `api_v1_admin_id_programmes_cards_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/id-programmes/{id}/cards` | `api_v1_admin_id_programmes_cards_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/id-programmes/{id}/cards/decide` | `api_v1_admin_id_programmes_cards_decide_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/id-programmes/{id}/design` | `api_v1_admin_id_programmes_design_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/id-programmes/{id}/imports` | `api_v1_admin_id_programmes_imports_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/id-programmes/{id}/imports/preview` | `api_v1_admin_id_programmes_imports_preview_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/incident-actions/{id}` | `api_v1_admin_incident_actions_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/incidents/{id}` | `api_v1_admin_incidents_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/incidents/{id}` | `api_v1_admin_incidents_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/incidents/{id}/actions` | `api_v1_admin_incidents_actions_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/incidents/{id}/assignees` | `api_v1_admin_incidents_assignees_retrieve` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/induction-links/{id}` | `api_v1_admin_induction_links_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/inventory/needs-fix` | `api_v1_admin_inventory_needs_fix_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/inventory/{id}` | `api_v1_admin_inventory_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/inventory/{id}` | `api_v1_admin_inventory_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/inventory/{id}/adjust-quantity` | `api_v1_admin_inventory_adjust_quantity_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/inventory/{id}/chain-of-custody` | `api_v1_admin_inventory_chain_of_custody_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/inventory/{id}/image` | `api_v1_admin_inventory_image_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/inventory/{id}/image` | `api_v1_admin_inventory_image_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/inventory/{id}/image` | `api_v1_admin_inventory_image_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/inventory/{id}/needs-fix` | `api_v1_admin_inventory_needs_fix_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/inventory/{id}/qr-history` | `api_v1_admin_inventory_qr_history_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/inventory/{product_pk}/assets` | `api_v1_admin_inventory_assets_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/invitation-requests/{id}/decline` | `api_v1_admin_invitation_requests_decline_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/invitation-requests/{id}/invite` | `api_v1_admin_invitation_requests_invite_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/issues/{id}` | `api_v1_admin_issues_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/kiosk-replays/{id}/` | `api_v1_admin_kiosk_replays_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/kiosk-stations/{id}/` | `api_v1_admin_kiosk_stations_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/kiosk-stations/{id}/` | `api_v1_admin_kiosk_stations_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/kiosk-stations/{id}/reveal/` | `api_v1_admin_kiosk_stations_reveal_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/kiosk-stations/{id}/rotate/` | `api_v1_admin_kiosk_stations_rotate_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/ledger` | `api_v1_admin_ledger_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/machine-access/{id}/revoke` | `api_v1_admin_machine_access_revoke_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machine-service-report` | `api_v1_admin_machine_service_report_retrieve` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| POST | `/admin/machine-service/batches/{id}/complete` | `api_v1_admin_machine_service_batches_complete_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machine-service/consumable-pools/{id}` | `api_v1_admin_machine_service_consumable_pools_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machine-service/consumable-pools/{id}` | `api_v1_admin_machine_service_consumable_pools_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machine-service/consumable-pools/{id}/adjustments` | `api_v1_admin_machine_service_consumable_pools_adjustments_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machine-service/files/{id}/url` | `api_v1_admin_machine_service_files_url_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machine-service/requests/{id}` | `api_v1_admin_machine_service_requests_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/machine-service/requests/{id}/collect` | `api_v1_admin_machine_service_requests_collect_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/machine-service/requests/{id}/uncollected` | `api_v1_admin_machine_service_requests_uncollected_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/machine-type-integrations/{id}` | `api_v1_admin_machine_type_integrations_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machine-type-integrations/{id}` | `api_v1_admin_machine_type_integrations_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machine-type-integrations/{id}` | `api_v1_admin_machine_type_integrations_partial_update` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/machines/documents/{id}` | `api_v1_admin_machines_documents_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/documents/{id}/url` | `api_v1_admin_machines_documents_url_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}` | `api_v1_admin_machines_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machines/{id}` | `api_v1_admin_machines_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/consumable-candidates` | `api_v1_admin_machines_consumable_candidates_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/consumables` | `api_v1_admin_machines_consumables_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/consumables` | `api_v1_admin_machines_consumables_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/machines/{id}/consumables/{cid}` | `api_v1_admin_machines_consumables_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/consumables/{cid}/log` | `api_v1_admin_machines_consumables_log_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/documents` | `api_v1_admin_machines_documents_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/documents` | `api_v1_admin_machines_documents_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/documents/presign` | `api_v1_admin_machines_documents_presign_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/downtime` | `api_v1_admin_machines_downtime_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machines/{id}/downtime` | `api_v1_admin_machines_downtime_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/error-logs` | `api_v1_admin_machines_error_logs_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/error-logs` | `api_v1_admin_machines_error_logs_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/machines/{id}/image` | `api_v1_admin_machines_image_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/image` | `api_v1_admin_machines_image_create` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/machines/{id}/image` | `api_v1_admin_machines_image_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/lockout` | `api_v1_admin_machines_lockout_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machines/{id}/open-access` | `api_v1_admin_machines_open_access_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/operator-candidates` | `api_v1_admin_machines_operator_candidates_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/operators` | `api_v1_admin_machines_operators_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/operators` | `api_v1_admin_machines_operators_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/machines/{id}/operators/{user_pk}` | `api_v1_admin_machines_operators_destroy` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machines/{id}/operators/{user_pk}` | `api_v1_admin_machines_operators_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/publicity` | `api_v1_admin_machines_publicity_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/machines/{id}/publicity` | `api_v1_admin_machines_publicity_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/retire` | `api_v1_admin_machines_retire_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/set-status` | `api_v1_admin_machines_set_status_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/unretire` | `api_v1_admin_machines_unretire_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/usage` | `api_v1_admin_machines_usage_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/machines/{id}/usage` | `api_v1_admin_machines_usage_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/usage-candidates` | `api_v1_admin_machines_usage_candidates_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/machines/{id}/warranty` | `api_v1_admin_machines_warranty_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/machines/{id}/warranty` | `api_v1_admin_machines_warranty_update` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/maintenance/log-documents/{id}/` | `api_v1_admin_maintenance_log_documents_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/maintenance/log-documents/{id}/url/` | `api_v1_admin_maintenance_log_documents_url_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/maintenance/logs/{id}/documents/` | `api_v1_admin_maintenance_logs_documents_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/maintenance/logs/{id}/documents/presign/` | `api_v1_admin_maintenance_logs_documents_presign_create` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/maintenance/schedules/{id}/` | `api_v1_admin_maintenance_schedules_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/maintenance/schedules/{id}/deactivate/` | `api_v1_admin_maintenance_schedules_deactivate_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/maintenance/schedules/{id}/run` | `api_v1_admin_maintenance_schedules_run_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/accountability` | `api_v1_admin_makerspace_accountability_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/active-loans` | `api_v1_admin_makerspace_active_loans_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/allowances` | `api_v1_admin_makerspace_allowances_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/api-client-scopes` | `api_v1_admin_makerspace_api_client_scopes_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/api-clients` | `api_v1_admin_makerspace_api_clients_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/api-clients` | `api_v1_admin_makerspace_api_clients_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/api-settings` | `api_v1_admin_makerspace_api_settings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/api-settings` | `api_v1_admin_makerspace_api_settings_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/archive-requests` | `api_v1_admin_makerspace_archive_requests_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/archive-requests` | `api_v1_admin_makerspace_archive_requests_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/archive-requests/{id}/withdraw` | `api_v1_admin_makerspace_archive_requests_withdraw_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/audit-verifications` | `api_v1_admin_makerspace_audit_verifications_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/audit-verifications` | `api_v1_admin_makerspace_audit_verifications_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/backup-status` | `api_v1_admin_makerspace_backup_status_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/backups` | `api_v1_admin_makerspace_backups_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/backups` | `api_v1_admin_makerspace_backups_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/billing-settings` | `api_v1_admin_makerspace_billing_settings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/billing-settings` | `api_v1_admin_makerspace_billing_settings_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/billing/tax` | `api_v1_admin_makerspace_billing_tax_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/billing/tax` | `api_v1_admin_makerspace_billing_tax_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/billing/tax/validate-gstin` | `api_v1_admin_makerspace_billing_tax_validate_gstin_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/categories` | `api_v1_admin_makerspace_categories_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/categories` | `api_v1_admin_makerspace_categories_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/certification-types` | `api_v1_admin_makerspace_certification_types_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/certification-types` | `api_v1_admin_makerspace_certification_types_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/chat-templates` | `api_v1_admin_makerspace_chat_templates_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/chat-templates` | `api_v1_admin_makerspace_chat_templates_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/consumables/planned-shortages` | `api_v1_admin_makerspace_consumables_planned_shortages_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/consumables/{id}/equipment-sources` | `api_v1_admin_makerspace_consumables_equipment_sources_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/consumables/{id}/use` | `api_v1_admin_makerspace_consumables_use_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/containers` | `api_v1_admin_makerspace_containers_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/containers` | `api_v1_admin_makerspace_containers_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/makerspace/{makerspace_id}/cover` | `api_v1_admin_makerspace_cover_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/cover` | `api_v1_admin_makerspace_cover_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspace/{makerspace_id}/cover` | `api_v1_admin_makerspace_cover_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/dashboard` | `api_v1_admin_makerspace_dashboard_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/data-exports` | `api_v1_admin_makerspace_data_exports_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/data-exports` | `api_v1_admin_makerspace_data_exports_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/data-exports/{job_id}/download-url` | `api_v1_admin_makerspace_data_exports_download_url_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/device-printer-bindings` | `api_v1_admin_makerspace_device_printer_bindings_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/device-printer-bindings` | `api_v1_admin_makerspace_device_printer_bindings_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/devices` | `api_v1_admin_makerspace_devices_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/devices` | `api_v1_admin_makerspace_devices_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/direct-loan-members` | `api_v1_admin_makerspace_direct_loan_members_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/direct-loans` | `api_v1_admin_makerspace_direct_loans_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/direct-loans` | `api_v1_admin_makerspace_direct_loans_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/domain-settings/{domain}` | `api_v1_admin_makerspace_domain_settings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/domain-settings/{domain}` | `api_v1_admin_makerspace_domain_settings_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/donations` | `api_v1_admin_makerspace_donations_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/donations` | `api_v1_admin_makerspace_donations_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/email-logs` | `api_v1_admin_makerspace_email_logs_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/email-logs/{id}/retry` | `api_v1_admin_makerspace_email_logs_retry_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/email-templates` | `api_v1_admin_makerspace_email_templates_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/email-templates/preview` | `api_v1_admin_makerspace_email_templates_preview_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/email/test` | `api_v1_admin_makerspace_email_test_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/equipment-kits` | `api_v1_admin_makerspace_equipment_kits_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/equipment-kits` | `api_v1_admin_makerspace_equipment_kits_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}` | `api_v1_admin_makerspace_equipment_kit_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}/archive` | `api_v1_admin_makerspace_equipment_kits_archive_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}/publication` | `api_v1_admin_makerspace_equipment_kits_publication_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}/versions` | `api_v1_admin_makerspace_equipment_kits_versions_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/equipment-requests/contextual` | `api_v1_admin_makerspace_equipment_requests_contextual_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/event-money-settings` | `api_v1_admin_makerspace_event_money_settings_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspace/{makerspace_id}/event-money-settings` | `api_v1_admin_makerspace_event_money_settings_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/event-registration-queue` | `api_v1_admin_makerspace_event_registration_queue_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/event-room-choices` | `api_v1_admin_makerspace_event_room_choices_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/events/with-room` | `api_v1_admin_makerspace_events_with_room_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link` | `api_v1_admin_makerspace_events_booking_link_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link` | `api_v1_admin_makerspace_events_booking_link_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-desk` | `api_v1_admin_makerspace_events_equipment_desk_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-desk` | `api_v1_admin_makerspace_events_equipment_desk_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/machine-use` | `api_v1_admin_makerspace_events_machine_use_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/machine-use/{link_id}/cost` | `api_v1_admin_makerspace_events_machine_use_cost_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/venue` | `api_v1_admin_makerspace_events_venue_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines` | `api_v1_admin_makerspace_events_workshop_machines_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines` | `api_v1_admin_makerspace_events_workshop_machines_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines/{link_id}` | `api_v1_admin_makerspace_events_workshop_machines_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/finance/events/{event_id}` | `api_v1_admin_makerspace_finance_events_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/finance/events/{event_id}/linked` | `finance_event_linked_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/finance/opening-balances` | `api_v1_admin_makerspace_finance_opening_balances_list` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/finance/opening-balances` | `api_v1_admin_makerspace_finance_opening_balances_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/hosting-invoices` | `api_v1_admin_makerspace_hosting_invoices_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/hosting-invoices/{invoice_id}/checkout` | `api_v1_admin_makerspace_hosting_invoices_checkout_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/hosting-plan` | `api_v1_admin_makerspace_hosting_plan_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/inventory` | `api_v1_admin_makerspace_inventory_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/inventory` | `api_v1_admin_makerspace_inventory_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/inventory/export` | `api_v1_admin_makerspace_inventory_export_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/inventory/import/jobs` | `api_v1_admin_makerspace_inventory_import_jobs_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/inventory/import/jobs/{job_id}` | `api_v1_admin_makerspace_inventory_import_jobs_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/inventory/import/sheet` | `api_v1_admin_makerspace_inventory_import_sheet_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/inventory/reorder-draft` | `api_v1_admin_makerspace_inventory_reorder_draft_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/inventory/reorder-suggestions` | `api_v1_admin_makerspace_inventory_reorder_suggestions_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/kiosk-replays/` | `api_v1_admin_makerspace_kiosk_replays_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/kiosk-stations/` | `api_v1_admin_makerspace_kiosk_stations_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/kiosk-stations/` | `api_v1_admin_makerspace_kiosk_stations_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/kit-checklist-preview` | `api_v1_admin_makerspace_kit_checklist_preview_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/ledger` | `api_v1_admin_makerspace_ledger_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/legal-pages/{slug}` | `api_v1_admin_makerspace_legal_pages_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/legal-pages/{slug}` | `api_v1_admin_makerspace_legal_pages_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/limits` | `api_v1_admin_makerspace_limits_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/loan-reservation-policy` | `api_v1_admin_makerspace_loan_reservation_policy_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspace/{makerspace_id}/loan-reservation-policy` | `api_v1_admin_makerspace_loan_reservation_policy_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/loans/{id}/renew` | `api_v1_admin_makerspace_loans_renew_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/makerspace/{makerspace_id}/logo` | `api_v1_admin_makerspace_logo_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/logo` | `api_v1_admin_makerspace_logo_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspace/{makerspace_id}/logo` | `api_v1_admin_makerspace_logo_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/machine-service-report` | `api_v1_admin_makerspace_machine_service_report_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-type-pricing` | `api_v1_admin_makerspace_machine_type_pricing_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/machine-type-pricing/{machine_type_id}` | `api_v1_admin_makerspace_machine_type_pricing_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-types` | `api_v1_admin_makerspace_machine_types_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/machine-types` | `api_v1_admin_makerspace_machine_types_create` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspace/{makerspace_id}/machine-types/{id}` | `api_v1_admin_makerspace_machine_types_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-types/{machine_type_id}/policy` | `api_v1_admin_makerspace_machine_types_policy_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/machine-types/{machine_type_id}/policy` | `api_v1_admin_makerspace_machine_types_policy_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-types/{type_id}/integration-status` | `api_v1_admin_makerspace_machine_types_integration_status_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-types/{type_id}/integrations` | `api_v1_admin_makerspace_machine_types_integrations_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/machine-types/{type_id}/integrations` | `api_v1_admin_makerspace_machine_types_integrations_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-use/events` | `api_v1_admin_makerspace_machine_use_events_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machine-use/{kind}/{id}/event` | `api_v1_admin_makerspace_machine_use_event_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/machine-use/{kind}/{id}/event` | `api_v1_admin_makerspace_machine_use_event_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/machines` | `api_v1_admin_makerspace_machines_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/machines` | `api_v1_admin_makerspace_machines_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/maintenance-overdue` | `api_v1_admin_makerspace_maintenance_overdue_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/members/{user_id}/included-hours` | `api_v1_admin_makerspace_members_included_hours_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/membership-invitations` | `api_v1_admin_makerspace_membership_invitations_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/modules` | `api_v1_admin_makerspace_modules_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/notification-destinations` | `api_v1_admin_makerspace_notification_destinations_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/notification-destinations` | `api_v1_admin_makerspace_notification_destinations_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/notification-recipient-rules` | `api_v1_admin_makerspace_notification_recipient_rules_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspace/{makerspace_id}/notification-recipient-rules` | `api_v1_admin_makerspace_notification_recipient_rules_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/notification-recipients` | `api_v1_admin_makerspace_notification_recipients_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/notification-recipients` | `api_v1_admin_makerspace_notification_recipients_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/notification-rules` | `api_v1_admin_makerspace_notification_rules_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/notification-rules` | `api_v1_admin_makerspace_notification_rules_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/oauth-apps` | `api_v1_admin_makerspace_oauth_apps_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/oauth-apps` | `api_v1_admin_makerspace_oauth_apps_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/organizations/{organization_id}/hours-bank/` | `api_v1_admin_makerspace_organizations_hours_bank_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspace/{makerspace_id}/organizations/{organization_id}/hours-bank/` | `api_v1_admin_makerspace_organizations_hours_bank_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/payment-settings` | `api_v1_admin_makerspace_payment_settings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/payment-settings` | `api_v1_admin_makerspace_payment_settings_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/payments` | `api_v1_admin_makerspace_payments_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/payments/{payment_id}/amend-settlement` | `api_v1_admin_makerspace_payments_amend_settlement_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/payments/{payment_id}/mark-offline` | `api_v1_admin_makerspace_payments_mark_offline_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/payments/{payment_id}/refund` | `api_v1_admin_makerspace_payments_refund_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/payments/{payment_id}/refunds/{refund_id}/amend` | `api_v1_admin_makerspace_payments_refunds_amend_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/presence-displays` | `api_v1_admin_makerspace_presence_displays_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/presence-displays` | `api_v1_admin_makerspace_presence_displays_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/presence-sessions/check-in` | `api_v1_admin_makerspace_presence_sessions_check_in_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/presence-sessions/check-out` | `api_v1_admin_makerspace_presence_sessions_check_out_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/presence-sessions/current` | `api_v1_admin_makerspace_presence_sessions_current_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/presence-sessions/privacy` | `api_v1_admin_makerspace_presence_sessions_privacy_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/presence-sessions/privacy` | `api_v1_admin_makerspace_presence_sessions_privacy_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/presence-sessions/{account_id}/related` | `api_v1_admin_makerspace_presence_sessions_related_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/pricing/overrides/{target_type}/{target_id}` | `api_v1_admin_makerspace_pricing_overrides_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/pricing/overrides/{target_type}/{target_id}` | `api_v1_admin_makerspace_pricing_overrides_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/pricing/{domain}` | `api_v1_admin_makerspace_pricing_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/pricing/{domain}` | `api_v1_admin_makerspace_pricing_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/printer-jobs` | `api_v1_admin_makerspace_printer_jobs_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/printer-jobs` | `api_v1_admin_makerspace_printer_jobs_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/problem-reports` | `api_v1_admin_makerspace_problem_reports_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/problem-reports/{id}/triage` | `api_v1_admin_makerspace_problem_reports_triage_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/profile` | `api_v1_admin_makerspace_profile_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/profile` | `api_v1_admin_makerspace_profile_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/provision-subdomain` | `api_v1_admin_makerspace_provision_subdomain_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/public-closed-notice` | `api_v1_admin_makerspace_public_closed_notice_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspace/{makerspace_id}/public-closed-notice` | `api_v1_admin_makerspace_public_closed_notice_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/public-stats-settings` | `api_v1_admin_makerspace_public_stats_settings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/public-stats-settings` | `api_v1_admin_makerspace_public_stats_settings_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspace/{makerspace_id}/public-stats-settings` | `api_v1_admin_makerspace_public_stats_settings_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/qr-print-batches` | `api_v1_admin_makerspace_qr_print_batches_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/qr-print-batches` | `api_v1_admin_makerspace_qr_print_batches_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/refund-cases` | `api_v1_admin_makerspace_refund_cases_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/refund-cases/{case_id}/approve` | `api_v1_admin_makerspace_refund_cases_approve_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/refund-cases/{case_id}/decline` | `api_v1_admin_makerspace_refund_cases_decline_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/refund-policies` | `api_v1_admin_makerspace_refund_policies_list` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/makerspace/{makerspace_id}/refund-policies/membership/plans/{plan_id}` | `api_v1_admin_makerspace_refund_policies_membership_plans_destroy` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/refund-policies/membership/plans/{plan_id}` | `api_v1_admin_makerspace_refund_policies_membership_plans_update` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/makerspace/{makerspace_id}/refund-policies/{area}` | `api_v1_admin_makerspace_refund_policies_destroy` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspace/{makerspace_id}/refund-policies/{area}` | `api_v1_admin_makerspace_refund_policies_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/reports/catalog` | `api_v1_admin_makerspace_reports_catalog_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/requests/{id}/cancel` | `api_v1_admin_makerspace_requests_cancel_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/return-policy` | `api_v1_admin_makerspace_return_policy_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspace/{makerspace_id}/return-policy` | `api_v1_admin_makerspace_return_policy_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/selfhost-move-request` | `api_v1_admin_makerspace_selfhost_move_request_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/selfhost-move-request` | `api_v1_admin_makerspace_selfhost_move_request_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/setup-state` | `api_v1_admin_makerspace_setup_state_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/space-pack` | `api_v1_admin_makerspace_space_pack_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/space-pack` | `api_v1_admin_makerspace_space_pack_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/sponsors` | `api_v1_admin_makerspace_sponsors_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspace/{makerspace_id}/sponsors` | `api_v1_admin_makerspace_sponsors_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspace/{makerspace_id}/stock-transfers` | `api_v1_admin_makerspace_stock_transfers_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/stock-transfers` | `api_v1_admin_makerspace_stock_transfers_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/stocktake-schedules` | `api_v1_admin_makerspace_stocktake_schedules_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/stocktake-schedules` | `api_v1_admin_makerspace_stocktake_schedules_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/stocktakes` | `api_v1_admin_makerspace_stocktakes_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/stocktakes` | `api_v1_admin_makerspace_stocktakes_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/subdomain-request` | `api_v1_admin_makerspace_subdomain_request_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspace/{makerspace_id}/subdomain-request` | `api_v1_admin_makerspace_subdomain_request_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/usage` | `api_v1_admin_makerspace_usage_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/waitlist` | `api_v1_admin_makerspace_waitlist_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspace/{makerspace_id}/warranties` | `api_v1_admin_makerspace_warranties_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces` | `api_v1_admin_makerspaces_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces` | `api_v1_admin_makerspaces_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{id}` | `api_v1_admin_makerspaces_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspaces/{id}` | `api_v1_admin_makerspaces_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/booking-issues/` | `api_v1_admin_makerspaces_booking_issues_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/booking-machine-types/` | `api_v1_admin_makerspaces_booking_machine_types_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/bookings/` | `api_v1_admin_makerspaces_bookings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/card-approval-levels` | `api_v1_admin_makerspaces_card_approval_levels_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspaces/{makerspace_id}/card-approval-levels` | `api_v1_admin_makerspaces_card_approval_levels_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/card-designs/titles` | `api_v1_admin_makerspaces_card_designs_titles_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/card-number-schemes` | `api_v1_admin_makerspaces_card_number_schemes_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspaces/{makerspace_id}/card-number-schemes` | `api_v1_admin_makerspaces_card_number_schemes_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/card-photo-batches` | `api_v1_admin_makerspaces_card_photo_batches_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/card-templates` | `api_v1_admin_makerspaces_card_templates_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/card-templates` | `api_v1_admin_makerspaces_card_templates_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/card-templates/builtin/{key}/{theme}` | `api_v1_admin_makerspaces_card_templates_builtin_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/event-categories/` | `api_v1_admin_makerspaces_event_categories_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/event-categories/` | `api_v1_admin_makerspaces_event_categories_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/event-certificate-library/` | `api_v1_admin_makerspaces_event_certificate_library_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/event-certificate-library/` | `api_v1_admin_makerspaces_event_certificate_library_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/event-certificate-library/{template_id}/` | `api_v1_admin_makerspaces_event_certificate_library_retrieve_2` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspaces/{makerspace_id}/event-certificate-library/{template_id}/` | `api_v1_admin_makerspaces_event_certificate_library_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/event-payouts/` | `api_v1_admin_makerspaces_event_payouts_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/event-series-collaborations/` | `api_v1_admin_makerspaces_event_series_collaborations_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/event-series/` | `api_v1_admin_makerspaces_event_series_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/event-series/` | `api_v1_admin_makerspaces_event_series_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/events/embed-policy/` | `api_v1_admin_makerspaces_events_embed_policy_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspaces/{makerspace_id}/events/embed-policy/` | `api_v1_admin_makerspaces_events_embed_policy_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/events/report-switches/` | `api_v1_admin_makerspaces_events_report_switches_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspaces/{makerspace_id}/events/report-switches/` | `api_v1_admin_makerspaces_events_report_switches_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/events/{event_id}/induction` | `api_v1_admin_makerspaces_events_induction_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/events/{event_id}/induction` | `api_v1_admin_makerspaces_events_induction_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/evidence-retention` | `api_v1_admin_makerspaces_evidence_retention_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspaces/{makerspace_id}/evidence-retention` | `api_v1_admin_makerspaces_evidence_retention_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/grafana` | `api_v1_admin_makerspaces_grafana_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/hosting-invitations` | `api_v1_admin_makerspaces_hosting_invitations_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/hosting-invitations` | `api_v1_admin_makerspaces_hosting_invitations_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/image-adapter` | `api_v1_admin_makerspaces_image_adapter_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspaces/{makerspace_id}/image-adapter` | `api_v1_admin_makerspaces_image_adapter_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/incidents` | `api_v1_admin_makerspaces_incidents_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/incidents` | `api_v1_admin_makerspaces_incidents_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/induction-events` | `api_v1_admin_makerspaces_induction_events_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/invitation-requests` | `api_v1_admin_makerspaces_invitation_requests_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/issues` | `api_v1_admin_makerspaces_issues_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/issues` | `api_v1_admin_makerspaces_issues_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/issues/photos` | `api_v1_admin_makerspaces_issues_photos_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-access` | `api_v1_admin_makerspaces_machine_access_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-access` | `api_v1_admin_makerspaces_machine_access_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-access/candidates` | `api_v1_admin_makerspaces_machine_access_candidates_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-bookings` | `api_v1_admin_makerspaces_machine_bookings_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-jobs/{id}/consumables` | `api_v1_admin_makerspaces_machine_jobs_consumables_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-jobs/{id}/consumables` | `api_v1_admin_makerspaces_machine_jobs_consumables_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-materials` | `api_v1_admin_makerspaces_machine_materials_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-materials` | `api_v1_admin_makerspaces_machine_materials_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-service/batches` | `api_v1_admin_makerspaces_machine_service_batches_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-service/board` | `api_v1_admin_makerspaces_machine_service_board_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-service/consumable-pools` | `api_v1_admin_makerspaces_machine_service_consumable_pools_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-service/consumable-pools` | `api_v1_admin_makerspaces_machine_service_consumable_pools_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-service/requests` | `api_v1_admin_makerspaces_machine_service_requests_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/machine-service/requests` | `api_v1_admin_makerspaces_machine_service_requests_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/machine-service/typed-manual-usage` | `api_v1_admin_makerspaces_machine_service_typed_manual_usage_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-service/typed-manual-usage` | `api_v1_admin_makerspaces_machine_service_typed_manual_usage_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-sessions` | `api_v1_admin_makerspaces_machine_sessions_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-sessions` | `api_v1_admin_makerspaces_machine_sessions_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-type-templates` | `api_v1_admin_makerspaces_machine_type_templates_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machine-type-templates` | `api_v1_admin_makerspaces_machine_type_templates_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/intake` | `api_v1_admin_makerspaces_machine_types_intake_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/intake` | `api_v1_admin_makerspaces_machine_types_intake_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/job-settings` | `api_v1_admin_makerspaces_machine_types_job_settings_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/job-settings` | `api_v1_admin_makerspaces_machine_types_job_settings_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/session-settings` | `api_v1_admin_makerspaces_machine_types_session_settings_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/session-settings` | `api_v1_admin_makerspaces_machine_types_session_settings_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machines/{machine_id}/maintenance/logs/` | `api_v1_admin_makerspaces_machines_maintenance_logs_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machines/{machine_id}/maintenance/logs/` | `api_v1_admin_makerspaces_machines_maintenance_logs_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/machines/{machine_id}/maintenance/schedules/` | `api_v1_admin_makerspaces_machines_maintenance_schedules_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/machines/{machine_id}/maintenance/schedules/` | `api_v1_admin_makerspaces_machines_maintenance_schedules_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/makerspaces/{makerspace_id}/maintenance/feed` | `api_v1_admin_makerspaces_maintenance_feed_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/maintenance/feed` | `api_v1_admin_makerspaces_maintenance_feed_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/maintenance/feed` | `api_v1_admin_makerspaces_maintenance_feed_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/member-cards` | `api_v1_admin_makerspaces_member_cards_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/member-cards/presence-check-in` | `api_v1_admin_makerspaces_member_cards_presence_check_in_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/member-claim-codes` | `api_v1_admin_makerspaces_member_claim_codes_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/member-claim-codes` | `api_v1_admin_makerspaces_member_claim_codes_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/member-claim-codes/{claim_id}/revoke` | `api_v1_admin_makerspaces_member_claim_codes_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/members/{user_id}/activity` | `api_v1_admin_makerspaces_members_activity_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/members/{user_id}/events/` | `api_v1_admin_makerspaces_members_events_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/membership-admission` | `api_v1_admin_makerspaces_membership_admission_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspaces/{makerspace_id}/membership-admission` | `api_v1_admin_makerspaces_membership_admission_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/membership-plans` | `api_v1_admin_makerspaces_membership_plans_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/membership-plans` | `api_v1_admin_makerspaces_membership_plans_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/memberships` | `api_v1_admin_makerspaces_memberships_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/memberships` | `api_v1_admin_makerspaces_memberships_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/memberships/{membership_id}/machine-scope` | `api_v1_admin_makerspaces_memberships_machine_scope_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/makerspaces/{makerspace_id}/memberships/{membership_id}/machine-scope` | `api_v1_admin_makerspaces_memberships_machine_scope_update` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspaces/{makerspace_id}/memberships/{membership_id}/role` | `api_v1_admin_makerspaces_memberships_role_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/metabase` | `api_v1_admin_makerspaces_metabase_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/my-jobs` | `api_v1_admin_makerspaces_my_jobs_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/my-maintenance` | `api_v1_admin_makerspaces_my_maintenance_retrieve` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/makerspaces/{makerspace_id}/pii-access` | `api_v1_admin_makerspaces_pii_access_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/pii-access` | `api_v1_admin_makerspaces_pii_access_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/pii-access` | `api_v1_admin_makerspaces_pii_access_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/refund-cases/bulk/{decision}` | `api_v1_admin_makerspaces_refund_cases_bulk_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/refund-cases/{case_id}/membership-suggestion` | `api_v1_admin_makerspaces_refund_cases_membership_suggestion_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/report-schedules` | `api_v1_admin_makerspaces_report_schedules_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/report-schedules` | `api_v1_admin_makerspaces_report_schedules_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/requests/{request_id}/repairs` | `api_v1_admin_makerspaces_requests_repairs_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/requests/{request_id}/repairs` | `api_v1_admin_makerspaces_requests_repairs_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/roles` | `api_v1_admin_makerspaces_roles_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/room-outages/impact` | `api_v1_admin_makerspaces_room_outages_impact_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/saved-report-views` | `api_v1_admin_makerspaces_saved_report_views_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/saved-report-views` | `api_v1_admin_makerspaces_saved_report_views_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/saved-views` | `api_v1_admin_makerspaces_saved_views_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/saved-views` | `api_v1_admin_makerspaces_saved_views_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/security-settings` | `api_v1_admin_makerspaces_security_settings_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspaces/{makerspace_id}/security-settings` | `api_v1_admin_makerspaces_security_settings_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/security/key-events` | `api_v1_admin_makerspaces_security_key_events_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/service-state` | `api_v1_admin_makerspaces_service_state_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/service-state` | `api_v1_admin_makerspaces_service_state_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/shop/event-offers/` | `api_v1_admin_makerspaces_shop_event_offers_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/spaces/` | `api_v1_admin_makerspaces_spaces_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/spaces/` | `api_v1_admin_makerspaces_spaces_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/staff-invitations` | `api_v1_admin_makerspaces_staff_invitations_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/staff-roles/` | `api_v1_admin_makerspaces_staff_roles_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/staff-roles/` | `api_v1_admin_makerspaces_staff_roles_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/staff-roles/bulk-invite/` | `api_v1_admin_makerspaces_staff_roles_bulk_invite_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/subject-maintenance` | `api_v1_admin_makerspaces_subject_maintenance_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/subject-maintenance` | `api_v1_admin_makerspaces_subject_maintenance_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/technician-defaults` | `api_v1_admin_makerspaces_technician_defaults_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/technician-defaults` | `api_v1_admin_makerspaces_technician_defaults_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/technicians` | `api_v1_admin_makerspaces_technicians_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/technicians` | `api_v1_admin_makerspaces_technicians_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/technicians/candidates` | `api_v1_admin_makerspaces_technicians_candidates_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/telemetry` | `api_v1_admin_makerspaces_telemetry_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/makerspaces/{makerspace_id}/telemetry` | `api_v1_admin_makerspaces_telemetry_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/uploads/evidence-url` | `api_v1_admin_makerspaces_uploads_evidence_url_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/waiver` | `api_v1_admin_makerspaces_waiver_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspaces/{makerspace_id}/waiver` | `api_v1_admin_makerspaces_waiver_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/walk-in-members` | `api_v1_admin_makerspaces_walk_in_members_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/makerspaces/{makerspace_id}/walk-in-members` | `api_v1_admin_makerspaces_walk_in_members_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/wallet-credentials` | `api_v1_admin_makerspaces_wallet_credentials_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/makerspaces/{makerspace_id}/wallet-credentials` | `api_v1_admin_makerspaces_wallet_credentials_partial_update` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/makerspaces/{makerspace_id}/website-embed-origins/` | `api_v1_admin_makerspaces_website_embed_origins_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/makerspaces/{makerspace_id}/website-embed-origins/` | `api_v1_admin_makerspaces_website_embed_origins_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/makerspaces/{makerspace_id}/work-orders` | `api_v1_admin_makerspaces_work_orders_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/makerspaces/{makerspace_id}/work-orders` | `api_v1_admin_makerspaces_work_orders_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/member-cards/{id}/download` | `api_v1_admin_member_cards_download_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/member-cards/{id}/email` | `api_v1_admin_member_cards_email_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/member-cards/{id}/photo-request` | `api_v1_admin_member_cards_photo_request_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/member-cards/{id}/print-face` | `api_v1_admin_member_cards_print_face_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/member-cards/{id}/print.pdf` | `api_v1_admin_member_cards_print.pdf_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/member-cards/{id}/reissue` | `api_v1_admin_member_cards_reissue_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/member-cards/{id}/revoke` | `api_v1_admin_member_cards_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/membership-invite-links/{id}/revoke` | `api_v1_admin_membership_invite_links_revoke_create` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/membership-plans/{id}` | `api_v1_admin_membership_plans_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/membership-plans/{id}/archive` | `api_v1_admin_membership_plans_archive_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/membership-plans/{id}/archive` | `api_v1_admin_membership_plans_archive_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/membership-requests/{id}/approve` | `api_v1_admin_membership_requests_approve_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/membership-requests/{id}/revoke` | `api_v1_admin_membership_requests_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/membership-terms/{id}/cancel` | `api_v1_admin_membership_terms_cancel_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/membership-titles/{id}` | `api_v1_admin_membership_titles_destroy` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/membership-titles/{id}` | `api_v1_admin_membership_titles_partial_update` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/memberships/{id}/capabilities` | `api_v1_admin_memberships_capabilities_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/memberships/{id}/consents` | `api_v1_admin_memberships_consents_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/memberships/{id}/extend` | `api_v1_admin_memberships_extend_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/memberships/{id}/history` | `api_v1_admin_memberships_history_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/memberships/{id}/record` | `api_v1_admin_memberships_record_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/memberships/{id}/record` | `api_v1_admin_memberships_record_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/memberships/{id}/revoke` | `api_v1_admin_memberships_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/memberships/{id}/role` | `api_v1_admin_memberships_role_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/memberships/{id}/terms` | `api_v1_admin_memberships_terms_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/memberships/{id}/terms` | `api_v1_admin_memberships_terms_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/memberships/{id}/titles` | `api_v1_admin_memberships_titles_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/memberships/{id}/titles` | `api_v1_admin_memberships_titles_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/memberships/{id}/titles/{title_id}` | `api_v1_admin_memberships_titles_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/memberships/{id}/waiver/witness` | `api_v1_admin_memberships_waiver_witness_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/my-application-reviews/` | `api_v1_admin_my_application_reviews_list` | web-only | event-role desk, web-only by decision 173 |
| DELETE | `/admin/oauth-apps/{id}` | `api_v1_admin_oauth_apps_destroy` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/oauth-apps/{id}` | `api_v1_admin_oauth_apps_partial_update` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/organization-invitations/{id}/` | `api_v1_admin_organization_invitations_destroy` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/` | `admin_organizations_list` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/` | `api_v1_admin_organizations_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| DELETE | `/admin/organizations/{id}/` | `api_v1_admin_organizations_destroy` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/` | `admin_organizations_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| PATCH | `/admin/organizations/{id}/` | `api_v1_admin_organizations_partial_update` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/email-sender/` | `api_v1_admin_organizations_email_sender_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| PUT | `/admin/organizations/{id}/email-sender/` | `api_v1_admin_organizations_email_sender_update` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/events/insights/` | `api_v1_admin_organizations_events_insights_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/hosting-invitations/` | `api_v1_admin_organizations_hosting_invitations_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/{id}/hosting-invitations/` | `api_v1_admin_organizations_hosting_invitations_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/hours-bank/` | `api_v1_admin_organizations_hours_bank_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/hours-bank/{makerspace_id}/ledger/` | `api_v1_admin_organizations_hours_bank_ledger_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/organizations/{id}/invitations/` | `api_v1_admin_organizations_invitations_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/{id}/invitations/` | `api_v1_admin_organizations_invitations_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/makerspaces/` | `api_v1_admin_organizations_makerspaces_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/{id}/makerspaces/` | `api_v1_admin_organizations_makerspaces_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/member-rollup/` | `api_v1_admin_organizations_member_rollup_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/memberships/` | `api_v1_admin_organizations_memberships_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| PATCH | `/admin/organizations/{id}/memberships/{membership_id}/` | `api_v1_admin_organizations_memberships_partial_update` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/{id}/resubmit/` | `api_v1_admin_organizations_resubmit_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{id}/review/` | `api_v1_admin_organizations_review_list` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/{id}/review/` | `api_v1_admin_organizations_review_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organizations/{organization_id}/id-programmes` | `api_v1_admin_organizations_id_programmes_list` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| POST | `/admin/organizations/{organization_id}/id-programmes` | `api_v1_admin_organizations_id_programmes_create` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/organized-events/attendance/` | `api_v1_admin_organized_events_attendance_retrieve` | web-only | organization-derived authority is web-only: native sessions carry local membership authority only |
| GET | `/admin/printer-jobs/{id}` | `api_v1_admin_printer_jobs_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/printer-jobs/{id}/apply` | `api_v1_admin_printer_jobs_apply_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/products/{id}/assets/generate` | `api_v1_admin_products_assets_generate_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/qr-print-batches/{id}` | `api_v1_admin_qr_print_batches_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/qr-print-batches/{id}/download` | `api_v1_admin_qr_print_batches_download_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/qr-print-batches/{id}/items` | `api_v1_admin_qr_print_batches_items_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/qr-print-batches/{id}/label-commands` | `api_v1_admin_qr_print_batches_label_commands_list` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/qr-print-batches/{id}/label-commands` | `api_v1_admin_qr_print_batches_label_commands_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/qr/boxes` | `api_v1_admin_qr_boxes_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/qr/external` | `api_v1_admin_qr_external_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/qr/resolve` | `api_v1_admin_qr_resolve_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/qr/tools` | `api_v1_admin_qr_tools_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/qr/{id}/print` | `api_v1_admin_qr_print_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/qr/{id}/rebind-target` | `api_v1_admin_qr_rebind_target_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/qr/{id}/revoke` | `api_v1_admin_qr_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/report-schedules/{id}` | `api_v1_admin_report_schedules_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/report-schedules/{id}` | `api_v1_admin_report_schedules_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/report-schedules/{id}/run-now` | `api_v1_admin_report_schedules_run_now_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/reports/catalog` | `api_v1_admin_reports_catalog_retrieve` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| POST | `/admin/requests/{id}/accept` | `api_v1_admin_requests_accept_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/requests/{id}/assign-box` | `api_v1_admin_requests_assign_box_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/requests/{id}/issue` | `api_v1_admin_requests_issue_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/requests/{id}/reject` | `api_v1_admin_requests_reject_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/requests/{id}/return` | `api_v1_admin_requests_return_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/requests/{id}/return-due` | `api_v1_admin_requests_return_due_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/requests/{id}/timeline` | `api_v1_admin_requests_timeline_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/search` | `api_v1_admin_search_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/shop/cash-sessions/{id}/close/` | `api_v1_admin_shop_cash_sessions_close_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/shop/cash-sessions/{id}/confirm/` | `api_v1_admin_shop_cash_sessions_confirm_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/shop/orders/{id}/` | `api_v1_admin_shop_orders_retrieve` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/shop/products/{id}/` | `api_v1_admin_shop_products_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/shop/products/{id}/` | `api_v1_admin_shop_products_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/shop/products/{id}/` | `api_v1_admin_shop_products_partial_update` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/shop/products/{id}/image/` | `api_v1_admin_shop_products_image_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/shop/products/{id}/image/` | `api_v1_admin_shop_products_image_create` | ok | native staff grant + X-Makerspace-Id |
| PUT | `/admin/shop/products/{id}/image/` | `api_v1_admin_shop_products_image_update` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/shop/variants/{id}/` | `api_v1_admin_shop_variants_destroy` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/shop/variants/{id}/stock/` | `api_v1_admin_shop_variants_stock_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/space-pack-profiles` | `api_v1_admin_space_pack_profiles_list` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| POST | `/admin/space-pack-profiles` | `api_v1_admin_space_pack_profiles_create` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| GET | `/admin/spaces/{id}/` | `api_v1_admin_spaces_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/spaces/{id}/` | `api_v1_admin_spaces_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/spaces/{id}/arrival/{booking_id}/depart/` | `api_v1_admin_spaces_arrival_depart_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/spaces/{id}/booking-rules/` | `api_v1_admin_spaces_booking_rules_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/spaces/{id}/booking-rules/` | `api_v1_admin_spaces_booking_rules_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/spaces/{id}/bookings/` | `api_v1_admin_spaces_bookings_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/spaces/{id}/bookings/` | `api_v1_admin_spaces_bookings_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/spaces/{id}/bookings/availability/` | `api_v1_admin_spaces_bookings_availability_retrieve` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/spaces/{id}/bookings/quote/` | `api_v1_admin_spaces_bookings_quote_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/spaces/{id}/bookings/readiness/` | `api_v1_admin_spaces_bookings_readiness_retrieve` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/spaces/{id}/broadcasts/` | `api_v1_admin_spaces_broadcasts_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/spaces/{id}/broadcasts/` | `api_v1_admin_spaces_broadcasts_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/spaces/{id}/eligible-members/` | `api_v1_admin_spaces_eligible_members_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| DELETE | `/admin/spaces/{id}/image/` | `api_v1_admin_spaces_image_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/spaces/{id}/organization-bookings/` | `api_v1_admin_spaces_organization_bookings_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/spaces/{id}/organization-bookings/choices/` | `api_v1_admin_spaces_organization_bookings_choices_list` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/spaces/{id}/photos/` | `api_v1_admin_spaces_photos_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/spaces/{id}/photos/` | `api_v1_admin_spaces_photos_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/spaces/{id}/website/` | `api_v1_admin_spaces_website_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PUT | `/admin/spaces/{id}/website/` | `api_v1_admin_spaces_website_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/staff-cards/{id}/print-face` | `api_v1_admin_staff_cards_print_face_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/staff-cards/{id}/reissue` | `api_v1_admin_staff_cards_reissue_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/staff-cards/{id}/revoke` | `api_v1_admin_staff_cards_revoke_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/stocktakes/{id}` | `api_v1_admin_stocktakes_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/stocktakes/{id}/apply-adjustments` | `api_v1_admin_stocktakes_apply_adjustments_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/stocktakes/{id}/approve` | `api_v1_admin_stocktakes_approve_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/stocktakes/{id}/complete` | `api_v1_admin_stocktakes_complete_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/stocktakes/{id}/count-lines` | `api_v1_admin_stocktakes_count_lines_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/stocktakes/{id}/resolve-scan` | `api_v1_admin_stocktakes_resolve_scan_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/admin/subject-maintenance/{id}` | `api_v1_admin_subject_maintenance_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/subject-maintenance/{id}/run` | `api_v1_admin_subject_maintenance_run_create` | ok | native staff grant + X-Makerspace-Id |
| DELETE | `/admin/technicians/{id}` | `api_v1_admin_technicians_destroy` | ok | native staff grant + X-Makerspace-Id |
| GET | `/admin/technicians/{id}` | `api_v1_admin_technicians_retrieve` | ok | native staff grant + X-Makerspace-Id |
| PATCH | `/admin/technicians/{id}` | `api_v1_admin_technicians_partial_update` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/technicians/{id}/consent` | `api_v1_admin_technicians_consent_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/technicians/{id}/opt-in-link` | `api_v1_admin_technicians_opt_in_link_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/users/{id}/restore-access` | `api_v1_admin_users_restore_access_create` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| POST | `/admin/users/{id}/restrict` | `api_v1_admin_users_restrict_create` | web-only | superadmin-only; a superadmin never holds a phone token (decision 356) |
| DELETE | `/admin/warranty/documents/{id}` | `api_v1_admin_warranty_documents_destroy` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/warranty/documents/{id}/url` | `api_v1_admin_warranty_documents_url_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/admin/warranty/{id}/documents` | `api_v1_admin_warranty_documents_list` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/warranty/{id}/documents` | `api_v1_admin_warranty_documents_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/warranty/{id}/documents/presign` | `api_v1_admin_warranty_documents_presign_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/admin/work-orders/{id}/assign` | `api_v1_admin_work_orders_assign_create` | ok | native staff grant + X-Makerspace-Id |
| POST | `/admin/work-orders/{id}/status` | `api_v1_admin_work_orders_status_create` | ok | native staff grant + X-Makerspace-Id |
| GET | `/integrations/makerspace/{makerspace_id}/channels/{channel}` | `api_v1_integrations_makerspace_channels_retrieve_2` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/integrations/makerspace/{makerspace_id}/channels/{channel}` | `api_v1_integrations_makerspace_channels_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/integrations/makerspace/{makerspace_id}/email-suppressions` | `api_v1_integrations_makerspace_email_suppressions_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/integrations/makerspace/{makerspace_id}/email-suppressions` | `api_v1_integrations_makerspace_email_suppressions_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/integrations/makerspace/{makerspace_id}/slack/install/start` | `api_v1_integrations_makerspace_slack_install_start_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/integrations/makerspace/{makerspace_id}/timing-policy` | `api_v1_integrations_makerspace_timing_policy_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| PATCH | `/integrations/makerspace/{makerspace_id}/timing-policy` | `api_v1_integrations_makerspace_timing_policy_partial_update` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/integrations/telegram/test-alert` | `api_v1_integrations_telegram_test_alert_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| GET | `/notifications/broadcasts/{makerspace_id}` | `api_v1_notifications_broadcasts_retrieve` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |
| POST | `/notifications/broadcasts/{makerspace_id}` | `api_v1_notifications_broadcasts_create` | ok | native staff grant + X-Makerspace-Id; delegable (org/resource authority is web-only) |

### Platform (superadmin) (71)

| Method | Path | operationId | Status | Note |
|---|---|---|---|---|
| GET | `/admin/makerspace/{makerspace_id}/restores` | `api_v1_admin_makerspace_restores_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/makerspace/{makerspace_id}/restores` | `api_v1_admin_makerspace_restores_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/accounts` | `api_v1_admin_platform_accounts_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/admins` | `api_v1_admin_platform_admins_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/analytics/makerspaces` | `api_v1_admin_platform_analytics_makerspaces_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/analytics/{report_key}` | `api_v1_admin_platform_analytics_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/announcements` | `api_v1_admin_platform_announcements_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/announcements` | `api_v1_admin_platform_announcements_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/backup-destinations` | `api_v1_admin_platform_backup_destinations_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/backup-destinations` | `api_v1_admin_platform_backup_destinations_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/backup-schedule` | `api_v1_admin_platform_backup_schedule_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/backup-settings` | `api_v1_admin_platform_backup_settings_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/backup-settings` | `api_v1_admin_platform_backup_settings_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/backups` | `api_v1_admin_platform_backups_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/backups` | `api_v1_admin_platform_backups_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/backups/{archive_id}/rehydrate` | `api_v1_admin_platform_backups_rehydrate_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/dashboard` | `api_v1_admin_platform_dashboard_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/email-settings` | `api_v1_admin_platform_email_settings_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/email-settings` | `api_v1_admin_platform_email_settings_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/firebase-web-settings` | `api_v1_admin_platform_firebase_web_settings_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/firebase-web-settings` | `api_v1_admin_platform_firebase_web_settings_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/grafana` | `api_v1_admin_platform_grafana_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/hosting-requests` | `api_v1_admin_platform_hosting_requests_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/image-adapter` | `api_v1_admin_platform_image_adapter_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/image-adapter` | `api_v1_admin_platform_image_adapter_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/inbox` | `api_v1_admin_platform_inbox_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/insights/` | `api_v1_admin_platform_insights_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/ip-blocks` | `api_v1_admin_platform_ip_blocks_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/ip-rules` | `api_v1_admin_platform_ip_rules_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/ip-rules` | `api_v1_admin_platform_ip_rules_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| DELETE | `/admin/platform/legal-pages/{slug}` | `api_v1_admin_platform_legal_pages_destroy` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/legal-pages/{slug}` | `api_v1_admin_platform_legal_pages_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PUT | `/admin/platform/legal-pages/{slug}` | `api_v1_admin_platform_legal_pages_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/limit-defaults` | `api_v1_admin_platform_limit_defaults_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PUT | `/admin/platform/limit-defaults` | `api_v1_admin_platform_limit_defaults_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/login-methods` | `api_v1_admin_platform_login_methods_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/login-methods` | `api_v1_admin_platform_login_methods_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/metabase` | `api_v1_admin_platform_metabase_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/mobile-readiness` | `api_v1_admin_platform_mobile_readiness_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/module-defaults` | `api_v1_admin_platform_module_defaults_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/native-apps` | `api_v1_admin_platform_native_apps_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/native-apps` | `api_v1_admin_platform_native_apps_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/oidc-providers` | `api_v1_admin_platform_oidc_providers_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/oidc-providers` | `api_v1_admin_platform_oidc_providers_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/overview` | `api_v1_admin_platform_overview_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/payment-settings` | `api_v1_admin_platform_payment_settings_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/payment-settings` | `api_v1_admin_platform_payment_settings_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/problems` | `api_v1_admin_platform_problems_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/queues` | `api_v1_admin_platform_queues_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/restore-drills` | `api_v1_admin_platform_restore_drills_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/restore-drills` | `api_v1_admin_platform_restore_drills_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/restores` | `api_v1_admin_platform_restores_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/restores` | `api_v1_admin_platform_restores_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/restores/{restore_id}` | `api_v1_admin_platform_restores_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/restores/{restore_id}/decision` | `api_v1_admin_platform_restores_decision_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/search` | `api_v1_admin_platform_search_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/selfhost-moves` | `api_v1_admin_platform_selfhost_moves_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/social-auth-settings` | `api_v1_admin_platform_social_auth_settings_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/social-auth-settings` | `api_v1_admin_platform_social_auth_settings_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/space-health/{makerspace_id}` | `api_v1_admin_platform_space_health_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/spaces/plan-bulk` | `api_v1_admin_platform_spaces_plan_bulk_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/spaces/{makerspace_id}/chat-templates` | `api_v1_admin_platform_spaces_chat_templates_list` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/platform/spaces/{makerspace_id}/chat-templates` | `api_v1_admin_platform_spaces_chat_templates_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/spaces/{makerspace_id}/snapshot` | `api_v1_admin_platform_spaces_snapshot_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/telemetry` | `api_v1_admin_platform_telemetry_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/telemetry` | `api_v1_admin_platform_telemetry_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/platform/wallet-credentials` | `api_v1_admin_platform_wallet_credentials_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| PATCH | `/admin/platform/wallet-credentials` | `api_v1_admin_platform_wallet_credentials_partial_update` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| GET | `/admin/space-restores/{restore_id}` | `api_v1_admin_space_restores_retrieve` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/space-restores/{restore_id}/abort` | `api_v1_admin_space_restores_abort_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |
| POST | `/admin/space-restores/{restore_id}/confirm` | `api_v1_admin_space_restores_confirm_create` | web-only | web-only by owner decision 356 — superadmin never holds a phone token |

### Other (14)

| Method | Path | operationId | Status | Note |
|---|---|---|---|---|
| GET | `/discover/events/organizers/` | `api_v1_discover_events_organizers_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/event-checkin-stations/{public_token}/badge/{registration_id}/` | `api_v1_event_checkin_stations_badge_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/event-checkin-stations/{public_token}/roster/` | `api_v1_event_checkin_stations_roster_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| DELETE | `/event-checkin-stations/{public_token}/session/` | `api_v1_event_checkin_stations_session_destroy` | n/a | public or signed non-account protocol (own credential, no account token) |
| POST | `/event-checkin-stations/{public_token}/session/` | `api_v1_event_checkin_stations_session_create` | n/a | public or signed non-account protocol (own credential, no account token) |
| POST | `/event-checkin-stations/{public_token}/sync/` | `api_v1_event_checkin_stations_sync_create` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/events/` | `api_v1_events_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/integrations/makerspace/{makerspace_id}/slack/oauth/callback` | `api_v1_integrations_makerspace_slack_oauth_callback_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| POST | `/integrations/makerspace/{makerspace_id}/slack/oauth/callback` | `api_v1_integrations_makerspace_slack_oauth_callback_create` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/notifications/announcements/{makerspace_id}` | `api_v1_notifications_announcements_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/notifications/unsubscribe/{token}` | `api_v1_notifications_unsubscribe_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |
| POST | `/notifications/unsubscribe/{token}` | `api_v1_notifications_unsubscribe_create` | n/a | public or signed non-account protocol (own credential, no account token) |
| POST | `/space-displays/register/` | `api_v1_space_displays_register_create` | n/a | public or signed non-account protocol (own credential, no account token) |
| GET | `/space-displays/state/` | `api_v1_space_displays_state_retrieve` | n/a | public or signed non-account protocol (own credential, no account token) |

## Every new or changed operation since 0.11.0 (763)

Change: n = new, c = changed (request/response/auth), r = operationId renamed. Audience is derived from the path.

| Chg | Method | Path | operationId | Audience |
|---|---|---|---|---|
| n | GET | `/admin/adapter-artifacts/{id}/url` | `api_v1_admin_adapter_artifacts_url_retrieve` | staff |
| n | GET | `/admin/adapter-bindings/{id}` | `api_v1_admin_adapter_bindings_retrieve` | staff |
| n | DELETE | `/admin/adapter-bindings/{id}` | `api_v1_admin_adapter_bindings_destroy` | staff |
| n | POST | `/admin/adapter-bindings/{id}/aim` | `api_v1_admin_adapter_bindings_aim_create` | staff |
| n | GET | `/admin/adapter-bindings/{id}/artifacts` | `api_v1_admin_adapter_bindings_artifacts_retrieve` | staff |
| n | POST | `/admin/adapter-bindings/{id}/commands` | `api_v1_admin_adapter_bindings_commands_create` | staff |
| n | PUT | `/admin/adapter-bindings/{id}/config` | `api_v1_admin_adapter_bindings_config_update` | staff |
| n | GET | `/admin/adapter-bindings/{id}/detections` | `api_v1_admin_adapter_bindings_detections_retrieve` | staff |
| n | POST | `/admin/adapter-bindings/{id}/indicate` | `api_v1_admin_adapter_bindings_indicate_create` | staff |
| n | GET | `/admin/adapter-bindings/{id}/jobs` | `api_v1_admin_adapter_bindings_jobs_retrieve` | staff |
| n | POST | `/admin/adapter-bindings/{id}/jobs` | `api_v1_admin_adapter_bindings_jobs_create` | staff |
| n | POST | `/admin/adapter-bindings/{id}/jog` | `api_v1_admin_adapter_bindings_jog_create` | staff |
| n | POST | `/admin/adapter-bindings/{id}/log-bundle` | `api_v1_admin_adapter_bindings_log_bundle_create` | staff |
| n | GET | `/admin/adapter-bindings/{id}/poses` | `api_v1_admin_adapter_bindings_poses_list` | staff |
| n | PUT | `/admin/adapter-bindings/{id}/poses` | `api_v1_admin_adapter_bindings_poses_update` | staff |
| n | DELETE | `/admin/adapter-bindings/{id}/poses` | `api_v1_admin_adapter_bindings_poses_destroy` | staff |
| n | GET | `/admin/adapter-bindings/{id}/position` | `api_v1_admin_adapter_bindings_position_retrieve` | staff |
| n | GET | `/admin/adapter-bindings/{id}/telemetry` | `api_v1_admin_adapter_bindings_telemetry_retrieve` | staff |
| n | POST | `/admin/adapter-bindings/{id}/watch` | `api_v1_admin_adapter_bindings_watch_create` | staff |
| n | DELETE | `/admin/adapter-credentials/{id}` | `api_v1_admin_adapter_credentials_destroy` | staff |
| n | DELETE | `/admin/adapter-watches/{id}` | `api_v1_admin_adapter_watches_destroy` | staff |
| n | POST | `/admin/adapter-watches/{id}/snapshot` | `api_v1_admin_adapter_watches_snapshot_create` | staff |
| n | GET | `/admin/adapters/{id}` | `api_v1_admin_adapters_retrieve` | staff |
| n | GET | `/admin/adapters/{id}/access-decisions` | `api_v1_admin_adapters_access_decisions_retrieve` | staff |
| n | POST | `/admin/adapters/{id}/bindings` | `api_v1_admin_adapters_bindings_create` | staff |
| n | GET | `/admin/adapters/{id}/commands` | `api_v1_admin_adapters_commands_list` | staff |
| n | GET | `/admin/adapters/{id}/config-versions` | `api_v1_admin_adapters_config_versions_list` | staff |
| n | POST | `/admin/adapters/{id}/config-versions` | `api_v1_admin_adapters_config_versions_create` | staff |
| n | GET | `/admin/adapters/{id}/events` | `api_v1_admin_adapters_events_list` | staff |
| n | GET | `/admin/adapters/{id}/usage` | `api_v1_admin_adapters_usage_retrieve` | staff |
| n | GET | `/admin/adapters/{id}/webhook` | `api_v1_admin_adapters_webhook_retrieve` | staff |
| n | PUT | `/admin/adapters/{id}/webhook` | `api_v1_admin_adapters_webhook_update` | staff |
| n | DELETE | `/admin/adapters/{id}/webhook` | `api_v1_admin_adapters_webhook_destroy` | staff |
| n | GET | `/admin/adapters/{id}/webhook/deliveries` | `api_v1_admin_adapters_webhook_deliveries_retrieve` | staff |
| n | POST | `/admin/adapters/{id}/webhook/rotate` | `api_v1_admin_adapters_webhook_rotate_create` | staff |
| c | GET | `/admin/analytics/{report_key}` | `api_v1_admin_analytics_retrieve` | staff |
| c | PATCH | `/admin/assets/{id}` | `api_v1_admin_assets_partial_update` | staff |
| c | POST | `/admin/assets/{id}/fix-status` | `api_v1_admin_assets_fix_status_create` | staff |
| c | POST | `/admin/assets/{id}/qr` | `api_v1_admin_assets_qr_create` | staff |
| c | GET | `/admin/assets/{id}/qr-history` | `api_v1_admin_assets_qr_history_retrieve` | staff |
| c | GET | `/admin/audit-logs` | `api_v1_admin_audit_logs_list` | staff |
| n | GET | `/admin/bookings/{id}/readiness/` | `api_v1_admin_bookings_readiness_retrieve` | staff |
| n | POST | `/admin/bulk/bookings/{decision}` | `api_v1_admin_bulk_bookings_create` | staff |
| n | POST | `/admin/bulk/event-registrations/{decision}` | `api_v1_admin_bulk_event_registrations_create` | staff |
| n | POST | `/admin/bulk/requests/{decision}` | `api_v1_admin_bulk_requests_create` | staff |
| c | DELETE | `/admin/card-designs/{id}` | `api_v1_admin_card_designs_destroy` | staff |
| n | POST | `/admin/card-designs/{id}/apply-template` | `api_v1_admin_card_designs_apply_template_create` | staff |
| n | POST | `/admin/card-designs/{id}/archive` | `api_v1_admin_card_designs_archive_create` | staff |
| n | GET | `/admin/card-designs/{id}/asset-library` | `api_v1_admin_card_designs_asset_library_list` | staff |
| n | DELETE | `/admin/card-designs/{id}/asset-library/{asset_id}` | `api_v1_admin_card_designs_asset_library_destroy` | staff |
| n | GET | `/admin/card-designs/{id}/badge-export` | `api_v1_admin_card_designs_badge_export_retrieve` | staff |
| n | POST | `/admin/card-designs/{id}/badge-import` | `api_v1_admin_card_designs_badge_import_create` | staff |
| n | POST | `/admin/card-designs/{id}/barcode` | `api_v1_admin_card_designs_barcode_create` | staff |
| n | GET | `/admin/card-designs/{id}/brand-kit` | `api_v1_admin_card_designs_brand_kit_retrieve` | staff |
| n | POST | `/admin/card-designs/{id}/convert-to-free-canvas` | `api_v1_admin_card_designs_convert_to_free_canvas_create` | staff |
| n | POST | `/admin/card-designs/{id}/csv-merge` | `api_v1_admin_card_designs_csv_merge_create` | staff |
| c | POST | `/admin/card-designs/{id}/reset` | `api_v1_admin_card_designs_reset_create` | staff |
| c | GET | `/admin/card-designs/{id}/templates` | `api_v1_admin_card_designs_templates_list` | staff |
| n | POST | `/admin/card-designs/{id}/unarchive` | `api_v1_admin_card_designs_unarchive_create` | staff |
| n | GET | `/admin/card-templates/{id}` | `api_v1_admin_card_templates_retrieve` | staff |
| n | PATCH | `/admin/card-templates/{id}` | `api_v1_admin_card_templates_partial_update` | staff |
| n | DELETE | `/admin/card-templates/{id}` | `api_v1_admin_card_templates_destroy` | staff |
| n | POST | `/admin/card-templates/{id}/duplicate` | `api_v1_admin_card_templates_duplicate_create` | staff |
| n | GET | `/admin/card-templates/{id}/export` | `api_v1_admin_card_templates_export_retrieve` | staff |
| n | GET | `/admin/card-verifications/{token}/staff` | `api_v1_admin_card_verifications_staff_retrieve` | staff |
| c | GET | `/admin/categories/{id}` | `api_v1_admin_categories_retrieve` | staff |
| c | PATCH | `/admin/categories/{id}` | `api_v1_admin_categories_partial_update` | staff |
| c | DELETE | `/admin/categories/{id}` | `api_v1_admin_categories_destroy` | staff |
| c | POST | `/admin/certification-grants/{id}/renew` | `api_v1_admin_certification_grants_renew_create` | staff |
| c | POST | `/admin/certification-grants/{id}/revoke` | `api_v1_admin_certification_grants_revoke_create` | staff |
| c | PATCH | `/admin/certification-types/{id}` | `api_v1_admin_certification_types_partial_update` | staff |
| c | DELETE | `/admin/certification-types/{id}` | `api_v1_admin_certification_types_destroy` | staff |
| c | GET | `/admin/certification-types/{id}/grants` | `api_v1_admin_certification_types_grants_retrieve` | staff |
| c | POST | `/admin/certification-types/{id}/grants` | `api_v1_admin_certification_types_grants_create` | staff |
| c | GET | `/admin/certification-types/{id}/members` | `api_v1_admin_certification_types_members_retrieve` | staff |
| c | GET | `/admin/containers/{id}/contents` | `api_v1_admin_containers_contents_retrieve` | staff |
| c | GET | `/admin/containers/{id}/history` | `api_v1_admin_containers_history_retrieve` | staff |
| c | PATCH | `/admin/event-id-cards/{id}` | `api_v1_admin_event_id_cards_partial_update` | staff |
| n | GET | `/admin/event-id-cards/{id}/photo-cutout` | `api_v1_admin_event_id_cards_photo_cutout_retrieve` | staff |
| n | POST | `/admin/event-id-cards/{id}/photo-cutout` | `api_v1_admin_event_id_cards_photo_cutout_create` | staff |
| n | PATCH | `/admin/event-id-cards/{id}/photo-cutout` | `api_v1_admin_event_id_cards_photo_cutout_partial_update` | staff |
| n | DELETE | `/admin/event-id-cards/{id}/photo-cutout` | `api_v1_admin_event_id_cards_photo_cutout_destroy` | staff |
| n | POST | `/admin/event-series-invites/{id}/revoke/` | `api_v1_admin_event_series_invites_revoke_create` | staff |
| n | GET | `/admin/event-series/{id}/invites/` | `api_v1_admin_event_series_invites_retrieve` | staff |
| n | POST | `/admin/event-series/{id}/invites/` | `api_v1_admin_event_series_invites_create` | staff |
| c | GET | `/admin/event-series/{id}/staff-grants/` | `api_v1_admin_event_series_staff_grants_retrieve` | staff |
| c | GET | `/admin/event-series/{id}/staff-invites/` | `api_v1_admin_event_series_staff_invites_retrieve` | staff |
| c | POST | `/admin/event-series/{id}/staff-invites/` | `api_v1_admin_event_series_staff_invites_create` | staff |
| c | PATCH | `/admin/event-staff-grants/{id}/` | `api_v1_admin_event_staff_grants_partial_update` | staff |
| c | POST | `/admin/event-staff-grants/{id}/revoke/` | `api_v1_admin_event_staff_grants_revoke_create` | staff |
| c | POST | `/admin/event-staff-invites/{id}/revoke/` | `api_v1_admin_event_staff_invites_revoke_create` | staff |
| c | PATCH | `/admin/events/{id}/` | `api_v1_admin_events_partial_update` | staff |
| n | DELETE | `/admin/events/{id}/` | `api_v1_admin_events_destroy` | staff |
| c | GET | `/admin/events/{id}/analytics/extras/` | `api_v1_admin_events_analytics_extras_retrieve` | staff |
| n | GET | `/admin/events/{id}/badge-designs` | `api_v1_admin_events_badge_designs_retrieve` | staff |
| n | POST | `/admin/events/{id}/badge-designs/{role}` | `api_v1_admin_events_badge_designs_create` | staff |
| n | GET | `/admin/events/{id}/badges/desk` | `api_v1_admin_events_badges_desk_retrieve` | staff |
| n | POST | `/admin/events/{id}/badges/print-receipts` | `api_v1_admin_events_badges_print_receipts_create` | staff |
| c | POST | `/admin/events/{id}/broadcasts/` | `api_v1_admin_events_broadcasts_create` | staff |
| n | DELETE | `/admin/events/{id}/broadcasts/{campaign_id}/` | `api_v1_admin_events_broadcasts_destroy` | staff |
| c | POST | `/admin/events/{id}/cancel/` | `api_v1_admin_events_cancel_create` | staff |
| c | GET | `/admin/events/{id}/card-designs` | `api_v1_admin_events_card_designs_retrieve` | staff |
| n | GET | `/admin/events/{id}/certificate-artwork/by-resource/{resource_id}/` | `api_v1_admin_events_certificate_artwork_by_resource_retrieve` | staff |
| n | POST | `/admin/events/{id}/checkin-lists/{list_id}/scan/{scan_id}/undo/` | `api_v1_admin_events_checkin_lists_scan_undo_create` | staff |
| n | POST | `/admin/events/{id}/checkin-lists/reorder/` | `api_v1_admin_events_checkin_lists_reorder_create` | staff |
| c | GET | `/admin/events/{id}/crew/` | `api_v1_admin_events_crew_list` | staff |
| n | PATCH | `/admin/events/{id}/crew/{crew_id}/` | `api_v1_admin_events_crew_partial_update` | staff |
| n | POST | `/admin/events/{id}/crew/reorder/` | `api_v1_admin_events_crew_reorder_create` | staff |
| n | GET | `/admin/events/{id}/guest-passes/` | `api_v1_admin_events_guest_passes_retrieve` | staff |
| n | GET | `/admin/events/{id}/hackathon/mlh-presets/` | `api_v1_admin_events_hackathon_mlh_presets_list` | staff |
| r | GET | `/admin/events/{id}/judge-assignments/` | `api_v1_admin_events_judge_assignments_list` | staff |
| r | GET | `/admin/events/{id}/judge-assignments/{assignment_id}/` | `api_v1_admin_events_judge_assignments_retrieve` | staff |
| c | POST | `/admin/events/{id}/judging-rounds/{round_id}/assign/` | `api_v1_admin_events_judging_rounds_assign_create` | staff |
| n | GET | `/admin/events/{id}/judging/scores-export/` | `api_v1_admin_events_judging_scores_export_retrieve` | staff |
| c | GET | `/admin/events/{id}/lists/{list_key}/` | `api_v1_admin_events_lists_retrieve` | staff |
| c | GET | `/admin/events/{id}/lists/{list_key}/export/` | `api_v1_admin_events_lists_export_retrieve` | staff |
| n | GET | `/admin/events/{id}/lists/{list_key}/presets/` | `api_v1_admin_events_lists_presets_retrieve` | staff |
| n | GET | `/admin/events/{id}/loans/` | `api_v1_admin_events_loans_retrieve` | staff |
| c | GET | `/admin/events/{id}/prize-claims/` | `api_v1_admin_events_prize_claims_retrieve` | staff |
| c | POST | `/admin/events/{id}/prize-shares/{share_id}/reveal/` | `api_v1_admin_events_prize_shares_reveal_create` | staff |
| c | GET | `/admin/events/{id}/registrations/` | `api_v1_admin_events_registrations_retrieve` | staff |
| n | POST | `/admin/events/{id}/reimbursements/staff-claims/` | `api_v1_admin_events_reimbursements_staff_claims_create` | staff |
| n | POST | `/admin/events/{id}/results/unpublish/` | `api_v1_admin_events_results_unpublish_create` | staff |
| c | GET | `/admin/events/{id}/staff-grants/` | `api_v1_admin_events_staff_grants_retrieve` | staff |
| c | GET | `/admin/events/{id}/staff-invites/` | `api_v1_admin_events_staff_invites_retrieve` | staff |
| c | POST | `/admin/events/{id}/staff-invites/` | `api_v1_admin_events_staff_invites_create` | staff |
| n | POST | `/admin/events/{id}/submissions/{submission_id}/reinstate/` | `api_v1_admin_events_submissions_reinstate_create` | staff |
| c | GET | `/admin/events/{id}/teams/{team_id}/` | `api_v1_admin_events_teams_retrieve_2` | staff |
| n | POST | `/admin/events/{id}/teams/{team_id}/delete/` | `api_v1_admin_events_teams_delete_create` | staff |
| n | POST | `/admin/events/{id}/teams/{team_id}/move-member/` | `api_v1_admin_events_teams_move_member_create` | staff |
| n | POST | `/admin/events/{id}/teams/{team_id}/rename/` | `api_v1_admin_events_teams_rename_create` | staff |
| n | POST | `/admin/events/{id}/teams/{team_id}/restore/` | `api_v1_admin_events_teams_restore_create` | staff |
| n | GET | `/admin/events/insights/` | `api_v1_admin_events_insights_retrieve` | staff |
| c | GET | `/admin/evidence/{id}` | `api_v1_admin_evidence_retrieve` | staff |
| n | POST | `/admin/guest-certification-grants/{id}/revoke` | `api_v1_admin_guest_certification_grants_revoke_create` | staff |
| c | DELETE | `/admin/id-programme-cards/{id}` | `api_v1_admin_id_programme_cards_destroy` | staff |
| c | DELETE | `/admin/id-programmes/{id}` | `api_v1_admin_id_programmes_destroy` | staff |
| n | POST | `/admin/id-programmes/{id}/archive` | `api_v1_admin_id_programmes_archive_create` | staff |
| n | POST | `/admin/id-programmes/{id}/unarchive` | `api_v1_admin_id_programmes_unarchive_create` | staff |
| n | PATCH | `/admin/incident-actions/{id}` | `api_v1_admin_incident_actions_partial_update` | staff |
| n | GET | `/admin/incidents/{id}` | `api_v1_admin_incidents_retrieve` | staff |
| n | PATCH | `/admin/incidents/{id}` | `api_v1_admin_incidents_partial_update` | staff |
| n | POST | `/admin/incidents/{id}/actions` | `api_v1_admin_incidents_actions_create` | staff |
| n | GET | `/admin/incidents/{id}/assignees` | `api_v1_admin_incidents_assignees_retrieve` | staff |
| n | DELETE | `/admin/induction-links/{id}` | `api_v1_admin_induction_links_destroy` | staff |
| c | POST | `/admin/inventory/{id}/adjust-quantity` | `api_v1_admin_inventory_adjust_quantity_create` | staff |
| c | DELETE | `/admin/inventory/{id}/image` | `api_v1_admin_inventory_image_destroy` | staff |
| c | GET | `/admin/inventory/{id}/lending-history` | `api_v1_admin_inventory_lending_history_retrieve` | staff |
| c | POST | `/admin/inventory/{id}/needs-fix` | `api_v1_admin_inventory_needs_fix_create` | staff |
| c | GET | `/admin/inventory/{id}/qr-history` | `api_v1_admin_inventory_qr_history_retrieve` | staff |
| c | GET | `/admin/inventory/{product_pk}/assets` | `api_v1_admin_inventory_assets_list` | staff |
| c | GET | `/admin/inventory/needs-fix` | `api_v1_admin_inventory_needs_fix_list` | staff |
| c | GET | `/admin/ledger` | `api_v1_admin_ledger_retrieve` | staff |
| c | GET | `/admin/ledger/export` | `api_v1_admin_ledger_export_retrieve` | staff |
| n | POST | `/admin/machine-access/{id}/revoke` | `api_v1_admin_machine_access_revoke_create` | staff |
| c | GET | `/admin/machine-service/consumable-pools/{id}` | `api_v1_admin_machine_service_consumable_pools_retrieve` | staff |
| c | PATCH | `/admin/machine-service/consumable-pools/{id}` | `api_v1_admin_machine_service_consumable_pools_partial_update` | staff |
| c | POST | `/admin/machine-service/consumable-pools/{id}/adjustments` | `api_v1_admin_machine_service_consumable_pools_adjustments_create` | staff |
| c | GET | `/admin/machines/{id}` | `api_v1_admin_machines_retrieve` | staff |
| c | GET | `/admin/machines/{id}/documents` | `api_v1_admin_machines_documents_list` | staff |
| c | GET | `/admin/machines/{id}/error-logs` | `api_v1_admin_machines_error_logs_list` | staff |
| n | PATCH | `/admin/machines/{id}/open-access` | `api_v1_admin_machines_open_access_partial_update` | staff |
| c | GET | `/admin/machines/{id}/operators` | `api_v1_admin_machines_operators_list` | staff |
| c | DELETE | `/admin/machines/{id}/operators/{user_pk}` | `api_v1_admin_machines_operators_destroy` | staff |
| c | GET | `/admin/machines/{id}/publicity` | `api_v1_admin_machines_publicity_retrieve` | staff |
| c | POST | `/admin/machines/{id}/retire` | `api_v1_admin_machines_retire_create` | staff |
| c | POST | `/admin/machines/{id}/unretire` | `api_v1_admin_machines_unretire_create` | staff |
| c | GET | `/admin/machines/{id}/usage` | `api_v1_admin_machines_usage_list` | staff |
| c | DELETE | `/admin/machines/documents/{id}` | `api_v1_admin_machines_documents_destroy` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/adapter-credentials` | `api_v1_admin_makerspace_adapter_credentials_list` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/adapter-credentials` | `api_v1_admin_makerspace_adapter_credentials_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/adapters` | `api_v1_admin_makerspace_adapters_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/allowances` | `api_v1_admin_makerspace_allowances_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/{report_key}` | `api_v1_admin_makerspace_analytics_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/active-loans` | `api_v1_admin_makerspace_analytics_active_loans_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/booking-utilization` | `api_v1_admin_makerspace_analytics_booking_utilization_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/damaged-lost` | `api_v1_admin_makerspace_analytics_damaged_lost_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/damaged-missing` | `api_v1_admin_makerspace_analytics_damaged_missing_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/event-attendance` | `api_v1_admin_makerspace_analytics_event_attendance_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/fablab-health` | `api_v1_admin_makerspace_analytics_fablab_health_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/machine-usage` | `api_v1_admin_makerspace_analytics_machine_usage_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/maintenance-activity` | `api_v1_admin_makerspace_analytics_maintenance_activity_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/member-activity` | `api_v1_admin_makerspace_analytics_member_activity_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/most-lent` | `api_v1_admin_makerspace_analytics_most_lent_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/payment-reconciliation` | `api_v1_admin_makerspace_analytics_payment_reconciliation_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/qr-scans` | `api_v1_admin_makerspace_analytics_qr_scans_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/recently-added` | `api_v1_admin_makerspace_analytics_recently_added_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/returns` | `api_v1_admin_makerspace_analytics_returns_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/summary` | `api_v1_admin_makerspace_analytics_summary_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/taken-items` | `api_v1_admin_makerspace_analytics_taken_items_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/analytics/top-borrowers` | `api_v1_admin_makerspace_analytics_top_borrowers_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/anthias-players` | `api_v1_admin_makerspace_anthias_players_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/anthias-players` | `api_v1_admin_makerspace_anthias_players_create` | staff |
| n | PATCH | `/admin/makerspace/{makerspace_id}/anthias-players/{id}` | `api_v1_admin_makerspace_anthias_players_partial_update` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/anthias-players/{id}` | `api_v1_admin_makerspace_anthias_players_destroy` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/anthias-players/{id}/sync` | `api_v1_admin_makerspace_anthias_players_sync_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/anthias-players/{id}/test` | `api_v1_admin_makerspace_anthias_players_test_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/area-overview/{section}` | `api_v1_admin_makerspace_area_overview_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/billing/cash-handovers` | `api_v1_admin_makerspace_billing_cash_handovers_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/billing/collection-sheet` | `api_v1_admin_makerspace_billing_collection_sheet_create` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/categories` | `api_v1_admin_makerspace_categories_list` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/categories` | `api_v1_admin_makerspace_categories_create` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/certification-types` | `api_v1_admin_makerspace_certification_types_retrieve` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/certification-types` | `api_v1_admin_makerspace_certification_types_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/consumables/{id}/equipment-sources` | `api_v1_admin_makerspace_consumables_equipment_sources_retrieve` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/consumables/{id}/use` | `api_v1_admin_makerspace_consumables_use_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/consumables/planned-shortages` | `api_v1_admin_makerspace_consumables_planned_shortages_list` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/dashboard/attention` | `api_v1_admin_makerspace_dashboard_attention_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/direct-loan-members` | `api_v1_admin_makerspace_direct_loan_members_list` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/direct-loans` | `api_v1_admin_makerspace_direct_loans_list` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/booking-context` | `api_v1_admin_makerspace_direct_loans_booking_context_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/booking-context` | `api_v1_admin_makerspace_direct_loans_booking_context_update` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/booking-context` | `api_v1_admin_makerspace_direct_loans_booking_context_destroy` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/event-context` | `api_v1_admin_makerspace_direct_loans_event_context_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/event-context` | `api_v1_admin_makerspace_direct_loans_event_context_update` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/direct-loans/{loan_id}/event-context` | `api_v1_admin_makerspace_direct_loans_event_context_destroy` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/donations/{id}/claim/confirm` | `api_v1_admin_makerspace_donations_claim_confirm_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/donations/{id}/claim/reject` | `api_v1_admin_makerspace_donations_claim_reject_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/donations/{id}/receipt/reissue` | `api_v1_admin_makerspace_donations_receipt_reissue_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/donations/donors` | `api_v1_admin_makerspace_donations_donors_list` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/donations/export.csv` | `api_v1_admin_makerspace_donations_export.csv_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/donations/settings` | `api_v1_admin_makerspace_donations_settings_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/email/test` | `api_v1_admin_makerspace_email_test_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/equipment-kits` | `api_v1_admin_makerspace_equipment_kits_list` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/equipment-kits` | `api_v1_admin_makerspace_equipment_kits_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}` | `api_v1_admin_makerspace_equipment_kit_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}/archive` | `api_v1_admin_makerspace_equipment_kits_archive_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}/publication` | `api_v1_admin_makerspace_equipment_kits_publication_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/equipment-kits/{kit_id}/versions` | `api_v1_admin_makerspace_equipment_kits_versions_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/equipment-requests/contextual` | `api_v1_admin_makerspace_equipment_requests_contextual_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/event-registration-queue` | `api_v1_admin_makerspace_event_registration_queue_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/event-room-choices` | `api_v1_admin_makerspace_event_room_choices_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link` | `api_v1_admin_makerspace_events_booking_link_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link` | `api_v1_admin_makerspace_events_booking_link_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/booking-link/replacement` | `api_v1_admin_makerspace_events_booking_link_replacement_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-availability` | `api_v1_admin_makerspace_events_equipment_availability_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-desk` | `api_v1_admin_makerspace_events_equipment_desk_retrieve` | staff |
| n | PATCH | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-desk` | `api_v1_admin_makerspace_events_equipment_desk_partial_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-kits` | `api_v1_admin_makerspace_events_equipment_kits_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-plan` | `api_v1_admin_makerspace_events_equipment_plan_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/equipment-request-products` | `api_v1_admin_makerspace_events_equipment_request_products_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/machine-use` | `api_v1_admin_makerspace_events_machine_use_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/machine-use/{link_id}/cost` | `api_v1_admin_makerspace_events_machine_use_cost_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/venue` | `api_v1_admin_makerspace_events_venue_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines` | `api_v1_admin_makerspace_events_workshop_machines_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines` | `api_v1_admin_makerspace_events_workshop_machines_create` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines/{link_id}` | `api_v1_admin_makerspace_events_workshop_machines_destroy` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/{event_id}/workshop-machines/{link_id}/replacement` | `api_v1_admin_makerspace_events_workshop_machines_replacement_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/events/with-room` | `api_v1_admin_makerspace_events_with_room_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/finance/events/{event_id}/linked` | `finance_event_linked_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/inventory` | `api_v1_admin_makerspace_inventory_list` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/inventory/import/jobs` | `api_v1_admin_makerspace_inventory_import_jobs_create` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/inventory/import/jobs/{job_id}` | `api_v1_admin_makerspace_inventory_import_jobs_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/ledger` | `api_v1_admin_makerspace_ledger_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/ledger/export` | `api_v1_admin_makerspace_ledger_export_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/legal-pages/{slug}` | `api_v1_admin_makerspace_legal_pages_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/legal-pages/{slug}` | `api_v1_admin_makerspace_legal_pages_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/limits` | `api_v1_admin_makerspace_limits_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/machine-types` | `api_v1_admin_makerspace_machine_types_list` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/machine-types/{machine_type_id}/adapter-profile` | `api_v1_admin_makerspace_machine_types_adapter_profile_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/machine-types/{machine_type_id}/adapter-profile` | `api_v1_admin_makerspace_machine_types_adapter_profile_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/machine-use/{kind}/{id}/event` | `api_v1_admin_makerspace_machine_use_event_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/machine-use/{kind}/{id}/event` | `api_v1_admin_makerspace_machine_use_event_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/machine-use/events` | `api_v1_admin_makerspace_machine_use_events_list` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/machines` | `api_v1_admin_makerspace_machines_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/members/{user_id}/included-hours` | `api_v1_admin_makerspace_members_included_hours_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/notification-destinations/{destination_id}/rotate-secret` | `api_v1_admin_makerspace_notification_destinations_rotate_secret_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/organizations/{organization_id}/hours-bank/` | `api_v1_admin_makerspace_organizations_hours_bank_retrieve` | staff |
| n | PATCH | `/admin/makerspace/{makerspace_id}/organizations/{organization_id}/hours-bank/` | `api_v1_admin_makerspace_organizations_hours_bank_partial_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/organizations/{organization_id}/hours-bank/ledger/` | `api_v1_admin_makerspace_organizations_hours_bank_ledger_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/organizations/{organization_id}/hours-bank/ledger/` | `api_v1_admin_makerspace_organizations_hours_bank_ledger_create` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/payments` | `api_v1_admin_makerspace_payments_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/payments/{payment_id}/area-pay-link` | `api_v1_admin_makerspace_payments_area_pay_link_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/payments/{payment_id}/area-reminder` | `api_v1_admin_makerspace_payments_area_reminder_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/payments/area-queue` | `api_v1_admin_makerspace_payments_area_queue_list` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/payments/area-queue/claims` | `api_v1_admin_makerspace_payments_area_queue_claims_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/payments/area-queue/claims/{claim_id}/confirm` | `api_v1_admin_makerspace_payments_area_queue_claims_confirm_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/payments/area-queue/claims/{claim_id}/reject` | `api_v1_admin_makerspace_payments_area_queue_claims_reject_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/payments/area-queue/summary` | `api_v1_admin_makerspace_payments_area_queue_summary_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/presence-displays` | `api_v1_admin_makerspace_presence_displays_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/presence-displays` | `api_v1_admin_makerspace_presence_displays_create` | staff |
| n | PATCH | `/admin/makerspace/{makerspace_id}/presence-displays/{id}` | `api_v1_admin_makerspace_presence_displays_partial_update` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/presence-displays/{id}` | `api_v1_admin_makerspace_presence_displays_destroy` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/presence-displays/{id}/link` | `api_v1_admin_makerspace_presence_displays_link_create_2` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/presence-displays/{id}/players` | `api_v1_admin_makerspace_presence_displays_players_update` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/presence-displays/link` | `api_v1_admin_makerspace_presence_displays_link_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/presence-now-config` | `api_v1_admin_makerspace_presence_now_config_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/presence-now-config` | `api_v1_admin_makerspace_presence_now_config_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/presence-sessions/{account_id}/related` | `api_v1_admin_makerspace_presence_sessions_related_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/presence-sessions/check-in-guests` | `api_v1_admin_makerspace_presence_sessions_check_in_guests_retrieve` | staff |
| c | PUT | `/admin/makerspace/{makerspace_id}/pricing/{domain}` | `api_v1_admin_makerspace_pricing_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/problem-reports` | `api_v1_admin_makerspace_problem_reports_retrieve` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/problem-reports/{id}/triage` | `api_v1_admin_makerspace_problem_reports_triage_create` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/qr-print-batches` | `api_v1_admin_makerspace_qr_print_batches_list` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/qr-print-batches` | `api_v1_admin_makerspace_qr_print_batches_create` | staff |
| c | POST | `/admin/makerspace/{makerspace_id}/refund-cases/{case_id}/approve` | `api_v1_admin_makerspace_refund_cases_approve_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/related-facts/bookings/{booking_id}` | `api_v1_admin_makerspace_related_facts_bookings_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/related-facts/events/{event_id}` | `api_v1_admin_makerspace_related_facts_events_retrieve` | staff |
| c | GET | `/admin/makerspace/{makerspace_id}/reports/{report_key}/export` | `api_v1_admin_makerspace_reports_export_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/requests/{request_id}/booking-context` | `api_v1_admin_makerspace_requests_booking_context_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/requests/{request_id}/booking-context` | `api_v1_admin_makerspace_requests_booking_context_update` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/requests/{request_id}/booking-context` | `api_v1_admin_makerspace_requests_booking_context_destroy` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/requests/{request_id}/event-context` | `api_v1_admin_makerspace_requests_event_context_retrieve` | staff |
| n | PUT | `/admin/makerspace/{makerspace_id}/requests/{request_id}/event-context` | `api_v1_admin_makerspace_requests_event_context_update` | staff |
| n | DELETE | `/admin/makerspace/{makerspace_id}/requests/{request_id}/event-context` | `api_v1_admin_makerspace_requests_event_context_destroy` | staff |
| c | PATCH | `/admin/makerspace/{makerspace_id}/return-policy` | `api_v1_admin_makerspace_return_policy_partial_update` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/schedule` | `api_v1_admin_makerspace_schedule_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/shelf-checks` | `api_v1_admin_makerspace_shelf_checks_retrieve` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/shelf-checks` | `api_v1_admin_makerspace_shelf_checks_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/shelf-pointer/clear` | `api_v1_admin_makerspace_shelf_pointer_clear_create` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/shelf-pointer/coverage` | `api_v1_admin_makerspace_shelf_pointer_coverage_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/shelf-pointer/locations` | `api_v1_admin_makerspace_shelf_pointer_locations_list` | staff |
| n | POST | `/admin/makerspace/{makerspace_id}/shelf-pointer/show` | `api_v1_admin_makerspace_shelf_pointer_show_create` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/spaces/{space_id}/equipment-kits` | `api_v1_admin_makerspace_spaces_equipment_kits_retrieve` | staff |
| n | GET | `/admin/makerspace/{makerspace_id}/spaces/{space_id}/equipment-request-products` | `api_v1_admin_makerspace_spaces_equipment_request_products_retrieve` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/card-designs` | `api_v1_admin_makerspaces_card_designs_list` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/card-designs/titles` | `api_v1_admin_makerspaces_card_designs_titles_list` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/card-number-schemes` | `api_v1_admin_makerspaces_card_number_schemes_retrieve` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/card-number-schemes` | `api_v1_admin_makerspaces_card_number_schemes_update` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/card-number-schemes/titles/{title_id}` | `api_v1_admin_makerspaces_card_number_schemes_titles_update` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/card-photo-batches` | `api_v1_admin_makerspaces_card_photo_batches_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/card-photo-batches/{batch_id}` | `api_v1_admin_makerspaces_card_photo_batches_retrieve` | staff |
| n | DELETE | `/admin/makerspaces/{makerspace_id}/card-photo-batches/{batch_id}` | `api_v1_admin_makerspaces_card_photo_batches_destroy` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/card-photo-batches/{batch_id}/apply` | `api_v1_admin_makerspaces_card_photo_batches_apply_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/card-photo-batches/{batch_id}/files` | `api_v1_admin_makerspaces_card_photo_batches_files_create` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/card-photo-batches/{batch_id}/items/{item_id}` | `api_v1_admin_makerspaces_card_photo_batches_items_partial_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/card-templates` | `api_v1_admin_makerspaces_card_templates_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/card-templates` | `api_v1_admin_makerspaces_card_templates_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/card-templates/builtin/{key}/{theme}` | `api_v1_admin_makerspaces_card_templates_builtin_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/card-templates/import` | `api_v1_admin_makerspaces_card_templates_import_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/community-policy` | `api_v1_admin_makerspaces_community_policy_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/community-policy` | `api_v1_admin_makerspaces_community_policy_partial_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/day-pass-products` | `api_v1_admin_makerspaces_day_pass_products_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/day-pass-products` | `api_v1_admin_makerspaces_day_pass_products_create` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/day-pass-products/{product_id}` | `api_v1_admin_makerspaces_day_pass_products_partial_update` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/day-pass-products/{product_id}/archive` | `api_v1_admin_makerspaces_day_pass_products_archive_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/events/{event_id}/induction` | `api_v1_admin_makerspaces_events_induction_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/events/{event_id}/induction` | `api_v1_admin_makerspaces_events_induction_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/events/{event_id}/induction/grant` | `api_v1_admin_makerspaces_events_induction_grant_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/grafana` | `api_v1_admin_makerspaces_grafana_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/grafana/bundle` | `api_v1_admin_makerspaces_grafana_bundle_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/grafana/connection` | `api_v1_admin_makerspaces_grafana_connection_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/grafana/connection` | `api_v1_admin_makerspaces_grafana_connection_partial_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/grafana/dashboards/{uid}/embed` | `api_v1_admin_makerspaces_grafana_dashboards_embed_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/grafana/dashboards/{uid}/render` | `api_v1_admin_makerspaces_grafana_dashboards_render_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/grafana/test` | `api_v1_admin_makerspaces_grafana_test_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/grafana/token` | `api_v1_admin_makerspaces_grafana_token_create` | staff |
| n | DELETE | `/admin/makerspaces/{makerspace_id}/grafana/token` | `api_v1_admin_makerspaces_grafana_token_destroy` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guardian-consents/{consent_id}/revoke` | `api_v1_admin_makerspaces_guardian_consents_revoke_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/guardian-terms` | `api_v1_admin_makerspaces_guardian_terms_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guardian-terms` | `api_v1_admin_makerspaces_guardian_terms_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/guest-pass-policy` | `api_v1_admin_makerspaces_guest_pass_policy_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/guest-pass-policy` | `api_v1_admin_makerspaces_guest_pass_policy_partial_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/guest-passes` | `api_v1_admin_makerspaces_guest_passes_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guest-passes` | `api_v1_admin_makerspaces_guest_passes_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guest-passes/{pass_id}/revoke` | `api_v1_admin_makerspaces_guest_passes_revoke_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guest-passes/{pass_id}/waiver` | `api_v1_admin_makerspaces_guest_passes_waiver_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guest-passes/scan` | `api_v1_admin_makerspaces_guest_passes_scan_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/guest-passes/sell` | `api_v1_admin_makerspaces_guest_passes_sell_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/image-adapter` | `api_v1_admin_makerspaces_image_adapter_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/image-adapter` | `api_v1_admin_makerspaces_image_adapter_partial_update` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/image-adapter/test` | `api_v1_admin_makerspaces_image_adapter_test_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/incidents` | `api_v1_admin_makerspaces_incidents_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/incidents` | `api_v1_admin_makerspaces_incidents_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/induction-events` | `api_v1_admin_makerspaces_induction_events_list` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/issues` | `api_v1_admin_makerspaces_issues_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/join-requests/{id}/request-changes` | `api_v1_admin_makerspaces_join_requests_request_changes_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-access` | `api_v1_admin_makerspaces_machine_access_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-access` | `api_v1_admin_makerspaces_machine_access_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-access/candidates` | `api_v1_admin_makerspaces_machine_access_candidates_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-bookings` | `api_v1_admin_makerspaces_machine_bookings_list` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-jobs/{id}/consumables` | `api_v1_admin_makerspaces_machine_jobs_consumables_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-jobs/{id}/consumables` | `api_v1_admin_makerspaces_machine_jobs_consumables_create` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/machine-service/consumable-pools` | `api_v1_admin_makerspaces_machine_service_consumable_pools_list` | staff |
| c | POST | `/admin/makerspaces/{makerspace_id}/machine-service/consumable-pools` | `api_v1_admin_makerspaces_machine_service_consumable_pools_create` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/machine-service/typed-manual-usage` | `api_v1_admin_makerspaces_machine_service_typed_manual_usage_list` | staff |
| c | POST | `/admin/makerspaces/{makerspace_id}/machine-service/typed-manual-usage` | `api_v1_admin_makerspaces_machine_service_typed_manual_usage_create` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/machine-sessions` | `api_v1_admin_makerspaces_machine_sessions_list` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-type-templates` | `api_v1_admin_makerspaces_machine_type_templates_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-type-templates` | `api_v1_admin_makerspaces_machine_type_templates_create` | staff |
| n | DELETE | `/admin/makerspaces/{makerspace_id}/machine-type-templates/{key}` | `api_v1_admin_makerspaces_machine_type_templates_destroy` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-type-templates/{key}/apply` | `api_v1_admin_makerspaces_machine_type_templates_apply_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/consumable-stock` | `api_v1_admin_makerspaces_machine_types_consumable_stock_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/consumables` | `api_v1_admin_makerspaces_machine_types_consumables_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/consumables` | `api_v1_admin_makerspaces_machine_types_consumables_create` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/consumables/{id}` | `api_v1_admin_makerspaces_machine_types_consumables_partial_update` | staff |
| n | DELETE | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/consumables/{id}` | `api_v1_admin_makerspaces_machine_types_consumables_destroy` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/documents` | `api_v1_admin_makerspaces_machine_types_documents_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/documents` | `api_v1_admin_makerspaces_machine_types_documents_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/documents/{id}` | `api_v1_admin_makerspaces_machine_types_documents_retrieve` | staff |
| n | DELETE | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/documents/{id}` | `api_v1_admin_makerspaces_machine_types_documents_destroy` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/documents/presign` | `api_v1_admin_makerspaces_machine_types_documents_presign_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/setup` | `api_v1_admin_makerspaces_machine_types_setup_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/setup` | `api_v1_admin_makerspaces_machine_types_setup_partial_update` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/machine-types/{type_id}/setup/apply-booking-defaults` | `api_v1_admin_makerspaces_machine_types_setup_apply_booking_defaults_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/member-import-reviews` | `api_v1_admin_makerspaces_member_import_reviews_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-import-reviews/{imported_id}/approve` | `api_v1_admin_makerspaces_member_import_reviews_approve_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-import-reviews/{imported_id}/reject` | `api_v1_admin_makerspaces_member_import_reviews_reject_create` | staff |
| r | GET | `/admin/makerspaces/{makerspace_id}/member-register` | `api_v1_admin_makerspaces_member_register_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-register/bulk` | `api_v1_admin_makerspaces_member_register_bulk_create` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/member-unit-levels` | `api_v1_admin_makerspaces_member_unit_levels_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/member-units` | `api_v1_admin_makerspaces_member_units_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-units` | `api_v1_admin_makerspaces_member_units_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/member-units/{id}` | `api_v1_admin_makerspaces_member_units_retrieve_2` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/member-units/{id}` | `api_v1_admin_makerspaces_member_units_partial_update` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-units/{id}/archive` | `api_v1_admin_makerspaces_member_units_archive_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-units/{id}/move` | `api_v1_admin_makerspaces_member_units_move_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/member-units/{id}/restore` | `api_v1_admin_makerspaces_member_units_restore_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/members/{user_id}/activity` | `api_v1_admin_makerspaces_members_activity_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/membership-plans/{plan_id}/units` | `api_v1_admin_makerspaces_membership_plans_units_retrieve` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/membership-plans/{plan_id}/units` | `api_v1_admin_makerspaces_membership_plans_units_update` | staff |
| c | PUT | `/admin/makerspaces/{makerspace_id}/memberships/{membership_id}/machine-scope` | `api_v1_admin_makerspaces_memberships_machine_scope_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/memberships/{membership_id}/unit` | `api_v1_admin_makerspaces_memberships_unit_retrieve` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/memberships/{membership_id}/unit` | `api_v1_admin_makerspaces_memberships_unit_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/minors` | `api_v1_admin_makerspaces_minors_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/minors` | `api_v1_admin_makerspaces_minors_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/minors/{profile_id}/clear` | `api_v1_admin_makerspaces_minors_clear_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/minors/{profile_id}/consents` | `api_v1_admin_makerspaces_minors_consents_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/minors/{profile_id}/consents` | `api_v1_admin_makerspaces_minors_consents_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/refund-cases/bulk/{decision}` | `api_v1_admin_makerspaces_refund_cases_bulk_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/requests/{request_id}/repairs` | `api_v1_admin_makerspaces_requests_repairs_retrieve` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/requests/{request_id}/repairs` | `api_v1_admin_makerspaces_requests_repairs_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/room-outages/impact` | `api_v1_admin_makerspaces_room_outages_impact_retrieve` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/saved-views` | `api_v1_admin_makerspaces_saved_views_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/service-state` | `api_v1_admin_makerspaces_service_state_list` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/shop/event-offers/` | `api_v1_admin_makerspaces_shop_event_offers_list` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/shop/event-offers/{event_id}/` | `api_v1_admin_makerspaces_shop_event_offers_update` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/shop/orders/` | `api_v1_admin_makerspaces_shop_orders_list` | staff |
| c | GET | `/admin/makerspaces/{makerspace_id}/shop/products/` | `api_v1_admin_makerspaces_shop_products_list` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/staff-card-design` | `api_v1_admin_makerspaces_staff_card_design_retrieve` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/staff-card-jobs` | `api_v1_admin_makerspaces_staff_card_jobs_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/staff-card-jobs` | `api_v1_admin_makerspaces_staff_card_jobs_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/staff-card-jobs/preview` | `api_v1_admin_makerspaces_staff_card_jobs_preview_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/staff-cards` | `api_v1_admin_makerspaces_staff_cards_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/staff-cards` | `api_v1_admin_makerspaces_staff_cards_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/staff-cards/bulk-issue` | `api_v1_admin_makerspaces_staff_cards_bulk_issue_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/staff-cards/settings` | `api_v1_admin_makerspaces_staff_cards_settings_retrieve` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/staff-cards/settings` | `api_v1_admin_makerspaces_staff_cards_settings_update` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/staff-roles/bulk-invite/` | `api_v1_admin_makerspaces_staff_roles_bulk_invite_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/staff/{membership_id}/unit-scope` | `api_v1_admin_makerspaces_staff_unit_scope_retrieve` | staff |
| n | PUT | `/admin/makerspaces/{makerspace_id}/staff/{membership_id}/unit-scope` | `api_v1_admin_makerspaces_staff_unit_scope_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/telemetry` | `api_v1_admin_makerspaces_telemetry_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/telemetry` | `api_v1_admin_makerspaces_telemetry_partial_update` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/volunteer-credits` | `api_v1_admin_makerspaces_volunteer_credits_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/volunteer-credits/{credit_id}/void` | `api_v1_admin_makerspaces_volunteer_credits_void_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/volunteer-hours` | `api_v1_admin_makerspaces_volunteer_hours_list` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/volunteer-hours` | `api_v1_admin_makerspaces_volunteer_hours_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/volunteer-hours/{entry_id}/decide` | `api_v1_admin_makerspaces_volunteer_hours_decide_create` | staff |
| n | POST | `/admin/makerspaces/{makerspace_id}/volunteer-hours/import-event-shifts` | `api_v1_admin_makerspaces_volunteer_hours_import_event_shifts_create` | staff |
| n | GET | `/admin/makerspaces/{makerspace_id}/wallet-credentials` | `api_v1_admin_makerspaces_wallet_credentials_retrieve` | staff |
| n | PATCH | `/admin/makerspaces/{makerspace_id}/wallet-credentials` | `api_v1_admin_makerspaces_wallet_credentials_partial_update` | staff |
| c | GET | `/admin/member-cards/{id}/download` | `api_v1_admin_member_cards_download_retrieve` | staff |
| n | GET | `/admin/member-cards/{id}/photo-cutout` | `api_v1_admin_member_cards_photo_cutout_retrieve` | staff |
| n | POST | `/admin/member-cards/{id}/photo-cutout` | `api_v1_admin_member_cards_photo_cutout_create` | staff |
| n | PATCH | `/admin/member-cards/{id}/photo-cutout` | `api_v1_admin_member_cards_photo_cutout_partial_update` | staff |
| n | DELETE | `/admin/member-cards/{id}/photo-cutout` | `api_v1_admin_member_cards_photo_cutout_destroy` | staff |
| n | GET | `/admin/member-cards/{id}/print-face` | `api_v1_admin_member_cards_print_face_retrieve` | staff |
| c | GET | `/admin/memberships` | `api_v1_admin_memberships_retrieve` | staff |
| n | GET | `/admin/organization-reviews/` | `api_v1_admin_organization_reviews_retrieve` | staff |
| c | GET | `/admin/organizations/{organization_id}/analytics/{report_key}` | `api_v1_admin_organizations_analytics_retrieve` | staff |
| n | GET | `/admin/organizations/{organization_id}/card-designs/member-cards` | `api_v1_admin_organizations_card_designs_member_cards_retrieve` | staff |
| n | POST | `/admin/organizations/{organization_id}/card-designs/member-cards` | `api_v1_admin_organizations_card_designs_member_cards_create` | staff |
| c | GET | `/admin/organizations/{organization_id}/id-programmes` | `api_v1_admin_organizations_id_programmes_list` | staff |
| n | GET | `/admin/organizations/{id}/events/insights/` | `api_v1_admin_organizations_events_insights_retrieve` | staff |
| n | GET | `/admin/organizations/{id}/hours-bank/` | `api_v1_admin_organizations_hours_bank_retrieve` | staff |
| n | GET | `/admin/organizations/{id}/hours-bank/{makerspace_id}/ledger/` | `api_v1_admin_organizations_hours_bank_ledger_retrieve` | staff |
| n | GET | `/admin/organizations/{id}/member-rollup/` | `api_v1_admin_organizations_member_rollup_retrieve` | staff |
| n | POST | `/admin/organizations/{id}/resubmit/` | `api_v1_admin_organizations_resubmit_create` | staff |
| n | GET | `/admin/organizations/{id}/review/` | `api_v1_admin_organizations_review_list` | staff |
| n | POST | `/admin/organizations/{id}/review/` | `api_v1_admin_organizations_review_create` | staff |
| n | GET | `/admin/organized-events/attendance/` | `api_v1_admin_organized_events_attendance_retrieve` | staff |
| n | GET | `/admin/platform/admins` | `api_v1_admin_platform_admins_retrieve` | superadmin |
| c | GET | `/admin/platform/analytics/makerspaces/{makerspace_id}/analytics/{report_key}` | `api_v1_admin_platform_analytics_makerspaces_analytics_retrieve` | superadmin |
| c | GET | `/admin/platform/analytics/makerspaces/{makerspace_id}/reports/{report_key}/export` | `api_v1_admin_platform_analytics_makerspaces_reports_export_retrieve` | superadmin |
| c | POST | `/admin/platform/backup-destinations` | `api_v1_admin_platform_backup_destinations_create` | superadmin |
| c | PATCH | `/admin/platform/backup-destinations/{destination_id}` | `api_v1_admin_platform_backup_destinations_partial_update` | superadmin |
| c | POST | `/admin/platform/backup-destinations/{destination_id}/retire` | `api_v1_admin_platform_backup_destinations_retire_create` | superadmin |
| c | POST | `/admin/platform/backup-destinations/{destination_id}/test` | `api_v1_admin_platform_backup_destinations_test_create` | superadmin |
| c | POST | `/admin/platform/backup-destinations/push` | `api_v1_admin_platform_backup_destinations_push_create` | superadmin |
| c | POST | `/admin/platform/backups/{archive_id}/rehydrate` | `api_v1_admin_platform_backups_rehydrate_create` | superadmin |
| n | GET | `/admin/platform/firebase-web-settings` | `api_v1_admin_platform_firebase_web_settings_retrieve` | superadmin |
| n | PATCH | `/admin/platform/firebase-web-settings` | `api_v1_admin_platform_firebase_web_settings_partial_update` | superadmin |
| n | GET | `/admin/platform/grafana` | `api_v1_admin_platform_grafana_retrieve` | superadmin |
| n | GET | `/admin/platform/grafana/bundle` | `api_v1_admin_platform_grafana_bundle_retrieve` | superadmin |
| n | GET | `/admin/platform/grafana/connection` | `api_v1_admin_platform_grafana_connection_retrieve` | superadmin |
| n | PATCH | `/admin/platform/grafana/connection` | `api_v1_admin_platform_grafana_connection_partial_update` | superadmin |
| n | GET | `/admin/platform/grafana/dashboards/{uid}/embed` | `api_v1_admin_platform_grafana_dashboards_embed_retrieve` | superadmin |
| n | GET | `/admin/platform/grafana/dashboards/{uid}/render` | `api_v1_admin_platform_grafana_dashboards_render_retrieve` | superadmin |
| n | POST | `/admin/platform/grafana/test` | `api_v1_admin_platform_grafana_test_create` | superadmin |
| n | POST | `/admin/platform/grafana/token` | `api_v1_admin_platform_grafana_token_create` | superadmin |
| n | DELETE | `/admin/platform/grafana/token` | `api_v1_admin_platform_grafana_token_destroy` | superadmin |
| c | GET | `/admin/platform/hosting-requests` | `api_v1_admin_platform_hosting_requests_list` | superadmin |
| n | GET | `/admin/platform/hosting-switch` | `api_v1_admin_platform_hosting_switch_retrieve` | superadmin |
| n | PUT | `/admin/platform/hosting-switch` | `api_v1_admin_platform_hosting_switch_update` | superadmin |
| n | GET | `/admin/platform/image-adapter` | `api_v1_admin_platform_image_adapter_retrieve` | superadmin |
| n | PATCH | `/admin/platform/image-adapter` | `api_v1_admin_platform_image_adapter_partial_update` | superadmin |
| n | POST | `/admin/platform/image-adapter/test` | `api_v1_admin_platform_image_adapter_test_create` | superadmin |
| n | GET | `/admin/platform/inbox` | `api_v1_admin_platform_inbox_retrieve` | superadmin |
| n | GET | `/admin/platform/legal-pages/{slug}` | `api_v1_admin_platform_legal_pages_retrieve` | superadmin |
| n | PUT | `/admin/platform/legal-pages/{slug}` | `api_v1_admin_platform_legal_pages_update` | superadmin |
| n | DELETE | `/admin/platform/legal-pages/{slug}` | `api_v1_admin_platform_legal_pages_destroy` | superadmin |
| n | GET | `/admin/platform/limit-defaults` | `api_v1_admin_platform_limit_defaults_retrieve` | superadmin |
| n | PUT | `/admin/platform/limit-defaults` | `api_v1_admin_platform_limit_defaults_update` | superadmin |
| n | GET | `/admin/platform/module-defaults` | `api_v1_admin_platform_module_defaults_retrieve` | superadmin |
| n | GET | `/admin/platform/queues` | `api_v1_admin_platform_queues_retrieve` | superadmin |
| n | GET | `/admin/platform/request-limits` | `api_v1_admin_platform_request_limits_list` | superadmin |
| n | PUT | `/admin/platform/request-limits/{scope}` | `api_v1_admin_platform_request_limits_update` | superadmin |
| n | DELETE | `/admin/platform/request-limits/{scope}` | `api_v1_admin_platform_request_limits_destroy` | superadmin |
| n | GET | `/admin/platform/search` | `api_v1_admin_platform_search_retrieve` | superadmin |
| n | GET | `/admin/platform/spaces/{makerspace_id}/hosting-type` | `api_v1_admin_platform_spaces_hosting_type_retrieve` | superadmin |
| n | PUT | `/admin/platform/spaces/{makerspace_id}/hosting-type` | `api_v1_admin_platform_spaces_hosting_type_update` | superadmin |
| n | GET | `/admin/platform/spaces/{makerspace_id}/limits` | `api_v1_admin_platform_spaces_limits_retrieve` | superadmin |
| n | PUT | `/admin/platform/spaces/{makerspace_id}/limits` | `api_v1_admin_platform_spaces_limits_update` | superadmin |
| n | GET | `/admin/platform/spaces/{makerspace_id}/snapshot` | `api_v1_admin_platform_spaces_snapshot_retrieve` | superadmin |
| n | POST | `/admin/platform/spaces/limits-bulk` | `api_v1_admin_platform_spaces_limits_bulk_create` | superadmin |
| n | POST | `/admin/platform/spaces/plan-bulk` | `api_v1_admin_platform_spaces_plan_bulk_create` | superadmin |
| n | GET | `/admin/platform/telemetry` | `api_v1_admin_platform_telemetry_retrieve` | superadmin |
| n | PATCH | `/admin/platform/telemetry` | `api_v1_admin_platform_telemetry_partial_update` | superadmin |
| n | GET | `/admin/platform/wallet-credentials` | `api_v1_admin_platform_wallet_credentials_retrieve` | superadmin |
| n | PATCH | `/admin/platform/wallet-credentials` | `api_v1_admin_platform_wallet_credentials_partial_update` | superadmin |
| c | GET | `/admin/qr-print-batches/{id}` | `api_v1_admin_qr_print_batches_retrieve` | staff |
| c | GET | `/admin/qr-print-batches/{id}/download` | `api_v1_admin_qr_print_batches_download_retrieve` | staff |
| c | GET | `/admin/qr/{id}/print` | `api_v1_admin_qr_print_retrieve` | staff |
| c | POST | `/admin/qr/{id}/revoke` | `api_v1_admin_qr_revoke_create` | staff |
| c | POST | `/admin/qr/boxes` | `api_v1_admin_qr_boxes_create` | staff |
| c | POST | `/admin/qr/containers` | `api_v1_admin_qr_containers_create` | staff |
| n | POST | `/admin/qr/external` | `api_v1_admin_qr_external_create` | staff |
| c | POST | `/admin/qr/resolve` | `api_v1_admin_qr_resolve_create` | staff |
| c | POST | `/admin/qr/scan` | `api_v1_admin_qr_scan_create` | staff |
| c | POST | `/admin/qr/tools` | `api_v1_admin_qr_tools_create` | staff |
| c | GET | `/admin/reports/{report_key}/export` | `api_v1_admin_reports_export_retrieve` | staff |
| n | GET | `/admin/shelf-checks/{id}` | `api_v1_admin_shelf_checks_retrieve` | staff |
| c | POST | `/admin/shop/orders/{id}/collect/` | `api_v1_admin_shop_orders_collect_create` | staff |
| n | POST | `/admin/shop/orders/{id}/move-pickup-to-space/` | `api_v1_admin_shop_orders_move_pickup_to_space_create` | staff |
| c | POST | `/admin/spaces/{id}/bookings/` | `api_v1_admin_spaces_bookings_create` | staff |
| n | GET | `/admin/spaces/{id}/bookings/availability/` | `api_v1_admin_spaces_bookings_availability_retrieve` | staff |
| n | POST | `/admin/spaces/{id}/bookings/quote/` | `api_v1_admin_spaces_bookings_quote_create` | staff |
| n | GET | `/admin/spaces/{id}/bookings/readiness/` | `api_v1_admin_spaces_bookings_readiness_retrieve` | staff |
| n | POST | `/admin/spaces/{id}/organization-bookings/` | `api_v1_admin_spaces_organization_bookings_create` | staff |
| n | GET | `/admin/spaces/{id}/organization-bookings/choices/` | `api_v1_admin_spaces_organization_bookings_choices_list` | staff |
| n | GET | `/admin/staff-cards/{id}` | `api_v1_admin_staff_cards_retrieve` | staff |
| n | GET | `/admin/staff-cards/{id}/download` | `api_v1_admin_staff_cards_download_retrieve` | staff |
| n | GET | `/admin/staff-cards/{id}/photo-cutout` | `api_v1_admin_staff_cards_photo_cutout_retrieve` | staff |
| n | POST | `/admin/staff-cards/{id}/photo-cutout` | `api_v1_admin_staff_cards_photo_cutout_create` | staff |
| n | PATCH | `/admin/staff-cards/{id}/photo-cutout` | `api_v1_admin_staff_cards_photo_cutout_partial_update` | staff |
| n | DELETE | `/admin/staff-cards/{id}/photo-cutout` | `api_v1_admin_staff_cards_photo_cutout_destroy` | staff |
| n | GET | `/admin/staff-cards/{id}/print-face` | `api_v1_admin_staff_cards_print_face_retrieve` | staff |
| n | POST | `/admin/staff-cards/{id}/reissue` | `api_v1_admin_staff_cards_reissue_create` | staff |
| n | POST | `/admin/staff-cards/{id}/revoke` | `api_v1_admin_staff_cards_revoke_create` | staff |
| c | POST | `/admin/users/{id}/reset-password` | `api_v1_admin_users_reset_password_create` | staff |
| c | POST | `/admin/users/{id}/restore-access` | `api_v1_admin_users_restore_access_create` | staff |
| c | POST | `/admin/users/{id}/restrict` | `api_v1_admin_users_restrict_create` | staff |
| c | GET | `/admin/users/booking-managers` | `api_v1_admin_users_booking_managers_list` | staff |
| c | POST | `/admin/users/booking-managers` | `api_v1_admin_users_booking_managers_create` | staff |
| c | GET | `/admin/users/event-managers` | `api_v1_admin_users_event_managers_list` | staff |
| c | POST | `/admin/users/event-managers` | `api_v1_admin_users_event_managers_create` | staff |
| c | GET | `/admin/users/handover` | `api_v1_admin_users_handover_list` | staff |
| c | POST | `/admin/users/handover` | `api_v1_admin_users_handover_create` | staff |
| c | GET | `/admin/users/inventory-managers` | `api_v1_admin_users_inventory_managers_list` | staff |
| c | POST | `/admin/users/inventory-managers` | `api_v1_admin_users_inventory_managers_create` | staff |
| c | GET | `/admin/users/machine-managers` | `api_v1_admin_users_machine_managers_list` | staff |
| c | POST | `/admin/users/machine-managers` | `api_v1_admin_users_machine_managers_create` | staff |
| c | GET | `/admin/users/space-managers` | `api_v1_admin_users_space_managers_list` | staff |
| c | POST | `/admin/users/space-managers` | `api_v1_admin_users_space_managers_create` | staff |
| n | GET | `/auth/browser-state` | `api_v1_auth_browser_state_retrieve` | member |
| c | POST | `/auth/claim/redeem` | `api_v1_auth_claim_redeem_create` | member |
| c | DELETE | `/auth/phone` | `api_v1_auth_phone_destroy` | member |
| n | POST | `/auth/social/github/link/authorize` | `api_v1_auth_social_github_link_authorize_create` | member |
| n | POST | `/auth/social/link/callback` | `api_v1_auth_social_link_callback_create` | member |
| n | POST | `/auth/social/oidc/{slug}/link/authorize` | `api_v1_auth_social_oidc_link_authorize_create` | member |
| c | GET | `/backups/selfhost-moves/{id}/{token}` | `api_v1_backups_selfhost_moves_retrieve` | member |
| n | POST | `/device/adapter/v1/access/authorize` | `api_v1_device_adapter_v1_access_authorize_create` | device-adapter |
| n | GET | `/device/adapter/v1/access/cache` | `api_v1_device_adapter_v1_access_cache_retrieve` | device-adapter |
| n | POST | `/device/adapter/v1/access/offline-decisions` | `api_v1_device_adapter_v1_access_offline_decisions_create` | device-adapter |
| n | POST | `/device/adapter/v1/artifacts` | `api_v1_device_adapter_v1_artifacts_create` | device-adapter |
| n | POST | `/device/adapter/v1/artifacts/{id}/complete` | `api_v1_device_adapter_v1_artifacts_complete_create` | device-adapter |
| n | GET | `/device/adapter/v1/bindings` | `api_v1_device_adapter_v1_bindings_retrieve` | device-adapter |
| n | POST | `/device/adapter/v1/commands/{id}/ack` | `api_v1_device_adapter_v1_commands_ack_create` | device-adapter |
| n | POST | `/device/adapter/v1/commands/lease` | `api_v1_device_adapter_v1_commands_lease_create` | device-adapter |
| n | GET | `/device/adapter/v1/config` | `api_v1_device_adapter_v1_config_retrieve` | device-adapter |
| n | POST | `/device/adapter/v1/config/ack` | `api_v1_device_adapter_v1_config_ack_create` | device-adapter |
| n | POST | `/device/adapter/v1/events` | `api_v1_device_adapter_v1_events_create` | device-adapter |
| n | POST | `/device/adapter/v1/hello` | `api_v1_device_adapter_v1_hello_create` | device-adapter |
| n | POST | `/device/adapter/v1/jobs/{id}/ack` | `api_v1_device_adapter_v1_jobs_ack_create` | device-adapter |
| n | GET | `/device/adapter/v1/jobs/{id}/file` | `api_v1_device_adapter_v1_jobs_file_retrieve` | device-adapter |
| n | POST | `/device/adapter/v1/jobs/{id}/progress` | `api_v1_device_adapter_v1_jobs_progress_create` | device-adapter |
| n | POST | `/device/adapter/v1/jobs/{id}/report` | `api_v1_device_adapter_v1_jobs_report_create` | device-adapter |
| n | POST | `/device/adapter/v1/jobs/lease` | `api_v1_device_adapter_v1_jobs_lease_create` | device-adapter |
| n | POST | `/device/adapter/v1/kiosk/sessions` | `api_v1_device_adapter_v1_kiosk_sessions_create` | device-adapter |
| n | DELETE | `/device/adapter/v1/kiosk/sessions/{sid}` | `api_v1_device_adapter_v1_kiosk_sessions_destroy` | device-adapter |
| n | POST | `/device/adapter/v1/kiosk/sessions/{sid}/evidence` | `api_v1_device_adapter_v1_kiosk_sessions_evidence_create` | device-adapter |
| n | POST | `/device/adapter/v1/kiosk/sessions/{sid}/issue` | `api_v1_device_adapter_v1_kiosk_sessions_issue_create` | device-adapter |
| n | POST | `/device/adapter/v1/kiosk/sessions/{sid}/return` | `api_v1_device_adapter_v1_kiosk_sessions_return_create` | device-adapter |
| n | POST | `/device/adapter/v1/kiosk/sessions/{sid}/scan` | `api_v1_device_adapter_v1_kiosk_sessions_scan_create` | device-adapter |
| n | POST | `/device/adapter/v1/media/{watch_id}/recording` | `api_v1_device_adapter_v1_media_recording_create` | device-adapter |
| n | GET | `/device/adapter/v1/media/{watch_id}/signal` | `api_v1_device_adapter_v1_media_signal_retrieve` | device-adapter |
| n | POST | `/device/adapter/v1/media/{watch_id}/signal` | `api_v1_device_adapter_v1_media_signal_create` | device-adapter |
| n | POST | `/device/adapter/v1/media/{watch_id}/snapshot` | `api_v1_device_adapter_v1_media_snapshot_create` | device-adapter |
| n | POST | `/device/adapter/v1/sessions/{id}/stop` | `api_v1_device_adapter_v1_sessions_stop_create` | device-adapter |
| n | POST | `/device/adapter/v1/sessions/start` | `api_v1_device_adapter_v1_sessions_start_create` | device-adapter |
| n | POST | `/device/adapter/v1/status` | `api_v1_device_adapter_v1_status_create` | device-adapter |
| n | GET | `/device/adapter/v1/time` | `api_v1_device_adapter_v1_time_retrieve` | device-adapter |
| n | POST | `/device/adapter/v1/usage` | `api_v1_device_adapter_v1_usage_create` | device-adapter |
| c | GET | `/discover/{kind}/` | `api_v1_discover_retrieve` | member |
| n | GET | `/discover/events/organizers/` | `api_v1_discover_events_organizers_retrieve` | member |
| n | GET | `/discover/legal/{page}/` | `api_v1_discover_legal_retrieve` | member |
| n | POST | `/event-checkin-stations/{public_token}/badge-receipts/` | `api_v1_event_checkin_stations_badge_receipts_create` | display/station/provider |
| n | GET | `/event-checkin-stations/{public_token}/badge/{registration_id}/` | `api_v1_event_checkin_stations_badge_retrieve` | display/station/provider |
| n | GET | `/handles/check` | `api_v1_handles_check_retrieve` | member |
| c | POST | `/integrations/push/devices` | `api_v1_integrations_push_devices_create` | member |
| n | GET | `/member/adapter-artifacts/{id}/url` | `api_v1_member_adapter_artifacts_url_retrieve` | member |
| n | GET | `/member/adapter-artifacts/requests/{request_id}` | `api_v1_member_adapter_artifacts_requests_retrieve` | member |
| n | GET | `/member/adapter-detections/requests/{request_id}` | `api_v1_member_adapter_detections_requests_retrieve` | member |
| n | DELETE | `/member/adapter-watch/{id}` | `api_v1_member_adapter_watch_destroy` | member |
| n | GET | `/member/adapter-watch/{id}/frame` | `api_v1_member_adapter_watch_frame_retrieve` | member |
| n | GET | `/member/adapter-watch/{id}/signal` | `api_v1_member_adapter_watch_signal_retrieve` | member |
| n | POST | `/member/adapter-watch/{id}/signal` | `api_v1_member_adapter_watch_signal_create` | member |
| n | POST | `/member/adapter-watch/{id}/talk` | `api_v1_member_adapter_watch_talk_create` | member |
| n | POST | `/member/adapter-watch/requests/{request_id}` | `api_v1_member_adapter_watch_requests_create` | member |
| n | GET | `/member/cards/{kind}/{card_id}/photo/cutout` | `api_v1_member_cards_photo_cutout_retrieve` | member |
| n | POST | `/member/cards/{kind}/{card_id}/photo/cutout` | `api_v1_member_cards_photo_cutout_create` | member |
| n | PUT | `/member/cards/{kind}/{card_id}/photo/cutout` | `api_v1_member_cards_photo_cutout_update` | member |
| n | PATCH | `/member/cards/{kind}/{card_id}/photo/cutout` | `api_v1_member_cards_photo_cutout_partial_update` | member |
| n | DELETE | `/member/cards/{kind}/{card_id}/photo/cutout` | `api_v1_member_cards_photo_cutout_destroy` | member |
| n | GET | `/member/event-payouts/{obligation_id}/payee-files/` | `api_v1_member_event_payouts_payee_files_list` | member |
| c | POST | `/member/issues` | `api_v1_member_issues_create` | member |
| n | POST | `/member/machine-jobs/{id}/consumables` | `api_v1_member_machine_jobs_consumables_create` | member |
| c | GET | `/member/machine-sessions` | `api_v1_member_machine_sessions_list` | member |
| c | POST | `/member/machine-sessions/{id}/stop` | `api_v1_member_machine_sessions_stop_create` | member |
| n | GET | `/member/machine-type-documents/{id}/url` | `api_v1_member_machine_type_documents_url_retrieve` | member |
| c | GET | `/member/machines/{machine_id}/session` | `api_v1_member_machines_session_retrieve` | member |
| c | POST | `/member/machines/{machine_id}/sessions/start` | `api_v1_member_machines_sessions_start_create` | member |
| n | POST | `/member/machines/{machine_id}/supervised-sessions` | `api_v1_member_machines_supervised_sessions_create` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/admission/photo` | `api_v1_member_makerspaces_admission_photo_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/allowances` | `api_v1_member_makerspaces_allowances_retrieve` | member |
| c | GET | `/member/makerspaces/{makerspace_id}/borrowing-history` | `api_v1_member_makerspaces_borrowing_history_list` | member |
| c | GET | `/member/makerspaces/{makerspace_id}/certifications` | `api_v1_member_makerspaces_certifications_retrieve` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/day-passes` | `api_v1_member_makerspaces_day_passes_list` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/day-passes/{product_id}/purchase` | `api_v1_member_makerspaces_day_passes_purchase_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/event-registrations/{id}/equipment/` | `api_v1_member_makerspaces_event_registrations_equipment_retrieve` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/events/{id}/teams/{team_id}/decline-request/` | `api_v1_member_makerspaces_events_teams_decline_request_create` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/events/{id}/teams/{team_id}/handover/` | `api_v1_member_makerspaces_events_teams_handover_create` | member |
| c | POST | `/member/makerspaces/{makerspace_id}/events/{id}/teams/{team_id}/leave/` | `api_v1_member_makerspaces_events_teams_leave_create` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/events/{id}/teams/{team_id}/remove-member/` | `api_v1_member_makerspaces_events_teams_remove_member_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/guardian-consents` | `api_v1_member_makerspaces_guardian_consents_retrieve` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/guardian-consents/{profile_id}/revoke` | `api_v1_member_makerspaces_guardian_consents_revoke_create` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/guardian-consents/{profile_id}/sign` | `api_v1_member_makerspaces_guardian_consents_sign_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/guest-passes` | `api_v1_member_makerspaces_guest_passes_retrieve` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/guest-passes/{pass_id}/accept-waiver` | `api_v1_member_makerspaces_guest_passes_accept_waiver_create` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/guest-passes/{pass_id}/wallet/{platform}` | `api_v1_member_makerspaces_guest_passes_wallet_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/guest-passes/sponsored` | `api_v1_member_makerspaces_guest_passes_sponsored_list` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/guest-passes/sponsored` | `api_v1_member_makerspaces_guest_passes_sponsored_create` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/guest-passes/sponsored/{pass_id}/revoke` | `api_v1_member_makerspaces_guest_passes_sponsored_revoke_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/incidents` | `api_v1_member_makerspaces_incidents_retrieve` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/incidents` | `api_v1_member_makerspaces_incidents_create` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/join-prefill` | `api_v1_member_makerspaces_join_prefill_retrieve` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/machine-access` | `api_v1_member_makerspaces_machine_access_retrieve` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/machine-types/{type_id}/guide` | `api_v1_member_makerspaces_machine_types_guide_retrieve` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/machine-use/events/` | `api_v1_member_makerspaces_machine_use_events_list` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/machines` | `api_v1_member_makerspaces_machines_retrieve` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/my-guardian-consent` | `api_v1_member_makerspaces_my_guardian_consent_retrieve` | member |
| c | POST | `/member/makerspaces/{makerspace_id}/payments/{payment_id}/checkout` | `api_v1_member_makerspaces_payments_checkout_create` | member |
| c | GET | `/member/makerspaces/{makerspace_id}/profile` | `api_v1_member_makerspaces_profile_retrieve` | member |
| c | PUT | `/member/makerspaces/{makerspace_id}/profile` | `api_v1_member_makerspaces_profile_update` | member |
| c | PATCH | `/member/makerspaces/{makerspace_id}/profile` | `api_v1_member_makerspaces_profile_partial_update` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/profile/achievements` | `api_v1_member_makerspaces_profile_achievements_list` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/profile/achievements` | `api_v1_member_makerspaces_profile_achievements_create` | member |
| n | PATCH | `/member/makerspaces/{makerspace_id}/profile/achievements/{id}` | `api_v1_member_makerspaces_profile_achievements_partial_update` | member |
| n | DELETE | `/member/makerspaces/{makerspace_id}/profile/achievements/{id}` | `api_v1_member_makerspaces_profile_achievements_destroy` | member |
| c | POST | `/member/makerspaces/{makerspace_id}/profile/handle` | `api_v1_member_makerspaces_profile_handle_create` | member |
| c | DELETE | `/member/makerspaces/{makerspace_id}/profile/handle` | `api_v1_member_makerspaces_profile_handle_destroy` | member |
| c | POST | `/member/makerspaces/{makerspace_id}/profile/image` | `api_v1_member_makerspaces_profile_image_create` | member |
| c | PUT | `/member/makerspaces/{makerspace_id}/profile/image` | `api_v1_member_makerspaces_profile_image_update` | member |
| c | DELETE | `/member/makerspaces/{makerspace_id}/profile/image` | `api_v1_member_makerspaces_profile_image_destroy` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/profile/project-import` | `api_v1_member_makerspaces_profile_project_import_list` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/profile/project-import` | `api_v1_member_makerspaces_profile_project_import_create` | member |
| c | GET | `/member/makerspaces/{makerspace_id}/profile/timeline` | `api_v1_member_makerspaces_profile_timeline_retrieve` | member |
| c | POST | `/member/makerspaces/{makerspace_id}/profile/timeline` | `api_v1_member_makerspaces_profile_timeline_create` | member |
| c | GET | `/member/makerspaces/{makerspace_id}/profile/timeline/{id}` | `api_v1_member_makerspaces_profile_timeline_retrieve_2` | member |
| c | PATCH | `/member/makerspaces/{makerspace_id}/profile/timeline/{id}` | `api_v1_member_makerspaces_profile_timeline_partial_update` | member |
| c | DELETE | `/member/makerspaces/{makerspace_id}/profile/timeline/{id}` | `api_v1_member_makerspaces_profile_timeline_destroy` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/supervised-sessions` | `api_v1_member_makerspaces_supervised_sessions_retrieve` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/volunteer-credits` | `api_v1_member_makerspaces_volunteer_credits_list` | member |
| n | GET | `/member/makerspaces/{makerspace_id}/volunteer-hours` | `api_v1_member_makerspaces_volunteer_hours_list` | member |
| n | POST | `/member/makerspaces/{makerspace_id}/volunteer-hours` | `api_v1_member_makerspaces_volunteer_hours_create` | member |
| c | POST | `/member/organizations/{id}/leave/` | `api_v1_member_organizations_leave_create` | member |
| n | GET | `/member/profile` | `api_v1_member_profile_retrieve` | member |
| n | PUT | `/member/profile` | `api_v1_member_profile_update` | member |
| n | PATCH | `/member/profile` | `api_v1_member_profile_partial_update` | member |
| n | GET | `/member/profile/achievements` | `api_v1_member_profile_achievements_list` | member |
| n | POST | `/member/profile/achievements` | `api_v1_member_profile_achievements_create` | member |
| n | PATCH | `/member/profile/achievements/{id}` | `api_v1_member_profile_achievements_partial_update` | member |
| n | DELETE | `/member/profile/achievements/{id}` | `api_v1_member_profile_achievements_destroy` | member |
| n | POST | `/member/profile/handle` | `api_v1_member_profile_handle_create` | member |
| n | DELETE | `/member/profile/handle` | `api_v1_member_profile_handle_destroy` | member |
| n | POST | `/member/profile/image` | `api_v1_member_profile_image_create` | member |
| n | PUT | `/member/profile/image` | `api_v1_member_profile_image_update` | member |
| n | DELETE | `/member/profile/image` | `api_v1_member_profile_image_destroy` | member |
| n | GET | `/member/profile/project-import` | `api_v1_member_profile_project_import_list` | member |
| n | POST | `/member/profile/project-import` | `api_v1_member_profile_project_import_create` | member |
| n | GET | `/member/profile/timeline` | `api_v1_member_profile_timeline_retrieve` | member |
| n | POST | `/member/profile/timeline` | `api_v1_member_profile_timeline_create` | member |
| n | GET | `/member/profile/timeline/{id}` | `api_v1_member_profile_timeline_retrieve_2` | member |
| n | PATCH | `/member/profile/timeline/{id}` | `api_v1_member_profile_timeline_partial_update` | member |
| n | DELETE | `/member/profile/timeline/{id}` | `api_v1_member_profile_timeline_destroy` | member |
| r | GET | `/member/shop/orders/` | `api_v1_member_shop_orders_retrieve` | member |
| r | GET | `/member/shop/orders/{id}/` | `api_v1_member_shop_orders_retrieve_2` | member |
| n | GET | `/member/supervised-sessions/{id}` | `api_v1_member_supervised_sessions_retrieve` | member |
| n | POST | `/member/supervised-sessions/{id}/close` | `api_v1_member_supervised_sessions_close_create` | member |
| n | GET | `/member/supervised-sessions/{id}/people` | `api_v1_member_supervised_sessions_people_retrieve` | member |
| n | POST | `/member/supervised-sessions/{id}/supervisees` | `api_v1_member_supervised_sessions_supervisees_create` | member |
| n | DELETE | `/member/supervised-sessions/{id}/supervisees/{user_id}` | `api_v1_member_supervised_sessions_supervisees_destroy` | member |
| n | POST | `/member/supervised-sessions/{id}/uses` | `api_v1_member_supervised_sessions_uses_create` | member |
| n | POST | `/member/supervised-uses/{id}/end` | `api_v1_member_supervised_uses_end_create` | member |
| n | PATCH | `/memberships/requests/{id}` | `api_v1_memberships_requests_partial_update` | member |
| n | POST | `/notifications/browser-firebase/{makerspace_id}/challenge` | `api_v1_notifications_browser_firebase_challenge_create` | member |
| n | DELETE | `/notifications/browser-firebase/{makerspace_id}/challenge` | `api_v1_notifications_browser_firebase_challenge_destroy` | member |
| n | GET | `/notifications/browser-firebase/{makerspace_id}/config` | `api_v1_notifications_browser_firebase_config_retrieve` | member |
| n | POST | `/notifications/browser-firebase/{makerspace_id}/confirm` | `api_v1_notifications_browser_firebase_confirm_create` | member |
| n | POST | `/notifications/browser-firebase/{makerspace_id}/may-resume` | `api_v1_notifications_browser_firebase_space_may_resume_create` | member |
| n | POST | `/notifications/browser-firebase/may-resume` | `api_v1_notifications_browser_firebase_may_resume_create` | member |
| c | GET | `/notifications/inbox/{makerspace_id}` | `api_v1_notifications_inbox_retrieve` | member |
| n | GET | `/notifications/inbox/{makerspace_id}/families` | `api_v1_notifications_inbox_families_retrieve` | member |
| n | GET | `/notifications/unsubscribe/{token}` | `api_v1_notifications_unsubscribe_retrieve` | member |
| c | GET | `/payments/connect/callback` | `api_v1_payments_connect_callback_retrieve` | member |
| n | GET | `/profiles/by-account/{user_id}/` | `api_v1_profiles_by_account_retrieve` | member |
| c | GET | `/public/{makerspace_slug}/bookings/calendar/{raw_token}.ics` | `api_v1_public_bookings_calendar_.ics_retrieve` | public |
| c | GET | `/public/{makerspace_slug}/calendar/mine/{raw_token}.ics` | `api_v1_public_calendar_mine_.ics_retrieve` | public |
| n | GET | `/public/{makerspace_slug}/day-passes` | `api_v1_public_day_passes_list` | public |
| c | GET | `/public/{makerspace_slug}/donations` | `api_v1_public_donations_retrieve` | public |
| n | GET | `/public/{makerspace_slug}/equipment-kits/` | `api_v1_public_equipment_kits_list` | public |
| n | GET | `/public/{makerspace_slug}/equipment-kits/{kit_id}/` | `api_v1_public_equipment_kit_retrieve` | public |
| c | POST | `/public/{makerspace_slug}/machine-service/3d-printer/requests` | `api_v1_public_machine_service_3d_printer_requests_create` | public |
| c | POST | `/public/{makerspace_slug}/machine-service/3d-printer/uploads` | `api_v1_public_machine_service_3d_printer_uploads_create` | public |
| n | GET | `/public/{makerspace_slug}/member-units` | `api_v1_public_member_units_retrieve` | public |
| c | POST | `/public/{makerspace_slug}/my-bookings/{public_token}/cancel/` | `api_v1_public_my_bookings_cancel_create` | public |
| n | POST | `/public/{makerspace_slug}/requests/contextual` | `api_v1_public_requests_contextual_create` | public |
| c | POST | `/public/{makerspace_slug}/spaces/{public_token}/book/` | `api_v1_public_spaces_book_create` | public |
| c | POST | `/public/{makerspace_slug}/tools/checkout` | `api_v1_public_tools_checkout_create` | public |
| c | POST | `/public/{makerspace_slug}/tools/return` | `api_v1_public_tools_return_create` | public |
| c | GET | `/public/event-programmes/{public_token}/results/` | `api_v1_public_event_programmes_results_retrieve` | public |
| n | GET | `/public/m/{makerspace_slug}/shop/events/{public_token}/offers/` | `api_v1_public_m_shop_events_offers_retrieve` | public |
| c | POST | `/public/m/{makerspace_slug}/shop/orders/` | `api_v1_public_m_shop_orders_create` | public |
| c | GET | `/public/machine-service/3d-printer/requests/{public_token}/status` | `api_v1_public_machine_service_3d_printer_requests_status_retrieve` | public |
| c | GET | `/public/machine-service/requests/{public_token}/status` | `api_v1_public_machine_service_requests_status_retrieve` | public |
| n | GET | `/public/makerspaces/{makerspace_slug}/machines/now/` | `api_v1_public_makerspaces_machines_now_retrieve` | public |
| n | GET | `/public/makerspaces/{makerspace_slug}/presence/here-now/` | `api_v1_public_makerspaces_presence_here_now_retrieve` | public |
| n | GET | `/public/makerspaces/{makerspace_slug}/presence/now-config/` | `api_v1_public_makerspaces_presence_now_config_retrieve` | public |
| n | GET | `/public/organizations/` | `api_v1_public_organizations_retrieve` | public |
| r | GET | `/public/organizations/{slug}/` | `api_v1_public_organizations_retrieve_2` | public |
| c | GET | `/public/page-handles/{handle}/` | `api_v1_public_page_handles_retrieve` | public |
| c | GET | `/public/profiles/{handle}/` | `api_v1_public_profiles_retrieve` | public |
| c | GET | `/public/profiles/{handle}/activity` | `api_v1_public_profiles_activity_retrieve` | public |
| c | GET | `/public/profiles/{handle}/events` | `api_v1_public_profiles_events_retrieve` | public |
| c | GET | `/public/profiles/{handle}/github` | `api_v1_public_profiles_github_retrieve` | public |
| c | GET | `/public/profiles/{handle}/projects` | `api_v1_public_profiles_projects_retrieve` | public |
| n | GET | `/space-displays/{token}/state/` | `api_v1_space_displays_state_retrieve_2` | display/station/provider |
| n | POST | `/space-displays/register/` | `api_v1_space_displays_register_create` | display/station/provider |
| n | GET | `/space-displays/state/` | `api_v1_space_displays_state_retrieve` | display/station/provider |
| c | GET | `/wallet/apple/v1/devices/{device}/registrations/{pass_type}` | `api_v1_wallet_apple_v1_devices_registrations_retrieve` | display/station/provider |
| c | POST | `/wallet/apple/v1/log` | `api_v1_wallet_apple_v1_log_create` | display/station/provider |
| c | GET | `/wallet/apple/v1/passes/{pass_type}/{serial}` | `api_v1_wallet_apple_v1_passes_retrieve` | display/station/provider |
| n | GET | `/wallet/guest-pass/{token}.pkpass` | `api_v1_wallet_guest_pass_.pkpass_retrieve` | display/station/provider |
