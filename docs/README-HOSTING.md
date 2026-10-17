## Roles & access

Access is scoped **per makerspace and per action**. Super Admin is global; every other role is a
per-makerspace membership.

Authority comes from **actions, not role names**. Each makerspace has seven fixed built-in role
instances. Their names and grants cannot be edited, and roles cannot be created or deleted.

| Role | What it can do |
|---|---|
| **Space Manager** | Administers the makerspace, staff, settings, inventory, machines, events, bookings, membership and finance |
| **Inventory Manager** | Runs the full hardware lifecycle, inventory, QR, evidence and audit; no machines, staff or settings |
| **Machine Manager** | Manages machines, service work, maintenance and usage within this person's assigned machine types |
| **Event Manager** | Manages events, registrations, event reports and email templates |
| **Booking Manager** | Manages bookable spaces, bookings, booking rules, reports and email templates |
| **Handover** | Issues accepted requests/direct handouts, takes returns, uploads evidence and collects completed machine jobs |
| **Member** | Uses community services without staff management actions |

A membership has a primary role and optional additional roles. **Space Manager and Member must each
stand alone**; the other five combine freely, such as Event Manager + Booking Manager. The console
assigns the complete set on a separate tenant staff account with checkboxes. Initial-setup invitations
snapshot the full role set and machine scopes. With platform access on, only the superadmin manages
Space Managers; with it off, another local Space Manager may manage them. Never self or the last active
Space Manager. Members cannot receive built-in staff roles. Staff resets are admin-issued; staff and
platform sign-in uses password (+ local authenticator MFA), while delegated helpers use member accounts.

Machine Manager types are assigned **per person**, not per role or individual machine. Save the role
and types together under **Staff & roles**; member accounts cannot become Machine Managers.
No selected types means no machines. A type includes machines added to it later; **All machine types**
selects today's available types, so newly created types need explicit assignment. Space Manager is
exempt and covers future types too. Existing direct type authority and per-machine operator grants
are unchanged.

