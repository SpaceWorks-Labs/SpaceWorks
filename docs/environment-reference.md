# Environment reference

Every environment variable the backend reads, grouped by area. The complete list spans
this page, [delivery, sign-in and rate limits](environment-reference-delivery.md),
and [operations](environment-operations.md). Compose-only host settings and the frontend's
build and container settings are at the end of this page. The local drift test
`backend/tests/test_environment_reference_drift.py` (test suites are kept out of the
repository) fails when a name in `apps/backup/settings_policy.ENV_SURFACE` (itself pinned
to what the code reads) is missing here. The env examples (`.env.example`, `.env.production.example`, `backend/.env.example`)
deliberately carry only what a deployment must decide; everything else has a default that
is correct off-box, shown below. Installer/Compose-only rows are classified separately
in `apps/backup/settings_policy.HOST_ONLY_POLICIES`: they are excluded from backend
restore compatibility and checked through the host topology record instead.

Defaults are the expressions in `backend/config/settings.py`; "read outside `settings.py`"
means a command, script or app module reads it directly (setup, build, host orchestration).

WP3 quiet hours, digest times and bounce signing credentials are tenant settings,
not environment variables. Booking ICS uses the existing
`THROTTLE_EVENT_CALENDAR_FEED_TOKEN` (120/hour) and `THROTTLE_EVENT_CALENDAR_FEED_IP`
(300/hour) budgets with separate booking cache keys; see the delivery reference.

## Core Django and hosting

Read by every backend process. `ALLOWED_HOSTS`, `SECRET_KEY` and the proxy posture must be set for any off-box deployment.

| Variable | Default | Notes |
|---|---|---|
| `ADMIN_SITE_NAME` | `'Space Works'` | Site name shown in the `/control/` admin. |
| `ACCOUNT_DELETION_RETENTION_DAYS` | `90` | Days between the account deletion request and scheduled identity purge; Stage A immediately deactivates the account. |
| `ACCOUNT_UNIFICATION_ACK` | empty | Release-2 upgrade only: the `plan_sha256` printed by `manage.py account_unification_report` after you reviewed it. The one-account-per-person migration refuses to convert existing staff accounts until this matches; leave it empty on fresh installs and once migrated. |
| `ALLOWED_HOSTS` | `['localhost', '127.0.0.1']` | Django's host check; add every custom domain on self-host. |
| `CORS_ALLOWED_ORIGINS` | `['http://localhost:5000', 'http://localhost:5173']` | Browser origins allowed to call the API. Set to your website origins in production. |
| `CSRF_TRUSTED_ORIGINS` | `[]` | `https://` origins trusted for Django form posts such as the `/control/` login. Needed in production behind HTTPS. |
| `DEBUG` | `False` | Must stay false off-box; it also selects JSON logs and several defaults. |
| `DJANGO_SETTINGS_MODULE` | `config.settings` | Set by `manage.py`, the WSGI/ASGI entry points and Celery. Do not change it. |
| `INFRA_HOSTS` | `['localhost', '127.0.0.1', 'backend', 'backend:8000']` | Container hostnames recognised as infrastructure callers by the managed host gate. |
| `LOG_JSON` | `not DEBUG` | One JSON object per log line; each line carries the request's `X-Request-ID`. |
| `LOG_LEVEL` | `'INFO'` | Python log level for the backend. |
| `PUBLIC_APP_BASE_URL` | `''` | Browser origin used in emailed links. Blank falls back to localhost, which is unclickable for real users. Personal optional mail emits RFC 8058 one-click headers only with an HTTPS origin whose `/api/v1` path reaches the backend. |
| `SECRET_KEY` | none | Required; the backend does not start without it. Rotating it invalidates sessions and signed tokens. |
| `SPACEWORKS_EDITION` | `'makerspace'` | What this box is for: `makerspace`, `events`, `bookings` or `organization`. An edition hides the public routes of modules it does not use; any other value refuses to start. |
| `TOMBSTONED_APPS` | empty (read outside `settings.py`) | Comma-separated separable apps to remove from this deployment. |

## Production release deployment

