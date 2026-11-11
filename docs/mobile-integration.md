# Connect a branded native app

Use this guide for the deployment's Android and iOS apps. An approved registration must have
**Makerspace left blank**: tenant-scoped rows remain inert. Create a separate row for each platform
and environment. Development registrations never publish association files or a production minimum.
Only one deployment-global registration may be approved for each platform/environment pair.
Together the production Android and Apple rows describe the deployment's one logical app.
Rotate Android distribution signers on the same row; keep both old and new digests during rollout.
To replace a package or bundle ID, revoke its previous registration before approving the replacement;
revocation permanently revokes that registration's device grants. Pending and revoked rows preserve history.

## Server values in /control/

Sign in to the superadmin control plane through your deployment's existing protected access path.
Do not enable a public control-plane proxy just to configure an app.

| Value | /control/ model and field | Meaning |
| --- | --- | --- |
| App display name | Accounts → Platform attestation settings → App display name | Deployment-owned name shared by Android and iOS; required, up to 100 characters, default SpaceWorks. This is independent of tenant branding. |
| Android package / Apple bundle ID | Accounts → Native app registrations → App ID | Exact identifier compiled into the app; for example org.example.spaceworks. |
| Platform and environment | Native app registrations → Platform, Environment | Apple or Android; development or production. |
| Approval | Native app registrations → Status | Approved permits the global app to authenticate. Revoking also permanently revokes its grants. |
| Scope | Native app registrations → Makerspace | Leave blank for deployment-global authority. |
| Distribution signing certificates | Native app registrations → Distribution signer digests / App ID Prefix | Android JSON list of 1–5 SHA-256 digests, hex or colon-separated hex. Include the current Play App Signing certificate and previous distribution keys needed during rotation. **The upload key is not a distribution signer**: it only authenticates uploads to Play. |
| App ID Prefix | Same registration field | Apple JSON list with exactly one ten-character uppercase alphanumeric prefix. Usually the Team ID, but use the actual App ID Prefix from the Apple developer account. It binds App Attest and the association app identifier. |
| Minimum version | Native app registrations → Min supported version | Optional dotted numeric version, such as 1.4.0. /config publishes the highest approved global production value per platform, comparing numeric components. Blank means no minimum. |
| Legacy verifier label | Native app registrations → Verifier config key | Choose a stable label for new rows; stored signers need no environment JSON. Old empty rows may temporarily resolve an existing DEVICE_ATTESTATION_APPS entry under this label. |
| Play Integrity service account | Accounts → Platform attestation settings → Play integrity service account raw | Write-only Google service-account JSON with an RSA key and permission to decode this app's Play Integrity Standard tokens. Stored encrypted. Enable Play Integrity and link its Cloud project in the Play Console. |
| FCM server credential | Integrations → Platform push settings → Fcm service account raw | Write-only service-account JSON for sending Firebase messages; this is not google-services.json. |
| APNs credential | Platform push settings → Apns private key raw, Apns team id, Apns key id, Apns topic | Apple .p8 key and its identifiers; topic must equal the particular iOS registration's bundle ID. Push is optional for login. |
| Google native audiences | Accounts → Platform social auth settings → Google android client id, Google ios client id | Native OAuth client IDs for the relevant platform. These are audiences, not the package/bundle identifier. |
| Apple native audience | Platform social auth settings → Apple native app ids | Include every enabled iOS bundle ID. This is a JSON list of bundle IDs, without the App ID Prefix. |
| Sign in with Apple revocation key | Platform social auth settings → Apple team id, Apple key id, Apple private key raw | Existing encrypted social-settings key. Optional for login readiness; needed by the Apple account-revocation flow. This team ID is distinct from the registration's App ID Prefix. |
| Generic OIDC audience | Accounts → OIDC providers → Client ID, Issuer, JWKS URL | Reuse the existing public-client OIDC configuration for each enabled provider. |

Apple in-process App Attest requires the registration prefix and public Apple trust material;
there is no private App Attest server key to upload. Android uses the Play Integrity credential above.
The existing external verifier override remains deployment configuration (HTTPS verifier URL and token).
**External mode supports one signer**, the first list entry: use in-process Play Integrity for a rotation
with several accepted distribution keys. A development-insecure bypass never makes production ready.

Enable the deployment's mobile module to allow new grants. Turning it off stops new pairings;
revocation remains explicit for existing devices. Enabled native Google/Apple sign-in providers need
their matching audiences; disable a provider you do not offer through the existing login-method controls.

Use **Mobile readiness** on the Native app registrations changelist. It reports each approved global
registration/environment and a production summary for Android and iOS. Each platform summary requires
all its eligible production registrations to be ready. Login requirements are separate
from optional push, Apple revocation and associations. The superadmin API presents the same report at
GET /api/v1/admin/platform/mobile-readiness. Checks read configuration only; they do not probe providers
or reveal secret values. Save operations are audited; reading the report is not audited.

