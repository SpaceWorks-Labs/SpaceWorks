# Environment reference: operations

See [environment-reference.md](environment-reference.md) for core, storage and sign-in settings.

## Scoped PII encryption

See `docs/scoped-pii-encryption.md`.

| Variable | Default | Notes |
|---|---|---|
| `PII_AWS_KMS_ENDPOINT_URL` | `''` |  |
| `PII_AWS_KMS_KEY_ID` | `''` |  |
| `PII_AWS_KMS_REGION` | `''` |  |
| `PII_DEK_CACHE_TTL_SECONDS` | `300` |  |
| `PII_ENCRYPTION_DUAL_READ` | `True` |  |
| `PII_ENCRYPTION_ENABLED` | `False` |  |
| `PII_KEY_BROKER` | `'local'` |  |
| `PII_MASTER_KEY` | `''` |  |
| `PII_MASTER_KEY_PREVIOUS` | `''` |  |
| `PII_SEARCH_HASH_KEY` | `''` |  |

## Row-level security and per-space keys (release 2, lane L8)

See `docs/INVARIANTS.md` "Row-level security backstop" and "Per-space key rotation".

| Variable | Default | Notes |
|---|---|---|
| `TENANT_RLS_MODE` | `'auto'` | `auto` enforces on a narrow runtime role and reports only on an owner role; `enforce`, `report` or `off` override it. The app never refuses to start. |
| `TENANT_RLS_PROBE_ROLE` | `''` | Tests and the release regression only: bound statements `SET LOCAL ROLE` to this narrow role, so a superuser test run is forced on. Leave empty in production. |
| `PUBLISHABLE_KEY_ROTATION_GRACE_HOURS` | `72` | How long a rotated public-site browser key keeps working before it is refused. |

## Audit attestation

| Variable | Default | Notes |
|---|---|---|
| `AUDIT_ATTESTATION_ANCHOR_BACKEND` | `''` |  |
| `AUDIT_ATTESTATION_DEPLOYMENT_ID` | `''` |  |
| `AUDIT_ATTESTATION_HTTP_BEARER_TOKEN` | `''` |  |
| `AUDIT_ATTESTATION_HTTP_TIMEOUT` | `10` |  |
| `AUDIT_ATTESTATION_HTTP_URL` | `''` |  |
| `AUDIT_ATTESTATION_RETENTION_DAYS` | `2555` |  |
| `AUDIT_ATTESTATION_S3_ACCESS_KEY_ID` | `AWS_ACCESS_KEY_ID` |  |
| `AUDIT_ATTESTATION_S3_BUCKET` | `''` |  |
| `AUDIT_ATTESTATION_S3_ENDPOINT_URL` | `AWS_S3_ENDPOINT_URL` |  |
| `AUDIT_ATTESTATION_S3_OBJECT_LOCK_MODE` | `'COMPLIANCE'` |  |
| `AUDIT_ATTESTATION_S3_PREFIX` | `'spaceworks-audit/v1'` |  |
| `AUDIT_ATTESTATION_S3_REGION_NAME` | `AWS_S3_REGION_NAME` |  |
| `AUDIT_ATTESTATION_S3_SECRET_ACCESS_KEY` | `AWS_SECRET_ACCESS_KEY` |  |
| `AUDIT_MAC_MASTER_KEY` | `''` |  |

## Backup, restore and tenant migration

Host-orchestration paths and timing knobs; see `docs/self-hosting.md` and the restore runbooks.

