# SpaceWorks dev workflow — program state and build conventions

> **This is the how-we-build half of `CLAUDE.md` / `AGENTS.md`.** It was split out when that file
> crossed the harness's memory-file size warning; nothing was dropped in the move. It has no
> `AGENTS.md`-style twin — both names of that document point at this one path, so edit it in place.
>
> Read it before starting a build on this program: it carries the current program state, who does the
> work (Claude agents; Codex is off), the worktree/test-harness conventions and the dev stack and isolated test runner. The
> non-negotiable one-liners are quoted in `CLAUDE.md`; everything else — the *why*, and every trap
> that has already cost a session — is here.

## Current work — FabLab expansion (branch `dev`)

Active multi-part program built on `dev`. It began as a **Codex-driven workflow**; since owner decision
#119 (2026-10-27) Claude agents write, review and fix everything, in parallel worktrees where files do
not collide, and a staging agent merges and verifies. **What has shipped is listed
in `docs/PROJECT-HISTORY.md`** — do not maintain a second copy of that list here.

**Programs already shipped on `dev`**, each with its rules in `docs/INVARIANTS.md` and its dated entry in
`docs/PROJECT-HISTORY.md`: the FabLab modules (Events, Bookings, Maintenance, Analytics/reports, Machine
Manager role, public self-booking + shared custom forms, the notification matrix, scoped PII encryption
H1–H4, historical custom editable roles L, replaced by seven fixed built-ins on 2026-10-16); **Phase C** (capabilities toggles, Stripe payments, advisory geofenced
check-in, custom machine-type config, per-space pricing, Stripe Connect, reconciliation, native device
sessions + push + PaymentSheet, social sign-in); machine-scoped `MANAGE_MACHINES`; deployment-removable
`payments` + install profiles + `suggest_tombstones`; generic OIDC providers; phone + SMS login;
one module key per notification channel; **Notifications v2**; the **module-architecture program**
(operator-facing module groups, the `payments`/`accounts`/`mobile` keys, Razorpay behind a
provider seam, a superadmin modules console, cloud/full deploy profiles and a beat-less scheduler, the
**account-less identity seam + staff-created walk-in members**, **four platform login-method switches**,
**opt-in maker profiles and a member directory**, **staff-side event registration** — its security and
loophole audit is **done and pushed**, `a465a2d`); the **events program** (presence split out of
registration, opt-in attended-events on the maker profile, QR event check-in, cross-makerspace
collaborative events with a host-waiver acceptance); **phases 8, 7, 4 and 5A** (emailed-OTP recovery,
account-less member surfaces, Space-Manager data export, deployment backup/restore); and the
**audit-attestation / API-scope / organizations program** of 2026-08-19 (per-row audit MACs plus signed
Merkle batches, organizations conferring actions across their makerspaces, and a frozen registry of every
protected route behind a `legacy:v1` cutover) — its rules are the two newest sections of
`docs/INVARIANTS.md`.

