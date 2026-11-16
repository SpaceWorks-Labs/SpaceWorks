# Decisions: Hosting and installer

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-348 — No-Redis install option stays as opt-in
- **Area:** hosting
- **Date:** 12 November
- **Decision:** The self-host "Redis: none (cron mode)" choice remains an explicit opt-in; the default is bundled Redis, with external Redis also offered. Redis resilience (an outage degrades, never 500s), pinned version, AOF persistence and TLS/password support are kept.
- **Why:** A first decision to remove the option was reversed the same day.
- **Status:** current

### D-295 — Organization workspaces
- **Area:** hosting
- **Date:** 11 November
- **Decision:** An organization without a makerspace (club, society, association) gets its own workspace, a space of kind `organization`, with Events, Memberships, ID cards and Bookings on and Inventory and Machines off by default. Its public page is `/o/<slug>`, it is the organization's home space for D-293, and it can book its own rooms, rooms in linked partner makerspaces, or name outside venues on events. The superadmin can create one, and organizations or makerspaces can request one through self-signup subject to superadmin approval; limits apply as for any space.
- **Why:** Organizations may host events and memberships before they have a makerspace.
- **Status:** current

### D-284 — Per-space quotas and limits for every countable resource
- **Area:** hosting
- **Date:** 11 November
- **Decision:** Monthly quotas apply to events created, bookings created (cancelled still count) and payments on any rail, and every countable per-space resource has a limit key the superadmin can set (single, or bulk up to 50 spaces all-or-nothing with re-sign-in, every change audited). Nothing is enforced until a value is set. Beyond a quota, new items are refused with typed 409s (`event_quota_reached`, `booking_quota_reached`, `payment_quota_reached`), but an existing charge can always still be paid online or offline, refunds work and recording a debt is never blocked. Limits never block reading, exporting, settling, returning items or privacy requests. Storage is counted for every space and limits resolve override, then plan, then none.
- **Why:** The superadmin needs control, while users must never be trapped with an unpayable charge.
- **Status:** current
- **Implemented in:** `backend/apps/managed_hosting/limit_services.py`, `backend/apps/managed_hosting/limit_catalogue.py`

### D-281 — Platform-credential usage limits per space
- **Area:** hosting
- **Date:** 11 November
- **Decision:** Usage of the platform's credentials (email, SMS, WhatsApp, push, wallet passes, and Stripe Connect payments through the platform rail) can be limited per space, counted only on the platform path; a space's own credentials are never limited. Limits live in the per-space override map (monthly count, and payment amount per currency), checks fail open on internal errors, and at a limit messages skip that channel with a recorded reason while the in-app inbox still delivers. The platform payment rail refuses with 409 `platform_rail_limit_reached` while offline settlement and the space's own gateway keep working. Each space chooses its notification channels, whether the platform's credentials may be used when it has none (default on), and its own encrypted credentials. Every limit defaults to none, pinned by a test.
- **Why:** Hosted operators need to bound platform spend without blocking spaces that bring their own credentials.
- **Status:** current
- **Implemented in:** `backend/apps/managed_hosting/platform_limits.py`

### D-262 — Backend image base is Ubuntu 24.04 LTS
- **Area:** hosting
- **Date:** 10 November
- **Decision:** The backend image defaults to Ubuntu 24.04 (noble) via the `BASE_OS=ubuntu-noble|debian-trixie|debian-forky` build argument, with distro Python 3.12 in a venv, pip removed, and PGDG client packages for pg 16 and 17. Trixie and forky remain options; remaining MEDIUM/LOW advisories get per-CVE risk notes and are fixed when Ubuntu publishes fixes.
- **Why:** It had 0 HIGH/CRITICAL findings against real advisory data and passed every smoke check, versus 50 HIGH rows on trixie.
- **Status:** current
- **Implemented in:** `backend/Dockerfile`, `docs/hosting/images.md`