| Variable | Default | Notes |
|---|---|---|
| `BACKUP_AGE_RECIPIENT` | `''` |  |
| `BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY` | `''` |  |
| `BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY` | `''` |  |
| `BACKUP_DECISION_SECONDS` | `5 * 60` |  |
| `BACKUP_DOWNLOAD_TTL_SECONDS` | `5 * 60` |  |
| `BACKUP_LEASE_SECONDS` | `2 * 60 * 60` |  |
| `BACKUP_OPS_DIR` | `'/var/lib/spaceworks/ops'` |  |
| `BACKUP_PRESIGN_DRAIN_SECONDS` | `max(EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECOND...` |  |
| `BACKUP_PRODUCER_CAPABILITY_MARKER_PATH` | `'/run/spaceworks-host/producer-capability.json'` |  |
| `BACKUP_PRODUCER_ENTRYPOINT_PATH` | `'/app/scripts/spaceworks_entrypoint.py'` |  |
| `BACKUP_PRODUCER_MIGRATIONS_DIR` | `str(BASE_DIR / 'apps')` |  |
| `BACKUP_PRODUCER_PRIVILEGED_SCRIPTS_DIR` | `'/run/spaceworks-privileged-scripts'` |  |
| `DATA_EXPORT_DEADLINE_SECONDS` | `900` |  |
| `DATA_EXPORT_DOWNLOAD_TTL_SECONDS` | `5 * 60` |  |
| `DATA_EXPORT_PAGE_SIZE` | `500` |  |
| `DATA_EXPORT_RETENTION_SECONDS` | `7 * 24 * 60 * 60` |  |
| `SPACEWORKS_HOST_MARKER_PATH` | `'/run/spaceworks-host/restore-marker.json'` |  |
| `SPACEWORKS_HOST_MARKER_WRITE_PATH` | read outside `settings.py` |  |
| `SPACEWORKS_OCI_DIGEST` | read outside `settings.py` |  |
| `TENANT_DUMP_STAGING_DIR` | `''` |  |
| `TENANT_DUMP_STAGING_MAX_AGE_SECONDS` | `7 * 24 * 60 * 60` |  |
| `TENANT_MIGRATION_AGE_IDENTITY_FILE` | `''` |  |
| `TENANT_MIGRATION_AGE_RECIPIENT` | `''` |  |
| `TENANT_MIGRATION_GATE_LEASE_SECONDS` | `2 * 60 * 60` |  |
| `TENANT_MIGRATION_PRESIGN_DRAIN_SECONDS` | `max(EVIDENCE_URL_TTL_SECONDS, PUBLIC_IMAGE_URL_TTL_SECOND...` |  |

## Connected devices

| Variable | Default | Notes |
|---|---|---|
| `DEVICE_COMMAND_LEASE_SECONDS` | `60` | Delivery lease for a printer/label command; covers delivery, not print duration. |
| `DEVICE_COMMAND_MAX_ATTEMPTS` | `10` | Bounded delivery retries before a command fails. |
| `DEVICE_ENROLLMENT_TTL_SECONDS` | `900` | Lifetime of a one-time enrollment code. |
| `DEVICE_NONCE_TTL_SECONDS` | `86400` | Replay-nonce retention for device-signed requests. |
| `DEVICE_SIGNATURE_MAX_SKEW_SECONDS` | `300` | Accepted clock skew on a device request signature. |

## Events, bookings and kiosk stations

| Variable | Default | Notes |
|---|---|---|
| `EVENT_CHECKIN_CLOCK_SKEW_SECONDS` | `300` |  |
| `EVENT_CHECKIN_ROSTER_LIFETIME_HOURS` | `24` |  |
| `EVENT_CHECKIN_ROSTER_MAX` | `1000` |  |
| `EVENT_CHECKIN_SYNC_GRACE_HOURS` | `24` |  |
| `EVENT_CHECKIN_WINDOW_AFTER_HOURS` | `2` |  |
| `EVENT_CHECKIN_WINDOW_BEFORE_HOURS` | `24` |  |
| `EVENT_STATION_PIN_PEPPER` | `''` | Independent secret of at least 32 bytes for station PIN hashing. Setup generates 50 random characters once; preserve across upgrades and backups. Changing it invalidates existing station PINs. |
| `KIOSK_COMMAND_MAX_AGE_SECONDS` | `8 * 60 * 60` | Oldest offline kiosk command a replay still accepts. |
| `KIOSK_OPERATOR_LEASE_RETENTION_SECONDS` | `7 * 24 * 60 * 60` | How long ended operator leases are kept before cleanup. |
| `KIOSK_OPERATOR_LEASE_TTL_SECONDS` | `8 * 60 * 60` | Lifetime of one staff operator lease on a kiosk Station. |
| `KIOSK_REPLAY_CLAIM_TIMEOUT_SECONDS` | `5 * 60` | A claimed replay is released for retry after this long. |
| `KIOSK_REPLAY_CLEANUP_BATCH_SIZE` | `500` | Rows per batch in the nightly replay cleanup. |
| `KIOSK_REPLAY_RETENTION_SECONDS` | `7 * 24 * 60 * 60` | Retention of completed replay commands, unless a review still references them. |
| `KIOSK_STATION_SESSION_TTL_SECONDS` | `12 * 60 * 60` | Lifetime of a kiosk Station session. |

