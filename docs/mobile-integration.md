# Connect a branded native app

Use this guide for the deployment's Android and iOS apps. An approved registration must have
**Makerspace left blank**: tenant-scoped rows remain inert. Create a separate row for each platform
and environment. Development registrations never publish association files or a production minimum.

## Server values in /control/

Sign in to the superadmin control plane through your deployment's existing protected access path.
Do not enable a public control-plane proxy just to configure an app.

| Value | /control/ model and field | Meaning |
| --- | --- | --- |
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
