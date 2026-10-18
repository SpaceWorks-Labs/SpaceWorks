# Additional free managed stack

Free requires explicit managed+free. It changes no full-server defaults. The primary proposed stack is Render
Free web + Supabase session PostgreSQL 17 + R2 + Resend/Brevo + Cloudflare static Worker/cron. Live account,
512 MB/0.1 CPU and recovery acceptance have NOT passed. Do not call it certified ongoing $0 hosting until
actual caps, card/domain prerequisites, overage controls and deployed measurements are recorded.

Use deploy/cloud/free.answers.example.json, free.env.example and free-provider-limits.json, plus the separate
deploy/render.free.yaml. The dedicated free image omits PostgreSQL tools/ffprobe, bakes static files and runs
uid 10001. Steady state is one sync web worker/thread, DatabaseCache and no Redis/worker/beat/loop/live process.
Heavy intents remain persisted; every job needs a real bounded checkpoint adapter. No scheduled pg_dump or
deployment backup runs. Unsupported video/media validation must refuse before upload acceptance. Scanning is
explicitly off with a visible notice; type/size validation does not scan malware.

Owner decision 43 is approved: POST /api/v1/internal/free/tick, X-Cron-Secret, no caller-selected jobs/body/credentials.
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
the real trigger and FREE_TICK_INTERVAL_SECONDS. Actions schedules can be delayed/disabled; third-party cron
needs current secret-delivery/allowance checks. Cloud Run requires billing/signup validation. Northflank is
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
two rooms per channel (twelve total), 25 scope links, 25 active staff, two push devices and 64 KiB of text.
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

The later Pages, Events submission/media and reimbursement programme packages are absent from this
checkout. Their manifest entries remain inactive; existing Events series, billing and membership tasks
are covered by the current catalog. Provider/VM/browser/Docker acceptance remains required before launch.

Sources checked 2026-10-18: [Render free services](https://render.com/docs/free),
[Supabase connections](https://supabase.com/docs/guides/database/connecting-to-postgres),
[Cloudflare limits](https://developers.cloudflare.com/workers/platform/limits/).