## Install, build and test-only

Consumed by `setup_instance`, the image build, or the e2e seed; never needed at runtime.

| Variable | Default | Notes |
|---|---|---|
| `BUILD_GIT_DESCRIBE` | read outside `settings.py` |  |
| `BUILD_GIT_SHA` | read outside `settings.py` |  |
| `E2E_PASSWORD` | read outside `settings.py` |  |
| `E2E_SEED_ALLOWED` | read outside `settings.py` |  |
| `SETUP_MAKERSPACE_NAME` | read outside `settings.py` |  |
| `SETUP_MAKERSPACE_SLUG` | read outside `settings.py` |  |
| `SETUP_MODULE_PROFILE` | read outside `settings.py` |  |
| `SETUP_MFA_ENABLED` | unset (on for a new row) | First-run two-step sign-in choice, `y`/`n`; later use `set_login_methods`. |
| `SETUP_SOCIAL_PROVIDERS` | unset (all on for a new row) | First-run built-in comma list or literal `none`; guided setup defaults to Google. |
| `SETUP_ORGANIZATION_NAME` | read outside `settings.py` |  |
| `SETUP_SUPERADMIN_EMAIL` | read outside `settings.py` |  |
| `SETUP_SUPERADMIN_PASSWORD` | read outside `settings.py` |  |
| `SETUP_SUPERADMIN_USERNAME` | read outside `settings.py` |  |

## Route metrics, organization creation and web analytics

These settings are runtime options. Metrics are excluded from backup compatibility;
organization policy and backend analytics destinations use non-blocking value comparisons
so restore preflight reports differences without preventing recovery.

| Variable | Default | Notes |
| --- | --- | --- |
| `ROUTE_METRICS_ENABLED` | `False` | Opt in to route-level request metrics; metrics access still requires `METRICS_TOKEN`. |
| `PROMETHEUS_MULTIPROC_DIR` | `''` | Process-local writable Prometheus scratch directory; Compose defaults to `/tmp/spaceworks-prometheus`. Do not share it across containers or persist it across boots. |
| `ORGANIZATION_SELF_CREATION_ENABLED` | `False` | Allow authenticated users to create organizations; off retains administrator-controlled creation. |
| `ORGANIZATION_SELF_CREATION_MAX_OWNED` | `3` | Maximum organizations owned by one account; integer from 1 to 100. |
| `ORGANIZATION_SELF_CREATION_MAX_PER_DAY` | `1` | Maximum organizations an account may create per day; integer from 1 to 100. |
| `WEB_ANALYTICS_SCRIPT_URL` | `''` | HTTPS Plausible manual-script URL. Supply all three backend analytics values together, or leave all empty. |
| `WEB_ANALYTICS_COLLECT_URL` | `''` | HTTPS collection endpoint; added to backend and SPA connect-src policies. |
| `WEB_ANALYTICS_DOMAIN` | `''` | Analytics hostname; no scheme or path. |
| `WEB_ANALYTICS_EXTRA_CONNECT_ORIGINS` | `''` | Frontend nginx only: space-separated HTTPS API/object-storage origins added to connect-src when analytics is enabled. Excluded from backend backup capture. |

Analytics is disabled by default. The website runtime generator composes framing,
referrer and optional analytics policies into the include used by SPA/static locations.
Django owns `/embed/` response policies; nginx passes those headers through.