The public `GET /api/v1/config` native object includes `app_display_name` and
`app_identity: {android: {app_id, signing_identities} | null, ios: {app_id, signing_identities} | null}`.
Only approved global **production** registrations publish identities. Signers are normalized Android
distribution SHA-256 hex digests or the Apple App ID Prefix. Missing or invalid identities return null.
The existing `min_app_version` and `providers` fields remain. These are public configuration values;
verifier labels, service-account JSON, private keys and tokens are never included. Editing the display
name with credential inputs left blank preserves existing encrypted credentials.

## Reconciled account and notification authority

Release 2 (one account per person, U-A2): a person signs in once and gets a member grant from
any primary method (password, Google, Apple, OIDC, phone). Staff authority is a **step-up** on
that person: device login with `authority=staff` + makerspace slug, or `POST
auth/device/staff-grant` from any active device session, always behind the authenticator and a
fresh attestation. The new grant carries `authority=staff` and the immutable
`staff_makerspace_id`; on staff routes the X-Makerspace-Id header is required and must match that
makerspace and the URL/body targets. A member grant never carries staff authority; losing the
staff role revokes the staff grants for that makerspace. Platform native grants are forbidden;
refresh cannot promote a grant and refuses a family from an older auth generation (401
`session_revoked`) or an app older than `MIN_NATIVE_APP_VERSION_*` (426
`native_app_update_required`). The release-1 `context`/`makerspace` login parameters are gone.
Self-deletion/90-day archive, restore, purge and Apple revocation stay person-only. Logout-all
revokes every session and device of the account. Full contract: `docs/mobile/MOBILE-APP-PRD.md` §7.
Accounts 0032 development role reset is not authorized for live authority data.

Personal push uses envelope deliveries with per-device children and optional inbox links;
inbox creation is not a trigger. Account-only source-tied recipients pass delivery policy,
but new native device registration/selection still requires active local membership. Disabling
the inbox module is supported; tombstoning the whole notifications app removes its adapter.
SMS consent binds the current phone instance/sender; WhatsApp requires separate signed endpoint
proof. STOP/suppression and ambiguous-outcome holds apply across device-independent delivery.
See the self-contained [builder contract](mobile/MOBILE-APP-PRD.md) for endpoint paths and
[rollout checkpoints](notification-reconciliation-rollout.md) for paused sending, original
mapping/replay sign-off, retained callback URLs and unsupplied destructive integrations 0043.
Regenerate OpenAPI after reconciliation; old generated type names are not the builder contract.

## Build inputs to hand to the app developer

Give the developer these inputs directly; there is no build-input API:

- Exact Android package name and iOS bundle ID, environment, API base URL and app branding.
- The **Play Integrity Cloud project number** (numeric project number, not the project ID), so the
  Android app can prepare Standard Integrity requests against the linked project.
- The app-specific **google-services.json** from Firebase for the exact Android package; it is a build
  configuration file, separate from both server service-account JSON credentials above.
- The native Google OAuth client IDs and the configured OIDC public-client details for the platforms built.
- The Apple App ID Prefix and associated-domains entitlement with **applinks:<host>** for every eligible
  host. Add webcredentials:<host> when the build uses associated web credentials. Enable App Attest for
  the matching environment in the provisioning configuration.
- Android verified HTTPS intent filters with android:autoVerify="true" and each eligible host. Derive
  their paths from **backend/apps/integrations/mobile_link_contract.py** (DESTINATIONS and
  association_patterns); the app must use the same contract to resolve destinations.

On a shared primary host, supported routes are /m/<slug>/member (including tabs/account and event
registration tickets), /m/<slug>/events/<token>, /m/<slug>/bookings/<token> and /m/<slug>/items/<id>.
On a verified custom domain, use the contract's corresponding /member, /events, /bookings and /items
forms; the host selects the makerspace. The contract also contains explicit excluded prefixes. Staff
admin, /control/, API and other public pages stay in the browser. Unsupported push links fall back to
inbox inside the app. Never generate an all-path intent filter from the association JSON alone.

## Hosts and release checks

Eligible primary hosts come from PUBLIC_APP_BASE_URL and the explicitly configured
PLATFORM_STAFF_ORIGINS frontend URLs. Custom frontend domains must be verified and belong to a
non-archived, servable makerspace. Infrastructure hosts and arbitrary CORS origins do not qualify.

Fetch these exact HTTPS paths on each host, with no trailing slash or redirect:

- /.well-known/assetlinks.json — Android distribution fingerprints.
- /.well-known/apple-app-site-association — Apple prefix.bundle app IDs, contract components/exclusions
  and webcredentials.

