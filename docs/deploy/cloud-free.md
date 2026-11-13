# Additional free managed stack

Free requires explicit managed+free. It changes no full-server defaults. The primary proposed stack is Render
Free web + Supabase session PostgreSQL 17 + R2 + Resend/Brevo + Cloudflare static Worker/cron. Live account,
512 MB/0.1 CPU and recovery acceptance have NOT passed. Do not call it certified ongoing $0 hosting until
actual caps, card/domain prerequisites, overage controls and deployed measurements are recorded.

Use deploy/cloud/free.answers.example.json, free.env.example and free-provider-limits.json, plus the separate
deploy/render.free.yaml. On your own server, the VPS installer can prepare the same environment as an opt-in:
`install.sh --profile free` (or choose Hosting model option 4 interactively, or set
`SPACEWORKS_DEPLOYMENT_PROFILE=free`). It writes a private `.env` from free.env.example with every secret
generated, including `FREE_TICK_SECRET`, prints the free-tier notice and starts nothing; full stays the
default. Then supply the external database, storage and email values and run the release job and
docker-compose.free.yml. The managed wizard (`scripts/init-cloud-environment.py`) also generates the
continuity keys (`ACCOUNT_PII_MASTER_KEY`, `EVENT_REGISTRATION_CREDENTIAL_*`, `PUSH_TOKEN_HMAC_KEY` with the
PII/audit/integration keys) once and never replaces them; keep its private secrets file in escrow. Free runs the same spaceworks-backend image as every other profile (static files baked in) and runs
uid 10001. Steady state is one sync web worker/thread, DatabaseCache and no Redis/worker/beat/loop/live process.
Heavy intents remain persisted; every job needs a real bounded checkpoint adapter. No scheduled pg_dump or
deployment backup runs. Unsupported video/media validation must refuse before upload acceptance. Scanning is
explicitly off with a visible notice; type/size validation does not scan malware.

The one scheduler route is POST /api/v1/internal/free/tick, X-Cron-Secret, no caller-selected jobs/credentials.
The body may be absent or an empty JSON object (`{}`, `Content-Type: application/json`, at most 1,024 bytes).
Full has no route/schema even when the secret is set. Browsers cannot reach internal/control paths. Only the
Cloudflare scheduled handler calls the fixed backend origin. Primary cron is */10 * * * * (600 seconds).
Use the exact deploy/static/cloudflare/free/wrangler.toml configuration with adjusted origins and provision
`wrangler secret put FREE_TICK_SECRET` plus the identical protected backend secret. Rotate both together and
verify old-secret refusal. Never put it in vars, frontend env, query strings or logs.

Set actual FREE_DB_CAP_BYTES, FREE_OBJECT_CAP_BYTES, FREE_EMAIL_DAILY_CAP, a stable FREE_EMAIL_ACCOUNT_KEY
and FREE_EMAIL_RESET_TIMEZONE. Omit FREE_EMAIL_MONTHLY_CAP when the provider has none. FREE_EMAIL_ACCOUNTS
binds credential fingerprints/aliases to one billing account, never independent tenant allowances. Accepted,
reserved, uncertain and pending mail remain distinct. Unknown usage outside this application is not zero.
UI reads stored samples, never bucket listings per page. Credential replacement cannot reset charged allowance.

Tick budget is 3..20 seconds (default 20); authenticated rate defaults to 6/minute with a separate fixed ingress
counter. At most one heavy chunk starts per tick. Running/uncertain work never becomes safe merely by age.
There is no response-start/background-thread worker. Reminders are best effort: tick interval plus backlog,
cold starts, missed triggers, provider pauses/restarts and quota suspension. No always-awake guarantee or SLA.