Automatic deploys use an optional Linux/systemd GitHub Actions runner. Register it with
`bash scripts/install-runner.sh`; set the GitHub repository variable `SPACEWORKS_DEPLOY=true` only after
applying the [required security settings](self-hosting.md#security). This variable belongs in GitHub,
not the application `.env`. The runner `.env` contains `SPACEWORKS_DIR` for the installed updater.
`SPACEWORKS_RUNNER_DIR` optionally selects its directory (default `/opt/spaceworks-runner`) when invoking
the helper. Manual updates use `bash scripts/update.sh --force`, optionally with `--version` for an exact
published main release. Forks configure their own repository, releases, runner and deploy variable.

| Variable | Default | Notes |
| --- | --- | --- |
| `SPACEWORKS_REPOSITORY` | `SpaceWorks-Labs/SpaceWorks` | Strict GitHub `owner/repo`; installer source, release lookup and runner registration URL. Persisted in `.env`. The lower-cased owner supplies default GHCR backend/frontend image namespaces unless `MAKERSPACE_BACKEND_IMAGE` / `MAKERSPACE_FRONTEND_IMAGE` override them. An install that still saves the old `SpaceWorks-HQ/*` repository or `ghcr.io/spaceworks-hq/*` images is switched to `SpaceWorks-Labs` / `ghcr.io/spaceworks-labs` automatically by the updater, installer re-run and compose wrapper (owner decision #107); forks are untouched. |

## TLS, cookies and proxies

TLS hardening is gated on `ENABLE_HTTPS`, never on `DEBUG`. Internal plain-HTTP probes (`/api/v1/health/`, `/api/v1/internal/`, `/api/v1/metrics/`) are exempt from the HTTPS redirect (`SECURE_REDIRECT_EXEMPT`).

| Variable | Default | Notes |
|---|---|---|
| `AUTH_COOKIE_SAMESITE` | `'None'` | SameSite attribute of the refresh-token cookie. `None` suits a website on a separate origin; local development through the same-origin proxy can use `Lax`. |
| `AUTH_COOKIE_SECURE` | `True` | Secure flag on the refresh-token cookie. Browsers drop a `SameSite=None` cookie without it. |
| `AXES_ENABLED` | `True` | django-axes lockout on password sign-in (API and `/control/`), keyed on address plus username. |
| `AXES_FAILURE_LIMIT` | `5` | Failed password sign-ins from one address for one username before a one-hour lockout. |
| `BEHIND_TRUSTED_PROXY` | `False` | Lets the managed host middleware be the host boundary (`ALLOWED_HOSTS=['*']`). |
| `CSRF_COOKIE_SECURE` | `ENABLE_HTTPS` | Secure flag on Django's CSRF cookie. |
| `ENABLE_HTTPS` | `False` | Turns on the HTTPS redirect, Secure cookies and HSTS (1 year, includeSubDomains, preload). |
| `SECURE_HSTS_SECONDS` | `31536000 if ENABLE_HTTPS else 0` | Start at 0 or small while verifying domains. |
| `SECURE_SSL_REDIRECT` | `ENABLE_HTTPS` | Redirect plain-HTTP requests to HTTPS (internal probes exempt). |
| `SESSION_COOKIE_SECURE` | `ENABLE_HTTPS` | Secure flag on the Django session cookie used by `/control/`. |
| `TRUSTED_PROXY_COUNT` | unset (`0` when `DEBUG=True`) | Proxies in front of the backend. Required in production: with `DEBUG` off the backend refuses to start until it is set, and a negative value also refuses. Use `0` for direct access. Throttles, django-axes and the automatic IP block all key on the real client IP only when this is right: too high and a client can spoof its address, too low and every client looks like the proxy. A request whose `X-Forwarded-For` chain is shorter than this is never counted towards an automatic block (logged once as `security.proxy_count_exceeds_hops`); `BEHIND_TRUSTED_PROXY=True` with `0` here is warned at startup (`accounts.W002`). |
| `TRUST_X_FORWARDED_PROTO` | `False` | Trust the proxy's `X-Forwarded-Proto`; only behind a TLS proxy that is the sole path in. |

## Managed SaaS mode

Every managed feature is dormant while `PLATFORM_DOMAIN_SUFFIX` is blank (self-host). See `docs/deploy-saas.md`.

| Variable | Default | Notes |
|---|---|---|
| `DOMAIN_CHANGE_COOLDOWN_SECONDS` | `0` | Managed mode: wait between custom-domain changes. |
| `PLATFORM_ADMIN_SSO` | `False` | Declares a password-free route into `/control/`. None exists today, so leave it false; it keeps the platform password login available. |
| `PLATFORM_DOMAIN_SUFFIX` | `''` | Blank = self-host. Non-blank activates managed mode and fair-use limits. |
| `PLATFORM_ORIGIN_HOST` | `''` | Managed mode: host a tenant's custom domain must resolve to (by CNAME) before it is verified. Blank skips the resolution check. |
| `PLATFORM_STAFF_ORIGINS` | `[]` | Exact platform-console origins allowed for platform API password login; tenant staff login supplies its makerspace slug and must match a verified custom origin. Member provider switches do not disable staff/platform passwords. |
| `PLATFORM_SUBDOMAIN_AUTO_TLS` | `False` | Guided platforms enable TLS admission for registered, verified, non-archived tenant subdomains. Unknown/pending/archived domains remain denied. Compared during restore preflight without blocking a target's TLS choice. |
| `MANAGED_PLANS_ENABLED` | `False` | Managed hosting limiter (#187A), **off by default**: superadmin plan tiers, a plan per space, trials, recorded hosting billing and its optional non-payment enforcement. Also needs a managed deployment (`PLATFORM_DOMAIN_SUFFIX`). Off = nothing visible or enforced; self-host is unchanged. |
| `MANAGED_BILLING_ONLINE_ENABLED` | `False` | Second switch, also off: lets a Space Manager pay a hosting invoice online through the platform's own Stripe/Razorpay account (keys are set encrypted in the superadmin console). Never charges without the payer opening the checkout. Meaningless unless `MANAGED_PLANS_ENABLED` is on. |
| `PERSON_CREDENTIAL_RATE_PER_MINUTE` | `120` | Requests per minute per personal access token or OAuth app connection (#196). |
| `OAUTH_OIDC_RSA_PRIVATE_KEY` | empty | PEM RSA key that signs OpenID Connect ID tokens for app connections (secret-bearing; `
` escapes allowed). Empty = OAuth 2.0 only, no ID tokens. |
| `OAUTH_ACCESS_TOKEN_SECONDS` | `3600` | Lifetime of an app connection's access token. |
| `OAUTH_REFRESH_TOKEN_SECONDS` | `2592000` | Lifetime of an app connection's refresh token (30 days; rotated on every use). |
| `THROTTLE_PERSON_TOKEN_MANAGE` | `30/hour` | Rate for creating and revoking personal access tokens. |
| `THROTTLE_OAUTH_CONSENT` | `30/hour` | Rate for granting app-connection consent. |
| `THROTTLE_API_CLIENT_MANAGE` | `120/hour` | Rate for creating, rotating and revoking API clients in the console. |

## Database

| Variable | Default | Notes |
|---|---|---|
| `CONN_HEALTH_CHECKS` | `True` | Check a persistent connection before reuse, so a restarted Postgres does not surface as a request error. |
| `CONN_MAX_AGE` | `60` | Persistent connection lifetime in seconds. Use direct/session transport; transaction pooling is unsupported. |
| `DATABASE_URL` | read outside `settings.py` | Supplied by the atomic ops pointer under Compose; never put it in a static `.env`. |
| `DISABLE_SERVER_SIDE_CURSORS` | `False` | Turn off server-side cursors. Keep the direct/session cursor policy; transaction pooling is unsupported. |
| `MANAGED_POSTGRES` | `False` | True on hosts that forbid `session_replication_role` (Supabase, RDS). |
| `SPACEWORKS_GRANTS_ONLY` | unset (read outside `settings.py`) | Host orchestration bootstrap: `1` only applies the runtime role's database grants and stops. Not set by hand. |
| `SPACEWORKS_GRANT_DATABASE_NAME` | empty (read outside `settings.py`) | Host orchestration bootstrap: database the runtime grants apply to. Not set by hand. |
| `SPACEWORKS_RUNTIME_DATABASE_URL` | read outside `settings.py` | Least-privilege runtime database URL used by the host orchestration scripts, the container entrypoint and analytics login sync; the bootstrap refuses to run without it. Compose derives it from `POSTGRES_APP_USER` and `POSTGRES_APP_PASSWORD`. |

## Cache, Celery, scheduler and live updates

Redis backs the cache (rate limits, nonces, verified hosts), the Celery broker and the SSE stream. Without a broker, tasks run eagerly and the live stream answers 503.

| Variable | Default | Notes |
|---|---|---|
| `CACHE_URL` | `''` | Redis URL for the cache. Blank uses `CELERY_BROKER_URL`; if that is blank too, Django's database cache (never a per-process cache, so rate limits hold across workers). |
| `CELERY_BROKER_URL` | `''` | Redis broker for Celery. Blank makes tasks run eagerly (inline); the setting then falls back to `redis://redis:6379/0`, which is not used for dispatch. |
| `CELERY_RESULT_BACKEND` | `''` | Celery result store; blank stores no results. |
| `CELERY_TASK_ALWAYS_EAGER` | `True` when `CELERY_BROKER_URL` is blank, else `False` | Run Celery tasks inline instead of on a worker. |
| `REMINDER_SWEEP_BATCH_SIZE` | `200` | Positive subject/claim batch per source and makerspace; shared reminders run every five minutes. Also bounds each inbox/delivery retention batch, including platform email logs (90 days read/sent/skipped, 365 failed; unread/in-flight kept). |
| `CRON_SECRET` | `''` | Enables `POST /api/v1/internal/cron/return-reminders`; 404 while unset. |
| `LIVE_MAX_STREAM_SECONDS` | `3600` | Longest a single live-update stream stays open before the browser reconnects. |
| `LIVE_REDIS_URL` | `''` | Defaults to the Celery broker; empty or unparseable makes `/api/v1/live/` answer 503 and the console polls. |
| `SPACEWORKS_SCHEDULER_CONTROL_PLANE_DISABLEMENT` | empty (read outside `settings.py`) | `external` scheduler only: how the external scheduler is switched off during restore. It or the host gate command must be set. |
| `SPACEWORKS_SCHEDULER_HOST_GATE_COMMAND` | empty (read outside `settings.py`) | `external` scheduler only: host command that fences the external scheduler during restore. |
| `SPACEWORKS_SCHEDULER_MODE` | empty (read outside `settings.py`) | `image` (the bundled Celery beat) or `external`. The host orchestration bootstrap refuses an empty or unknown value; the production Compose file sets `image`. |
| `SPACEWORKS_SCHEDULER_SERVICES` | empty (read outside `settings.py`) | `image` mode: comma-separated scheduler services, for example `beat` (set by the production Compose file). Must not be empty in that mode. |

## Observability

| Variable | Default | Notes |
|---|---|---|
| `METRICS_TOKEN` | `''` | Bearer token for `GET /api/v1/metrics/`; 404 while unset. |
| `SENTRY_DSN` | `''` | Opt-in error tracking; the SDK is imported only when set; PII is never sent. |
| `SENTRY_ENVIRONMENT` | `'production' if not DEBUG else 'development'` | Environment label attached to Sentry events. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Share of requests sent as performance traces (0 to 1). |

## Object storage

`AWS_S3_ENDPOINT_URL` is what the backend talks to; `AWS_S3_PUBLIC_ENDPOINT_URL` is what browsers see inside presigned URLs.

| Variable | Default | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | `''` | Object-storage access key. Required in production; bundled Compose passes `MINIO_ROOT_USER`. |
| `AWS_S3_ENDPOINT_URL` | `'http://localhost:9000'` | Endpoint the backend uses; Compose sets `http://minio:9000`. |
| `AWS_S3_PUBLIC_ENDPOINT_URL` | `AWS_S3_ENDPOINT_URL` | Must be browser-reachable; on-box default only works on the server itself. |
| `AWS_S3_REGION_NAME` | `'us-east-1'` | Storage region used for signing. |
| `AWS_SECRET_ACCESS_KEY` | `''` | Object-storage secret key. Required in production; bundled Compose passes `MINIO_ROOT_PASSWORD`. |
| `AWS_STORAGE_BUCKET_NAME` | `'evidence'` | Private bucket for evidence and other private files. Must differ from `PUBLIC_IMAGE_BUCKET`. |
| `PUBLIC_IMAGE_BASE_URL` | `''` | Public base URL of `PUBLIC_IMAGE_BUCKET`. |
| `PUBLIC_IMAGE_BUCKET` | `'public-images'` | Anonymous-read bucket for public item photos and space logos and covers. |
| `PUBLIC_IMAGE_MAX_BYTES` | `10485760` | Largest public image upload, in bytes. |
| `PUBLIC_IMAGE_URL_TTL_SECONDS` | `300` | Lifetime of a presigned public-image upload URL. |
| `STORAGE_PRESIGN_METHOD` | `'post'` | `post` (MinIO) or `put` (R2, Supabase Storage). |

## Upload limits and evidence retention

Personal subject exports reuse the tenant export limits and private bucket above;
this feature introduces no new environment variables. Signed links use the browser
storage endpoint and expire no later than the archive retention boundary.

| Variable | Default | Notes |
| --- | --- | --- |
| `DATA_EXPORT_DEADLINE_SECONDS` | `900` | Maximum worker build time for tenant and personal exports. |
| `DATA_EXPORT_PAGE_SIZE` | `500` | Database iterator batch size for export rows. |
| `DATA_EXPORT_RETENTION_SECONDS` | `604800` | Archive retention (seven days), including personal ZIPs. |
| `DATA_EXPORT_DOWNLOAD_TTL_SECONDS` | `300` | Maximum personal signed-link lifetime (five minutes). |

| Variable | Default | Notes |
|---|---|---|
| `EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED` | `False` | Deployment switch for deleting upload slots no workflow consumed; each makerspace must also opt in. |
| `EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS` | `7` | Default age before an unconsumed upload slot is eligible. |
| `EVIDENCE_MAX_BYTES` | `10485760` | Largest evidence photo upload, in bytes. |
| `EVIDENCE_OBJECT_EXPIRY_ENABLED` | `False` | Delete evidence photo bytes after the retention window. Photo rows, remarks and audit history are kept. |
| `EVIDENCE_OBJECT_RETENTION_DAYS` | `365` | Days evidence bytes are kept when expiry is on. |
| `EVIDENCE_RETENTION_BATCH_SIZE` | `100` | Rows handled per evidence expiry or abandoned-upload cleanup batch. |
| `EVIDENCE_URL_TTL_SECONDS` | `300` | Lifetime of presigned URLs for private objects (evidence, certificates, feedback files, card assets). |
| `MACHINE_DOC_ALLOWED_EXT` | `['pdf', 'jpg', 'jpeg', 'png', 'webp', 'stl', '3mf', 'step...` | File extensions accepted for machine documents. |
| `MACHINE_DOC_ALLOWED_MIME` | `['application/pdf', 'image/jpeg', 'image/png', 'image/web...` | MIME types accepted for machine documents. |
| `MACHINE_DOC_MAX_BYTES` | `10485760` | Largest machine document upload, in bytes. |
| `PRINT_ALLOWED_MODEL_EXT` | `['stl', '3mf', 'step', 'stp', 'obj', 'amf', 'ply', 'gcode...` | File extensions accepted for print and machine-job model files. |
| `PRINT_ALLOWED_MODEL_MIME` | `['application/octet-stream', 'model/stl', 'application/sl...` | MIME types accepted for print and machine-job model files. |
| `PRINT_UPLOAD_MAX_BYTES` | `104857600` | Largest print model upload, in bytes (100 MiB). |
| `PROCUREMENT_RECEIPT_ALLOWED_MIME` | `['application/pdf', 'image/jpeg', 'image/png', 'image/webp']` | MIME types accepted for procurement receipts. |
| `PROCUREMENT_RECEIPT_MAX_BYTES` | `10485760` | Largest procurement receipt upload, in bytes. |
| `REPORT_DELIVERY_URL_TTL_SECONDS` | `6 * 60 * 60` | Lifetime of the signed download link in a scheduled report email (six hours). |
| `WARRANTY_DOC_ALLOWED_MIME` | `['application/pdf', 'image/jpeg', 'image/png', 'image/webp']` | MIME types accepted for warranty documents. |
| `WARRANTY_DOC_MAX_BYTES` | `10485760` | Largest warranty document upload, in bytes. |

## Events programme and account Saved details

Read by `backend/config/settings.py` at checkpoint `f1ef7736`. **Keep programme features
and Saved details off until [integration acceptance](events/integration-status.md).**
These are independent deployment secrets/settings, not extra module keys.

| Variable | Default | Notes |
| --- | --- | --- |
| `ACCOUNT_SAVED_DETAILS_ENABLED` | `False` | Enables configured owner vault/key readiness. No host membership required; missing/unhealthy account broker fails closed. Does not enable tenant PII or any Events feature. |
| `ACCOUNT_PII_KEY_BROKER` | `'local'` | `local` or `aws_kms`; independent account wrapping broker, never a tenant-key or SECRET_KEY fallback. |
| `ACCOUNT_PII_MASTER_KEY` | `''` | Local account wrapping key in Fernet format (URL-safe base64 of 32 bytes). Required for local readiness; secret, retain with deployment backup custody. |
| `ACCOUNT_PII_MASTER_KEY_PREVIOUS` | `''` | Previous local account wrapping key for transition/read compatibility; not permission to discard keys still needed by retained ciphertext. |
| `ACCOUNT_PII_AWS_KMS_KEY_ID` | `''` | Account KMS wrapping key identifier; AWS broker uses account/version-specific encryption context and bounded calls outside transactions. IAM credentials use the normal SDK chain. |
| `ACCOUNT_SAVED_ASSET_BUDGET_BYTES` | `50 * 1024**2` | Default 50 MiB account résumé pool. Managed mode stays at 50 MiB; self-host may raise it, never below that floor. File cap remains 10 MiB. Separate from event storage. |
| `ACCOUNT_SAVED_RESUME_SCAN_REQUIRED` | `False` | When true, every saved PDF must pass the configured callback; missing/error fails closed. Separate from B's event scanner runtime options. |
| `ACCOUNT_SAVED_RESUME_SCANNER` | `''` | Dotted import path to a core callable `(bytes) -> 'clean'`. Blank/broken while required refuses. No production callback is installed here; do not point core Accounts at separable Events. |
| `EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY` | `''` | Independent standard-base64 32-byte HMAC key for event-bound v2 lookup. Changing it requires coordinated invalidation/reissue, not an unnoticed rotation. |
| `EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION` | `1` | Current integer keyring version; its string form must exist in the JSON map below. |
| `EVENT_REGISTRATION_CREDENTIAL_KEYS` | `{}` | JSON object mapping string versions to standard-base64 32-byte AES-GCM keys. Keep old versions needed by stored credentials. Empty configuration refuses v2; no Django/PII-key fallback. |

The shared Compose application anchors forward these eleven settings to all relevant
web/migration/worker/scheduler processes. Secrets remain operator-owned; upgrades must
retain current/previous wrapping keys and credential digest/keyring values. Tenant dumps
exclude the global vault and live credentials. Real install/upgrade continuity is still
an acceptance check.

Event budgets, lower file/group caps and retention anchors are domain policy.
All eleven settings above are forwarded through each Compose application environment
anchor, including migration/worker/beat processes, without generating or rotating keys.

| Setting | Default | Purpose |
| --- | --- | --- |
| `EVENT_ASSET_SCAN_BACKEND` | `'none'` | `none` or `clamav`; optional event-asset scanner; configured failures refuse publication. |
| `EVENT_ASSET_CLAMAV_HOST` | `''` | Explicit external ClamAV endpoint; no silent host inference. |
| `EVENT_ASSET_CLAMAV_PORT` | `3310` | Scanner TCP port. |
| `UI_DELIGHT_ENABLED` | `True` | Deployment kill switch for frontend artwork/motion. On by default; each space can still turn `ui.delight` off, and a reduced-motion preference always applies. |
| `UI_EASTER_EGGS_ENABLED` | `True` | Deployment kill switch for easter eggs. On by default; each space can turn `ui.easter_eggs` off; scanner, kiosk and payment routes always suppress eggs. |

Travel support (`event_reimbursements`) and staged event forms. Each value is bounded;
an out-of-range value refuses to start. Retention counts from the record's terminal
financial anchor (receipts, payee data) or the event end (stage uploads), never from upload time.

| Setting | Default | Purpose |
| --- | --- | --- |
| `EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS` | `2555` | Days a private reimbursement receipt is kept after its claim's financial closure (1–36500). A space's own finance retention policy must exist before a non-default value is used. |
| `EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS` | `30` | Days after full payment or finance cancellation before payee bank/routing details and routing documents are purged (1–36500). Shown to members in the payee disclosure. |
| `EVENT_REIMBURSEMENT_FILE_MAX_BYTES` | `10485760` | Per-file cap for receipts and payee documents; can only be lowered (max 10 MiB). |
| `EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES` | `104857600` | Per-member finance attachment budget within one event. |
| `EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES` | `1073741824` | Per-event finance attachment budget. |
| `EVENT_STAGE_FILE_RETENTION_DAYS` | `365` | Days a submitted stage-form upload is kept after the event ends (1–36500); the value is snapshotted onto each upload. |
| `EVENT_STAGE_MEMBER_QUOTA_BYTES` | `104857600` | Per-member stage-form upload budget within one event. |
| `EVENT_STAGE_EVENT_QUOTA_BYTES` | `1073741824` | Per-event stage-form upload budget. |

The installed video provider invokes the bounded non-root ffprobe launcher; the backend
image includes ffmpeg. [Scanner/probe setup](events/operations.md#optional-malware-scanner)
requires real provider/fault tests. These controls do not enable programme capabilities.
Certificate verify uses a fixed 30/min anonymous throttle, rather than a new env setting.

## API clients (HMAC)

See `docs/api-client-protocol.md`.

| Variable | Default | Notes |
|---|---|---|
| `APICLIENT_REQUIRE_NONCE` | `False` | Refuse signed requests without `X-Nonce`. |
| `API_CLIENT_AUTH_REQUIRED` | `False` | Enforce client authentication on protected paths (otherwise log would-reject). |
| `API_CLIENT_ENC_KEY` | `''` | Fernet key for every stored integration secret. Back it up; changing it makes stored secrets unreadable. |
| `HMAC_CLIENT_ID` | `''` | Read only by `manage.py seed_demo`, which registers this signed client for the demo frontend. |
| `HMAC_MAX_CLOCK_SKEW_SECONDS` | `300` | Largest allowed difference between a signed request's timestamp and server time. |
| `HMAC_PROTECTED_PATH_PREFIXES` | `['/api/public/', '/api/v1/public/']` | Paths that require a signed or publishable-key client. |
| `HMAC_SECRET` | `''` | Secret for the `seed_demo` client above; not used at runtime. |
| `THROTTLE_CLIENT_PUBLIC` | `'30/min'` | Public-route budget for an API client in the `public` tier. |
| `THROTTLE_CLIENT_STANDARD` | `'120/min'` | The same budget for the `standard` tier. |
| `THROTTLE_CLIENT_TRUSTED` | `'600/min'` | The same budget for the `trusted` tier. |

## Install-time sign-in choices

Accounts and authentication are always installed by the guided installer. It asks which built-in
providers to offer and whether to enable two-step sign-in; provider credentials are entered later
in the platform console. Provider switches are read-only in `/control/` and compose with the social
master switch and configured credentials. OIDC keeps its per-provider `is_enabled`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SETUP_MFA_ENABLED` | unset (preserve model default: on) | First `setup_instance` creation only: `y` or `n`. Guided setup defaults to `Y`. |
| `SETUP_SOCIAL_PROVIDERS` | unset (preserve model defaults: all on) | First creation only: comma list of `google,apple,github`, or literal `none`. Guided setup defaults to `google`. |

Both are one-shot setup inputs, excluded from backup compatibility requirements; do not add them to
runtime service settings. Reruns never rewrite an existing login-methods row. Use
`manage.py set_login_methods --mfa on|off --providers google,apple,github` (or `--providers none`) for
later changes; the command validates the full state and records an audit event in the same transaction.

## Two-step sign-in

Superadmins sign in with a password and may opt in to TOTP. Every staff role in every space
must have two-step sign-in (an authenticator app or a passkey; release 2, #62): it is a platform rule
with no setting, and newly appointed staff get three days to set it up. Members can opt in at `/mfa`.
Secrets use the existing `API_CLIENT_ENC_KEY` encryption; recovery codes are hashed. No separate key is
needed.

`Platform login methods` in `/control/` shows `mfa_enabled` read-only (existing deployments
default on) and the `passkeys_enabled` switch (default on; passkeys are offered, never required).
Setup chooses `mfa_enabled` at install ("Let members turn on two-step sign-in too?"); change it later
with `manage.py set_login_methods --mfa on|off`. It governs MEMBER opt-in only: turning it off pauses
member challenges, enrollment and recovery-code regeneration and keeps existing authenticators; it
never pauses staff MFA. Disable remains available. Sessions issued while bypassing required/enrolled MFA cannot continue after re-enabling,
even after refresh rotation. Identity-provider sign-ins skip local TOTP by owner decision and
carry provider proof; credential resets/disable still revoke them. Django control sessions also
carry source and credential version, so host recovery requires a fresh password login.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MFA_CHALLENGE_TTL_SECONDS` | `300` | Lifetime of the opaque first-factor proof (60–600 seconds); no JWT exists until verification. |
| `MFA_MAX_ATTEMPTS` | `5` | Failed second-factor attempts per challenge before refusal (1–10). |

### GitHub member sign-in

In GitHub **Settings → Developer settings → OAuth Apps → New OAuth App**, set the
homepage to the public SpaceWorks site. Register the **Authorization callback URL**
as the exact member sign-in page, for example `https://space.example/member` or
`https://platform.example/m/makerspace/member`. Locally, use
`http://localhost:5000/member` (or the corresponding `/m/<slug>/member` page).
The browser returns to that same page, which posts the code, state and its tab-held
nonce to `/api/v1/auth/social/github/callback`; the API URL is not the registered
callback. Use an OAuth App registration matching the public sign-in URL being used.

Copy the **Client ID** and generate a **Client secret**. Paste them into
**Platform → Social sign-in → GitHub OAuth App (members)** in the staff console, or
the platform social-auth settings in `/control/`. The secret uses `API_CLIENT_ENC_KEY`,
is write-only, and a blank field keeps the saved value; use **Clear saved GitHub secret**
to remove it. Keep social sign-in and member accounts enabled. Members must have a
primary verified email on GitHub. New accounts also require self-registration enabled.
GitHub does not sign into the staff console. No new environment variables are needed.

See [GitHub's OAuth App flow](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)
for the authorization-code and PKCE contract.

### Staff invitations

Staff invitation links use `PUBLIC_APP_BASE_URL` or the verified tenant frontend domain.
The email module may be off; staff still receive a copyable link. Links expire in seven
days by default, contain a fragment token, and are single use. Existing accounts must
supply their password and, while platform MFA is on, enrolled second factor; an invitation cannot reset passwords.


## Installer topology selectors

These values are written after the shared deployment questionnaire is confirmed. Keep `.env` private.
The wrapper selects and validates the corresponding compose layers for setup, updates, rollback and
restore; missing selectors preserve the existing bundled stack. These rows are host/Compose-only
and excluded from backend backup preflight; `PLATFORM_SUBDOMAIN_AUTO_TLS` is a Django setting
documented under managed SaaS mode above.

| Variable | Default / meaning |
| --- | --- |
| `SPACEWORKS_HOSTING_MODEL` | `1`: one makerspace; `2`: shared `/m/<slug>` spaces; `3`: subdomain platform. Records intent; does not enforce a tenant-count limit. |
| `SPACEWORKS_RUN_FRONTEND` | `yes`; `no` disables the website and selects the API nginx edge. |
| `SPACEWORKS_STORAGE` | `bundled`; `external` disables Silo/MinIO and bucket initialization. |
| `API_BIND` | API edge listener address, default `0.0.0.0`; existing proxies use `127.0.0.1`. Built-in HTTPS removes this listener and uses Caddy. |
| `API_PORT` | API edge listener port, default `80`; existing proxies use `8080`. |
| `HTTP_PORT_BIND` | Website listener address, default `0.0.0.0`; existing proxies use loopback with `HTTP_PORT=8080`. |
| `SPACEWORKS_WEB_UPSTREAM` | `frontend:80` or `api-edge:80`, selected automatically for Caddy. |
| `TLS_EMAIL` | Required certificate-contact email for guided automatic HTTPS. |
| `PUBLIC_DOMAIN` | Public API/server domain the bundled Caddy serves and certifies. Required when the `tls` layer is used (Compose refuses to start without it); `apply-settings.sh` also reads it. |
| `TLS_HTTP_PORT` | Host port for Caddy's plain-HTTP listener, default `80`. |
| `TLS_HTTPS_PORT` | Host port for Caddy's HTTPS listener, default `443`. |
| `MINIO_API_BIND` | Address the bundled storage API port listens on, default `0.0.0.0`. The installer writes `127.0.0.1` behind an existing proxy or when Caddy serves storage over HTTPS. |
| `MINIO_CORS_ALLOWED_ORIGINS` | Comma-separated browser origins allowed to upload to bundled storage, default `*`. The installer writes your site origins. |
| `COMPOSE_PROFILES` | Extra Compose profiles saved by the installer, for example `clamav` when the optional scanner is chosen. The wrapper adds `tls` itself. |
| `PLATFORM_DOMAIN` | Platform apex DNS name used by the installer SaaS Caddy configuration. |
| `PLATFORM_FIRST_HOST` | First tenant API/site hostname; explicitly certified so API-only hosting can use a separate frontend origin. |
| `CADDY_SAAS_CONFIG` | Defaults to existing `./deploy/Caddyfile.saas`; new guided platforms use `./deploy/Caddyfile.saas-install` for public ACME. Existing deployments keep their origin-certificate configuration. |
| `STORAGE_DOMAIN` | Bundled HTTPS storage hostname (`files.<server/platform-domain>`). Requires DNS; an existing proxy forwards to loopback Silo port 9000. |
| `STORAGE_CADDY_CONFIG` | Defaults to `/etc/caddy/storage-disabled.caddy`; guided bundled HTTPS storage selects `/etc/caddy/storage.caddy`. External storage has no local route. |
| `CONTROL_PLANE_PROXY` | `false` (server-only). `true` makes the bundled proxy (Caddy or the website nginx) forward `/control/`, `/mfa/control/` and `/mfa/reauth/` to Django on the site's own host. Django reads it too (#189/#191): while it is `false`, `/control/` answers 404 to everything except the server itself and the SSH tunnel. Only `true`/`false` are valid; anything else stops the proxy from starting. Apply a change with `bash scripts/apply-settings.sh`. |
| `CONTROL_PLANE_TUNNEL` | Set to `on` by `docker/compose.control-tunnel.yml` for Caddy and the backend; never set it by hand. Django believes the tunnel listener's `X-SpaceWorks-Control-Tunnel` stamp only while it is `on`, and only from a private peer. |
| `CONTROL_PLANE_ALLOW_CIDRS` | Empty (any address). Space-separated IPv4/IPv6 addresses or CIDRs allowed to reach the control plane; others get 403. Only meaningful where the proxy sees the real client address — not behind your own reverse proxy. |
| `CONTROL_PLANE_TUNNEL_PORT` | Empty (off). Automatic-HTTPS installs only: a `127.0.0.1`-only HTTPS port serving just the control plane, for `ssh -L`. Needs Docker Engine 28 or newer. |

External storage also writes existing `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_S3_ENDPOINT_URL`, `AWS_S3_PUBLIC_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_STORAGE_BUCKET_NAME`,
`PUBLIC_IMAGE_BUCKET`, `PUBLIC_IMAGE_BASE_URL` and `STORAGE_PRESIGN_METHOD` (`put` or `post`). The private
and public buckets must differ. The endpoint must be browser reachable; HTTPS sites need HTTPS endpoint
and image URLs. Configure provider CORS, private evidence policies, public-image reads and versioning
in the provider dashboard. Production Compose retains the bundled MINIO credential fallback.

API-only answers populate `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` and `PUBLIC_APP_BASE_URL` from
the supplied HTTPS origins; the first is the canonical staff website and makerspace `frontend_domain`.
Shared multi-tenant staff sites also populate `PLATFORM_STAFF_ORIGINS`. Set external frontend
`VITE_API_URL=https://<API-domain>/api`. The installer writes `ENABLE_HTTPS`,
`TRUST_X_FORWARDED_PROTO`, `TRUSTED_PROXY_COUNT`, `PLATFORM_DOMAIN_SUFFIX`, `BEHIND_TRUSTED_PROXY`,
`PLATFORM_ORIGIN_HOST` and `INFRA_HOSTS` to match the selected edge/proxy topology.

## Metrics, organization creation and analytics

See [the operations reference](environment-operations.md#route-metrics-organization-creation-and-web-analytics)
for `ROUTE_METRICS_ENABLED` (default `False`), `PROMETHEUS_MULTIPROC_DIR` (empty;
Compose uses `/tmp/spaceworks-prometheus`), `ORGANIZATION_SELF_CREATION_ENABLED`
(default `False`), `ORGANIZATION_SELF_CREATION_MAX_OWNED` (3), and
`ORGANIZATION_SELF_CREATION_MAX_PER_DAY` (1).

`WEB_ANALYTICS_SCRIPT_URL`, `WEB_ANALYTICS_COLLECT_URL` and `WEB_ANALYTICS_DOMAIN`
default to empty and must be configured together for manual Plausible analytics.
`WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS` is a frontend-only CSP option (empty by default),
not a Django setting. The operations reference describes their validation and backup policies.
Station PINs also require the independent `EVENT_STATION_PIN_PEPPER` secret documented
there; setup creates it once and upgrades must preserve it.

Space analytics (Metabase embedding, release 2) adds no environment variables. Each
space's Metabase URL, embed secret and read-only database login are stored encrypted on
its analytics connection, and the platform has its own connection row.

## Addressed messaging

Canonical Twilio/Meta credentials live in `ChannelConfiguration`, with explicit platform
opt-in. Compatibility callback verifiers and encrypted retired credential versions remain
available during replay; retirement and sending activation require separate operator
checkpoints. Canonical Meta HTTP uses `WHATSAPP_META_GRAPH_VERSION` (default `v25.0`),
documented in [the delivery reference](environment-reference-delivery.md); the
compatibility send and template-check helpers read the same setting, and it does not enable a
sender. Preserve old signed callback routes through the
[callback/replay compatibility period](notification-reconciliation-rollout.md).

| Variable | Default | Notes |
| --- | --- | --- |
| `MESSAGING_WEBHOOK_BASE_URL` | empty | Operator-owned absolute externally reachable origin (scheme and host, optional deployment prefix). Required for SMS and compatibility SMS/WhatsApp callback resolution. Old callback paths shown in settings remain under `/api/v1/integrations/messaging/`; canonical WhatsApp routes are under `/api/v1/integrations/makerspace/{id}/whatsapp/`. Twilio signatures use this configured base, never forwarded headers. |

Provider credentials live encrypted in the platform or tenant settings, not environment
variables. OTP SMS keeps its existing independent platform configuration. Retired callback
credentials are accepted for fourteen days and wiped by `messaging-credential-wipe` in
both Celery beat and `run_scheduled_tasks`. Sending remains separately paused by NotificationCutover
until explicit replay verification/activation; migrations do not enable delivery.


Addressed channel operations: see [SMS and WhatsApp notifications](messaging-channels.md)
for exact versioned webhook URLs, Twilio Advanced Opt-Out and connection overrides,
Meta registration/PIN and permissions, and the bounded WhatsApp correlation probe.
`MANAGED_RESOURCE_LIMITS["sms"]` and `["whatsapp"]` default to 100 logical messages per
makerspace/day, with existing per-space resource-limit overrides. Self-host bypasses
these notification quotas. Both scheduler modes run `messaging-recovery` every five
minutes and `canonical-messaging-retention` hourly; provider secrets retired for 14 days are
wiped independently of module state.

Cloud integration: [hosting choices and operational contracts](deploy/cloud-overview.md). Full host defaults remain unchanged; managed/free is explicit and subject to release acceptance gates.
Provider/cloud inputs and secret-file rules: [managed environment reference](deploy/cloud-environment.md). FREE_* caps apply only in the selected free profile.

## Login security (release 2)

These are the deployment's **platform defaults** for login security. Each space has its own
security policy (Security settings in the staff console and `/control/`); a space may only
make a value **stricter** than the platform default, never looser, and a superadmin lock is a
floor the space cannot go below. For a person who is staff in several spaces, the strictest
value across those spaces applies. Out-of-range values refuse to start the backend.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PASSWORD_BREACH_CHECK_ENABLED` | `True` | Refuse new passwords found in known breaches, using the Have I Been Pwned k-anonymity range API (only a 5-character hash prefix leaves the server). Fail-open: an unreachable service never blocks a password change. |
| `PASSWORD_BREACH_CHECK_TIMEOUT_SECONDS` | `2` | Time limit for that lookup (1–10 seconds). |
| `TURNSTILE_SITE_KEY` | empty | Cloudflare Turnstile site key. CAPTCHA stays off until both keys are set. Also pass it to the frontend container (the Compose files do) so the SPA's Content-Security-Policy allows `https://challenges.cloudflare.com`; it is public and published in `/api/v1/config` as `turnstile_site_key`. When Turnstile is on, Cloudflare sees the address of anyone asked to solve it (after failed sign-ins); say so in your privacy notice. |
| `TURNSTILE_SECRET_KEY` | empty | Cloudflare Turnstile secret key (secret-bearing). Set it together with the site key; setting only one of the two refuses to start. |
| `TURNSTILE_FAIL_MODE` | `open` | `open` lets a sign-in through when Turnstile cannot be reached; `closed` refuses it. |
| `TURNSTILE_AFTER_FAILURES` | `3` | Failed sign-ins before the CAPTCHA is shown (1–20). |
| `TURNSTILE_HOSTNAMES` | empty | Comma-separated hostnames Turnstile runs on (and a token must have been issued for); empty means the request's own verified origin host. A space's custom domain must also be listed here and in the Cloudflare widget for its `security.captcha_on_sign_in` setting to take effect. |
| `LOGIN_IP_BLOCK_ENABLED` | `True` | Automatically block a source address that fails sign-in against many different accounts (credential stuffing). Superadmin allow and deny rules in `/control/` always win. |
| `LOGIN_IP_BLOCK_DISTINCT_ACCOUNTS` | `10` | Distinct accounts one source may fail against inside the window before it is blocked (2–1000). |
| `LOGIN_IP_BLOCK_WINDOW_SECONDS` | `900` | The counting window (60–86400 seconds). |
| `LOGIN_IP_BLOCK_SECONDS` | `3600` | How long an automatic block lasts (60–604800 seconds). |
| `LOGIN_RISK_FAILURE_THRESHOLD` | `3` | Failed sign-ins after which the next one is treated as unusual and asks for a second check (1–20). |
| `LOGIN_REMEMBERED_DEVICE_DAYS` | `90` | How long a device that passed the unusual-login check stays remembered (1–90 days). |
| `LOGIN_CODE_TTL_SECONDS` | `600` | Lifetime of an emailed 6-digit login code (60–1800 seconds). |
| `SECURITY_ALERT_LINK_TTL_DAYS` | `14` | How long the "this wasn't me" link in a security alert email works (1–30 days). |
| `WEBAUTHN_RP_NAME` | `Space Works` | Name a browser shows when creating a passkey (1–64 characters). The passkey relying-party ID is the site's own host. |
| `MIN_NATIVE_APP_VERSION_IOS` | empty | Oldest iOS app version (`x.y.z`, compared numerically) allowed to sign in or refresh a device session. Older or unversioned apps get HTTP 426 `native_app_update_required`. Empty = no minimum. |
| `MIN_NATIVE_APP_VERSION_ANDROID` | empty | The same minimum for the Android app. |
| `THROTTLE_LOGIN_CODE_RESEND` | `'5/hour'` | Emailed login-code sends per challenge. |
| `THROTTLE_LOGIN_CODE_IP` | `'30/hour'` | Login-code sends and checks per source address. |
| `THROTTLE_PASSKEY_OPTIONS` | `'30/min'` | Passkey registration and sign-in option requests. |
| `THROTTLE_PASSKEY_VERIFY` | `'10/min'` | Passkey verification attempts. |
| `THROTTLE_SECURITY_ALERT_ACTION` | `'10/hour'` | Uses of a security alert's "this wasn't me" link. |
| `THROTTLE_ACCOUNT_MERGE_START` | `'10/hour'` | Account-link requests and code resends per person (`auth/account-merge/start`, `.../resend`). |
| `THROTTLE_ACCOUNT_MERGE_PROVE` | `'30/hour'` | Account-link proofs, previews, confirmations and cancels per person. |

## Compose host settings

Read only by the Compose files and the wrapper scripts, never by backend Python. Defaults are
the Compose interpolation defaults (`docker-compose.yml` for development, `docker-compose.prod.yml`
for production, `docker-compose.cloud.yml` and the managed/free files for cloud images). See
[self-hosting](self-hosting.md) for which ones a deployment must decide.

| Variable | Default | Notes |
| --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | Docker's default (directory name) | `.env.example` sets `spaceworks`; keep it stable or Compose treats the stack as new. |
| `POSTGRES_PASSWORD` | none in production | Required in production (Compose refuses to start without it). Owner/maintenance database password; never used by application processes. Development uses `makerspace`. |
| `POSTGRES_USER` | `makerspace` | Owner/maintenance database user. |
| `POSTGRES_DB` | `makerspace_manager` | Database name. |
| `POSTGRES_APP_USER` | `spaceworks_app` | Least-privilege runtime role used by backend, worker, beat and cron. |
| `POSTGRES_APP_PASSWORD` | `spaceworks-app-dev` | Runtime role password. Required in production: replace the development default. |
| `MINIO_ROOT_USER` | none in production | Required in production with bundled storage. Storage access key; also the backend's `AWS_ACCESS_KEY_ID` unless that is set. Development uses `minioadmin`. |
| `MINIO_ROOT_PASSWORD` | none in production | Required in production with bundled storage. Storage secret key; also the backend's `AWS_SECRET_ACCESS_KEY` unless that is set. |
| `MINIO_API_PORT` | `9000` | Host port of the bundled storage API. |
| `MINIO_CONSOLE_BIND` | `127.0.0.1` | Address of the storage web console listener. |
| `MINIO_CONSOLE_PORT` | `9001` | Host port of the storage web console. |
| `SILO_IMAGE_TAG` | `RELEASE.2026-09-16T00-00-00Z` | Tag of the bundled storage image. |
| `MAKERSPACE_BACKEND_IMAGE` | `ghcr.io/spaceworks-labs/spaceworks-backend` | Backend image name (derived from `SPACEWORKS_REPOSITORY` by the installer). The managed and free cloud files require an immutable digest instead. |
| `MAKERSPACE_FRONTEND_IMAGE` | `ghcr.io/spaceworks-labs/spaceworks-frontend` | Frontend image name. |
| `MAKERSPACE_IMAGE_TAG` | `latest` | Image tag for both images; `update.sh` and `apply-settings.sh` set it to the installed release. |
| `HTTP_PORT` | `80` | Host port of the website (bundled nginx). |
| `GUNICORN_WORKERS` | `3` | Backend web workers. |
| `GUNICORN_TIMEOUT` | `60` | Backend request timeout in seconds. |
| `LIVE_THREADS` | `32` | Threads of the separate live-update (SSE) web process; each open stream holds one. |
| `CELERY_CONCURRENCY` | `4` | Celery worker processes. |
| `SPACEWORKS_HOST_STATE_DIR` | `/var/lib/spaceworks/host` | Host directory for the restore marker and host state. |
| `SPACEWORKS_OPS_HOST_DIR` | `/var/lib/spaceworks/ops` | Host directory for the database pointer, operation lock and backup work files. |
| `SPACEWORKS_DB_POINTER_GENERATION` | set by the wrapper | Generation of the atomic database pointer. `scripts/spaceworks-compose.sh` supplies it with `DATABASE_URL`; never set it by hand. |
| `BACKEND_PORT` | `8000` | Cloud and managed Compose files: host port of the backend. |
| `FRONTEND_PORT` | `8080` | `docker-compose.cloud.yml`: host port of the website. |
| `CRON_INTERVAL_SECONDS` | `900` | `docker-compose.cloud.yml`: seconds between scheduled-task runs in the cron loop. |
| `SPACEWORKS_RUNTIME_ENV_FILE` | none | Managed brokerless and free files: required path of the protected runtime-only env file. Never put maintenance credentials in it. |
| `DEV_UID`, `DEV_GID` | `1000` | `docker-compose.dev.yml`: user and group the development containers run as. |

## Frontend build and container settings

The website reads two kinds of settings. `VITE_*` values are compiled into the JavaScript at
build time. The container settings are read by the nginx image's start-up scripts
(`frontend/docker-entrypoint.d/`) and written into `config.js`, so one image serves any
deployment; a container value wins over the build value. The container also reads
`TURNSTILE_SITE_KEY`, `WEB_ANALYTICS_*`, `CONTROL_PLANE_PROXY`, `CONTROL_PLANE_ALLOW_CIDRS`,
`UI_DELIGHT_ENABLED` and `UI_EASTER_EGGS_ENABLED` (documented above).

| Variable | Default | Notes |
| --- | --- | --- |
| `TENANT_API_URL` | `VITE_API_URL`, then `/api` | Container: API base URL, a relative `/api` path or an `http(s)` URL. Compose sets `/api`. An invalid value stops the container. |
| `TENANT_TOKEN` | `VITE_TENANT_TOKEN`, then empty | Container: makerspace public code a single-tenant website is pinned to. At most 256 characters of letters, digits, `.`, `_`, `:` and `-`. |
| `TENANT_ORIGIN_BOOTSTRAP` | `false` | Container: `true` or `1` resolves the makerspace from the request origin (shared and subdomain platforms). |
| `VITE_API_URL` | `http://localhost:8000/api` (image build: `/api`) | Build: API base URL. |
| `VITE_TENANT_TOKEN` | empty | Build: makerspace public code for a pinned single-tenant build. |
| `VITE_PUBLIC_API_KEY` | empty | Build: publishable key sent as `X-Publishable-Key` on public routes when no space key has been loaded. |
| `VITE_PUBLIC_CLIENT_ID` | empty | Build: API client ID sent as `X-Client-Id`; when set it replaces the publishable key header. |
| `VITE_EVENT_UPLOAD_ORIGINS` | empty | Build: comma-separated exact origins the browser may upload event files to. Empty allows same-origin uploads only; local development lists `http://localhost:9000`. |
| `VITE_UI_DELIGHT_ENABLED` | on unless `false` | Build: fallback for the artwork and motion switch when the container sets none. |
| `VITE_UI_EASTER_EGGS_ENABLED` | on unless `false` | Build: fallback for the easter-egg switch when the container sets none. |
| `VITE_APP_VERSION` | empty | Build: version string shown by the maker-mode easter egg. No build script sets it today. |
| `VITE_DEV_PROXY_TARGET` | `http://localhost:8000` | Vite dev server and preview only: where `/api` and the Django-served share pages are proxied. The development Compose file sets `http://backend:8000`. |

The start-up scripts also accept internal path overrides (`TENANT_CONFIG_PATH`,
`WEB_ANALYTICS_HEADERS_PATH`, `CONTROL_PLANE_SNIPPET`, `CONTROL_PLANE_LIB`) and two
control-plane routing overrides (`CONTROL_PLANE_UPSTREAM`, default `http://backend:8000`;
`CONTROL_PLANE_PROTO`, default `$external_scheme`). Leave them unset.

## Removed in release 2

These were documented and read in the last release-1 build (`v0.9.2`) and are no longer read.
Remove them from `.env`; leaving them has no effect.

| Variable | Why |
| --- | --- |
| `ANONYMOUS_REQUEST_OUTSTANDING_LIMIT` | The original account-less request flow was removed. Spaces without member accounts now use the emailed-code flow limited by the `THROTTLE_ANONYMOUS_REQUEST_*` budgets. |
| `ANONYMOUS_REQUEST_IDEMPOTENCY_KEY_MAX_LENGTH` | Same removal. |
| `BACKUP_RECIPIENT_CHALLENGE_TTL_SECONDS` | Archive recipients and custody were removed from backups. |
| `THROTTLE_ARCHIVE_RECIPIENT_VERIFY` | Same removal. |
| `PRINT_URL_TTL_SECONDS` | Unused; private print files use `EVIDENCE_URL_TTL_SECONDS`. |

Pre-release builds of release 2 also briefly read `MOBILE_MIN_VERSION_IOS` and
`MOBILE_MIN_VERSION_ANDROID` (use `MIN_NATIVE_APP_VERSION_IOS` / `_ANDROID`, or per-registration
minimum versions in `/control/`) and `WHATSAPP_GRAPH_VERSION` (use `WHATSAPP_META_GRAPH_VERSION`).
There is no staff two-step sign-in switch: it is a platform rule.
