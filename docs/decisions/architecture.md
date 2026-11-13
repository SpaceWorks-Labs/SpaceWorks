# Decisions: Architecture and data

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-368 — Shared product rules for engineering
- **Area:** architecture
- **Date:** 13 November
- **Decision:** The design system documents rules every product follows: file size (about 200 lines target, 300 ceiling), modules hidden everywhere when off, action-based RBAC with makerspace scoping, tenancy and privacy, audit and evidence, API documentation with the same authority for web and native plus throttles, money, i18n, accessibility, themes, motion and testing. The rules were later generalised to every product, with install and hosting shapes and a per-product status matrix. "Hybrid" hosting means each part (database, Redis, storage, email, website) can be local or external.
- **Why:** Consistency across products.
- **Status:** current

### D-339 — Redis audit and sign-in methods guide
- **Area:** architecture
- **Date:** 12 November
- **Decision:** Every Redis use was inventoried with its behaviour when Redis is down, TTLs, namespacing, TLS and password support, documented in `docs/architecture/redis.md`. Every supported sign-in method was checked end to end and listed in `docs/guide/sign-in-methods.md`.
- **Why:** Redis failure behaviour and sign-in switches must be explicit and consistent.
- **Status:** current
- **Implemented in:** `docs/architecture/redis.md`, `docs/guide/sign-in-methods.md`

### D-337 — Adapter audit, safety auto-off and shelf-check limits
- **Area:** architecture
- **Date:** 11 November
- **Decision:** Staff-issued adapter command leases are audited (`devices.adapter_command_leased`). Safety auto-off runs even in read-only spaces. Shelf checks have a monthly limit (default off) and travel in tenant dumps but not personal data exports. Several loan-context reports, display panels (inventory highlights, sponsors) and a "no Redis, cron mode" install option were built in 0.12.0.
- **Why:** Protecting people takes precedence over read-only state, and shelf checks are the space's operational records.
- **Status:** partly superseded by D-348

### D-332 — Outbound task time limits and safety sweeps
- **Area:** architecture
- **Date:** 11 November
- **Decision:** Adapter webhook delivery, Anthias sync and background-eraser jobs have per-task soft and hard time limits, and the adapter safety and retention sweeps run on free deployments too.
- **Why:** Safety auto-off must run everywhere.
- **Status:** current

### D-330 — Notification, Celery and adapter audit
- **Area:** architecture
- **Date:** 11 November
- **Decision:** Every notification event must be registered, translated, routed, module-gated, preference-aware and deduplicated; every Celery task must be registered, idempotent, time-bounded and tenant-safe; every adapter route must match its schema and OpenAPI. The structure is documented rather than shown on an explainer page.
- **Why:** A single audit closes gaps across background work and notifications.
- **Status:** current
- **Implemented in:** `docs/architecture/notifications.md`, `docs/architecture/background-jobs.md`, `docs/device-adapters/`

### D-305 — AccountProfile implementation and handle claiming
- **Area:** architecture
- **Date:** 11 November
- **Decision:** `AccountProfile` is a OneToOne to the user in the makerspaces profile code, with visibility and section toggles defaulting on and public indexing defaulting off. Legacy `MemberProfile` rows stay read-only this release. The default handle is auto-claimed from the username only when it fits the 3-30 handle grammar, is free and is not reserved; otherwise none is generated.
- **Why:** Implements D-303 and D-304.
- **Status:** partly superseded by D-308 (every account must have a handle)
- **Implemented in:** `backend/apps/makerspaces/account_profile.py`

### D-304 — One global profile per account
- **Area:** architecture
- **Date:** 11 November
- **Decision:** There is one global, account-level profile per user, listing every active space, organization workspace and organization membership (explicit and derived) while omitting revoked, suspended or restricted memberships and hidden spaces. Content is written once and events and verified achievements aggregate across spaces. Legacy per-membership profile rows are migrated into it (merged and deduplicated) and kept read-only; each space's member directory is a per-space projection. The account profile is exported with the account, never in a tenant dump.
- **Why:** One person should have one profile regardless of how many spaces they join; supersedes the per-membership profile model.
- **Status:** current
- **Implemented in:** `backend/apps/makerspaces/account_profile.py`, `backend/apps/makerspaces/account_profile_access.py`

### D-297 — All notifications are sent from Celery
- **Area:** architecture
- **Date:** 11 November
- **Decision:** Every outbound message (email, SMS, WhatsApp, push, chat webhooks, Telegram) is sent from a Celery worker through the outbox/dispatcher, never inline in a request or admin action, with backoff retries and an idempotency key so a retry never double-sends; failures are recorded, not raised. The whole fan-out (recipient resolution, locale rendering, preference and limit checks, inbox rows, delivery) also runs in Celery, enqueued once after commit and ordered per subject. The only synchronous send is the explicit admin test-email action. A guard test blocks new inline sends outside the dispatcher allow-list.
- **Why:** Keeps request flows fast and fail-safe against external-service failure.
- **Status:** current
- **Implemented in:** `backend/apps/notifications/tasks.py`, `backend/apps/notifications/emit.py`