Alternative triggers are in deploy/cloud/free-triggers/. A Neon pause-friendly slower cadence must change both
the real trigger and FREE_TICK_INTERVAL_SECONDS. For intervals of at least five minutes, storage proof TTL
defaults to `(binding count + 1) × tick interval + tick budget` (at least 900 seconds): 1,820 seconds for two
bindings at ten minutes, 5,420 at thirty minutes. Faster custom triggers also account for the refresh task's
five-minute due interval, rounded up to the next trigger slot.
Explicit TTLs below that refresh cycle plus headroom refuse startup. The ceiling remains 86,400 seconds;
reduce the cadence interval if the complete cycle cannot fit. Full-profile TTL defaults remain 900 seconds.
Actions schedules can be delayed/disabled; third-party cron needs current secret-delivery/allowance checks.
Cloud Run requires billing/signup validation. Northflank is
verify-on-signup, not an entitlement. All static requests pass through the Worker guard: measure request/CPU/
cron/subrequest allowances including asset traffic and cold-wake retries. Fail closed on edge quota exhaustion.

An external daily database backup with matching client, or separately qualified portable export, can add
recovery inputs; the free web tick never runs database dumps. Escrow config/keys independently. Object durability
alone cannot undo deletion. [Recovery](cloud-recovery.md) does not promise atomic DB/object restoration.
[Oracle Always Free](cloud-oracle-free.md) instead uses host/full on a VM.

The catalog installs bounded domain, personal-envelope/legacy/mail, six persisted-work, storage-refresh and
usage callbacks. Export admission is at most 500 rows and 2 MiB of logical JSON including account closure;
import admission is at most 2 MiB ciphertext, 512 extracted files, 500 CSV rows, four object files and eight
carried keys. Larger work requires a full external worker before claim/freeze. Portable source capture
requiring presign drain or object bytes also requires that worker. Audit verification additionally bounds
250 rows, 1,000 leaves, 25 batches, eight rotations and 36 anchor reads. These are enforced input limits,
not measured completion promises. A Linux total deadline fences uncertain effects rather than reclaiming
them automatically. Required acceptance still includes real 512 MiB/0.1 CPU export/PDF, overlap, guard-loss,
crash/resume, provider mail/storage and full-profile isolation measurements.

Legacy notification fanout is also bounded before dispatch: at most two email and two inbox destinations,
two rooms per channel (twelve total), 25 scope links, 25 active staff and 64 KiB of text. Native push
has no free-profile device or staff cap: it keeps the mobile delivery behaviour on every profile.
Oversized intents refuse before an effect; partially dispatched fanout retains its ambiguity marker.
The [supervised recovery commands](cloud-recovery.md) require exact attempt evidence rather than age-based
claim takeover. These admission limits apply only to the free managed profile.

Object accounting samples current and retained versions plus incomplete multipart parts with durable
cursors. New writes reserve capacity before effects. Confirmed deletion is credited once by receipt;
unknown or stale usage refuses admission and remains visible. Only a drained physical inventory can
fold old browser-upload reservations. `reconcile_cloud_storage` performs that supervised operation.
Mail shows accepted, reserved, uncertain and pending separately per configured account. An uncertain send
stays charged across retries; `reconcile_cloud_email` requires independent provider nonacceptance or
acceptance evidence and a current platform operator. Account aliases cannot create another allowance.

Every Events scheduled task (admission, contributors, broadcasts, assets, certificates, print and
judging recovery, stage forms and files, reimbursement deadlines, payout recovery/retention, saved
details) runs through the free tick under its own catalog key. Each sweep sizes its batch with
`bounded.rows`: unchanged on a full server, the chunk's remaining limit inside a tick, and one row per
chunk for scans, renders, validation and object I/O; unfinished work resumes on the next tick. Scans,
renders and validation are heavy tasks, so at most one starts per tick. The older programme wrappers
stay unselected (`CLOUD_PROGRAMMES` is empty) because these keys already cover the same work, and the
boot guard refuses selecting them while those keys are scheduled. Provider/VM/browser/Docker
acceptance remains required before launch.

Sources checked 2026-10-18: [Render free services](https://render.com/docs/free),
[Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres),
[Cloudflare limits](https://developers.cloudflare.com/workers/platform/limits/).

## New in 0.12.0

See [the 0.12.0 settings](cloud-environment.md#new-settings-in-0120) and [choose your hosting](../choose-your-hosting.md). Free renders the same non-secret 0.12.0 defaults as full. The breach check and card font downloads make outbound calls that count against cold-start time; set `CARD_FONT_DOWNLOADS_ENABLED=False` to keep cards to the bundled faces. Photo clean-up is not available on free (no durable shared storage for the model); there is no live process, so the console polls.
