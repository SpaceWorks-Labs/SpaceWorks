# SpaceWorks project status — what exists today

GitHub member sign-in is available through browser OAuth with PKCE, verified primary email, encrypted platform credentials and lockout guards; it does not issue staff sessions.

> **This is the what-exists-today half of `CLAUDE.md` / `AGENTS.md`.** It was split out when that
> file crossed the harness's memory-file size warning; nothing was dropped in the move. It has no
> `AGENTS.md`-style twin — both names of that document point at this one path, so edit it in place.
>
> This is a description of the shipped platform, not a rule set: the superadmin control plane, the
> security posture, the non-technical installer, the release-title convention, per-tenant
> integrations and overall implementation status. The rules these areas impose live in
> `docs/INVARIANTS.md`; when a feature landed is in `docs/PROJECT-HISTORY.md`.

## 0.12.0 release (in preparation, 2026-11-09)

`VERSION` is `0.12.0` on the release integration branch (`codex/release-0.11.0-integration`). It is not
yet published: the full backend and frontend regressions, the browser suite, the live flow audit and
publication are release gates recorded outside this file. The 0.11.0 candidate was never published and is
folded into 0.12.0; the last published release is 0.9.3. 0.12.0 adds the decision-216 module
interconnections (event/booking loan context, equipment kits, the event–booking link, related facts,
linked finance and loan-context reports) — see the [0.12.0 notes](release-0.12.0.md). Counted from the
code on 2026-11-08 unless noted:

- **Modules and features.** 37 module keys in 12 console areas (6 core); 209 feature keys, of which the
  staff console shows 208 (`machines.integrations` is control-plane only).
- **Roles.** Ten built-in roles: Space Manager, Inventory Manager, Machine Manager, Event Manager,
  Booking Manager, Handover, Technician, Shop Manager, Fundraising and Member.
- **API.** 1,827 OpenAPI paths (2026-11-09); schema version `0.12.0` once `frontend/openapi-schema.json`
  is regenerated.
- **Audit.** 1,311 reviewed audit actions plus 59 shared-service prefixes
  ([audit action reference](audit-action-reference.md)).
- **Help.** 122 English in-app help articles in 13 role sections ([user manuals](USER-MANUALS.md)).