Both return application/json with a five-minute cache. With no eligible production registrations,
they return valid empty documents. Unknown hosts retain the managed host middleware's 400 response;
other deployments return 404 from the view. Association publication grants no CORS or browser-origin
trust. Only public application proxies serve these routes; control-only listeners still refuse them.
After changing signers, verify the published documents and allow their short cache to expire before
shipping. Test real-device attestation, login and links before release: readiness is configuration
validation, not evidence of a successful provider round trip.

## Payments (Stripe and Razorpay)

The payment provider is per makerspace (`MakerspacePaymentSettings.provider`, default
`stripe`, alternative `razorpay`). The Space Manager chooses the rail for that space;
apps consume the resolved vendor and never select it or store merchant secrets.
The Space Manager can set up either provider in the staff console's Online payments
settings, without deployment-maintainer provisioning. Select Stripe or Razorpay, enter
that account's credentials, copy its webhook URL into the provider dashboard, and save.
Credential writes and provider selection require recent session reauthentication; the
console prompts for verification when needed.

Credentials live on the server's per-makerspace payment-settings row. The Space Manager's
web console payment settings uses GET/PATCH
`/api/v1/admin/makerspace/{makerspace_id}/payment-settings`, authorized by
`MANAGE_MAKERSPACE` with the existing makerspace scope (including its superadmin-access
switch). Select `provider: "stripe" | "razorpay"`. Stripe fields are `stripe_publishable_key`, `stripe_secret_key`,
`stripe_webhook_secret` and `default_currency` (lowercase three-letter code).
Credential inputs are write-only; GET returns `*_set` booleans and
`effective_mode` (`raw`, `connect` or `unavailable`), never saved keys.
The protected /control/ Payments > Makerspace payment settings form remains an operator alternative
for Stripe fields. Secret keys and webhook secrets are encrypted at rest.
The Razorpay model fields are `razorpay_key_id` (public), `razorpay_key_secret` and
`razorpay_webhook_secret` (encrypted through their model setters). All three are writable
through the same staff API/panel and write-only in settings responses, including the public
key ID. GET returns `razorpay_key_id_set`, `razorpay_key_secret_set` and
`razorpay_webhook_secret_set`. Omit a credential to keep it, or send `""` to clear it;
the panel has an explicit clear control for each saved field. Razorpay key IDs start with
`rzp_test_` or `rzp_live_`. Validation is local; saving keys does not prove a provider round trip.
The response includes exact `stripe_webhook_url` and `razorpay_webhook_url` values, with
copy buttons in the panel. Audit metadata records changed field names only.

Own Stripe credentials take precedence. Managed deployments can alternatively use Stripe
Connect: configure platform publishable/secret/webhook keys and `stripe_connect_client_id`
in /control/ Platform Stripe Connect settings (or the superadmin
`/api/v1/admin/platform/payment-settings` API), then let the manager POST
`/api/v1/admin/makerspace/{makerspace_id}/payment-settings/connect/onboard` and open the
returned `{authorize_url}`. The callback is `/api/v1/payments/connect/callback`.
An active connected account with charges enabled is required. Connect is dormant on self-host;
Razorpay always uses the makerspace's own account, with no Connect fallback/application fee.

Install the opt-in `payments` module and enable `payments.enabled` and the relevant
`payments.loans|machines|bookings|events|membership` capability. Credentials must resolve too.
Recording a debt is separate: `charges.enabled` and the corresponding `charges.<domain>`
control it without a rail/module/credential requirement. Removing online payments leaves the
core ledger, manual settlement, history and receipts readable. Deployment tombstoning of
`payments_rail` removes checkout, native intents and webhook routes; tenant module/capability
toggles alone do not remove the callbacks for money already taken.

Configure these exact HTTPS webhook URLs in the provider dashboards (no trailing slash).
`public_code` is the makerspace's public code, not its database ID or slug:

| Rail | URL | Signature secret / verification |
| --- | --- | --- |
| Own Stripe | `/api/v1/webhooks/stripe/{public_code}` | That row's `stripe_webhook_secret`; verifies `Stripe-Signature` over raw request bytes. Use the endpoint's webhook signing secret, not the Stripe API secret key. |
| Managed Stripe Connect | `/api/v1/webhooks/stripe/connect` | Platform `stripe_webhook_secret`; same raw-body `Stripe-Signature` verification, scoped to the connected account. |
| Own Razorpay | `/api/v1/webhooks/razorpay/{public_code}` | That row's `razorpay_webhook_secret`; HMAC-SHA256 of raw body checked against `X-Razorpay-Signature`. This webhook secret is separate from `razorpay_key_secret`. Preserve `X-Razorpay-Event-Id` through proxies for deduplication. |