Handover alone uses the narrow Requests, Direct handout and Job handover console and cannot
accept/reject requests, edit inventory or manage QR. Combining it with other built-ins adds their
actions. Guest Admin and Print Manager remain retired. `transfer_stock` and `manage_staff` remain
superadmin-only, outside the role catalogue. Upgrade from editable/custom roles requires an offline,
irreversible migration: read [the fixed-role upgrade procedure](update-recovery.md#fixed-role-upgrade-2026-10-16)
before running migrations.

**Organizations reach across makerspaces.** A network, a university or a chain can be registered as an
organization, linked to any number of makerspaces as owner, manager or affiliate, and grant member
accounts specific actions across those spaces without tenant staff accounts or memberships. An
organization grant confers **actions, never identity**: an organization administrator can hold
`manage_events` across the network's spaces while being Space Manager of none of them, and staff lists
still show only that space's own people, with a separate read-only view of which organizations reach in.
A makerspace that has hidden itself from the platform superadmin stays hidden — authority cannot be
routed in through an organization.

Outside this system entirely: **Public** users browse, submit requests, and — where enabled —
self-checkout and return eligible QR tools, gated on member presence and photo evidence.

Staff work in the **React console** at `/admin`; the superadmin-only **Django control plane** lives at
`/control/` (backend-only, never exposed on the public port). Two design rules are load-bearing — the
Request Workflow module is the single source of truth for state transitions, and the Inventory
Availability module owns all quantity math. Details in **[.github/CONTRIBUTING.md](../.github/CONTRIBUTING.md)**.

## Hosting

**The goal is to self-host inside the makerspace, on your own server** — your data, your network, no
third party. The [Quick start](../README.md#quick-start) is the recommended path. After it's up:

| Surface | URL |
|---|---|
| Public catalog | `http://localhost` |
| Staff console | `http://localhost/admin` |
| API | `http://localhost/api` (Swagger at `/docs/`) |
| Django control plane | `/control/` on the backend only — **not** exposed on the public port |

Create the first superadmin + makerspace (the wizard does this for you; for a manual instance):

```bash
scripts/spaceworks-compose.sh bundled run --rm --no-deps backend --role management python manage.py setup_instance
```

With no arguments it creates **`superadmin` with a generated password**, prints it once for you to save, and forces a password change on first login. Re-running setup keeps the existing password and does not print it. Supply `--password` or `SETUP_SUPERADMIN_PASSWORD` to choose your own credential. On first creation of the login-methods row, `SETUP_MFA_ENABLED=y|n` and `SETUP_SOCIAL_PROVIDERS=google,apple,github` (or literal `none`) choose the sign-in options. Reruns preserve them; later use `manage.py set_login_methods`. Provider keys are entered in the console.
Guided installs pin the latest published main release from `SPACEWORKS_REPOSITORY`. Updates run through
an optional server GitHub Actions runner after release publication, or `bash scripts/update.sh --force`
as the install owner. Use `--version X.Y.Z-main.<run>.<12-hex sha>` for an exact published main release.
The updater backs up PostgreSQL, pulls pinned images, runs migrations and checks readiness. A failed
deployment attempts application-image rollback; forward schema changes remain applied. Follow your fork
by setting `SPACEWORKS_REPOSITORY=Owner/Repo`; default GHCR image names use its lower-cased owner.
Automatic deploys require Linux/systemd, runner label `spaceworks-prod`, and the repository variable
`SPACEWORKS_DEPLOY=true`. See [Updating](self-hosting.md#updating) for registration and the exact GitHub
steps; read [SECURITY](self-hosting.md#security) before enabling a runner on this public repository.
A fork runs its own release workflow, registers its own runner and enables its own deploy variable.

**No server of your own?** Space Works is multi-tenant — partner with a nearby makerspace to run your space
as a tenant on their instance. **Prefer managed Postgres?** The database URL must live in the versioned
pointer/CAS adapter, never ambient shell state. The Cloud static-environment initializer and D7 provider
callbacks are not implemented yet, so the older Supabase path is suitable only for a non-H1 demo—not a
supported restore topology.

### Split deployment: backend on your server, frontend on Netlify

The installer can configure this split deployment: answer **No, API only** to the website question,
enter your HTTPS site origin(s), and choose automatic Caddy or your existing HTTPS reverse proxy.
It sets CORS/CSRF, the first makerspace's `frontend_domain`, and a persistent API-only compose overlay.
No website container is started or updated. Caddy publishes the API on 80/443; an existing proxy forwards
`https://<API-domain>` to the loopback nginx API edge at `127.0.0.1:8080`, preserving Host and
`X-Forwarded-Proto: https`. `/control/` stays private; live events route to the dedicated backend process.
External S3 storage can also be selected in the same questionnaire, disabling both bundled storage
services. Updates, rollback and restore retain these choices. See [the topology instructions](self-hosting.md#api-only-and-external-storage).

Supported, and `netlify.toml` in the repo root configures it. Netlify builds **only** the React app —
it never touches the Dockerfiles or compose files, and because `frontend/src/generated/api.ts` is
committed, the build never has to reach your server.

Netlify picks up `base = frontend`, `npm run build`, `publish = dist` and `NODE_VERSION = 22` from
that file (Vite 8 needs Node 20.19+/22.12+, and Netlify's default image can be older). It also adds
the catch-all rewrite to `index.html`, without which every deep link — `/m/<slug>`, `/admin/*`,
`/event-check-in/<token>` — 404s on refresh. Set **`VITE_API_URL`** in the Netlify UI to your API,
e.g. `https://api.example.org/api`.

The backend then has to accept a browser on a different origin. Auth already defaults to cross-site
cookies (`AUTH_COOKIE_SAMESITE=None`, `AUTH_COOKIE_SECURE=True`), **which only works if both sides
are HTTPS**:

```env
ENABLE_HTTPS=True
ALLOWED_HOSTS=api.example.org
CORS_ALLOWED_ORIGINS=https://your-site.netlify.app
CSRF_TRUSTED_ORIGINS=https://your-site.netlify.app
```

Three more that are easy to miss:

- **Set each makerspace's `frontend_domain`** to the site's domain. Origin scoping validates it, so
  tenant-scoped routes are rejected without it.
- **Object storage must be addressed publicly.** `AWS_S3_PUBLIC_ENDPOINT_URL` and
  `PUBLIC_IMAGE_BASE_URL` are baked into presigned URLs and every public image `src`, so a
  `localhost` value yields a site that works only from the server console and shows broken images to
  everyone else. On R2 or S3 also set `STORAGE_PRESIGN_METHOD=put`, and allow your site's origin in
  the bucket's CORS rules **in the provider dashboard**.
- **Keep a scheduler.** Hosting the frontend elsewhere does not affect scheduled work, but the
  backend profile you choose does: `docker-compose.prod.yml` runs Celery `beat`, while
  `docker-compose.cloud.yml` has no beat and relies on its `cron` service instead. With neither,
  `.delay()` still runs inline so nothing looks broken, yet return reminders, the evidence-retention
  sweep and event-series extension silently never fire. If you use the cloud profile, drop only its
  `frontend` service — never `cron`.

### Moving a makerspace onto its own server

A space that started as a tenant on someone else's instance can take its data with it. A superadmin
on the source deployment exports that one makerspace — rows, encrypted personal data, and the
space's uploaded files, all inside a single `age`-encrypted archive — and a superadmin on the
destination imports it as a new tenant.

Three things are deliberate, because this moves real accountability records:

- **Whose personal details travel is approved explicitly.** The export lists the exact people whose
  contact details the archive would contain and requires a source superadmin to approve that list.
  Anyone not approved is carried as an opaque reference instead. Approval is bound to that exact
  list, so if it changes the approval no longer counts.
- **Only one deployment is writable at a time.** The source freezes its writes before the final
  snapshot and stays frozen through cutover, so nothing committed after the export can be lost. The
  destination stays closed to users until every file has been copied and verified.
- **The source is archived, not deleted** — and archives are outside the purge guarantee.

Both sides are driven from the staff console; nothing here needs a shell.

Tenant staff travel as new accounts of the imported makerspace with built-in roles, remapped machine
types, active/deactivated status and staff notification preferences. They never adopt an existing
target member or staff identity, even with the same email. Passwords, MFA, sessions, device grants,
chat endpoints and invitations are omitted: a target administrator issues passwords and each chat
connection proves ownership again. Platform audit actors remain inert provenance. See the permanent
[account-split portability contract](account-split-portability.md) for PORTABLE, sovereign Lane D,
purge retirement and the separate sealed-slice deployment-backup rules.