The owner decisions closing the candidate (#203–#210) add the separate **Inventory** page, light mode by
default, per-area public-stat settings, the shared listing banner, Shop pickup fulfilment, listing photos
across areas, own-history links and the uploaded tenant logo in the public header.

## Release 2 (combined tree, 2026-11-05)

Every release-2 lane is merged into one combined tree that became the 0.11.0 candidate, now part of
0.12.0 above. What it adds, in short:

- **Accounts.** One account per person; ten built-in roles (Technician, Shop Manager and Fundraising are new); staff
  roles granted to people or by emailed invitation; mandatory staff two-step sign-in with a 3-day grace;
  passkeys, unusual-sign-in checks, security alerts, IP blocking, Turnstile and breached-password checks;
  per-space security rows with platform locks. Native apps get a clean break (see the
  [mobile PRD](mobile/MOBILE-APP-PRD.md)) and event-role grants for judges, mentors and crew.
- **Money.** The pricing kernel, tax, the finance ledger, refund cases, price-drop refunds, donations and
  sponsors, paid ticketing v2 and venue fees, and the per-space shop.
- **Operations.** ID cards and ID programmes, repairs and the Technician, maintenance under each parent,
  machine sessions, machines and loans depth, the public stats page, the help centre, Google Sheets
  imports and per-space Metabase analytics.
- **Platform.** The superadmin is always on; one backup and restore flow with per-space restore points;
  the Postgres RLS backstop; per-space key rotation and emergency re-key.
- **Django settings.** `config.settings` assembles the domain settings sections and applies deployment
  overrides in order. The release regression with RLS forced on, the end-to-end flow audit and
  README screenshots are separate release gates.

## Events programme status

The hackathon programme (hackathons, Mentor Desk, mentor rounds, volunteering, project gallery) ships as
ordinary per-space switches, off for a new space. Release 2 added applications for any event, review
stages, crew, finalists, prize payouts and team fees. Runtime and browser evidence is recorded by the
release-phase flow audit. See the [closure ledger](events/integration-status.md),
[operator runbook](events/operations.md), [source map](SOURCE-MAP-EVENTS-PROGRAMME.md)
and [acceptance checklist](events/acceptance.md).

## Admin control plane (superadmin-only)

The **Unfold Django admin is the Super Admin's server-side power tool and fallback**, mounted at
**`/control/`** (NOT `/admin/` — that belongs to the React staff console SPA route), locked to superadmins.
Day-to-day platform work is in the web superadmin console, which has a path for every `/control/` write
except host-only ones (`config/control_parity.py`, #190; after the r2-parity-followups lane only
platform/server backup key rotation and the platform-wide re-encryption, the RLS sync, axes recovery and raw
plumbing rows remain host-only). Since 0.12.0 the web console groups that work into platform pages that
open without choosing a space: Platform dashboard, Spaces (with Create makerspace and the requests queue),
Platform analytics, People & access, Platform security, Data & recovery (including offsite backup
destinations, previously `/control/`-only) and Platform settings (`features/staff/platformConsole/`).
The `/control/` sidebar is fourteen ordered groups (Overview, Spaces, People & roles, Inventory, Machines, Events, Bookings, Shop, Money, Messaging & notifications, Integrations & analytics, Limits & hosting, Data & recovery, Security & audit) built
from one catalogue (`config/control_catalog.py`, #188) and its home is a dashboard of totals, items needing
attention and quick links. **It is server-only by default (#189/#191):** with `CONTROL_PLANE_PROXY=false`
`config/control_plane_access.py` answers 404 to everything but loopback and the SSH tunnel, and the website
edges answer 404 too. On supported bundled topologies, `CONTROL_PLANE_PROXY=true` routes `/control/` and
`/mfa/control/` through Caddy or the website nginx; `CONTROL_PLANE_ALLOW_CIDRS` restricts the socket peer
IP (blank allows any peer), never a forwarded client-IP header. The optional TLS-layer
`CONTROL_PLANE_TUNNEL_PORT` instead provides a loopback-only HTTPS listener for an SSH tunnel
(Docker Engine 28+); it works with website exposure off. Apply changes with `scripts/apply-settings.sh`.
SaaS and API-only behind an operator's proxy are excluded from this switch. See the
[control-plane deployment rules](INVARIANTS.md#container--deployment-invariants).
Gated two ways: `config.admin_access.AdminSuperuserOnlyMiddleware` (denies
any authenticated non-superadmin; the `/api/v1/admin/...` React staff APIs are NOT gated) and
`config.admin_access.SuperuserOnlyModelAdmin` (first base of every `ModelAdmin`). Superadmin operations are
Django admin **actions that route through the existing services** (never mutating status directly);
issue/return remain React-only. Superadmin monitoring surfaces (QR ZIP, inline QR/photo previews, print file
downloads) are read-only and guard storage failures.
Since owner decision #115 the superadmin also works in the React staff console as any space's Space
Manager: choose a space and every report, analytics page, export, setting and email surface of that
space opens (person data masked outside a PII window); each `/control/` makerspace page links there,
and the platform dashboard compares and totals the spaces.
On a managed platform the **Hosting requests** model admin (sidebar entry beside Subdomain requests, hidden
on self-host) reviews requests to host a makerspace: read-only rows, Accept/Reject actions (reject needs a
reason that is emailed), and a "Create makerspace" link that re-authenticates and opens the existing Add
makerspace form pre-filled. Nothing is provisioned automatically.

**U-SEC:** django-axes admin-login lockout, scoped `login`/`public_request_submit` throttles + write-only
`website` honeypot on public submit, production-gated security headers, always-on CSP via django-csp 4, and
a `pip-audit` CI job. The global CSP `script-src` omits `'unsafe-eval'`; a tiny
`config.admin_access.AdminCspEvalMiddleware` appends `'unsafe-eval'` to `script-src` **and** the S3 public
origin to `img-src` **only for `/control/` responses** (django-unfold ships eval-requiring Alpine.js; the
JSON API + public docs stay on the strict policy).
Release 2 (lane S-C, #62/#66) adds sign-in protection: automatic IP blocking against credential stuffing
(one address failing against 10 different accounts in 15 minutes is blocked for an hour), superadmin
allow/deny rules and the automatic-block list in `/control/`, the Have I Been Pwned breached-password
check (k-anonymity, fail-open) on every password a person or admin sets, optional Cloudflare Turnstile
after failed sign-ins (off until keys; the SPA CSP allows `challenges.cloudflare.com` only then), and the
per-space staff IP allow-list and CAPTCHA settings. Host recovery: `manage.py login_security --list |
--allow <cidr> | --unblock <ip|all>` beside `axes_reset_ip` and `recover_superadmin --reset-mfa`. Rules
are under **IP blocking, allow/deny rules and CAPTCHA** in `docs/INVARIANTS.md`.

**Staff MFA and invitations.** Since release 2 (lane S-A, owner decision #62) two-step sign-in is
**mandatory for every staff role in every space** (an authenticator app or a passkey); it is a platform
rule, not a setting, and the old `security.staff_mfa_required` switch is retired (makerspaces 0119). A
person who gains a staff role without a factor gets a 3-day grace, then staff screens refuse
(`mfa_enrollment_required`) until they enrol; member features never block (#128 C-1). The superadmin
stays optional (password-only until they enroll) and members opt in. Passkeys (WebAuthn, web only)
sign people in and count as the staff factor. The MFA-reset rule, `staff_mfa_readiness` and the details
are in **Login security** in `docs/INVARIANTS.md`.
When MFA applies, enrolled password, phone and native password sign-ins return an
opaque five-minute challenge before issuing tokens. Identity-provider sign-ins (Google,
Apple and configured OIDC) skip local TOTP for members only and carry provider proof, which never
satisfies a staff route. The platform login-method setting `mfa_enabled` defaults on and governs
MEMBER opt-in only: switching it off pauses member enrollment/recovery regeneration without clearing
credentials, and never pauses staff MFA.
Sessions minted while bypassing a challenge are refused when MFA is re-enabled, including
rotated native sessions and Django control sessions; verified and provider sessions retain
credential-version revocation. A locked credential
accepts a +/-1 time-step window and refuses replay. Ten recovery codes are hashed and
shown once; regeneration and optional disable require password reauthentication.
Secrets and enrollment keys use the existing Fernet mechanism. Credential versions
invalidate older access, refresh, device and control-panel sessions. `/mfa/control/`
finishes the Django password session of an enrolled superadmin before `/control/` becomes
accessible. Operators can recover a lost superadmin authenticator with host-only
`recover_superadmin --reset-mfa`; this clears the credential and sessions and returns the
account to password sign-in until it enrolls again (superadmin MFA is optional). A superadmin
can also reset a forgotten password by emailed OTP through the platform context
(`/admin/reset-password?context=platform`): it needs platform mail configured and a request
Origin in `PLATFORM_STAFF_ORIGINS`, and is re-checked at confirmation. The member-context flow
still discards superadmin accounts. Host-side `changepassword` / `recover_superadmin` remain
the out-of-band path when platform mail is unavailable.
Spent MFA challenges join the existing 30-day auth-challenge cleanup.

`staff.invitations` defaults on. Staff with makerspace-management authority invite an
address to a permitted local role, list/revoke/resend invitations in Users, and receive
a copyable link even when tenant email delivery is unavailable. Email addresses are
encrypted, tokens are stored as digests, resend rotates the bearer and rechecks the
current sender's authority, and acceptance is
single use. Existing accounts prove their current password and, while platform MFA is on, enrolled MFA; new
accounts receive a verified address. Both get the same response with no session tokens.
Acceptance rechecks tenant servability, role grants and the inviter's current ceiling;
revoked, restricted, walk-in and imported-stub principals cannot regain authority.
Management and public acceptance are throttled and audited. Credentials, challenges
and invitation grants are omitted from portable tenant dumps; staff must be invited
again on the target deployment. See the [environment reference](environment-reference.md)
for deployment budgets and timings.

**Django admin coverage** is complete (every domain model registered; immutable/workflow-owned models
read-only; a `list_filter` per makerspace-scoped admin). The Unfold sidebar (`config/unfold.py`) is curated
into grouped sections and a test asserts every sidebar link resolves. `tests/test_admin_hidden_scope.py`
walks every registered admin and forces an explicit scoped/global decision (via `NESTED_MAKERSPACE_LOOKUPS`
/ `GLOBAL_ADMIN_MODELS`) so a new admin can't silently leak across the superadmin hide/archive scoping.

The superadmin is always on (P1b, owner decisions #110/#111): the `/control/` makerspace list is one
ordinary list, and platform superadmins archive, unarchive, purge and review pending archive requests after
recent control-session reauthentication, always seeing the unsettled-charge counts. Every backup is
encrypted to the platform key; there are no archive recipients, custody states or custody alarms, and the
`backup` module key is retired (managers see a read-only "Last backup" line). The tenant-exit export takes
one-shot `--recipient` keys plus the platform key. `Makerspace.superadmin_access_enabled` is dropped
(`makerspaces/0110`).

**Per-space backup and restore (P1b B2):** every live space gets a nightly one-space archive (raw tenant
slice, encrypted to the platform key and this server's restore key) plus "Back up now"; the superadmin
restores ONE space from its own restore points through preview -> confirm (re-auth + typed slug) -> live
progress, with a mandatory safety backup first, in one transaction with identical ids. The same flow is in
the React Backup & Restore panel (scope picker, timeline, schedule view) and the `/control/` backup
console. Rules: **Per-space backup and restore** in `docs/INVARIANTS.md`. One space from a WHOLE-PLATFORM
backup (#144): the operator decrypts it off the server and `manage.py extract_space_restore_point` adds that
space as an ordinary restore point (docs/self-hosting.md, "Restore one space").

**Non-technical install:** the root `install.sh` curl flow on supported Linux families or Windows Git Bash
(preflight → tagged source archive → published-image pull → `setup.sh` secrets/instance/live module ticks →
version marker), with `SPACEWORKS_DIR` override and an existing-install update/module menu.
The frontend question is **Full** (web app + API) or **API-only** (backend for mobile apps and
integrations; optional website elsewhere), also `--frontend full|api-only`; it is recorded once as
`SPACEWORKS_RUN_FRONTEND=yes|no`, which compose, update and rollback already follow.
Fresh installs pin the newest published, non-draft, non-prerelease GitHub release built from `main`.
Reruns stage that release's updater/helpers, back up the database, then install the closed host runtime
bundle with previous files retained in `backups/host-config-*`. A normal user's install and optional
runner service remain user-owned; a sudo/root install uses root for setup, updates and its version
marker. Host Python is optional except for runner registration: orchestration configuration
uses the backend image, and Compose validation uses that image if host Python 3.10+ is unavailable.
`setup.sh --build` is the explicit source-build path via `docker/compose.build.yml`. Native Windows covers
install/run/update, using the crash-recoverable PID/timestamp update lock when `flock` is unavailable;
restore and compound host recovery stay WSL2-only because they require AF_UNIX sockets and
root-owned-file trust semantics. See
`docs/setup-for-makerspaces.md`. TLS is env-gated (`ENABLE_HTTPS`, default off). First-run
`setup_instance` creates `superadmin` with a generated password printed once + `must_change_password` (surfaced by login + `/auth/me`,
cleared by `/auth/change-password`).

**Releases are titled `SpaceWorks <version>`**, where the git tag is
`vX.Y.Z-main.<run>.<12-hex sha>` and the image/version-marker value omits the leading `v`.

**Production updates** are host operations, triggered by the optional release workflow's self-hosted
GitHub Actions runner or `bash scripts/update.sh --force`. The final deploy job waits for image/release
publication and requires `main` plus repository variable `SPACEWORKS_DEPLOY=true`; it runs the installed
updater with the exact release `--version`, no checkout, no third-party actions and no token permissions.
Setup defaults runner installation to No; Linux/systemd only, verified latest x64/arm64 runner archive,
silent short-lived registration token, and a service running as the install owner. Existing menu updates
do not re-register; `scripts/install-runner.sh` installs/replaces, and `--remove` unregisters.
`SPACEWORKS_REPOSITORY` chooses source/releases and default lower-cased GHCR owner; forks publish their
own releases and register/enable their own runner. Public-repository runners need all external-contributor
approvals and repository/workflow restrictions because Docker access is effectively root; see
[SECURITY](self-hosting.md#security).
The host validates the exact requested release, or selects the newest main release, takes a SQL backup, pulls pinned images, runs
migration/orchestration gates, checks readiness and records `.spaceworks-version`. Successful setup,
update and image rollback remove completed one-shot containers. Failed containers remain for inspection.
Image rollback keeps forward schema migrations and the SQL backup; verified backup/restore features
retain their independent recovery gates and supervisor. See [Updating](self-hosting.md#updating).

**Per-makerspace integrations are backend-only and never leak.** `Makerspace` holds per-tenant
`telegram_bot_token` + `smtp_*`; secrets are encrypted at rest with `API_CLIENT_ENC_KEY` via
`apps/makerspaces/secrets.py` and decrypted only in delivery code. The staff serializer exposes them
**write-only** + a `*_set` boolean. Bootstrap returns only frontend-safe config (module flags, not secrets).
No shared-integration entity exists — makerspaces sharing SMTP/Telegram enter the same credentials per space
(stored/encrypted independently).

**Implementation status.** The multi-frontend platform and open operations/reporting PRDs are implemented
end-to-end (public browse, auth/RBAC, API-client HMAC, QR/box, audit/evidence, 3D Printing Manager, Hardware
Request Workflow, procurement "To Buy", stock transfers incl. true cross-makerspace movement, stocktake,
analytics/ledger/exports, Users CRUD, and the FabLab modules). The detailed PRDs (`docs/prd-*.md`) are
**internal planning docs kept local only** (gitignored); "PRD §N" references point to those. Google Sheets
OAuth publishing remains outside this programme. Native backend contracts and physical device
protocols are implemented; external Android/iOS app builds and real-provider/device release checks
remain separate work. See the [mobile PRD](mobile/MOBILE-APP-PRD.md).

**2026-10-18 reconciliation, as amended by release 2.** Native staff use a staff step-up grant on
the person's own account, fixed to one space, with two-step sign-in and attestation; any person may
delete their account (one account per person). Canonical personal envelopes now incorporate
Twilio SMS, Twilio/Meta WhatsApp, durable STOP/sender history, BSUID correlation and per-device
push with optional inbox links. Reports use canonical delivery/mapped history rather than the
retired addressed send table. Destructive integrations 0043 is unsupplied and sending activation
remains held pending [replay sign-off](notification-reconciliation-rollout.md).

## Observability (phase 0 of the 2026-09-03 forward plan)

**Wave 6 platform monitoring lane (uncommitted; coordinator verification pending).**
The central staff console adds a superadmin-only platform dashboard and read-only
problem checks, plus scoped Usage & limits for makerspace managers. No tenant can be
hidden from the platform (#110). Checks run every 15 minutes in beat and
cron; beat completion telemetry now shares the scheduler journal. Implementation,
thresholds and unsupported MFA/TLS signals: [platform monitoring](platform-monitoring.md).

Every request carries an `X-Request-ID` (honoured from a proxy when it is short plain ASCII, minted
otherwise), bound in `config/request_id.py` and echoed on the response. Log lines are JSON in production
(`config/log_setup.py`; `LOG_JSON` overrides), each stamped with that id, and Celery messages carry it into
the worker (`config/celery_signals.py`). Audit rows are correlated **through the log line**
(`audit_recorded` with the row's `event_uuid`), not by writing the id into `meta`, so the attested record
is unchanged. `GET /api/v1/metrics/` serves Prometheus text behind `METRICS_TOKEN` (404 when unset);
`SENTRY_DSN` opts into error tracking with PII off. Tests run locally before pushing
(`./scripts/dev.sh test`, `./scripts/dev.sh e2e`), not in Actions. The release workflow builds/publishes
backend/frontend images, creates the GitHub Release, promotes rolling tags and optionally deploys via
the self-hosted runner; `security-audit.yml` runs `pip-audit` on PRs.

**Search and live updates (phase 1).** Every inventory, machine and event list accepts `?q=` (full-text with
phrase and exclusion syntax, typo-tolerant on the name) through `apps/inventory/search.py`; the member
directory matches identity fields only. The staff console holds one Server-Sent Events stream
(`/api/v1/live/`, `frontend/src/lib/live.ts`) and invalidates the matching TanStack queries when an audit
row commits, so queues update without polling; the stream runs on the dedicated `live` compose service and
falls back to polling (503) on a deployment without Redis. Public routes are lazy chunks and the eleven
over-ceiling frontend files were split.

**Audit explorer (phase 10).** `/api/v1/admin/audit-logs` keeps its URL, pagination and fields but now
returns catalogue-projected `meta` (unknown or dynamically built actions expose `{}`) plus `action_label`,
`actor_display`, `meta_redacted` and `target_link` (always null), with validated `actor`/`start`/`end`
filters. The request timeline adds `kind=audit` rows and `evidence_retention`. Staff can request an
asynchronous, throttled, bounded integrity verification of a filtered range
(`/api/v1/admin/makerspace/<id>/audit-verifications`), reported as orthogonal MAC / batch / chain / anchor
coverage; the `audit-trail` report is a CSV-only, export-only, unschedulable, tenant-only download.

**Browser and accessibility gates (phase 2).** `frontend/e2e/` (Playwright) drives the loan spine through a
real browser and object storage — `./scripts/dev.sh e2e` locally before pushing — and axe runs in
both jsdom panel tests and Chromium. `manage.py seed_e2e` seeds a disposable makerspace per run.

**Signed webhooks (phase 3).** `webhook` is a notification channel module: a destination with an HTTPS
endpoint and a signing secret receives every matrix-routed notification as signed JSON
(`docs/api-client-protocol.md` → "Outbound webhooks"), through the same delivery log and retries as the
chat channels; failed deliveries can be re-queued from `/control/`.

**Editions (phase 4).** `SPACEWORKS_EDITION` (`makerspace`, `events`, `bookings`,
`organization`) hides the loan or events surfaces and 404s their public routes without changing any
capability (`docs/MODULES.md` → Editions); `events` and `bookings` install profiles match.
The single-box shape and `spaceworks-allinone` image were removed on 2026-10-15;
`.spaceworks-layer=single` is refused by setup, update and the Compose wrapper with
[switch steps](update-recovery.md#moving-off-a-single-box-install).

**Member ID cards and certification gating (phase 5).** A member card is a revocable QR credential over one
membership, printed as a CR80 card or a sheet, resolvable only by staff holding `scan_member_cards`, with a
consent-gated private photo that is deleted the moment the card is revoked (`docs/INVARIANTS.md` → Member ID
cards). `machines.certifications` (a Space-Manager feature switch) requires an unexpired certification per
machine type before a member may book a linked space or request work; an override needs machine-type
authority and a recorded reason. Held certifications print as an optional card field, appear on the maker
profile only after a separate opt-in, and roll up in the `certification-coverage` report row.

**Money and membership depth (phase 6).** Refunds (full or partial, Stripe and Razorpay, as immutable
`payments.Refund` ledger lines), the `payments.loans` feature (deposit raised on issue, capped late fee
raised once at close, optional deposit-blocks-issue gate), membership plans and terms with a beat-less
renewal charge and an optional lapsed-members-cannot-borrow rule, public invitation requests (throttled,
honeypot, PII-encrypted) feeding the existing invitation path, provenance on every report export and
scheduled report delivery to a destination or email list as a signed link. `Warranty.vendor_contact` stays
non-PII by decision 6 (`docs/INVARIANTS.md`). Phases 7–11 are planned and PAUSED by owner instruction.

Stack (in use):

- **Backend:** Django 6 + Django REST Framework (`backend/`). Requires Python 3.12+.
- **Frontend:** React 19 + Vite 8 + TypeScript (`frontend/`). Requires Node 20.19+ / 22.12+.
- **Server-state management:** TanStack Query v5
- **Database:** PostgreSQL 16 (via `docker-compose.yml`)
- **Styling:** Tailwind CSS 4 (CSS-first; `src/index.css` uses `@import "tailwindcss"` + `@config
  "../tailwind.config.ts"`; PostCSS via `@tailwindcss/postcss`) with CSS-variable light/dark theme tokens.
  The theme follows the OS theme until the user chooses; the choice is persisted locally (#77).
- **API documentation:** drf-spectacular / OpenAPI (snapshot `frontend/openapi-schema.json` + generated
  `frontend/src/generated/api.ts`; regenerate both when routes/models change — spectacular needs
  `--format openapi-json`).
- **Admin theme:** django-unfold; site name via `ADMIN_SITE_NAME` (default "Space Works").
- **Telegram:** request alerts and test alerts. Outbound only — the webhook acknowledges and discards
  callbacks; decisions are made in the staff console or `/control/`.


**Phase 7d lane (2026-10-10, uncommitted and awaiting coordinator DB verification).** Added tenant-gated
one-minute offline detection, signed-heartbeat recovery, bounded auth retention, default-off devices
notifications/templates, an identity Devices console and offline failure classification in module
operational health. No public endpoint or report schema added. Printer/label UI requires 7b/7c,
absent from this 7a-based lane. Generated API snapshots remain coordinator-owned.


## Cloud integration in progress (2026-10-18)

The cloud/integration tree contains runtime/database, storage, HTTP mail, jobs/tick, recipes and static/UI lanes.
Shared models/migrations/settings/routes/mail/images/health/panels are being integrated. Defaults remain host/full.
Additional managed/full and managed/free images declare amd64/arm64 with build-time static; no publication occurs here.

All nine cloud/VPS lanes are now combined. Closure source adds durable encrypted object staging, managed
writer/presign drain and supervised reconciliation, bounded catalog/domain/work adapters, physical storage
and provider-account mail accounting, C5 privileged active-database targeting and C17 real scheduler/worker
diagnostics. Full retains its task calendars, cache/queue choices, upload limits and host recovery authority;
the host beat wrapper adds observation with the same persistent schedule.

This is not an AO24/AO25 or launch acceptance pass. Incoming Pages, Events submission runtime and
reimbursement packages are absent here, so those programme entries remain inactive. Real Docker/provider/
VM/browser/recovery evidence remains required. The release process regenerates OpenAPI/client/catalogue hash
in Docker; those generated artifacts were deliberately left untouched. See [hosting](deploy/cloud-overview.md),
[free limits](deploy/cloud-free.md) and [recovery](deploy/cloud-recovery.md).
