# Cloud integration contracts, version 1

Frozen on 2026-10-18 as the first step of the cloud integration order. The binding
source is the approved cloud plan (sections 2–8 and 11). One decision matters here:
the HTTP scheduler is free-only. These files describe interfaces for
parallel implementation; they do not certify managed deployment.

They were written on the `cloud/integration` branch. No incoming Pages,
Events or reimbursement delta is incorporated. The historical 63-failure ledger
is not a fresh baseline run. No container or Django run was part of freezing these contracts.

## Files every implementation consumes

* `backend/cloud_contracts/deployment.py`: dependency-free selectors. M calls
  `parse_selection(os.environ)` before Django and maps ValueError to exit 78;
  this parser does not replace M's admission/role/recovery checks.
* `backend/cloud_contracts/jobs.py`: `PeriodicJob`, `ChunkContext`, `ChunkRunner`,
  `ChunkResult`, `TickResponse`. J owns execution; I adapts domain call sites later.
* `backend/cloud_contracts/usage.py`: `UsageMetric`, `QuotaSnapshot`,
  `TickFreshness`, `EmailBudgetConfig`, `MailReservation`, `MailBudget`.
* `backend/cloud_contracts/dependencies.py`: frozen dependency names, not runtime
  discovery or evidence of implementation. Owners send explicit corrections to I.
* `deploy/contracts/{baseline,environment,models,programmes}.json`: checked merge
  artifacts. Reserved model declarations are **not** Django models or migrations.
* `deploy/contracts/free-tick.openapi.json`: tick wire contract; I regenerates both
  actual schema/client variants later. Never hand-edit the generated frontend files.

These new paths are I-owned ownership expansions. `backend/config/cloud_settings/**`
is also I-owned. None expands permission into M/S/E/J/V/R/F/Q namespaces. All
other ownership remains exactly the plan's section 11 table. Tests added here are
local-only under `backend/tests/cloud/profile_integration/`.

## Selectors and shared wiring

Missing selectors mean `host` + `full`. Empty/unknown values and `host+free` refuse.
`MANAGED_POSTGRES` controls database privileges; `PLATFORM_DOMAIN_SUFFIX` controls
product tenancy. Neither selects launch mode/profile. M still rejects changed-mode
recovery bypasses and free resident roles. One image runs every profile; the selectors pick it.

Legacy host/full with no `CLOUD_TASK_PROFILE`/`CLOUD_SCHEDULER` keeps its exact
broker fallback, cache selection, eager setting, schedules and imports. Managed or
explicit task selection validates a coherent Redis or brokerless configuration.
`CLOUD_SCHEDULER=beat|loop|external|tick`; Redis uses beat, full brokerless uses
loop/external, free uses tick. Defaults for newly selected managed paths are
Redis+beat when a broker is present, otherwise brokerless+loop. Free selects
brokerless+tick. Empty broker/cache/live/result and eager=true are mandatory for
brokerless. No legacy Redis fallback there. Shared DB cache and polling remain.

All `FREE_*` values, even malformed values and a set secret, are unread under full.
Free settings bounds: interval 60–86400 s (default 600), budget 1–20 s (20), rate
1–60/min (6). Absent caps mean unknown, never zero/unlimited/healthy. R refuses
setup completion without explicit verified DB/object/mail caps; E refuses sending
without an applicable verified account budget. The tick secret may be absent to
disable the route (view returns 404). R generates >=32 random bytes, URL-safe ASCII,
once, keeps it only in protected backend/trigger stores, and preserves on rerun.
The tick secret and launch/task selectors are explicitly EXCLUDED from backup
setting comparison; the secret remains marked secret-bearing. This preserves old
full archives without inventing a new restore-blocking continuity requirement.

M exports `config.cloud_database.configure_database(*, database, env) -> dict`.
It is settings-time, query-free validation/transport configuration. It retains TLS,
requires direct/session mode, refuses known transaction endpoints, separates runtime
from maintenance credentials and never logs a DSN. Admission/probes occur later.
M exports `apps.backup.managed.admission.assert_managed_admission(*, role) -> dict`
for ordinary service/command boundaries: it raises on refusal and returns only safe
non-secret admission facts. It re-reads primary DB/recovery/identity/privilege facts;
neither this function nor configure_database may create a recovery singleton/adopt
an identity for an ordinary process. The finite release/adopt command owns that.