### D-216 — Interconnections built; venue pricing and retention rules
- **Area:** architecture
- **Date:** 9 Nov 2026
- **Decision:** The 18 planned connections are implemented by extending existing seams, with optional Events/Bookings code never a dependency of core lending and request transitions, stock math and ledger ownership staying in their modules. Cancellation of a pickup event or event-to-booking link preserves orders, stock reservations, money, attendance, lending and evidence, and a cancelled pickup event moves the order into staff coordination. Free/paid event registration and free/paid venue booking work independently: registration stays Events-owned, a booking-owned venue cost uses the Booking service's quote and is recorded once in the core ledger (even with the online rail off), and no separate Events venue fee is charged for the same booking. A rejected or cancelled linked reservation shows its real state and a replacement goes through normal booking availability, pricing and approval.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** docs/equipment-contexts.md, docs/MODULES.md

### D-215 — Module interconnection research
- **Area:** architecture
- **Date:** 8 Nov 2026
- **Decision:** Connections among events, bookings, inventory, maintenance, shop, membership, money, notifications and portability are planned with explicit prerequisites and behaviour when either side is off, re-enabled, or removed; recommendations are a backlog, not approval to create a central module owning every domain's state.
- **Why:** Reason not recorded
- **Status:** partly superseded by D-216

### D-201 — Codebase untangle pass must keep the architecture modular
- **Area:** architecture
- **Date:** 6 Nov 2026
- **Decision:** A one-time behaviour-preserving restructure of backend and frontend runs under binding limits: no Django app is merged or split, every module key and separable app keeps its own code, core never imports a separable app and no new core-to-separable dependency is added. `workflow.py`, `availability.py`, `module_registry` and `rbac` keep their single-owner roles, files stay at or under 300 lines using the barrel pattern, frontend feature folders stay per module, and path-pinned guards move with the code. The module-separation matrix must re-run green afterwards.
- **Why:** The maintainer asked that the codebase stay modular after the cleanup.
- **Status:** current
- **Implemented in:** backend/apps/separability, docs/INVARIANTS.md

### D-188 — Restructured /control/ admin
- **Area:** architecture
- **Date:** 5 November
- **Decision:** The Django admin at `/control/` is regrouped into ordered sections (Overview, Makerspaces, Organizations, People and access, Security, Money, Events, Machines, Inventory, Backups, Integrations, Audit, System) with a dashboard of totals and items needing action, plain-language names and help text. A test requires every registered admin model to appear in exactly one section. Behaviour, permissions, re-authentication, PII masking and audit are unchanged.
- **Why:** Make the control plane structured and easier to understand.
- **Status:** current
- **Implemented in:** `backend/config/control_catalog.py`, `backend/config/control_dashboard.py`

### D-160 — Account portability on space moves
- **Area:** architecture
- **Date:** 1 November
- **Decision:** Credentials (password hash, TOTP, recovery digests, passkeys; encrypted) travel on the portable path used by the self-host move; the sovereign exit dump carries the password hash only; sessions and device grants never travel. On a space exit, active staff travel in full and members of several spaces as stubs. An imported person whose email already exists on the target refuses the import until the superadmin decides, and created people start with unverified email.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/tenant_migration/`, `docs/account-portability.md`

### D-144 — Per-space archives and restore
- **Area:** architecture
- **Date:** 30 October
- **Decision:** Per-space archives use the raw lossless tenant slice, while tenant exit to another server uses the portable export. Restoring one space from a whole-platform backup is a host-side command run with the offline platform key, producing a normal per-space restore point re-encrypted to both keys; the platform key never lives on the server. Staff added after a restore point block the restore until the superadmin retires them.
- **Why:** Keeps the platform key off the server; reason for the rest not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/backup/`, `backend/apps/tenant_migration/`

### D-143 — Event embeds have one route
- **Area:** architecture
- **Date:** 30 October
- **Decision:** The `events` kind on the shared website-embed route is retired. Events embed only through the styled card route with its own per-space allow-list, off by default.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/events/embed_policy.py`, `backend/apps/events/urls_embed.py`

### D-89 — Backup host guard and free-profile events jobs
- **Area:** architecture
- **Date:** 24 October
- **Decision:** On a full server, when the deployment-mode binding cannot be read, backup and restore proceed as before; they still refuse when the database positively shows a managed binding, and managed deployments refuse when it is unknown. The free profile runs every Events scheduled task through the free tick via an Events-owned job adapter, leaving full-server beat unchanged.
- **Why:** The scoped exception keeps full-server behaviour unchanged.
- **Status:** current
- **Implemented in:** `backend/apps/events/cloud_runtime.py`

### D-86c — Email bounces have one canonical record
- **Area:** architecture
- **Date:** 23 October
- **Decision:** The mobile `email-bounce-webhook` is the canonical bounce record, and the cloud `email-provider-webhook` forwards into it so both setups record bounces in one place.
- **Why:** Reason not recorded.
- **Status:** current

### D-79 — External Check-In API stays retired
- **Area:** architecture
- **Date:** 22 October
- **Decision:** There is no external Check-In API setup, global or per space, and nothing is planned for it. The leftover `external_checkin_user_id` column and everything reading it are removed.
- **Why:** Requester identity comes from authenticated accounts.
- **Status:** current

### D-75a — Old-decision audit answers
- **Area:** architecture
- **Date:** 22 October
- **Decision:** Machine scope is per machine type, not per machine. Notification object scope applies to every recipient kind (people, roles, rooms, addresses). A Postgres row-level-security backstop is built on tenant tables. The PRD self-accept rule is dropped, so staff may accept their own requests. Translations are English only with a language switcher and translation-ready strings.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/tenant_rls`, `docs/i18n.md`