**Codex is OFF; Claude agents do all the work (owner decision #119, 2026-10-27).** The owner briefly
switched implementation to Codex (#118) and reversed it the same day: every build, plan review, code
review and fix is done by Claude agents, and no Codex run is started unless the owner asks for it
again. Where the global config sends Stage 1, 2 or 4 to `/run-codex`, a Claude agent does that stage.
If Codex is turned back on, check `codex doctor` first; the earlier note that the gates were "LIVE"
went stale for weeks without anyone editing it.

**The commit-trailer rule is attribution, not ceremony:** name Codex in a `Co-Authored-By` trailer only on
work Codex actually wrote. A Codex trailer on work it did not write is false attribution, and that overrides
the unconditional three-trailer rule in the global config — so the trailer set is decided per commit by who
really wrote the code, never by the branch or the program.

Per owner direction, the **single user QA is deferred to the very end** (after all Parts) — no per-Part QA
gate. Commits sit **local and unpushed on
`dev`**; **pushing is the owner's call alone.** Ask `git rev-list --count origin/dev..dev` rather than
trusting any number written here.

**Phase 5B (per-makerspace tenant migration, managed → self-host) is BUILT on `dev`.** All three review
lenses approved `2026-08-16-phase5b-plan-v13.md` after thirteen adversarial rounds, the owner signed off,
and every part is merged. Its load-bearing conclusions are under **Backup, restore and tenant migration** in
`docs/INVARIANTS.md`. The one deferred end-to-end owner QA is still outstanding.

**Review prompts must be scoped to the DELTA once a plan is large.** Two round-13 reviewers ran **6h11m**
(against a normal 5–10 min) still grepping migrations, because they were handed the full ~900-line
cumulative plan plus the standing "verify every claim against the real code" instruction — unbounded when
the document carries hundreds of `file:line` citations. Re-running them against a 48-line `diff -u v12 v13`
plus their prior verdict returned both approvals in minutes.

## Standing build conventions for this program

- **The Codex notes below apply only if the owner turns Codex back on (#119).**
- **Parallel Codex via git worktree.** A second track runs in a sibling worktree (e.g. `../IM-nbuild` on its
  own branch) with a dedicated test DB, so two Codex builds don't collide on shared files (`rbac.py`,
  `origin_scope.py`, `admin_api/urls.py`, `openapi-schema.json`, `api.ts`). Worktrees are fresh checkouts →
  **gitignored files (e.g. `backend/.env`) must be copied in**. Cap at 2 heavy builds. At the end, prepare
  and verify the proposed merge, report exactly what would land, then hand it to the owner. **Only the
  owner merges and pushes.** Keep the worktree until the owner has merged; remove it and its dedicated
  test DB only after that handoff is complete.
- **Codex gotchas.** Run Codex with skill-free prompts that skip reading this file, in the **background**
  (`run_in_background:true`) — the 10-min foreground ceiling is too short. Stage-4 = `codex exec review
  --uncommitted` (no `--sandbox`, no custom prompt; findings at the literal tail). If Codex dies with
  Windows `-1073741502` / "host exited during handshake", it's desktop-heap exhaustion — kill **only** codex
  PIDs (never `node.exe` = harness/MCP); a reboot clears it. **Never `git add`/stage before a Codex
  workspace-write run** — a non-empty staged index makes Codex's `apply_patch` silently fail with a
  misleading "workspace/tests/ is read-only" error and no files written. Keep the index clean during
  implementation; only `git add` right before the Stage-4 `codex review` (so it sees new untracked files),
  then `git reset` before the next Codex build.
- **Test harness.** Run `./scripts/dev.sh test [pytest args]`: every invocation creates a unique
  network and disposable Postgres 16 (tmpfs), Redis and MinIO, with no host ports or shared ops mounts.
  The current repository is mounted at `/workspace`, with pytest in `/workspace/backend`; explicit
  test environment values override any mounted `backend/.env`, and two Fernet keys are generated
  inside `spaceworks-backend`. Build that image with `./scripts/dev.sh up --build` first.
  Cleanup removes all run-labelled containers and the network, including on interruption.
  **Never run two `pytest` procs against one DB** (TRUNCATE-FK teardown races + false concurrency
  failures) and **never run the full suite concurrently with `codex review`** (it runs its own pytest).
  If a background full-suite is killed by the environment, run it as **foreground chunks**
  (`./scripts/dev.sh test tests/<subdirs>`, `tests/test_[a-l]*.py`, `tests/test_[m-z]*.py`).
  **The baseline is ZERO reds** —
  the seven long-standing failures were fixed on 2026-08-12, so any red is a NEW regression, not background
  noise. This bullet once exempted `test_machine_image_presign_finalize_delete_and_audit` as a permitted
  MinIO-host-port failure; that test no longer exists in the tree and the exemption went with it. Do not
  reintroduce a "known failures" allowance without naming the test and the date it was granted.
- **Local dev topology — everything in Docker with live reload.** `./scripts/dev.sh up --build`.
  The gitignored, machine-specific `docker-compose.override.yml` supplies local port remaps; the
  committed dev layer bind-mounts `./backend` and `./frontend`, runs Django with autoreload and
  `DEBUG=True`, and serves Vite with HMR. Frontend :5000; backend, `/control/` and `/docs/` :8000.
  Secrets come from Compose interpolation (`.env` or exported variables). No host virtualenv is needed.
  The infrastructure-only / host backend / host frontend topology has been removed.
  Production-shaped Docker still uses `docker compose up -d --build` (gunicorn + nginx serving the
  baked `dist`); code changes there need a rebuild.

  **`scripts/dev.sh` exists because passing any `-f` to `docker compose` disables the automatic merge
  of `docker-compose.override.yml`.** It spells the chain out as base → override → dev, in that order: the
  override supplies the infrastructure port remaps, and the dev layer must come last so its app-service
  commands, ports and bind mounts win. Other than `up`, `down`, `test` and `e2e`, every argument is
  forwarded verbatim to Compose. Three traps this topology already hit:
  - **The base file hands `backend`'s environment to `migrate`/`worker`/`beat` through a YAML anchor**, so a
    patch to `backend` alone never reaches them — the override applies the MinIO host-port rewrite to all
    four (the Celery worker builds public image URLs into outbound mail).
  - **`tsc -b` must not emit `vite.config.js` next to `vite.config.ts`** — Vite resolves `.js` first, so a
    stale artifact silently shadows the real config; `tsconfig.node.json` therefore emits into
    `node_modules/.tmp/`.
  - **The dev frontend must carry its own `image:` tag** (`spaceworks-frontend-dev`): `frontend` is the only
    service overriding `build.target`, so without it both topologies derive the same `spaceworks-frontend`
    name, whichever built last owns the tag, and a later prod `docker compose up -d` **without `--build`**
    silently runs the dev image — `CMD` is `npm run dev`, nginx never starts, `8080->80` points at a dead
    port, and the container sits **unhealthy while its logs read a perfectly normal "VITE ready"**. The
    instant tell is the port: the dev stage is `FROM deps` (no source), so without the dev layer's
    `./frontend:/app` mount there is no `vite.config.ts` and Vite falls back to its default **:5173**
    instead of the configured **:5000**.
- **Migration heads drift.** Specs quote stale migration numbers; every Codex prompt must
  `ls backend/apps/<app>/migrations/` and chain off the **actual** leaf, not the spec number. A new
  migration whose dep is a rewound app can break migration-executor tests (rewind the full graph forward in
  the test's `finally`).

## Local development

The topology bullet above explains the dev stack and isolated test runner; this section is the commands.

The dev stack and pytest runner need Docker and Bash on the host; e2e also needs Node/npm and Playwright.
Migrations run automatically as a `depends_on: service_completed_successfully` step, so `up` is the
whole story:

```bash
# Everything — db, redis, minio, Django, Celery worker/beat, Vite — with live reload.
./scripts/dev.sh up --build     # first run; drop --build afterwards
./scripts/dev.sh run --rm --no-deps backend --role management python manage.py seed_demo   # first run only
./scripts/dev.sh logs -f backend
./scripts/dev.sh restart worker beat   # Celery has no autoreload
./scripts/dev.sh down

# After changing package.json, recreate the node_modules volume:
./scripts/dev.sh up --build -V frontend

# Tests use their own database owner, generated keys and disposable infrastructure.
./scripts/dev.sh test
./scripts/dev.sh test tests/backup tests/tenant_migration

# Playwright uses the running dev stack (install frontend deps and Chromium first).
./scripts/dev.sh e2e
```

`tests/backup` and `tests/tenant_migration` are **Docker-only in practice**: they need a PostgreSQL
client whose major equals the server's (16), which `postgres_client.client_binary` looks for under
`/usr/lib/postgresql/{major}/bin` or `/usr/pgsql-{major}/bin`. Neither path exists on Arch, so on the
host they all refuse with `PostgresClientUnavailable` — the environment, not a regression. The backend
image installs client 16 *and* 17 on purpose (`pg_dump` must be >= every supported source server;
`pg_restore` must be <= the target, because 17+ emits a `transaction_timeout` GUC that 16 rejects).

After `up`, the dev stack has seven long-running containers (db, redis, minio, backend, worker,
beat, frontend). `up` retires any running `spaceworks-live`, waits for orchestration-init, migrate,
orchestration-ready and createbuckets, and removes those four containers only after successful exits.
A failure keeps the containers and prints a `dev.sh logs <svc>` hint. A later `up` recreates them;
`restart` affects long-running services only. `down` keeps volumes unless you pass `-v`.

- Public inventory page: `http://localhost:5000/m/makerspace`
- API: `http://localhost:8000/api` — Swagger UI at `/docs/`, ReDoc at `/redoc/`, schema at `/schema/`.

## The `live` service (SSE)

`docker-compose.yml` and `docker-compose.prod.yml` run a second backend process, `live`
(`spaceworks-live`), that serves only `/api/v1/live/`: gunicorn `-k gthread --timeout 0` and **no**
`--max-requests`, because recycling a worker severs every open stream. `frontend/nginx.conf` routes
`/api/v1/live/` to it above the `/api/` block with buffering off. The dev layer puts `live` behind the
`prod-only` profile; the Vite proxy sends `/api/v1/live/` to the single runserver, which works for development
but holds a runserver thread per open tab. `LIVE_REDIS_URL` defaults to the Celery broker; empty (or the
eager, broker-less local flow) makes the endpoint answer 503 and the console keeps polling.

## End-to-end tests (Playwright)

`frontend/e2e/` drives a REAL stack — never mocks — and pins the Hard Rules through a browser and a real
presigned upload to object storage. `./scripts/dev.sh up --build`, then `./scripts/dev.sh e2e`
is the local recipe before pushing. Install host frontend dependencies with `cd frontend && npm ci`
and Chromium with `npx playwright install --with-deps chromium` first. The script polls the running
Django :8000 health endpoint and Vite :5000 for up to 60 seconds, runs `seed_e2e --write-json` in
backend, copies the seed JSON to `frontend/e2e/.seed.json`, and passes its native host path to
Playwright. The dev-only login throttle defaults to 200/min because the suite signs in repeatedly
from one IP. Seeding refuses unless `DEBUG` or `E2E_SEED_ALLOWED=1`.

Each seed run creates a fresh random `e2e-<token>` tenant with users and immutable workflow records;
those tenants accumulate in the persistent dev database, isolated from other data. `dev.sh down -v`
wipes that database when wanted. Seed identifiers are loaded by
`frontend/e2e/helpers.ts` from the output of
`backend/apps/operations/management/commands/seed_e2e.py`.

Unit-level accessibility checks use `frontend/src/test/axe.ts` (jsdom cannot compute
colour contrast; `e2e/a11y.spec.ts` covers that in Chromium).

Tests run locally only, before pushing: `./scripts/dev.sh test` and `./scripts/dev.sh e2e`.
Actions builds/publishes backend/frontend images, creates the GitHub Release, promotes rolling tags
and optionally deploys through the self-hosted runner; `security-audit.yml` runs `pip-audit` on PRs.

## CI checks (`.github/workflows/checks.yml`)

The **Checks** workflow runs on every PR into `main` or `dev`, on pushes to `dev`, and by hand. It runs
**checks only** (owner decision #108): the pytest and vitest suites stay local and gitignored, so a green
Checks run is not a test run. Its four jobs are the required status checks on `main`; keep their names:

- **`frontend`** — `npm ci`, `npx tsc -b`, `npm run lint` (ESLint, `frontend/eslint.config.js`: the
  recommended JS and typescript-eslint rules plus the rules of hooks; `exhaustive-deps` only warns, and
  the gitignored test suites are not linted), `npm run build` (which runs the PWA verify script).
- **`backend`** — Python 3.12, `manage.py check`, `manage.py makemigrations --check --dry-run`. Settings
  get dummy values plus keys from `scripts/ci/throwaway_keys.py` (`SECRET_KEY` and the
  Fernet keys, including the mandatory `PII_MASTER_KEY`); no database or service is started.
- **`contracts`** — regenerates the OpenAPI snapshot (`spectacular --format openapi-json`) and fails on
  any diff with `frontend/openapi-schema.json`; reruns `npm run generate:api` and fails if
  `frontend/src/generated/api.ts` changes; runs `validate_catalog()`, so a stale
  `CATALOG_SCHEMA_SHA256` fails here.
- **`rules`** — `scripts/ci/check_rules.py`: the 300-line ceiling over tracked, non-migration, non-test,
  non-generated source files in `backend/apps`, `backend/config` and `frontend/src` (its `ALLOWLIST`
  holds the accepted exceptions, today only `config/settings.py`), plus `CLAUDE.md` == `AGENTS.md`, plus
  no tracked plans, prompts, hand-offs, lane notes or research notes (#148b; `planning_reason` lists the
  folders and note names it refuses, help articles excepted, and `.gitignore` carries the same patterns).

Run the rules locally with `python scripts/ci/check_rules.py` from anywhere in the repo; it measures
tracked files only, so local test trees never affect it. The backend and contracts commands need Linux
(`apps/backup` imports `fcntl`), so run them in a `python:3.12-slim` container or the backend image
rather than a Windows venv, with the same dummy env the workflow sets.