### D-239 — Hybrid self-hosting: every component is an independent choice
- **Area:** hosting
- **Date:** 10 Nov 2026
- **Decision:** The installer lets each component be local (default) or external: website (local, elsewhere, or none for API-only), database (bundled Postgres 16 or external 16-17 such as Supabase, Neon, RDS), Redis (bundled or external URL), file storage (bundled MinIO or any S3-compatible store) and email. The installer tests each external connection before finishing; backups and tenant migration work against an external DB with a version-matched client; poolers need the direct/session connection for migrations and `pg_dump`. Re-running can switch a component with an explicit data-migration step.
- **Why:** Let operators mix providers while staying local by default.
- **Status:** partly superseded by D-348
- **Implemented in:** docs/hosting/hybrid.md, docker/compose.external-db.yml, docker/compose.external-redis.yml, docker/compose.external-storage.yml

### D-236 — Per-space hosting type; every limit defaults to unlimited
- **Area:** hosting
- **Date:** 10 Nov 2026
- **Decision:** The superadmin chooses per space between Own (no plan, limits or hosting billing) and Hosted (plan, limits, trials and hosting billing); superadmin-created and existing spaces are Own, spaces from a host request are Hosted. The install-wide switch only unlocks Hosted and the host form. Every limit defaults to unlimited and applies only when set by a plan or a per-space override; built-in fair-use defaults are suggestions only.
- **Why:** Reason not recorded
- **Status:** current

### D-234 — One deployment mode: self-hosted
- **Area:** hosting
- **Date:** 10 Nov 2026
- **Decision:** There is no separate "managed SaaS" product. Hosting other makerspaces (host requests, subdomains, plans and limits) is an optional capability of any self-hosted install, switched on or off by the superadmin in the platform console (default off), and user-facing text drops "managed" and "SaaS" wording while env keys and `MANAGED_*` overrides remain for compatibility.
- **Why:** The maintainer wanted to avoid complicating the product into two modes.
- **Status:** partly superseded by D-240
- **Implemented in:** docs/hosting/managed-spaces.md

### D-233 — Full cloud hosting scope and providers
- **Area:** hosting
- **Date:** 10 Nov 2026
- **Decision:** Existing hosting recipes (Render, Railway, Fly, Koyeb, Cloud Run, DigitalOcean, Oracle, Kubernetes/Helm, Cloudflare/Vercel/Netlify) are kept and AWS, Azure and Hetzner/Coolify are added, plus a mix-and-match guide (any compute plus any managed Postgres, S3-compatible storage and email provider). Without provider accounts, full, split and free shapes are booted locally and every recipe is statically validated. Each recipe documents Full vs API-only.
- **Why:** Reason not recorded
- **Status:** partly superseded by D-234
- **Implemented in:** docs/hosting/cloud.md, docs/hosting/hybrid.md

### D-232 — Standard curl one-line installer
- **Area:** hosting
- **Date:** 10 Nov 2026
- **Decision:** The installer is `curl -fsSL https://github.com/SpaceWorks-Labs/SpaceWorks/releases/latest/download/install.sh | sh` (a tag-pinned URL also works; options via `sh -s -- --frontend api-only` or env vars). Every release publishes `install.sh`, a versioned bundle tarball, `SHA256SUMS` and a keyless cosign signature; the installer always verifies the checksum and the signature when cosign is available. It is POSIX sh with its whole body in `main()` so a truncated download never runs, has OS/Docker/disk/RAM preflight, `--dry-run`, `--version`, `--uninstall` and `--help`, and re-running it updates (forward-only).
- **Why:** Follow the pattern used by common tools (Docker, Tailscale, rustup).
- **Status:** current
- **Implemented in:** install.sh, scripts/release-assets.sh, .github/workflows/release.yml