Stripe settlement handles `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
`checkout.session.expired`, `checkout.session.async_payment_failed`, `payment_intent.succeeded`
and `payment_intent.payment_failed`; refund handling accepts `charge.refunded`,
`charge.refund.updated`, `refund.created`, `refund.updated`, `refund.failed`.
Connect additionally handles `account.updated` and `account.application.deauthorized`.
Razorpay handles `payment_link.paid` for hosted checkout, `order.paid` / `payment.captured`
for native Orders, `payment.failed`, and refund state from refund entities (`refund.processed`
for successful refund callbacks). Subscribe to the events used by the rails you offer.
Valid events return 200 `{detail:"Verified."}` even when ignored; invalid configuration,
signature or payload returns 400; unknown/unservable tenants return 404. Signature checking
requires unchanged raw body bytes. Do not change providers or remove old webhook credentials
while collections are unsettled: Razorpay callbacks require the selected provider to remain
Razorpay. Switching provider is refused with 409 `payment_provider_conflict` while a pending
collection on the other vendor has an unexpired hosted checkout, native Order or PaymentIntent.
Settle or close those collections first. Uncollected ledger debts without online handles do not
block selection. Razorpay credential rotation/clearing is also refused while its collections
are pending; saved keys can be resubmitted unchanged.

The apps use an attested device bearer and matching `X-Makerspace-Id`, then POST with no body:
`/api/v1/member/makerspaces/{makerspace_id}/payments/{payment_id}/mobile-intent`.
Only a pending charge owned by the caller is eligible. Response dispatch is by `vendor`:

- Stripe: `{vendor:"stripe",payment_id,client_secret,publishable_key}`; optional nullable
  `customer_id` / `ephemeral_key` are declared in the schema but currently not returned.
  Configure the native PaymentSheet from these runtime values.
- Razorpay: `{vendor:"razorpay",payment_id,key_id,order_id,amount_minor,currency,name,description}`.
  Configure native Checkout with the key, Order ID and the integer minor-unit amount as returned.
  The server recovers/reuses a matching Order instead of creating a new one on every retry.

409 `payment_rail_conflict` means another online rail already owns the charge. A charge whose
hosted checkout page was created when the charge was raised is stamped `online_rail=checkout`, so
the native sheet answers 409 for it too: open that hosted `checkout_url` in the system browser (it
is on the member payment row) instead of the sheet. 503
`payments_unavailable` means the online rail is disabled, unconfigured or failed.
The SDK callback never settles the ledger. After completion/cancellation, refetch
GET `/api/v1/member/makerspaces/{makerspace_id}/payments` and locate the payment ID;
there is no member payment-detail endpoint. `paid_online` / `paid_offline` are settled,
`waived` / `canceled` are terminal, and a failed attempt can remain `pending`.

Test in a separate staging makerspace with no real debt or live credentials:

1. In Online payments settings, choose the provider and save matching test/sandbox keys and
   the test webhook endpoint's signing secret. Copy the displayed webhook URL to its dashboard.
   There is no `test_mode` request parameter or separate mobile test endpoint: mode comes
   from the provider credentials. Keep live and test keys/webhook secrets separate.
2. Enable the source domain and charge capabilities with the online rail initially off.
   Create a small charge through its real booking/event/membership/loan/service workflow;
   this leaves a pending debt without a hosted checkout. Then enable the payment module/rail
   capabilities and verify `online_payment_available:true` for the owning test member.
3. Sign in on an approved test native registration and request the mobile intent. Complete
   the SDK's sandbox flow. Verify delivery/signature acceptance in the provider webhook
   dashboard and the server's payment row becoming `paid_online` before calling it successful.
4. Exercise cancellation/failure (must not become paid), repeat the intent request (reuse),
   resend the same provider webhook (no duplicate settlement), and try a charge with a live
   hosted checkout (409). Also verify disabled/unconfigured rails return 503.
5. Check member history and payment documents, staff reconciliation and the audit trail.
   Switch to live credentials only after sandbox flows pass and pending test rails are closed.

Reconciliation lives in the staff payments console and GET
`/api/v1/admin/makerspace/{makerspace_id}/payments` (`VIEW_FINANCE`; receipt recording can
use `for_recording=true` with `RECORD_PAYMENT`). The report registry's
`payment-reconciliation` and ledger/cash-book reports retain currency partitions.
Desk settlement uses POST `.../payments/{payment_id}/mark-offline` with
`{settlement:{method,reference?,received_at}}` (received_at is an ISO datetime), and corrections
use `.../amend-settlement`;
waiver is `.../waive`. Online refunds use `.../refund` only with the rail installed;
offline refunds and deposit releases remain ledger operations. Inspect `payment.*` audits
for late captures. For `payment.double_paid_refund_required`, use the audited provider
payment ID to refund excess in the provider dashboard; do not overwrite the original charge.
Member documents use GET `.../payment-documents` and GET
`.../payment-documents/{document_id}/download-url` in their member makerspace scope.
The download grant is user-bound and expires after five minutes.
