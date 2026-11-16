# Delivery, sign-in and rate-limit environment settings

Part of the [complete environment reference](environment-reference.md).

## Email, Telegram and outbound integrations

Platform SMTP, SMS, push and Stripe Connect credentials normally live encrypted in the database (`/control/` and the Platform settings panel); these variables are the deployment-level fallbacks.

| Variable | Default | Notes |
|---|---|---|
| `DEFAULT_FROM_EMAIL` | `'Makerspace <noreply@makerspace.local>'` | From address for platform mail when no other sender is configured. |
| `EMAIL_BACKEND` | `'django.core.mail.backends.console.EmailBackend'` | Must be the SMTP backend for `email_enabled()` to report on. The default only prints mail to the log. |
| `EMAIL_HOST` | `''` | Fallback SMTP server. |
| `EMAIL_HOST_PASSWORD` | `''` | Fallback SMTP password (secret). |
| `EMAIL_HOST_USER` | `''` | Fallback SMTP user. |
| `EMAIL_PORT` | `587` | Fallback SMTP port. |
| `EMAIL_USE_TLS` | `True` | Use STARTTLS for the fallback SMTP connection. |
| `GITHUB_API_TOKEN` | `''` | Optional; raises the GitHub rate limit for maker-profile contribution refresh and the hackathon first-commit flag. |
| `WEB_PUSH_VAPID_PRIVATE_KEY` | `''` | Secret. Base64url raw P-256 private scalar for browser notifications (W3C Web Push); the public key is derived. Blank = browser notifications dormant. Generate once per deployment and keep it: rotating it invalidates every browser subscription. |
| `HOSTING_REQUEST_RESUBMIT_ENABLED` | `True` | Managed platforms: applicants may edit and resubmit a hosting request after the superadmin asks for changes. `False` keeps "changes requested" one-way (the applicant reads the note only). |
| `PUBLIC_SPACE_REQUESTS_ENABLED` | `False` | Self-hosted installs: opens the public "request a makerspace or organization workspace" form and the /control/ review of those requests (managed platforms always have them). Needs platform email and `PUBLIC_APP_BASE_URL`. Off means the routes answer 404. |
| `WEB_PUSH_VAPID_SUBJECT` | `''` | `mailto:` or `https:` contact sent to push services with each browser notification. Required with the key. |
| `NOTIFICATION_SLACK_REDIRECT_URI` | `''` | Fixed HTTPS frontend notification-settings return, registered byte-for-byte in the provider app; blank refuses personal linking. No placeholders: the signed OAuth state carries the makerspace and challenge. |
| `NOTIFICATION_MATTERMOST_REDIRECT_URI` | `''` | Same frontend OAuth return policy as Slack. |
| `NOTIFICATION_DISCORD_REDIRECT_URI` | `''` | Same frontend OAuth return policy as Slack. |
| `NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS` | `False` | Only boolean true allows private self-hosted Mattermost addresses. |
| `OTP_SMS_DAILY_CAP` | `200` | Platform-wide daily cap on SMS sign-in codes. |
| `MANAGED_OTP_EMAIL_DAILY_LIMIT` | `200` | Managed mode: platform-wide daily cap on email sign-in codes. |
| `MANAGED_OTP_SMS_DAILY_LIMIT` | `100` | Managed mode: platform-wide daily cap on SMS sign-in codes, tightening `OTP_SMS_DAILY_CAP`. |
| `PUSH_TOKEN_HMAC_KEY` | `''` | Keys the device-token digest; push registration answers 503 while unset. |
| `STRIPE_CONNECT_REDIRECT_URI` | `''` | Return URL registered with Stripe for Connect onboarding. Blank refuses onboarding even when platform Connect credentials are set. |
| `TELEGRAM_API_URL` | `'https://api.telegram.org'` | Telegram Bot API base URL; change only for a proxy or mirror. |
| `TELEGRAM_BOT_TOKEN` | `''` | Fallback bot token used when none is saved in platform settings (secret). |
| `TELEGRAM_WEBHOOK_SECRET` | `''` | The webhook answers 403 while unset; callbacks are acknowledged and ignored. |
| `WHATSAPP_META_GRAPH_VERSION` | `'v25.0'` | Canonical Meta HTTP version. Twilio/Meta adapters and the whatsapp module are wired; sender/proof/template gates and the independent cutover activation hold still apply. |