### D-220 — Install, designer font and machine follow-ups
- **Area:** hosting
- **Date:** 9 Nov 2026
- **Decision:** The installer keeps the setup-areas questionnaire, Full/API-only choice and domain/email with Enter defaults, and is Linux/macOS only (setup.ps1 is a dev helper). Designers get a real `Outfit` font family with a data migration from `Gilroy`. Machine-time bookings and sessions can report a problem, technicians get the maintenance calendar feed for machines they cover, and lockout and queue ETA use the space's local date. Offsite backup retire, key rotation, push and rehydrate need a recent server-owned reauthentication.
- **Why:** Reason not recorded
- **Status:** partly superseded by D-232

### D-197e — Hosting defaults: compose passes switches and identity only
- **Area:** hosting
- **Date:** 5 Nov 2026
- **Decision:** Compose passes the release switches, secrets and identity keys only; tuning knobs stay at settings defaults. Turnstile and VAPID secrets stay out of blueprints and wizard defaults, `WALLET_*` is not passed (it needs mounted files), `MANAGED_*` stay off by omission and the installer never asks, photo clean-up is VPS-only, Helm keeps refusing the free profile, and the self-host superadmin origin is `PUBLIC_APP_BASE_URL` (written by the installer, backfilled by the updater). The row-level-security policy generator treats a NULL nullable last link as a platform row.
- **Why:** Two release blockers found by local boots: RLS hid account rows via the nullable `User.staff_makerspace_id` (every space route answered 401 under the narrow app role), and a default install could not sign the superadmin in. Regression runs must include the narrow app role.
- **Status:** current
- **Implemented in:** backend/apps/tenant_rls, docs/hosting/environment.md

### D-194 — Hosting matrix gate
- **Area:** hosting
- **Date:** 5 November
- **Decision:** Every supported hosting shape must install, boot, migrate, serve and update: full VPS (installer and production compose with Caddy), backend VPS with a separate static frontend, frontend-only build, cloud platforms and the free profile, Kubernetes via Helm, and the dormant managed profile. Verification uses `docker compose config`, local boots, `helm lint`, blueprint and env-surface diffs, and checks that release env keys and Celery beat entries exist in each profile. Real paid-cloud deploys are not performed.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `docs/choose-your-hosting.md`

### D-192 — Hide from directory and own domain
- **Area:** hosting
- **Date:** 5 November
- **Decision:** The Space Manager can hide a space from the platform directory, Discover, cross-space search and aggregated stats at any time, independent of a custom domain; the space stays reachable on its own URL. The Space Manager can also set their own frontend domain in any hosting mode, but no CORS, staff-origin or cookie trust is granted until DNS TXT verification passes (a superadmin-set domain on self-host keeps immediate trust). The save-time auto-trust hook was later removed.
- **Why:** A tenant-set trusted origin without proof is a cross-tenant token-theft vector.
- **Status:** current
- **Implemented in:** `backend/apps/makerspaces/domain_verification.py`, `backend/apps/makerspaces/website_directory.py`

### D-187 — Hosting limiter built but off by default
- **Area:** hosting
- **Date:** 5 November
- **Decision:** A hosting-plan limiter exists behind `MANAGED_PLANS_ENABLED` (default off): superadmin-defined plan tiers bundling limits, usage versus limit shown to the Space Manager (warn at 80%, hard stop at 100%), optional trials, and recorded or online hosting billing with optional auto-enforcement. With the switch off nothing is visible or enforced. Self-hosting is the priority and has its own readiness checks.
- **Why:** Built now for later use; self-hosting takes priority for the release.
- **Status:** partly superseded by D-234 and D-236
- **Implemented in:** `backend/apps/managed_hosting/`

### D-185 — Superadmin hosting controls
- **Area:** hosting
- **Date:** 5 November
- **Decision:** The superadmin can suspend a space (reversible, reason recorded, public pages offline, data kept, scheduled jobs stop), set read-only mode, transfer ownership by assigning a new Space Manager, schedule archive and purge (default 90-day grace with reminders), approve host-my-space onboarding requests, send announcements, and see a per-space health card. Hosting plans, trials and billing were not chosen at this point (see D-187).
- **Why:** Reason not recorded
- **Status:** partly superseded by D-187, D-195
- **Implemented in:** `backend/apps/space_controls/`, `backend/apps/hosting_requests/`

