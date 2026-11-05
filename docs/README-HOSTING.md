## Roles & access

Access is scoped **per makerspace and per action**. Super Admin is global; every other role is a
per-makerspace membership.

Authority comes from **actions, not role names**. Each makerspace has nine fixed built-in role
instances. Their names and grants cannot be edited, and roles cannot be created or deleted.

| Role | What it can do |
|---|---|
| **Space Manager** | Administers the makerspace, staff, settings, inventory, machines, events, bookings, membership and finance |
| **Inventory Manager** | Runs the full hardware lifecycle, inventory, QR, evidence and audit; no machines, staff or settings |
| **Machine Manager** | Manages machines, service work, maintenance and usage within this person's assigned machine types |
| **Event Manager** | Manages events, registrations, event reports and email templates |
| **Booking Manager** | Manages bookable spaces, bookings, booking rules, reports and email templates |
| **Handover** | Issues accepted requests/direct handouts, takes returns, uploads evidence and collects completed machine jobs |
| **Technician** | Works the repair jobs assigned to them, runs scheduled maintenance and sets machine service state; no inventory, money or settings |
| **Shop Manager** | Runs the shop: products, stock, prices, orders, the front desk, cash-ups, shop refunds and shop reports; nothing else |
| **Member** | Uses community services without staff management actions |

A membership has a primary role and optional additional roles. **Space Manager and Member must each
stand alone**; the other seven combine freely, such as Event Manager + Booking Manager. There is one
account per person: staff roles are added to a person's own account (a staff-track membership), either
by picking an active member of the space or by an emailed invitation the person accepts while signed in.
Invitations snapshot the full role set and machine scopes. Only the superadmin grants, changes or revokes
the Space Manager role, in every space; nobody changes their own staff roles, and the last active Space
Manager cannot be removed. Anyone with a staff role must use two-step sign-in (an authenticator or a
passkey); a person who gains a role without one gets a single 3-day grace. A Space Manager no longer sets
staff passwords or resets their factors; MFA resets follow the reset rule in `docs/INVARIANTS.md`.

Machine Manager types are assigned **per person**, not per role or individual machine. Save the role
and types together under **Staff & roles**.
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
accounts specific actions across those spaces without staff roles or memberships. An
organization grant confers **actions, never identity**: an organization administrator can hold
`manage_events` across the network's spaces while being Space Manager of none of them, and staff lists
still show only that space's own people, with a separate read-only view of which organizations reach in.
No makerspace can hide from the platform superadmin, who is always on and sees every space.

Outside this system entirely: **Public** users browse, submit requests, and — where enabled —
self-checkout and return eligible QR tools, gated on member presence and photo evidence.

Staff work in the **React console** at `/admin`; the superadmin-only **Django control plane** lives at
`/control/` (server-only by default: the public port answers 404 unless `CONTROL_PLANE_PROXY=true`). Two design rules are load-bearing — the
Request Workflow module is the single source of truth for state transitions, and the Inventory
Availability module owns all quantity math. Details in **[.github/CONTRIBUTING.md](../.github/CONTRIBUTING.md)**.

### Staff sign-in, invitations and recovery

There are no separate staff accounts. A person signs in once (username or email + password, or any
member method the deployment offers) and the console shows the spaces where they hold a staff role.
Staff routes need a verified second factor (an authenticator or a passkey); during the 3-day grace a
banner asks the person to enrol, and a few sensitive screens refuse until they do. Each space can
tighten staff session length, idle timeout, passkey use and a staff IP allow-list; a person gets the
strictest value across the spaces where they are staff.

A Space Manager grants roles to an active member of the space, or sends an emailed invitation. The
invitee accepts it while signed in to their own account, with a fresh code sent to the invited address;
an invitation never creates an account. Revoking a role keeps the person's account and member features.
Only the superadmin grants, changes or revokes the Space Manager role, and only the superadmin can
disable a whole account (web console Platform settings → Accounts, or `/control/` "Disable account"). Nobody changes their own staff roles, and the
last active Space Manager cannot be removed.

Password recovery is the same for everyone with an account: `/reset-password` mails a six-digit code
(the member sign-in screen has no link to it yet). The platform superadmin recovers through the platform
sign-in screen, and the operator keeps a host break-glass command. Member sign-in methods are described
in [Sign-in, identity and borrowing](sign-in-and-borrowing.md).

## Hosting

**The goal is to self-host inside the makerspace, on your own server** — your data, your network, no
third party. The [Quick start](../README.md#quick-start) is the recommended path. After it's up:

| Surface | URL |
|---|---|
| Public catalog | `http://localhost` |
| Staff console | `http://localhost/admin` |
| API | `http://localhost/api` (Swagger at `/docs/`) |
| Django control plane | `/control/`, server-only by default (SSH tunnel or this machine); the public port answers 404 |

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

**Row-level security.** The database also refuses cross-space reads and writes as a backstop to the app's
own scoping, but only when the app connects as a narrow role: one that owns no table, holds no BYPASSRLS and
is not a superuser. The bundled compose and installer already run the app as `spaceworks_app` and migrations
as the owner. On an external database where the app uses the owner role (common on free tiers that cannot
create roles) RLS runs report-only and `/control/` > Row-level security says so; nothing stops working.
`TENANT_RLS_MODE=off` turns it off entirely. Per-space key rotation and emergency re-key are on each
makerspace's `/control/` Keys page.

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

It also sends the security and cache headers the bundled nginx sends (no framing, `nosniff`, a strict
referrer, immutable hashed assets, `no-store` runtime config, revalidated service workers). Link previews
(`/share/`), embeds (`/embed/`), `sitemap.xml`, `robots.txt` and the native-app association files are
pages the backend renders: uncomment the proxy block in `netlify.toml` and put in your API origin, or
those links land on the React app. If Turnstile or web analytics are on, add their origins to a CSP
header there; the nginx image derives them from env and Netlify cannot. Every shape is compared in
[choose your hosting](choose-your-hosting.md).

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

People travel with their staff roles (staff-track memberships with built-in roles, remapped machine
types and their notification preferences). A person created on the target arrives with their
travelled sign-in credentials -- password, authenticator and same-domain passkeys, sealed under the
space's key -- so staff and members can sign in without a reset; a person linked to an existing
target account keeps that account's credentials and gets staff roles only when the superadmin
grants them. Sessions, device grants, chat endpoints and invitations never travel. Merged accounts
travel as inert, PII-free shells and platform audit actors remain inert provenance. See the
[account portability contract](account-portability.md) for PORTABLE, sovereign Lane D, per-space
restore and data export.

Cloud integration: [hosting choices and operational contracts](deploy/cloud-overview.md). Full host defaults remain unchanged; managed/free is explicit and subject to release acceptance gates.