E exports `apps.integrations.mail_providers.settings.email_settings(*, env) -> dict`
with required `EMAIL_BACKEND` and optional `ANYMAIL` settings. It validates the fixed
provider enum/config file, rejects arbitrary backend paths/config keys and returns
only mail settings. No send/probe/query at import. Empty `EMAIL_PROVIDER` preserves
the old SMTP/console selection exactly. HTTP selection adds `anymail` to installed
apps and uses django-anymail 15.2..<16 (existing boto3 covers SES). No webhook is
implicitly enabled. Dependency preparation follows the
[Anymail installation contract](https://anymail.dev/en/stable/installation/).

J exports `apps.operations.cloud_jobs.discovery.task_modules() -> tuple[str, ...]`
and `catalog.periodic_jobs() -> tuple[PeriodicJob, ...]`, query-free. Discovery names
only installed/active task modules, never tick handlers under full. Celery consumes
`CELERY_IMPORTS` through its existing namespaced settings loader. Beat/CLI/external
and tick project the same catalog; free does not run the existing whole beat sweeps.
Default full schedule values remain untouched in this preparation.

Explicit cloud settings require the reviewed M/E/J implementations. Missing imports
raise ImproperlyConfigured, with no permissive fallback. This step alone is not a
bootable managed/free release. Compose preparation is in separate standalone files;
do not layer either onto the legacy host files.

## Tick and checkpoints (J with I models/schema)

Only free mounts `apps.operations.cloud_jobs.tick_urls`, at
`api/v1/internal/free/`; J declares leaf `tick`, name `free-tick`, no trailing slash.
The full branch returns before any import/include of J. J defensively checks free
again. HTTPS POST with `X-Cron-Secret`; unset configured secret -> 404; missing,
wrong or non-ASCII supplied secret -> generic 403; mounted non-POST -> 405.
Accept no command/task selection. Empty request body or `{}` only; ingress bound
1024 bytes. Never put a secret in query/body/URL/frontend/logs. Schema marks
Internal, `x-internal`, header API-key security; statuses 200/400/403/404/405/413/415/429/503.
Retry-After is an integer number of seconds on 429/503. Repeated authenticated
calls only check due work. Failure of PostgreSQL rate/admission state returns 503
before work. Invalid-auth rejection is bounded independently of the authenticated
atomic counter. Secret rotation replaces both backend and trigger secret followed
by restart/redeploy; old secret then fails without disclosing either value.

J uses a dedicated guard transaction for the **whole chunk**,
`pg_try_advisory_xact_lock(namespace, stable_key)`; namespace `1129075787`
(`0x434C544B`, CLTK). Stable key: signed big-endian first four bytes of SHA-256
of UTF-8 catalog key. A rare collision serializes unrelated jobs safely. This does
not conflict with or replace admitted domain session locks such as audit anchoring.
The guard transaction has no domain row locks and no business writes. Short
separate transactions CAS attempt/generation/checkpoint state. A committed
PeriodicTaskRun claim or expired lease alone is never execution authority.

`ChunkContext.check_active()` checks guard health, current attempt/generation and
domain admission before every effect. Guard loss cancels/fences; no reconnect and
continue. Uncertain attempts block takeover until termination or safe domain
idempotent reconciliation is proved. Remote acceptance can remain uncertain even
after process death. Domain provider receipts/idempotency and late-delete receipts
remain authoritative; no exactly-once mail promise.

Use monotonic remaining time for every DB/network operation; reserve response
headroom, do no post-response work. One heavy chunk at a time. Checkpoints contain
opaque IDs/cursors/private object locators and bounded JSON, never PII, credentials,
signed URLs or local paths; maximum serialized checkpoint 16384 bytes. A chunk
result with remaining pages is deferred and remains due; completed advances only
after the whole logical sweep. J rotates overdue work and reserves reminder,
outbox and retained-safety capacity. Each job declares bounded/resumable/unavailable,
an exact reason for refusal, and deliberate first-run due semantics.

Track contact and successful progress separately. Respond with `TickResponse`,
safe reason codes (max 64, max length 100), <64 KB JSON. Budget deferral/no-due is
200; task failures or admission/DB/service failures are 503, retaining successful
checkpoints. Audit sanitized summaries via `apps.audit.services.record`, not secret
or tenant data. Retain operational detail 30 days; keep current progress/uncertainty
and budget/reconciliation receipts as long as needed; never prune immutable audit.

## Outbox and quota (E/S/J -> I -> F)

E `budget.reserve(*, config, delivery_key, recipients, now) -> MailReservation`
and `budget.settle(*, reservation_id, outcome) -> None` implement the MailBudget
protocol. Stable delivery key survives retries; account key is an opaque shared
provider-account alias, never tenant ID/API key. All platform/tenant/OTP/retry paths
reserve atomically against daily and monthly windows, billed recipient units,
active reservations and uncertainty. Reset timezone is IANA; calendar day/month
comes from provider semantics, not server midnight. Definite nonacceptance releases;
accepted and uncertain consume allowance. Unknown config fails closed.

E `outbox.drain_chunk(*, context, checkpoint, limit) -> ChunkResult` invokes existing
owning delivery services. I wires existing outbox/retry/flush command seams later.
Budget exhaustion defers eligible rows until reset with a safe reason; it is not
a bounce/final failure. Expired auth proofs never send late; their owning OTP/reset
flow must cancel/replace them. Minimized keyless platform bodies are not persisted
to bypass existing PII policy. Full ignores this new free budget completely.
Provider-account budget config lives in the provider config file's `free_budget`
object using EmailBudgetConfig fields; tenant accounts carry the same typed encrypted
config. `FREE_EMAIL_DAILY_CAP` is the deployment default account's configured cap;
it must agree with that account config. Reused account aliases share one allowance.

S `accounting.sample_usage(*, context, checkpoint, limit) -> ChunkResult` performs
incremental reconciliation, not a full bucket listing per request/tick. I keeps
usage samples/physical receipts; confirmed finalized private/public/staging bytes,
unfinalized reservations and uncertainty remain distinct. Credit deletion exactly
once, only after confirmed absence including required versions. Unknown/stale
provider scope cannot appear healthy or zero. S capabilities are independent facts,
not provider-name presets or “POST absent therefore no versioning”.
S's descriptor export `descriptors.StorageCapabilities` reports independent
`presigned_post`, `presigned_put`, `versioning`, `list_versions`,
`delete_versions`, `object_lock`, `conditional_create`, `copy_object`,
`multipart`, `privacy` facts (supported/unsupported/unknown), plus `observed_at`
and safe `source`. Unknown facts never grant a guarantee. Its existing probe/file
schema remains S-owned; send the exact serialized shape to I/R before wiring it.

I `cloud_quotas.services.snapshot(*, actor, makerspace_id=None, now) -> QuotaSnapshot | None`
uses accounts/rbac scoping. Superadmin sees deployment totals; staff sees tenant
usage and safe deployment warnings (database=null), never another tenant/account's
counts. Full returns no free projection and performs no new quota queries. F consumes
the safe types as an optional `deployment` field on existing authenticated config/
staff health responses (I final mounts); public health gets no infrastructure data.
Warning thresholds >=70%, >=90%, >=100%; unknown/stale take precedence. Compute tick
age at request time from durable completion; >3x interval is late, no completion is
never. Show failed tasks separately from contact. Source/unit/date labels and
cold-start/best-effort/scanner notices remain visible and accessible in both themes.
Cap source and verification date are separate from usage source/sample time;
I persists them on the usage/config record from R's verified setup evidence.

## Release gates and handoff

`programmes.json` deliberately marks incoming sections pending. It is a checked
merge inventory, not a runtime plugin mechanism. Final integration must reject any
pending/missing actual hooks, unresolved model manifests or unimplemented chunk
adapters. No free endpoint/recipe release before real guard-loss/concurrency/resume,
512 MB and 0.1 CPU workload, full isolation and live primary Worker evidence.
Managed archives remain archive-and-purge custody records with no restore reader.
Portable dumps and provider recovery retain the approved distinct capabilities.

Step 1 does not create a migration, change generated schema/client/catalog hash,
publish a recipe/image, commit, stage or merge. Actual runtime tests
remain later gates; no provider prices or free-allowance promises are certified here.


## Integration step 2 schema update

The provisional FreeTickRun/FreeTaskProgress/FreeTaskAttempt/FreeMailBudgetWindow/FreeMailReservation names
are replaced by actual J/E journal/account models in deploy/contracts/models.json. Literal field snapshot:
deploy/contracts/cloud-model-fields.json. No parallel provisional tables are registered. The final M database
hook is config.cloud_database.django.managed_database_configuration; discovery consumes J's periodic_catalog.
Source-local fields keep explicit export/portable-dump dispositions.

Exactly two images are published: spaceworks-backend and spaceworks-frontend. The
backend `release` target adds scripts/cloud_setup under /app/scripts from the BuildKit named context
cloud_tooling (the repository root); the default `full` target is the plain source build. The one image runs
host/full, managed/full and managed/free: in managed mode the common entrypoint hands over to
cloud_entrypoint for secret materialization and generation capture before M's role/admission checks.
Recipes select one verified immutable spaceworks-backend digest.

Cross-owner blockers include M's SQL-function catalogue entry for operations_storage_capability_guard and
finite diagnostic allowlist, J's launcher and domain/free adapters, and R's exact bootstrap argv/descriptor
alignment. These are blockers, not implicit ownership overrides. Incoming programmes remain inactive until reviewed.