### D-107 — GitHub organization rename
- **Area:** hosting
- **Date:** 25 October
- **Decision:** The GitHub organization and container registry namespace moved to SpaceWorks-Labs, and all repo links, image names and install URLs follow. The updater and installer automatically switch a saved old image or repository to the new one on update, with a log record.
- **Why:** The organization was renamed.
- **Status:** current
- **Implemented in:** `scripts/update.sh`, `scripts/spaceworks-repository.sh`

### D-52 — Two published packages
- **Area:** hosting
- **Date:** 20 October
- **Decision:** Exactly two images are published, a frontend and a backend. One backend image runs every process and profile (api, migrate, worker, beat, live; full, managed or free chosen at start-up), while Postgres, Redis and the object store stay official images in compose. There is no all-in-one image.
- **Why:** One image keeps release and verification simple; free hosts accept the larger download.
- **Status:** current

### D-50 — Cloud scheduler and restore behaviour
- **Area:** hosting
- **Date:** 20 October
- **Decision:** In a full-server scheduler pass a failing job keeps the run going, exits 0 and records its last error, while cloud one-off jobs still exit nonzero. Failed or aborted restores expire and clean up their copied material, and only in-flight restores keep it.
- **Why:** Reason not recorded.
- **Status:** current

### D-46 — Hosting requests on a managed platform
- **Area:** hosting
- **Date:** 19 October
- **Decision:** A hosted platform accepts makerspace hosting requests through a public "Host your makerspace" form and through invitations from existing makerspaces or organizations. The superadmin reviews them, and approval only marks the request accepted; the space is then created through the existing creation paths. An invited applicant may join the inviting organization (offered only by someone who can manage that organization's members) or create their own, and the choice pre-fills the creation step without auto-applying. Rejected or withdrawn requests have applicant details wiped after 90 days.
- **Why:** Reason not recorded.
- **Status:** partly superseded by D-190
- **Implemented in:** `backend/apps/hosting_requests`

### D-41a — Free-tier deployment profile
- **Area:** hosting
- **Date:** 18 October
- **Decision:** A complete zero-cost deployment path on free plans exists as an additional, opt-in profile. Full-server deployments keep their behaviour and defaults unchanged, and the free-profile code paths activate only when that profile is selected. The authenticated HTTP "run due jobs" tick endpoint exists only under the free profile (404 otherwise).
- **Why:** Free tiers must be supported without changing full-server installs.
- **Status:** current
- **Implemented in:** `deploy/cloud`, `backend/apps/accounts/route_exemptions.py`

### D-40 — The VPS installer covers everything new
- **Area:** hosting
- **Date:** 18 October
- **Decision:** The VPS install script must work end to end and cover all new features, with changes limited to audited bug fixes so a correctly working full-server install is unchanged. The installer offers the free single-process profile as an opt-in choice; the full profile stays the default and generates the tick secret only when free is chosen.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `scripts/installer`

### D-36a — Cloud hosting is provider-agnostic
- **Area:** hosting
- **Date:** 18 October
- **Decision:** Hosting supports any managed Postgres, any S3-compatible store, any HTTP/SMTP email provider and optional Redis, with recipes for common PaaS and static frontend hosts. Storage supports both limited stores (presigned PUT, no versioning) and full-parity S3 (size policy, versioning, Object Lock), chosen by capability detection and never silently weaker. There is no data-residency requirement, and malware scanning on cloud is off by default with a clear notice and an optional external ClamAV.
- **Why:** The maintainer wanted any cloud service to work.
- **Status:** current
- **Implemented in:** `backend/apps/storage_capabilities`, `deploy/cloud`