For installations predating generated station secrets, set `EVENT_STATION_PIN_PEPPER`
once in the private `.env` (for example, generate with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`) before enabling PIN
stations. Keep the existing value on upgrades; the updater preserves `.env`.

Cloud integration: [hosting choices and operational contracts](deploy/cloud-overview.md). Full host defaults remain unchanged; managed/free is explicit and subject to release acceptance gates.
Provider/cloud inputs and secret-file rules: [managed environment reference](deploy/cloud-environment.md). FREE_* caps apply only in the selected free profile.

Cloud configuration and finite-job inputs (host/full ignores free limits):

| Variable | Default | Operational meaning |
| --- | --- | --- |
| `SPACEWORKS_DEPLOYMENT_MODE` | `host` | Explicit host or managed admission; never infer from absent markers. |
| `SPACEWORKS_DEPLOYMENT_PROFILE` | `full` | Free requires managed; the normal VPS installer remains full. |
| `SPACEWORKS_DEPLOYMENT_ID` | empty | Stable managed deployment UUID; bind through release/adopt. |
| `DATABASE_CONNECTION_MODE` | direct on host; explicit managed | Direct or proven session transport; transaction pooling refuses. |
| `DATABASE_MAINTENANCE_CONNECTION_MODE` | explicit | Direct/session declaration for the finite maintenance connection. |
| `DATABASE_MAINTENANCE_URL` | empty | Secret owner connection for release/adopt/qualified export jobs only. |
| `SPACEWORKS_MAINTENANCE_DATABASE_URL` | empty | Host Compose maintenance connection; never an ordinary runtime secret. |
| `CLOUD_SCRATCH_DATABASES_FILE` | empty | Private version-1 file declaring two isolated scratch DB credentials. |
| `CLOUD_TASK_PROFILE` | legacy host selection | Managed redis or brokerless task transport. |
| `CLOUD_SCHEDULER` | legacy host selection | Managed beat, loop or external; free permits tick only. |
| `SPACEWORKS_ADMITTED_GENERATION` | entrypoint-owned | Original launch generation; active boundaries retain their own generation. Do not set manually. |
| `SPACEWORKS_FINITE_MAINTENANCE_JOB` | entrypoint-owned | Exact admitted export command only; erased for other invocations. |
| `PYTHONPATH` | entrypoint-owned | Set only in managed mode, so processes started by the one image can import its cloud setup tooling. Host mode leaves it untouched. |
| `MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS` | `0` | Zero refuses coordinated capture. Set only after proving the provider's enforced transfer horizon, at most 86,400 seconds. |
| `STORAGE_CAPABILITIES_FILE` | empty | Required managed version-1 role/identity/capability descriptor, not a credential file. |
| `STORAGE_CAPABILITY_TTL_SECONDS` | Full: `900`; free: derived | Qualified proof freshness, up to 86,400 seconds. Full accepts 60..86,400; free requires a complete binding refresh cycle plus one tick and execution headroom. See [free cadence](deploy/cloud-free.md). |
| `AWS_SESSION_TOKEN` | empty | Optional private S3 temporary credential token. |
| `EMAIL_PROVIDER` | empty legacy selection | smtp, resend, postmark, ses, brevo, mailgun or sendgrid. |
| `EMAIL_PROVIDER_CONFIG_FILE` | empty | Private runtime provider JSON; never embed in frontend configuration. |
| `EMAIL_PROVIDER_WEBHOOKS_ENABLED` | `False` | Enable only supported native signed provider callbacks. |
| `SPACEWORKS_SECRET_FILE_MODE` | `native` | Explicit inline mode materializes private files before admission. |
| `SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64` | empty | Inline provider secret JSON; removed from child environment after materialization. |
| `SPACEWORKS_STORAGE_CAPABILITIES_B64` | empty | Inline descriptor JSON; removed after protected file materialization. |
| `UPLOAD_SCAN_POLICY` | managed none; existing host selection | none or configured external clamav; no malware-scanning claim for none. |
| `CLAMD_HOST` | empty | Private external scanner endpoint when clamav is selected. |
| `CLAMD_PORT` | `3310` | External scanner port. |
| `CLAMD_TIMEOUT_SECONDS` | `5` | Bounded scanner request timeout. |
| `CLAMD_MAX_SCAN_BYTES` | `2147483648` | Scanner maximum; domain/free limits remain stricter where applicable. |
| `TRUST_FORWARDED_HOST` | `False` | Opt in only with independently restricted managed ingress and exact proxy chain. |
| `TRUSTED_EDGE_CIDRS` | empty | Allowed immediate edge socket networks; no browser authority. |
| `TRUSTED_EDGE_UPSTREAM_HOSTS` | empty | Exact raw upstream Host values; no wildcard. |
| `TRUSTED_EDGE_INGRESS_SECRET` | empty | Protected 32..256 ASCII byte edge/backend proof, distinct from cron secret. |
| `FREE_TICK_SECRET` | empty | Protected fixed internal scheduler secret; full has no route. |
| `FREE_TICK_INTERVAL_SECONDS` | `600` | Must match the actual external trigger; affects freshness warnings. |
| `FREE_TICK_BUDGET_SECONDS` | `20` | Total tick budget, bounded 3..20 seconds with checkpoint headroom. |
| `FREE_TICK_RATE_LIMIT_PER_MINUTE` | `6` | Authenticated database counter limit, 1..60. |
| `FREE_TICK_INGRESS_LIMIT_PER_MINUTE` | `120` | Separate fixed unauthenticated ingress counter, 6..600. |
| `FREE_DB_CAP_BYTES` | configured allowance | Actual operator-verified database cap; unknown usage is never zero. |
| `FREE_OBJECT_CAP_BYTES` | configured allowance | Actual physical object allowance including retained versions/incomplete uploads. |
| `FREE_MAX_PROMOTION_BYTES` | `16777216` | Free promotion ceiling; domain/job limits can be lower. |
| `FREE_EMAIL_DAILY_CAP` | configured allowance | Account-wide recipient allowance, never a per-tenant multiplier. |
| `FREE_EMAIL_MONTHLY_CAP` | none | Optional actual monthly recipient allowance. |
| `FREE_EMAIL_ACCOUNT_KEY` | empty | Stable billing-account alias, preserved across credential rotation. |
| `FREE_EMAIL_PROVIDER` | empty | Provider associated with the configured shared allowance. |
| `FREE_EMAIL_RESET_TIMEZONE` | `UTC` | Actual provider reset timezone. |
| `FREE_EMAIL_ACCOUNTS` | `{}` | Protected multi-account cap/fingerprint map; tenants cannot mint allowances. |
| `SETUP_SUPERADMIN_PASSWORD_GENERATED` | `False` | Setup annotation for a newly generated password; force first change, never print it. |
| `SPACEWORKS_PRIVILEGED_TARGET_REQUIRED` | unset | Ephemeral V proof flag held under the operation lock, never persist in dotenv. |
| `SPACEWORKS_PRIVILEGED_TARGET_NAME` | unset | Proven active database name for privileged bootstrap/migration. |
| `SPACEWORKS_PRIVILEGED_TARGET_OID` | unset | Matching positive active database OID. |
| `SPACEWORKS_PRIVILEGED_TARGET_UUID` | unset | Matching protected database UUID; all four proof values travel together. |
| `SPACEWORKS_GRANT_DATABASE_OID` | unset | Separately supervised sibling grant-only target OID. |
| `SPACEWORKS_GRANT_DATABASE_UUID` | unset | Separately supervised sibling grant-only target UUID. |
| `SPACEWORKS_INITIALIZE_DATABASE_NAME` | unset | Ephemeral pre-H1 name proof for a populated legacy database without a marker. |
| `SPACEWORKS_INITIALIZE_DATABASE_OID` | unset | Matching pre-H1 OID proof; empty fresh initialization retains its explicit path. |
| `BUILD_IMAGE_PROFILE` | image build metadata | Build-owned image identity, always `full`: the one published image runs every profile. |
| `GUNICORN_CMD_ARGS` | empty | Free rejects arbitrary command arguments; use its fixed one-worker topology. |
| `PGCONNECT_TIMEOUT` | validated transport | Connection timeout only; passfiles and validated URLs own credentials. |
| `PGSSLMODE` | validated URL/provider choice | Remote managed connections require explicit TLS; prefer verify-full. |
| `PGSSLROOTCERT` | empty | Optional provider/system CA path. |
| `PGSSLCERT` | empty | Optional client certificate path. |
| `PGSSLKEY` | empty | Optional protected client private-key path. |
| `PGSSLCRL` | empty | Optional certificate revocation-list path. |
| `PGCHANNELBINDING` | validated URL/provider choice | Explicit supported libpq channel-binding policy. |