These notification settings are loaded from the environment and forwarded by deployment manifests.
OAuth returns signed code/state; authenticated endpoints GET resolves `oauth_state` to the current
account's challenge, then the frontend posts to authenticated personal challenge verification.
Redirect URIs are fixed registered values, without dynamic challenge IDs or placeholders. Authorization and exchange must use the identical provider-registered URI.
See the [delivery contract](notification-contract.md#provider-connection-and-deployment) for setup.

## Sign-in: social, OIDC, native devices, member claims

| Variable | Default | Notes |
|---|---|---|
| `DEVICE_ANDROID_ATTESTATION_VERIFY_TOKEN` | `''` | Bearer token for the external Android (Play Integrity) attestation verifier (secret). |
| `DEVICE_ANDROID_ATTESTATION_VERIFY_URL` | `''` | External Android attestation verifier endpoint. Blank leaves the external verifier off. |
| `DEVICE_APPLE_ATTESTATION_VERIFY_TOKEN` | `''` | Bearer token for the external Apple (App Attest) verifier (secret). |
| `DEVICE_APPLE_ATTESTATION_VERIFY_URL` | `''` | External Apple attestation verifier endpoint. Blank leaves the external verifier off. |
| `DEVICE_ATTESTATION_APPS` | `{}` | Legacy fallback only for approved global native registrations whose signing list is empty; keys map to `signing_identity` and `environments`. New installations enter distribution digests / Apple App ID Prefix and minimum versions on registrations in `/control/`. A system warning lists empty eligible rows. See [mobile integration](mobile-integration.md). |
| `DEVICE_ATTESTATION_DEV_INSECURE` | `False` | Accept development attestation for development registrations only; requires `DEBUG=True`. External and configured in-process verifiers take priority. |
| `DEVICE_ATTESTATION_CHALLENGE_TTL_SECONDS` | `180` | Lifetime of a native-app attestation challenge. |
| `DEVICE_ATTESTATION_PROVIDER_TIMEOUT_SECONDS` | `10` | Time limit for a call to an attestation verifier. |
| `MEMBER_CLAIM_CODE_TTL_SECONDS` | `15 * 60` | Lifetime of a claim code that staff hand to a member in person. |
| `MEMBER_CLAIM_SESSION_TTL_SECONDS` | `12 * 60 * 60` | Absolute lifetime of the session a redeemed claim code starts. |
| `OIDC_ATTEMPT_TTL_SECONDS` | `300` | Lifetime of one browser OIDC or GitHub sign-in attempt (its state and nonce). |
| `OIDC_DISCOVERY_CACHE_SECONDS` | `300` | How long a provider's discovery document is cached. |
| `OIDC_HTTP_MAX_BYTES` | `65536` | Largest response accepted from an OIDC provider or GitHub. |
| `OIDC_HTTP_TIMEOUT_SECONDS` | `5` | Time limit for each call to an OIDC provider or GitHub. |
| `SOCIAL_APPLE_JWKS_URL` | `'https://appleid.apple.com/auth/keys'` | Apple's signing keys for Sign in with Apple tokens. |
| `SOCIAL_AUTH_CLOCK_SKEW_SECONDS` | `60` | Allowed clock difference when checking provider token times. |
| `SOCIAL_AUTH_JWKS_CACHE_SECONDS` | `3600` | How long provider signing keys are cached. |
| `SOCIAL_AUTH_JWKS_MAX_BYTES` | `1048576` | Largest signing-key document accepted. |
| `SOCIAL_AUTH_JWKS_TIMEOUT_SECONDS` | `5` | Time limit for fetching provider signing keys. |
| `SOCIAL_AUTH_NONCE_TTL_SECONDS` | `300` | Lifetime of a social sign-in nonce. |
| `SOCIAL_GOOGLE_JWKS_URL` | `'https://www.googleapis.com/oauth2/v3/certs'` | Google's signing keys for Google sign-in tokens. |

## Rate limits

Every `THROTTLE_*` value is a DRF rate string (`<n>/<second|minute|hour|day>`). Defaults are correct in production; raise one only with a reason.

| Variable | Default | Notes |
|---|---|---|
| `THROTTLE_ANONYMOUS_REQUEST_EMAIL` | `'5/hour'` | Borrower email-code sends per address (spaces without member accounts). |
| `THROTTLE_ANONYMOUS_REQUEST_IP_BURST` | `'5/min'` | Account-less borrow requests and code sends per IP. |
| `THROTTLE_ANONYMOUS_REQUEST_IP_HOUR` | `'30/hour'` | Account-less borrow requests and code sends per IP. |
| `THROTTLE_AUDIT_VERIFICATION` | `'6/hour'` | On-demand audit chain verification runs. |
| `THROTTLE_BOOKING_SUBMIT` | `'10/hour'` | Member booking submissions. |
| `THROTTLE_PAYMENT_CLAIMS` | `'5/hour'` | Member "I've paid" offline claims per account. |
| `THROTTLE_PAY_LINKS` | `'30/min'` | Public pay-link reads, claims and checkouts per IP. |
| `THROTTLE_PRICING_QUOTE` | `'60/min'` | Price previews (`POST /api/v1/pricing/quote`) per account, or per IP when signed out. |
| `THROTTLE_DATA_EXPORT_CREATE` | `'3/hour'` | New tenant or personal data-export jobs. |
| `THROTTLE_DEPLOYMENT_ANON` | `'600/min'` | Deployment-wide ceiling for signed-out requests to any route without its own rate limit, per verified API client or else per client IP. Signature-verified provider webhooks are exempt. |
| `THROTTLE_DEPLOYMENT_DEVICE` | `'600/min'` | Deployment-wide ceiling for signed device and adapter requests to routes without their own rate limit, per device (never per IP, so machines behind one address do not share it). |
| `THROTTLE_DEPLOYMENT_USER` | `'1200/min'` | Deployment-wide ceiling for signed-in requests to any route without its own rate limit, per account. |
| `THROTTLE_DEVICE_ATTESTATION_CHALLENGE` | `'5/min'` | Native-app attestation challenges. |
| `THROTTLE_DEVICE_LOGIN` | `'5/min'` | Native device sign-ins per IP. |
| `THROTTLE_DEVICE_LOGIN_USER` | `'10/hour'` | Native device sign-ins per username. |
| `THROTTLE_DEVICE_REFRESH` | `'30/min'` | Native device session refreshes. |
| `THROTTLE_EMAIL_VERIFICATION_CONFIRM` | `'10/min'` | Email verification code checks. |
| `THROTTLE_EMAIL_VERIFICATION_RESEND` | `'5/min'` | Email verification resends. |
| `THROTTLE_EVENT_CALENDAR_FEED_IP` | `'300/hour'` | Event and booking calendar (ICS) feed reads per IP. |
| `THROTTLE_EVENT_CALENDAR_FEED_TOKEN` | `'120/hour'` | Calendar feed reads per feed token. |
| `THROTTLE_EVENT_CHECKIN_RESOLVE` | `'60/min'` | Event check-in code lookups. |
| `THROTTLE_EVENT_OFFLINE_ROSTER` | `'10/hour'` | Offline check-in roster downloads. |
| `THROTTLE_EVENT_OFFLINE_SYNC` | `'60/hour'` | Offline check-in uploads. |
| `THROTTLE_EVENT_REGISTER` | `'10/hour'` | Event registrations. |
| `THROTTLE_EVENT_REGISTRATION_RETRY` | `'30/hour'` | Retries of a registration that can still be repaired. |
| `THROTTLE_EVENT_SHORT_LINK` | `'30/min'` | Event short-link (`/e/<code>`) lookups. |
| `THROTTLE_EVENT_STATION_PIN_IP` | `'30/hour'` | Event check-in station PIN attempts per IP. |
| `THROTTLE_EVENT_STATION_PIN_TOKEN` | `'10/hour'` | Event check-in station PIN attempts per station. |
| `THROTTLE_EVENT_STATION_REVEAL` | `'5/hour'` | Event check-in station PIN reveals. |
| `THROTTLE_EVENT_STATION_SESSION` | `'120/hour'` | Event check-in station session requests. |
| `THROTTLE_HOSTING_INVITATION_CREATE` | `'20/hour'` | Per staff user: hosting invitations created (managed platform only). |
| `THROTTLE_HOSTING_REQUEST_EMAIL` | `'3/day'` | Per applicant address: hosting-request submissions; overflow is silently dropped with the usual 202. |
| `THROTTLE_HOSTING_REQUEST_SUBMIT` | `'5/hour'` | Per client: public hosting-request and invitation-answer submissions. |
| `THROTTLE_HOSTING_REQUEST_TOKEN` | `'30/hour'` | Per client: hosting-request status and invitation-preview links. |
| `THROTTLE_KIOSK_OPERATOR_LEASE` | `'30/hour'` | Kiosk operator sign-in leases. |
| `THROTTLE_KIOSK_REPLAY_EXECUTE` | `'240/hour'` | Kiosk offline actions replayed. |
| `THROTTLE_KIOSK_REPLAY_PREPARE` | `'60/hour'` | Kiosk offline-action replays prepared. |
| `THROTTLE_KIOSK_STATION_PIN_IP` | `'30/hour'` | Kiosk station PIN attempts per IP. |
| `THROTTLE_HANDLE_CHECK` | `'20/min'` | Username availability checks (`GET /handles/check`), per account when signed in, otherwise per IP. |
| `THROTTLE_HANDLE_CHECK_DAILY` | `'300/day'` | Daily cap on the same username availability checks. |
| `THROTTLE_KIOSK_STATION_PIN_TOKEN` | `'10/hour'` | Kiosk station PIN attempts per station. Kiosk PIN reveals are fixed at 5/hour and have no setting. |
| `THROTTLE_KIOSK_STATION_SESSION` | `'120/hour'` | Kiosk station session requests. |
| `THROTTLE_LOGIN` | `'10/min'` | Password sign-ins; the django-axes lockout applies on top. |
| `THROTTLE_MEMBERSHIP_REQUEST` | `'10/hour'` | Membership applications. |
| `THROTTLE_MEMBER_CLAIM_ISSUE` | `'10/hour'` | Claim codes issued by staff. |
| `THROTTLE_MEMBER_CLAIM_REDEEM` | `'10/min'` | Claim code redemptions. |
| `THROTTLE_MEMBER_IMAGE_PRESIGN` | `'20/hour'` | Member avatar and project-image upload slots. |
| `THROTTLE_MEMBER_SIGN_UP` | `'5/min'` | Member self-registrations. |
| `THROTTLE_MEMBER_VERIFICATION_EMAIL` | `'5/hour'` | Verification emails per address. |
| `THROTTLE_PASSWORD_RESET_CONFIRM` | `'10/min'` | Password-reset and account-restore confirmations. |
| `THROTTLE_PASSWORD_RESET_CONFIRM_EMAIL` | `'15/hour'` | Password-reset confirmations per email address. |
| `THROTTLE_PASSWORD_RESET_EMAIL` | `'5/hour'` | Password-reset emails per address. |
| `THROTTLE_PASSWORD_RESET_REQUEST` | `'5/min'` | Password-reset requests. |
| `THROTTLE_PHONE_CONFIRM_NUMBER` | `'15/hour'` | Phone code checks per number. |
| `THROTTLE_PHONE_LOGIN_CONFIRM` | `'10/min'` | Phone sign-in code checks per IP. |
| `THROTTLE_PHONE_OTP_NUMBER` | `'5/hour'` | SMS codes sent per number. |
| `THROTTLE_PHONE_OTP_REQUEST` | `'5/min'` | SMS code requests per IP. |
| `THROTTLE_PRESENCE_START` | `'10/hour'` | Presence check-ins started. |
| `THROTTLE_PRINT_REQUEST_SUBMIT` | `'10/min'` | Print and machine-service job submissions. |
| `THROTTLE_PROFILE_LOOKUP` | `'30/min'` | Signed-in profile reads by account id (`/profiles/by-account/<id>/`) or by handle, per account. Signed-out handle reads use `THROTTLE_PUBLIC_READ`. |
| `THROTTLE_PROFILE_LOOKUP_DAILY` | `'500/day'` | Daily cap on the same signed-in profile reads, per account. |
| `THROTTLE_PUBLIC_INVITATION_REQUEST` | `'10/hour'` | Public requests for an invitation to a space. |
| `THROTTLE_PUBLIC_READ` | `'120/min'` | Public booking and event reads, and member booking lists. |
| `THROTTLE_PUBLIC_REQUEST_SUBMIT` | `'10/min'` | Borrow-request submissions and inventory watch changes. |
| `THROTTLE_PUBLIC_STATS` | `'30/min'` | Public statistics reads. |
| `THROTTLE_PUBLIC_TOOL_CHECKOUT` | `'10/min'` | Self-checkout and kit checkouts. |
| `THROTTLE_PUBLIC_TOOL_RETURN` | `'10/min'` | Self-checkout returns. |
| `THROTTLE_PUSH_DEVICE_REGISTRATION` | `'10/min'` | Push token registrations. |
| `THROTTLE_REQUEST_STATUS` | `'60/min'` | Borrow-request and machine-job status reads. |
| `THROTTLE_REQUEST_SUBMIT` | `'10/min'` | Read, but no view uses this scope today; borrow submissions use `THROTTLE_PUBLIC_REQUEST_SUBMIT`. |
| `THROTTLE_SOCIAL_LINK` | `'10/hour'` | Native provider linking only. |
| `THROTTLE_SOCIAL_LOGIN` | `'10/min'` | Social, GitHub and OIDC sign-in completions. |
| `THROTTLE_SOCIAL_NONCE` | `'10/min'` | Social, GitHub and OIDC sign-in starts. |
| `THROTTLE_TELEGRAM_WEBHOOK` | `'60/min'` | Telegram webhook calls. |
| `THROTTLE_ANTHIAS_PLAYER_CALL` | `'20/min'` | Anthias player test and sync calls, per account. |
| `THROTTLE_IMAGE_ADAPTER_TEST` | `'10/min'` | Image-adapter provider test calls, per account. |
| `THROTTLE_DEVICE_ADAPTER` | `'300/min'` | Signed device-adapter calls, per device. |
| `THROTTLE_DEVICE_ADAPTER_CREDENTIAL` | `'60/min'` | Adapter credential (NFC/PIN) checks, per device. |
| `THROTTLE_ADAPTER_WATCH_START` | `'10/min'` | Opening a camera watch, per account. |
| `THROTTLE_ADAPTER_WATCH_RELAY` | `'300/min'` | Camera watch signalling and talk relay, per account. |
| `THROTTLE_TENANT_MIGRATION_READ` | `'120/min'` | Tenant-migration reads. |
| `THROTTLE_TENANT_MIGRATION_WRITE` | `'30/hour'` | Tenant-migration changes. |
| `THROTTLE_TENANT_MIGRATION_UPLOAD` | `'1200/min'` | Resumable tenant-archive chunks (up to 8 MiB per request). |
| `THROTTLE_MFA_VERIFY` | `'10/min'` | Per-IP second-factor/enrollment budget; also controls control-panel verification. |
| `THROTTLE_MFA_CHALLENGE` | `'10/min'` | Budget for one challenge token. |
| `THROTTLE_MFA_USER` | `'20/hour'` | Account budget across challenges and IPs. |
| `THROTTLE_MFA_MANAGE` | `'10/hour'` | Authenticated enrollment and recovery/disable management. |
| `THROTTLE_STAFF_INVITE` | `'20/hour'` | Scoped staff invitation list/create/revoke/resend. |
| `THROTTLE_STAFF_INVITE_ACCEPT` | `'10/min'` | Public invitation acceptance budget. |
| `THROTTLE_CARD_VERIFY` | `'30/min'` | Public card checks (`/api/v1/public/card-verifications/<token>`) per IP. |
| `THROTTLE_MEMBER_CARD_RESOLVE` | `'60/min'` | Staff member-card scans at the desk, per account. |
| `THROTTLE_ID_JOIN` | `'10/min'` | ID-programme join requests and invite acceptances per account. |
| `THROTTLE_ID_JOIN_UPLOAD` | `'12/hour'` | ID-programme join photo uploads per account. |

## ID cards: card fonts, photo clean-up and wallet passes

The card font library is the open Google Fonts catalogue, fetched **by the server** on first use and served by this app; browsers never call Google. Wallet-pass credentials are platform-level (one Apple Pass Type ID, one Google Wallet issuer); the buttons stay hidden until set. Key and certificate values are FILE paths to secrets mounted into the container.

| Variable | Default | Notes |
|---|---|---|
| `CARD_FONT_DOWNLOADS_ENABLED` | `True` | `False` keeps cards to the bundled faces (the "Gilroy" token as Outfit, Unbounded, Noto) on air-gapped servers. |
| `CARD_FONT_SOURCE_URL` | `'https://fonts.googleapis.com/css2'` | CSS endpoint the server asks for static TrueType faces; point it at a mirror if you run one. |
| `CARD_FONT_CACHE_DIR` | `''` | Local cache for fetched font files; empty uses the system temp directory. |
| `CERTIFICATE_SHARED_RENDERER` | `False` | Event certificates: `True` lets issuance pin `renderer: "shared"` so the server-side renderer draws the same plan as the browser studio; `False` keeps the legacy renderer. |
| `CARD_PHOTO_MODEL_PATH` | `''` | The background clean-up model (`manage.py fetch_card_photo_model`); empty uses the temp directory. |
| `WALLET_APPLE_PASS_TYPE_ID` | `''` | Apple Pass Type ID (e.g. `pass.org.example.cards`). |
| `WALLET_APPLE_TEAM_ID` | `''` | Apple developer team id. |
| `WALLET_APPLE_CERT_FILE` | `''` | Path to the Pass Type ID certificate (PEM). |
| `WALLET_APPLE_KEY_FILE` | `''` | Path to its private key (unencrypted PEM, mounted as a secret file). |
| `WALLET_APPLE_WWDR_FILE` | `''` | Path to Apple's WWDR intermediate certificate (PEM). |
| `WALLET_GOOGLE_ISSUER_ID` | `''` | Google Wallet issuer id. |
| `WALLET_GOOGLE_SERVICE_ACCOUNT_FILE` | `''` | Path to the Wallet API service-account JSON key. |

## Device adapters

Optional knobs for the device adapter API. They apply only where `machines.integrations` is on, and every default suits
most installs.

| Variable | Default | Notes |
|---|---|---|
| `ADAPTER_CACHE_KEY_VERSION` | `1` | Version of the Ed25519 key that signs offline access lists and signed time. The key pair is derived from `SECRET_KEY`. Raise it to rotate; adapters learn the public keys from `hello`. |
| `ADAPTER_CACHE_KEY_ROTATED_AT` | `0` | Epoch seconds of the last rotation. For the grace period after it, the previous key is still listed as `previous`. |
| `ADAPTER_CACHE_KEY_GRACE_DAYS` | `7` | How long the previous key stays listed after a rotation. |
| `ADAPTER_ACCESS_CACHE_TTL_SECONDS` | `900` | Life of an offline access list (a binding can set its own, 60 to 86400 seconds). |
| `ADAPTER_ARTIFACT_RETENTION_DAYS` | `{}` | JSON object of artifact kind to days, overriding the defaults: thumbnail and preview 90, failure snapshot and timelapse 30, log bundle 7, audio recording 3. `docker-compose.prod.yml` does not pass this one (a `{}` default cannot be written there); add it to the backend `environment:` block if you need it. |
| `ADAPTER_TELEMETRY_RAW_HOURS` | `24` | How long raw telemetry samples are kept. |
| `ADAPTER_TELEMETRY_MINUTE_DAYS` | `7` | How long one-minute summaries are kept. |
| `ADAPTER_TELEMETRY_QUARTER_DAYS` | `90` | How long fifteen-minute summaries are kept. |
| `ADAPTER_TURN_URLS` | empty | Comma-separated TURN server URLs handed to camera watch sessions. TURN is used only when this and the secret are both set. |
| `ADAPTER_TURN_SECRET` | empty | Shared secret used to make short-lived TURN credentials. Keep it secret; empty means TURN is off. |

The background eraser address and secret are not variables: they are entered in the app
([Remove card photo backgrounds](how-to/background-eraser.md)).
