# SpaceWorks Invariants (do not regress)

> **This is the reference half of `CLAUDE.md` / `AGENTS.md`.** Those two files carry orientation,
> the Hard Rules and the engineering conventions and are loaded into every agent session; this file
> carries the long-form load-bearing rules and is read **per area, on demand** — open the subsection
> covering what you are touching, not the whole document. It was split out when `CLAUDE.md` crossed
> the harness's memory-file size warning; nothing was dropped in the move.
>
> **`CLAUDE.md` and `AGENTS.md` must stay byte-identical to each other.** This file has no twin —
> both of them point at it by path, so edit it in place.

The load-bearing rules, grouped by area. These were established across many shipped batches and matter
beyond any single module. Read the subsection covering what you are touching.

The mobile reconciliation preserves immutable member/staff/platform kinds. Accounts
`0032_account_context` resets development roles only; it is not authorized for live authority data.
Canonical envelopes/configurations and Twilio/Meta providers own personal delivery, including SMS,
WhatsApp and per-device push. Addressed sender, consent, STOP, callback, template and analytics
protections run through that pipeline. Duplicate addressed enqueue/worker entry points are inert
compatibility shims; legacy schema and compatibility ingress remain pending separately verified
retirement. Destructive integrations `0043` is not supplied. Workers/schedulers stay stopped and
sending remains paused until durable ingress, conversion, replay, verification and activation
checkpoints in [the rollout guide](notification-reconciliation-rollout.md) pass.
Documentation is not rollout sign-off.

## Account kinds (member / staff / platform)

These are the account-split owner decisions D1–D12, including approved amendments V1–V12.
They supersede older shared-account, staff social-login and staff-role stripping descriptions
in historical batch notes below. Account identity never changes to obtain another surface.

**Identity and database boundaries (D1–D3, M1–M5, V7/V10).**

- `User.account_kind` is non-null: `member`, `staff` or `platform`. The same person uses separate
  accounts for community activity, each makerspace's staff work and platform administration.
  Staff have a `staff_makerspace` FK with `PROTECT`; kind and tenant are immutable in model and
  database guards, except the retirement/restore transitions below. Platform means both
  `is_superuser=True` and `role=superadmin`; members/staff cannot have those flags (M1/M2).
- Email is case-insensitively unique among members, among platform accounts, and within each
  staff makerspace, independently. A staff email never blocks member signup. Member phone,
  Telegram and legacy external-check-in identities have member-only uniqueness. Username is
  globally unique; staff allocation uses `<handle>.<slug>` (bounded to 150 characters), captured
  at creation and unchanged by a later makerspace slug change (M3).
- A nonretired staff account has exactly one active or revoked membership in its own makerspace,
  with only the six built-in staff roles; Space Manager stands alone, the other five combine.
  Member memberships hold only Member; platform and retired accounts have none (M4).
  `DEFERRABLE INITIALLY DEFERRED` constraint triggers on User, MakerspaceMembership and
  MembershipAdditionalRole validate at commit, including both old and new subjects when links
  move. Deferral permits atomic creation/import/role replacement, never a durable invalid set.
  Object and SQL readers in `accounts/rbac_roles.py` fail closed even before commit; deleting a
  staff membership requires the exact-tenant purge guard.
- Community-owned profiles, cards, terms, waivers, presence, bookings, loans, registrations and
  payments are created for member accounts only. No history or credential moves between a
  person's accounts (M5). Resource event/booking helpers and organization grants/governance stay
  on member accounts (D8); they confer their specific actions, never built-in staff identity.

**Surface policy and simultaneous sessions (D5/D8/D9, V8/V10/V12).**

Staff and platform authentication accepts username/email + password, with local authenticator
MFA where applicable. Social/OIDC/Google/Apple/GitHub, phone OTP, claims and magic-link methods
are member-only. Native member grants use those member methods; native staff grants require a
staff account, password, MFA and attestation and are fixed to its staff tenant. Platform native
grants are forbidden. Member login-method switches
cannot strand staff/platform: their password door remains available. `/control/` accepts only
live platform Django sessions and retains its own MFA/reauth gates and password fallback.
Platform API sign-in requires `PLATFORM_STAFF_ORIGINS`.

Staff password login explicitly supplies `context=staff` and a makerspace slug; a verified
custom origin must agree. Wrong kind/tenant has the generic credential failure. Access/refresh
tokens carry `kind` and, for staff, `makerspace`; kind-less pre-cutover tokens are refused.
`accounts/surface_policy.py` rechecks the live account on access, refresh, MFA completion,
reauthentication and device issuance. Staff stay in their own tenant and cannot enter member
surfaces. Platform accounts reach platform/control operations and authorized staff lifecycle
actions, and (owner decision #115) every `membership-only` or `delegable` staff route outside
`/api/v1/auth/` in every servable space -- see "Superadmin console parity" below. Member-only,
signed-protocol and unknown routes stay closed to them; every kind may use its own classified
account utilities.

`accounts/delegated_routes.py` and `delegated_route_catalog.py` classify staff routes as
`membership-only`, `delegable` or `shared-account-utility`. Unknown routes deny; Django URL
system check `accounts.E001` rejects unclassified/unnamed staff routes. A member reaches a
delegable route only with a live resource grant, organization action grant or organization
governance source in the target scope. The route's ordinary action/resource checks still decide
the operation. A registry entry alone grants nothing, and members cannot enter membership-only
routes. Shared utilities cover only the actor's own profile/password/MFA/personal connections.

Browser contexts are `member`, `staff:<slug>` and `platform`. Refresh/logout explicitly select
one context (omission defaults to member) and validate only that context's cookie. Cookie names
are `refresh_token`, `refresh_token_staff_<slug>` and `refresh_token_platform`; Django control
sessions remain separate. Frontend token stores, refresh promises/generation fences, QueryClients,
reauth queues and offline/staff state are partitioned by context. Sign-out affects that context
only; late responses cannot restore it or replace another account's state. Delegated workspaces
use the member context with `surface=delegated`.

Current integration limitation: cookie names are tenant-specific, but all refresh cookies use
`AUTH_COOKIE_PATH` (`/api/v1/auth/`). The approved slug-specific Path requirement needs endpoint
aliases and matching frontend calls: a slug-specific Path cannot reach the shared refresh/logout
URLs. Do not describe the current implementation as providing slug-specific cookie paths.

**Staff lifecycle and recovery (D2/D4/D6/D7, V2/V6).**

Only a local Space Manager or the platform superadmin creates staff accounts. Only the
superadmin manages Space Managers, in every makerspace (owner decisions #110, #111 Q14); local
Space Managers manage all other staff. No lifecycle action may target self.
Deactivation and demotion lock the tenant and its Space Manager memberships and refuse removal
of the last active Space Manager, including concurrent removals. Removal deactivates and keeps
history; staff membership deletion/self-service leave and member-to-staff attachment are refused.

The lifecycle API under `admin/makerspaces/<id>/staff-accounts/` and `/control/` actions share
services, recent server-owned reauthentication, tenant write gates, quotas and append-only audits.
Generic admin account fields/password/bulk/delete and legacy membership/reset writers cannot
bypass them. There is no application break-glass reset; the operator's server-side management
command remains the platform break-glass recovery surface.

Email onboarding initializes the already-created staff account, never links by email or creates
one on redemption. Invitations bind account ID, full role/machine-scope snapshot and
`credential_generation`. Under locks redemption rechecks the inviter's live authority, matching
snapshots/generation, expiry, active status and unusable password. Resend revokes the old bearer.
Admin password issue and deactivation increment generation and revoke open invitations atomically,
so reset/redemption races cannot install stale credentials. Admin-issued passwords set
`must_change_password`, revoke sessions/grants and are never logged/emailed; generated passwords
are displayed once in a no-store response. Optional authenticator reset consumes pending MFA.
Without Email, Membership, staff invitations or MFA, admin-set initial passwords still work.

Self-service email recovery uses separate `member`, `staff` and `platform` contexts. Envelopes bind
an account, context, staff tenant, trusted request origin and credential generation, never shared-email
ownership. Member recovery remains independent; legacy UID/token links remain member-only. Staff
supply their tenant slug and email or username; platform recovery uses only the platform origin.
Staff/platform recovery requires configured Platform Email at request and issuance, irrespective of
tenant email/modules. Unknown, unavailable, other-kind/tenant and unconfigured requests acknowledge
identically without issuing mail. Staff accounts must be live, unrestricted, have active membership
and a servable, nonmigrating tenant; trusted origin and all live conditions are rechecked at issuance
and confirmation. Mail contains a six-digit OTP and a trusted reset-page URL, never a bearer link;
only verified tenant domains override configured central URLs.

Recovery, invitation redemption, admin password issue and deactivation share the lock order:
Makerspace, account invitations, User, then envelopes. OTP expiry, attempt budget, single use and
credential generation fence concurrent operations. Email confirmation validates the password,
clears `must_change_password` and calls `revoke_sessions_only` once: sessions/device grants and open
invitations end, generation advances once. Established MFA remains enrolled and required on next
sign-in; pre-reset MFA/reauth proofs cannot complete. Staff envelopes of retired staff or of
unservable tenants remain invisible even on the otherwise global operational envelope admin,
including direct object reads.
The operator's host command remains a platform break-glass option.

JWT issuance/rotation and session/device logout lock User before outstanding/blacklist tokens,
session markers or device grants/families; MFA/phone confirmation locks User before its proof.
These token paths take no later tenant/invitation locks.
Issuance rechecks the proved account's credential generation under that lock; rotation rechecks
revocation after waiting. Cookie logout validates CSRF and clears only the selected namespace even
when its refresh credential has expired or already been revoked.

Deactivation revokes the account's Django sessions, outstanding JWTs/browser markers, native
device grants/refresh families and push destinations, station operator leases, pending MFA,
email/phone verification, bound OIDC/GitHub attempts/social nonces, reauth proofs/intents, reset
envelopes, open invitations and personal chat challenges/endpoints. Offline replay refuses inactive
actors and revoked leases. Reactivation restores none of these and leaves an unusable password
until admin issue. Independent HMAC API clients (creator is provenance), hardware devices and
Station credentials remain separate principals.

**Shared chat binding (D10, V3).** Live uniqueness is
`(configuration, identity_digest, user)`: each account proves the shared destination independently.
Signed STOP/opt-out, START/consent renewal and inbound-window facts lock and update all live
bindings of that configuration/digest atomically. Account unlink affects only that account;
delivery callbacks remain delivery-ID-bound. Preferences and recipient envelopes remain account-keyed.

**Transport, retirement and rollout (D11/D12, V4/V5/V9/V11).** Staff travel with their tenant in
PORTABLE and sovereign Lane D exports as new target staff identities, preserving active status,
built-in roles, remapped machine scopes and staff notification preferences. Never link an existing
target account. Passwords, MFA, sessions, device grants, chat endpoints and invitations do not
travel: target staff start with unusable passwords and `must_change_password`; a target admin
issues credentials. Member memberships remain Member; platform attribution is inert provenance.
Full contract: [account-split-portability.md](account-split-portability.md).

Tenant purge retires staff before removing the tenant: scrub name/email/phone/avatar, allocate
`retired-<uuid>` username, revoke credentials, remove MFA secrets, set inactive + `retired_at`, and
clear `staff_makerspace` under `app.account_retirement_makerspace_id` for that exact tenant.
Staff are never hard-deleted. This one-way shell preserves global authentication audit actor IDs,
MACs and signed batch leaves; shells cannot log in or enter exported identity/list results.

Readable-main deployment backups use the same PII-free, inactive same-PK staff shells, never null
AuditLog.actor. Full staff rows and account credential rows reside in sealed tenant slices;
browser sessions are omitted. The registered inert-shell boundary and username reservations
protect delayed slices. Guarded slice restoration checks the exact complete shell, owning restore
component, staged full row, inverse deltas and merge role; ordinary occupied-ID upserts or partial
reversals remain refused. The unserved producer reconstruction clone has its own narrow guard.

This programme is an atomic release, not conversion of mixed production accounts (D12). Rebuild
dev data from separate platform/staff/member seeds; classify existing superusers as platform and
other legacy accounts as member while stripping old built-in staff assignments. Cutover invalidates
existing sessions/refresh credentials. Installer/setup, target restore and host recovery use only
platform operators and never promote an existing member/staff identity.

## Cross-cutting invariants (from shipped batches)

**Analytics measurement ledgers (mobile 1f-1).** Consumable quantities have one finalized
source per operation: pooled service requests at completion/failure (including actual =
reserved, which writes no reconciliation adjustment), manual consume adjustments, and
every non-pool `ServiceRequestConsumption`, including productless grams. Reservations,
corrections, reconciliation deltas and retirements are separate measures; manual usage
grams and printer telemetry must never be added again. Units remain separate.
`ConsumableCostRecord` freezes the contemporaneous pool/product price in the consumption's
own measurement unit and currency minor units, with half-up rounding of the total. Current
prices use major currency units per `cost_unit`; kg/liter/meter prices normalize to
grams/milliliters/millimeters. There is no procurement fallback or historical backfill.
Unpriced consumption stays cost-unknown. Pool and inventory-product price triples are
nullable together. Productless non-pool grams currently have no priced source.

Every runtime machine status writer uses `machines/status_tracking.change_status` under
the existing machine lock: manual change, service start/release, retirement, maintenance.
It appends `MachineStatusEvent` and audit in the same transaction only for real changes.
Before the first observed edge the historical status is unknown. Manual usage may set an
active local `member` and `started_at` at INSERT only; older rows remain unattributed and
the existing UPDATE/DELETE trigger is unchanged. The optional member picker is scoped to
the resolved machine and requires permission to operate it.

Authenticated native activity is unique on `(grant, makerspace-or-NULL, local_day)`, with
NULLs treated as equal. Only the validated selected membership supplies the tenant and
its timezone; unselected requests use NULL and the deployment timezone. The short cache
uses the same triple and is populated after commit. This measures active app sessions
(grants); platform counts deduplicate grants across tenant and NULL observations.

Retained staff matrix push uses `integrations.PushDeliveryAttempt`; canonical personal push
uses envelope-parented `MemberPushDelivery` children and fenced claims. Both stamp
platform/provider source at creation; retries
update attempts on that row and successful destinations are not resent. Staff attempts
snapshot the recipient so device reassignment cannot transfer ownership of history.
Email provider source comes from the actual connection, including platform SMTP fallback;
older unknown values remain blank. Provider message IDs are retained only when returned.
Signed bounce ingress deduplicates `(makerspace, event_id)` and correlates timestamps only
on exact same-tenant message IDs; bounce and complaint timestamps remain independent.
Uncorrelated events still suppress the address. SMS outcomes contain no phone/body;
attestation outcomes contain no identifiers, proof or verifier response. Provider errors
never enter these ledgers as free text.

`InventoryStockSnapshot` is an append-only observation per `(product, local_day)` in the
tenant timezone. It reads quantity buckets through inventory availability, never rebuilds
past days, and measures **days observed out of stock**. Beat, the beat-less scheduler and
the fan-out source-gate registry must all include its daily writer.

Status, cost and stock facts travel in tenant exports; cost source IDs remap to their
domain sources. Service-module purge deletes costs for the sources it removes, while
independent manual pool usage and costs survive. Activity, push attempts, SMS/attestation
outcomes and provider replay events are runtime-only and never travel in tenant dumps.
Personal archives include a separate `runtime_activity/` section with explicit field
allowlists for own activity and push outcomes, with no device destinations, tokens,
leases or message content. Own unselected activity is included; another tenant's selected
activity is not. Account purge must delete user-linked runtime rows. The 1d contract retains immutable
usage rows and their member link to the anonymized User stub; it does not update the
usage row or its started_at. SET_NULL is the declared policy for a future physical User
delete, not permission to bypass the usage trigger. Anonymous facts survive.

**Recent reauthentication (Lane F).** `accounts.ReauthenticationSession` holds
server-only proof bound to the stable browser session ID or native DeviceRefreshFamily ID, user, surface,
deployment generation, password/email/linked-identity fingerprint and MFA version.
Refresh never changes auth_time; proofs expire after ten minutes. Device grants
skip browser Origin validation only after authentication. Password verification also requires TOTP when MFA is enrolled;
passwordless MFA holders may use replay-protected TOTP alone. Social intents are
single-use, session/origin/version bound and five-minute limited: verified linked
subject is required, never a new link. Provider auth_time must be within five minutes.
Apple requires it; OIDC requests prompt=login and max_age=0; Google requests it through
claims. GitHub, Google without fresh auth_time and OIDC without auth_time additionally need
TOTP, else verified-phone OTP, else an intent-bound verified-email code. Email codes
are single-use, ten-minute limited and attempt-capped. Passwordless MFA
enrollment instead accepts fresh social proof or a single-use, verified-email,
session-bound fifteen-minute confirmation; emailed proof never authorizes sensitive
actions by itself. Existing password checks for other MFA management remain.

Role/grant changes, API-client management and organization governance/deletion use
the shared boundary. Control has its own CSRF-protected reauthentication form and
preserves the existing control MFA gate; its proof never authorizes the SPA. Global
proof/intent mutation is source-gate exempt, while protected tenant operations still
use their ordinary fences. Proofs are global, omitted from tenant artifacts, have an
explicit excluded User edge/unique-key disposition, no scoped PII or object ownership,
CASCADE on account deletion and existing thirty-day auth-state cleanup. The complete
model graph is pinned; deployment restore generation invalidates old proof.

**Monitoring and analytics (Lane F).** `/control/storage/` is read-only and inherits
superadmin/active-account/control-MFA boundaries and lists every tenant; deployment
database/table totals remain global. Optional route metrics use
bounded compiled route/method/status labels and Prometheus multi-process files,
never raw paths/queries/credentials. Per-master directories are cleared at master
start, with a separate directory for each standard container or pod. Prometheus owns
retention. The existing metrics token gate is unchanged. Optional analytics supports
only trusted Plausible manual scripts, route-template URLs and empty referrers.
Unknown/private/bearer routes never inject; credential-boundary navigation removes
script/queue, cancels collection and reloads the document. Disabled analytics installs
no navigation guard. Strict-origin applies site-wide and configured origins alone
extend CSP. See `docs/monitoring-and-analytics.md` and `docs/helm.md`; Helm retains H1
admission and requires externally prepared state, never inventing recovery authority.

**Makerspace local days** go through `makerspaces.local_time`; never derive a tenant's day from deployment UTC or the browser zone. Opening hours are advisory (empty = always open; dated exceptions replace a day), and public bootstrap exposes timezone/hours only. Country remains staff-only. The profile currency is `MakerspacePaymentSettings.default_currency`; existing charge currencies never change with it.

**Self-host vs managed SaaS (all managed features dormant by default).** `PLATFORM_DOMAIN_SUFFIX`
blank/whitespace ⇒ `domain_verification.is_self_host()` is True ⇒ **every managed feature is inert**
and single-domain behavior is byte-for-byte unchanged (self-hosters unaffected). Self-host trusts a
superadmin-set custom `frontend_domain` immediately (no DNS TXT challenge — the challenge only ever
defended the shared managed box). The self-host branch is strictly superadmin-only (the staff-origin/
CORS allowlist is process-global; letting any tenant set a trusted origin is a cross-tenant token-theft
vector). Managed mode adds `<slug>.space-works.tech` provisioning + tenant self-serve custom domains on one
shared instance (no per-tenant DB). **VERIFIED is the trust gate** — a `frontend_domain` grants CORS/
staff-origin/bootstrap/Host/TLS trust only when `frontend_domain_status=VERIFIED` and non-archived.

**Managed hosting requests (platform-level, dormant on self-host).** `apps/hosting_requests/` lets anyone
ask to host a makerspace (`/hosting`) and lets an existing makerspace or organization send an invitation
that pre-fills the request. Availability: `admin_available()` = not `is_self_host()`; `public_available()`
additionally needs `email_enabled()` and `PUBLIC_APP_BASE_URL`. Every public and staff view calls
`require_public_available()` first (404 otherwise); `/config` carries `hosting_requests` only when public
availability holds; the `/control/` admin and its `_managed_item` sidebar entry are hidden on self-host; the
add form's hidden `hosting_request` field is rendered and honoured only when `admin_available()`.
- **One writer.** `hosting_requests/workflow.py` is the only code that assigns `HostingRequest.status`
  (literal `ALLOWED` pairs; anything else is `HostingRequestConflict`, 409 `invalid_transition`; field
  problems are 400; unknown/expired tokens 404). Approval only **marks** a request accepted and emails the
  applicant; nothing is provisioned. Rejection needs a 10–2000 character reason that is emailed and kept
  after redaction (the reject form warns not to include personal details).
- **Authority, no new action.** A makerspace invitation needs `MANAGE_MAKERSPACE` in that (servable)
  makerspace; an organization invitation needs a member account holding `MANAGE_ORGANIZATION_MEMBERS`
  (`lock_governance_membership`). **"Join <organization>" is offered only when the inviter governs that
  organization**: always for an organization invitation; for a makerspace invitation only when the inviter
  is a member account governing the space's active owner organization. A staff Space Manager's invitation
  therefore never offers Join (`join_offered=false`, the organization is not even locked). Governance is
  checked at creation only; cancel re-runs the authority for the route's scope.
- **Owner by default, superadmin override (#49).** For Join, the pre-filled add form names the inviting
  organization as owner; for Own, a new organization name. A Join whose organization is gone or inactive
  fills **neither** owner field and the request shows a warning, so the add form's exactly-one rule forces a
  choice — never a silent switch to Own. `link_created_makerspace` runs inside the add view's atomic block
  after owner assignment, requires an accepted, unlinked request, and never compares the chosen owner with
  the applicant's choice; a refusal rolls the whole creation back and the redirect keeps the query string.
  "Create makerspace" is a custom admin URL (registered before the defaults) that re-authenticates first,
  so the superadmin starts the add form inside a fresh 10-minute window.
- **Bearer tokens.** Invitation and status tokens are 32-byte random values sent only in a URL fragment
  (`/hosting/invite#token=`, `/hosting/request#token=`) and stored as SHA-256 digests. The only HTTP
  response that ever carries one is the inviter's one-time `invite_url`. The status link also verifies the
  address on first open; the request reaches review only after that.
- **Enumeration-safe intake.** Submit always answers the same 202 — honeypot, per-address overflow
  (`HostingRequestEmailThrottle`, called manually, never in `throttle_classes`) and a real submission are
  indistinguishable — and the verification mail is generic (no applicant-supplied text to an unconfirmed
  address). No route takes an email as a lookup key; the inviter's list never shows applicant details.
- **Lock order:** makerspace → organization → organization membership → hosting row.
- **Data classification.** `hosting_requests.HostingRequest` is OMITTED from tenant export and dumps; its
  `invited_by`/`decided_by` edges are declared and never expand a portable closure; makerspace, organization
  and user links are `SET_NULL`, so a tenant purge leaves the platform row with null links.
- **Retention.** A daily beat task (`hosting-request-retention`, also in `run_scheduled_tasks`) deletes
  unconfirmed public submissions 48 hours after submit and wipes applicant details (name, email, phone,
  description, website, invite note, new organization name, both token digests) 90 days after a request
  died — rejected from `decided_at`, withdrawn from `withdrawn_at`, never-completed invitations from
  `invite_expires_at`. Status, space name, location, slug, owner choice, inviter links, decision fields and
  the rejection reason are kept as the decision record. Accepted requests are retained. **Hosting-request
  email logs follow the request's retention:** applicant mail carries `source_kind="hosting_request"` and
  `source_id`, and those `EmailLog` rows are deleted with the 48-hour deletion and the 90-day redaction. The
  sweep runs on self-host too, so a deployment that left managed mode still honours the wipe.
- **Reserved `/hosting`.** `hosting` is a reserved top-level segment. On the central origin `/hosting`
  shadows any pre-existing public handle named `hosting` (accepted; such a profile stays reachable only
  through `/m/…` or a redirect).
- **Named exceptions.** *Console parity:* review is `/control/`-only by owner decision #47; there is no
  React superadmin review surface. *Audit:* unverified public submissions and the retention sweep's
  deletions/redactions are deliberately unaudited (the sweep logs counts only); verification, every later
  transition, invitation creation/cancellation and the makerspace link are audited with literal actions
  and no free text.


**Installer-managed subdomain TLS is explicit opt-in.** `PLATFORM_SUBDOMAIN_AUTO_TLS` defaults off,
retaining the origin-certificate SaaS edge's refusal to issue platform-subdomain certificates on demand.
Guided hosted platforms enable it for public ACME: admission still requires an exact registered
`frontend_domain` in VERIFIED state on a non-archived tenant. Arbitrary suffix-matching hosts are never
admitted. The first API hostname and apex are operator-configured infrastructure names.

**Managed fair-use limits (dormant on self-host).** `apps/makerspaces/limits.py` `resource_limit(ms, key)`
(self-host → None = unlimited; per-space `resource_limit_overrides` JSON, else `MANAGED_RESOURCE_LIMITS`)
+ `check_quota(ms, key, *, adding)` called **inside each creation service's `transaction.atomic()`**
(self-locks the makerspace row; raises DRF 400 `{"limit": …}` / typed `limit_reached` at cap). Storage
counter (`add_storage`/`free_storage`) charged at finalize; `recompute_storage` management command is the
authoritative reconciler. Email daily cap via `integrations.DailyEmailCounter`.

**One domain per makerspace.** `Makerspace.frontend_domain` (case-insensitively unique) is the single
frontend-registry field (the old per-type `TenantFrontend` model is deleted). Two origin helpers in
`platform.py`: `makerspace_staff_origins` (ONLY the exact `https://<frontend_domain>`, feeds refresh/
logout CSRF + the origin→tenant guard) vs `makerspace_public_origins` (that ∪ `cors_allowed_origins`,
feeds general CORS + publishable-key validation) — so an API-client/public origin can make
publishable-key calls but **can never mint a staff session**. `origin_scope.py` hard-scopes a browser
staff request to its domain's makerspace; origin-less (server) requests fall back to `MakerspaceMembership`.

**Superadmin is always on (owner decision #110).** The platform superadmin holds global authority in
every servable makerspace: `rbac.can`, `effective_actions`, `scope_by_action`, `makerspaces_for_action(s)`,
`resolve_scope` and `is_space_manager_identity` exclude only archived and otherwise unservable spaces
(`archived_makerspace_ids` / `_exclude_archived_ids`), never a per-space switch. There is no hidden-space
403/404/empty-200 contract, no slim `/control/` row, no Platform-Email precondition and no
space-manager-only re-enable. Platform dashboards, reports, ledgers, `/control/` lists and FK widgets,
API-client reads and organization grants all cover every servable space, and scheduled work
(`rbac.scope_for_scheduled_work`) runs for every servable space. Platform accounts have no memberships; a
local manager uses a separate tenant staff account. Only the superadmin manages Space Managers (D7).
`accounts/rbac_superadmin.py` now holds only the identity helpers; keep its path, which
`tenant_migration.authority_guards.AUTHORIZATION_SOURCES` pins.

**Superadmin console parity (owner decision #115).** The superadmin sees and uses everything a
space's Space Manager does, in every servable space:
- *Surface.* `accounts/platform_tenant_surface.admits` lets the platform superadmin (platform kind,
  superuser, superadmin role, never native) into every `membership-only`/`delegable` route outside
  `/api/v1/auth/`. It opens the surface only: each route's RBAC (global for the superadmin), module
  gates, servability, recent re-authentication and audit still apply, and every change is audited in
  that space with the superadmin as actor. Do not add per-route platform mirrors; the
  `platform-tenant-*` report routes predate this and remain for the platform dashboard.
- *Console.* `/auth/me` carries `superadmin_actions` (the grantable set; `[]` for everyone else). The
  console passes them only once a space is chosen, so `getStaffAccess` shows exactly that space's
  Space-Manager tabs beside the platform tabs, and only the platform tabs before a choice. Tabs that
  belong to a person -- My channels, Organized events, Organization analytics, Assigned resources --
  stay off, because their endpoints are per account, not per space.
- *Email (#115a).* Provider and sender (`api-settings`, re-auth), templates, the delivery test (mailed
  to the superadmin's own address) and the space's delivery log are all Space-Manager routes, so the
  superadmin reaches them through the surface rule; each write is audited in that space.
- *PII.* `accounts/platform_tenant_pii.PlatformTenantPiiMiddleware` masks person data in every
  response to an admitted superadmin request unless `pii_seam.pii_visible` allows it (#111 Q12, #114):
  DIRECT keys (email, phone, names, requester/contact fields, `to_email`, answer snapshots) always,
  GENERIC keys (`name`, `note`, `subject`, bodies) only inside a dict that carries a DIRECT key. The
  response gains `X-PII-Masked: 1`. A JSON write containing the mask is refused 400
  `pii_access_required`, so a masked value can never be saved back. Masking is presentation only.
- *Reports (#115b).* Inside a space the superadmin reads every report, analytics page and export the
  Space Manager does; an `identity_bearing` report or export additionally needs a PII window on that
  space (`report_subjects.require_report_action`, 403 `pii_access_required`); the deployment aggregates (`analytics-aggregate`, `report-*-aggregate`,
  `ledger-aggregate`) and the platform dashboard's "Compare spaces" table total and compare across
  spaces; each space's `/control/` page links into its reports (`admin_console_links.py`,
  `?context=platform&space=<slug>`).
- *Pages.* `public_page_authority.reject_platform(actor, tenant=True)` admits the superadmin to a
  makerspace's own page and its events' websites; organization pages stay owner-only.
- *Guard.* The local parity test walks every tenant staff route as a Space Manager and as the
  superadmin and fails on any route the Space Manager opens and the superadmin cannot. Gaps are fixed,
  never allow-listed. `Makerspace.superadmin_access_enabled`
still exists until the P1b wave-2 migration drops it, but no read path consults it. Server-side operator
recovery remains outside application authority.

**Makerspace archive → purge (superadmin, `/control/` only).** `Makerspace.archived_at` is the
single soft-delete flag; archive scoping is threaded through central rbac + all aggregates + public +
token-status surfaces (archived is invisible everywhere but `/control/`). `lifecycle.py` is the single
lifecycle source. Its public decision services independently require an active platform superadmin.
Unarchive still refuses an active migrated-out handoff. **Purge** is break-glass: collects S3 keys, writes a platform-scoped audit, then in
one `transaction.atomic()` suspends immutability triggers **transaction-scoped** and deletes the full
`PROTECT` object graph in verified dependency order, then best-effort deletes S3.
- Self-host: `SET LOCAL session_replication_role='replica'` (all triggers off; FK off — ORM does
  CASCADE/SET_NULL in Python).
- Managed Postgres (`MANAGED_POSTGRES=True`, e.g. Supabase forbids `session_replication_role`):
  `SET LOCAL app.allow_immutable_delete='on'` (only OUR immutability triggers bypass; FK stays on).
- **Every append-only/immutability trigger is purge-aware**: DELETE allowed only under GUC
  `current_setting('app.allow_immutable_delete', true)='on'`; UPDATE always blocked (audit/0003 style).
  A new PROTECT-FK + immutable model must add itself to the purge graph **and** the drift-guard.
- **The evidence-photo guard has exactly one other DELETE path** (phase 11): abandoned-upload
  cleanup's transaction-local `app.evidence_abandoned_delete_id = '<exact photo id>'`. It is a
  transaction flag, not a role. The trigger honours it only for that `OLD.id`, only for an
  `unconsumed` row with its exact `EvidenceAbandonedUploadReceipt`, and only when all six inbound FK
  tables and every workflow-consumption audit are absent. Purge deletes the two now-`PROTECT` photo
  sidecars (`EvidenceUploadFinalization`, `EvidenceObjectRetentionState`) explicitly before the
  photos and never deletes receipts: they are FK-free, have **no** purge hatch, and keep reconciling.

**Archiving a makerspace must never strand its members' money (phase 1 of the five open items).**
`Payment.makerspace` outlives archival and `member_payment_queryset` deliberately never filtered
`archived_at`, but four separate gates defeated that intent. Fixing only the obvious one would have
been **worse than doing nothing**, which is the lesson worth keeping here.
- **THE PER-MAKERSPACE WEBHOOKS MUST SETTLE AFTER ARCHIVAL, and this was a live money-loss bug.**
  `StripeWebhookView`/`RazorpayWebhookView` looked the tenant up with `archived_at__isnull=True` and
  404'd. Since `MemberPaymentCheckoutView` has **no membership gate at all**, a member could already
  reach checkout for an archived space, have Stripe take the money, and have the callback refused —
  the charge stayed PENDING forever and the member was out of pocket. The 404 never prevented the
  charge, only the **recording** of it, so it directly contradicted the documented "webhook always
  settles / a real charge is never stranded" invariant. Archived is no longer refused: the public
  code is **addressing**, the unchanged per-space signature secret is **authorization**, and a purged
  row still 404s naturally because it is gone. Its origin is worth knowing before anyone
  "restores" it: both the filter and the test asserting it landed in `92eda37`, whose webhook was
  **verify-only** — it settled nothing, so refusing cost nothing. Settlement arrived in C.3 and
  nobody revisited the filter.
- **`member_activity_service.active_member_memberships(user)` is the ONE identity predicate**, and it
  deliberately does not filter archival — each caller applies its own rule (`active_membership` adds
  the archived filter, `payments.member_access` does not). It lives in `makerspaces`, not `payments`,
  because `apps.payments` is separable and a tombstoned deployment must still resolve member identity.
  An `include_archived=` flag was rejected: it would put a security-relevant relaxation in reach of
  every caller. So was restating the predicate in `payments` — that shipped briefly and produced two
  copies of the same five-part check in two apps, which is drift nobody notices until an audit.
- **`member_payment_actor` is payments-only and must NEVER grow a waiver gate.** `active_membership`
  never checked the waiver (that is `presence.guard.require_active_member`); adding one would let a
  newly revised waiver block someone from **discharging an existing debt**, recreating the stranding.
- **An API fix alone does not reach anybody.** `platform.resolve_frontend` and
  `views_memberships.MyMembershipsView` both exclude archived, and `MemberArea`'s payments query is
  gated on both, so the fixed endpoint had no route to it. The answer is the narrow
  `GET /member/archived-payments` discovery endpoint plus a `/member/archived` page that depends on
  **authentication only** — never on `bootstrapTenant` or `/memberships/me`. **Do NOT widen those two
  instead**: they would resurrect the archived space across every unrelated feature.
- **The discovery LINK must survive a failed bootstrap, and that is pinned by a test rather than by
  reading.** `MemberArea` does not early-return when `bootstrapTenant` rejects — it renders an error
  panel *inside* the shell — and the archived banner sits above every bootstrap-dependent section, so
  central `/member` still offers the link to a member holding nothing but an archived space.
  `MemberAreaArchivedLink.test.tsx` asserts exactly that (bootstrap rejects, `/memberships/me` returns
  empty, link present), because the people this route exists for are precisely the people who would
  otherwise have to guess its URL. **Residual limit, deliberate:** on the space's own archived custom
  domain the API calls fail (an archived domain loses origin trust), so the banner does not render
  there and the member must reach the central app. Closing that would mean re-granting origin trust to
  archived domains, which is the isolation archival exists to create.
- **A checkout must return the payer to the space that ROUTED the charge, not the one that owns it.**
  `create_checkout` reads `payment.via_makerspace or payment.makerspace`: for a collaborative-event
  charge, host A owns the row but member space B is the only member area the visitor can sign into,
  so deriving the URL from A lands them where they hold no membership. `platform.member_payment_
  return_url` then sends an ARCHIVED space to the central `/member/archived` instead of
  `member_area_url`'s dead `/member` or `/m/<slug>/member`. Both the Stripe branch and the provider
  seam read that one value, so every rail is fixed at once, and the two arms compose: host archived +
  home live correctly returns to the live home rather than the recovery page, which deliberately
  lists only archived spaces. The seam is monkeypatched **by name** in `test_connect.py` and
  `test_machine_payments.py`. **Known limit:** a session created *before* archival keeps its original
  return URL — the provider stores it and `MemberPaymentCheckoutView` hands back the saved
  `stripe_checkout_url` when present.
- **The bootstrap bypass must read the ROUTER's location, never `window.location`.** `App` short
  circuits to `/member/archived` before the tenant "Loading site" / "Site unavailable" screens,
  which is what an archived member has to get past. Reading `window.location.pathname` made that
  branch non-reactive: a client-side `Link` updates router context without touching
  `window.location`, so every **click** on the recovery CTA fell through to the central table and
  rendered not-found, while a direct page load worked perfectly — which is exactly what made it easy
  to miss. `useLocation()` fixes it. Pinning this needs a REAL `Link` under `MemoryRouter`; a stub
  using `history.pushState` does change `window.location` and would pass against the broken code.
- **`/member` must exist in BOTH route tables, and a component test cannot tell you it does.**
  The central table defined only `/m/:slug/member`, so `/member` fell through to not-found — and the
  member this recovery route exists for cannot supply a slug they can no longer discover. Rendering
  `MemberArea` directly proves the link renders, never that anyone can reach it;
  `App.centralMemberRoute.test.tsx` drives the real router instead. Same shape as the tombstone-suite
  lesson: the test that passes is not always the test that matters.
- **A 404 from the discovery endpoint means TOMBSTONED, and must be told apart from every other
  error.** `payments` is separable, so on such a deployment the endpoint is spliced out; treating
  that like a network failure renders a call-to-action whose destination immediately 404s. The
  recovery page reads the same signal and renders as not-found. It cannot ask tenant bootstrap which
  modules exist — not depending on bootstrap is the whole reason the route exists.
- **`lifecycle.archive_impact()` reports, never blocks.** It counts pending charges the space
  **owns** and pending collaborative-event charges merely **routed** through it (`via_makerspace`,
  de-duplicated) — the second arm is easy to miss and is exactly the visiting-member money at risk.
  `archive()` recomputes it under the row lock into the audit meta and still returns the makerspace
  (seven call sites depend on that return). The count is **advisory**: payment creation does not
  universally take that lock, so it cannot be frozen against concurrent inserts. "Never blocks" means
  a non-zero count is not an error — not that database failures are swallowed. The admin action grew
  a per-makerspace confirmation screen because it previously archived **immediately**, so there was
  nowhere to show a count.

**Archiving is TWO-KEY: a Space Manager requests, a superadmin confirms (phase 3).**
`makerspaces.MakerspaceArchiveRequest` + `archive_requests.py` (the one workflow service; never
mutate status outside it). Direct SM archive was rejected as a **self-lockout** — archiving
removes the space from RBAC scope and `unarchive` is `/control/`-only, so the person who pressed
the button loses the space and any way to undo it.
- **The `/control/` makerspace list is one ordinary list** (P1b: superadmin is always on, so the
  slim hidden-row variant is gone). Platform superadmins can archive/unarchive/purge directly
  without a request, and can approve/decline the pending request through dedicated list actions,
  whose confirmation pages always show the unsettled-charge counts. Review discloses request id,
  time, requester username and reason (no contact details). Recent control-session reauthentication
  protects both action and confirmation POSTs, including the ordinary makerspace delete route.
- **Authority is the `MANAGE_MAKERSPACE` ACTION, never `rbac.is_space_manager_identity`.** That
  helper deliberately does not infer identity from actions. Organization-derived authority can
  carry the action without local Space Manager identity. Both view and service must check the
  action and agree; changing the role catalogue must not replace either action gate.
- **The requester must be emailed the outcome**, including auto-approval from a direct archive.
  Once archived they lose RBAC scope, the console, the request history and their tenant domain,
  so no in-app surface can ever tell them. Sends go through `transaction.on_commit`, catch and
  log, and do **no SMTP work under the makerspace lock** — an SMTP failure must never roll back
  an archive. Platform mail (`makerspace=None`), so no module toggle can mute it.
- **A direct `/control/` archive AUTO-APPROVES any pending request atomically.** Leaving it
  pending is false state that is invisible once archived and blocks a fresh request after an
  unarchive.
- **A COLLEAGUE's withdrawal notifies the requester; your own does not.** Because authority is
  the action rather than "the person who filed it", any `MANAGE_MAKERSPACE` holder can withdraw
  someone else's request — and without the mail that request simply vanishes with no trace the
  requester can see. Withdrawing your own needs no mail: you just did it. This is the one
  transition the design review got wrong ("withdrawal needs no email"), because it assumed the
  actor and the requester are the same person.
- **Approving from the request queue must show the same impact screen as the direct route.**
  Approving *is* archiving; without it a superadmin could archive without ever seeing the
  owned/routed pending charges — two ways to do one thing, one of them uninformed.
- **Never copy `reason`/`resolution_note` into audit metadata** (append-only ⇒ undeletable), do
  not put `reason` in the broad superadmin mail, and send `resolution_note` with
  `persist_body=False`. The text is makerspace-scoped operational text like
  `ApiKeyRequest.reason` — length-bounded, **not** `ScopedPiiModelMixin`.
- Lock order is **`Makerspace` → `MakerspaceArchiveRequest`** on every transition. The partial
  unique index (one PENDING per space) is the backstop, and its `IntegrityError` becomes a typed
  409, not a 500. A **per-space one-hour cooldown** stops `request → withdraw → request` fanning
  mail at every superadmin; it deliberately does **not** consume the OTP/SMS quotas, because a
  governance-mail flood must never be able to suppress password-reset mail.
- `makerspace` is **CASCADE** (the `SubdomainRequest` precedent); both user FKs are **SET_NULL**,
  because durable attribution lives in the append-only audit log and PROTECT here would only
  widen the user-deletion graph. No module key, purge plan, tombstone entry or PII registration:
  `makerspaces` is core and archival is governance, not an optional feature.
- **DRF field errors are not the `detail`/`code` shape.** A blank/overlong `reason` returns
  `{"reason": [...]}`, so the 400 is documented with its own serializer (the
  `ProvisionSubdomainValidationErrorSerializer` precedent) rather than the typed error schema a
  generated client would destructure and find empty.

**Publishing a borrower's NAME is opt-in, and the guard must short-circuit (phase 2).**
`inventory.public_stats_hardware.current_loans` served `holder_name` on the **unauthenticated**
stats endpoint, resolving the free-text `requester_name`, then `requester_username`, then
`get_full_name()` — a real person's name bound to a specific tool and a due date, readable by
anyone. `Makerspace.public_stats_show_holder_names` now gates it, **default off**, and migration
`makerspaces/0060` backfills **True unconditionally** for existing rows (the `0050`/`0056`
precedent: an opt-in default silently removes behaviour a space relies on). Accepted consequence,
written in the migration: a currently stats-disabled space will publish names if it enables stats
later, unless its manager turns this off first.
- **The OFF branch must not CALL `public_display_name` at all** — not call it and discard the
  result. `HardwareRequest` is a `ScopedPiiModelMixin` and `requester_name` is encrypted **and
  Bloom-indexed**, so reading it transparently decrypts; a names-disabled public request must not
  depend on PII decryption or key availability for a value it throws away. A test spies on the
  helper and asserts **zero calls**, because every output-only assertion passes against a
  compute-then-replace implementation — verified by writing that regression and watching the four
  output tests stay green while only the spy failed.
- **`'Member'` is not anonymisation.** The row still carries exact `due` and `since` timestamps
  with the item, so an observer who was in the space can still correlate. The toggle removes the
  directly searchable identifier; coarsening dates or suppressing `current_loans` outright is a
  broader policy decision that was **not** taken.
- The view is mounted at **two** URL aliases (`/api/public/<slug>/stats/` and
  `/api/v1/public/<slug>/stats/`) fed by one builder, so guarding the builder covers both. Neither
  the machines nor printing stats builders carry requester identity — `current_loans` is the only
  identity-bearing section. `/control/` gained `public_stats_enabled` too, which it had never
  exposed: a privacy switch the superadmin cannot see is not a control plane.

**A new public image field must register in FOUR places, and three of them fail silently.**
`Event.image_key` (phase 22) is the worked example. Adding the column and an upload view is the
visible half; the half nothing will remind you about is that
`inventory/public_image_storage.build_object_key` validates the **kind** against an allowlist (a
missing kind is the only one that fails loudly — `ValueError: Invalid public image kind`), while
`makerspaces/lifecycle._collect_public_image_keys` (makerspace purge),
`module_purge_collectors` + `module_purge_plans.public_image_keys` (per-module purge) and
`recompute_storage._public_image_keys` (the authoritative storage reconciler) each fail **open**:
skip one and the objects simply outlive every row that could name them, or the reconciler silently
writes a total that omits them. `public_image_key_in_use` also has to learn the new model, or two
entities can claim one key and clearing either blanks the other. The `BookableSpace` gap this
paragraph used to name is **FIXED** — `recompute_storage._public_image_keys` now includes it, with
a comment recording why. `MaintenanceLogDocument` had the same hole (charged on upload, collected
by both purges, absent from the reconciler) and is fixed too; the 2026-10-09 makerspace audit then
found three more charged kinds the reconciler omitted — member-card photos, event-series images and
event attendance certificates — now counted and pinned by `tests/test_storage_reconciler_gaps.py`.
**Any new `limits.add_storage` call site needs its kind in `recompute_storage`**, or the
authoritative reconciler silently lowers a space's recorded usage. This list exists because that
failure mode keeps recurring in the one mechanism that fails silently. Storage accounting itself is a **no-op on self-host** (`limits.add_storage`/`free_storage`
return early), so a test asserting `storage_bytes_used` must force managed mode with
`monkeypatch.setattr(limits, 'is_self_host', lambda: False)` and wrap `on_commit` object deletes in
`django_capture_on_commit_callbacks(execute=True)`.
- **A purge that deletes image-holding rows must free the quota, and the accounting belongs
  POST-COMMIT with the object deletion — never inside the purge transaction.**
  `module_purge._delete_public_images_and_free_storage` is generic over the plan's `public_keys` and
  handles each key in one loop: HEAD the size, delete the object, then free the quota **only when
  deletion reports success**. `public_image_storage.delete_object` returns `True`/`False`; swallowing
  its own `BotoCoreError`/`ClientError` without reporting failure once let the counter fall while the
  object survived, permanently granting free storage. The HEAD still has to precede deletion or the
  size is lost, but accounting must follow confirmed deletion. The whole loop runs after commit and
  best-effort: inside `purge_module`'s `atomic()` those network calls would hold the makerspace
  `select_for_update` lock and could roll back rows that were correctly deleted. An absent size or a
  failed deletion frees nothing.
- **External I/O must never run inside a transaction that holds a row lock.** HTTP and object-storage
  calls have network-bounded latency and failure modes; putting them under `select_for_update()` turns
  a slow dependency into lock contention and lets an unrelated transport failure roll back valid
  database work. Scheduled work follows `run_scheduled_tasks`' **claim-then-work** shape: a short
  transaction locks the `PeriodicTaskRun`, checks due-ness and stamps `last_run_at`, then the runner
  executes after commit. The same rule was violated twice in one review session, so it is recorded
  here as a general transaction boundary rather than left as two per-site fixes.
- **A TEST THAT ASSERTS ON SOURCE TEXT PROVES NOTHING ABOUT BEHAVIOUR.** Prefer an observable: the
  scheduler lock-boundary test records `transaction.get_connection().in_atomic_block` while the task
  runs. When a test exists to prevent a specific regression, reintroduce that regression and verify
  the test fails before trusting it.
- **A presigned upload is a hole in all three row-walking mechanisms, and it is a PLATFORM property,
  not a bug in any one endpoint.** `presigned_upload` hands out write access to a key before any row
  claims it. Public-image POST and PUT now both target **staging**; promotion validates a bounded
  snapshot's size, MIME and image bytes, then conditionally creates the final key exactly once.
  Replays cannot replace that final object; attachment charges its winning size. An unattached upload
  remains invisible to `limits.add_storage` (charged at attach), to `recompute_storage` (sums
  rows) and to every purge collector (enumerates rows) simultaneously. `MemberImagePresignThrottle`
  caps the one presign an ordinary member can reach — per **account**, POST-only, so a member who
  spends their uploads does not lose the ability to *clear* an image, the one action that frees
  storage. That bounds the damage; it does not eliminate orphans. Staging also needs a bucket
  lifecycle rule or a sweeper for unclaimed keys; staging alone does not delete abandoned bytes.
  Do not add a new member-reachable presign without a per-account cap.

**Rate limits are global only when their cache is global.** `CACHES` must stay configured to use
Django's `RedisCache` when `CACHE_URL` or an explicitly set `CELERY_BROKER_URL` supplies Redis; a
per-process cache silently multiplies every DRF throttle by the Gunicorn worker count and loses its
counters when a worker recycles. The fallback must be Django's shared `DatabaseCache`, never
`LocMemCache`: the brokerless cloud profile sets `CELERY_BROKER_URL` empty but runs three Gunicorn
workers by default with `--max-requests 1000`, so a per-process cache multiplies every rate limit and
then resets its counters as workers recycle. The operations migration creates the cache table; no
separate operator step is required.

**Object storage.** Two buckets per env: a private evidence/docs bucket and a separate **public-read**
image bucket (`PUBLIC_IMAGE_BUCKET`, served via `PUBLIC_IMAGE_BASE_URL`, kept distinct from the signing
host). New file types use the **prefix model** (single shared bucket, isolated by
`<module>/<makerspace_id>/<machine_or_resource_id>/<category>/<uuid>` — NOT bucket-per-makerspace, which
would hit S3's ~100-bucket limit) — applied to NEW files only, no re-keying. Presign follows
`STORAGE_PRESIGN_METHOD` (POST for MinIO, PUT for Supabase; PUT-mode re-validates size server-side at
attach). Object keys are identifiers, not secrets — privacy is the private bucket + short-lived signed
URLs. Upload validation: strict magic-sniff for PDF/image; the private maker/CAD allowlist
(`apps/maker_file_formats.py`) accepts STL/OBJ/3MF/STEP/etc. on ext+MIME (+signature for 3MF/STEP);
public-image + evidence buckets stay strictly image-only.

**Evidence object retention bounds live bytes without weakening evidence-row immutability.** Evidence,
like public images, uses both POST and PUT presigns targeting
`staging/<final-key>`, and an attaching workflow promotes to the never-client-writable final key. The
deployment default is 365 days; a makerspace override must be between 30 and 3650 days. The global
`EVIDENCE_OBJECT_EXPIRY_ENABLED` switch ships false, and policy GET/PATCH plus preview remain available
while it is false. The six-hour sweep is bounded per tenant, enters one source-gate fan-out boundary per
makerspace, and refuses to run outside deployment recovery state `NORMAL`.

Expiry locks only long enough to claim in the order `EvidencePhoto`, `EvidenceUploadFinalization`, then
`EvidenceObjectRetentionState`; all object-store HEAD/delete work happens outside that transaction. A
claim makes the photo unavailable to finalization and every issue/return attachment path. Success means
that **all versions and delete markers** of both the final key and its staging key are confirmed deleted;
an unsupported version-listing API or any transport/auth failure is retryable failure, not best-effort
success. Only a confirmed two-key deletion may write terminal `expired`, release managed quota once and
append `evidence.object_expired`. `recompute_storage` excludes only terminal expired rows. The immutable
`EvidencePhoto` row, its inbound request/return/accountability relationships and the PostgreSQL
immutability triggers remain unchanged; object expiry does not authorize row pruning.

An expired evidence read returns 410 from the terminal state without contacting object storage. Backup,
restore and tenant migration treat `expiring` as a refusal and `expired` as a signed, state-backed
intentional-absence tombstone: both final and staging keys must be absent, while the row and retention
state remain in the database image. Live missing evidence is still an error. An archive captured before
expiry can contain and later resurrect the old photo bytes, so this mechanism bounds the live store; it
is not legal erasure from historical archives.

**Abandoned-upload cleanup deletes only proven never-consumed presigns; attached evidence is never
deleted (phase 11).** `EvidencePhoto` rows are created at presign time, so a cancelled form leaves an
unattached row. Absence of relationships is not proof: the positive proof is
`EvidencePhoto.consumption_state='unconsumed'`, which only the two production presign views write.
Every pre-migration, imported or directly-inserted row is `legacy_unknown` (Django `default` and
Postgres `db_default`) and is permanently ineligible; tenant import (portable and Lane D) resets the
field to `legacy_unknown` and resets the two tenant cleanup policy fields to off/null, so a source
archive never carries cleanup authority. `apps/evidence/consumption.py::mark_consumed` is the only
permitted photo UPDATE — one-way `legacy_unknown|unconsumed → consumed` with every other column
unchanged, enforced by the trigger — and all seven consuming transactions call it after
`lock_evidence_for_attachment` (reviewed issue/return, direct-loan issue/return, self-checkout
issue/return, problem-report triage including `no_issue`). A new consuming workflow, inbound FK or
consumption audit must be added to `abandoned_upload_candidates.py`, the 0007-style trigger and the
tests in the same change.
- **All six inbound relationships are `PROTECT`.** `EvidenceUploadFinalization.evidence` and
  `EvidenceObjectRetentionState.evidence` moved from `CASCADE`, `PublicToolLoan.return_evidence` from
  `SET_NULL`, because Django's collector clears/deletes those before a parent-delete trigger runs.
  Cleanup deletes the two sidecars explicitly; any domain link makes the collector raise.
- **Both switches are independent and default off:** `EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED` and the
  per-tenant `abandoned_upload_cleanup_enabled`; age `EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS=7`
  (tenant 1–3650), checked strictly longer than `EVIDENCE_URL_TTL_SECONDS` at system check and PATCH,
  and recomputed at sweep time as `max(days, TTL + 1 s)`. Policy is `MANAGE_MAKERSPACE`, not
  `MANAGE_EVENTS`; PATCH is partial and the policy row exists only while non-default.
- **Order is mandatory:** fan-out source-gate boundary → `satisfy_retention_fence` (first durable
  per-tenant operation) → candidates strictly below `min(age cutoff, rolled_through −
  REFINALIZE_LOOKBACK)` (the rollup re-derives seven days below its watermark, so deleting inside
  that window would append a lower revision to a historical bucket) → locked `CLEANING` claim (blocks
  attachment; never steals `EXPIRING`; `EXPIRED` keeps its expiry metadata so quota is not credited
  twice) → strict two-key deletion outside the DB → one final transaction: quota once (Mechanism A's
  charged rule), exact receipt, sidecar deletes, exact-ID GUC parent delete, one
  `evidence.abandoned_upload_deleted` audit targeting the **makerspace**. Mechanism A never claims
  `CLEANING`; backup, object capture and tenant export refuse it like `EXPIRING`; the detail API answers
  409 `evidence_cleanup_in_progress` without storage; `recompute_storage` leaves the tenant unchanged.
- **The receipt is permanent deletion authority and a key reservation.** `EvidenceAbandonedUploadReceipt`
  is FK-free (raw source makerspace/evidence ID snapshots), unique on both the pair and `object_key`,
  rejects every DELETE (no purge hatch) and every UPDATE except `next_reconcile_at`,
  `last_reconciled_at`, `last_error`, `updated_at` — at the ORM (`reconcile_update`) and in Postgres.
  Receipt and photo INSERTs share an advisory lock on the exact key: a receipt may only name its exact
  live `unconsumed` candidate, and a photo INSERT on a receipt key is rejected. `choose_target_key`
  treats receipt keys as occupied even when storage reports them absent. The receipt is omitted
  coordination in data export (retained global in the Lane E readable main), `DROP` in Lane D, and its
  key is `COORDINATION_ONLY` — never archive content.
- **Late-write reconciliation is deployment coordination, not tenant mutation.** An upload admitted
  before URL expiry can finish after cleanup; every scheduled run first strict-deletes both keys of a
  bounded due batch ordered `(next_reconcile_at, pk)`: success +360 min, failure +720 min (two sweeps,
  so failures cannot starve the batch). It ignores both switches, servability, source-gate state
  (`MIGRATED_OUT`) and whether the makerspace still exists; non-`NORMAL` recovery is its only fence. It
  never changes quota or audits. Purge collects both receipt keys into its immediate deletion closure.
- **Portable history:** a missing EvidencePhoto audit target is exported as blank target plus
  source-local provenance only when a same-tenant cleanup audit proves that exact ID was cleaned
  (`data_export/deleted_audit_targets.py`); an unproved missing target fails the export. The static
  EvidencePhoto target disposition stays `REMAP` for surviving photos. Cleanup is live-store
  minimisation only; older archives may restore a cleaned row and bytes.

**Reports/analytics extend one registry** (never a parallel system). `apps/operations/report_registry.py`
holds canonical `ReportDefinition`s (module-gated, `report_scope.eligible_makerspaces` excludes archived
+ reports-disabled). FabLab domain builders (`reports_events`/`_bookings`/
`_maintenance`/`_machine_usage`/`_inventory` + fail-safe `reports_health`) mirror printing's date-range
contract; **aggregate output groups by `makerspace_id` and never flattens cross-tenant data**. Per-makerspace
report rows are gated by query-level scope (no per-row Python check → no N+1).

**Every previewable report declares a valid F1 `chart_spec`.** Chart dimensions and values
reference only its registered output fields. Money charts partition by currency and preserve
negative corrections; reports without a currency field chart non-money measures. Detail
loan lists expose `count=1` per row, never sum identifiers. These counts describe the returned
(possibly limited) rows. Event, booking and audit detail lists retain their export allowlists;
their table specs use an empty `values` list and no aggregation settings. The audit trail remains
export-only even though its definition also carries a table spec. The platform analytics
view returns the definition's typed `chart_spec` beside the existing rows and metadata.

**Role dashboards (analytics 1f-4) reuse those reports.** `dashboard_widgets.WIDGETS`
declares actions, source modules, report keys, kind and a default 30-local-day period.
The existing dashboard counters remain compatible; `widgets` adds authorized descriptors
and the canonical typed `chart_spec`. `data.meta.deferred` supplies tenant-local `start`/`end`
labels; clients fetch each widget independently through the existing tenant analytics
endpoint, which rechecks current authority. Dashboard counter requests never invoke report
builders. Consumption predicates precede source materialization, cost reads match bounded
batches of selected source identities, and return-history reads stay within selected requests.
Every widget requires both its declared action
and its report's action, source modules plus `reports`, and a servable tenant.
Identity-bearing widgets additionally require `VIEW_AUDIT` and their domain action.
Machine widgets forward the actor
to the builders' `role_scope.manage_scope_for()` boundary, including consumable pools
and cost: Inventory Manager alone does not gain machine-report authority.
Handover-only actors get `scope_mode=handover`, empty `widgets` and `queue_tiles`
(`ready_to_issue`, `due_returns`, `pickups`) without invoking analytics. Direct loans'
linked requests are counted once in these queues. Native staff use the same widgets
under local membership authority; `is_native_session` cuts organization grants in RBAC.
The dashboard's tenant discovery remains local-membership-based. Organization charts
use only the existing strategy-backed endpoint, retain the breakdown beside the total,
and project `chart_spec` onto the strategy's combined fields (no fake tenant dimension).

**The platform tenant picker uses explicit platform reads.** `/admin/platform/analytics/makerspaces/<id>/`
provides `reports/catalog`, `analytics/<key>`, `dashboard` and `reports/<key>/export` through the
canonical tenant handlers. Each read retains report RBAC, module checks and servability;
it grants no staff session, device grant or tenant credential access.
Deferred dashboard widgets and exports use those same platform routes. Tenant staff accounts
continue to use their separate fixed-tenant session.

**Platform analytics group by `makerspace_id` across every servable space.** `platform-services`
(with a server-owned active-superadmin `PlatformContext`) and every other platform analytic
(activity, adoption, growth) read `platform_dashboard.platform_spaces()`; there is no anonymous
hidden-tenant bucket any more (#110). Tenant-local reports apply the report's own action through
RBAC.

**One narrow, deliberate exception to the no-flattening rule, added 2026-08-20 by owner decision** after a
Stage-4 review correctly flagged the organization dashboard as a regression of it: **a single
organization's server-resolved OWNER set may carry a combined total, and that total may only ACCOMPANY —
never replace — the per-makerspace breakdown.** The rule exists to stop unrelated tenants being mixed and
provenance being lost; a total over one organization's own OWNER-linked makerspaces, resolved server-side
and always shown beside the per-space rows, does neither. The exception is bounded by four conditions, all
of which must hold: (1) the id set comes from `operations/org_report_scope.py`'s resolver, never from
client-supplied ids; (2) `relationship = OWNER` only — MANAGER and AFFILIATE links are excluded; (3) the
per-makerspace breakdown is always present in the same response; (4) `ReportScopeMode.COMBINED` is the only
mode permitted to flatten, and only for that resolved set. Anything wider is still a regression. Deployment
-wide aggregates are unchanged: they stay grouped by `makerspace_id`.

**Addressed messaging analytics** reads canonical `NotificationDelivery` and immutable
`NotificationLegacyMapping` observations, never the retired `MessagingDelivery` send table.
`operations.reports_communications.build_communications_health` is the registered version-4 builder.
Email physical outcomes come from `EmailLog`; push outcomes come from device ledgers, without
also counting the parent. Mappings supplement original observations without creating another send.
Failure observations cannot erase delivery/read evidence. Held, canceled, pending and sending
history remain distinct; held ingress and original abandoned-receipt history are separate measures.
Only exclusive current outcomes may be stacked; cumulative progress and ratios remain lines.
Current member-consent snapshots are date-independent, account-kind safe and excluded from
organization totals. SMS requires the current phone verification instance, sender and generation;
WhatsApp requires a current signed endpoint proof and no opt-out. Account-only recipients still
enter delivery cohorts. Segment totals prefer billed values including zero, otherwise labelled
estimates. Platform services/module health are version 3, mobile devices/auth version 2.
Platform metering separates OTP from notifications for visible tenants; hidden buckets retain
only service/day/count. Sender keys, phones, bodies and credentials never enter report rows.
Measurement notes: [report-builders-messaging.md](report-builders-messaging.md).


**Report provenance and scheduled delivery (forward plan phase 6, 2026-09-04).** Every CSV/XLSX export
leaves through `apps/operations/report_exports.py` with an `ExportProvenance`: CSV line 1 is a raw
`# generated_at=… generated_by=… makerspace_id=<id|all> report_key=… report_version=… filters=<json>` row
and XLSX carries a second `Provenance` sheet; the data columns stay exactly the registry fields, CSV is
streamed and XLSX is written write-only, and `ReportDefinition.version` is bumped whenever a report's shape
changes. A `ReportSchedule` runs only through `run_report_schedules` → the same `report_rows` builder as the
manual export (`generated_by="schedule:<id>"`), inside a per-tenant `fanout_tenant_write`, after a
`skip_locked` claim that advances `next_run_at` before any work (idempotent under a coarse cron); it is
skipped and audited (`report_schedule.skipped`) when the makerspace is not report-eligible or the creator no
longer holds the definition's `required_action`. Deliveries never carry bytes into chat: the file lives in
the private bucket under `reports/<makerspace_id>/…`, recipients get a signed URL bounded by
`REPORT_DELIVERY_URL_TTL_SECONDS` (default 6h — the one presign that deliberately outlives a quiesce drain,
read-only), the object is swept after expiry, email delivery is link-only, and `ReportSchedule` is a Lane D
DROP like every other live disclosure rule. `recipient_emails` is staff-entered contact data and is NOT in
the encryption registry (no existing JSON-list email column to mirror) — an owner call if that should change.
**Scoped PII encryption (Part H, `apps/encryption/`; dormant unless enabled).** Per-makerspace DEK via a
key broker (local/AWS-KMS), AAD-authenticated envelope crypto, `ScopedPiiModelMixin` on the 6 PII-holding
models with a save-boundary that single-INSERTs envelopes + dual-read cache.
Strict reads reject persisted legacy plaintext, while fresh in-memory assignments remain readable for
model normalization before encryption; refreshing a row replaces stale caches with freshly verified values.
Blind-index search (domain-separated HMAC bloom + exact + event-email hashes) for enabled deployments; disabled deployments
search plaintext via ORM. Write-fence (`PiiGlobalWriteFence`/`PiiMakerspaceWriteFence` + PG
`pii_assert_mapped_write_allowed()` triggers with global-then-tenant advisory locks) blocks mapped writes
during maintenance; mapped services acquire the fence **before** their domain row lock. Enabling is a
staged dual-read rollout; `decrypt_scoped_pii` is the fenced rollback. **Encryption is never enabled
before H3 (search) ships.**

**`warranty.Warranty.vendor_contact` is NOT registered as PII — by decision, not omission (forward plan
phase 6, owner decision 6, 2026-09-04).** It is a free-text vendor/business contact (a support desk, a
reseller's sales line), and no vendor or business contact anywhere in `warranty` or `procurement` is
classified as scoped PII; the registries are self-consistent on that reading. The alternative — a
`procurement.Vendor` record with `ScopedPiiModelMixin` contact fields, a data migration moving each
distinct `vendor_contact` value into an encrypted vendor row, and a sweep test over contact-like columns
— is written up in `docs/plans/2026-09-03-forward-plan/phase-6-money-and-membership.md` ("Vendor record")
and should be built only if the owner decides vendors can be named individuals. Until then, do not
re-raise the question from a grep for "contact" columns; this entry is the answer.

**Seven fixed per-makerspace roles (replaces Part L).** `makerspaces/role_catalog.py` defines
Space Manager, Inventory Manager, Machine Manager, Event Manager, Booking Manager, Handover and Member.
Names, slugs and grants are immutable; role CRUD and the capabilities editor/API are removed. Each
membership has a primary `assigned_role` plus `MembershipAdditionalRole` rows. Space Manager and Member
stand alone; the other five combine freely. `accounts/rbac_roles.py` shares the validity predicate
between object and SQL readers: additional rows contribute only when the primary and additional role
belong to the membership's tenant and both have combinable canonical slugs. Account-kind/context
validation also applies; null primary or foreign/obsolete roles fail closed. Authority is
the union of valid roles' actions, with existing implication and active/tenant/origin fences unchanged.
`/auth/me` and login expose `role_ids`, `role_slugs`, `role_names` and effective `actions`; navigation
continues to use server authority, never role-name inference. Organizations have empty role arrays.

`replace_membership_roles` is the complete-set writer. Both assignment routes accept `role_ids` (or
compatibility `role_id`, never both), reject empty or incompatible sets, and enforce the actor's grant
ceiling and the account-kind/D7 lifecycle policy above; with platform access off, another local
Space Manager may manage Space Managers, never self or the last active one. Create/reattach,
activation/reactivation/approval and invitation acceptance clear ALL additional roles and membership
machine links before assigning afresh. In-life edits preserve type links only while Machine Manager
is retained. Staff initial-setup invitations snapshot the complete role set and machine scopes;
community invitations remain Member-only. Existing writers keep their lock order: Makerspace
`FOR NO KEY UPDATE` before membership `FOR UPDATE OF self`; helpers add no role-row locks. Existing
User/invitation/role locks in callers retain their established order and strength.

**Fixed-role upgrade (`makerspaces/0091` schema, `0092` data, `0093` constraint) is irreversible
and never widens except E1/E2.** Back up,
stop all writers, run the new image's `python manage.py preview_fixed_roles` against the old schema,
resolve every “must fix before upgrading” diagnostic, then migrate (see `update-recovery.md`). Mapping
uses RAW grants, not implied actions: a combinable role qualifies only when all its grants were held;
redundant subsets are removed, no match becomes Member, and Space Manager is never inferred. **E1**
restores a narrowed canonical Space Manager rather than demoting the administrator. **E2** maps the
legacy six handout actions to Handover, adding direct `collect_service_request`. Every gained/dropped
action is reported. Foreign references become Member; null-primary legacy memberships stay untouched. Its reverse (`migration_support/fixed_roles_reverse.py`) is schema-only and runs only while nothing relies on the catalogue -- no additional role, no per-person machine link, and no membership, request, invitation, recipient rule or report schedule naming Event Manager, Booking Manager or Handover; it then deletes just those three unused rows. Anything else refuses, and the backup is the rollback.

Migration refuses `NotificationRecipient(kind=role)` references to obsolete/custom roles: operators
must repoint them to a built-in or named users, or remove them in the old console, then rerun preview.
There is no automatic conversion to user rules. ReportSchedule pruning only narrows; empty schedules
are deactivated and audited. Rejected pending staff invitations are revoked AND repointed to Member;
accepted mappings preserve invitation history/expiry/attempt state. Colliding obsolete names/slugs
are renamed first, all surviving defaults temporarily renamed second, new built-ins seeded third,
and canonical defaults restored last. References are repointed before obsolete rows are deleted;
`staff.roles_migrated` retains signed before/after role and machine-scope evidence.

Mutes silence a membership only when EVERY stream-applicable role it holds is muted; an unrelated
role does not count. Space packs no longer export roles: legacy empty `roles: []` is accepted and
removed, while nonempty role sections are refused. Membership and per-person authority never travel
in a pack. Tenant imports reduce member memberships to Member; staff retain built-in roles and
remapped additional roles/type links under D11 (see the account-kinds section above).

**`apps/makerspaces/module_registry.py` is the single source of truth for module keys.** All 37
`ModuleDefinition`s live there (`key`, `label`, `description`, `app_label`, `enforcement`, `group`,
`requires_modules`, `default_enabled`, `is_core`, `frontend_exposed`, `frontend_workflows`), and the
lists that used to be hand-kept in parallel now **derive** from it: `models.DEFAULT_ENABLED_MODULES`,
`platform.MODULE_WORKFLOWS`, `capabilities.FEATURE_MODULES`, and the former hardcoded
`printing → machine_service` branch (now `requires_modules` data). Add a module **only** in the registry.
Two rules the registry must not break: it **never imports `makerspaces.models`** (models imports it, so
the reverse edge is a cycle), and `default_enabled_module_keys()` returns a **fresh list** because it
backs a JSONField default. `frontend_exposed=False` marks an internal master switch and drops the key
from both the bootstrap `modules` array and `MODULE_WORKFLOWS`, preserving the byte-for-byte payload
invariant; unknown legacy keys stay exposed (`_canonical_modules` deliberately preserves them).
`is_core` marks the six un-toggleable modules — `public_inventory`, `request_workflow`, `staff_admin`,
`evidence_uploads`, `qr_management`, `scanner` — because the Hard Rules require a box QR scan **and** an
issue photo to issue hardware. `tests/makerspaces/test_module_registry.py` is the drift guard: it
AST-parses `apps/` and fails if a registered module has no real guard call site, if a guarded key is
unregistered, if the derived lists change, or if a migration-referenced callable stops resolving.

**Modules are OPT-IN.** `DEFAULT_ENABLED_MODULES` resolves to **7 keys** - the 6 core ones plus
`member_accounts` (owner decision #91; the `backup` key was retired in P1b, #111 Q2). Release
deployment is host tooling, not a module.
`member_accounts`, `mobile` and `payments` once carried it too and are now opt-in for new
makerspaces (existing rows kept them through `0057`). Everything else is off in the registry default. Guided setup explicitly installs the chosen
areas and always-on services. Legacy CLI profiles remain available (`minimal` 6 / `workshop` 13 / `lending` 16 /
`recommended` 19 / `cloud` 24 / `events` 12 / `bookings` 12 / `everything` = `full` 37 — pinned by
`tests/modules/test_combo_profiles.py`).
`ModuleDefinition.default_enabled` defaults to **False** and core must not set it (core is on by
definition; two sources for one fact is the drift the registry exists to remove). `member_accounts`
is the only registry entry that sets it, and `default_enabled_module_keys()` is the one place to ask
rather than counting by hand. (This paragraph read "core only (6 keys)", then "10 keys"; it is the
kind of count that goes stale silently, which is why the README table is generated from the registry
rather than written out.) **Existing makerspaces
are untouched** — a default change never rewrites stored JSON rows, and `_canonical_modules` preserves
unknown keys. Because almost every backend test exercises a module's behaviour rather than the install
default, `tests/conftest.py` has an autouse fixture that patches **only the `enabled_modules` field
default** to the `everything` profile; anything reading `default_enabled_modules()` /
`DEFAULT_ENABLED_MODULES` directly still sees the real opt-in value, which is how
`tests/makerspaces/test_module_registry.py` and `test_module_install.py` still assert production
defaults. A test asserting a module's *disabled* path must now disable it explicitly.

**Module install path (opt-in modularity).** `/control/` is deliberately not proxied on the public
frontend port, so it can never be the only way to enable a module — a non-technical operator cannot
reach it. `apps/makerspaces/module_install.py` is the single service behind
`python manage.py list_modules | install_module <key> | uninstall_module <key>` (`--makerspace <slug>`,
defaulting to the only makerspace). Installing resolves `requires_modules` transitively; uninstalling
**refuses core modules and modules another installed module requires**, and only clears the capability
key — **data is always retained** and reinstalling restores the surfaces. Every mutation locks the
makerspace row, validates through `validate_capabilities`, and audits `makerspace.capabilities_changed`.
`apps/makerspaces/module_profiles.py` defines **minimal / lending / workshop / recommended / everything**
(`lending` = a tool library with no machines; `workshop` = machines + service queue + maintenance, no
lending extras). **No profile can go below core**, so `workshop` still ships the request/evidence/QR
spine — the Hard Rules make the loan flow the system rather than a feature of it. Going leaner than
that is the *other* axis: `python manage.py suggest_tombstones` reads what every makerspace actually
has installed and prints the `TOMBSTONED_APPS=` line to paste into `.env`. It is conservative by
construction — an app is suggested only when **no** makerspace uses any of its modules, because a
tombstone is process-global and would break the one tenant still using it. Apps owning no module key
(`warranty`, `presence`) are listed separately for a by-hand decision. `setup_instance --profile` remains available to legacy CLI automation and applies only on creation.
The guided installer instead selects areas in its up-front questionnaire, deriving all satisfiable
features from the registries and applying validated answers through `apply_setup_areas` on stdin.
It offers neither profiles nor individual module questions. The change menu uses the same areas,
asking follow-ups only for newly enabled areas; uninstall always retains data. Inventory off clears
`loans.enabled` while keeping core. Registry defaults are unchanged; areas are an explicit operator
choice, never a rewrite of existing tenants.
Core modules are **added back by `_canonical_modules`, not rejected** — no caller has to carry the core
set and no otherwise-valid save fails on a row that lost one. Because `public_inventory` is core, the
module can no longer express "private makerspace"; the existing `Makerspace.public_inventory_enabled`
catalogue switch does. `public_site_enabled` independently controls directory publication,
embed-key validation and public machine listings; its migration copies the previous catalogue flag.
The **minimal profile turns both off** until the operator opts in.

**Per-space module families.** `loans.enabled` is a default-on feature under `staff_admin`.
Turning it off hides loan tabs, bootstrap loan modules/workflows and loan dashboard counters,
and refuses the public catalogue and new borrowing with 400. It never uninstalls core or changes
loan rows. Retained-loan policies, charge tracking and payment rails remain independent.
`public_landing_page` selects an available family; auto chooses the first available
catalogue/events/bookings/machines/membership surface. Bookings has no membership dependency:
active accounts may book, while existing memberships retain waiver and active-status obligations.
Advance booking does not require presence. Events also has no membership dependency: members
remain the default audience, with account/invite admission behind the opt-in event features.

**Disabling a module is race-safe under the row lock, never at the form.** `require_module` at a view
boundary reads an **unlocked** row, so a concurrent uninstall can commit in the window between that check
and the create. `guards.require_module_locked(makerspace, key)` re-checks under `select_for_update` and
must be called **inside the creation service's `transaction.atomic()`, next to `check_quota`** — every
`module_install` mutation takes the same makerspace lock, so one lock and one ordering serializes creators
against disablers exactly the way `check_quota` serializes creators against each other. Validating on the
disable side instead does not help: it loses the same race from the other end. Guarded creation paths:
event create + publish, booking create, machine create + unretire, machine-service submit
(`service_workflow._require_module(..., locked=True)`, whose error shape stays identical to the unlocked
call). Calling it outside `atomic()` raises `TransactionManagementError` rather than silently not locking.

**Per-module purge is NEW semantics, and is the irreversible second step after uninstall.**
`lifecycle.purge()` deletes an entire archived makerspace; `makerspaces/module_purge.py` deletes **one
module's rows while the makerspace stays live**. Contract: the module must **already be uninstalled**
(uninstall retains everything and is reversible — no single command may both hide and destroy),
**superadmin-only**, re-checked under the makerspace lock inside one `transaction.atomic()` that suspends
immutability triggers transaction-scoped the same two ways the makerspace purge does
(`session_replication_role='replica'` self-host, `app.allow_immutable_delete` GUC on
`MANAGED_POSTGRES`), with object-storage keys collected **before** the delete and removed **after** the
commit, best-effort. `module_purge_plans.py` is the per-module declaration; a module absent from it either
owns no data or is listed in `NOT_SEPARABLE` with the reason (core modules, and `machines`, whose rows
host warranty, consumables and service history). **NO MODULE PURGE DELETES A `Payment` — reversed
deliberately on 2026-08-11, and `payment_subjects` is gone from `ModulePurgePlan` entirely.** Switching a
module off and purging its rows is not grounds to destroy the record of money that really changed hands: a
receipt must stay visible and a pending charge payable, which is the same reasoning that always retained
membership dues. A `Payment` is **payments**-module data; its subject vanishing is not its business. Three
things this required, and the first two are what made it safe rather than reckless:
- **`Payment.clean()` had to learn to tolerate a missing subject**, because `save()` calls `full_clean()`
  unconditionally. Without it, every WRITE path broke once the subject went: hosted checkout created the
  provider session then failed persisting its URL, mobile intent 503'd, offline reconcile/waive raised an
  untranslated `ValidationError`, and **webhook settlement 500'd and rolled back its idempotency row**, so
  a charge that really settled at Stripe could never be recorded. `_subject_identity_unchanged()` gates it
  and is deliberately narrow — a **saved** row still naming the same makerspace, subject and member.
  Skipping merely because `pk` exists would let an existing payment be repointed at a foreign subject, and
  a **new** payment still requires a real same-tenant subject.
- **`Payment.subject_label` is snapshotted at creation** and read **FIRST**, before any live lookup
  (`payments/subjects.py`). Snapshot-first is not an optimisation: event titles and space names stay
  editable after a charge exists, so live-first silently rewrites what a paid receipt appears to have been
  for. The live fallback exists only for legacy blanks and now carries the owning makerspace/member ids,
  because it was keyed on **global subject pk with no ownership check at all**. It must never return an
  empty string — Stripe rejects a blank `product_data.name`, and this value feeds the checkout line item.
  The column is financial metadata and **must never carry PII**: titles and space names, never a person's
  name, contact details or custom-form answers.
- **KEEPING A CHARGE PAYABLE MEANS KEEPING IT SETTLEABLE, and machine scoping broke the second
  half.** `reconciliation._require_machine_scope` compared the *scoped* service-request ids against
  every machine-service `subject_id`, so once the request was purged the sets could never be equal
  and **both mark-offline and waive 403'd for every actor** — the pending charge was stranded
  forever: unwaivable, and unrecordable if the member paid cash at the desk. Preserving a payment to
  keep it payable while making it impossible to settle is the same failure wearing the opposite mask.
  The comparison is now against the ids that still **exist**, and the orphans are gated separately.
  Failing **open** to every `MANAGE_MACHINES` holder was rejected: machine scoping is documented as
  failing closed and that would silently widen a role narrowed to one team. An orphan names no
  machine, type or team, so there is nothing left for scoping to answer — it is actionable only by
  the actors that mechanism **already exempts** (space manager, superadmin, null-`assigned_role`
  legacy fallback), all of whom are unscoped everywhere else. **Only machine-service was affected**:
  the booking/event/membership arm scopes `Payment` rows by makerspace and never dereferences the
  subject, which is why the bug hid — three of the four subject types were fine.
- **`lifecycle.purge` (whole makerspace) still deletes every payment** and is untouched, because
  `Payment.makerspace` is `PROTECT` — the rows cannot outlive their makerspace. Preservation is a
  module-purge property only. (The archive gap noted here is **fixed** — see the archive section below.)
Still declared per plan: **`PiiBlindIndex` rows** (keyed HMACs of PII with
**no FK** to the source row, so nothing cascades them — leaving them is a real leak). Encrypted envelopes
live on the source row itself, so they go with it. **A per-module purge must respect the modules that are
still installed**, which is why `_machine_service_delete` is not `service_lifecycle.delete_for_makerspace`:
consumable **pools stay** (they are gated by `require_module(..., "machines")` and are PROTECT-referenced
by surviving manual usage entries), while usage entries **derived from a purged service request go** —
they carry the requester's name/email/phone copied off the request, and their blind-index rows are cleared
**per object id, not per label**, or the surviving manual entries lose their search rows. Consumable ledger
rows are deleted, not reversed: the material really was consumed, so a pool keeps its `remaining_grams` and
loses only the trail. `MakerspaceMembership` survives a `membership` purge
(core RBAC state, plan A7); its waiver acceptance is under an all-or-none check constraint, so the three
acceptance fields are cleared **together** before the waivers go. Membership-dues Payments are deliberately
retained — their subject still exists. CLI: `python manage.py purge_module_data <key> [--makerspace slug]
[--actor username] [--yes|--list]`, slug-typed confirmation, and a platform-scoped
`makerspace.module_purge_started`/`module_purged` audit pair naming a real superuser actor.

**The `email` module gates tenant mail only.** `integrations.dispatch.email_module_blocks(makerspace,
stream, event)` is the single gate, and it is checked in **three** places, not one: `dispatch_email()`
(new mail), `_deliver()` (a row can sit in Celery across an uninstall, and retry re-enters here), and
transitively `retry_email_log()`, whose existing FAILED/SENDING whitelist already refuses the new status.
A blocked message becomes a **terminal `EmailLog.Status.SKIPPED`** row — recorded, not dropped, so the
operator can see what the toggle suppressed — and `SKIPPED` is neither a delivery nor a failure:
`notify._dispatch_email_delivery` counts it as neither, because `notify_return_due` returns
`bool(delivered_counts)` and a skip must not read as a reminder that went out. Three messages are
**exempt, matched on stream AND event** (an event name alone is not unique across streams):
`("account","password_reset")`, `("account","email_verification")` — missing the second leaves a new
account unable to verify and therefore unable to join — and `("hardware","return_reminder")`, a
duty-of-care message in the accountability flow (`integrations/dispatch_policy.EMAIL_MODULE_EXEMPT`; the
two backup custody alarms left this list with custody itself in P1b). **Platform mail (`makerspace=None`) is never gated**:
no tenant owns it, and the platform-level `integrations.email.email_enabled()` behind `/api/v1/config`
is *deliverability*, not tenant enablement — conflating them hides forgot-password from the login screen.
Because modules are opt-in, a newly registered key is off by default, which is right for a new makerspace
and catastrophic for an existing one; migration `makerspaces/0050` is the one-time backfill (with a working
reverse) that keeps every pre-existing space sending mail across the upgrade. Any future default-on module
key needs the same treatment.

**The member dashboard is membership-module-gated; money is not (2026-09-06, D8).**
`member_activity_views` already calls `require_module(makerspace, "membership")`, so the
dashboard simply does not exist for a space that runs no memberships — and every frontend query
feeding it must include `membershipModuleOn` in its `enabled`, or it calls a gated endpoint and
errors. `member_dashboard_service` adds loan history, request history (previously only ACTIVE
self-checkout loans were visible, so a member could not see a request they submitted), dues, the
member's own plan term (`membership_term`, 2026-10-09 — current-else-latest, `current` computed with
`require_current_term`'s own predicate, `blocks_borrowing` when none is current and the space refuses
lapsed members) and notices (`term_lapsed`, `term_ending_soon` within 7 days). Notices are DERIVED from
member-owned rows: `notifications.Notification` is
makerspace-wide, has no recipient column and shares one `read_at`, so serving it would leak staff
alerts and let one member's read mark speak for everyone. Payment/receipt visibility sits OUTSIDE
the gate — `member_may_see_own_charges` admits an account with no membership that owns a charge
here, because a loan deposit is raised against a BORROWER who needs an active account rather than
a membership. It preserves every account-status clause and still refuses a revoked member, which
is a deliberate pre-existing contract.

**Personal usage (analytics 1f-4)** is `GET /member/makerspaces/<id>/my-usage`, next to
activity. It accepts no target member: every source is filtered by `request.user` and
the server-resolved tenant, without invoking staff reports. An active membership plus
the `membership` module enables non-payment usage; otherwise an eligible caller receives
only `payments` with `usage_available=false`. Payments use `member_may_see_own_charges`
and `member_payment_queryset`, preserving own-charge and collaborative-event routing
without requiring membership or the online rail module. Revoked/inactive memberships
are refused here, including the separate rejoining-admission exception. Recovery and
archived payment surfaces remain in payments; my-usage requires a servable tenant.
Loan counts represent handovers, deduplicating a direct loan's workflow request; monthly
returns count ReturnEvents by event time, including partial returns; only legacy direct
returns without events fall back to `returned_at`, and quantities are never inferred. Machine hours use
only attributed `MachineUsageEntry.member` rows, never staff/contact identity inference.
Monthly charts use the tenant timezone; cancelled bookings are excluded; events count
attended registrations. Paid and outstanding amounts remain partitioned by currency.
Responses are private/no-store and carry typed chart specs. Web and native member grants
share this contract; a claim session stays tenant-local through the existing claim policy.

**A pending payment no longer refuses a tenant dump (2026-09-06, owner decision D5).** Both
refusals are gone — `tenant_dump_cross_tenant` and `_source_row_allowed`. What makes carrying an
unsettled debt safe: (1) `preflight._check_live_checkouts` refuses any pending row with a live
rail, and it now counts `stripe_payment_intent_id` as live, not just hosted sessions; (2) pending
rows are held to the same `PAYMENT_CLEARED_VALUES` projection as terminal ones, so no order id,
session, intent, checkout URL, connected account or routing survives to be resumed on the target;
(3) `money_digest.money_fingerprint` is taken INSIDE the capture gate over pending payments plus
the settlement chain, and `publish_tenant_dump` revalidates it under the makerspace row lock, refusing
with `money_drift` when the source has moved on. Terminal rows are deliberately excluded from the
digest: they are immutable, so they cannot drift, and including them would make every ordinary
settlement read as drift. A blank digest (captures predating the field) is not revalidated —
blank means "not recorded", not "nothing owed". `provider` stays PRESERVE on pending rows: every
actual handle is cleared, so it is inert, and a target whose vendor differs simply resolves no
source and settles the charge offline.

**The payment ledger cannot be tombstoned; the rail can (2026-09-06).** `apps.payments` holds
the models and every ledger surface and is NOT in `SEPARABLE_APPS`; `apps.payments_rail` holds
checkout, the native intent, Connect, refunds, credential settings and the webhooks, and is what
a tombstone removes. Before the split, `TOMBSTONED_APPS=payments` withdrew the reconciliation
console and the member's own payment history — which, once debts could be recorded with no
gateway, meant such a deployment accrued money owed that nobody could read or settle. Existing
deployments keep writing `payments` in their env: `RENAMED_LABELS` translates it, so upgrading
does not fail `separability.E007`. The machine-service mark-offline/waive routes became
unconditional for the same reason; only the credential routes moved to the rail gate.

**Charge tracking is separate from the online rail (2026-09-06).** `charge_tracking_enabled` decides
whether a debt is RECORDED; `online_payments_enabled` decides only whether a Stripe/Razorpay rail may be
raised for it, and keeps all four of its clauses. The `charges.*` family carries tracking and is
deliberately free of any `payments` dependency, so uninstalling the module cannot prune it; `payments`
became **opt-in** at the same time. A charge raised with no gateway carries `provider=unclaimed` and is
claimed exactly once by the first checkout that reaches a provider, enforced by the payment
terminal-guard trigger. Settling one offline requires an append-only `ManualSettlement` receipt written
in the same transaction as the status flip. NOTE: the line below calling `payments.enabled` standalone is
stale — it is parented to the `payments` module, and the per-domain `payments.*` keys are parented to
their own domain modules with `payments` in `requires_modules`.

**Booking ledger writes are required (BK-0, 2026-10-15).** With charge tracking enabled,
instant creation and approval commit their required debt in the booking transaction.
Debt lookup, insert or audit failure rolls back confirmation, calendar revision, audits
and post-commit notification callbacks. Recurrence retains its outer atomic transaction:
a required ledger failure rolls back earlier occurrences too. Cancellation likewise
requires the pending-charge update and audit to succeed with the booking transition;
failure rolls both back. Missing or nonpending charges remain a valid no-op, settled
money stays unchanged, and tracking disabled after confirmation does not prevent
cancelling an existing pending debt. Optional rail readiness, checkout scheduling and
post-commit checkout remain best-effort. Provider expiry/native-intent cancellation
retain the existing best-effort boundary in `payments/reconciliation_rail.py`.
No feature flag may bypass these ledger guarantees; cancellation provenance added by
BK-B must join the same transaction.

**A6 master switches are additive `AND`s, never replacements.** `payments.enabled`, `mobile.push` and
`presence.geofence` are standalone (`parent_module=None`) features that sit **in front of** the readiness
check each capability already had — `online_payments_enabled` still requires the per-domain
`payments.<domain>` feature *and* resolved credentials; `deliver_native_push` still requires platform
FCM/APNs; `evaluate_geofence` still requires `geofence_effective`. Turning a master switch **on** can
therefore never make an unconfigured capability start working. `evaluate_geofence` returns `None`
when disabled; `require_inside` treats that as unavailable and refuses self check-in with staff
guidance. Authorized staff check-in remains available without location. They must
stay **independently switchable**: do *not* express the coupling as `requires_features` on the domain
features, because that would make the kill switch un-flippable until every domain was unticked first.
All three **default enabled** so their introduction changed nothing, and migration `makerspaces/0051`
backfills them onto pre-existing rows (`enabled_features` is stored per row, so a `default_enabled` flip
alone would read as OFF for every existing space). Bootstrap omits `geofence_enabled` entirely when the
feature is off, preserving the byte-for-byte dormant-payload invariant. A test that enables
`payments.<domain>` by assigning `enabled_features` wholesale must now include `payments.enabled` too.

**Social sign-in is platform-scoped and must never become a tenant feature** — it resolves before a
makerspace is selected, so a `social.*` feature key would be unreachable at token-verification time and
read as disabled for everyone (`test_a6_toggle_scoping.py` pins this). Disabling a provider is the
dangerous direction: `accounts/social_lockout.py` refuses, at the `/control/` form, to clear the last
credential of accounts that have that provider, no other provider, and no usable password — those users
cannot be recovered by forgot-password because there is no password to reset. Inactive users don't block
the change. This is the platform-wide twin of the per-user `last_credential` guard in
`unlink_social_identity`.

**The staff console's feature list is a hand-kept mirror and is drift-guarded.**
`frontend/src/lib/features.ts` `FEATURE_DEFINITIONS` backs the Space-Manager feature checkboxes;
`tests/test_capabilities.py::test_frontend_feature_definitions_match_the_backend` parses that file and
fails if it diverges from `capabilities.FEATURE_DEFINITIONS` (keep the one-object-literal-per-line shape
the guard reads). A feature missing there is invisible to the Space Manager who owns it, and a stale
`parent_module` renders a wrongly-disabled checkbox — which is omitted from the PATCH and silently clears
the capability. **Regenerating the OpenAPI snapshot requires the pinned toolchain**: `requirements.txt`
pins `drf-spectacular>=0.30`, and regenerating with an older installed version rewrites ~240 unrelated
lines (`allow_blank` `oneOf` wrappers, `nullable` on file fields) — check `pip show drf-spectacular`
before `manage.py spectacular`, and expect the diff to contain only what you changed.

**Two-level capabilities (modules + features).** `Makerspace.enabled_modules` (whole modules) is
**superadmin-only** — edited only in the `/control/` capability matrix; a staff-API PATCH containing
`enabled_modules` is a hard **403**. `Makerspace.enabled_features` (namespaced sub-features via the
`apps/makerspaces/capabilities.py` registry — `payments.machines|bookings|events|membership`,
`inventory.self_checkout`) is **Space-Manager-writable** (`MANAGE_MAKERSPACE`), validated so a feature can
be enabled only when its parent module (and any `requires_*`) is on, and audited (`makerspace.features_changed`).
A `FeatureDefinition.parent_module` of **None** = a standalone feature with no module prerequisite (effective
purely when enabled) — `inventory.self_checkout` is standalone (self-checkout + staff direct handouts are
per-makerspace loan capabilities independent of the public catalogue; they must NOT be reparented under
`public_inventory`). `feature_enabled`/`require_feature` (typed key `feature`) mirror the module guards;
bootstrap exposes effective `features: string[]` + feature-workflows. `payments.*` keys are **dormant
substrate** in the capabilities layer — enforcement lands in the payment tracks (C.2/C.3), not here. The
`/control/` matrix widget must derive its disable rule from each feature's real `parent_module` (never
disable a parentless feature — a disabled checkbox is omitted from POST and would silently clear the
capability). Widget templates live in the **app** templates dir (`apps/<app>/templates/...`), not project
`templates/`, so the form renderer (app-dirs only) finds them. The matrix's **module** choices come from
`module_registry.MODULES`, never from "defaults + keys already on the row" — that older rule made any
non-default module unreachable for a makerspace that didn't already have it (`notifications` was enforced
but un-enableable), and under opt-in defaults it would have hidden nearly the whole registry. Core is
**labelled, not disabled**, and unrecognised stored keys stay selectable so an untouched save can't drop
them.

**The `membership` module gates the community feature, not RBAC (A7).** `MakerspaceMembership` is core
RBAC state, so gating it wholesale would lock a makerspace out of its own staff administration.
**Never gated:** membership list/create, role assignment, revoke, capabilities, staff roster,
`memberships/me`, and waivers (member read + accept, staff publish + witness — liability evidence, made
core by `cd2936d1`). **Gated by `membership`:** public join request, community requests in the queue and
the approve/decline on them, verify/unverify, member activity, referrals, profiles/directory, member cards,
plans and terms. Community invitations through `membership_services.invite_membership` are
Member-only and membership-gated at issue, queue, approval/decline and claim; referrals remain gated
with their additional `referrals_enabled`/`can_refer` checks. Built-in staff onboarding now uses
`accounts.staff_account_services` and account-bound initial-password invitations, outside this
community queue. Membership off never blocks staff creation or administrator password issue.
Email onboarding additionally needs Email + `staff.invitations`; with either off, use admin-set
passwords. The old shared invitation path must never grant staff roles to member accounts.

Staff invitation and activation/welcome owner mail uses the core `account` stream without the
community `members` category. Its source still rechecks the live role, owner, sender and revision;
the envelope or compatibility outbox owns the email leg exactly once. Community mail and existing
membership staff summaries retain their membership category and gates.

**Membership plans, terms and invitation requests (forward plan phase 6, 2026-09-04).** Plans are optional
and never an access state: a `MembershipTerm` expiring changes neither `MakerspaceMembership.status` nor
`User.access_status`; the only effect is the per-makerspace opt-in `lapsed_members_cannot_borrow`, enforced
solely by `request_access.require_current_term` AFTER the who-may-submit rule has admitted the member
("current" = `status=active AND starts_at <= now` with expiry or promised grace still ahead,
so it does not depend on the hourly sweep), and a member who
has never held a term is untouched. **It is called on every path that HANDS a member a tool** — request
submission, self-checkout and its issue-evidence presign, and staff direct handout — and on no path that
takes one back: a lapsed member can always return. (It had one call site, request submission, until
2026-10-09: a lapsed member could still self-check-out or be handed a tool at the desk, and the switch was
missing from the settings serializer, so the console toggle never rendered.) It is inert while the
`membership` module is off, since plans are that module's. Bookings, events and machine service are not
borrowing and are not covered. One renewal charge per term, raised only by
`membership_plan_services.run_membership_renewals` as `Payment(subject_type=membership_term,
subject_id=term.pk)` inside the manual plan's 7-day window or the opted-in plan's local-day
renewal window, only when `charge_tracking_enabled(ms, "membership")`. Debt commits before
checkout creation; checkout retries reuse that debt. Optional `membership.auto_renew` plus
the plan's `auto_renew` opens exactly one successor after settlement/waiver, or without
charge tracking for a free renewal. `renewed_from` is one-to-one and remapped on import.
Promised `grace_until` survives policy changes and import; expiry never auto-revokes.
Cancellation stops renewal in the current lifecycle; a fresh audited admission resets it.
Owner-only lifecycle mail and subject exports require their separate opt-in features.
Personal export row ownership intersects tenant RBAC and uses the reviewed export field
classification; staff tenant-export routes and runners refuse personal jobs.
An `InvitationRequest` is a lead, not authority:
name/email/phone are scoped source PII (encrypted at rest, purged with `membership`, `(PRESERVE, DROP)` in
tenant dumps), the public endpoint answers the same 202 to real and honeypotted submissions, and "Invite"
only ever calls `membership_services.invite_membership`, inheriting the role non-escalation and the
community/staff discrimination of a hand-typed invitation.

**Payments (Stripe, C.2/C.3; dormant until configured).** `apps/payments.Payment` is the **single payment
authority** (one row per subject via unique `(makerspace, subject_type, subject_id)`; positive amount;
statuses pending/paid_online/paid_offline/waived/canceled; terminal rows immutable — **enforced by a Postgres
BEFORE UPDATE/DELETE trigger that blocks terminal-row mutation AND blocks DELETE unless the purge GUC
`app.allow_immutable_delete='on'` is set; `Payment`+`ProcessedStripeEvent` are in the lifecycle purge graph**).
Effective online payment = `feature_enabled(ms,"payments.<domain>")` AND `MakerspacePaymentSettings.is_configured`
— blank creds fail closed; no platform-wide Stripe fallback (a **Stripe-Connect creds track** for managed hosting
is planned, self-host stays per-makerspace raw keys). The webhook settles both synchronous
(`checkout.session.completed` payment_status=paid) and **asynchronous** (`checkout.session.async_payment_succeeded`,
matched by session id) charges. **Machine-service pricing lives in `apps/machines.MakerspaceMachineTypePricing`
(per makerspace × machine_type; built-in AND custom types; `rate_per_unit`/`flat_fee`/`payment_enabled`),
NOT in `MachineType.capability_config` (which is structural-only — no pricing/payment keys); currency = the
makerspace default currency snapshotted into `Payment`; the charge quantity is `service_payments.effective_quantity`
(minutes→`actual_minutes`, else `actual_consumed_quantity`, else grams). Configuring machine types AND their
pricing is gated by `rbac.is_space_manager_identity` (space-manager membership only — NOT `MANAGE_MACHINES`
breadth — honoring archived scoping; surfaced to the console via the per-membership
`can_configure_machine_types` flag).** **Never-block:** machine `complete()`/`collect()` succeed even if
Payment creation or Stripe checkout fails; checkout is created post-commit best-effort (and can be regenerated
on demand via the member endpoint). **Webhook always settles:** `apply_webhook_event` verifies the
per-makerspace signature on `request.body`, is idempotent via `ProcessedStripeEvent`, and settles a matching
pending Payment to paid_online **regardless of the live feature toggle** (a real charge is never stranded); a
paid event for an already-terminal payment is audited (`payment.paid_after_terminal`), not dropped. Reconciling
(mark_offline/waive) best-effort **expires** any live Checkout session. Checkout return URLs come from
`platform.member_area_url` (VERIFIED custom domain → `/member`, else shared `/m/<slug>/member`). Legacy
`MachineServiceRequest.payment_*` are **read-only historic** (a backfill migration maps them into Payment);
refunds are out of scope. Amounts are staff-private (serializer split); requesters/members see status + own
checkout link only.

**Payment credentials, subjects, and reconciliation (Phase C final tracks).** Self-hosted makerspaces
may manage their own encrypted Stripe credentials; managed hosting resolves through platform Stripe
Connect without exposing secret values. Credential mutation validates live Stripe ownership and protects
in-flight checkout/webhook sessions. Booking, event-registration, membership-dues, and machine-service
charges all create the same immutable `Payment` subject rows. Reconciliation is makerspace-scoped through
RBAC, reports/dashboard aggregates never flatten tenants, and offline/waive actions audit the actor and
best-effort expire live online sessions.

**Per-makerspace provider setup.** Space Managers select Stripe or Razorpay and provision
their own credentials through the staff payment-settings API/panel (`MANAGE_MAKERSPACE`,
scoped through RBAC). Provider/credential writes require
recent server-owned session reauthentication. All credential inputs are write-only, including
public keys; responses contain set booleans and exact per-space webhook URLs. Omission preserves
a credential, `""` clears it, and secret setters encrypt it. Audits contain field names only.
Provider selection is checked again under the checkout coordination settings-row lock and
returns 409 `payment_provider_conflict` if the other vendor has a pending collection with a
live hosted/native handle (the same handle/expiry rule as tenant-migration preflight).
Razorpay rotation/clearing likewise refuses pending Razorpay collections. Bare debts do not
block selection. This does not change charge tracking or the online-payment availability gates.

**Refunds and loan charges (forward plan phase 6, 2026-09-04; owner decision 7 defaulted to "charging
allowed, off by default").** A `Payment` row never changes for a refund: refunds are `payments.Refund`
ledger lines on a `paid_online` Payment, the sum of PENDING+SUCCEEDED refunds never exceeds
`payment.amount` (enforced under the Payment row lock and in `Refund.clean()`), a settled refund is
immutable, provider I/O happens outside every row lock, and webhooks (`charge.refunded`/`refund.*`,
`refund.processed`) only ever settle a locally raised PENDING row through `_record_once` — a dashboard
refund this deployment never raised is logged, never invented. Loan charges (`LOAN_DEPOSIT`,
`LOAN_LATE_FEE`, one each per request by the subject uniqueness) are raised only by the workflow module,
post-commit, through `apps/hardware_requests/loan_payments.py`, and never block a handover or return —
except the one opt-in gate: with `loan_deposit_blocks_issue` on, `issue_request` refuses with
`deposit_required` (409) **before** the QR/evidence Hard Rules, fails OPEN on payment-system errors, and
the deposit it raised is the row the later issue accepts. A late fee is computed exactly once at close
(`ceil(days past due + grace) × per_day`, capped when the cap is > 0) and never recomputed; an uncollected
deposit is cancelled at close, a collected one is released only by a staff refund. `payments.loans` is an
additive AND behind `payments.enabled`, the `payments` module and resolvable credentials; off means nothing
is raised and lateness is only recorded.

**Refund cases are entitlements, never money (decision #59/#60, 2026-10-21).** `payments.RefundCase`
records what a member may be owed; it never counts against the refundable balance, is never settled by a
webhook and never blocks deletion as a pending refund does. The ONLY path from a case to money is
`services_refund_decisions.approve_case`, a staff action, which creates the `Refund` under the lock order
domain row -> Payment -> RefundCase -> Refund (the same Payment-first order as `settle_refund`). Rules:
- **One active case per payment** (`open`/`approval_failed`, DB-conditional unique) and at most one
  policy assessment (`kind=due`) per payment. Every writer locks the Payment first and decides both rules
  under that lock, so a booking cancellation never raises an IntegrityError: a cancel UPGRADES an active
  member request in place, and a member asking on an open due case adds their reason to it.
- **A case opens only when something is owed** (R5): a cancellation whose due is zero opens nothing; a
  member request opens with due zero and staff decide the amount. Loan deposits are never requested (their
  release path is `release-deposit`).
- **Due arithmetic** (`refund_policy.assess`): balance cap first; a space-cancelled event and a booking
  staff cancelled on a member's behalf (`staff_cancelled`, decision 72) owe the full balance; otherwise the area policy band (full / percent / nothing) minus the fee (space currency only)
  minus refunds already made, floored at zero, rounded DOWN to min(ISO exponent, 2). Policy areas are
  `events`, `bookings` and `membership` (owner decision 68, superseding the membership half of #60). No
  per-event override in v1.
- **Membership terms** (`refund_policy_membership`): a renewal charge raised against term T pays for the
  term opened with `renewed_from = T`, so that successor is the covered term. One default rule per space
  plus optional per-plan rules (`RefundPolicy.plan`; a plan rule wins). Full refund before the term starts
  or within `full_within_days` of its start; then `partial_mode` `pro_rata` (amount x unused / total, multiplied
  before dividing) or `percent` until the term ends; then nothing; minus the fee. A paid renewal whose term
  never opened is owed in full. `cancel_term` (and so membership revocation) opens the due in its own
  savepoint for both the term's own renewal and the charge that bought it; "do not renew" only voids a
  pending renewal and opens nothing. Dues and admission charges have no term: request-only.
- **Approval re-clamps** to the live balance, refuses more with 409 `refund_exceeds_balance`, and voids the
  case (then 409) when nothing is left. A refund raised outside a case voids every active case once the
  balance reaches zero (`void_exhausted_cases`, called inside the Payment lock by `open_refund_locked` and
  `record_offline_refund`); approval marks its own case approved BEFORE creating the refund for that reason.
- **Authority**: deciding is `_require_subject_authority` per case (+ machine scope); VIEW_FINANCE reads the
  whole queue but cannot decide; an offline approval also needs RECORD_PAYMENT and a receipt. Online approval
  calls the provider after commit; a refusal moves the case to `approval_failed`. With `payments_rail`
  tombstoned an online case answers 409 `refund_rail_unavailable` -- decline is its only exit.
- **Events and membership-term cancellation swallow payment errors**, so `refund_case_sweeper` rebuilds
  missed due cases hourly in both schedulers (bounded 7-day lookback, and NEVER before the deploy
  watermark -- the apply time of `payments.0023_refund_cases` in `django_migrations`, so the first deploy
  back-fills nothing; no record means the sweep does nothing (decision 72); terms are timed by their
  `membership.term_cancelled` audit entry; the events half is skipped when `events` is tombstoned). Bookings open their case
  in the cancellation transaction and roll back with it.
- Open, approved and approval-failed cases join `money_fingerprint`; purges delete cases before refunds
  (both PROTECT); an undecided case is the `refund_under_review` deletion blocker.
- Stripe Connect refunds send `refund_application_fee` when the charge carried a platform fee and never
  `reverse_transfer` (direct charges have no transfer).

**Payments completeness pass (2026-10-09, lane `payments`).** Five rules the audit found broken or
unpinned; each now has a test under `tests/payments/`:
- **A closed hosted checkout is forgotten in BOTH column pairs.** A checkout is recorded in the
  Stripe-shaped columns and the generic `external_order_id`/`checkout_url`; the expiry webhook and
  credential rotation cleared only the first pair, so `create_checkout_url` handed back the dead
  link forever. `payments/checkout_expiry.forget_closed_checkout` is the one place that clears a
  closed page, and `live_checkout_url` is the one reader (member list, checkout endpoint, service):
  a link counts only while `stripe_checkout_session_expired_at` is null. `stripe_payment_intent_id`
  is never cleared there — it is the refund anchor.
- **Native payments dispatch on the Payment's resolved vendor BEFORE any provider call.** Stripe
  PaymentSheet keeps its PaymentIntent rail; Razorpay native Checkout uses an Order. A Razorpay
  source carries its key secret in `secret_key` and must never be passed to Stripe. Both response
  branches carry `vendor` and `payment_id`; hosted checkout and native rails remain mutually exclusive.
  Razorpay recovery is lookup-first: fetch a stored order, otherwise search by deterministic
  `sw-pay-<payment.pk>` receipt (at most 40 characters) before creating. Reuse requires an exact
  receipt, matching payment/makerspace notes, integer minor-unit amount, currency, and
  `created`/`attempted` state. A duplicate-receipt 400 repeats that lookup; incompatible provider
  state fails closed with a logged 503. Provider error descriptions stay out of logs and responses.
  Offline settlement/waiver marks native Orders closed locally; Orders never reach the Payment
  Link cancellation API, and their IDs remain available for late-capture matching.
- **Razorpay captures retain the refund anchor and deduplicate excess by provider payment ID.**
  Pending or waived charges settling online store the capture's `external_payment_id`. Other
  terminal rows are untouched. A different capture is audited once per provider payment ID as
  `payment.double_paid_refund_required`, with `provider_payment_id`, `amount_minor` and `currency`.
  `order.paid` and `payment.captured` for the same capture never flag excess. Staff refund excess
  collections in the provider dashboard using that audit ID; no in-app refund action or change to
  `Refund.counted_total` is involved, preserving the original charge's refundable balance.
- **Provider amounts use the currency's ISO 4217 exponent** (`payments/money.to_minor_units`): zero
  for JPY/KRW and the rest of Stripe's zero-decimal list, three for BHD/JOD/KWD/OMR/TND. Checkout,
  the provider seam, native intents, refunds, the Connect fee and refund-webhook matching all use it;
  `int(amount * 100)` anywhere in a money path is a bug.
- **Purges delete `Refund` rows before `Payment`.** `Refund.payment` is PROTECT, so both the
  makerspace purge and `machines.service_lifecycle.delete_for_makerspace` raised ProtectedError for
  any space that had ever refunded. Manual settlements still cascade.
- **Receipts reach both sides.** The staff reconciliation row carries the standing manual receipt
  (`settlement`, with `corrected` when amended) and the console corrects it through
  amend-settlement; the member row carries `refunded_amount` and `refunds` (never `created_by`).
  `StaffPaymentSerializer` deliberately drops the refund fields so the machine-service queue does
  not grow a query per row. The machine-service waive route now answers 409 on a terminal charge,
  like every other reconciliation route, instead of a silent 200.

**Native clients use attested device grants, never browser-token shortcuts.** Device login starts with a
short-lived attestation challenge and creates a revocable `DeviceGrant`; access tokens carry
`device_grant_id`, refresh tokens rotate in a grant family, and replay revokes that family. Native
staff makerspace selection requires `X-Makerspace-Id`, an attested staff-kind grant, its fixed
tenant and active local staff membership;
core own-charge surfaces retain their account-only ownership exception. Push
tokens are encrypted with an HMAC dedup fingerprint, owned by a device grant, and disabled when a provider
reports them invalid. Native Stripe PaymentSheet and Razorpay Orders delegate to the same
Payment/provider resolution as web checkout, with rail-specific idempotency/recovery.
Native staff issuance requires staff kind, password, MFA and attestation. Phone/social/OIDC
issuance is member-only; platform accounts cannot receive native grants.
`session_authority=native_staff` still requires current local actions and a selected makerspace
matching URL/body targets. Refresh cannot promote a member grant, organization grants never
supply native authority, and both forms of superadmin are refused at device grant issuance.

- **Sign-out follows the credential's scope.** Device logout revokes that grant, its refresh
  families and its push devices; per-session revoke invalidates the selected browser or device
  session. Password change/reset revoke every device grant; account deletion signs out everywhere,
  and restore requires fresh sign-in.
- **`POST /api/v1/auth/logout-all` is global and always available to authenticated browser and
  device sessions**, including account-only members, without a makerspace or feature gate. One
  transaction revokes active browser sessions, legacy refresh sessions, device grants (and their
  push devices), and blacklists outstanding refresh tokens. It audits `auth.logout_all` with counts
  per kind and clears the refresh cookie and selected account context. The response counts browser sessions (including legacy)
  and devices; audit metadata separates modern and legacy browser sessions.
- **Settings-time authenticator enrollment on a device keeps that grant, never mints one.**
  `POST /auth/mfa` from a member device session records the grant in the challenge. Starting
  invalidates the caller's tokens (new MFA version), so `/auth/mfa/enroll` and `/confirm` use the
  challenge as the credential, as on the web; another authenticated grant and browser headers are
  refused, and the result is issued only on the recorded, still-active grant. Enabling revokes
  every other grant, browser session and outstanding token, rotates only the kept grant's families,
  and re-issues a pair on it. No grant is created without attestation. Staff device sessions are
  refused (`native_staff_mfa_managed`); recovery regeneration and disable still sign the device out,
  because re-issuing there would mint an MFA-verified session from a password-only proof.
- **Membership revocation and self-leave invalidate push only in that makerspace.** The shared
  `_revoke_locked` cleanup deactivates the user's active `PushDevice` rows there and stamps
  `invalidated_at`; their grants and push subscriptions in other makerspaces remain usable.

**Native app configuration lives on the registration (phase 1e).** Only one approved global
identity per platform/environment is allowed (database constraint). The
deployment-owned `PlatformAttestationSettings.app_display_name` is edited in `/control/` and
published as `native.app_display_name` alongside `native.app_identity.{android,ios}` (production
app ID and public signer list, or null). Editing the name preserves blank write-only credential
inputs. Signer rotation updates the existing registration; replacing its app ID requires revoking
the old registration before approving the new one.
All native eligibility checks
require an approved deployment-global registration (makerspace IS NULL); association files and
minimum versions additionally require production. Registrations hold 1–5 Android distribution signer
digests or exactly one Apple App ID Prefix. Challenges snapshot the complete list and retain the
first scalar for the external verifier; every grant issuer records the matched signer from verified
metadata, including MFA. Only an empty registration list may consult DEVICE_ATTESTATION_APPS, with
a warning check; new operator configuration needs no env JSON. External verification supports only
the first signer. The legacy tenant_restore_target_state.reconcile_native_app_registrations helper
still rebuilds rows from env declarations, has no caller in this tree, and is a compatibility gap;
it must not be introduced into a live restore without adapting it to stored identities. These
platform security models remain omitted from tenant exports. The highest dotted-numeric production
minimum per platform comes from registrations. Readiness uses one read-only builder for the
superadmin API and /control/ page, with login separate from optional push/revocation/associations,
no secret values, persisted readiness state or provider probes. Registration edits use the existing
control settings audit mixin.

**Mobile associations grant no browser trust.** Exact well-known JSON paths are served only on
configured primary frontend hosts and verified, servable non-archived custom frontend domains.
Managed host middleware keeps its 400 refusal; other untrusted hosts receive view-level 404. The
existing integrations/mobile_link_contract.py supplies all supported components and exclusions.
Only public application proxy blocks route these paths; control-plane and tunnel snippets, their
404 fallback and socket-peer allowlists stay unchanged. See docs/mobile-integration.md.

**Generic OIDC providers are configuration, not a second verification path (phase 17).**
`accounts/models_oidc.OidcProvider` (superadmin-only, platform-scoped) holds `issuer`, `jwks_url`,
`client_id` and two switches; `social_oidc.verify_oidc_token` reuses the same
`social_jwt.decode_rs256_token` the built-ins use, because two RS256 implementations means two
places to get RS256 wrong. This covers Keycloak, Authentik, Azure AD, Okta and Google Workspace —
they differ only in configuration. Load-bearing details:
- **No client secret is stored.** This is the ID-token flow: verifying a signature needs only the
  JWKS, so there is no secret to leak and none is modelled.
- The stored provider key is **`oidc:<slug>`**, namespaced so a provider slugged `google` cannot
  shadow the built-in. `SocialIdentity.provider`/`SocialLoginNonce.provider` widened to 64 and lost
  their `choices` — validity is answered by configuration (`provider_for_slug`), which an enum never
  could. `_available_username` now strips the colon, which Django's username validator rejects.
- **`allow_auto_link` exists for an IdP that does not verify email ownership.** With it off, an email
  match demands an explicit link instead of silently handing over the account. Auto-link still
  additionally requires provider-asserted `email_verified` **and** a locally verified address — the
  switch only allows it to be considered. `email_verified` is parsed strictly: a missing claim must
  never read as verified.
- **`issuer` is compared verbatim, never normalized.** The built-ins accept two spellings only
  because Google genuinely issues both; tolerating a trailing slash generally is how an issuer check
  stops being a check. A provider row **cannot be deleted** in `/control/`, only disabled — deleting
  it orphans every `SocialIdentity` naming it and locks out anyone who never set a password, the same
  lockout `social_lockout` refuses for the built-ins.
- **SAML is deliberately NOT included.** It is not a configuration variant of the same flow: it needs
  XML signature verification (a new security-sensitive dependency), a POST binding, and its own
  assertion/replay handling. It is its own phase, not a footnote to this one.

**Social identity is global; authorization remains per makerspace.** `SocialIdentity(provider, sub)` links
Google/Apple to the global `User`; it never grants a role. Provider JWTs are server-verified against bounded,
cached static JWKS endpoints and one-time origin/device-bound nonces. Auto-linking is allowed only when both
provider and local email are verified. All social/OIDC sign-in and linking is member-only;
native linking uses a nonce bound to the current device grant plus recent reauthentication
(checked before the nonce burns) and the `social_link` throttle; browser linking keeps the origin nonce;
staff/platform accounts use password plus local MFA. Social
tokens carry `surface=member|staff`: member tokens are rejected by staff APIs, while staff tokens require
the exact trusted staff origin and matching tenant scope on access and refresh. Provider secrets remain
write-only/encrypted, and unconfigured social auth is omitted from public config.

**Phone is a login identity on a SEPARATE column, and only when VERIFIED (phase 18).**
`User.phone` stays free-text contact info (non-unique — two members may share a landline, and it is
copied onto requests as text). The identity is `User.phone_e164` + `phone_verified_at`, with a
partial unique constraint on non-empty `phone_e164` (the `uniq_telegram_user_id` shape). Reusing
`phone` was rejected: it would have meant rewriting existing free-text values in a migration and
putting a unique index on a column that already holds duplicates in real deployments; `phone_e164`
starts empty everywhere, so its constraint always applies cleanly.
- **`save()` clears `phone_verified_at` whenever `phone_e164` changes — unconditionally.** That is
  the guard stopping an edited number from inheriting a verified stamp, and `/control/` can edit the
  field, so it cannot live only in the service. Consequence: the linking service must write the
  stamp **after** `save()` via `User.objects.filter(...).update(...)`, exactly as
  `confirm_challenge` does for `email_verified_at`. Setting both in one `save()` silently loses it.
- **Deferred raise, or the attempt cap is inert.** `confirm_link`/`confirm_login` collect a failure
  and raise **after** `transaction.atomic()` exits. Raising inside rolls back the
  `failed_attempts` increment with everything else, so the counter never rises and a code stays
  guessable — the bug that shipped in the first draft and that `test_attempts_are_capped_per_challenge`
  caught. `services_registration.confirm_challenge` defers for the same reason.
- **MEMBER SURFACE ONLY.** `refresh["surface"]` is hardcoded `"member"`, never derived from the
  request. An SMS code is the weakest factor here (SIM swap, number recycling) and staff hold
  destructive powers, so staff must use their tenant password door plus local MFA where required.
- **The login start endpoint is a uniform 200 in every case** — unknown, malformed, suspended, or on
  cooldown. `ChallengeCooldown` is swallowed there on purpose: a 429 only for real numbers leaks
  exactly what the generic ack protects. `LINK` and `LOGIN` challenges are discriminated by
  `purpose`, so an abandoned link code cannot sign anyone in, and the code digest is
  **domain-separated by number** because a login challenge is resolved by number, not by user.
- **Requesting a code and guessing a code have SEPARATE per-number budgets**
  (`phone_otp_number` vs `phone_confirm_number`). One shared bucket meant three typos locked a
  member out for an hour holding a valid code.
- **E.164 is required, never guessed.** `phone_numbers.normalize_e164` strips only separators humans
  type and accepts a leading `00`; a bare local number is rejected rather than assigned a default
  region, because an ambiguous identity is a login that hands one person's account to another. No
  `phonenumbers` dependency.
- **SMS is platform-scoped and dormant by default.** `PlatformSmsSettings` (singleton, encrypted
  token, `/control/`-only) rather than env vars, matching `PlatformEmailSettings` — no new variable
  through four compose services and both installers. `apps/integrations/sms/` is the provider seam
  (`base.py` protocol, `twilio.py` the one impl, stdlib `urllib`), shaped like the encryption key
  broker so a self-hoster outside Twilio's footprint can add one without touching call sites.
  `get_sms_provider()` returns **None** when unconfigured and `/api/v1/config` **omits
  `phone_login` entirely**, preserving the dormant-payload invariant. `reserve_platform_otp_sms_quota`
  is the one quota that **also applies on self-host** — every text is billed to the operator, so it
  is a cost ceiling, not fair use — and it fails **open**, because the security controls are the
  cooldown and the attempt cap.
- **`accounts.User` is deliberately absent from the PII encryption registry**, which is what makes a
  plaintext unique index and a direct login lookup possible: scoped encryption is per-makerspace and
  `User` is platform-global, so it could never be scoped-encrypted.

**`Makerspace.clean()` NORMALIZES capabilities; the explicit call sites VALIDATE.** `clean()` prunes
features whose module is absent (and already adds core modules back rather than rejecting), because a
row must never be unsaveable: `enabled_features` takes its field default independently of
`enabled_modules`, so a makerspace created with a narrow module list is born holding the default-on
`payments.enabled`/`mobile.push` without their modules — and a strict `clean()` then rejected **every
later save, including ones touching neither field**. The operator-facing strictness lives at the two
direct `validate_capabilities` call sites (`/control/`'s capability matrix, `module_install`), so a
conflict somebody actually expressed is still reported instead of silently cleared, and
`MakerspaceSerializer.validate` prunes **only when the request does not carry `enabled_features`** —
if the caller sent features they expressed the combination; if they did not, it is not their conflict.
This reverses a phase-3 rule; `tests/makerspaces/test_module_install.py` carries the reversal and the
reasoning.

**Account-less identity: `accounts` removes the ECOSYSTEM, never identity (module program phase 9).**
`apps/accounts/member_identity.py` is the one seam every member-facing login surface asks, and it has
two exemptions that are load-bearing:
- **Staff authentication is never gated.** Core RBAC — a deployment that could switch off its own staff
  logins could not be administered (the A7 reasoning). The gate is therefore keyed on the login
  *surface*, not merely on the provider.
- **A configured `oidc:*` provider is never gated.** Those rows are the space's own directory and are
  precisely the identity source an accounts-off install authenticates against; gating them would remove
  the alternative at the moment it removes the default. `is_external_provider` reuses
  `slug_from_provider_key`, so the namespace has one parser.
Reads fail **OPEN** (a broken capability lookup must never lock people out), which is deliberately the
opposite of the access rules — do not "fix" one to match the other. Gated on the member surface only:
phone sign-in (checked on start **and** confirm, so a code issued before the switch cannot still mint a
session), the built-in Google/Apple providers, and self sign-up. `/api/v1/config` emits
`member_accounts` **only when off**, preserving the byte-for-byte payload; that key is discovery, and
`SocialLoginView` enforces member-only provider methods. `social_auth` advertises member
methods; staff/platform use their independent password doors and cannot obtain those provider sessions.
- **`makerspaces/walk_in_services.py` is the substitute, and is gated by NO module.** `membership`
  requires `accounts`, so gating walk-ins by either would remove the substitute and the thing being
  substituted together. It creates a real `User` with an **unusable password** — naming a person, not
  provisioning a login — so every downstream PROTECT FK keeps working. Two rules: a typed number goes
  to free-text `User.phone` and **never `phone_e164`** (a login identity under a partial unique
  constraint, and a counter-typed number proves nothing), and a **known email is refused, never bound**
  — attaching an existing account to a roster is a `MANAGE_MAKERSPACE` decision, and binding would
  silently reactivate a deliberately revoked membership through the one form meant for strangers. The
  endpoint is gated on `ISSUE_DIRECT_LOAN`, because naming the stranger at the counter is the same
  front-desk act as handing them a tool.
- **The unusable password is NOT the boundary — `User.is_walk_in` is** (`accounts/0014`).
  `set_password` replaces an unusable password perfectly happily, so `ForgotPasswordView` finding the
  record by the email staff typed at the counter, and `ResetPasswordConfirmView` setting a password on
  it, is a complete path from person record to real login — past disabled self-registration, into a
  membership somebody else created. The flag is checked on **both** paths (request *and* confirm, so a
  link minted before the record was marked still fails), and both keep their generic response, because
  refusing visibly would disclose which addresses belong to walk-ins. Generalise it: an unusable
  password is a statement about the present, and every path that can *set* a password must know the
  record is not supposed to have one. **That means EVERY path**: `admin_api.services_user_access.
  reset_user_password` hands back a usable temporary password and is refused for a walk-in in the
  **shared service**, because the REST endpoint and the Django admin action both call it and a check
  in one leaves the other open. Migration `accounts/0015` backfills the marker from the **union** of
  the append-only `member.walk_in_created` audit trail and usernames beginning `walkin_`, and revokes
  any password/refresh token already acquired through the hole for both sets. The second signal is
  load-bearing: audit rows are makerspace-scoped and die with a tenant purge, while the username lives
  on the global `User` row and survives untouched. `walk_in_services._available_username()` assigns
  every walk-in the `walkin_<name>_<random>` namespace; self-registration uses `member_<uuid>`, so the
  two cannot collide. A marker that leaves the credential working changes nothing for exactly the
  accounts it exists for. Enforcement lives at credential *creation*, never at login: after these
  guards no application path can give a walk-in a password, so a login check would guard an
  impossible state while blocking a superadmin who deliberately set one in `/control/`. **The
  backfill must also clear what a working session was used to LINK** — `SocialIdentity` (whose
  login path returns on an existing identity match *before* the auto-link guard), `phone_e164` +
  `phone_verified_at` (a login identity resolved by number, which never reads the marker) and
  `DeviceGrant` (its own rotating refresh family, so blacklisting today's tokens is not enough).
  Revoking the password alone leaves three doors open. **And `_explicit_link` refuses a walk-in
  outright** — the migration cannot reach a live *access* token for ~15 minutes, and that window is
  long enough to link a fresh provider and undo the revocation. The guard sits inside
  `_explicit_link` (after its `select_for_update`), because that function is where every explicit
  link in the system is created.
- **AN ACCEPTED RISK IS A CLAIM ABOUT THE CODE AND MUST BE VERIFIED LIKE ONE.** A6 was accepted on
  the assertion that no durable signal identified a walk-in after tenant purge, even though the
  function generating exactly that global-row signal had already been read in the same session.
  Writing the dismissal into a report did not settle it; the next review correctly re-raised it.
- **Phone linking is guarded too** — `services_phone.confirm_link` writes a verified `phone_e164`,
  and a verified number IS a login identity resolved by number. The check sits inside its
  `transaction.atomic()` on a `select_for_update` re-read (the caller's `user` came off a JWT and
  may be stale) and uses the file's **deferred-raise** pattern, because raising inside the block
  rolls back the `failed_attempts` increment and silently disables the attempt cap. `start_link` is
  refused as well: it writes a challenge row and spends real SMS credit.
- **A guard that runs after a challenge or token has been consumed is itself a state-changing path
  and must emit an audit entry.** Phone `_confirm` persists `consumed_at` before the walk-in refusal,
  so that branch records `member.phone_link_refused_walk_in`; returning an error does not make the
  already-committed consumption read-only.
- **THE COMPLETE LIST of guarded credential-writers for a walk-in** — forgot-password,
  reset-password confirm, change-password, member sign-up, `admin_api` staff reset, social auto-link,
  social explicit link, phone `start_link` + `confirm_link`, plus username-collision assertions in
  `seed_demo` / `setup_instance`. The CLI checks protect data integrity rather than access control —
  shell access already overrides the application. **Adding any new way to set or verify a credential
  means adding it here.**
- **Audited and deliberately NOT guarded: phone unlink only.** `views_phone.py` only clears a login
  identity. A guard on that revocation path would make a walk-in's phone identity impossible to
  remove, which is the opposite of the marker's purpose. Change-password now refuses explicitly even
  though `check_password` already failed against an unusable password; member sign-up now returns
  silently before stamping `email_verified_at` on a reused walk-in row, preserving the endpoint's
  account-enumeration-safe response; and the two CLI commands now assert against collisions. The
  social new-user branch creates a fresh account and therefore has no existing walk-in target.
- **The meta-rule, learned across FIVE review rounds on this one seam:** when a marker means "this
  record must never hold a credential", **enumerate every writer of a credential once, as a list,
  and guard them together** — never close paths one at a time as a reviewer points at them. Each of
  the seven above was found in a separate round, all the same mistake. Note that this rule was
  already written here after round 5 and the *next* commit still guarded a single path: writing the
  lesson down did not apply it, so the list above exists instead of the advice alone.
- **A walk-in may carry neither an email nor a phone, and downstream models often require both.**
  `EventRegistration` has two non-blank contact columns, so the members this seam made registrable
  were exactly the ones that could not be registered. Each such surface needs a **caller-supplied
  fallback** (`member.email or email`, `member.phone or phone` — account first, so the fallback can
  never redirect a real member's mail) **and the matching console field**: a fallback the staffer
  cannot type is the same as no fallback. **A conditional console field must key off
  `StructuredApiError.body`, never `.message`** — the message is built from `Object.values(body)`
  alone, so a DRF field error arrives as the bare `"This field cannot be blank."` with the field
  name stripped. Matching the message for `/phone/i` looked right and never once fired, so the
  prompt it gates had been dead since the day it shipped.
- **OIDC has a browser flow** (`accounts/views_oidc_browser.py`): `social/oidc/<slug>/authorize` starts
  an attempt (discovery, `state`, `nonce`, PKCE `S256`) and `social/oidc/callback` exchanges the code;
  the sign-in page renders every enabled `oidc:*` provider. The ID-token endpoint
  `social/oidc/<slug>` remains for native clients. Accounts-off still hides only the built-in consumer
  providers, never a configured OIDC provider.

**Login methods are four independent platform switches (module program phase 10).**
`accounts.PlatformLoginMethods` (`pk=1`, superadmin-only) governs member password / social / phone /
self-registration; staff/platform password doors are independent (V12). Platform-scoped and never a tenant feature, for the reason that keeps social sign-in
off the capability registry: each resolves before a makerspace is selected. All four default **on** and
are additive `AND`s in front of the readiness each method already had, so switching one on can never
make an unconfigured method work. `load()` deliberately does **not** `get_or_create` — this is read on
every unauthenticated login attempt, and a read path that writes is a write per login attempt.
- **The `social` master covers built-ins AND OIDC**. The built-ins additionally require
  `google_enabled`, `apple_enabled` or `github_enabled` AND configured keys; OIDC retains each
  row's `is_enabled`. New provider flags default on so existing deployments are unchanged.
- **MFA and built-in provider choices belong to installation**. `/control/` displays all four
  read-only, with `manage.py set_login_methods` as the recovery/change path. The guided installer
  asks platform MFA before areas, defaults providers to Google on Enter, and transports explicit
  `none` unchanged. With MFA off, it skips the staff-MFA prompt and writes no such feature.
  Provider keys are collected later in the console, never by the installer.
- **`login_methods_validation.validate_login_methods(proposed)` checks the complete state**,
  including credential readiness, all simultaneous provider removals and enabled OIDC providers.
  The admin form, operator command and setup service share it. Social-only users must retain
  a usable enabled credential. Staff/platform are password-only, regardless of the member password
  switch; social identities never count as their alternative credentials. Reads fail open with
  last-known-good switch values; writes fail closed when validation cannot prove member survival.
- **Setup applies `SETUP_MFA_ENABLED` and `SETUP_SOCIAL_PROVIDERS` only on first row creation**,
  independently of whether the makerspace already exists. Reruns preserve later operator choices.
  `set_login_methods --mfa on|off --providers google,apple,github` (empty/`none` = none)
  saves the singleton and its audit event in one transaction. Both setup env names are one-shot
  excluded backup settings, registered in the backend env surface because setup reads them.

`PlatformLoginMethods.mfa_enabled` (default on) is the authenticator master switch and overrides
staff-MFA-required spaces while off, without clearing credentials. Shared policy governs JWTs and
Django control sessions: `bypass` proof is refused after re-enabling; `verified` proof records local
TOTP/recovery verification, `provider` proof skips local TOTP by owner decision for Google, Apple
and configured OIDC, and `none` records an ordinary password session without a factor requirement.
Refresh rotation preserves proof rather than upgrading bypass to verified; credential-version
changes still revoke verified/provider tokens and control sessions. Enrollment, verification and
recovery regeneration refuse while off; disable and password-only invitation acceptance remain available.

**GitHub sign-in delivers member sessions only.** Its browser OAuth flow reuses the
single-use attempt ledger, binds state to origin and a browser-held nonce, uses PKCE
S256, and requires a primary verified email. The platform client secret is encrypted
and write-only; provider access tokens never persist or enter audit metadata. Google,
Apple, GitHub and OIDC all authenticate member accounts only. Provider removal/unlink
checks protect member credentials; none can replace a staff/platform password.
Both settings surfaces refuse clearing a GitHub credential when it would strand a GitHub-only member. Provider-issued GitHub sessions
use the same version-bound MFA provider proof as other social sign-ins.

**Maker profiles hang off `MakerspaceMembership`, and are deliberately NOT PII-encrypted (phase 12).**
`User` is platform-global and scoped encryption is per-makerspace, which is why `accounts.User` is
outside the PII registry — so a profile attached to the user could be scoped to nothing. Per-membership
is also the truer model: what someone publishes to one space is not theirs to publish in another.
`ScopedPiiModelMixin` is omitted on purpose (`separability.E001` only fires for models that take it, and
its own hint names dropping the mixin as the right answer): every field is content the member wrote and
asked to have shown, so encrypting it buys nothing and drags in the envelope/dual-read machinery.
- **Visibility is opt-in and defaults off**, and no profile row is the same answer as an invisible one.
  Directory rows carry display name, headline and avatar and **nothing else** — everyone who did not opt
  in becomes part of `hidden_count`, so a space can show its size without naming anyone. One 404 covers
  "no such member", "not a member here" and "has not published".
- **`member` is a fifth public-image kind and needed all four registrations plus the collision check.**
  `build_object_key`, `lifecycle._collect_public_image_keys`, `recompute_storage._public_image_keys`,
  `module_purge_plans["membership"].public_image_keys` and `public_image_key_in_use` (new `profile_id` /
  `project_id` exclusions). All but the first fail **open**. Profiles are reached through
  `membership__makerspace`, since the row carries no makerspace column.
- **Profiles go with a `membership` purge; the membership itself still does not** (plan A7 unchanged).
- **Link URLs are restricted to http/https**, because they render as an `href` on a page other members
  read — a stored `javascript:` URL is stored XSS and escaping the text does nothing for an href.
  The separate public `links` field requires HTTPS without credentials. Every member-writable list
  is length-capped.
- **GitHub is never fetched on a read path.** `refresh_github_contributions` (command + Celery) does it;
  a failure keeps the last known count and still stamps `github_synced_at` so a throttled API backs off.
  Unset `GITHUB_API_TOKEN` = dormant, count stays `None`, section omitted. Changing the handle clears the
  cached count outright, or one account's total shows under another account's name. **The write-back
  is filtered on the handle that was FETCHED, not just the pk**: a member can change their handle
  while the HTTP call is in flight, and an unconditional `.update()` then lands the old account's
  total under the new name. A count under the wrong name is a false claim about a person, not stale
  data, so the raced write is dropped rather than applied.

**Staff event registration is the SAME service, with exactly one relaxation (phase 13).**
`services_registration.register(..., staff_registration=True)` relaxes only the `is_public` check —
that flag means "listed in the public catalogue", and a staffer at the door is not the public, so
without it a members-only event could not be registered for by anyone. Published, not-ended, capacity,
waitlisting, duplicates, the custom form, the write fence and the charge are all unchanged, because the
state machine has one home. The endpoint takes a `member_id` (an account ID): members-only events require a host membership;
account/invite audiences also admit an existing account without one. A person with no account is given a
walk-in record first, so there is one identity path instead of the events surface minting
half-identified attendees. `phone` is a **fallback used only when the account has none** (`member.phone
or phone`) — `EventRegistration.phone` is non-blank, so an account without a number was previously a
dead end; the public path passes none and is unchanged. The picker hangs off the EVENT
(`EventEligibleMemberListView`), inheriting `_manageable_event` rather than inventing a second answer to
"who may see this makerspace's members", and excludes the already-registered.

**A login-method switch is enforced on `/control/` too — but only while another way in exists.**
`password_enabled` lives in `LoginView` (the JWT API) *and* in `AdminSuperuserOnlyMiddleware`, which
refuses a POST to `admin:login` **before the form authenticates**, so no session is minted. Enforcing
only the API left a password door on the one surface that can turn the switch back on. Existing
sessions are deliberately not revoked: a login-method switch is a policy change, not a revocation.
- **The middleware check ALSO requires `settings.PLATFORM_ADMIN_SSO`, and that is load-bearing.**
  Social sign-in mints **JWTs for the React console and never a Django session**, so there is no
  password-free route into `/control/` today — enforcing unconditionally sealed the only page that
  can undo the switch, the moment the last admin session expired, with no application-level recovery.
  The flag is declared in settings (default False) rather than read with a `getattr` default so it is
  findable and an operator building such a route has somewhere to flip. **Do not "tighten" this back
  to unconditional without first shipping the alternative route** — the accepted consequence (a
  superadmin can still sign into `/control/` with a password) is written up as A5 in
  `docs/module-program-security-report.md`, and the enforcement path is already tested.
- **The rule this came from: a fix to an auth path needs its own "what is now unreachable?" check**,
  not just "is the hole closed?". The original fix was correct about the hole and created a permanent
  lockout that only the next review pass caught.

**Member profile writes are audited WITHOUT their content.** `member.profile_updated` /
`member.profile_image_updated` / `member.profile_image_cleared` record the fields touched, the
visibility transition and the project counts — never the bio, the education entries or the object
key. The audit log is append-only, so anything written there is permanently undeletable member PII,
and an object key logged there outlives the image and every row that could name it.

**Public handles are separate publication consent (2026-10-17).** One `PublicHandle` per account
selects one membership profile. Normalize lowercase; use 3–30 ASCII letters/digits/dots/underscores/
hyphens, beginning and ending alphanumeric. Reserved top-level segments include `now`; keep
`public_profile_reserved` and crawler exclusions aligned with the route inventory. Namespace writes
lock the account and names; DB constraints enforce case-insensitive uniqueness and grammar.

- Rename/repoint only after 30 days. Retired names remain reserved for 30 days; release also prevents
  another claim during that window and clears publication consent. A retired URL redirects only to
  a currently eligible public claim; otherwise every public surface gives the same 404.
- `is_visible` is the member-directory opt-in. `public_visible` plus `public_consented_at` is the
  independent public opt-in; false→true requires fresh `publication_consent=true`. Public visibility,
  graph, events, speaking, projects, machine activity, bookings and loans all default off. Existing
  directory consent grants none of them. Account/membership standing, Membership module, tenant
  servability and both request Host and Origin/Referer constrain every public read and share card.
- Activity is counts-only, at most 120 inclusive days in the selected makerspace's timezone. The
  graph master, family consent and domain module must all pass before a source runs. Deduplicate
  each source's record/day milestones; loan/booking identities are model-qualified. Exclude a direct
  loan's backing request to avoid counting
  it twice. No titles, links, source IDs, remarks or exact timestamps enter graph responses.
- Event history has one row per event and badge priority **SPOKE > HOSTED > ATTENDED**. Hosting
  needs creator/organizer authority or a live edit/publish grant, not a speaker-only grant; remote
  hosting needs durable registration provenance through the selected space. Public speaking uses
  `speaker_history.contributions_for` plus public/published/past-session predicates. Attendance and
  hosting use `show_events`; speaking uses independent `show_speaking`. Current state is re-read.
- `GET /api/v1/public/profiles/<handle>/github` returns `{source:"github",days:[{date,count}]}`,
  separately from SpaceWorks families. Reads only cache after live public/graph consent checks.
  The existing daily GitHub task refreshes with `GITHUB_API_TOKEN`; no token, cache miss/expiry or
  failure yields empty days. Keys include handle/profile timestamps, username and generation so
  raced workers cannot republish an old calendar. TTL 25 h, refresh due 23 h, failure backoff 1 h.
  The older scalar contribution total retains its separate last-known-value behaviour.
- `/<handle>` is the last named React route before `*` in both route tables. `/share/profiles/<handle>/`
  serves live-gated OG/Twitter cards and public sitemap entries use the same predicate. Bundled nginx
  and Caddy rewrite recognized crawlers on grammar-matching, nonreserved single segments to that share
  route; ordinary navigation goes to the SPA. No crawler exception may bypass consent/tenant gates.
  The main public read optionally authenticates JWTs and returns `viewer_is_owner` from the live
  account/handle owner match (false for anonymous/other viewers), with no-store. Member profile
  reads/writes expose `verified` from this selected membership's `verified_at`, never another space's
  proof. Mutations still resolve the authenticated membership. Portable import resets public/family consent.

**Notification channels are modules, one key each (phase 20).** `email`, `telegram`, `slack`,
`mattermost` and `discord` each own a module key, so a space living in Discord ships no Slack
surface. Each is an additive **AND** in front of the credential check that already existed:
enabling a key cannot make an unconfigured channel send, and disabling it stops delivery while the
**stored webhook survives**, so re-enabling needs no re-entry.
- **`dispatch_channels.channel_module_blocks` is checked in TWO places**, mirroring the email gate:
  `dispatch_channel` (new alerts) and `_deliver_notification` (a PENDING row can sit in Celery
  across an uninstall, and a retry re-enters there). A blocked message becomes a terminal
  `NotificationDeliveryStatus.SKIPPED` — recorded, not dropped — and `notify._run_guarded` counts
  SKIPPED as **neither** delivered nor failed, because `bool(delivered_counts)` must not read a
  suppressed channel as a reminder that went out. It fails **open** on a lookup error: a broken
  capability check must not silently mute a space's alerts.
- **`makerspaces/0056` backfills `slack`+`mattermost` UNCONDITIONALLY onto existing rows** — the
  `0050` email precedent. Both were previously governed by webhook presence alone, so the opt-in
  default would have muted every upgrading space silently. Unconditional (not "only spaces that
  already hold a webhook") because granting the key restores the old rule *including* for a space
  that configures Slack for the first time next month. `discord` is **not** backfilled: it is new,
  so opt-in is correct for it.
- **The notification matrix OMITS a channel whose module is uninstalled** rather than rendering it
  disabled (`views_notification_rules._response_data` filters both `channels` and `preferences`).
  A tickable column would accept the tick, store the preference, and then SKIP every send — the
  same reasoning as pruning a tombstoned sidebar entry instead of permission-hiding it. **The write
  paths agree** (2026-10-09): the matrix PATCH refuses to switch such a channel ON (400; OFF stays
  allowed), and a `ReportSchedule` refuses a destination on an uninstalled channel and a report
  whose source module is off — the same 400s the destination API and the manual export give.
- **Discord is not Slack-shaped.** `webhooks.py` maps channel → body key because Discord names the
  field `content` and ignores `text` (400, nothing delivered), and trims to its hard 2000-character
  limit, which rejects rather than clips. `native_push` has **no** module key — it is governed by
  the standalone `mobile.push` feature.
- **Chat credentials are per-makerspace by nature, identity credentials are platform-wide.** The
  tenant owns the destination channel and pays for it; identity resolves before a tenant exists.
  Do not re-propose per-makerspace auth credentials — that was considered and cancelled.

**Notifications v2 — recipients, rooms, templates, scoping (phase 21).** The Phase-1a personal
contract in `docs/notification-contract.md` complements the existing tenant matrix and room delivery.
Personal delivery uses explicit-recipient transactional envelopes,
proven integration-generation-bound endpoints, multi-select preferences and live source authority.
Never infer a personal destination from an email/name, route requester/campaign bodies to a room,
or treat the new personal preference as the existing tenant matrix. Authentication mailbox proofs
stay synchronous/redacted email; the five mandatory-mail module exemptions, separate
closed-with-issue opt-out exception and bounce/complaint suppression remain independent.

**Personal delivery (2026-10-17).** Domain transactions reserve explicit-recipient
`NotificationEnvelope` intents; outbox enqueue waits for commit and a sweeper recovers broker loss.
`NotificationSource` predicates reload ownership/resource state before delivery. Scoped bodies and
endpoints are encrypted; an envelope snapshots installation identity/generation, so reconnecting
cannot acquire an old private message. Acceptance is not delivery; retries/callbacks use bounded,
monotonic delivery states. `notification-contract.md` owns the HTTP/provider details and current
integration gaps; `notification-coverage.md` distinguishes converted producers from legacy paths.

**Machine-service owner self-notices (decisions 44/45, 2026-10-18).** `next`, `started`,
`completed` and `cancelled` go to the request OWNER only and are authorized by the owner's current
ownership + live standing + an immutable marker, never by the initiating staff/member/device
(documented exception in `notification-contract.md`). `started`/`completed`/`cancelled` mark the
request's own row (`*_notice_at`, queryset update, no `updated_at` bump) in the milestone
transaction; `next` never locks or writes another member's row — its once-only marker is the stable
envelope key `machines.service:<id>:next:requester:<owner>`, reserved under the scope lock by
`service_queue_notices.reevaluate_head`. The envelope insert is fail-closed; template rendering
happens at delivery with the default copy as fallback, so a bad tenant template can never roll back
a completion or cancellation. Never re-reserve a suppressed milestone; reads never emit.

- Space Manager identity owns `ChannelConfiguration`: enabled/room/personal switches, write-only
  encrypted credentials, quotas, provider and identity. Credential/provider/identity PATCH advances
  generation; unrelated switch changes must not resend those fields. Module removal also invalidates
  endpoints/generation. Personal choices are multi-select by category, constrained by the tenant
  matrix, modules, available channels, verified endpoints and live consent. Manager defaults prefer
  verified Telegram, otherwise email; other accounts default email/in-app. Email fallback needs both
  tenant and recipient permission and retains suppression/module rules. Security mail stays email-only.
- Telegram proves a private `/start`; Slack workspace OIDC, Mattermost configured-server OAuth and
  Discord identify OAuth prove provider identities. The authenticated challenge verify endpoint
  binds signed state to both the signed-in account and URL challenge before provider I/O, then
  locks/consumes once. The frontend returns with code and state, resolves the challenge through
  authenticated endpoints GET with `oauth_state`, then posts to that verify route; anonymous
  personal completion is gone. Member JWTs full-match exactly the six
  frozen personal route shapes, never a broad integrations prefix; channel settings/tests/installations
  retain staff authority. No typed destination ID establishes identity.
- WhatsApp is a personal channel (`twilio|meta`), without rooms, behind the independent
  default-off `whatsapp` module. Signed
  matching inbound codes prove consent; SMS login proof is unrelated. STOP revokes, authenticated
  inbound opens the 24 h service window; outside it an approved event/audience/locale template is
  required. Both providers use `notification_opt_in` (code variable) / `notification_test` (no
  variables), member/en. Both are registered/mounted and share `in_session_window` across provider,
  resolver and delivery; exactly 24 h and future timestamps refuse free text. The combined registry
  includes `whatsapp`, resolving the former missing-module readiness blocker. Existing operational
  T installations require explicit per-tenant conversion preserving enabled state and opt-outs;
  new installations and platform senders remain default off.
  Neither provider promises exactly-once upstream send.
- Provider settings are deployment-wide: `TELEGRAM_WEBHOOK_SECRET` is environment-backed.
  OAuth reads `NOTIFICATION_SLACK_REDIRECT_URI`, `NOTIFICATION_MATTERMOST_REDIRECT_URI` and
  `NOTIFICATION_DISCORD_REDIRECT_URI` from Django settings: HTTPS frontend notification-settings
  URL used exactly as registered, including any fixed query. Dynamic placeholders and appended
  challenge IDs are forbidden; signed state carries the challenge. Blank refuses.
  Mattermost private hosts default refused unless
  `NOTIFICATION_MATTERMOST_ALLOW_PRIVATE_HOSTS is True`; Meta defaults
  `WHATSAPP_META_GRAPH_VERSION` to `v25.0`. All five are environment-backed in `config/settings.py`
  and forwarded through deployment manifests; backup treats them as nonblocking value comparisons.
  Authorization and token exchange use identical redirects. Slack installation uses PKCE and its
  callback requires an authenticated matching actor; personal completion uses only challenge verify.
- Hardware, machine, watch, certification, membership, ledger, API-access, device and operations
  adapters reserve personal source-backed intents. Equipment rooms re-check their source/scope
  before delivery. Maintenance/procurement barrels delegate to machine adapters; member broadcasts
  reserve per-account intents inside the audited transaction. Stocktake/first-email-failure legacy
  inbox mirrors share source intent and UUID/get-or-create identity with personal delivery. Catalog
  strings include the landed membership/document/problem-report/API/report/failure/stocktake events.
- Legacy email recipients retain narrow compatibility. `bookings.owner_mailbox` preserves an
  unverified owner's same booking contact address for lifecycle/reminders, rechecking ownership,
  decrypted address equality, revision and all live delivery gates. Its reserved email leg prevents
  parallel envelope mail; skipped legs release recoverable delivery. Operational unverified staff
  email requires the `legacy_staff_email_allowed` source whitelist plus active tenant membership/RBAC
  and current recipient scope; never campaigns or requester/member audiences. Hardware's separate
  same-owner verified-contact mail remains; equipment policy/render hooks now participate in
  the shared resolver/mail transport. Source-specific module overrides map machines.service to
  machine_service, operations.stocktake to stocktake, inventory.watch to request_workflow and
  core inventory.threshold to no optional module.

The original v2 additions below remain additive and dormant until configured. Their default selection
fails **OPEN** to the action-based default — a broken selection, scope, module or template lookup must
never mute a makerspace. Deliberately the opposite of the *access* rules, which fail closed.
- **`integrations/recipients.py` — per-event recipient selection, where NO ROWS MEANS TODAY'S BEHAVIOUR,
  not "nobody"** (`DEFAULT_CHANNEL_STATE` has bookings email+telegram ON, so default-nobody would have
  silently stopped booking mail that flows in production). Rows become authoritative only once one exists
  for a (feature, event); deleting them all restores the action-based default. Only
  `events`/`bookings`/`maintenance`/`members` are selectable — **`hardware_requests` and `printing` keep
  `EmailNotificationMute` untouched**, being the alerts a space cannot afford to lose to a wrong backfill.
  Kinds: `role` (a real FK, so a rename keeps its rules and a delete removes them), `requester` (a **flag
  the caller reads**, never an address this layer emits), `members`, `user`. **A named `user` must hold a
  membership of that makerspace**, enforced at the picker AND re-checked at send time — bodies carry
  requester names, machine detail and booking info, so an arbitrary platform account is a hand-operated
  cross-tenant leak. A member's `receives_notifications` opt-out **always wins**, filtered in the query so
  no branch can forget it. The module gate lives inside `selection_rows`, not in front of the resolver, so
  stale rows for an uninstalled module fall back rather than mute. Native push is filtered by the same
  selection, which is why `dispatch_channel` stores the scope on the log — push resolves recipients at
  DELIVERY time and would otherwise match nothing.
- **Canonical native push belongs to an envelope delivery.** A `NotificationDelivery(native_push)`
  owns `MemberPushDelivery` children unique per `(envelope_delivery, push_device)`. The optional
  `inbox_row` link uses SET_NULL; inbox insertion never triggers a push, and inbox/module removal
  cannot erase delivery history. Member/requester accounts with a current proved source tie need
  no membership or inbox installation in recipient policy. Native selection and new device
  registration still require active local membership. Staff use separate fixed-tenant grants. Platform
  grants are forbidden. Disabling the inbox module is supported; tombstoning the entire notifications
  app removes its registered push adapter and is a different deployment operation.
  Delivery rechecks current source/revision, account kind/generation, tenant, recipient selection,
  module/matrix including `mobile.push`, intersected personal preferences, approved registration,
  grant and current device identity before provider I/O.
  Claims use atomic UUID lease tokens. Explicit transport rejections may retry within the parent's
  four attempts; unknown outcomes and expired leases are held without email fallback or blind resend.
  A proved completion from the original fenced worker may settle only its own held attempt;
  token rotation cannot invalidate a replacement destination. The five-minute sweep re-enters the
  envelope dispatcher and respects parent backoff/history. Account cleanup cancels outstanding
  children, clears leases and redacts original mappings before clearing envelope ownership metadata.
  Inbox-only purge retains push history.
  Migrations notifications `0008` expand, `0009` map every old push row to an inert historical
  parent while preserving exact original snapshots, and `0010` verify mappings then enforce
  parent/device uniqueness. Untouched pending rows are canceled, attempted pending/sending/expired
  work is held, and terminal history stays inert; conversion never sends. Sending activation and
  destructive retirement remain separate operator checkpoints after replay and reconciliation.
- **Native push payload v2** uses string data `v=2`, `event_id`, `makerspace_id`, `feature`, `event`,
  optional `inbox_row_id` and an allowlisted local `link`. Canonical event identity is
  `uuid5(NAMESPACE_URL, envelope.dedup_key)`. Content is rendered for the personal recipient,
  never copied from a room body. Titles name the makerspace; APNs uses its thread ID. Local links
  must pass both the inbox sanitizer and native link contract. Retained legacy staff matrix legs
  keep their existing stable event/log identifiers and are deliberately pre-skipped in matching
  envelopes. Apps deduplicate and refetch source APIs on tap/foreground. Unsupported links fall
  back to inbox when available, otherwise the selected makerspace home.
- **`NotificationDestination` — one row per room, and `[None]` means the legacy column.**
  `destinations.resolve_destinations` returns rows **or the single sentinel `None`**, which every sender
  already handles. No rows for a channel ⇒ `[None]` ⇒ byte-for-byte the old behaviour, which is what makes
  migration `0021` (one space-wide destination per configured webhook **and per Telegram chat id**) safe;
  the `Makerspace.*_webhook_url` columns stay readable for a release. The query is deliberately **not**
  filtered on `is_active` — that would make a deactivated sole room read as "no rooms" and fall back to the
  credential underneath. **No scope links ⇒ space-wide**, the OPPOSITE default to membership machine-type scope (an
  unscoped *role* must reach nothing; an unscoped *room* is not a permission); an alert naming no subject
  reaches no *scoped* room. Credentials are typed per channel with a check constraint, never one overloaded
  column. One log row per destination (D13), quota charged per room, and `destination_label` is snapshotted
  so a queued row whose room was deleted goes terminal instead of falling through to the space-wide webhook.
- **Telegram has one sender identity across a tenant's rooms.** Destinations carry no bot token.
  `telegram.resolve_bot_token` selects the contract `ChannelConfiguration` token first, then the
  makerspace/deployment fallback. Personal delivery requires the explicit contract token and current
  integration generation. No accept/reject callback or keyboard is permitted. Secret-authenticated
  private `/start` proofs are the sole accepted inbound action; see the Telegram rule below.
  `notification_enums.MAX_MESSAGE_LENGTH` owns room limits (Telegram 4096, Slack 40000,
  Mattermost 16383, Discord 2000); oversized room text is trimmed before transport.
- **Templates extend `email_templates_registry`, never a second engine.** Four FabLab streams
  (`events`/`bookings`/`maintenance`/**`membership`**) × both audiences × 20 events = 40 entries with
  declared `fields`, `sample_context` and defaults reproducing what each adapter sent inline. The `members`
  feature maps to the **`membership`** stream — the one pair where feature key and stream name differ,
  because existing `EmailLog` rows carry `membership`. `ChatTemplate` is **one body per (makerspace,
  feature, event) shared by all four chat channels** (per-channel bodies quadruple the editing surface),
  falling back to `LifecyclePayload.text` when absent, inactive, unknown, empty or broken. **Chat is a
  STAFF surface, enforced in code**: `render_chat_text` raises on a requester audience and resolves only
  STAFF entries — a webhook is a room, so "your booking is confirmed" would expose that member's name to
  everyone with channel access. Retained legacy staff matrix push takes `payload.text`; canonical personal push
  takes the source-rendered recipient body independently of inbox creation.
- **Recipient object scoping composes as `object_scope AND (rule_scope OR all)` — narrowing only — for
  EVERY recipient kind (owner decision #75c, audit NM-71).** Rule links reuse the destination shape
  (`no links ⇒ everything`). For `kind=role` the floor is the role's machine reach
  (`machines/role_scope` via the batch `manage_scopes_for_memberships`, never a parallel resolver). People
  selected as `user` or `members` get `integrations/recipients_object_scope.person_object_filter`: a person
  receives an alert naming a machine or machine type only if they could see it in the console — role reach
  (EXEMPT or a linked type), a direct grant of the type's `managing_action`, or an operator row on that
  machine (for a type-only alert, on a machine of that type). A plain member therefore no longer receives a
  machine-scoped alert through a members-wide or named selection; that is the decision, not a regression.
  Alerts naming no machine/type (categories, events, payments) are unaffected. **Chat rooms** have no
  principal, so their object scope is their own destination links: a scoped room receives only subjects
  it names and nothing without a subject, and an unscoped room stays the space's general channel (D11).
  Personal owner deliveries (the requester/booker/registrant the alert is about) are the object's owner and
  are not filtered. A booking alert is ROOM-scoped (its scope is the room's machine type,
  `bookings/notifications.scope_for`), so for people the floor also admits whoever can see the room:
  `MANAGE_BOOKINGS` holders and live staff-grant holders on a room of that type. For booking alerts the
  `kind=role` rows follow that same people rule (#91); every other role keeps its machine-reach floor.
- **Staff API + console are mandatory, not optional** — `/control/` is not proxied on the public frontend
  port, so without `notification-recipient-rules` and `notification-destinations` a space manager could not
  configure any of this. Saves **replace** rather than merge (a merge makes unticking impossible), an
  unknown/foreign scope id is a **400, never a silent drop**, a room's channel cannot be changed after
  creation, and the credential is **write-only** (blank on update keeps the stored value).
  `admin_api/notification_scope.py` is the one scope writer shared by both surfaces. Email-template
  `STREAM_ACTIONS` gained the four streams (membership is `MANAGE_MAKERSPACE`-only: it carries applicant
  identity) plus a module gate.
- **G4/G5 fallout:** `integrations/health.py` gained a `chat_destinations` section reporting every room
  (configured / last delivery / last error, never the credential) plus the channels still on the legacy
  path. And `module_purge_plans` gained one plan per chat channel key: a destination holds an encrypted
  secret, so uninstall-then-purge of `discord` must destroy it. Delivery history survives (`SET_NULL` +
  label).

**Presence self check-in fails closed on geofence (2026-10-17).** `presence.geofence.require_inside`
requires an enabled, configured geofence and finite in-range browser coordinates; accuracy above
50 m refuses, and accuracy never widens the radius. Missing/denied location, an outside reading or
an unavailable geofence returns a typed refusal with staff guidance. **GPS remains spoofable**, a
convenience control rather than proof of identity. Authorized `MANAGE_MEMBERS` staff can check a
person in without location, including using a staffed kiosk principal; there is no client `staff`
bypass. Coordinates are validated and discarded, never stored in sessions, audits or notifications.

- **`presence` is an independent opt-in module.** `require_enabled` gates session, roster, privacy
  and TV APIs on module/runtime/servability. Uninstall retains rows; purge removes sessions,
  `PresencePreference` and `PresenceSettings`. Portable import drops all three, never reviving
  source attendance or display consent. `makerspaces/0096` installs it on every existing makerspace,
  including archived rows, preserving other module choices without duplicates; reverse is a no-op.
  New makerspaces still opt in through the module registry.
- **Identity is an account, with optional membership.** An existing membership must be active;
  an account-only guest cannot bypass a revoked membership. Staff use members or this space's
  walk-ins; account-only guests self check in through the geofence. `account` and legacy `member`
  reference the same user, enforced by a DB check. Presence-service defaults are 60/120/180/240
  minutes in both the service and bootstrap validator; configured presets win.
- **Statuses have provenance.** `working` requires an owned project here; private projects remain
  selectable without publishing their titles. Members may be `visiting`; account-only visitors and
  staff-recorded walk-ins are `guest`. Only the post-commit live event-ticket hook assigns
  `attending_event`: it reloads current published/running attendance and fresh server evidence,
  refuses historical/offline marks and binds once per registration. Hook failure cannot undo check-in.
- **Expiry and renewal are revision-bound.** Renew from now, retaining claim deadlines and the event
  end; an expired session can renew for ten minutes, otherwise start a new geofenced session. The
  minute sweeper in both schedulers closes at actual expiry and retries failed reminder creation.
  `presence.expiry` emits a personal renewal notice, default in-app/native push with no email fallback.
  Old revisions and notices older than ten minutes refuse delivery. No advance reminder is enabled.
  The notification feature enum still omits presence, so the shared category editor cannot offer it.
- **Names and opt-out are separate settings, both default on.** `show_names=false` anonymizes all
  rows and removes project/event titles. With names on and personal opt-out allowed, `hide_on_display`
  does the same for that person. With opt-out disabled, the name remains visible despite the flag.
  Labels are `A member`/`A guest`. Presence names do not depend on profile publication. Session
  responses expose display policy. Current-session returns top-level `personal_opt_out_allowed`
  and `names_displayed`, even without a session, respecting the person's hidden preference. Paginated
  staff rosters expose the tenant policy on empty/populated results; end responses retain policy too.
- **TV is an allow-list projection.** Anonymous `GET /api/v1/public/makerspaces/<slug>/presence/now/`
  and `/m/<slug>/now` expose display_name/status/since and optional public project/event titles,
  no IDs, contacts, coordinates or history. Servability/module/origin checks precede the shared
  30-second tenant/display-generation cache. Model saves invalidate by generation; bulk writes
  bypassing signals are bounded by TTL. Public responses prevent intermediary retention;
  authenticated previews bypass cache and return no-store. `PresencePrivacySettings` is mounted in
  the settings shell for Space Managers when the presence module is enabled.

**One colour vocabulary.** `frontend/src/index.css` holds the literal light and dark RGB triplets
from `docs/design-revamp/research/ui-brand-spec.md` section A. Keep `:root {` and `:root.dark {` literal:
the backend contrast guard parses those blocks. Tailwind maps each colour token one-to-one.
- `accent` is Maker Teal for staff actions, active navigation and focus. `brand` defaults to accent
  and is tenant-overridable on public/member surfaces only. Staff uses no brand utilities except
  the tenant-theme preview. `emphasis` is Workshop Orange, never tenant-overridable: an orange
  pill with its fixed `on-emphasis` label carries attention. **Orange standalone text is banned.**
- Fills pair with fixed per-mode `on-*` labels through rest, hover and active. Standalone text uses
  `ink`, `muted`, `accent-ink`, `brand-ink`, `success-ink`, `warn-ink`, `info-ink` or `danger`.
  **No translucent text**, including opacity applied to a text element. Opaque `*-soft` tokens
  replace semantic alpha tints; nested cards cannot accumulate translucent fills.
- Status pills always include a word. Light success/warn/info use their fills with `on-*` labels;
  dark uses their soft fills and matching inks. Accent uses soft/ink in both modes; danger uses
  panel/danger-line/danger. Issued and checked-out are accent. Limited stock is emphasis;
  unavailable is neutral. Neutral statistic panels have ink numbers; emphasis is an orange pill
  with its ink label. Colour assignment follows meaning or stable identity, never randomness.
- **Exactly two font families** (approved brand kit, 2026-10-15): Gilroy 400/500/600/700 for all
  text — headings, titles and display numbers at 600 (inline emphasis 700), body 400, labels and
  meta 500 — and Unbounded 500-600 for one accent phrase per layout. Outfit and the free Gilroy
  300/800 weights are retired. `font-synthesis: none` prevents fake weights. Stacks end in the
  generic sans-serif only.
  Native `code`, `kbd`, `samp`, `pre` use Gilroy with tabular/slashed-zero numerals, 0.02em tracking
  and 1em size; `pre` wraps. `.code-text` carries the same features for machine strings. Neither
  a monospace family nor `font-mono`/`font-code` utilities exist. The shared `.title-page`,
  `.title-panel`, `.title-section`, `.eyebrow` and `.col-header` classes own the spec type scale.
- **Buttons are a closed family:** `desk-button` (neutral outline), `-primary` (accent), `-brand`,
  `-emphasis`, `-success`, `-warn`, `-danger`, `-danger-outline` and `-ghost`. Each has a 44px target,
  10px radius, explicit rest/hover/active fills and `disabled:bg-surface text-muted border-line`.
  Controls use outline boundaries; cards use 16px radii and line borders; tags are fully round.
  Cards have no shadow; `shadow-overlay` is reserved for menus, popovers, drawers, modals and toasts.
  Hover changes colour over 120ms, with no translate/scale; reduced-motion preferences are honoured.
- **Tenant contract: degrade, never reject a well-formed colour.** Keep `brandColours.ts` and
  `makerspaces/theme_contrast.py` in lockstep. Labels try Deep Ink, Warm Cream, white, then black;
  black is permitted only as the tenant functional fallback. Emit exactly seven brand variables,
  including opaque brand-soft. Derive soft at at most 12% over panel, links toward the mode neutral,
  and hover/active away from the label. If a derived pair fails, soft falls back to panel, link ink
  to accent-ink, and interaction fills to the previous derivation. Only malformed colour values
  are rejected. The 4,096-colour backend sweep, frontend grid and frozen acceptance parity guard
  protect this contract. No tenant override changes staff, status, focus, neutrals or sidebar.

**Accessibility floor.** These rules protect every screen through the shared token system:
- The backend frontend-theme guard strips comments before parsing RGB blocks, checks every text ink
  at AA (4.5:1) on the universal neutral/soft grounds, every on-fill label at rest/hover/active,
  sidebar labels and selected states, focus at 3:1 and control outlines at 3:1. Source guards ban
  alpha text, semantic alpha fills, fill-as-text, obsolete fonts/colours and tenant classes in staff.
  Token provenance is checked against the authoritative spec. Browser axe remains the check for
  real composited/rendered pages; unit checks alone do not establish screen-level contrast.
- **`focus:outline-none` is banned.** Every control carries `focus-visible:outline-2
  focus-visible:outline-offset-2 focus-visible:outline-focus`; the dedicated focus token is opaque.
- A skip link needs `tabIndex={-1}` on a target that always renders, outside loading/module gates.
  Its target is the content region, so focus moves with scrolling. MemberArea currently has no
  skip link because its shell has no nav.
- Collapsed content is unmounted, never hidden-but-present, so invisible controls cannot receive
  focus. Counts use one text node (for example, `` `${n} items` ``) to preserve the accessible name.

**Console parity principle.** Every backend lifecycle capability reachable in the Django `/control/` admin
must have a React staff-console surface — a capability with no console surface is a latent dead/broken
feature for normal staff. New workflow actions ship their staff UI in the same batch.

**Who may submit a borrow request is DERIVED from the modules (owner decision #80, revising #75f).**
`apps/makerspaces/request_access.py` is the only answer, with three states and no stored switch
(`makerspaces/0105` dropped `anonymous_requests_enabled`): `member_accounts` on + `membership` on →
**members**; `member_accounts` on + `membership` off → **accounts** (any active signed-in account);
`member_accounts` off → **contact**. A space without member accounts has accounts for STAFF only, so EVERY
request there takes the contact path, signed in or not (owner decision #91: staff and organisation
sign-ins included; `request_access.uses_contact_path`). The one exception is a walk-in's claim session,
which is not an account but the staff-created person record itself, so it keeps acting as that person:
`contact_name`,
`contact_phone` and `contact_email` are all required, and the email must carry the one-time code mailed by
`POST public/<slug>/requests/email-code`. `hardware_requests/contact_verification.py` reuses the sign-up
OTP machinery (the `EmailVerificationChallenge` table, generator, HMAC digest, 10-minute expiry, 60-second
resend cooldown, 5-attempt cap, platform OTP quota and verification mail); a challenge is owned by the
space's inert `Makerspace.anonymous_requester` principal and its `email` column holds a per-makerspace
fingerprint, never the address. A wrong code burns an attempt in its own committed transaction and is
audited (`request.contact_code_failed`); sends are audited (`request.contact_code_sent`) and throttled per
IP and per address fingerprint. The request is recorded against the principal with
`requester_contact_verified=True` and a non-empty `anonymous_idempotency_key_fingerprint` marker (one per
consumed code), which every owner/contact-mail path already keys on. Phone and email exist only in the
scoped-PII encrypted contact snapshot and are staff-only; the typed name is the borrower's public name
(`inventory.public_stats_hardware.public_display_name` prefers `requester_name`). Bootstrap publishes
`request_access: "contact"` only for such spaces. The email-code route answers 404 where the space has
member accounts. Rows from the retired unverified opt-in keep `requester_contact_verified=False` and its
mail suppression. **Self-checkout follows the same rule (#91), behind its own switch (#95):** without member accounts,
and with `inventory.contact_self_checkout` on (default off; returns never need it), the evidence-URL,
checkout and return routes take the same name/phone/email + code identity (`self_checkout_contact.py`);
the evidence rules are unchanged. Uploads belong to the principal, so each returns a signed
`evidence_grant` bound to the borrower's address, which the handover must send back; a return must come
from the address the checkout used (`anonymous_payload_fingerprint` holds the per-makerspace email
fingerprint, which also scopes borrow limits to the person). The kit contents preview works on this path too
(#104, `kit_contact_preview.py`): it CHECKS the email code without spending it (a wrong guess still burns
an attempt and is audited), the checkout or return then spends it, and a return preview only finds a loan
checked out under the same confirmed email. `membership` requires `member_accounts` (#91): installing it pulls member accounts in, and
`makerspaces/0108` turned member accounts on, audited, for spaces that had membership without them.
Staff handout is unchanged.

**PRD §4.4's self-accept rule is DROPPED (owner decision #75e).** The PRD line "an admin cannot accept
their own personal request unless also superadmin" is not a requirement: `request_workflow.accept_request`
and `AcceptRequestView` deliberately carry no requester-versus-actor check, and none is to be added. A
reviewer may accept a request they submitted; the accept is still audited with the actor, so the
self-acceptance is visible after the fact. (Recorded 2026-10-22; audit row RO-100.)

**Authority is re-checked under row lock in the service, not only in the view.** A view authorizes with
plain reads and the service then mutates, so a revocation committed in between would otherwise still
land. `makerspaces/authority_lock.require_under_lock(actor, makerspace_id, predicate)` takes the tenant row
(`FOR NO KEY UPDATE`), then the actor's membership, roles and organization rows (the `role_authority`
order), confirms the actor is still live, and re-runs the view's own predicate on fresh reads; the object
being mutated is locked AFTER it, and any object-level predicate (machine reach, collect partition,
operator rows) is re-evaluated after that lock. The six races deferred in `a4fa9084` use it:
domain-verification (`domain_verification.verify_domain(actor=...)`, re-checked inside every status
write), machine-service collect (`service_workflow_collect`, via `service_request_partitions.may_collect`),
the asset/machine warranty PUT and warranty-document presign, finalize and delete (`warranty/services.py`).
A new write path that authorizes in the view must do the same.

**A core module must work with every optional module uninstalled.** Two halves. The *declared* half is
checked at import time: `module_registry._validate_registry` refuses a registry where an `is_core` module
names a non-core key in `requires_modules`. The *undeclared* half — core code reaching for a row an optional
module owns — has no sound static check in this codebase, because an app label is not the unit of module
ownership (`hardware_requests` owns core `request_workflow` **and** optional `guest_handover`; `admin_api`
owns core `staff_admin` and many optional surfaces), so no per-file rule can tell a legitimate
optional-module gate from a genuine violation. It is covered behaviourally instead, by
`tests/makerspaces/test_core_module_independence.py`: the core loan spine (catalogue → submit → staff queue
→ accept → public status) is driven over HTTP on a core-only makerspace and on `core + every optional
module except M`, for every optional `M`, with the **test identity built to match each configuration** —
with `membership` installed the spine legitimately needs an active member and an open presence session, and
a test that always used a plain account would be refused before reaching the code under test and would
prove nothing. This is the regression `9e496997` shipped: core `request_workflow` called
`require_active_member_presence` unconditionally and the default `recommended` profile ships no
`membership`, so a fresh self-host install 403'd every public borrow request. Do not weaken the claim in
that file's docstring; it says what it proves and what it does not.

**Telegram is outbound for decisions; private account-link proof is the only accepted inbound action.**
`LifecyclePayload` has no `telegram_reply_markup`; `telegram.send_message` has no `reply_markup`.
`TelegramWebhookView` verifies `X-Telegram-Bot-Api-Secret-Token` against the nonempty deployment
`TELEGRAM_WEBHOOK_SECRET`, acknowledges every `callback_query` and takes no workflow action.
A private, original, human `/start <opaque-code>` with matching positive `chat.id`/`from.id` may
consume a live account/tenant/generation-bound challenge through `notification_proofs`. Group,
forwarded, edited, expired and replayed proofs never establish a link. Browser-supplied chat IDs
are never proof. No message carries a keyboard. Keep the route to avoid retry loops on existing
`setWebhook` installs; register `allowed_updates` including `message` with the same webhook secret.
Rooms post as the contract bot token when configured, otherwise the existing tenant/platform fallback.
Rotation through channel PATCH advances generation: old endpoints and challenges cannot follow it.

**Accepting and rejecting a borrow request are one-at-a-time acts.** The `/control/` bulk `accept_selected`
and `reject_selected` actions were removed; `admin_request_review.RequestReviewAdminMixin` serves a
per-request review page instead, showing requester identity, contact-verification state and per-item
accepted quantities. Accepting reserves stock and rejecting closes a person's ask, and neither is a
judgement made about twenty rows from a checkbox column. The mutations still go through
`request_workflow`, so the state machine, audit entry and notification fan-out are unchanged — only the
entry point moved. The review URL must keep `admin_site.admin_view`, must load through
`self.get_queryset(request)` (the same admin scoping as the changelist), must re-check
`has_change_permission`, and must parse quantities as ints before calling the workflow.

**The shared account-less requester principal is not a person, and no per-PERSON aggregate may rank it.**
Every account-less request in a makerspace (a space without member accounts, #80, and the retired
opt-in's history) points at one `Makerspace.anonymous_requester`, so grouping by
`requester_id` folds every unrelated stranger into a single fictional human. `_repeat_offenders`,
`_top_borrowers`, `globally_ranked_borrowers` and `_restricted_requesters` exclude
`anonymous_requesters.anonymous_requester_ids(...)` **before** any limit or slice, so the principal cannot
displace a real borrower from the top N. The excluded damage and loss is not dropped: `accountability_data`
reports it as an additive `anonymous_accountability` total, because an accountability panel that silently
lost every account-less incident would be worse than one naming a fake person. Per-request rows keep
showing, but route their `requester_username` through `display.requester_label` so an overdue account-less
loan shows the contact the borrower gave rather than the principal's internal `member_<uuid>`. Restricting
the principal is refused at the write side by
`accounts.principal_guards.refuse_anonymous_requester_access_mutation` — the principal must never become a
usable or restrictable account — and the read-side exclusion is the backstop for rows predating that guard.
**Observability (forward plan phase 0, 2026-09-03).** Every request carries an `X-Request-ID`: honoured
from the caller only when it matches `^[A-Za-z0-9_.:-]{1,64}$`, minted otherwise, bound in a
`contextvars.ContextVar` by `config.request_id.RequestIdMiddleware` (third in `MIDDLEWARE`, after the
recovery gate pinned first and the calendar-feed log redactor second) and echoed on the response. Log
records carry it through `config.log_setup.RequestIdFilter`; Celery messages carry it in a
`spaceworks_request_id` header (`config/celery_signals.py`). **The id never enters audit `meta`** — the
row MAC covers `meta`, and correlation is done from the `audit_recorded` log line that `record()` emits
with the row's `event_uuid`. `GET /api/v1/metrics/` (Prometheus text) fails closed: 404 when
`METRICS_TOKEN` is unset, 401 on a wrong bearer, and it exposes counts and ids only, never tenant
content. It is outside `HMAC_PROTECTED_PATH_PREFIXES`, so it must NOT be added to the API-client scope
registry (an entry there would be stale). Any new `env(...)` read in `settings.py` must be listed in
`apps/backup/settings_policy.py::ENV_SURFACE`, or the env-surface drift guard fails.

**Search and live updates (forward plan phase 1, 2026-09-03).** `?q=` is one contract, implemented once in
`apps/inventory/search.py::apply_q`: a `websearch`-syntax full-text match on a trigger-maintained
`search_vector` column ORed with trigram similarity on the primary label, ordered by rank. The vectors on
`inventory.InventoryProduct`, `machines.Machine` and `events.Event` are **derived** columns: filled by a
Postgres trigger (never by `save()`), declared in all three registries (`data_export` classification +
`ALWAYS_OMITTED`, `tenant_migration.OMITTED_FIELD_RECONSTRUCTIONS` DERIVED) and rebuilt on the target
after a tenant move. **A trigger may only concatenate plain columns — scoped-PII fields are never
indexed**, which is why `HardwareRequest` has no vector and its queue keeps the blind-index search, and
why the member directory matches username/display name/headline/institution only. Live updates ride the
audit log: `audit.services.record` schedules `operations.live.publish_audit_event` on commit, and the
payload is `{kind, makerspace_id, target_type, target_id, actor_id, ts}` — never `meta`, never content.
`GET /api/v1/live/` subscribes a session to its own user channel plus every makerspace
`rbac.scope_by_makerspace` returns; it is served by the separate `live` compose service (thread workers,
no timeout, no `--max-requests`) behind an nginx `location /api/v1/live/` that sits above `/api/` with
buffering off; it answers 503 when the deployment has no Redis and browsers keep polling. Neither
`/api/v1/metrics/` nor `/api/v1/live/` belongs in the API-client scope registry.

**Browser and accessibility gates (forward plan phase 2, 2026-09-03).** The Hard Rules are pinned by
`frontend/e2e/` against a real stack (`./scripts/dev.sh e2e` locally before pushing): a request is accepted,
issued with a container code and a real presigned photo upload, and returned with container code, photo
and remark, and the API's 400s for a missing photo, box or remark are asserted directly. The public
catalogue spec asserts the seeded storage location, box label and box code never appear in the DOM. The
accessibility floor is enforced, not documented: `frontend/src/test/axe.ts` in panel tests (jsdom, no
colour contrast) and `e2e/a11y.spec.ts` in Chromium (WCAG 2.1 AA including contrast) — a violation is a
red build, and there is no allow-list. `text-ink/<alpha>` for body copy is therefore off-limits; use the
`muted` token, which is tuned to clear 4.5:1 on every surface it sits on.

**Signed webhooks (forward plan phase 3, 2026-09-03).** `webhook` is a notification channel, not a second
integration system: a `NotificationDestination` with `channel="webhook"` carries an encrypted endpoint URL
**and** an encrypted `signing_secret`, is routed by the same feature × channel matrix, and is written to the
same `NotificationDeliveryLog` with the same Celery retries. A destination without a signing secret is
*not-configured* (terminal FAILED), never sent unsigned. The body is `webhooks.webhook_event_body(log)` —
the notification's text, event, feature, ids and the matrix `payload` — i.e. exactly what a chat room
would receive; nothing from audit `meta` and no contact fields travel. The signature is
`t=<unix>,v1=<hex hmac-sha256(secret, "<t>." + body)>` over the exact bytes sent, mirroring the API-client
HMAC discipline. Endpoint URLs pass `webhook_validation.validate_webhook_url` (https, no private or
loopback ranges) at save time and are re-resolved and pinned at send time; a delivery error never stores
the URL. Both secrets are `ALWAYS_OMITTED` from export and DERIVED-omitted from tenant migration. The
superadmin "Re-queue failed deliveries" admin action is the dead-letter path and audits each row.

**Editions (forward plan phase 4, 2026-09-03).** `SPACEWORKS_EDITION` is a
**deployment**-level setting (`apps/makerspaces/editions.py`), never per makerspace, exactly like
`member_accounts` is read deployment-wide. An edition hides a fixed set of module keys:
`platform.available_modules()` (and therefore every bootstrap `modules` list and staff `enabled_modules`
payload) omits them, and the public loan/machine routes check `editions.public_surface_available(key)`
and answer 404 when hidden — **every** public route of a hidden module, not only its
catalogue: the public tool routes (`request_workflow`), public booking, machine-service
submit, every printer route including the token status lookup, and the per-member event
ICS feed all check it (2026-10-09; each had gated only on its module or feature, which an
edition deliberately leaves alone, so an events-only box still lent tools and took
bookings). Prefer `guards.require_module_for_servable`, which does the edition check and
the module check together. It does **not** change `core_module_keys()`, `module_enabled()` or any
`require_module` gate: staff endpoints, workflows, migrations, purge plans and backups behave identically in
every edition, so a hidden surface is recoverable and nothing that was recorded becomes unreachable to
staff. `Event.makerspace` remains the tenancy anchor in all editions.
The single-box shape and `spaceworks-allinone` image were removed on 2026-10-15;
`.spaceworks-layer=single` is refused by setup, update and the Compose wrapper with
[switch steps](update-recovery.md#moving-off-a-single-box-install).

**Member ID cards (forward plan phase 5, 2026-09-03).** `makerspaces.MemberCard` is `membership`-module
behaviour with no module key: its QR is a core `boxes.QrCode` with `target_type=member_card`, so
revocation, active-target uniqueness and the immutable `QrScanEvent` history are the ones every QR has.
**Identity never travels through the inventory scanner**: `qr_target_payload` and `QrResolveView` raise
404 for a member-card target; only `member_card_services.resolve` (action `scan_member_cards`) may resolve
one, it records a `member_lookup` scan even when refused, and it refuses uniformly (a foreign tenant's
card, a box QR and garbage all 404). **No inventory path may load a member-card QR at
all** (2026-10-09): `boxes.access.inventory_qr_codes()` excludes the target type and backs
`qr_for_action`/`locked_qr_for_action` (scan, print, revoke, rebind, stocktake scan) and the
self-checkout and direct-handout lookups, and `_checkout_target` has an explicit BOX branch.
Before that a card's `target_id` — a MemberCard pk — fell through to the box branch and
checked out whichever public box shared the number, and a `manage_qr` holder could revoke
or rebind a card without `manage_member_cards`. Authority is by action, never role name: `manage_member_cards`
implies `scan_member_cards`, is granted to the protected Space Manager default (migration 0069 backfills
existing rows); the fixed catalogue now owns the grants. `printed_name` is scoped source PII
(`encryption/registry.py`); `photo_object_key` is a PRIVATE object (`backup/object_ownership_registry.py`)
whose final key is never client-writable (staging presign → single promotion in
`member_card_storage.finalize_photo`) and whose bytes need recorded consent. **Revoke redacts
immediately** (photo bytes deleted, quota freed, name blanked); reissue rotates the QR and the old payload
resolves as `revoked` forever; reprint never rotates. No rendered PDF is written to storage. The
`membership` purge revokes the QRs and deletes the cards and photo bytes. **Revoking the MEMBERSHIP
revokes its card** (`member_card_services.revoke_for_membership`, reason `membership_revoked`, same
redaction), with no module gate and no card action — `revoke_membership` is core RBAC and the authority to
revoke the membership is the authority here; until 2026-10-09 a revoked member's card stayed a live
credential bearing their name and photo. The same revocation cancels every ACTIVE `MembershipTerm` and its
pending renewal charge (`membership_plan_services.cancel_terms_for_membership`), as it already cancelled
the dues charge. An invitation for someone who is already an active member is refused, as a referral was. **One LIVE
card per membership, not one card ever** (`makerspaces/0073`: `MemberCard.membership` became a
ForeignKey with the partial `uniq_live_member_card_per_membership`): a revoked card stays as the redacted
record behind its revoked QR and a fresh card (new number, new QR) can be issued — as a OneToOne the first
revocation stranded the member, since issue refused an existing row and reissue refused a revoked one. The
tenant-migration uniqueness policy moved from `field:membership` to that constraint name.

### Audit presentation and staff verification (phase 10)

- **One projector, fail closed.** Staff never see `AuditLog.meta` raw. `apps/audit/presentation.project` is
  the only path from a row to a reader, shared by `/admin/audit-logs`, the request timeline and the
  `audit-trail` CSV; it rebuilds only the catalogue's exact LEAF paths (scalars or flat scalar lists) and
  flags `meta_redacted` whenever anything was withheld. An action absent from the catalogue is labelled
  "Unrecognized audit action" with `{}`. Do not add a serializer or export helper that returns `row.meta`.
- **The catalogue is exact against the tree.** `presentation_guards.presentation_catalog_errors()` must be
  empty: every literal `audit.record` action has one entry; permitted paths are discovered literal leaves;
  `request_reference_paths` must be declared `HardwareRequest` REMAP references. A new emitter therefore
  fails the build until its metadata is reviewed — add the entry, never weaken the guard.
- **Dynamic emitters are denied, line-free.** Actions built at runtime (`a if x else b`, a parameter, an
  f-string) and literal actions whose `meta` is non-literal always project `{}`, even when another emitter
  writes the same string literally, because a row cannot say which site wrote it. The policy is held exact
  by `presentation_discovery` (exact constants, non-literal-meta actions, and reviewed namespace prefixes
  per wrapper FILE — never line numbers, which every unrelated edit would move).
- **Verification claims are orthogonal.** MAC (`mac_valid | unattested | invalid | unavailable`), batch
  membership, scope chain and external anchor are separate counts/statuses over SELECTED ROWS; they overlap
  and are never summed. "All entries fully verified" requires every dimension, including a configured
  anchor; anything weaker is "coverage is incomplete". A blank anchor backend is `not_configured`, not a
  failure.
- **Anchor failures are classified at the sink.** Sinks raise `AnchorTransportError` (timeout, 408/425/429,
  5xx, connection/S3 throttling), `AnchorConfigurationError` (settings, 401/403/other 4xx, credentials) or
  `AnchorInvalidEvidence` / `AnchorConflict` (malformed or disagreeing evidence, scope-head 404) — never a
  plain `AnchorError`. Only `AnchorTransportError` may produce the internal `anchor_transport` cause, and
  only that cause (or a database error) may append `RETRYING`. `AnchorReadBudgetExceeded` is deliberately
  not an `AnchorError`.
- **Runs are immutable and bounded.** `AuditVerificationRun` + append-only `AuditVerificationRunEvent`,
  guarded by ORM and Postgres triggers (state order `QUEUED -> RUNNING(n) -> {terminal | RETRYING(n) ->
  RUNNING(n+1)}`, at most 3 attempts). One active run per makerspace, fingerprint dedupe before snapshot,
  10,000 selected rows, 50,000 expanded leaves, 2,500 chain batches, 256 rotations and 2,760 counted sink
  reads per attempt — preflighted at admission and rechecked in the task. Runs are `OmittedModel`s (a target
  deployment must not inherit a source's verification), purged events-first, and only a superuser sees the
  closed `failure_code` and diagnostic coordinates.
- **Genesis membership is bounded too.** Staff verification uses the same 50,000-row cap for
  the activation manifest and its current membership set (manifest IDs plus every un-MAC'd row).
  Check manifest length before signature work; load at most cap + 1 current rows with a SQL limit.
  Exhaustion terminates `INCOMPLETE/verification_bounds_exceeded`, preserves calculated aggregates
  and never retries. MAC'd post-cutover rows are excluded from this membership load. Existing
  whole-log command callers retain their optional, unlimited path.
- **Anchor checks do not reload batch leaves.** Selected local membership is verified from one bulk
  leaf load. The scoped anchor phase verifies each fetched envelope's payload with the local stored
  signature/public key and compares its signed batch coordinates with local state, without rebuilding
  envelopes through per-batch leaf/key queries. Unselected batches receive chain/anchor checks without
  claiming local membership coverage for their rows.
- **Report reachability is per definition.** `allowed_formats`, `schedulable`, `previewable` and
  `deployment_aggregate` on `ReportDefinition` are enforced server-side (preview, export, schedule create/
  update, the runner's `_skip_reason`, every deployment-wide catalogue/analytics/export view). `audit-trail`
  is CSV-only, export-only, unschedulable, excluded from organization and deployment aggregation, and its
  builder refuses `makerspace_id=None`.

**Connected device monitoring (forward-plan phase 7d lane).** Both Celery beat and the beatless
scheduler register `apps.devices.tasks.scan_offline_devices_task` every minute and omit it when
`devices` is deployment-tombstoned. A beatless installation must invoke cron every minute to attain
that latency. The scan iterates canonically servable, module-enabled tenants, takes one
`fanout_tenant_write` boundary per tenant and uses Makerspace -> Device lock order. Offline/recovery
edges append `DeviceEvent` and `devices.*` audit rows with a null User actor, once per edge.
Never-seen active devices use their retained enrollment event as the activation time; pending and
revoked devices are excluded. Reactivation starts a fresh observation window. Bounded cleanup removes
only expired nonces and terminal expired enrollments; a one-second nonce grace protects the inclusive
integer-second signature window. No event or audit history is retention-pruned.

`devices` notification events `offline`/`recovered` are distinct from maintenance, selectable,
module-gated and default-off on every channel. Active `MANAGE_DEVICES` staff form the fallback;
explicit recipient rules retain existing opt-out, tenant and reach filters. Email and chat templates
use a staff-only `devices` stream and credential-free edge snapshots. Notifications run after commit
and cannot roll back a heartbeat or scan. `devices.offline_detected` counts as a failure in the existing
module-health report; recovery is activity only and singular `device.*` remains native mobile activity.

The identity-only Devices console requires `MANAGE_DEVICES` until 7b/7c adapter surfaces exist. Enrollment
bearers live only in local modal state: secret requests return void to TanStack mutations, and closing
the modal discards them. Shared query keys start with `["devices", makerspaceId]`; mutations invalidate
both list and detail. Machine/QR-only adapter controls must wait for scoped sibling APIs.

## Per-space security settings, platform locks and superadmin PII access

Owner decisions #110c/#110e and #111 Q9-Q13 (P1b, superadmin always on).

- **One registry.** `makerspaces/security_settings_registry.py` lists every per-space security setting
  (key, label, kind `bool|int|choice|list`, default, `stricter(a, b)`, storage `feature|policy`). Release 1
  registers only `security.staff_mfa_required` (storage `feature`: presence in `enabled_features`).
  Release 2 login-security adds its keys here with storage `policy` and creates the policy table; do not add a
  second registry or panel.
- **One writer.** `makerspaces/security_settings.py` (`set_setting`, `set_settings`, `lock`, `unlock`,
  `effective`) is the only path that changes a security key. It holds the makerspace row lock, checks
  authority, checks the lock floor and records `makerspace.security_setting_changed` (key, from, to,
  `via=space|platform`), `_locked` (key, floor, note) or `_unlocked` (key, floor), all makerspace-scoped so
  the space's audit readers see them. No email.
- **Authority (Q10/Q11).** Only the space's OWN Space Manager (a staff account of that tenant holding the
  Space Manager identity through its direct membership) or an active platform superadmin. Never delegable:
  no module manager, no organization grant, no resource grant. Precedence: platform lock > Space Manager >
  module manager. Every change needs recent re-authentication: the API uses `require_recent_reauth`,
  `/control/` its own step-up (`RecentReauthenticationAdminMixin`), and the host setup command
  (`apply_setup_areas`, a superadmin on the server shell) goes through the same service.
- **The lock is a floor (Q9).** `MakerspaceSecurityLock(makerspace, key, floor, note<=200, locked_by,
  locked_at)`, unique per (makerspace, key). The space may tighten but never go below the floor; a boolean
  lock means "forced on" (a false floor is refused) and locking raises a looser stored value to the floor,
  audited as a `via=platform` change. Only a superadmin unlocks; unlocking keeps the stored value. The
  space sees "Locked by platform: <note>".
- **The guard.** `makerspaces/security_lock_guard.py` is a `pre_save` receiver on `Makerspace` (registered
  in `makerspaces/apps.py`). A change to a security key that did not come from the service is NOT applied --
  the stored value is put back -- so the generic settings PATCH, the `/control/` capability matrix (which
  shows `security.*` read-only), module install/uninstall, space packs and setup can never change or loosen
  one. A service write below a lock's floor raises `SecuritySettingLocked` (`security_setting_locked`,
  a 400 on the API and a Django `ValidationError` elsewhere). A queryset `.update(enabled_features=...)`
  bypasses the receiver; a local AST test keeps that pattern out of `backend/apps`.
- **Readers are unchanged.** `accounts/mfa_policy.py` still reads `enabled_features__contains`; the lock
  works by keeping the stored value at or above the floor.
- **Superadmin PII view (#110e, Q12).** Everything is visible to the superadmin, but personal data is
  MASKED until they open a window. PII means the scoped-encryption registry's fields plus an account's
  email, phone and name. `PlatformPiiAccessGrant(id, actor, makerspace | subject, reason 10-300, opened_at,
  expires_at, closed_at, close_reason)` is a 30-minute window on one space, or on one person across every
  space they belong to (the `/control/` per-person reveal). Rows are append-only except the one-way close.
  Opening needs a reason and recent re-authentication (password; MFA is not demanded) and is audited as
  `platform.pii_access_opened`; closing and expiry as `platform.pii_access_closed` (`close_reason`
  `closed|expired`, `closed_at` = the real expiry time). Each row is makerspace-scoped; a per-person reveal
  writes one row in EVERY space the person belongs to. Expiry is closed lazily on the next read of that
  superadmin's windows or of the space's status (no Celery task yet). The space's Space Manager reads the
  open windows through `GET .../pii-access` and the audit log.
- **Masking is presentation only.** `accounts/pii_presentation.py` (`pii_visible`, `person_pii_visible`,
  `PiiMaskingSerializerMixin`, `require_pii_access`) and `accounts/admin_pii_masking.PiiMaskingAdminMixin`
  mask staff-console API responses, `/control/` list/change pages and PII exports (identity-bearing reports
  refuse with `pii_access_required`). NEVER mask at the decrypt seam
  (`encryption/mappers.ScopedPiiModelMixin`) or in a workflow: mail, receipts, notifications and every
  service read the real attributes. Non-superadmins are never masked; RBAC alone decides what they see.
  Platform accounts and platform mail (email logs with no makerspace, owner decision #114) are not
  tenant data and are not masked. A masked `/control/` change page leaves the PII
  fields out of the form, so saving it cannot overwrite them.
- **Portability.** Both models are `OmittedModel`s in `data_export/classification_security.py` and DROP in
  tenant dumps (`tenant_migration/catalog_security.py`); their user edges are excluded. The audit rows travel.

## Account deletion

Self-deletion, archive/restore, the 90-day purge and Apple revocation are member-only. Staff
lifecycle remains administrator-controlled; platform accounts use their separate recovery surface.

**Comeback restores identity only, inside the archive window.** Under the same User
row lock used by restore, Stage B commits `purge_started_at` before its first tenant
scrub. It cannot start before `now >= deletion_purge_after`. Restore refuses when
that fence is set, at the exact deadline, after global purge, or when deletion is no
longer requested. The fence survives tenant commits, gated tenants and object-storage
cleanup; extending the deadline cannot reopen an account whose scrub already started.
Every purge invocation locks User and skips an account restored since task discovery.

Password-reset **requests remain account-independent**: identical queue work for active,
archived and unknown addresses. Only the existing drain resolves identity; for an eligible
archived account it sends a single-use, 24-hour restore link instead of reset mail, with
five attempts and an identifier/credential fingerprint. Reset confirmation cannot redeem
a restore proof. Signup does not issue restore mail. Phone login start performs the same
one lookup and at most one send: an archived **phone-only** account gets a distinct
restore OTP, with the existing uniform 200, shared login/restore cooldown, attempt cap,
expiry and exact device-attestation binding. Restore OTPs never mint login sessions.

Accounts with neither email nor phone may use an already-linked provider. Recovery
intents are single-use, five-minute, nonce/state-bound, and browser-origin or exact
approved native-app-attestation bound. Apple, Google and OIDC require verified fresh
`auth_time` within five minutes; OIDC requests `prompt=login` and `max_age=0`, while Google
requests the authentication-time claim. An `iat` or silent provider response never
substitutes. This flow never creates or links an identity. Providers unable to prove
freshness have no second-factor fallback after Stage A deletes those factors. Deletion
preflight returns `restorable` and `restore_reason`, also shown before web confirmation;
unverified phones without email and disabled/unconfigured providers are not advertised
as usable recovery paths. Native-only configured Apple/Google identities can recover
with their approved app and audience.

Every confirmation rechecks the recovery-path exclusions against locked User: either
form of superadmin (including promotion after issuance), walk-ins, anonymous principals,
tenant-dump stubs and restricted accounts are refused. Identifier or linked-identity
changes invalidate the issuance fingerprint. Email/phone restore requires a new validated
password; social-only restore requires fresh provider authentication and keeps its password
unusable. Success clears deletion timestamps and pending, unrun tenant/object purge work,
sets `is_active=True`, and audits `account.restored`. Memberships, organization grants,
sessions, device grants and push destinations remain revoked; restore returns no session.
`account_restored_at` permanently refuses legacy browser JWTs without a revocable `sid`,
so reactivation cannot revive old access tokens. Recovery issuance and confirmation take
User before envelope locks, rechecking the proof/generation after locking, consistent
with Stage A and final purge. Invalid guesses resolve no User and commit their counters.

Stage A archives the member account immediately; Stage B removes mutable identity
copies after the retention window (90 days by default). The account deletion endpoint
is a member surface for browser and device sessions. Email enrollment confirmation
never proves deletion authority. Phone-only accounts use a separate `reauth` OTP
purpose with uniform start responses and committed failed-attempt accounting.

Deletion requires explicit `DELETE` confirmation and reauthentication within the existing
ten-minute window. The timestamp is compared again against the locked
`ReauthenticationSession` row inside the deletion transaction; proof consumption and
failed attempts commit independently before that transaction. A refusal rolls back all
domain mutations and records its audit outside the rollback.

Every blocker is global: pending charges/refunds, held deposits (count only effective
succeeded refunds with `amended_by IS NULL`), outstanding loans/requests, unresolved
problem reports, restricted access, uncollected service jobs, upcoming active bookings
and registrations, the last makerspace manager, any last organization governor, gated
tenants and either form of superadmin. Service-job ownership includes legacy rows with
`member IS NULL AND requester=user`. The leave-membership and existing
`assert_governor_remains` rules remain authoritative. Open membership applications are
cancelled through their applicant service, rather than becoming deletion blockers.

Tenant discovery covers every owned/copied subject-selector path, including account-only
participation and legacy service jobs. Locks follow source-gate shared locks, ascending
Makerspace rows, ascending Organization rows, then User. Recompute both tenant and
organization sets under the User lock and retry any growth, at most three attempts;
continued changes return `deletion_retry` without a partial deletion.
The account lock uses `no_key=True`, serializing obligation writers while allowing
unrelated foreign-key references. Browser and device refresh rotation lock the User
before token/family rows, so credential revocation cannot invert that lock order.
All session issuers take User before registration/credential rows too, including
password, first-device phone/social and MFA completion. Under that lock they recheck
active/deletion state and the authenticated password/restoration snapshot before
creating any grant, refresh family or browser session. Phone login discovers its
challenge without locking, then takes User before locking and revalidating that exact
challenge; failed attempts and consumption still commit before attestation/issuance.

Membership revocation reuses `_revoke_locked(self_leave=True)`. Organization self-departure
requires no governor authority, suspends only the subject's membership, preserves the
last governor and audits `organization.member_departed`. Stage A revokes device grants,
refresh families, browser sessions, outstanding/API tokens and reauthentication proofs;
revokes and audits EventStaffGrant and BookingSpaceStaffGrant rows, including accounts
whose only tenant participation is a resource grant (those tenants join discovery);
deactivates push destinations; deletes MFA secrets/recovery codes; sets an unusable
password and `is_active=False`; stamps `deletion_requested_at` and
`deletion_purge_after` using `ACCOUNT_DELETION_RETENTION_DAYS` (default 90); and audits
`account.deletion_requested`. Identity copies and immutable history remain at this stage.

Obligation writers lock the owner's User with `select_for_update(no_key=True)` after
their own tenant/domain locks and refuse a deletion-requested account: hardware request
submission, staff direct handout, self-checkout, booking/registration creation and
restoration, service submission/reprint, membership renewal/plan purchase and admission
approval/acceptance. A late return fee may arrive after deletion through its on-commit
hook; it still records the debt and audits `account.obligation_after_deletion`. Staff
refunds remain allowed because they return money.

Stage A records the current email in `User.deletion_email_ciphertext`, encrypted with the
platform secret key, so subsequent address edits cannot strand address-only EmailLog
copies. A random `deletion_username` coordinates tenant snapshots before the global
username changes. These snapshots are never portable and are cleared at final purge. Address-only
EmailLog ownership is resolved through decrypted model attributes, never SQL equality
against scoped ciphertext. Blockers carry the owning makerspace slug for web fix links.

**Stage B is resumable per tenant.** The daily `accounts.tasks.purge_deleted_accounts_task`
is registered in both beat and the beat-less scheduler (1440 minutes), and declared as a
tenant writer. `AccountPurgeProgress(user, makerspace, done_at)` tracks each tenant.
Each scrub uses its own transaction under the skip-and-count `boundary_tenant_write`
adapter. A gated tenant is retried later; completed tenants remain complete. Scoped PII
is always rewritten row by row through `save()`, including valid nonempty Booking
placeholders, cleared notes/custom answers, and unique EventRegistration email placeholders.
Machine-service ownership remains `member=user OR (member IS NULL AND requester=user)`;
staff authorship alone never erases somebody else's job. MemberCard stays exactly as
membership revocation already redacted it.

Mutable profile/project rows are deleted only after their public image keys, buckets and
sizes have been written to `AccountPurgeObject` in the same transaction. Object deletion
and its `deleted_at` stamp commit first. The ordinary `limits.free_storage` quota decrement
and `quota_released_at` stamp then commit together in a separate transaction. Missing
objects count as deleted. A storage failure or gate closure leaves durable pending work;
tenant progress cannot finish until every quota stamp exists. Purge never substitutes a
best-effort `release_public_image_on_commit` callback for this journal. Storage
reconciliation counts each journal's recorded size until `quota_released_at` is
stamped, even after byte deletion. It holds Makerspace through its snapshot and
total write, matching the scrub/quota-release lock order.

Only after all tenants finish and every AppleRevocation is terminal are global identity
fields cleared and `account_purged_at` set. The username becomes `deleted_<uuid hex>` and
the display name becomes `Deleted member`; social identities and Apple credentials,
email/phone/MFA challenges, password-reset envelopes, push devices and personal inbox
rows are removed. Hardware-request identity snapshots, booking contacts/notes/answers,
registration contacts/answers, owned service-job contacts, recipient/address-matched
EmailLog content, and MembershipRequest invite addresses/application answers are scrubbed.
EmailLog scrubbing also clears `provider_message_id`; bounce/complaint timestamps and
provider outcome fields remain. Member push deliveries are deleted through either the
user's inbox rows or push devices. Staff push attempts are deleted through their saved
recipient or the user's push devices, inside the delivery log's tenant boundary.
`DeviceActivityDay` rows are deleted through `grant.user` in the final global step,
including NULL-makerspace activity, only after every tenant has finished. A gated
tenant keeps its push history and defers all activity cleanup until a later sweep.
Repeated sweeps do not repeat quota release or final-purge auditing.

**Apple authorization is revoked, not merely unlinked.** Verified Apple claims retain
their `aud`; optional sign-in authorization codes are exchanged using that client ID,
the original web redirect URI, and an ES256 client-secret JWT. The exchanged id_token
must verify for that client and match the authenticated subject. Refresh credentials are
encrypted per `(social_identity, client_id)` and replaced with a new credential version on re-sign-in. Exchange failure
never prevents verified sign-in. Stage A creates revocation work in its own transaction;
each work row holds its own encrypted token copy and captured credential ID/version.
The worker revokes only that snapshot, including after account restore, and deletes the
current credential row only if its captured ID/version still matches. New sign-ins and
repeat departures cannot replace old pending work. Terminal work clears its token copy;
an on-commit task and the daily sweep retry with backoff. No stored credential, or failure
through day 80, audits `account.apple_revocation_unavailable` and marks the work terminal.
The confirmation UI always discloses manual removal in Apple Account settings.

Portable and deployment backups preserve deletion timestamps. Portable identity creation
keeps deletion-requested users inactive with their timestamps and anonymises purged users;
linking a deleted source to an existing target account is refused rather than changing
that target's unrelated platform identity. The fixed `global/users.csv` identity projection
does not grow: PORTABLE carries deletion fences in `global/user_lifecycle.json`, only for
deleted identities in the approved user closure. The migration envelope hashes this sidecar;
the importer validates its literal timestamp fields and merges them into identity resolution.
Subject exports keep the same fixed identity projection. Source cleanup journals and Apple credentials
never travel in tenant artifacts; target cleanup resumes from the imported timestamps.

**Retained and disclosed:** `AuditLog`; `Payment`/`Refund`/`ManualSettlement`;
`PaymentDocument.payer_label` (historical username — walk-in usernames embed a name);
`RequesterAccountability`/`ReturnEvent`; `EvidencePhoto` rows (bytes follow evidence
retention); `MachineUsageEntry` (including `member` linked to the anonymized User stub
and unchanged `started_at`), `EventAttendanceCertificate`, `EventFeedbackResponse`
(immutable triggers); staff-addressed notification emails mentioning the member (kept
until EmailLog's existing retention); `NotificationDeliveryLog` text (deleted by
`notifications/retention.py` on its existing windows); staff actor snapshots on other
people's memberships; anonymous `ConsumableCostRecord`, `InventoryStockSnapshot`,
`MachineStatusEvent`, `SmsSendLog` and `AttestationVerificationLog` rows. Backups age out
under their own retention. The operator-facing
[privacy note](privacy-account-deletion.md) discloses the same list.

## Handover roles and the retired Guest Admin

**Handover is a fixed built-in again** (`makerspaces/0092_fixed_roles_data`, after schema `0091`
and before constraint `0093`), combinable with Inventory, Machine,
Event and Booking Manager. Its grants are `view_inventory`, `assign_box`, `issue_request`,
`issue_direct_loan`, `return_request`, `upload_evidence` and `collect_service_request`. On its own
it cannot accept/reject requests, edit inventory or manage QR. Evidence, scans, remarks and audit
requirements are unchanged. `rbac.HANDOUT_ACTIONS`/`is_handout_only` decide narrow console presentation;
they do not cap a combined membership's authority.

Historically `0052`–`0054` and `accounts/0009`–`0010` retired Guest Admin and converted it to editable
handover roles. Fixed-role migration maps those rows to the canonical catalogue using the raw-grant
rules and E2 above. Guest Admin remains retired; it is not a new enum or a second handover role.
The `guest-admin/` **URL paths** in `hardware_requests/urls.py` remain the handover API surface
(module key `guest_handover`); changing them would break clients.

Print Manager remains retired (`makerspaces/0046` reassigned it to Machine Manager). Its string
survives only in `_MEMBERSHIP_ROLE_ACTIONS` as the frozen null-primary legacy fallback.

## Separability and tombstoning

**Separability: two registries, and the gap that fails OPEN (Phase 7, `apps/separability/`).**
An app can be **tombstoned** — surfaces gone, rows and migrations retained (`apps/printing`,
`apps/roadmap` are the precedent) — and that forces two registries with opposite lifetimes.
**Retention** (PII field mappings, purge plans, storage collectors, historical payment subjects) is
registered **even when tombstoned**: deregistering it makes retained rows unpurgeable and
unencryptable and strands private S3 objects nothing can name. **Runtime** (URLs, reports, admin,
frontend surfaces, origin-scope routes) registers only while the app is active.
- **A missing PII registration fails OPEN, which is why B3 is a system check and not an assertion.**
  `ScopedPiiModelMixin` asks the registry for a model's fields and reads an empty answer as "holds no
  PII"; every protection then no-ops in the safe-looking direction — `__getattribute__` returns the raw
  column, the `bulk_create` guard passes, the save boundary writes no envelope, the write fence is
  skipped — and the row lands in the clear with nothing raised. `separability.E001` now **refuses
  startup** (verified: deleting `bookings.Booking` from the map makes `manage.py check` a
  `SystemCheckError`), and `UnmappedPiiModel` is the runtime backstop for a `--skip-checks` process.
  The check is deliberately **not** gated on `PII_ENCRYPTION_ENABLED` — the deployment that has not
  enabled encryption yet is exactly the one that will, and the gap must be caught before the flip.
- **Registration happens in `AppConfig.ready()`, so it must be query-free and idempotent** — `ready()`
  also runs for `migrate`, `makemigrations`, tests, Celery workers and management commands.
- **`apps.separability` must stay LAST in `INSTALLED_APPS`.** Django imports every models module, then
  calls every `ready()` in list order; being last is what guarantees all registration precedes
  `finalize()`, which freezes the maps. Registering after the freeze raises rather than mutating a map
  some consumers already read.
- **Duplicate keys are fatal, never last-write-wins** — two apps claiming one purge node or PII model
  means one is silently unprotected, and the loser is invisible.
- **Consumers call accessors (`fields_for_label`, `all_fields`, `registered_labels`, `runtime_active`),
  never `from ... import BY_MODEL`/`ALL_FIELDS`** — a module-level import binds an import-time snapshot
  that stops being true once registration is per-app.
- **`runtime_active(app_label)` replaces `apps.is_installed()`** at the two call sites that had it
  (`member_activity_service`, `reports_health`): a tombstoned app is still installed — it must be, or
  its migrations unapply — so `is_installed()` answers "are the tables there?" when the caller means
  "are the surfaces live?". Unregistered defaults to **active**, so no app must opt in to keep working.

**Tombstoning an app: `TOMBSTONED_APPS` + `SEPARABLE_APPS` (Phase 8+, `separability/tombstones.py`).**
A tombstone is a **deployment** decision, never per-tenant — URL routing, admin registration and the
OpenAPI schema are process-global, so an app's surfaces are present for everyone or absent for everyone.
It composes with, and does not replace, the per-makerspace `enabled_modules` switch: a module is usable
only when the tenant enabled it **and** the deployment ships the app. The env var names **app labels,
not module keys** (one app can own several keys — `printing`/`machines`/`machine_service` are all
`apps.machines`), and it never touches data: rows, migrations, purge plans and PII mappings all stay.
- **The payment rail joined `SEPARABLE_APPS` (phase 16).** A makerspace that takes no money
  online ships **no Stripe surfaces at all**. The import counts are a red herring — 26 modules import `apps.payments`
  and every one keeps working, because a tombstone removes *surfaces*, never models: the rows stay
  readable, purgeable and nameable by the retention registry. Three things this needed beyond the
  standard pattern:
  - **The Stripe webhook is spliced out, not left answering.** An endpoint that still verified and
    settled a charge for an app whose reconciliation console is gone would move real money nobody
    can see. `config.urls.separable_paths` is the shape of `separable()` for inline single-view
    routes rather than an app urlconf.
  - **Some routes live in another app's urlconf.** `admin_api` owns the staff surface for payments
    so those cannot be removed by dropping an `include()` — `admin_api/urls.py` has its
    own in-place `_separable()` gate. The tombstone tests assert a **neighbouring** route in the
    same list still resolves, because splicing in place is exactly where an off-by-one removes too
    much.
  - **`_managed_item` had to become None-safe.** It called `_item(...)` and then subscripted the
    result; `_item` returns `None` for a tombstoned app, so the Stripe Connect entry would have
    turned a supported tombstone into a boot crash.
  The payment rail owns the `payments` module key; tombstoning it removes that key from the
  available-module list while the core payment ledger survives. `TOMBSTONE_PROFILE_APPS` in
  `tests/tombstone/conftest.py` stays in step with the registry. `tenant_migration` is separable
  because its whole superadmin surface is deployment-local.
- **Still NOT separable, with reasons:** `integrations` (platform mail carries password reset and
  email verification — removing it locks users out of their own accounts), `encryption` (the
  `ScopedPiiModelMixin` substrate six models depend on), `operations` (owns six module keys and the
  report registry that `machines`/`bookings`/`events` builders extend), `apiclients` (its HMAC
  middleware authenticates the whole public API surface), plus the core apps. `machines` is
  removable in principle and is the remaining piece for an inventory-only install; it has the widest
  surface area of any candidate and is deliberately left to its own phase.
- **`SEPARABLE_APPS` is declared, not derived.** Nothing in the module registry encodes "can this app's
  surfaces be removed without leaving the rest incoherent" — `is_core` comes closest and is a different
  question (`apps.makerspaces` owns only non-core modules yet is the tenant root; `apps.inventory` owns
  a core module *and* two optional ones). Anything in `TOMBSTONED_APPS` but absent from `SEPARABLE_APPS`
  **refuses startup** (`separability.E007`), which is what turns a typo, a dotted path or a core app
  from a silently inert setting into a boot failure. The set grows one app per B6 phase.
- **`module_enabled()` is the chokepoint**, ANDing `module_registry.module_available(key)` in, so a
  guard written later inherits the check without knowing it exists. `platform.available_modules()` is
  the read side — used by the bootstrap payload and both staff makerspace serializers, because the
  console turns those keys straight into tabs and a stale key renders a tab whose every request 404s.
  `/control/` and `module_install` keep reading the **raw** field: a superadmin must see what is stored.
- **Admin registration cannot ask the manifest.** `django.contrib.admin` sits above every `apps.*` entry
  in `INSTALLED_APPS`, so autodiscovery imports every `admin.py` *before* the owning app's `ready()` has
  registered anything. An `admin.py` must therefore call `app_is_tombstoned()` (settings) rather than
  `runtime_active()` (manifest); both derive from `tombstoned_app_labels()`, so they cannot disagree.
- **A sidebar entry must be omitted, not permission-hidden.** Unfold calls `str(link)` on every item to
  compute `active` **before** consulting the permission callback, so a `reverse_lazy` to a route the
  tombstoned app no longer registers raises `NoReverseMatch` and 500s the whole console.
  `_item(..., app_label=...)` returns `None` and `_prune_navigation` drops it (and any group left
  empty). `config/unfold.py` reads the env directly because settings *imports* it.
- **URL includes are spliced in place, never appended** (`config.urls.separable`): resolution is
  order-sensitive. `include()` is evaluated only when the app is active, because a genuinely gutted app
  has no urlconf to import.
- **The tombstone suite is a separate pytest run** (`tests/tombstone/`), because import-time surfaces
  cannot be re-derived in-process and the all-active suite asserts the opposite for the same objects:
  `TOMBSTONED_APPS=bookings,devices,events,maintenance,notifications,payments,presence,procurement,tenant_migration,warranty
  pytest tests/tombstone` — the conftest demands the **whole ten-app profile** (`devices` joined in
  phase 7a; `payments` is accepted for `payments_rail`) and names the exact
  string it wants, so a single app (this line said `procurement` alone until 2026-08-11) is a hard
  `UsageError`, not a partial run. A whole-tree run skips the directory; an
  explicit run without the profile is a hard `UsageError`, never a green no-op. `TOMBSTONE_PROFILE_APPS`
  in its conftest must stay in step with `SEPARABLE_APPS`.

**Device identity (forward plan phase 7a, `apps/devices/`, module `devices`).**
- **A device is NOT an actor.** `AuditLog.actor`, `EvidencePhoto.uploaded_by` and every scan actor stay
  `accounts.User` FKs. Device-originated audit rows carry `actor=None` plus typed metadata
  (`device_id`, `device_name`, `device_key_version`, `operation_id`, `outcome`, `enrollment_id`) and a
  matching append-only `DeviceEvent` (ORM guard + `devices_event_append_only` trigger honouring only the
  purge GUC). `DevicePrincipal` never reaches `accounts.rbac`.
- **One lock order, makerspace first.** Every device mutation runs `services_locks.lock_tenant()` inside
  its transaction — the tenant source gate (`assert_write_allowed`), `require_module_locked(..., "devices")`
  (the row lock uninstall/purge take) and a locked `is_servable` re-check, because `module_enabled` answers
  capability for archived tenants — then locks Device, then DeviceEnrollment.
- **Replay authority is a DB INSERT, after signature verification.** `DeviceRequestNonce` is unique on
  `(device, key_version, nonce_digest)`; an invalid signature, a closed gate or a module-off tenant claims
  nothing. `DEVICE_NONCE_TTL_SECONDS` must be >= 2 x `DEVICE_SIGNATURE_MAX_SKEW_SECONDS` (`devices.E003`).
  The signed target is the exact raw request target (`RAW_URI`/`REQUEST_URI`/ASGI `raw_path`); with none
  available authentication fails closed — never a normalized fallback.
- **The `/api/v1/device/` surface is covered exactly by `devices/route_registry.py`**, keyed by (qualified
  URL name, method) with a closed auth mode (`ENROLLMENT_TOKEN` | `DEVICE_SIGNATURE`); `devices.E001`
  refuses missing/stale/method-drifted entries or a view whose authenticators disagree with its mode, and
  `DeviceRoutePermission` default-denies. It is NOT the API-client HMAC registry and must never be merged
  into it. `source_gate_http_guards` admits the singleton `DeviceAuthentication` only while its
  `authenticate` assigns `request.selected_makerspace_id` before `_assert_source_gate(request)`.
- **No device authority travels or survives a restore.** Exports omit DeviceEnrollment/DeviceRequestNonce
  and the device key/fingerprint; imports reserve fresh UUIDs, reset Device to pending (keeping the
  monotonic `key_version`) and keep the five `DeviceEvent.*_snapshot` columns byte-for-byte as
  source-local history (`tenant_migration/references_devices.py` guards them out of every remap path).
  `backup.recovery.enter_quarantine()` resets every Device to pending, clears key material, bumps
  `key_version`, revokes open enrollments and deletes nonces, so a pre-backup signature fails even after
  acknowledgement. A remapped UUID audit reference is written to JSONB as a string
  (`semantic_remap._json_pk`).
- `MANAGE_DEVICES` is a Space Manager default (`makerspaces/0073` backfill) and is **never
  organization-grantable**; Inventory/Machine Managers do not get it.

**Printer commands and terminal reports (forward plan phase 7b).**

- A binding requires `devices`, `machines` and `machine_service`, an active printer Device and
  active Machine in the same tenant. Creation and approval require `MANAGE_DEVICES` and current
  machine-specific management scope. A snapshot never supplies authority.
- Commands pin the exact owning Device and key version. Random delivery tokens travel once and
  their digest stays private. Bounded lazy expiry/backoff never grants simultaneous leases. After
  acknowledgement, the signed owner can report through a long print without extending the delivery
  lease. Revocation/key rotation refuses prior authority. Disabling/deleting a binding cancels
  unprocessed commands and jobs.
- Terminal measurements require a stable operation UUID, immutable external job ID, actual minutes
  and explicit typed `MachineConsumable` quantities. Reserved pools use existing grams or quantity
  reconciliation inputs. Failure additionally requires a reason and percentage. Unknown fields,
  device-supplied money and ambiguous measurements are rejected before claim.
- Claim and application are separate transactions. Identical operation plus canonical payload returns
  the stored result; different payload/operation conflicts. Application calls only existing
  `service_workflow_actions.complete/fail`, with `actor=None` for automatic effects or the approving
  User for staff effects. Workflow failure rolls back consumption, charge and transition, retains
  the claim and records review in a fresh transaction. Review never auto-retries.
- Automatic application defaults false. The existing payment service reads current authoritative
  pricing; the adapter accepts no pricing input. Failure retains the workflow's no-charge behavior.
  Telemetry updates advisory job fields and last-seen only. Authoritative maintenance/reserved/offline
  and running states take precedence; public machine output stays unchanged.
- Free-text failure notes use scoped PII encryption and a database write fence. Services take the
  source gate, then PII fence, then tenant/device/command/job/request/machine locks. Database guards
  freeze claimed identities, measurements and consumptions while permitting adapter FK `SET_NULL`,
  authorized purge and PII ciphertext maintenance. Application verifies the plaintext report hash.
- Exports classify all four models and creator/processor User edges, omit lease digests and preserve
  typed history. Portable import and raw dumps disable bindings, cancel commands, clear leases,
  preserve applied/cancelled history and turn unprocessed jobs into review. Imported work stays inert
  after re-enrollment. Device purge deletes printer rows first; adapter purge nulls live links and
  retains device history.

## Machine scoping — `MANAGE_MACHINES` is per person by type, and fails CLOSED

- **Tier 1 is per-person, type-only scope.** `machines/role_scope.py` resolves
  `MembershipMachineTypeScope(membership, machine_type)`. A Machine Manager reaches machines whose
  types are linked to that membership, including machines added to those types later. **No links means
  no machines.** `RoleMachineTypeScope` and `RoleMachineScope` are gone; there is no membership-to-machine
  scope table. Space Manager remains exempt, including future types; null `assigned_role` keeps the
  frozen legacy exemption. Foreign-tenant roles or links never confer reach.
  - **Data migration `makerspaces/0092_fixed_roles_data` never widens machine reach.** It copies old
    role TYPE links per person. Old MACHINE links are dropped, never expanded to their types, and
    listed in preview/audit as `machine_scope.dropped_machine_ids`. A nonempty machine-only old scope also drops Machine Manager
    from the mapped set (`machine_manager_dropped: machine-only scope`), avoiding the empty-scope
    notification fallback that would otherwise widen lifecycle alerts. An already empty old scope
    retains its existing behavior. Old EXEMPT authority mapping to Machine Manager enumerates all
    currently global/tenant types; future types need explicit assignment (a narrowing). Space Manager
    needs no links. The E1/E2 action exceptions and stopped-writer preview requirements are above.
  - **New assignments are deliberately inert until types are picked.** There is no automatic default
    scope seeder. “All machine types” links the currently available set; it is not a grant to future
    types. The internal resolver contract stays `EXEMPT` or `(type_ids, machine_ids)`, with
    `machine_ids = frozenset()`; query/service consumers retain their signatures and type paths.
  - **Tier 2 now requires a DIRECTLY granted `managing_action`** (`role_scope.grants_directly`, and
    its query-level twin `makerspaces_granting_directly`). This is the hole that made the whole
    feature nearly worthless: `IMPLIED_ACTIONS[MANAGE_MACHINES]` contains `MANAGE_PRINTING`, and the
    built-in `3d_printer` type's `managing_action` **is** `manage_printing` — so a role scoped to
    lasers alone still satisfied the type-manager check for every 3D printer in the lab, straight
    through tier 1's links. A valid direct `manage_printing` grant can supply type authority
    (Space Manager holds it; Print Manager is retired). Machine Manager receives printing authority
    through implication, so its per-person type links still apply. `rbac.can` is untouched, so nothing
    outside `machines/` changes. The object
    check and the list filter **must stay in step** — disagreeing is how a row lists and then 403s
    on click, which is why `capabilities_for_machines`' `_type_mgr` carries the same check.
  - **Tier 3 (per-machine operators) is untouched** — an operator row already names one machine.
  - **A MACHINE-TYPE SLUG IS NOT UNIQUE, and three surfaces assumed it was.** Uniqueness is
    *scoped* (`uniq_global_machinetype_slug` among globals, `uniq_lab_machinetype_slug` per
    makerspace), so a makerspace may legally create a local type carrying a built-in's slug — and
    a global type must be `is_builtin` (`machinetype_builtin_is_global`). Filtering service data
    by slug therefore returned **both** types' rows, so one type's jobs appeared under another and
    a manager could accept or reject from the wrong section. The staff queue and typed manual
    usage now accept **`machine_type_id`**, which takes precedence; the slug parameter stays for
    existing callers, and a malformed id is a **400 via `_query_int`, never a silent fall-through**
    to the printer default. The frontend `isBuiltinPrinterType` mirrors
    `printer_capabilities.is_printer_type` (`makerspace === null && slug === "3d_printer"`) —
    matching the bare slug mounted the printer console for a generic service.
  - **The machine-service REPORT still discriminates on the SLUG, and switching it to the id is a
    crash.** `MakerspaceMachineServiceReportView` branches on `machine_type` to decide whether to
    emit `printer_metrics`; sending an id returns the generic report, and `PrinterServiceConsole`
    dereferences `printer_metrics`, taking the **whole Machines panel** into its error boundary.
    Requests and manual usage use the id; the report keeps the slug. A test that stubs the
    transport cannot catch this — the existing report test answered regardless of query string, so
    the regression test asserts on the **request URL**.

**Staff Machines console is organised as machine type → everything of that type, on PER-TYPE
SUBPAGES.** `MachinesPanel` is the container: it owns the queries (machines, types, and ONE
canonical pool query), the status filter, the service drafts, the create form and the drawer, and
routes between an index of type cards (`MachineTypeCards`) and one type's page (`MachineTypePage`,
which replaced the collapsible `MachineTypeSection`); `SharedConsumablesSection` owns unbound pools.
- **The URL is `/admin/machines/<id>-<slug>` and THE ID IS AUTHORITATIVE.** Machine-type slug
  uniqueness is only *scoped* (`uniq_global_machinetype_slug` / `uniq_lab_machinetype_slug`), so a
  makerspace may legally own a local type carrying a global built-in's slug and both appear in one
  console — three shipped surfaces have already served one type's jobs under another by keying on
  the slug. `parseMachineTypeSegment` reads the leading integer; a malformed segment is "no
  selection" (the index), never a silent fall-through to a default type.
- **`StaffWorkspace` canonicalizes the URL to the active tab's path, so the subpath had to be
  threaded through it** (`keptStaffSubPath`) — otherwise the redirect fires on every load and strips
  the segment, and no per-type link can survive its first render. Subpaths are opt-in per tab
  (`TABS_WITH_SUBPATHS`): every other tab still normalises trailing junk away, and relaxing that
  globally would change how existing bookmarks resolve. The rule is extracted from the component
  precisely so a test can hold it — the panel's own tests mount a router at the deep link and stay
  green with it reverted.
- **A single reachable type renders its page INLINE at the index URL; it does NOT redirect.**
  Redirecting would make the index — and with it machine creation, machine-type configuration,
  shared pools and the delegated recipient picker — permanently unreachable for exactly the scoped
  maintainer those controls exist for. Rendering inline also removes the redirect loop, the
  flash-redirect and the one-versus-many decision during loading.
- **An unknown or unreachable id normalises to the index, and only once BOTH server-scoped sources
  have settled successfully.** Judging on the types query alone contradicts the navigable nested
  fallback; judging while loading bounces every direct link; judging after a failure turns a network
  blip into an apparent permission revocation.
- **The machines query walks EVERY page** (`?page=N`, never DRF's absolute `next`, which
  `staffRequest` would prefix with the API base into a malformed URL). The cards state a count and a
  status roll-up as fact, so a first-page-only read prints a wrong number rather than an obviously
  truncated list.
- **`useServiceDrafts` lives in the container, not the page.** Only one type is mounted at a time
  now, so a hook inside the page would discard a half-typed service form on every navigation.

Load-bearing details that carried over unchanged:
- **Three DISTINCT pool concepts.** *Type display* pools are bound to a machine of that type;
  *shared display* pools (`machine_id === null`) appear ONLY in the Shared section, ending the
  duplication where a shared pool rendered under every compatible type; *form-usable* pools are
  shared pools **plus pools bound to the machine selected in that form** — the UI previously
  offered every pool bound anywhere in the type while the backend rejected them. Pool **creation**
  lives in the Shared section only, because both former create forms omitted `machine_id` and
  could therefore only ever produce shared pools.
- **Pages derive from TYPES, never from status-filtered machine rows** — a status filter
  matching nothing must still render that type's queue, manual usage and bound pools. But the
  type list is **merged with the nested `machine.machine_type`** as a display-only fallback: the
  two requests are independent, so building the index from the types response alone makes machines
  **vanish** whenever it fails or goes stale. Those fallback types **are navigable** (the machines
  list is server-scoped too, so a machine the server returned implies a reachable type) but grant no
  creation authority, because nested copies carry no `can_create_machine`. The governing rule is
  "navigate from server-scoped responses only, never from inferred action strings".
- **Drafts must reset after a completed ACTION.** Drafts live in `useServiceDrafts` keyed by
  machine-type id;
  clearing only `action` on success left the previous job's machine, pool and grams in the form, so
  confirming a prefilled value could **reserve or reconcile the wrong consumable amount**.
  `clearedActionDraft` resets the values with it.
- **Service transitions must invalidate `machineKeys.list`**, not just service queries: they change
  the assigned machine's status and usage hours, and the integrated row would otherwise stay stale.
- **Two service implementations, never three** — `MachineServiceConsole` takes a fixed
  `machineType` prop; the printer console keeps its genuine differences (planned/actual grams,
  reprint, printer reports) and **lost its duplicate roster/create panel**, which meant restoring
  `type_payload.model` to the shared create form and the machine row: that roster was the only
  place a printer model was ever written *or* displayed, and `run_machine_model` reads it.
- Pool load failure renders at **panel level**, because pools feed every type's forms while the
  Shared section may be collapsed; and the empty-machine copy requires a **successful** load, or a
  failed request tells the operator no machines are registered.
  - **FIVE SERVICE SURFACES BYPASSED THE SCOPE ENTIRELY until Phase 5 (2026-08-12).** Each resolved
    a machine (or a service request) by **makerspace alone**, so a laser-scoped maintainer reached
    every printer: typed manual-usage **GET** and **POST** (`views_machine_service_printer`), the
    optional `service_request_id` on that POST (scoped machine, unscoped request — attach a laser
    job's usage to a printer), **pool creation**'s bound `machine_id`, and **staff service-request
    submission** (`views_machine_service`), where an out-of-scope maintainer created a request that
    fired notifications, audit and quota and which they then could not see.
  - **`service_workflow.start()` takes a REQUIRED resolved machine scope, and the scope constrains
    the CANDIDATE QUERYSET, not the winner.** `FIRST_IDLE` picks the first idle machine before any
    scope consideration, so checking the chosen machine afterwards **rejects an authorized start**
    whenever an unauthorized machine sorts earlier — the failure is a wrong outcome, not a 403,
    which is why the regression test asserts on `assigned_machine_id` rather than status. The
    argument is **required** so a future call site cannot silently revert to unscoped behaviour; the
    view resolves the actor's scope and passes it, keeping general RBAC out of the workflow kernel,
    and trusted kernel tests pass `role_scope.EXEMPT` explicitly.
  - **The machine-type list is scoped, and VISIBILITY IS NOT CREATION AUTHORITY.** It previously
    returned every global and tenant type once the actor could see any machine, so per-type sections
    would render headings a role cannot reach. "Reachable" is the union of linked types (**including
    types with zero machines**), types reached through direct type-manager authority and explicit
    operator machines; a **shared machine-less pool does NOT make a type reachable**.
    `can_create_machine` needs type authority; an operator-reachable type alone does not authorize
    another machine of that kind. The console must filter its
    creation selector by it, or it offers an action that can only 403. The field lives on a
    **dedicated** `serializers_machine_types.MachineTypeAccessSerializer`, never on the shared
    `MachineTypeSerializer`, which is nested inside machine responses and reused by create/update
    where the actor context is absent; for the same reason the frontend `MachineType.can_create_machine`
    is **optional** — nested copies genuinely lack it, and absent correctly reads as no authority.
  - **The makerspace-level surfaces AND it in too** (Phase 3), or the narrowing would have been
    cosmetic: the queue, the detail view, service files, consumable pools, machine payments,
    publicity and the machine-service report were each gated on `MANAGE_MACHINES` alone, so a
    laser-scoped role still read every printer job, its costs, its uploaded CAD and its requester's
    contact details. `role_scope.scoped_related_q` is the shared helper; **callers name the lookup
    paths explicitly** because the route from a row to a machine is genuinely per-model and often
    plural — a service request reaches one through `assigned_machine` (null until allocated),
    through its bucket, and through its queue's machine **type**. Naming them at the call site is
    what makes a missed path reviewable. Reports take a resolved scope
    (`build_machine_service_report(..., machine_scope=)`); `None` means "no actor to scope by" (the
    report registry, the superadmin aggregate) and matches everything, and an EXEMPT actor resolves
    to an empty `Q()` so their report is the query it always was.
    - **A collect-only role is added back untouched.** Machine scoping narrows the
      `MANAGE_MACHINES`-derived scope only; `COLLECT_SERVICE_REQUEST` is a different action and
      front-desk handover has nothing to do with which machines a team runs.
    - **Consumable pools with no machine stay visible to everyone** holding `MANAGE_MACHINES` in the
      space — shared stock belongs to no team, and hiding it would make shared filament unmanageable
      by everyone rather than by the wrong people.
    - **Deliberately NOT narrowed:** `views_notification_recipients` (`MANAGE_MACHINES` there
      selects who *receives* maintenance alerts — makerspace configuration, not machine data) and
      `reconciliation.list_payments` (already gated on `MANAGE_MAKERSPACE`, which is exempt anyway).
      The reconciliation **bulk** path is narrowed, via `_require_subject_authority`.
  - **The console owns per-person type links:**
    `GET/PUT /admin/makerspaces/<id>/memberships/<membership_id>/machine-scope`, backed by
    `MemberMachineScopeView` and `machines/member_scope_services.py`, accepts only
    `{machine_type_ids}`. `MemberMachineTypes.tsx` edits server-provided `available_machine_types`
    from the Users and Members rosters. First save Machine Manager, then pick types; an empty
    selection grants no machines. Space Manager/null-primary/non-machine memberships return
    `scoping_applies:false`; PUT refuses with 409, including “assign a role first” for null primary.
    The editor must show that refusal instead of reporting a successful no-op.
    Saves replace the full set, reject unknown/foreign IDs with 400 and audit
    `staff.machine_scope_changed` only on change. The service requires the existing makerspace-first,
    membership-second locks and revalidates authority; immutable roles need no new role locks.
    Role/scope saves invalidate roster, membership, member-scope and auth/me caches and refresh the
    session driving navigation. The service remains in `apps.machines` for tombstone separability.
  - `can_create_machine` needs a type link (or existing exempt/direct-type authority).
    `can_see_machines` uses assigned types, direct type authority or live operators. Type listings
    include assigned types with zero machines and operator-reachable types without creation rights.
    Machine-bound pools follow their machine's type; unbound shared pools keep existing visibility.
    Resolution always ANDs the makerspace, so a cross-tenant link stays inert.
- **`COLLECT_SERVICE_REQUEST` splits job handover out of `MANAGE_MACHINES`.** Collecting a finished machine job is a front-desk act; `MANAGE_MACHINES` is the whole machine lifecycle, so requiring it to hand someone their print forced a front-desk role to also be able to retire a printer. `IMPLIED_ACTIONS[MANAGE_MACHINES]` now includes it, which is why the split needed **no migration and caused no regression** — every Space Manager and Machine Manager already holds `MANAGE_MACHINES`. `_manageable_request(actor, pk, action)` in `views_machine_service` takes the required action per operation: **only** collect passes the narrow one; accept/reject/start/complete/fail/reprint/create keep `MANAGE_MACHINES`. A collect-only actor's queryset is narrowed to `COMPLETED` rows (`_collect_only`), so the queue, drafts and in-progress work stay invisible — the list and detail reads are allowed on the narrow action precisely so the narrowed view has something to show. The action was deliberately **not** granted to anyone by migration: widening real permissions on deployments that never asked is not a migration's job.
- **Collection is CUMULATIVE with machine scope, and the two partitions must stay separate
  (phase 6a).** A role holding scoped `MANAGE_MACHINES` **and** a **directly** granted
  `COLLECT_SERVICE_REQUEST` previously got neither the union nor front-desk breadth, because the
  code recognised only makerspaces that were collect-*only*. The contract is now
  `machine-scoped rows (all statuses) UNION makerspace-wide COMPLETED rows where collect is
  granted DIRECTLY`, split across **two** querysets in `views_machine_service_common.py`:
  `_read_or_collect_queryset` (list, detail, collect) and `_manage_queryset` (every lifecycle
  mutation, plus service files). Adding the union to one shared queryset would have let an
  out-of-scope completed job reach `reprint` and any future completed-state action. An
  **implied** collect grant must never activate the second arm.
  - **`role_grants_directly` exists because `grants_directly` short-circuits on superadmin.**
    That short-circuit is right for tier-2 type authority (it does not come from a role row) and
    wrong for "did this role grant this?". `actions_for_membership` **expands implied actions** —
    so `MANAGE_MACHINES` implying collect would make the union fire for a role that never stored
    it. The role-only variant reads `granted_actions` directly.
  - **Organization collection has its own direct-grant predicate and no machine arm.**
    `organization_grants_directly` uses the filtered organization vocabulary and the centralized
    servable organization-membership query, and is ORed only into the makerspace-wide
    `COMPLETED` collection partition. It never participates in `grants_directly`, type-manager
    authority, `_manage_queryset`, or service-file access. Thus a direct organization
    `collect_service_request` grant can list/detail/collect finished jobs, while pending and
    in-progress jobs and every lifecycle/file operation stay unavailable; organization
    `manage_printing` likewise grants no machine or machine-type manager authority.
  - **`_machine_partition_q` resolves exemption with `role_scope.manage_scope_for`, NOT with
    `makerspaces_for_action(...) is rbac.ALL`.** Those disagree for a global superadmin who also
    holds an explicit machine-scoped membership: `manage_scopes_for` narrows them to that role's
    links, yet they still answer `ALL` at the action level — so the `ALL` shortcut (inherited from
    the pre-6a `_narrow_to_machine_scope`) handed them every row and their machine links did
    nothing. `manage_scopes_for` already answers correctly for both shapes: EXEMPT when a
    superadmin has no membership there, the role's links when they do.
  - **AN EMPTY `Q()` IS THE IDENTITY FOR `filter` AND AN ANNIHILATOR FOR `|`.** Django's
    `Q._combine` short-circuits a falsy operand, so `Q() | Q(status=COMPLETED)` returns
    `Q(status=COMPLETED)` — not "everything OR completed". Representing "unrestricted" as `Q()`
    therefore **inverted** the union for unrestricted actors, narrowing them to COMPLETED rows and
    hiding the whole live queue (a superadmin's detail view 404'd on every pending job).
    Unrestricted is now `None` and callers branch on it. `scope_q_for` may still return `Q()`
    because every one of its callers only ever passes it to `.filter()`.
- **The dashboard narrows machine counters and OMITS non-machine ones — two INDEPENDENT
  decisions (phase 6a).** `build_dashboard` takes `machine_scope` (narrows machine-derived
  counters) and `machine_only` (whether the non-machine counters appear at all). Conflating them
  was wrong, because authority is **action-based and cumulative**: a combined membership can hold
  `VIEW_INVENTORY` *and* a scoped `MANAGE_MACHINES`, and treating "has a machine scope" as "is a
  maintainer" silently removed hardware and stock counts that role is independently authorized
  for. Machine scoping must narrow machine data without revoking another granted action.
  - **The response carries a server-derived `scope_mode: "machine" | "full"`.** `DashboardPanel`
    renders an absent field as `0`, so omission alone silently reads as "nothing to do". The
    frontend must **not** infer exemption from effective actions — that cannot express a
    null-`assigned_role` legacy membership, which is exempt.
  - **Printing is identified by the GLOBAL built-in printer type ID, never the slug.** Slug
    uniqueness is scoped (`uniq_global_machinetype_slug` / `uniq_lab_machinetype_slug`), so a
    makerspace may legally own a local type slugged `3d_printer`; filtering by slug counts its
    jobs as prints. Mirrors `printer_capabilities.is_printer_type`.
  - **`prints_awaiting_collection` follows COLLECTION authority, not machine scope**, or the tile
    disagrees with the Handover queue it links to — a job actionable there and invisible here. It
    is built as a **separate queryset** rather than by OR-ing the scope clause, precisely because
    of the empty-`Q` collapse above.
  - **Asset warranties are inventory data.** A machine-only maintainer sees only their own
    machines' warranty rows; a mixed role also keeps asset rows, which machine scoping has nothing
    to say about. Maintenance schedules are always scoped, since a schedule names a machine and
    there is no non-machine remainder.
  - **Organization-only authority deliberately does not open this dashboard or the notification
    inbox.** Both remain rooted in local membership visibility: their mixed, makerspace-wide
    projections have narrower parity than the action-specific surfaces converted for organization
    reach. This exclusion is intentional, not a missed `scope_by_visibility_or_action` conversion.
- **The hardware `requests` tab is hidden when `canSeeHardware` is false.** It previously also
  passed for `canSeePrinting`, so a machine-only role got a tab whose panel renders no hardware
  rows at all — only a pointer to Machines. Hardware API authorization is **untouched**; a
  deep-linked or stored route normalises to the actor's first allowed tab rather than rendering a
  dead-tab denial.
- **A NARROWED RECIPIENT RULE MUST NOT SUPPRESS THE DEFAULT FOR SUBJECTS IT DOES NOT COVER
  (phase 6c2).** This was a live bug, not a consequence of the delegation feature.
  `staff_emails_for_feature` and `staff_user_ids_for_feature` asked
  `has_selection(makerspace, feature, event)`, which **ignored `scope`** — so once any row existed
  for a (feature, event) the selection became authoritative, and if every row was scoped to the
  lasers while the alert was about a printer, `selected_*` matched nothing and **the printer
  warning reached nobody**. `has_selection` now takes `scope` and is True only when at least one
  row **covers** the subject (`recipient_scope_matching.rule_covers`), so an uncovered subject falls
  through to the action-based default. That restores the module's governing rule: everything here
  fails **OPEN** — over-notifying is recoverable, a missed maintenance warning is not.
- **PRECEDENCE APPLIES ONLY AMONG ROWS THAT COVER THE SUBJECT (phase 6c2).**
  `_selected_memberships` chose one responsible row per membership — members-wide first, then
  role, then user — and tested `rule_covers` **after**. So a members row scoped to the printers
  was picked for a laser alert, failed coverage, and skipped the membership, meaning the
  laser-scoped role row that *did* cover it was never consulted and **the alert reached nobody**.
  That is the same suppression `has_selection` was fixed for, one level further down, and 6c2 makes
  the pairing ordinary: a delegated laser rule sits beside a preserved space-wide members rule by
  design. Rows are filtered by coverage **before** precedence is applied.
- **THE ACTION-BASED FALLBACK IS SCOPED TOO, BUT NO LINKS MEANS UNCONFIGURED, NOT "REACHES
  NOTHING" (phase 6c2).** Once `has_selection` learned to fall through per subject, the fallback
  became reachable for an alert naming a machine — and it predates machine scoping, so it would
  mail every `MANAGE_MACHINES` holder the printer's maintenance detail, including a laser-only
  maintainer who cannot open that machine in the console. `recipients.reach_filter_for` narrows it.
  **The asymmetry with access is deliberate and must not be "fixed":** for access, a
  machine-managing role with no links reaches nothing (fail closed); here the same state means the
  role was never configured, and treating it as "reaches no machine" would mute a space's
  maintenance mail the instant an alert named a machine. The filter therefore removes a membership
  only when its role holds links that genuinely exclude the subject. Exempt actors always admit,
  so a machine nobody is scoped to still reaches whoever administers the space, and alerts naming
  no machine admit everyone — leaving every non-machine feature untouched.
- **Delegated recipient rules: a maintainer edits their own partition and nothing else
  (phase 6c2).** Behind the `notifications.delegated_recipients` feature (SM-writable,
  **default OFF**, and OFF means *invisible* — today's 403, not a greyed editor). Authority is
  `feature_enabled(...) AND role_scope.is_machine_only(...)`, and **maintenance only**;
  `MANAGE_MAKERSPACE` keeps full authority over every feature.
  - **`PUT` deletes by an explicit id list, and for a delegated actor that list is only the rows
    ENTIRELY within their reach.** A full replace would have destroyed space-wide and other-team
    rows the actor cannot even see. `row_fully_reachable` returns **False for a row with no scope
    links** — that is what preserves a space-wide policy — and False for any category link, since
    `manage_scope_for` grants no category reach (fail closed).
  - **A rule with no scope links means "everything", so a delegated actor may never write one**, or
    a narrow grant authors space-wide policy. A multi-type rule needs **full** coverage to edit, or
    one team silently narrows another's.
  - **Identities are validated, not merely offered.** The picker shows a delegated actor their own
    role and the teammates holding it; the API refuses anything else. Accepting identities the
    editor never presents is the inverse of a list that 403s on click — it would let a narrow grant
    point alerts at an arbitrary colleague or a role it does not hold.
  - **Hidden policies surface as an identity-free marker** (`{feature, event, count}`) — never full
    rows (which expose recipient identities and role configuration to a narrow grant) and never
    silence (which makes the operator reason wrongly about fallback).
  - **Chat destinations and `receives_notifications` stay Space-Manager-only** and were deliberately
    not widened.
  - **A `requester`/`members` row is SHARED, and is merged rather than replaced.**
    `uniq_notification_recipient_special` is `(makerspace, feature, event, kind)`, so exactly one
    such row can exist per event — two teams wanting "notify the requester for MY machines" are
    describing one row, and delete-then-insert cannot express that (the second team's insert tripped
    the constraint and surfaced as a misleading "a Space Manager-managed policy already uses one of
    these recipients"). `recipient_rule_merge` therefore strips only the links inside the delegate's
    reach and adds their submission back. Refusing the two kinds outright was tried and reverted: it
    removes a capability the design intends, and a pre-existing test asserts a delegate CAN write a
    scoped `requester` rule.
    - **`_manageable_identity` returns True for these two kinds**, reversing the original rule.
      They name no identity at all, so scope is the only question — and refusing them meant a
      delegate could not round-trip their own save. **The accepted consequence is that SCOPE IS
      OWNERSHIP here: `created_by` is never consulted, so a delegate may delete a Space Manager's
      special row lying entirely inside their reach.** That is already the contract for a `role`
      row naming their own role, and the schema carries no per-link contributor provenance to
      express anything finer. Pinned by a test rather than left implicit.
    - **A partially-overlapping row is PROJECTED, not hidden.** `payload` would otherwise omit it
      and the delegate's successful save would read back as absent — the same "looks dropped"
      defect the merge exists to remove. `project_special_row` emits their own links only, with
      **`id: None`** (PUT is not id-addressed, nothing reads it, and the real key would disclose a
      row they do not own), and the row is *still* counted in `managed_policy_markers`. The
      projection and the merge **share `owned_links`**, or an untouched form silently changes
      policy on save.
    - **A link-less row is refused with a 400, never narrowed or silently no-oped.** No links means
      EVERYTHING, so adding the delegate's links would shrink somebody else's space-wide policy.
      Omitting the kind leaves it untouched.
    - **Delete-on-last-link is UNREACHABLE by construction** (a preserved row always keeps an
      out-of-reach, cross-tenant or category link) and is kept only as a fail-safe, because a
      linkless leftover would silently promote a narrow rule to space-wide. It counts remaining
      links **through the link models, never `row.machine_type_scopes.count()`** — the service hands
      these rows over `prefetch_related`, and a populated related manager answers `.count()` from
      that stale cache, reporting one link for a row that has none. Driven by a direct unit test,
      since no API path reaches it.
    - The marker copy names **no author**: with a shared row the hidden remainder may be another
      maintainer's links, so "a Space Manager-managed policy" would often be false.
  - **`revalidate` refreshes the identity gate as well as the reach**, and the success response
    serializes with `keep.reach` — both were resolved before the makerspace lock, so a concurrent
    role reassignment or scope narrowing left the write and the reply using authority the actor no
    longer held.
- **`role_scope.is_machine_only` is the ONE answer to "is this actor a per-type maintainer and
  nothing else" (phase 6c1).** Shared by the dashboard's non-machine counters and the in-app
  notification inbox, because two copies would drift and the failure is silent — a surface that
  keeps appearing for the very role it was meant to hide from. Three conditions: holds
  `MANAGE_MACHINES`; resolves to a **non-EXEMPT** scope (so space managers, membership-less
  superadmins and null-`assigned_role` legacy Machine Managers are excluded); and holds neither
  `VIEW_INVENTORY` nor `MANAGE_MAKERSPACE`. `MANAGE_PRINTING` deliberately does not count —
  `MANAGE_MACHINES` implies it, so asking `rbac.can` would make the answer always False and the
  whole predicate inert. A role that **stores** `manage_printing` is exempt, read through
  `role_grants_directly` — same distinction, and the same reason, as
  `procurement.access.machine_type_scope`. The batched copy in `accounts/serializers.py` must read
  the stored grant too: its `actions` set is the *expanded* one, where the implication is always
  present.
  - **`AuthMembershipSerializer` in `accounts/views.py` is the documented contract for this
    payload, and it is easy to forget.** `user_payload` emits the dict; the inline serializer is
    what reaches `openapi-schema.json` and `api.ts`. Adding a key to the dict alone leaves a
    generated client unable to discover it — and a schema-sync check still passes, because nothing
    told spectacular the field exists. `can_configure_machine_types` had been undocumented that way
    since it shipped. **Two exact-payload tests pin this dict** (`tests/accounts/test_auth_payload_l4.py`
    and `tests/test_auth_profile_scope.py`); both must be updated, and they exist to catch exactly
    this drift.
  - **The inbox is withheld, not scoped.** A `Notification` carries no machine provenance and its
    `read_at` is makerspace-wide, so one team's acknowledgement silences the row for everyone.
    Accepted cost: a scoped maintainer gets no in-app alerts and relies on email/chat, where
    per-event recipient rules already narrow by machine. Adding provenance plus a per-recipient
    read state is the alternative and is its own phase. All four endpoints share
    `_makerspace_for_manager`, so the denial is one check rather than four.
  - **The console reads `is_machine_only` off the membership** (`/auth/me` + `/auth/login`, beside
    `can_configure_machine_types`) and passes it into `getStaffAccess`; it must not be re-derived
    from effective actions, for the same reason as `scope_mode` and `machine_type_required`. It is
    resolved with the **batch** `manage_scopes_for_memberships` — the per-actor call would put an
    N+1 behind both endpoints, which is the query budget that payload is written to protect. The
    tab is **omitted**, not permission-hidden, and the unread badge lives inside that link so it
    stops polling with it. The flag defaults permissive so a caller that has not loaded it yet does
    not flicker the tab away.
- **`ToBuyItem.machine_type` narrows procurement, and `NULL` means LEGACY — never "shared"
  (phase 6b).** `MANAGE_MACHINES` implies `MANAGE_PRINTING`, and `procurement/access.py` keys the
  PRINTING stream off that action, so a laser-scoped role read **every** printing To Buy row in the
  space: `vendor_name`, `actual_unit_cost`, `purchaser`, `link` and every attached receipt.
  - **A NULL row is visible only to scope-exempt actors**, under an explicit "Unassigned" heading.
    Reading NULL as "shared" would have exposed every pre-migration row to every maintainer — the
    exact leak the phase exists to close. Migration `procurement/0007` therefore infers a type
    **only from durable provenance**, in order: `resulting_machine`, then a **machine-bound**
    `source_pool`, then a machine-bound `resulting_pool`. Everything else stays NULL. Never guess
    from `name`, `kind` or the creator's role: a wrong stamp hides a row from the Space Manager who
    created it, which is worse than leaving it unassigned.
  - **`access.machine_type_scope` returns `None` for "not narrowed" and an EMPTY SET for "narrowed
    and reaches nothing".** Callers must test `is None`; conflating them makes a role with no links
    fail *open*. Three exits, in this order: no `MANAGE_MACHINES`; scope-EXEMPT; or the role
    **stores** `MANAGE_PRINTING`. The last one matters because only the *implied* grant is the leak
    — a role whose `granted_actions` really lists `manage_printing` was given that stream
    deliberately, and revoking it because the role also gained machine duties is the mixed-role
    mistake from the dashboard. EXEMPT is checked first, or a legacy null-role membership's frozen
    action set would answer that question instead. Read with `role_grants_directly`.
  - **Use the person's linked TYPE ids only.** There are no per-machine membership scope links.
    Type-assigned Machine Managers see those types' printing To Buy rows; Space Manager sees all.
    A tier-3 operator grant does not confer procurement authority for the machine's whole kind.
  - **`kind` stays server-derived and orthogonal**, and the narrowing applies to PRINTING rows only
    — hardware rows survive for a role that independently holds `EDIT_INVENTORY`.
  - **Scoping the list is not enough; `procurement/access.py` is stream-based, so the object
    endpoints were the real hole.** One `scope_items` helper feeds list, detail get/patch/delete,
    export, both move endpoints and `resolve_item` — and `resolve_receipt` delegates to
    `resolve_item`, so the receipt-pk paths (url, delete) are scoped transitively rather than by a
    second copy of the rule.
  - **`machine_type_required` is SERVER-derived** (`access.machine_type_is_required`, the same
    predicate `validate_machine_type` enforces) and shipped on the options endpoint. The console
    originally inferred it from effective actions plus `role_id !== null`, which is the mistake
    `scope_mode` exists to prevent: a null-`assigned_role` legacy membership is exempt and cannot be
    expressed client-side, and "holds `manage_machines`" is a different question from "is narrowed"
    (a `MANAGE_MAKERSPACE` role holds it and is exempt). It defaults to `false` while the query is
    in flight, so the form never demands a value before the options that satisfy it exist.
  - **`select_for_update()` cannot be combined with `select_related()` on a NULLABLE FK.** Postgres
    rejects it outright — *"FOR UPDATE cannot be applied to the nullable side of an outer join"* —
    so `move_to_printing` must not select-related `machine_type`; it lazy-loads in one extra query,
    free next to the writes that transaction already performs. `makerspace` is non-nullable, so its
    INNER JOIN is fine to lock against.
  - **The type cannot be retagged away from durable provenance.** Because `scope_items` treats the
    column as an authorization label, relabelling a row that came from a real machine (or clearing
    it to the exempt-only NULL bucket) hides it from the team owning that machine and shows it to
    another, while contradicting the asset it names. Only a scope-exempt actor can reach that PATCH,
    so this is an **integrity** rule, not an escalation one. `validate_machine_type_provenance`
    refuses a mismatch; re-asserting what provenance already implies is a no-op and rows with no
    provenance stay freely taggable, so nothing is trapped — a mislabelled row is fixed by
    correcting the provenance, not the label.
  - **A BARREL SPLIT MUST NOT MAKE SUBMODULES IMPORT EACH OTHER.** Extracting the export view into
    `views_items_export.py` while leaving the shared constants in `views_items.py` created a real
    cycle — `views_items_export` imported `views_items`, which imported `ToBuyExportView` back at
    the **bottom of the file** — so importing the export module *first* raised
    `ImportError: cannot import name ... from partially initialized module`. It stayed hidden
    because the urlconf always imported `views_items` first. Shared constants and query helpers
    live in a neutral `views_common.py`; submodules depend on it and never on each other, and
    `views.py` is the only thing that names the public surface. Verified by importing **each**
    submodule first in its own process, which is the check that fails when this regresses.
  - **A migration test must pin every app whose historical model it instantiates.**
    `MigrationExecutor.project_state(targets)` replays only the named targets and their
    dependencies, so `makerspaces` left unpinned yields a historical `Makerspace` behind the real
    table; Django applies field defaults in Python rather than DDL, so the INSERT omits newer
    columns and Postgres rejects the NOT NULL. Rewind the full graph forward in `finally`.

- **Certification gating (forward plan phase 5, 2026-09-04) is one function and fails CLOSED.**
  `machines/certifications.py::require_certification` is the only place that decides "is this member
  trained"; `service_workflow_actions.submit` and `services_bookings.create_booking` call it and let it
  raise. It is a no-op while the `machines.certifications` feature is off or the `machines` module is
  uninstalled (a bookings-only space is never gated by a module it lacks — `BookableSpace.machine_type`
  is nullable and the import is lazy), and once on, no resolvable membership or no live grant is a
  refusal, never a pass. Requirements live on the **machine type** (`CertificationType`, flags
  `is_required_for_service` / `is_required_for_booking`), so adding a machine cannot un-gate it; a grant's
  expiry is the **stored** `expires_at`, so tightening `validity_days` later cannot retroactively
  invalidate correctly-issued training. Authority to define types, grant, revoke or **override** is
  `access.can_create_machine` — machine-TYPE authority, never a per-machine link — and every honoured
  override writes `certification.override` naming the type it skipped. Types are deactivated, never
  deleted (grants are evidence); grants are revoked, never edited. Publication is consent, not
  configuration: certifications reach the maker profile only through `MemberProfile.show_certifications`,
  a separate opt-in from `is_visible`, and reach a printed card only when the template lists the
  `certifications` field.

- **Machine-service queue ETA and cancellation (decisions 44/45) cover EVERY machine type.**
  The forecast is derived, never stored: `service_queue_eta_core.Timeline` simulates one
  (makerspace, machine type) timeline across every bucket/queue sharing those machines, assigns
  only ACCEPTED rows in `created_at, id` order to the earliest-free compatible machine (a forecast
  tie-break, not a dispatch policy), honours `ServiceQueue.capacity` including slots held by running
  jobs on excluded or unassigned machines, and withholds (`unavailable`, both timestamps null) rather
  than guessing when a required duration or a machine's availability is unknown. Capacity is
  `is_active` and status IDLE/RUNNING, but a coherent in-progress row governs availability whatever
  the flag says (C8) — `start()` refuses a machine that still has an in-progress row. Counts stay
  scope-local and agree with the legacy `queue_position` fields. The ORM adapter makes at most four
  SELECTs per tenant snapshot, loads scalar columns only and is request-scoped; serializers read the
  snapshot from context, never the ORM. Staff `service_queue_summary` appears only where the actor
  may edit (manage) that machine and the tenant has `machine_service`.
  - **`cancelled` is terminal** (pending/accepted/in_progress → cancelled). Cancel releases any
    consumable hold with ZERO consumption through the kernel's reconcile (`actual_quantity=0`
    when `reserved_quantity` is set; the legacy gram branch only for pre-metering holds), never
    debits consumptions and never creates a payment; only a cancelled RUNNING job frees its
    machine. A cancelled RUNNING job still records its consumable cost through
    `consumable_costs.record_service_cost`, in the cancel transaction and the complete/fail lock
    order (decision 58) — a cost record only, never a charge. Staff (and, through the API, the
    owner) may confirm `consumed_quantity` for a RUNNING job (decision 61a): validated
    `0 ≤ amount ≤ hold` in the hold's own unit, it settles the hold with that consumed quantity
    (it stays taken from stock) and is what the cost record prices. Empty or 0 is the
    zero-consumption release; a waiting job refuses a non-zero amount. The staff form pre-fills
    elapsed ÷ estimated duration × planned quantity (capped at the hold); the member form hides
    the field and sends nothing. Staff reject releases holds the same way and keeps its pending-only meaning. Owner
    cancel is `member_id == caller` on the member surface
    (`/api/v1/member/machine-service/requests/<pk>/cancel`, plus the `by-token/<token>/owner`
    lookup), works with `membership` off, refuses claim/staff/platform sessions, and a bearer
    tracking token alone never authorizes a write. Staff cancel is manage-scoped only.
  - **Lock order is request-first everywhere (C1):** write fence → request → scope (pooled
    `ServiceQueue` row, or the bucket's own `Machine` row) → machine(s) → pool. The scope lock is
    taken only when the waiting head can change (accept, reject, reprint, cancelling a waiting
    row, start); complete/fail and cancelling a running row never take it. `start()` counts the
    queue's in-progress rows before locking the chosen machine and without a row lock (it can only
    over-count); a bucket start locks the bucket machine and the chosen machine in id order (C15).
    Linked typed manual usage follows request → machine → pool → attributed member `User`
    (`usage_attribution.validate_attribution`); submit and reprint lock the obligation owner
    (`lock_obligation_owner`) after their makerspace/target locks. `submit()` (pooled and bucket)
    takes the makerspace fence FIRST, then the queue / bucket machine — the device adapter's
    makerspace → … → request → machine order — so submit, the device adapter and the
    request → queue writers cannot form a three-way cycle. Staff cancel re-checks the actor's
    machine-type scope (`role_scope.covers_service_request`) under the row lock.
  - **Never join extra rows into a workflow FOR UPDATE, and lock the makerspace row FOR NO KEY
    UPDATE.** Django FKs are DEFERRABLE INITIALLY DEFERRED, so every commit takes FOR KEY SHARE on
    the makerspace (and other referenced rows) at COMMIT. A FOR UPDATE on those rows — directly
    (`require_module_locked`, `require_feature_locked`, `limits.check_quota`,
    `_require_module(locked=True)`, all now `no_key=True`, so a caller taking several of them
    never upgrades to FOR UPDATE) or via a
    `select_related` join without `of=("self",)` — deadlocked the device printer adapter and
    `start()` against a concurrent cancel's commit. NO KEY UPDATE still serializes against module
    install/uninstall. The machine-service workflow — including typed manual usage and the device
    adapter's `printer_access.live_target` — takes every request, queue and machine row lock FOR
    NO KEY UPDATE (`of=("self",)` wherever relations are joined) for the same reason: a row updated twice in
    one transaction re-runs its FK checks at COMMIT, taking KEY SHARE on its queue/machine. After a row lock that may have waited, re-read (`refresh_from_db`) before
    trusting joined relations: Postgres re-checks only the locked row, not its joined rows.

## Community workflow additions (2026-10-17)

- **Loan policy belongs to lending authority.** `ReturnPolicyView` and
  `loan_policy_settings.update_loan_policy` accept `EDIT_INVENTORY` or `MANAGE_MAKERSPACE`;
  audit action stays `makerspace.return_policy_updated`. General settings no longer owns a
  duplicate default-loan-days write. Inventory, Machine, Event and Booking Managers edit domain
  settings from their console; this grants no makerspace/staff/payment-credential authority.
- **Space Manager navigation is task-grouped, permission derivation unchanged.** Today, People,
  Inventory & loans, Machines, Events, Bookings, Money and Space settings; Platform for superadmins.
  Staff & roles leads People; less-used destinations live under More. The settings hub searches
  sections/consoles and shows the setup checklist. Other roles retain their scoped sidebar.
- **The public makerspace page composes existing gates.** Featured activities → inventory →
  machines/bookable spaces/membership/contact; no new permission or projection. `publicHome`
  chooses the composed page for Inventory or multi-family automatic landing, even with no catalogue.
  Explicit non-inventory and single non-inventory-family landing stay on their family pages.
  Old `?space=`/`?confirmation=` booking links retain routing. Featured events cap at six and use
  the existing public events query; no room/QR/evidence/private inventory fields enter the page.

### Event speakers, edits and envelopes

- **Speaker credit is explicit account linkage.** `EventSpeaker` links a scoped member/staff/
  registrant, or a signed-in claimant of a single-use 14-day HMAC-digested fragment link. Optional
  speaker check-in access requires event-manager authority, rechecked for the inviter at claim.
  Removal is soft/audited and does not revoke its separately created Team check-in grant.
- `speaker_history.contributions_for(user, makerspace)` returns account-linked, not-removed
  `SpeakerContribution(event, occurred_at, role="speaker", speaker_id)` rows for this live host,
  events module on, published/completed events and past milestones. Time is earliest linked website
  session start, otherwise event start. Callers separately enforce public title/consent rules.
- Ticket/category edits are audited. Referenced ticket delete refuses 409 `ticket_type_referenced`;
  referenced category delete refuses 409 `category_referenced`. Used ticket price/audience freeze;
  capacity cannot fall below live registrations. Deactivate a used type rather than rewriting sales.
- Private attendee history is exact-account-owned and does not require Membership; an existing
  membership must be active. Staff member-drawer history needs `MANAGE_EVENTS` or `MANAGE_MEMBERS`.
  Create shows essentials with More options; drawer uses Overview/Registrations/Check-in/More,
  retaining old eventTab links and explaining draft check-in availability.
- Event lifecycle/series/registration, reminders, certificates and campaigns have personal sources.
  Staff rooms retain the summary; legacy staff in-app/push remain, so staff envelopes pre-skip those
  legs. Delegates use audience `member` with live registration-grant checks. Event campaigns retain
  batch-worker email and pre-skip envelope email; the additional channel fan-out has no periodic
  lost-task resume. Staff email now requires a verified account mailbox. Invitations retain their
  existing email/share paths; no optional account-linked invitation notice was added.

### Booking queue, galleries and departure evidence

- Requests queue is resource-authorized through `booking_authority`; issues are scoped the same way.
  Reject requires a trimmed reason (max 1000); cancel accepts an optional reason. Reasons reach
  requester notices/history and clear on restore. No other decision fields are accepted.
- `BookingDepartureEvent` is append-only in model methods and Postgres; `remark` is scoped PII.
  Audit carries facts/has_remark, never remark text. One departure per confirmed/completed booking,
  from 30 minutes before start; exact-account owner has until 48 h after end. Staff need check_in
  or manage_reservations. Outcomes are all_good/issue/damaged/left_early; every non-all_good outcome
  requires a remark and opens one `BookingIssue`. Resolution is audited and never edits evidence.
- `BookableSpacePhoto` is public place imagery, max 12/resource, separately accounted from private
  evidence. Staging presign → size/sniff finalize → locked attach; writes need edit_details and
  audit, delete releases bytes/quota after commit. Shared Gallery supplies keyboard viewing.
  Hosted at matches event location text to a public space name/location, then host-cover fallback;
  no venue FK or private resource disclosure is implied.
- Booking lifecycle/reminders/campaigns reserve owner/staff/grant-holder personal envelopes;
  sources recheck calendar revision, owner, requester toggle, grant and campaign sender/audience.
  Rooms keep staff summaries; account-less guests retain contact email. Account envelopes need
  verified account email. Saved booking-category campaign choices use envelopes; other recipients
  keep batch email, never both. Requester notifications default on; migration makerspaces/0095
  flips only false rows without an audit-recorded write to that setting. Resource overrides win.

## Events program invariants (four phases, `f16896f`..`dab0354`)

### Events programme integration contract (2026-10-18)

Checkpoint `f1ef7736` adds the programme schema/mounts and generated API, not completed
runtime acceptance. Keep `events.hackathons`, `events.mentoring`, `events.mentor_rounds`,
`events.volunteering`, `events.project_gallery` and event hackathon config OFF until the
[closure ledger](events/integration-status.md) and [AO evidence](events/acceptance.md) pass.
The rules here are binding; a rule's presence does not claim every adapter is installed.

- **One admission writer and real hard capacity.** A application lifecycle calls the
  canonical registration/payment/ticket/waiver bridge, never a second status writer.
  Draft/context GET creates no registration, charge, QR, redeemed code or vault intent.
  Private staged decisions change no owner/public admission/count and send nothing.
  Explicit atomic release rechecks current versions/reviews/live nonconflicted authority.
  RSVP defaults to four days from release. Offer reservations/overbooking are separate
  from hard confirmed event/ticket seats. Cohorts count people, require each member's own
  RSVP and confirm all-or-none; decline/expiry releases the cohort. Zero/unlimited semantics
  remain owned by existing capacity helpers, not duplicated by clients.
- **Consent is specific evidence.** Each applicant accepts the current immutable CoC;
  host waiver follows existing audience/provenance policy and cannot be inferred from
  a draft ID/checkbox. MLH sharing, gallery metadata/items, sponsor recruiting résumé,
  print photo, public card and public certificate verification are independent choices.
  Role approval, upload, leader consent and publication never manufacture another choice.
  Only D's `ParticipantSponsorResumeConsent` workflow grants/revokes sponsor access,
  including contributor UI and B asset replacement/deletion. Own-track frozen project,
  exact current ready asset/hash and live grant are all required; no vault access.
- **Roles are scoped sources, not tenant roles.** Helpers/contributors use member accounts.
  Delegation cannot exceed the issuer's current permissions/scope/window; imported roles
  are inert. Manual and shift/contribution entitlement sources remain distinct. Expiring
  one source must not revoke an independent manual permission. Display roles alone grant
  nothing. Shift attendance is separate from event attendance; verified positive work
  minutes require a second person and gate volunteer thanks. Practice stays isolated.
- **Programme lock contract supersedes legacy order for migrated paths.** Prepare keys,
  KMS material and immutable resources outside event row transactions. Enter declared
  source boundary → global PII fence → sorted tenant fences → sorted affected-account
  fences → series/event → sorted makerspaces → live authority → parents → children.
  Declare every affected owner/reviewer/print subject before locking; never expand the
  scope afterward or lock User/key rows beneath Event. Recheck prepared epoch/hash/date/
  source revision inside fences. Never combine `select_for_update()` with nullable-FK
  `select_related()`. `programme_locks.py` alone does not migrate ordinary/legacy callers;
  GF4 routes canonical writers through the shared boundary; real PostgreSQL lock/race proof remains required.
- **Snapshots and scores freeze their inputs.** B's submit is the sole content-snapshot
  writer; roster, exact ready assets/links/tracks/prizes/form references and hashes freeze.
  Later drafts/uploads cannot alter judging or a published card. Amendment requires a
  reason/new snapshot and invalidates old judging; submitted scores/results remain history.
  Missing/recused work is not zero. Results finalize separately from publication and
  corrections append revisions. One initial gallery publish selects exact consented items;
  live teammate withdrawal stops bytes immediately, regrant requires a fresh amendment.
- **Accepted bytes have immutable ownership.** Stage-only grants, server-side size/hash/
  signature checks, optional explicit scan policy, bounded non-root video probe and
  conditional final promotion precede ready state. A configured scanner outage never
  means clean. Live authorization runs before storage and between bounded chunks (at most
  1 MiB, policy interval at most two seconds); no positive policy cache/download presign
  bypass survives consent/role/source revocation. HEAD has the same gate. Public IDs reveal
  no private keys. No accepted source/firmware/toolpath is executed.
- **Quota and expiry are independent of permission switches.** Managed allowance is decimal
  25,000,000,000 bytes per event; self-host may use a bounded or unlimited event pool.
  Per-file/group/submission caps still apply. Used+reserved includes pending and failed
  cleanup; release follows confirmed deletion. First results/cancellation/fallback retention
  is 365 days and cannot extend an existing deadline. Logical expiry denies reads even
  while deletion retries; retained records/hashes are not removed. All final/staging/
  verification versions/multipart locators need durable cleanup, even after runtime-off,
  migration or purge. Permanent FK-free asset obligations and print receipts retain exact locators across purge; bounded byte-only recovery must survive Events tombstoning.
- **Backup is distinct from live file retention.** Typed capture reads direct asset state/
  expiry/size/hash. Missing ready unexpired bytes fail; terminal expired absence is valid;
  in-progress cleanup/promotion and overdue-ready rows require finalization before capture.
  Existing archives have their own retention and can retain prior bytes. Portable import
  preserves absolute expiry, typed hash provenance and evidence but resets live consent,
  public/claim/credential authority; no in-flight upload resumes abroad. Account vault/keys
  never enter tenant closure. GF4 installs typed encrypted answer remapping and verified target asset publication; real portable/raw-dump proof remains required.
- **Saved details is private account data.** F's single standard-key/form validator controls
  mappings/show-if/disclosure; P owns always-encrypted account values/intent preparation.
  Only explicit true per-field choices on visible validated submitted answers create intents;
  sensitive DOB/résumé/diet/accessibility/emergency choices default false. Conflicts never
  overwrite a newer saved value. Organizer sees actual submitted answers only. Vault delete
  does not delete independent submitted evidence. Account erasure permanently fences new
  vault writes and removes owner drafts through explicit lifecycle hooks. Event retained-history boundaries may lock erased owners without reviving vault/key writes; nested vault writes still recheck permanent erasure.
- **DOB is a source; age is a projection.** Registration, application and role-only assignment
  derive age as of the event-local start date from encrypted DOB/source history. No numeric
  age is persisted in a field, snapshot, audit or coordination cache. Prelock date changes
  require source review/recomputation; locked revisions keep the frozen as-of date; reopening
  archives the old source. Explicit DOB questions disclose that fact before submit; ordinary
  age questions expose age only. No age limit, guardian/minor gate, age bounds or age/DOB
  visibility dependencies may control admission, roles, shifts, CoC or another answer.
- **Selected photos never default to private identity.** Choose both own active profile and
  membership explicitly, or neither; print and public-card scopes require separate consent.
  Public handle/profile/module eligibility is live. Source deletion must clear both FKs and
  consent atomically, invalidating print/card readers without deleting independent evidence.
  Foreign profile bytes and the global vault are never collected by an Events-only purge.
- **Verification is not document access.** Explicit event policy plus per-certificate opt-in
  exposes only snapshotted event title/local event date and valid/revoked state. No recipient,
  reason, PDF URL, answers or bearer. Unknown/private/pending is uniform 404; no-store/throttle.
  Ended/private website does not defeat an independently enabled policy; host servability,
  Events module and withdrawal still gate. Historical opt-in defaults false. Private certificate
  PDFs may use authorized personal attachment delivery; bearer badge/QR PDFs never do.

UI acceptance includes Space Works tokens in both themes, approved Gilroy/one Unbounded
accent, lucide controls, AppShell layouts, original artwork, keyboard/44px/reduced motion/
real contrast checks. Account and retention mechanisms survive optional Events removal;
runtime providers/pages/reports do not. Reimbursement (decision 34) and full staged forms
(35) are integrated on `lane/events-final`; their rules follow.

### Staged forms and travel support (integration, 2026-10-20)

- **Inline blocks prepare outside, bind inside, roll back together.** `events/inline_forms.py`
  validates `stage_forms` and `reimbursement_request` before the outer transaction and binds
  them after the canonical registration/application rows exist, before the outer receipt.
  Any bind, intent, notice or receipt failure rolls back the whole signup. The outer digest
  includes both blocks; replay resolves before preparation. No HTTP field is accepted as
  binding proof. Drafts and answer edits refuse inline blocks (`inline_forms_submit_only`).
  Only a self-signup carries them; staff on a member's behalf get `owner_consent_required`.
  Explicit Saved-details choices are cross-checked across the base form and every inline stage
  form; a conflicting value refuses the signup with `saved_detail_form_conflict`.
- **An omitted required application form refuses the signup.** When an event has a published
  required application-stage form, every self-signup binds, so a missing applicable form
  raises `stage_incomplete` and leaves no registration, application or assignment.
- **A present request block with the module off is refused, never dropped** (409
  `reimbursement_unavailable`). An omitted block is harmless with the module off.
- **Stage readiness is read under the lock, never inferred.** RSVP accept and every
  attendance source call `staged_forms.guards.require_complete_locked`; offline sync reports
  `stage_incomplete` for that item. An empty assignment list or a cached roster is not proof
  of completion. Claim submit uses the same guard.
- **One installed Saved-details binding.** `contracts/admission_registration.py` installs a
  single `IntentSubjectBinding` that routes `stage_response` subjects to
  `staged_forms/prefill_provider.py`; stage subjects never enter the DOB derivation resolver.
- **Attendance feeds payout eligibility in the attendance transaction.** Check-in bumps
  `attendance_revision`; a correction appends `EventAttendanceCorrection` with the latest
  check-in watermark; both republish claim eligibility while the add-on is live.
- **Archive pauses settlement.** `archive_impact` adds `unpaid_event_payouts`; both archive
  routes show every money count. Payout authority requires a servable space, so nothing settles
  while archived.
- **Purge preflight is always shown.** `purge_module_data` prints the read-only
  `preflight_report` before any prompt and refuses on a blocker; `--preflight` exits after
  printing; `--yes` skips only the confirmation prompt.
- **Payee purge timing is a deployment setting.** `EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS`
  feeds both the purge anchor and the member disclosure; the eight `EVENT_REIMBURSEMENT_*` /
  `EVENT_STAGE_*` settings are bounded and refuse to start when out of range.
- **Mandatory finance envelopes, and their one tenant-import exception.** Payee `details` and
  obligation-revision `decision_summary`/`cancellation_note` must always be `pii:gcm:v1:` envelopes
  whose key row (`active` or `rotated`) exists for the tenant (`finance_mandatory_envelope_guard`, even
  with optional PII encryption off). `encryption/0011` waives ONLY the key-row lookup, and only while
  that tenant's write fence is closed for `tenant_import` under the session's own
  `app.pii_fence_operation` (a Lane D build, whose DEKs travel sealed and install at activation). The
  envelope format check, the host check and the write-fence check stay on in every case; another
  tenant's fence never waives it. Owner decision #61b.
- **Stage forms, travel support and the payout ledger migrate custodially.** All domain and
  ledger rows are portable (`tenant_migration/catalog_reimbursements.py`); work rows and
  FK-free cleanup locators never travel. Mapped finance fields (payee details, decision
  summaries) stay ciphertext in the archive and are rebound to the target tenant key in
  memory (`pii_reimbursements.py`, which also remaps typed IDs inside encrypted
  documents). Domain `uuid` columns and every `operation_id` are preserved and a target
  collision refuses the import; UUID primary keys follow the PK map
  (`semantic_reimbursements.py`). Imported programmes are disabled and `imported_paused`
  with the request window closed; imported stage assignments are inert. Only
  `ready`/`attached` bytes travel; in-flight uploads become inert `failed` rows. The target
  creates its own cleanup locators (`reimbursement_assets_import.py`, also after a Lane D
  restore). Rows whose insert guards check a not-yet-inserted pointer are inserted NULL and
  updated once every row exists; self-pointer chains insert parents first
  (`import_pointers.py`, which also sets the transaction-local `app.tenant_import` flag so
  the attendance-correction guard admits historical revisions). Readable exports never
  carry these rows.

**Delight is on by default and per space (2026-10-20).** `ui.delight` and `ui.easter_eggs`
are standalone default-on features (also in `setup_areas.ALWAYS_FEATURES`); migration
`makerspaces/0098` added both to every existing space because no earlier per-space choice
existed. `UI_DELIGHT_ENABLED` / `UI_EASTER_EGGS_ENABLED` now default `True` and act only as a
deployment kill switch: the browser shows effects when the deployment flag AND the showing
space's feature are on. A reduced-motion preference always wins, and scanner, kiosk,
check-in and payment routes never show easter eggs.

### Event printable credentials (Lane E)

- Badge templates read as version 2 with top-left millimetre boxes, grid snapping,
  bundled font choices, 6-48 pt size, bold, alignment and colour. Version 1 converts
  on read without mutating the stored template; legacy contact selectors are removed
  from that safe projection (name is the fallback). New contact bindings refuse.
  ReportLab remains authoritative:
  text shrinks no lower than 6 pt, then overflow refuses with a typed validation error.
  Shared `operations/printable_*` geometry, serializers, fonts and PDF primitives
  never import events or bookings. Noto fonts ship in the backend image; CJK uses
  the standard PDF CID fallback. RTL wraps logical lines before bidi reordering.
- Legacy display badges never contain email, phone or a bearer check-in QR. The separate
  v2 desk-badge workflow permits only its typed opaque event-bound registration credential
  QR, resolved by an authorized authenticated online scanner. Confirmation rechecks live
  authority, payload and generation through the canonical attendance writer; resolve itself
  is read-only. Rotation/cancellation/adoption invalidate old credentials; legacy UUID,
  offline roster/sync and station paths must refuse v2/inert mode. This exception permits
  no contacts, arbitrary bearer URLs, public credential resolution or badge PDFs in chat.
  GF4 confirms v2 through the canonical already-locked attendance writer; real scanner/rotation/race proof remains required. Custom-answer
  bindings retain current-form validation and require live registration-management
  authority AND tenant `VIEW_AUDIT` before reading answers. Template-edit authority
  cannot widen printing authority. Check-in-only staff may print attended rows only;
  the existing check-in result offers a single attended badge through the same path.
- `events.certificate_designer` defaults off, is parented to Events and needs only
  Events. Live `edit_details` designs and previews; issue/revoke/reissue retains full
  event management. A preview accepts a fixed sample recipient, never staff-supplied
  recipient data. Render/download paths are private/no-store, throttled and audited.
- Every certificate-design save inserts an immutable `EventCertificateTemplateRevision`.
  Issuance locks the event and copies both its revision FK and complete layout/artwork
  parameters into the immutable certificate snapshot. Pending, failed and retried
  renders use that snapshot even after edits or feature disablement. Database triggers
  enforce revision/snapshot immutability and same-event artwork/template ownership.
  Recurrence edits cancel configured old drafts instead of deleting retained designs.
- Artwork is private PNG/JPEG input, at most 10 MiB and 16 million decoded pixels.
  Ten-minute PUTs bind MIME and length to staging keys only. Server validation strips
  metadata and re-encodes PNG; conditional final-key creation promotes once. Reads
  verify SHA-256, using the frozen S3 version when available; restored versions may
  fall back to canonical bytes only with the same checksum. Final keys are never
  client writable. Object I/O runs outside row-lock transactions.
- Presigning reserves 10 MiB of managed quota transactionally with the owned row and
  audit. Signer failure rolls all three back. Successful promotion replaces the
  reservation with canonical size; failed uploads/attachments keep their reserved
  budget and purgeable keys. Transient staging bytes follow existing storage-accounting
  conventions rather than being charged twice. Purge releases artwork quota only
  after both final and staging keys are confirmed deleted.
- Design rows have no User FK or textual PII; recipient names remain on the existing
  encrypted certificate model. Revisions/artwork remain retained until module/tenant
  purge, ordered certificates -> revisions -> artwork. Purges collect both key forms
  and preserve foreign tenants. Unpromoted reservations are omitted from portable
  data and object capture. Portable import remaps artwork keys in rows AND issuance
  JSON through the object manifest, clears source bucket VersionIds and preserves
  checksums. Deployment backups preserve the complete design/snapshot metadata.

### Event websites and shared public serving (Lane C)

`events/website_visibility.py` owns the existing public event predicate (public, published,
not expired), extracted without changing the core list/detail contract. Enhanced detail,
programme, session, speaker, image, embed and share reads also require `events.website`
and the effective page's release. Only `visibility=published` children are projected;
unknown, foreign, draft, unreleased, disabled and expired website data are uniform 404s.
Core event fields and existing public-bucket covers retain their original behavior.
Directory discovery and sitemaps add public-site publication, canonical servability
and central-directory consent; direct event access does not inherit directory
consent. Tenant custom-domain sitemaps name their own canonical URLs. Event discovery
uses tenant-local date filters through `local_time.local_date_expression`, pagination 24,
and honors `show_registration_count`; the older tenant list stays an array.

`EventPage` has exactly one typed event/series owner and a matching makerspace. A series
page supplies occurrence defaults until an occurrence copies its content on write. That
snapshot and every private asset have independent identities, start unreleased, and cannot
change their owner. Typed `EventPageSection` kinds share bounded editorial fields for
speakers, tracks, rooms, sponsors, FAQs, resources, introductions and logos. Concrete session
track/room/speaker/asset FKs must remain on that page and have the appropriate kind, enforced
by SQL triggers as well as service validation. Planned session windows fit their owner and
all inheriting occurrences; owner edits refuse with typed validation, with SQL backstops.
Series -> occurrence locks serialize programme/window writes. SQL wall-time conversion
matches recurrence's ZoneInfo fold=0 at DST overlaps/gaps; duration arithmetic is elapsed UTC.
A session delay of 0–1440 minutes leaves planned times intact and shifts that session and
later published sessions in its track by the running maximum delay. Other tracks do not
move. Occurrences with differing programmes must first create their own overrides.

Page-owned metadata includes a bounded tagline, optional hex accent colour, a complete
canonical group order and group toggles (HERO, ABOUT, HIGHLIGHTS, SCHEDULE, SPEAKERS,
SPONSORS, VENUE, FAQ, RESOURCES). Legacy logo/intro sections map to HERO/ABOUT.
Disabled groups are removed by the public projection, including direct speaker/session
reads and private-image reference checks; hiding a group never deletes its editorial rows.
Speaker sections carry headline, organization and HTTP(S)-only website/LinkedIn/X links;
the existing page asset is the photo. Sponsors use the same asset as their logo and one
of platinum/gold/silver/partner/community_partner. Highlights carry icon, title and text.
Venue is one typed, bounded page JSON value with public address, finite range-checked
coordinates, HTTP(S) map link, directions, parking, transit and accessibility notes;
rooms remain sections with a maximum of 30 per page. These JSON fields contain no model
or User IDs. Clone and series copy-on-write preserve all content/layout fields while
release still resets. Older payloads that omit new page metadata or same-slug section profile/tier/icon fields
preserve saved values; explicit blanks still clear optional text.

All mutations recheck live `event_authority` under locks: sections/assets require
`edit_details`, programme/delays/release require `publish_schedule`. A read-only grant cannot
create a copy-on-write page, even with an unchanged payload. Optimistic page revisions
refuse stale saves/releases. Release requires an own page and a published owner; the event
publish action can atomically release a saved own page only with the explicit checkbox and
current revision. Every write audits identifiers/revision/counts, not content. Clone uses
the reserve/work/finalize event asset transaction, copies the effective website before optional series
attachment, and never copies release or live-delay history. This preserves valid short
occurrence overrides when attaching their draft clones to a longer series template.

Always-present `makerspaces/website_assets.py` accepts multipart uploads, never client keys
or final-key presigns. It bounds input to 5 MB, one frame and 16 megapixels before decode,
reuses byte sniffing, strips metadata and re-encodes to WebP at most 2048 pixels per edge.
New keys use `<domain>/website/<tenant>/<page>/...` in the private bucket. Staging is removed
before commit; every new key is enlisted for rollback cleanup. Replacement redirects working
section references to a fresh asset; saved revisions pin their old assets until whole-owner
removal. Only an unpinned upload or an authorized owner deletion can schedule byte deletion,
which runs only after the owning transaction commits. Only confirmed deletion frees quota.
Copy/clone validates ownership and byte-size metadata, uses fresh keys and the
shared bounded-copy limits. Public images are streamed through a live-gated backend path,
with no-store/nosniff and no object URL in JSON. Public React reads use tenant-aware blob
transport (including client headers and external API origins); staff previews use staff
transport and separate private/no-store endpoints.

Event website upload/clone keys have a durable, FK-free cleanup intent committed before
byte I/O. Its `owner_kind=event` owner ID is the venue makerspace ID. `storage_accounted`
commits with the asset and tenant counter; rollback leaves unaccounted cleanup debt which
still counts against the tenant allowance. Cleanup claims a retry in a short transaction,
deletes both staging and final keys outside row locks, and releases accounted quota once.
The reservation pass builds and validates a tentative graph in a transaction which is
rolled back; only independently committed cleanup intents survive. Its event/page primary
keys are reserved for final replay, so no partial clone or occurrence override is visible.
HEAD, PUT, COPY and staging deletion run outside every domain transaction. Final replay
reacquires the existing source/series/tenant/authority/page locks, repeats live permission,
source-gate and current quota checks, and refuses changed owner/content/relational inputs
with the existing `revision` field error. The random final key is the write claim token;
only its exact ready, unexpired receipt with zero cleanup attempts can attach. Cleanup's
attempt increment fences late writers. Repeated object work reuses verified final bytes,
and repeated receipt finalization cannot charge twice. This costs two bounded graph builds
for operations with new objects; operations with no object work commit in one transaction.
Legacy event cover copies also run outside locks. Their event-prefix cleanup receipts use
the public bucket; after attachment, the existing public-image lifecycle owns quota release,
so the completed receipt only repairs late writes and never credits quota again. Live cover
receipts are excluded before the bounded cleanup batch is selected. Bookings retains its
separate existing transaction. The HTTP contract adds no retry/idempotency token: supplied
event revision preconditions still reject stale HTTP replays, and legacy unconditioned
uploads and explicit duplicate requests retain their existing semantics.
Scheduling captures a checked `ownership_proven` receipt for imported keys before owner
deletion can remove their original import-object journal.
Completed event intents periodically repair late provider writes without a second quota
credit. Owned-row ORM deletion queues cleanup in the deletion transaction; raw lifecycle
adapters must capture the same journal before deleting rows. Unattached collection waits
24 hours and refuses assets pinned by any revision or relational section.

Account-linked speaker sections retain their row identity across content saves. Removing
one from the draft sets `is_working=false`; it is absent from working projection, new
snapshots, clones and new speaker-link choices, while `EventSpeaker.section` remains intact.
Speaker history uses linked sessions in the selected released snapshot with its frozen
series anchor, retaining the event-start fallback and account-only credit rules.

Curated website text and image descriptions are intentional publication data, like event
titles/descriptions, not private contact/answer fields or new scoped-PII sources. Editorial,
asset and session rows have no User FKs or credentials; revision creators use nullable
`SET_NULL` attribution, never authority. The models have explicit export datasets, field/reference
and unique dispositions, retained object ownership, private-key collectors, quota
reconciliation and module/tenant purge coverage. Portable content travels with remapped
FKs and verified object-journal keys, but release and framing origins reset to false/empty.
An imported asset's typed page row plus its verified same-tenant object journal prove
ownership even after collision-driven key regeneration and a second migration. Deployment
backup retains the original content/release graph. Retention remains registered under
Events tombstoning; the runtime adapter and public surfaces disappear. Deleted page audit
targets remain inert source provenance.

`makerspaces/website_visibility.py`, `website_directory.py`, `website_serving.py` and
`website_views.py` are domain-neutral infrastructure. Typed adapters own public resolution,
query predicates, cards and effective-page release; bookings supplies its adapter without
importing events or inheriting event expiry. Restricted Markdown is rendered by React with
no HTML parser and only HTTP(S) links. Share HTML uses escaped core fields and the existing
public cover, is noindex, and caches content server-side for 600 seconds only after a live
gate on every request; HTTP revalidation prevents unrelease/module changes reviving stale
HTML. Cache identities include subject, tenant and release revision.

Every supported SPA serving config denies framing, including nginx's index fallback.
`/embed/` is proxied to Django, which alone emits the exact `frame-ancestors` policy and
exempts its response from X-Frame-Options. `website_embed_origins` is a separate framing
allow-list (at most 20 canonical exact HTTPS origins; no paths, credentials or wildcards),
never a CORS/staff-origin grant. Empty or invalid stored policy refuses embeds. Only tenant
`MANAGE_MAKERSPACE` may edit it. New proxy locations forward the real client chain so
public throttles do not collapse all visitors into the frontend container's address.

### Event communications and subject reports (Lane D)

`integrations/broadcasts_models.py`, `broadcasts_registry.py`, `broadcasts_worker.py`
and `broadcasts_delivery.py` are always-present shared infrastructure. Domain adapters
own typed campaign/recipient models, resource authority and selection. Events uses
`EventBroadcast` and `EventBroadcastDelivery`; bookings must not import events to reuse
the engine. Campaigns require the domain feature plus notifications and email. Queueing
is serialized by the tenant lock and limited to ten campaigns per hour per makerspace.
The worker batches at 200 accounts, deduplicates by account, and creates each delivery
and its unique outbox relation in one transaction. The existing reminder task recovers
unfinished batches and enqueue failures through per-tenant source-gate boundaries.
This guarantees durable enqueue identity, not exactly-once SMTP acceptance.

Campaign email passes through `integrations/delivery_sources.py` inside `dispatch_delivery`;
selected non-email legs use `events/broadcast_channels.py` personal envelopes, with email pre-skipped.
The durable campaign worker reserves these envelopes in the same transaction as its
recipient cursor, including accounts without verified email. A failed reservation rolls
back the batch; `resume_broadcasts` recovers initial enqueue loss and lost continuation
batches, while the personal outbox sweeper recovers envelope dispatch. On the email path:
immediate, quiet-hours release and retry all reload campaign state, the original sender's
current resource authority and live recipient eligibility. Unknown/tombstoned sources
fail closed. Event recipients need matching registration status/attendance, a verified,
valid account email, active account and any existing membership, notification consent,
matrix, suppression and module/feature gates. Cancellation stops unclaimed sends;
already accepted provider sends cannot be recalled. Templates render data-only bounded
placeholders at send time through the existing email renderer. Ticket URLs navigate to
the authenticated member ticket page; they contain no check-in/admission credential.
Audit records contain state/counts and identifiers, never message bodies or recipient lists.

Campaign sources are excluded when assigning digests AND while collecting digest inputs.
Digest summaries retain input outbox IDs; `delivery_digest.py` rebuilds them by rechecking
each registered source before delivery and every retry, dropping stale entries and skipping
empty summaries. Booking reminder adapters supply durable booking/window/revision/offset
identity via personal envelope source fields; retained legacy email rows use their registered
EmailDelivery/dispatch_email predicate. No generic worker imports a separable domain to implement
these checks.

Bulk event invitations accept at most 200 validated addresses per call and reuse
`create_invite`. Emails contain only an event navigation link. Verified-email resolution
and bound-code redemption use the existing locked resolver; invite-only registration
without a code now uses that resolver and explains missing verification. Organization
audience membership remains an additional admission requirement. No credential enters
an outbox body, template context, log or export.

`operations/report_subjects.py` validates paired `subject_kind`/`subject_id` through typed
domain adapters and resolves the subject inside the selected tenant. Event-scoped
attendance, registration/feedback preview, CSV/XLSX download and saved views require
manage_registrations authority AND tenant VIEW_AUDIT. PDFs require full event management
(tenant/organizer, no scoped grant) and an ended event. New detail/PDF definitions are
unschedulable, non-deployment-aggregate and explicitly excluded from organization reports.
Subject filters are refused on ALL schedules and aggregate paths, including legacy keys.
Unfiltered legacy report permissions and calculation semantics remain intact. Saved views
recheck reader and owner authority against their exact subject. PII previews/downloads
audit; export provenance includes subject identity and tenant-local date bounds. Report
registry PDF dispatch uses the same builder rows, provenance and render throttle as other
formats. Feedback text uses the scoped-PII model accessor; exports never carry ticket tokens.

Campaign subject/body use scoped secondary PII encryption and the DB write fence. Both
concrete history models are tenant export datasets with explicit User closure. Portable
import cancels nonterminal campaigns, clears delivery outbox links/cursors, and skips
pending deliveries; terminal history survives. The source outbox and digest references
are omitted telemetry. Events-only purge removes event campaigns and event-source outboxes,
preserving other domains; whole-tenant purge removes all. These models own no S3 objects;
manual PDF bytes are streamed, never stored. Retention/encryption/purge declarations survive
tombstoning while adapters, feature rows and report definitions disappear.

### Booking public resource websites (BK-F)

`bookings/website_visibility.py` owns the active/public resource predicate extracted
unchanged from `views_public`. New core detail keeps existing direct visibility without
adding central-directory consent. `bookings.website` and explicit page release additionally
gate enhanced detail, images, embeds and share HTML. Only published sections and their
referenced images are public. Private, inactive, foreign, disabled and unreleased enhanced
content returns indistinguishable 404s. Public detail returns core fields and null website
when the feature is off/unreleased; the legacy catalogue remains an array. Availability
and booker-name flags keep their existing separate behavior. Approved public flat price,
currency and duration/lead/horizon/cancellation summaries never expose internal buffers,
machine links, notes, answers, contacts or reservation identities.

`BookingResourcePage` belongs to one resource; its tenant is derived from that typed FK.
Bounded rules/amenity/FAQ/link/sponsor/gallery sections and assets have immutable page
ownership, with SQL guards for cross-page asset references and reparenting. Editorial
text is deliberate publication data, not a new private-contact source; there are no User
FKs or new scoped-PII/JSON fields. Restricted Markdown uses the shared React renderer with
escaped HTML and HTTP(S)-only links. New features default off and are Bookings-parented.

Content and private image changes require live `edit_details`; release/unrelease requires
`publish_page`. Services acquire the source gate, resource and tenant/authority locks,
then check revision and permission again. Publishing cannot make a resource public or
active. Private previews are authorized no-store endpoints; public image IDs never grant
draft access. Saves, release and image changes advance page revision and audit only that
revision. Asset upload accepts no object keys, uses shared bounded staging/sniff/WebP/quota
and rollback cleanup, and stores `bookings/website/<tenant>/<page>/...` privately.
Replacement remaps section references to fresh keys and releases quota only after confirmed
post-commit deletion. Cloning copies the page/sections/assets inside the existing durable
clone transaction with independent keys and reset release; no authority/history is copied.

The Bookings adapter consumes always-present makerspaces visibility, assets, directory,
embed/share and clone mechanisms; it imports no Events services and has no event expiry
rule. Discover/sitemap add public-site and directory consent. Custom-domain sitemaps use
verified canonical resource URLs. Shared embeds require feature/release and a nonempty
exact HTTPS framing policy, and use “Book a time”; nginx/Caddy retain default SPA framing
denial through index fallback. Crawler routes use the existing public cover and shared
escaped, noindex HTML. Live visibility checks precede cache reads; identity includes tenant,
resource update and page release revision, so unrelease/visibility/module changes cannot
revive cached content. Public analytics continues to use route templates, with private
and credential routes excluded.

All three concrete models have literal export fields, datasets, reference/unique policies,
object ownership and retention registrations independent of runtime tombstoning. Portable
import resets page release; typed imported asset metadata plus the same-tenant verified
object journal proves ownership when keys retain source IDs. Deleted page audit targets
remain inert source provenance. Module purge cascades page rows from `BookableSpace` and
collects private keys/sizes; whole-tenant purge, storage reconciliation and backup/migration
capture include gallery objects. The core payment ledger remains outside module purge.

### Booking clone, edits and cancellation undo (BK-B)

`bookings.clone` and `bookings.staff_tools` are opt-in Bookings features with no
Events dependency. Cloning requires tenant `MANAGE_BOOKINGS`, copies declared
configuration into an active private resource with a fresh UUID and owned cover key,
and never copies reservations, grants, feeds, payments or delivery/arrival history.
Rules use model defaults unless explicitly copied by a `MANAGE_MAKERSPACE` actor;
machine links revalidate installed modules and tenant ownership. The shared durable
clone transaction accounts storage and cleans failed copies. Query-free extensions
in always-present makerspaces infrastructure let website adapters copy their children
inside that transaction; a copied website must remain unreleased.

Reservation note/answer and time edits require live `manage_reservations` authority
and run under source/write fences and resource then booking locks. Inputs are strict
allow-lists; answer edits validate the current schema into the existing private
snapshot format, and audit only changed field names. Time edits permit only pending
or confirmed rows whose old start is strictly beyond the current cutoff; the proposed
start must also be strictly beyond it, using one server-clock snapshot. Shared
`bookings/admission.py` checks active resource/owner, optional-membership waiver,
certification, duration, lead/horizon, opening hours and buffers. Moves check conflicts,
retain status/identity/flat charge and increment the calendar revision. Approval
intentionally retains its established narrower policy. Active-arrival refusal runs in this same locked movement boundary; the model save
guard rotates the credential atomically with the calendar change using the captured
server clock. Detail edits also refuse arrived and terminal reservations.

Cancellation records nullable `cancelled_at` and `status_before_cancel` in the same
atomic transaction as calendar changes, audit and required pending-debt cancellation.
Legacy null provenance refuses undo. Undo requires current cancelled state, prior
pending/confirmed, and `cancelled_at <= now < cancelled_at + five minutes`. Any
historical payment row or newly required charge refuses it. Ordinary current admission
must yield exactly the prior state; previously approved confirmations cannot bypass
an approval policy. Pending restores occupy no window, matching creation. Restore
preserves creation time/identity, clears cancellation provenance, increments calendar
revision, audits `booking.restored` and schedules `restored` after commit through the
normal registered requester/staff templates and preference/module gates. Refusal or
rollback emits no restored event. These scalar provenance fields travel with the
existing booking dataset; they add no User edges, PII mapping or object ownership.
Existing booking module/tenant purge and owned-image collection cover clones, while
the core payment ledger remains retained. Target undo still needs live authority,
current admission and its server clock; portable provenance is never permission.

### Booking resource analytics and exports (BK-E)

Booking reports extend the always-present report registry and subject/PDF infrastructure;
no booking code imports separable events. `subject_kind="bookable_space"` resolves the
resource inside the selected tenant before a builder runs. New analytics, reservations
and answer previews/downloads/saved views require live tenant `MANAGE_BOOKINGS` or that
resource's `manage_reservations` grant, AND tenant `VIEW_AUDIT`. PDFs require full tenant
booking management plus audit and a complete positive date period. Rules/price/payment
permissions, scanners and descriptive editors convey no report authority. Saved views
reauthorize their owner and reader on every replay; sharing never grants access.

`bookings.analytics`, `bookings.utilization_pdf` (also needs analytics) and
`bookings.exports` are opt-in Bookings children requiring Reports, discovered by the
installer without installing Reports implicitly. All four new definitions are
unschedulable, non-deployment-aggregate and explicit organization exclusions. Subject
filters are refused on every scheduling/deployment/organization path, including legacy
`booking-utilization`. The unfiltered legacy report retains its permissions and metrics.

Resource analytics applies the resource predicate BEFORE the existing utilisation
aggregation. Confirmed/completed/no-show reserved intervals clip to the requested window;
the denominator is the whole calendar window, never opening hours or measured use.
Utilisation is null without both bounds. Dates are inclusive tenant-local calendar labels
converted by `local_day_bounds` to UTC half-open bounds; exports stamp those instants,
subject and tenant timezone in provenance. Reservation/answer details select overlapping
booking windows (not creation dates), retain original booking timestamps and use explicit
column lists. PII reads use model attributes and eager tenant paths, never raw values or
ciphertext. Custom-answer snapshots preserve their stored labels. No notes, payment data,
public booking UUIDs, feed/check-in credentials or arbitrary model fields are exported.
Previews/downloads audit through the source write fence; subject responses are private,
no-store. CSV/XLSX keep the shared formula protection and export renders are throttled.

`reports_booking_resources.extend_with_booking_arrival_counts` is the named BK-C hook.
It now calls `bookings.arrival_projection.arrival_metrics` over the same tenant, resource
and half-open reservation-overlap predicate, sets `arrival_counts_available=True`, and
adds `arrived_reservations` and `confirmed_without_recorded_arrival` to resource rows and
CSV/XLSX/PDF columns (report version 2). Reversals clear the current arrival; completion
alone never implies one. The resource UI labels these counts separately from reservation
hours. Legacy tenant utilisation retains its existing fields and calculations. The shared PDF renderer embeds a Unicode
font (bundled Apache-licensed Roboto through the shared, domain-independent font
helper), rather than silently dropping Greek glyphs from bundled Vera. This keeps
Latin, Greek and Cyrillic coverage independent of the host's installed fonts.

This lane creates no persistent models/fields, stored report objects or new routes.
Existing SavedView import projection resets state/sharing, so source subject IDs cannot
replay in another tenant. Existing tenant/module purge, classification, User closure,
encryption and object ownership remain sufficient; the model catalog hash is unchanged.
Tombstoning Bookings removes its subject adapter, report definitions and feature keys;
tombstoning events does not affect booking reports.

### Booker communications and occurrence reminders (BK-D)

`bookings/broadcasts.py` is a thin typed adapter over the always-present
`integrations/broadcasts_*` engine. `BookingBroadcast` targets exactly one resource
and its tenant, a future start window ending within 366 days, and pending/confirmed
states (confirmed by default). Selection excludes started and contact-only bookings,
deduplicates by account and uses the current verified account email, never copied
`Booking.email`. Compose/queue/cancel and every send require live `manage_reservations`
through `booking_authority`, `bookings.broadcasts`, Notifications and Email, plus a
servable tenant. Ten queues/hour/tenant are serialized by its row lock;
API calls additionally have a per-user throttle. Sender revocation and matching booking
loss stop unclaimed sends on immediate, quiet-hours and retry paths. Render-time loss
also skips safely. The batch worker reserves saved bookings-category choices through
`broadcasts_personal.py` envelopes instead of the email leg, in the same transaction as
the recipient cursor. Reservation failures roll back that batch for recovery. No campaign body
enters a staff room. Personal envelopes use the shared timing policy.

`communication_recipients.py` preserves current account standing, optional membership
status/notification consent, requester selection, matrix, personal preferences and
suppression. Account-owned booking reminders do not require the Membership module.
Email-only eligibility gates do not suppress independently enabled requester inbox delivery.
`reminders.py` now emits `bookings.reminder` personal envelopes through `reminder_envelopes.py`;
`notification_sources.py` owns their live revision/owner/toggle check. The legacy email adapter
`reminder_delivery.py` retains source `bookings.booking`: tenant/resource/booking/
recipient IDs, exact UTC start/end, calendar sequence, reminder kind and offset are
stored on the outbox. The claim subject includes the occurrence window and revision;
an old revision's completed claim cannot suppress a moved or restored occurrence.
Legacy claims still prevent duplicate/uncertain sends for the same start on upgrade,
including bookings whose calendar sequence already advanced through approval. Delivery reloads
that exact source and requires confirmed status, a future start, current offset and
effective requester toggle. The shared digest retains input outbox IDs and rebuilds
at inclusion, delivery and every retry; stale entries are dropped, empty summaries
skip. Legacy source-less booking reminders fail closed even when Bookings is tombstoned.
No note, answer or credential belongs in source metadata or a template placeholder.

Campaign subject/body use scoped secondary PII encryption and the persistent DB write
fence. Concrete campaign/delivery datasets include both tenant and typed resource closure,
with explicit created_by/recipient User edges. Import cancels nonterminal campaigns,
zeros cursors, marks recipients complete, clears outbox links and skips pending delivery
history. Audit targets remap through the exported-model catalog; count-only metadata
has no new reference edges. Outbox/source/digest references are omitted telemetry.
Bookings-only purge removes booking campaigns and booking-source outboxes, retaining
other domains and letting shared summaries rebuild survivors; whole-tenant purge removes
all. No S3 objects are created, so object/storage/backup ownership registries need no
new keys. Retention declarations remain present under tombstoning; runtime adapters and
the opt-in capability disappear. Restored lifecycle notifications remain BK-B's concern.

### Booking resource staff grants (BK-A)

`bookings/booking_authority.py` owns every booking staff predicate, including locked
service mutations. Tenant `MANAGE_BOOKINGS` retains local fixed-role-set and organization
action authority. A resource grant adds only its typed `BookableSpace`: `edit_details`
allows name/kind/description/capacity/location/form and images; `manage_reservations`
allows roster, purpose-limited member selection, ordinary on-behalf creation/recurrence
and lifecycle transitions. `check_in` and `publish_page` reserve their separate scanner
and page-release boundaries for their owning lanes; neither admits roster or contact data.
No grant conveys rules (`MANAGE_MAKERSPACE`), pricing, machine links/certification
overrides, activation, public/name policy, payment controls, cloning or delegation.
Staff creation retains active local membership/current waiver and ordinary booking rules;
account-only self-booking remains independent of membership. Grant-only rosters have no
payment summary; finance actions retain existing tenant finance/payment permissions.

`bookings.staff_grants` is opt-in, parented on Bookings, with no events dependency. Live
queries recheck account standing, module/feature, canonical servability, target ownership
and revocation. Origin target registration applies to every new route.
The shared source registry projects `source="booking_grant"` with resource permissions,
never tenant actions; sign-in/refresh/MFA discover it without importing events. Mixed
assignments share the narrow workspace. Revocation is effective on the next request and
before a locked mutation. Always-present `resource_grant_locks.py` stabilizes delegation
against local roles, accounts and organization authority, shared by events and bookings.

Concrete `BookingSpaceStaffGrant` and `BookingSpaceStaffGrantInvite` use the shared
seven-day HMAC-only invitation lifecycle and typed resource FKs. Only tenant
`MANAGE_BOOKINGS` creates, updates or revokes; redemption revalidates the sender's live
authority, permission subset and matching verified email under resource/tenant/invite
locks. No grantee can delegate. State changes audit `booking.staff_grant_*` without
credentials or contacts. Raw invitation tokens appear once or in synchronous redacted
email fragment links; no persisted outbox body or query cache contains them.

Both entire models are omitted at both export fidelities and DROP on portable import.
They have no datasets or unique-value materialization. All five User edges are excluded
from archive closure; audit targets retain inert source provenance. These rows contain
only keyed email digests and account FKs, no new PII fields or S3 objects: no encryption,
write-fence mapping or object collector is needed. Module purge explicitly deletes both
credential tables in that tenant; whole-tenant purge cascades them. Retention registration
survives tombstoning; runtime discovery/routes/features do not. Source migration gates
apply before grant mutations. The catalog pin includes both concrete model graphs.

### Booking printable passes (BK-G)

`bookings.passes` defaults off, belongs to Bookings and requires
`bookings.confirmations`; it has no Events, Membership, Presence or payment-rail
dependency. Owners may download confirmed/completed passes through their existing
private account-owned confirmation scope. Claim sessions are explicitly refused.
Staff printing requires live resource `check_in`, the check-in feature, a
confirmed/completed booking and a current active arrival. Neither `edit_details`
nor reservation-management alone grants scanner printing. Resource -> booking locks
serialize the final arrival check and render/audit with arrival reversal and lifecycle
changes. A completed arrival may print until explicitly reversed.

Every save, template read, preview and actual render validates the same fixed field
bindings: display name, resource, tenant-local booking window and optional numeric
booking reference. Unknown/legacy custom-answer, note, contact, QR, public-token,
arbitrary-text and artwork bindings refuse; no sensitive binding is silently removed.
Only these four projected strings cross into the shared PDF renderer. Template editors
can preview only fixed fictional values, never select another person's booking.
All booking passes use this answer-free policy, regardless of additional roster/export
authority. Actual PDFs are regenerated after authorization, never cached or shared with
sample previews or confirmation PNGs. Public booking/check-in identities never print.

The existing always-present `operations/printable_*` utilities own grid geometry,
Unicode/RTL/fallback fonts and overflow refusal. Layout is bounded version-2 JSON on
`BookableSpace.pass_template`, copied independently on ordinary resource cloning.
It contains no PII, User FK, object key or live embedded reference: the existing tenant
resource dataset and purge paths cover it, both export fidelities emit it, and portable
import preserves configuration subject to target feature/authority gates and render
validation. No encryption registration or object collector is needed, and no PDF or
artwork is persisted. The schema graph pin includes the new field and the integrated
Lane E/BK-C models. Uninstall retains layouts; module/tenant purge deletes them with
their resource, preserving other tenants and the core ledger. Template writes, previews
and downloads audit identifiers only. All pass routes are private/no-store/no-referrer
including pre-dispatch failures; renders are limited to 30/hour/account.

### Booking confirmations and QR arrival (BK-C)

`bookings.confirmations` and `bookings.checkin` are opt-in Bookings-parented features;
check-in additionally requires confirmations. Owned detail, QR PNG, rotation and one-booking
ICS use the existing account-owned booking predicate without requiring membership, events,
presence or the payment rail. Existing revoked-member and account restrictions still apply.
Submission returns the noncredential booking UUID and confirmation availability; the
honeypot response remains status-only and creates nothing. Account-less claim sessions
are explicitly refused on these durable credential/download routes. Every private success/error is
no-store/no-referrer. PNG/ICS downloads and credential rotation audit without private content.
`calendar_render.booking_calendar` serializes both feed and single downloads with stable UID,
calendar revision, and CANCELLED/TENTATIVE/CONFIRMED state. Calendar links contain only public
resource title/location and selected times. PNGs contain resource/window/status and the QR,
never contacts, notes or custom answers. No PNG is persisted or reused as a printable pass.

Booking QR credentials are independent random UUIDs prefixed `spaceworks-booking:`; neither
public booking identity nor calendar tokens are accepted. Scanner requests carry credentials
only in POST bodies. `check_in` authority is checked on the selected resource for read-only
resolve and again under resource -> booking locks for arrival/reversal. Malformed, unknown and
foreign-resource credentials have uniform 404 responses. Scanner projections are answer-free:
display name, resource, window/status, current arrival and advisory waiver state. Scanner-only
users cannot open the roster, contacts, answers, notes or payment summary. Camera capture and
manual entry require explicit resolve and confirmation; no station/offline/door path exists.

Only confirmed reservations on active resources may arrive, inclusively from 30 minutes
before start through end. Duplicate arrival is idempotent only while still eligible. Arrival
never changes occupancy, completion, payment, presence or physical access. Cancellation,
member/staff time edits and no-show require an explicit reversal first; no-show additionally
requires confirmed and ended. Completion after end is valid with or without QR arrival and
retains an existing arrival. Authorized reversal after completion clears only arrival, never
reopens the booking. Pending and all terminal states refuse new/reinstated arrival.
`services_arrival_policy.prepare_booking_save` protects ordinary service saves, including
BK-B staff edits and exact undo, under their existing locks: terminal/started/old-cutoff and
new-cutoff time edits refuse; moving/cancelling/restoring atomically rotates the old QR.
Member rescheduling uses one clock snapshot for old/new cutoff checks and current account /
optional-membership waiver eligibility. BK-B retains ownership of full staff-edit admission,
cancellation provenance and restore notification policy; it can set `_arrival_clock` to its
already-captured server time before saving. Queryset updates are not workflow entry points.

`BookingCheckInEvent` is append-only at ORM and PostgreSQL boundaries; corrections append
`reversed` facts and change only `Booking.arrived_at`. Every mutation audits IDs/actions,
never credentials. Shared log redaction removes prefixed QR payloads. History is an explicitly
tenant-filtered portable dataset, its actor joins the reviewed User closure, and subject export
follows the booking owner. The credential is omitted at both fidelities and regenerated on
import; arrival/history remain historical facts. No new free-text PII, encrypted column or
stored object is introduced; the existing booking name accessor and encryption fence apply.
Bookings/module and whole-tenant purge explicitly remove immutable history before its
PROTECTed booking, using their existing authorized immutable-delete context. Retention
registries remain present when bookings is tombstoned. BK-E calls
`bookings.arrival_projection.arrival_metrics(queryset)` with its already-authorized tenant,
resource and date predicate. It returns `arrived_reservations` and
`confirmed_without_recorded_arrival`; these counts never imply measured-use duration or
replace calendar reservation utilisation.

### Event-scoped staff grants

`events/event_authority.py` is the staff event authority API: tenant `MANAGE_EVENTS`,
unchanged organization organizer authority, relevant series authority and live scoped grants.
`edit_details`, `manage_registrations`, `manage_invitations`, `check_in` and
`publish_schedule` confer only their event operations. A grant never adds makerspace RBAC
actions or widens `scope_by_makerspace`; list predicates admit only its event or series
occurrences. Grant management, station PINs, collaboration, payments, deletion,
certificate issue/revoke and analytics PDFs remain tenant/organizer operations.

Concrete `EventStaffGrant` and `EventStaffGrantInvite` rows belong to events and use typed
event/series FKs, exactly one target, and partial uniqueness for live grants. The abstract
fields and locked create/redeem/update/revoke mechanism live in always-present
`makerspaces/resource_grants_models.py` and `resource_grants_services.py`, parameterized
by a domain adapter. Bookings can supply its own concrete models without importing events.
Permission validation, HMAC-only token/contact digests and seven-day expiry are shared.
Redemption locks the resource and invite, rechecks single use, expiry, revocation, resource
servability, the creator's current management authority and non-escalation, and requires a
matching verified account email for bound invitations. Raw tokens are returned once and
may appear only in synchronous redacted invitation email links, never persisted outbox
bodies, list responses or audit metadata. Every mutation records `event.staff_grant_*`.

Account staff sign-in/refresh, workspace discovery and staff MFA consult the query-free
`makerspaces/resource_grant_sources.py` registry, never events directly. An active app
registers its source in `AppConfig.ready()`; a tombstoned app contributes no authority.
Queries recheck grants on every request, including tenant/module and staff-origin scope.
Granted events are projected with `source="event_grant"` and their permissions; no
makerspace actions are manufactured. Organizer authority is unchanged.

Both entire models are omitted at **both export fidelities** and `DROP` in tenant imports.
They have no export datasets or target uniqueness materialization: a target must reissue
all delegated authority and credentials. Their User FKs are explicitly excluded from user
closure, and retained audit targets become inert source provenance. Email is never stored
in these rows, only a deployment-local keyed digest, so they need no PII encryption mapping
or S3 collector. Events module purge and whole-tenant purge delete both concrete models;
retention registration survives tombstoning even though discovery and routes disappear.

### Participating-organizations audience (Lane G)

`participating_organizations` requires `events.organization_audience` (Events parent,
default off); it needs neither membership installation nor account-registration features.
The live candidate set is the event's selected audience organizations
(`EventAudienceOrganization`, single events only) plus its organizer organizations plus its
venue's OWNER organization. Manager/affiliate links and accepted collaborators add no organization.
Active direct organization members qualify regardless of action grants; active members
of the candidates' OWNER-linked spaces also qualify. Accounts must be persisted, active,
unrestricted and non-stub. Organizations must be active; public-profile consent is not
eligibility. Both venue and contributing spaces use canonical servability. No membership or RBAC
identity is created. The venue remains the PII, audit, money and routing anchor.

`organizations/audience.py` is the reusable, always-present batched membership predicate.
The events adapter `organization_audience.py` fences event -> all discovered makerspaces
(sorted PK) -> organizations -> accounts (NO KEY UPDATE) -> links -> memberships, then
rechecks the proof. Ownership changing during root discovery refuses with a retryable
409 rather than acquiring an out-of-order root. Organization console and standalone
admin owner-link mutations route through `services_console.change_link`; the inline
under Organization is read-only to avoid parent-first owner writes. Series organizer
projection/removal locks all affected occurrences before the makerspace root.

Registration, re-registration, approval, automatic/manual promotion and cancellation undo
all apply the live predicate under the event lock. Automatic FIFO skips ineligible rows
without changing their queue, quote or debt; explicit operations refuse atomically.
Optional code/email invites require the invite feature and cannot substitute for membership.
Bound codes and email resolution require verified email, and failed admission consumes
no invite/promo. Public/staff/partner registration share host-waiver checking/stamping:
current explicit self-consent or already-recorded current consent is required. Staff cannot
assert another person's acceptance. Partner membership, collaboration, waiver and module
requirements remain additional requirements, with no presence-session dependency.

Public projections expose only usable organization IDs/names and the audience label.
The separate authenticated eligibility advisory is private/no-store, varies on authorization
and cookie, and carries no membership/proof identity. The staff roster's batched live
`no_longer_eligible` flag is advisory; eligibility loss never cancels a ticket. Saved admission
provenance permits exact-owner QR, PNG, one-registration ICS and cancellation after loss,
subject to existing account/local-membership, tenant/module and recorded-waiver safeguards.
It never grants membership history. Audience writes recheck `edit_details` under locks and
audit old/new audiences and organization IDs, never membership lists.

Event/series `organization_admission_blocked` is exported data but RESET to true during
portable import. Global organizations, memberships and organizer bridges remain excluded;
an unrelated target venue owner cannot make an imported audience ready. Only explicit
staff audience reconfiguration clears the block; generated occurrences and clones inherit
it. Deployment backup preserves the original graph/marker. These booleans add no PII,
User edge or object ownership. Existing event datasets and local purge predicates retain
responsibility; local purges never delete shared global organizations or foreign organizers.

### Organizers, partners and audience organizations (int-events, 2026-10-16)

- **Audience is not authority.** `EventAudienceOrganization(event, organization, added_by,
  created_at)` admits an organization's members to a `participating_organizations` event and
  nothing else: no `event_authority`, `organizer_authority` or `staff_grant_locks` path reads
  it. An organization that should co-manage an event is an ORGANIZER (`EventOrganizer`),
  which grants its `MANAGE_EVENTS` members management of that one event.
- **Organizers stay limited to the actor's own organizations** (active membership in every
  newly assigned one; superadmin exempt) -- deliberately no consent/invitation flow for
  external organizers, because attaching an organization as an organizer hands its event
  managers authority over this event. Other organizations are added as AUDIENCE instead.
- **`candidate_ids` is a union for back-compat**: audience rows + organizers + venue owner.
  Events that chose this audience before audience rows existed keep exactly their audience;
  series and occurrences have no audience rows and keep the organizer/owner set. Audience
  writers hold the event lock first (`_locked_event`), the same order as organizer writers,
  so the admission fence sees the old or the new set, never half. Writes need `edit_details`
  (rechecked after `lock_authority`), refuse terminal events with 409, audit
  `event.audience_organizations_updated` with old/new IDs only, and are a no-op (no audit)
  when the set is unchanged.
- **Discoverability is opt-in.** `Organization.is_discoverable` defaults to False for new
  AND existing organizations; only `manage_organization_profile` governance toggles it
  (profile PATCH, audited as `organization.profile_updated`). The staff directory
  (`GET admin/organizations/directory/`) returns active organizations that are discoverable
  or that the actor actively belongs to (superadmin: all active). A NEWLY added audience
  organization must pass that same predicate server-side; an already-listed one may stay
  after it stops being discoverable. The route lives in the events app so a tombstoned
  `events` takes its only consumer's directory with it.
- **Partner makerspaces are picked, not typed.** `GET admin/event-partner-makerspaces/`
  returns servable spaces with the `events` module that are in the central public directory
  (`public_site_enabled` and not `hidden_from_central_directory`) plus spaces the actor holds
  `MANAGE_EVENTS` in -- nothing the public site does not already list. Invitation and
  accept/decline consent are unchanged.
- Both directories need an actor who runs events somewhere (tenant `MANAGE_EVENTS` or an
  organization membership granting it; superadmin), are paginated at 24 and throttled
  per user (`event_directory_search`, 120/min). They are global routes, so a custom staff
  origin refuses them like every other unscoped admin route.
- **Create applies everything in one transaction.** `create_event` takes optional
  `organization_ids`, `audience_organization_ids` and `collaborator_slugs` (create-only
  `EventCreateSerializer`; PATCH still refuses them) and calls `replace_organizers`,
  `replace_audience_organizations` and `invite_collaborators` inside its atomic block, so any
  refusal creates no event. It locks the host AND every partner space up front in PK order:
  the new event is invisible to everyone else, so taking spaces before it cannot deadlock,
  whereas acquiring a partner after the host could deadlock against a reciprocal create.
- Retention: `EventAudienceOrganization` is OMITTED from tenant exports (it references a
  deployment-global organization) and so `DROP` in tenant imports; its `added_by` is a
  declared User edge; whole-tenant purge deletes it with organizer rows; events module purge
  and event deletion cascade it.

### Check-in list and staff role labels (int-events, 2026-10-16)

- `GET admin/events/<pk>/check-ins/` needs only the `check_in` event permission, so a door
  volunteer or speaker grantee can see who arrived beside the scanner. It lists ATTENDED
  registrations (a corrected attendance leaves the list) with the latest
  `EventCheckInEvent` per registration (served by `event_checkin_history_idx`), newest first,
  paginated at 24. The projection is minimal on purpose: attendee name, ticket type name,
  `attended_at`, source (`qr`/`manual`/`offline`/`station`/`legacy`) and the checking
  actor's display name -- never email, phone, payment or custom answers.
- `EventStaffGrant.role_label` / `EventStaffGrantInvite.role_label` (`speaker`,
  `volunteer`, `check_in`, or blank) are DISPLAY ONLY. Permissions alone decide authority.
  The shared resource-grant lifecycle carries it through `GrantAdapter.label_field`
  (bookings passes none): invites store it, redemption copies it to a new grant and only
  fills a blank label on a merged one, PATCH changes it only when sent, and audit metadata
  includes it only when non-blank. The "Speaker" preset in the console is `check_in` only.

### Event access, ticketing and discovery (WP1, 2026-10-11)

- **Lane B staff tools (2026-10-15).** Duplication requires live `edit_details` authority,
  creates a fresh draft identity, defaults to standalone, and never copies registrations,
  credentials or grants. Optional series attachment requires management of that series.
  The explicit adapter copies only declared children and fresh owned asset keys; durable
  outer transactions roll back quota and clean failed copies. Shared helpers in makerspaces
  and operations never import events, so bookings can reuse the mechanisms.
- **Cancellation undo restores state, not money.** Cancellation records server-clock
  provenance; legacy null provenance refuses undo. Within five minutes, event and ticket
  locks serialize exact restore with registration and promotion. Any historical charge,
  invite/promo consumption or newly required charge refuses it. Confirmed/approval restore
  uses the registration admission helper; waitlist restore preserves its queue position,
  except a later-created waiter's intervening promotion moves it to the tail. Creation time
  remains intact. Refusals mutate nothing; restore audits and dispatches `registration_restored`.
- **Ticket PNGs are owner-only, registered/attended-only, no-store, throttled and audited.**
  Calendar formatting receives only authorized public fields. Public projections honor
  `show_registration_count`, including suppressing exact ticket spots when counts are hidden.

- **Events no longer requires membership.** `members` remains the default audience. `accounts`
  requires `events.account_registration` and `require_active_account`; `invite` requires
  `events.invites`, that same account guard, and a usable event-bound invite. Guest/no-account signup
  remains deferred. Collaborating-space registration still uses `require_active_member` there.
- **No membership is created by event registration.** Staff on-behalf registration names a real
  account or existing walk-in. QR reads and member cancellation may use the caller's own
  account/invite registration; that grants no other member history or tenant authority.
  The registration preserves its admission audience so event/series edits cannot revoke an existing ticket.
- **Codes are credentials, never audit content.** Invites and promo codes use deployment-keyed
  digests. Optional invite email is a keyed digest too. Expiry, revocation, email binding and limits
  are checked under the event lock; invalid/expired/foreign/exhausted codes return the same 404.
  The registration throttle bounds redemption. Duplicate retries spend no additional use.
  Codes are shown once to authorized staff, never in subsequent list responses or public payloads.
- **Ticket eligibility degrades to public types.** Membership off or no active membership hides and
  refuses member types. Event capacity and ticket capacity both apply, with 0 meaning unlimited.
  FIFO promotion skips a full type while considering eligible waiters for other types. Sales windows
  gate new sales, not an already accepted waitlisted quote.
- **The registration freezes its quote and discount.** New registrations reserve invite/promo uses
  only in the successful attachment transaction; this includes approval and waitlist rows. Cancellation
  does not restore a use. Per-redemption audit records IDs and discount amount, never code or email.
  Charges are raised at REGISTERED through the existing record-first seam; no online rail is required,
  and offline settlement still requires an append-only ManualSettlement. Local ledger creation failure
  rolls back admission and code use; optional provider failures preserve the recorded debt. Legacy null quotes retain
  the previous flat-price behavior. Paid cancellation re-registration stays refused.
- **Ticket templates are copied, not shared.** Series creation copies its template rows into each
  occurrence; per-type occupancy belongs to that occurrence. Editing one copy cannot change others.
- **Discovery is public-only.** Categories and tags are tenant-scoped. Detail reuses the public
  serializer; private, terminal and unknown events are indistinguishable 404s. Module-off is 400.
  Source code digests are omitted from exports; imported code rows are revoked and receive inert,
  fresh random digests. They cannot grant admission or discounts on a target deployment.


- **The event venue Station is a public bearer channel with a fixed compatibility contract.** Its public
  token stays in `/api/v1/event-checkin-stations/<public_token>/...`; the signed HttpOnly cookie is named
  `sw_event_station`, is scoped to that token's API prefix, uses salt
  `spaceworks.events.station-cookie.v1`, and contains exactly `public_token`, `version`, `session_id` and
  `expires_at`. PINs are eight digits and their HMAC input remains
  `spaceworks:event-station-pin:v1:<event_id>:<version>:<pin>` under `EVENT_STATION_PIN_PEPPER`; rotation
  increments the version and invalidates earlier cookies. Public failures are deliberately uniform, and every
  success response is no-store. PIN exchange requires the exact allowed Origin/Referer plus
  `X-Station-CSRF`; the existing token/IP/session/reveal throttle scopes, event window/status checks,
  `events.offline_checkin` feature gate and tenant source-migration gate are part of the protocol.
- **Shared Station metadata is inert; credentials are the complete live authority envelope.**
  `makerspaces.Station` holds only tenant, kind, name and provisioning provenance;
  `makerspaces.StationCredential` holds the public token, encrypted/revealable PIN, digest, rotation version,
  enabled state and timestamps. Portable export/import carries Station metadata without `created_by` and
  without any credential, so it arrives inert. Deployment `database.dump` recovery is different: it preserves
  Station, binding and every credential field byte-for-byte, so an enabled URL/PIN remains usable and a
  disabled credential remains disabled.
- **Event Station authority remains owned by events through `events.EventStationBinding`.** The binding is
  one-to-one on both event and Station, and services require the same makerspace plus kind `event_checkin`.
  Events purge locks and collects those Station IDs, then removes their credentials, bindings and Stations;
  scanner/handover Stations survive an events-only purge, while whole-tenant purge removes every kind. A
  tombstoned events app mounts no event Station URL. Disabling a credential blocks sessions, while PIN reveal
  requires a usable-password step-up and keeps the existing audit actions. Roster and synchronization stay
  event services, and station attendance remains anonymous (`actor=None`, source `venue_station`), distinct
  from authenticated staff offline check-in.
- **A kiosk Station PIN opens a channel; it never authorizes a handover (phase 9b, `inventory.kiosk`).**
  Scanner/handover Stations are managed under `MANAGE_MAKERSPACE` (`station_views_admin.py`; the event kind
  is refused). The PIN (`spaceworks:kiosk-station-pin:v1:<station_id>:<version>:<pin>` under the existing
  `EVENT_STATION_PIN_PEPPER`) buys only the `sw_kiosk_station` cookie, path
  `/api/v1/kiosk-stations/<token>/`, which is session-bound bearer material, never device-bound. Every
  cookie-accepting route runs the exact Origin/Referer + `X-Station-CSRF` check and the
  `StationSessionRevocation` lookup; session DELETE records the revocation before clearing the cookie, so a
  copied cookie is dead for the rest of its signed life. Rotation and disable revoke every lease.
- **Kiosk work is attributed to a real User through a `StationOperatorLease`.** A lease needs a normal login
  AND the Station cookie; it stores `station-kind allow-list ∩ rbac.effective_actions ∩ live capability
  conjunctions` (local membership or organization grant -- never a second membership-only gate), is clamped
  to the session expiry, and holds no bearer token. Every work/evidence/command call re-checks the signed
  token, row, Station/session/version, active user, live RBAC, source gate and the literal operation in
  `hardware_requests/kiosk_command_policy.py`; the stored snapshot only narrows. The Station is never an
  audit actor: existing services write their normal rows with the User, plus one companion
  `kiosk.online_command_executed` row carrying station/session/version/lease identity. Capability off
  answers 400, missing authority 403, `inventory.kiosk` off refuses the session uniformly. Deployment
  quarantine revokes every lease; leases and revocations are omitted from tenant archives.
- **Handover replay is ordered, token-fenced coordination over the existing workflows (phase 9c).**
  `hardware_requests.ReplayCommand` stores only canonical SHA-256 identity, Station/session/human lease,
  aggregate sequence/predecessor, claim state, catalogued failure and stable domain/evidence references.
  It never stores payload/response JSON, raw QR or borrower PII. Prepare and execute require the same
  signed Station cookie, exact Origin/Referer and `X-Station-CSRF`, plus `X-Kiosk-Operator-Lease`.
  Replay reloads the lease's real User without requiring their normal browser login to remain live;
  current account, membership/organization RBAC, Station version/revocation and operation capabilities
  are checked before claim and again before the domain effect. Module/feature off is 400.
  Prepare establishes one immutable evidence identity and presigns staging only. Execute commits a
  short claim plus `kiosk.replay_claimed` audit before S3, then commits workflow effects, stable results and `kiosk.replay_succeeded`
  together in one outer transaction. Nested workflows reuse finalized evidence from database state,
  so their domain locks never span completed-evidence S3 cleanup. Stale claims are reclaimed after
  five minutes with a new token; an old executor cannot release or complete a newer claim.
  Duplicate success has no second physical effect; changed canonical identity conflicts. Expected
  domain refusals become terminal typed failures with `kiosk.replay_failed`; storage/unknown faults
  stay retryable. Failed evidence stays immutable and readable under existing evidence permissions
  and retention. Maximum command age (eight hours) cannot exceed coordination retention (seven days),
  and server timestamp validation prevents cleanup from reopening old ownership keys. Daily bounded
  cleanup expires prepared/stale-claimed work and deletes retained terminal leaves, preserving any
  predecessor still referenced by a descendant. Whole-tenant purge removes all replay links first.
  Coordination and its actor edge never travel in portable tenant exports. Direct return may resolve
  the loan from its succeeded predecessor chain; per-item resolutions keep the existing staff contract.
  Browser queue and recovery UI are separate slices.
- **Registering for an event does NOT require a `PresenceSession`; check-in does.**
  `require_active_member` (identity + membership + waiver) was split out of
  `require_active_member_presence`, and **only** `PublicEventRegistrationView` switched wholesale. The
  hardware and facility invocations — self-checkout ×3, direct handout, public booking, and the two
  machine-service surfaces — still require a session, because "is this member here right now" is the
  whole question (the two machine-service surfaces only while `membership` is installed: without it
  they take the identity-only guard, `machines/views_public_service.require_public_machine_requester`).
  "Check-in does" means the staff-scanned event QR check-in is the presence evidence, not that it
  looks up a `PresenceSession`. Request submission also keeps that guard while `membership` is enabled; with
  `membership` off it uses the separate identity-only guard because a request is only a proposal and
  staff acceptance is the control. There is no waiver check on that branch because waiver acceptance
  can only be recorded on a membership row. Signing up for an event is planning to attend; presence is
  proven later by the staff-scanned QR, which is stronger evidence than a self-declared session.
- **`events.member_history.registrations_for_space` is the ONE answer to "which registrations does
  this member hold in this space"**, shared by the profile counts, the profile's recent-attended list,
  member activity and the QR lookup. It filters on **durable provenance**
  (`EventRegistration.registered_via_makerspace`, `SET_NULL`), **not** current collaboration: accepted
  collaboration authorizes *discovery and creation*, provenance records *where participation
  happened*, so an administrator editing a collaborator list cannot retroactively delete a member's
  history or break a QR someone already holds. A **NULL provenance falls back to the host**, so the
  read fails OPEN to pre-provenance behaviour and the backfill is tidiness rather than load-bearing.
  History still stops at the **host's** archival or withdrawn `events` module.
- **Presentation and PAYMENT are gated differently, and conflating them loses money.**
  `payments.member_scope.member_payment_queryset` widens the three member payment surfaces (history,
  web checkout, native intent) to an `EVENT_REGISTRATION` charge raised by another host when the
  member's own registration names this space as provenance — otherwise a visitor's charge exists and
  is undiscoverable, since the host 403s them and their own space filters it out. It is gated by
  **neither** the host's module **nor** archival: a module toggle must never hide a receipt or block a
  pending charge, and the separability contract keeps historical payment subjects usable when
  tombstoned.
- **Cancelling an event (or its series) cancels its PENDING registration charges** (2026-10-09):
  `services_lifecycle.cancel` schedules `cancel_for_registration` after commit for every pending
  one, so provider-session expiry never runs under the event lock. Settled charges stay — a refund is
  a staff decision. **Known open hole (owner decision):** re-registering after a cancellation revives
  the same row and pk, so the terminal CANCELED charge is found again and `payment_one_per_subject`
  forbids a fresh one — a paid event becomes free for that member.
- **PAYMENT ROUTING LIVES ON `Payment.via_makerspace`, NOT ON THE REGISTRATION'S PROVENANCE.**
  One column cannot serve both: `module_purge_collectors.events_delete` must clear
  `registered_via_makerspace` (destroying activity history is what a purge is *for*), and keying
  payment visibility on that same column meant a collaborator's purge made a host-raised charge
  invisible in the member's area while the host still 403s them — a receipt gone and a **pending
  charge unpayable**. The routing therefore sits on the money record, which no purge touches:
  stamped at creation by `service_payments._get_or_create` as
  `registered_via_makerspace or event.makerspace`, read directly by `member_scope`'s second arm, and
  **never cleared by any collector**. The `subject_type=EVENT_REGISTRATION` clause stays on that arm
  so it can never widen to "every payment this user has anywhere". Two traps this hit: the backfill
  (`payments/0011`) stamps **only where the registration's member matches the payment's member** —
  `Payment.clean()` does not validate that, and the old subquery did, so stamping blindly would newly
  expose one member's charge through another space; and a payment whose registration was already
  deleted by an earlier purge is **unrecoverable and reported**, not silently skipped. The immutability
  trigger permits the backfill because it raises only when `status` or `amount` change.
- **A DELAYED charge needs routing preserved BEFORE the purge, which `Payment` cannot do.** A
  waitlisted registration has no `Payment` at all — one is raised only when `_promote()` lifts it to
  REGISTERED — so if the collaborator purges `events` in between, provenance is already NULL and the
  charge falls back to the **host**, where the visiting member holds no membership: refused there,
  filtered out at home, payable from neither. `EventRegistration.payment_via_makerspace` is the second
  durable copy, written beside `registered_via_makerspace` at registration and **deliberately not
  cleared** by `events_delete`; `_get_or_create` reads it first. Keeping it resurrects nothing —
  member history, the maker profile and the QR lookup all read `registered_via_makerspace`, never
  this column. **Both columns are scoped to the COLLABORATOR's purge, not the host's** — and what
  the HOST's purge does has since CHANGED, so the text that stood here is corrected rather than
  preserved. It read that a host purging `events` destroyed every host-owned event charge
  (visitors' included) through the plan's `payment_subjects=("event_registration",)`, deleting
  payments before their subject so none survived as a dangling generic reference, and it recorded
  that as an **open question**. That question is now **settled the other way, and the mechanism it
  described no longer exists**: `ModulePurgePlan` has no `payment_subjects` field at all (removed
  2026-08-11 — see "NO MODULE PURGE DELETES A `Payment`" under the per-module purge invariant),
  `module_purge_plans.py` carries a comment saying so deliberately, and
  `tests/payments/test_payment_survives_module_purge.py` asserts
  `not hasattr(ModulePurgePlan, "payment_subjects")` for every plan. **A host purge therefore leaves
  a visiting member's receipt readable and their pending charge payable.** The dangling generic
  subject the old design refused to accept is exactly what `Payment.subject_label`'s creation-time
  snapshot and the relaxed `Payment.clean()` were built to tolerate. This contradiction survived in
  this file because the two programs were written weeks apart and neither re-read the other —
  **verify against `module_purge_plans.py` before relying on any account of purge-versus-payment.**
- **`create_for_registered_registration` SWALLOWS EVERY EXCEPTION**, so a signature mismatch against
  `payments.services.create_payment` does not raise — it silently stops creating charges while
  registration still returns 201. Any test covering event charging must drive the real path; one that
  fabricates a `Payment` row proves nothing about the wiring. `create_payment`'s `via_makerspace`
  keyword defaults to `None`, so bookings/membership/machine-service call sites are unaffected (their
  charges are owned by the member's own space, which arm 1 already covers).
- **The collaborative registration route shares the CREATE budget and splits the RETRY budget.**
  `_collaborative_events()` deliberately includes the member's own space's events, so the same event
  is reachable through both `MemberCollaborativeEventRegistrationView` and
  `PublicEventRegistrationView`; throttling only one is a bypass. Both therefore use
  `ClientTierRateThrottle` + scope `event_register` — **not** `MemberPrincipalRateThrottle`, whose
  `member:<pk>` ident is a *different* DRF cache key and would hand out the limit twice, closing half
  the bypass. But DRF checks throttles in `initial()`, before `post()`, so a blanket throttle 429s the
  `DuplicateRegistration` retry that is a member's **only** way to repair a registration holding no
  waiver acceptance — and since the bucket is shared, the public route could exhaust it and strand
  them at the door. `check_throttles` therefore reassigns `self.throttle_scope` to
  `event_registration_retry` when a registration already exists (`self.kwargs` is set by `dispatch()`
  before `initial()`). Retries stay bounded; they are never blocked by the create budget.
- **`checkin_token` is surfaced only while the registration is REGISTERED AND the event is still
  checkable.** `services.cancel()` changes only `Event.status` and leaves registrations REGISTERED, so
  gating on the registration alone hands out an admission code nothing can ever confirm. The QR route
  and `member_activity_service` must agree, or a token is advertised whose route refuses it.
- **Resolve answers unknown, malformed and wrong-event tokens identically.** Distinguishing them makes
  it an oracle for "this code is real but belongs elsewhere". **UUID4 entropy** is what makes
  enumeration infeasible; authorization + event scoping + the uniform 404 stop a stolen token crossing
  tenants; the staff-keyed throttle only bounds abuse. Resolve is **read-only** and confirm reuses the
  existing pk-authorized `mark-attended`, so a scanned token never mutates anything.
- **A route kwarg feeding `MODEL_LOOKUPS` MUST be named `pk`** — `origin_scope_routes` reads
  `kwargs['pk']` and marks the request invalid when absent, so `<int:event_id>` is **denied on every
  tenant custom domain despite being registered**.
- **The collaboration API has TWO tenant scopes and needs four DISTINCT route names**, because
  `origin_scope_routes` is keyed by route name, not HTTP method: host invite/list → `events.Event`,
  host remove → `EventCollaborator.event__makerspace_id`, collaborator inbox → its `makerspace_id`
  kwarg, accept/decline → `EventCollaborator.makerspace_id`. Registering accept against the host would
  **403 it from the collaborator's own domain**, which is the entire feature.
- **Legacy Events paths use `event → makerspace(s)`**, matching shipped `publish()`,
  `update_event()` and image attach. `require_module_locked` goes **after** `_locked_event` in
  `register()` (before would deadlock against `publish`), two makerspaces lock in **sorted pk order**,
  and `remove_collaborator` reads the event id **unlocked** first — a `select_for_update()
  .select_related("event")` locks both rows in the wrong order. Programme paths require the
  source/global/tenant/account-first contract above. These legacy callers still need the
  coordinated conversion in GF1 items 2–4; this historical rule is not permission to mix
  incompatible orders or to claim conversion complete.
- **The host waiver lives on the `EventRegistration`, not a membership** (a visitor membership would
  corrupt the host's member reporting, roster, quota and dues — `reports_members` counts every row).
  Three fields under an all-or-none check constraint, `PROTECT`, with acceptance an **explicit API
  field** — inferring it from a submitted id lets any caller manufacture evidence about a real person.
  Re-read under the host lock so a superseded version is refused. Stamping is one helper shared by the
  create and idempotent-retry paths. Audited with id + version, **never the body**: the purge clears
  the columns, so the append-only log is the surviving evidence, and the body would be undeletable
  member data. A registration with **no** acceptance yields no QR — but **not** gated on the *current*
  version, or revising a waiver strands a legitimate member at the door.
- **Waiver evidence lives in TWO places, and reading one reports a falsehood about a real person.**
  A visitor's acceptance is stamped on the `EventRegistration`; a **host member's lives on their
  `MakerspaceMembership`**, because the registration path deliberately does not re-record an agreement
  the member already gave their own space. The check-in resolve payload shipped as
  `bool(registration.host_waiver_id)`, which is therefore **structurally false for every host member**
  — the scanner told correctly-accepted members to "take one at the desk", and said the same when the
  host had configured no waiver at all. `views_checkin.host_waiver_state()` is the one answer:
  `not_required` when the host has no active waiver, `on_file` when either location holds an
  acceptance, `missing` otherwise. Not compared against the *current* version, matching the QR gate.
  **"Not a visitor" is NOT "not required"** — `views_admin`'s staff registration only checks that a
  membership exists, never `require_active_member`, so a host member genuinely can hold a registration
  with an active waiver and no acceptance anywhere. That contract had **no test at all** before
  (nothing ever asserted on the field), which is how it shipped wrong.
- **`confirmable` mirrors `mark_attended`'s own precondition** (`status == REGISTERED` **and**
  `event.status in CHECKABLE_EVENT_STATUSES`) rather than inventing a second rule. Resolve accepts
  waitlisted/cancelled/attended rows and previously omitted event status, so a registered row on a
  **cancelled event** rendered a Confirm button whose request could only ever 409. Everything on this
  screen stays reported-never-enforced: it is the button that is withheld, never the door.
- **That `PROTECT` FK breaks BOTH purges if unhandled**: `membership_delete` must clear the
  registration's three fields alongside the membership's, and `lifecycle.purge` must clear them for
  registrations hosted **elsewhere** before its explicit
  `EventRegistration.objects.filter(event__makerspace=makerspace).delete()` (placed after the
  `ProcessedStripeEvent` delete, since Payment must precede its generic subject). Verified: removing
  either clearing step raises `ProtectedError`.
- **The member QR route lives in its own separable `events/urls_member.py`.** Declared alongside the
  rest of the `member/` surface it kept resolving, and stayed in the OpenAPI schema, on a deployment
  that ships no events app — caught by the tombstone suite.
- **Purging `events` at a collaborator must clear `registered_via_makerspace` on registrations hosted
  elsewhere**, or reinstalling resurrects supposedly purged activity and profile history.
- **`MemberProfile.show_attended_events` is consent, not configurability.** `is_visible` publishes the
  fields the member typed into the profile form; attendance is neither typed nor on that form. The
  `activity` payload is now a typed nested serializer that **omits** absent keys — a zero says
  "attended nothing", an absent key says "this space does not run events".

## Backup, restore and tenant migration (Phase 5A/5B and Lane D D1-D4/D6 built)

- **A restored `DataExportJob` download bearer is never usable.** The download route is anonymous,
  and quarantine's credential reset does not cover it. `apps/data_export/restore_hooks.py` clears
  bearers at classic `rehydrate_control_record` (both kinds). Tenant dumps never carry this model
  (`OMITTED_MODELS`).
- **A restored `backup.BackupArchive` download bearer is never usable.**
  `apps/backup/services_access.invalidate_download_tokens_after_restore` clears bearers at classic
  `rehydrate_control_record`. Tenant dumps omit the model (`OMITTED_MODELS`).
- **`TenantDumpCapture` download bearers are cleared pre-emptively** by
  `apps/tenant_migration/restore_hooks.py` at classic `rehydrate_control_record`. Today `publish_tenant_dump`'s token has no caller and no redeemer.
  **RULE:** a future `TenantDumpCapture` download route must keep these hooks, and any new model carrying
  a `download_token_*` bearer needs a sweep at every seam that copies its rows.

### Offsite destinations and the `backup` module (lane backup, 2026-10-09)

- **An offsite copy is `bytes_verified`, never "restorable".** `offsite_push` streams the primary
  ciphertext to each active `BackupDestination`, re-hashes it on the way, then streams the remote
  object back and compares size + SHA-256 with the artifact ledger (or the archive row when no ledger
  exists). HEAD/ETag are not proofs. The platform cannot open a sealed slice or a tenant archive, so no
  surface may describe a verified copy as restorable.
- **A destination outage never fails a backup.** The push runs after the build has released
  `deployment_operation_lock`, holds no row lock during I/O, touches no `BackupRun`/`BackupArchive`
  state, and backs a journal row off `5 min × 2^attempts` capped at 6 h.
- **Pushed:** every deployment archive and every run-produced tenant archive. **Not pushed:** ad hoc
  makerspace archives. Destinations are platform-held only (a tenant cannot register its own).
- **Verified copies are re-read every 30 days** (`offsite_reverify`). A digest mismatch returns the
  row to `pending` for a fresh upload and is audited `backup.offsite_copy_corrupted`; a transport
  failure only records its code. This is byte integrity, not a restore drill.
- **Retention never removes the newest verified copy** per destination (and per tenant), whatever its
  age. Retiring a destination wipes its credentials and keeps the journal.
- **Primary archive retention is 7 daily + 4 weekly for nightly runs** (BK-09, `backup/retention.py`).
  Every run-produced archive expires after 7 days; the first one per scope/makerspace to complete in an
  ISO week is the weekly copy and expires after 4 weeks. On-demand archives keep the flat
  `PlatformBackupSettings.retention_days`. Expiry is stamped once at completion (both completion paths),
  so `purge_expired_archives` stays the only thing that deletes archive bytes.
- **Credentials** are Fernet under `API_CLIENT_ENC_KEY` via `makerspaces.secrets`, write-only in API and
  `/control/`, never in audit meta or logs. `fetch_offsite_archive` reads them from a mode-0600 file,
  never argv/env, and its output still goes through `import-backup.sh`'s signature preflight.
- **Rehydration is create-only.** A verified copy is fetched and checked locally, then written to the
  archive's own locator with `If-None-Match: *`; it never overwrites a present primary object.
- **There is no `backup` module key (retired in P1b, owner decision #111 Q2).** Space Managers no longer
  request, list or download archives: makerspace archives and downloads are superadmin-only. A manager
  reads a read-only "Last backup" line (`GET /admin/makerspace/<id>/backup-status`, `MANAGE_MAKERSPACE`)
  and keeps their own copy through data export. `backup/0032` strips the key from `enabled_modules`.
- **Never hand a `StreamingBody` to `put_object`.** `create_final_from_staging` did, so against a real
  store (botocore 1.43, MinIO) promotion raised `io.UnsupportedOperation` — outside its caught
  exception types — because botocore seeks the body for checksums and, over http, reads it to sign
  the payload. Every promotion test mocked the primitive, so nothing noticed. It now spools staging to a
  private temporary file and puts that; `tests/backup/test_storage_promotion_real_store.py` runs it
  against the harness MinIO.

### The SHAPE a projected model must have (catalog-driven, 2026-09-03)

Being classified is not the same as being importable. Two shapes break a tenant move
silently, and each was found only by running a full round-trip *after* the model had
already shipped, so both are now enumerated over the whole
`PROJECTED_MODEL_LABELS` catalog by
`tests/tenant_migration/test_projected_catalog_travel_guard.py` — a newly projected
model inherits the checks instead of waiting for a bespoke round-trip test:

- **The primary key must be an auto-integer or a UUID.** `pk_maps` can only reserve
  target values for those shapes and raises `UnsupportedPrimaryKey` otherwise, and a
  `OneToOneField(primary_key=True)` additionally exports no `id` column at all, so the
  materializer's read of the pk fails mid-move. **A `OneToOneField(primary_key=True)`
  on any model that travels is a latent break — prefer a normal auto pk plus a unique
  `OneToOne`.** Both evidence retention models shipped this way and had to be amended.
  `pk_maps.SUPPORTED_PK_FIELD_TYPES` is the single source of truth; the guard asserts
  against it rather than keeping a second copy.
- **Every deployment-global unique column needs a `DEPLOYMENT_GLOBAL_UNIQUE_RULES`
  entry** deciding REGENERATE versus PRESERVE-and-refuse. An unruled unique column
  violates its own constraint the first time a target already holds the value. The one
  deliberate exemption is `accounts.User.username`, resolved before insertion by
  `identity_resolution.allocate_username`; the guard holds that exemption as an exact
  set, so adding a rule for it fails the test until the exemption is removed.

Relational uniqueness is scoped by the row it points at, so a unique `OneToOne` is not
a deployment-global collision and is deliberately out of scope. Object pointers are a
separate, already-guarded axis: `tests/backup/test_object_field_coverage.py` requires
every `*_key` field to be either captured by name in `OBJECT_FIELD_NAMES` or exempted
with a reason in `NON_OBJECT_KEY_FIELDS`.

### Lane D tenant-exclusive identity and payment closure (D6, 2026-08-23)

The account-kind extension (D11/V5) in [account-split-portability.md](account-split-portability.md)
preserves tenant staff authority without credentials; platform actors remain inert provenance.

**Lane D does not use the older per-identity `DisclosureClosureApproval` policy.** That
path remains for the older PORTABLE data-export/API contract, but a sovereign tenant
dump classifies identities from its immutable captured database image: a referenced
user is full only when at least one `MakerspaceMembership` exists and every membership,
active or revoked, belongs to the exiting makerspace. Every other referenced person is
an artifact-scoped, PII-free `is_tenant_dump_stub` row. Missing users, unclassified
edges, dangling non-null edges, and semantic user references without a rewrite handler
refuse the build. The persisted stub marker is a permanent denial input to password,
JWT/refresh, device, phone, social, password-reset, member-claim, and RBAC paths; editing
the stub's password, active flag, access status, or role does not make it a principal.

The manifest's `user_closure` has exact sorted `included`, `stubbed`, and `refused`
lists and a canonical SHA-256 digest. Entries contain only the artifact-scoped user
reference, emitted source PK, reason, stub schema version, and sorted referencing-edge
tuples. Source derivation, the migrated scratch database, the restored target-shaped
verification database, and publication manifest validation reproduce or validate that
same digest independently. Source audit stores only its digest, counts, and
artifact/capture identifiers—never the identity lists.

**Cross-tenant and payment history is fail-closed.** Foreign EventCollaborator rows and
foreign-owned stock-transfer lines are dropped with PII-free lost-edge records;
StockTransfer foreign makerspace/container pairs are nulled atomically. Registration
routing is cleared. Pending tenant Payments travel (owner decision D5, see **A pending payment no
longer refuses a tenant dump**): the preflight refuses one with a live rail, and publication
revalidates the money fingerprint. Pending and the four terminal statuses keep readable
amount/currency/provider/status/subject history while clearing all routing,
merchant/account/order/payment/session/intent handles and checkout URLs.
The exact external-FK registry and independent scratch/target postconditions refuse
schema drift or a surviving live provider binding.

### Deployment archives: one platform-readable component (P1b, 2026-10-27)

**Superadmin is always on (owner decisions #110/#111), so every archive this deployment builds is
encrypted to the platform key `BACKUP_AGE_RECIPIENT` and nothing else** (`backup/age_recipients.py`).
There are no per-makerspace archive recipients, recipient challenges, custody states, custody alarms,
recipient reservations or activation states; their tables were dropped in `backup/0030`. A deployment
archive has exactly ONE component, the readable main. Sovereign slices, the readable-main exclusion of
sovereign rows, the W8 slice DEK rewrap, E7 restore reservations and fences, the E8 delayed slice merge,
the not-restored component state and the E9b compound restore coordinator were all deleted (`backup/0031`
drops their tables and every `backup_b1_*` function). An archive that still declares `partial: true` is
refused by the restore preflight before any effect: nothing can open its slices any more.

**The readable main is still projected and verified before packaging.** `main_projection` restores the
frozen dump into a scratch database, deletes `OMIT_OPERATIONAL` rows and emptied non-model tables (no
makerspace is ever excluded), dumps it, restores that dump into a second fresh database and checks it
against the expected row-identity ledger and the physical-catalog digest. The main-projection registry
(`main_projection_registry.table_rules`) remains the drift guard every physical table must be classified
in. Object capture still builds the typed `ObjectOwnershipPlan` (E4) and proves reference/manifest/byte
equality for the main component; an evidence-retention tombstone is still the only no-byte member.

**The signed outer manifest is protocol v2** (`compound_protocol.PROTOCOL_VERSION`). It is an allowlist:
capture/build identity, source PostgreSQL/client facts, `makerspace_ids`, the main component (path, size,
ciphertext SHA-256, schema-catalog digest, semantic digest, platform recipient fingerprints) and its object
and content ledgers, plus compatibility names (`covered_makerspace_ids`, `excluded_makerspace_ids: []`,
`partial: false`). Its Ed25519 signature binds canonical manifest bytes plus the one-entry component
ledger; the artifact carries only the signer fingerprint and signature. Verification trusts
`BACKUP_ARCHIVE_VERIFY_PUBLIC_KEY` from the host channel, while the producer alone gets
`BACKUP_ARCHIVE_SIGNING_PRIVATE_KEY`. A manifest-provided key can never authenticate itself. A v1 archive
(sovereign slices, reservation facts, source-partition proof) fails `format_version`; none without a slice
could ever be built, because the v1 source verifier refused a capture with no slice.

`BackupArtifactLedger` and `BackupArtifactComponent` outlive the optional `BackupArchive` row. Artifact and
component identity facts are immutable and transitions are database-guarded. Do not fold this state back
into `BackupArchive`: byte retention may delete that convenience row, but reconciliation must survive it.

**A deployment artifact is never uploaded directly to its advertised key.** The server uploads to the
artifact-unique staging locator, streams it back for size plus SHA-256, conditionally creates the immutable
final locator with `If-None-Match: *`, and streams the final object back too. HEAD and ETag are not integrity
proofs. No artifact row lock may be held during those remote steps. Only then may
`promotion.promote_verified_artifact()` run its one short no-I/O transaction, in this lock order: artifact
rows; components; `BackupArchive`; `PlatformBackupSettings`. That transaction revalidates the signed
manifest and its makerspace population against the frozen snapshot, the signed identities/digests, the
durable component row, final verification facts and predecessor success state. Availability, the success
audit and `last_success_at` commit or roll back together.

The initial runner and `reconcile_backup_artifacts_task` call the same promotion primitive. Pending with
staging resumes final creation; pending with final bytes stream-verifies and enters the same transaction;
available with leftover staging retries cleanup only. Staging is deleted after promotion commit, and a
cleanup failure never demotes a verified final. A failed newer run may set `last_error`, but must preserve
the prior artifact and `last_success_at`.

**Compound production is admitted only by the separate host-installed producer-capability marker (Lane E
P1, 2026-08-24).** This is not the H1 restore-state marker and is not an entrypoint launch grant. The root
installer writes `/var/lib/spaceworks/host/public/producer-capability.json` mode `0444` through file fsync,
same-directory atomic replacement and parent-directory fsync, after the archive verification public key is
installed. It records SHA-256 for the installed `host-capability.py`, `import-backup.sh`, `restore.sh`,
`spaceworks-compose.sh`, its sourced `compose-deployment.sh`, and `validate-compose-wrapper.py` host scripts, SHA-256 for the image's actual common
entrypoint, the closed supported deployment-archive protocol range, only the verification-key fingerprint, and a
length-framed digest of the installed Django migration files. It never records or receives the private
archive-signing key.

`backup/archive_builder.py` checks this marker only for deployment/compound builds and does so before
platform-recipient resolution, temporary workspace creation, capture bytes, encryption, staging upload or artifact
ledger persistence. The marker and directory must be root-owned and non-writable by non-root principals,
and the marker must be exactly mode `0444`. The producer re-hashes every privileged script from the
read-only host scripts mount, the common entrypoint from the running image and the installed migration
files; recorded versions never substitute for those byte comparisons. It also proves the protocol to be
emitted is inside the marker range, derives the public identity of the configured private signing key,
requires it to equal the configured verification key, and compares its fingerprint with the marker. A
missing, unreadable, malformed, misowned, wrong-mode, locally modified or rolled-back input refuses with a
stable reason code. Ordinary makerspace/single archives do not read this marker and remain available on
hosts that do not have one.

**The PostgreSQL client major must equal the server major for anything that dumps or restores THIS
deployment**, and `apps/backup/postgres_client.py` is the only place that resolves those binaries. The
image ships two client majors on purpose: `pg_dump` must be at least as new as any *source* server tenant
migration reads (14-17), so the newest is on `PATH`, while the deployment's own dump and restore need the
server's own major. Getting this wrong does not degrade, it breaks silently in both directions: `pg_dump`
17 writes archive header version **1.16**, which `pg_restore` 16 refuses outright, and `pg_restore` 17+
emits an unconditional `SET transaction_timeout = 0;`, a GUC that does not exist before 17, so a PG16
server rejects it and `--exit-on-error` aborts. This was not hypothetical: until 2026-08-23 the backend
dumped with client 17 against `postgres:16` while `scripts/restore.sh` restored inside the `db` container
with client 16, so **every deployment archive produced was unrestorable through the shipped restore path**.
Never call a bare `pg_dump`/`pg_restore`/`createdb`/`dropdb` from application code, and keep the archive
build's readiness gate checking the *resolved* binaries rather than `PATH`.

**A host-supplied deployment archive is rejected before any deployment mutation.**
`apps.backup.import_preflight.validate_import_preflight` is the shared, side-effect-free admission path for both
the validate-only management command and `import_backup_archive`. It binds the optional caller digest to the
encrypted outer artifact; verifies the host-trusted signer, signature, compound format/version, declared
component paths/sizes/digests and member allowlist; validates the exact nine-name single-line continuity-key
shape; and requires source-build plus exact pg_dump/source-server/target-server major compatibility. The
host wrapper holds its existing `flock` while it decrypts into the operation-owned temporary directory and
runs that validator through `docker compose run --rm --no-deps`; only success permits the `.env` backup and
rewrite or recreation of backend, worker and beat. Refusal writes no restore intent or audit, calls no object
store, leaves `.env` byte-identical with no `.env.pre-restore-*`, does not restart a service, and cleans the
temporary directory. The compound coordinator calls this same validator while holding the host operation
lock, then independently validates the installed host capability record and topology before its first ledger
effect; `host_restore_gate_status()` remains descriptive only and never confers launch authority.

**Auto-created many-to-many through tables are physical tables, not fields embedded in their owning
model's row.** Each must therefore have its own literal physical-table disposition and its own count,
identity digest and concrete-column row digest. The owning model's digest covers only its concrete columns.
Never bypass `raw_projection.fixture_payload`'s refusal to synthesize missing auto-created M2M rows: a new
through table without an explicit disposition is registry drift and must fail the build.

> **Retracted (P1b, 2026-10-27).** This document used to carry a "guarantee" that the platform-readable
> portion of a deployment artifact excluded sovereign tenant content. With the superadmin always on there
> are no sovereign tenants and no sealed slices: **every byte of every archive is readable with the
> platform key.** No UI, API, audit event, manifest field, docstring or comment may claim that any
> makerspace is withheld from a backup or from the platform operator.


**Never combine a `RunPython` data migration and an `AddConstraint` on the same table in one
migration.** PostgreSQL raises *"cannot ALTER TABLE because it has pending trigger events"* as soon as
there are rows to update, so the migration passes on a fresh database and aborts on a real upgrade.
This cost a real bug here and is why the constraint lives in its own migration. `makemigrations --check`
cannot catch it — **a `MigrationExecutor` test that actually runs the migration over pre-seeded rows is
required** (pattern: `tests/test_procurement_machine_type_migration.py`).

**The deployment recovery gate reads live state on EVERY request, deliberately uncached.**
`apps/backup/middleware.py` is first in `MIDDLEWARE` and resolves `DeploymentRecoveryState.mode`
before anything else. A cache was written and **reverted**, and the reasoning is the invariant: a TTL
leaves a deployment that has *just* been quarantined still serving traffic, which is the one failure
a default-deny gate exists to prevent. It also made the per-request query count depend on cache
warmth, which broke three query-count tests that capture a count with N rows and assert **equality**
with N+1 — the first request paid for the lookup and later ones did not. The cost is one primary-key
lookup on a single-row table. **If it ever needs optimising, use an invalidation mechanism with no
staleness window (connection-level or `LISTEN`/`NOTIFY`), never a TTL.** A cache miss must still
query and still fail closed; treating a miss as `NORMAL` makes the gate fail open.

**Consequence for query-count tests:** the gate is a constant **+1 on every request**, not an N+1.
`tests/events/test_public_api.py`'s constant is 3 for that reason. The tests that capture-then-assert
equality (`test_perf_query_counts.py`, `test_machines.py`) stay correct **because** the count is
deterministic — which is the second reason not to reintroduce caching.

**A new app must classify its models in `apps/data_export`, or the drift guards refuse the build.**
Phase 5A added six `backup.*` models and four user edges and hit this, exactly as phases 7 and 8 did
at their integration. Deployment-scoped operational state is `OmittedModel` even when a row names a
makerspace: `BackupArchive.makerspace` records which tenant an archive covers, and exporting the row
would carry its single-use download token into a tenant archive. **Archives are outside the purge
guarantee, so they must not travel inside one either.**

**`select_for_update()` + `select_related()` across a NULLABLE FK is rejected by Postgres** — *"FOR
UPDATE cannot be applied to the nullable side of an outer join"*. Already documented under
procurement (`move_to_printing`); Phase 5A hit it again in three places. Drop the `select_related`
and lazy-load; the extra query is free next to the writes the transaction already performs. **This
is now a recurring trap, not a one-off.**

**Phase 5B (tenant migration) is BUILT on `dev`.** The plan is
`docs/superpowers/specs/2026-08-16-phase5b-plan-v13.md` (gitignored) — **cumulative and standalone;
v1–v12 are history only**. Conclusions that cost thirteen review rounds and must not be re-derived:

**Lane D D1 adds a separate deny-by-default source catalog.** Its literal model and
concrete-or-M2M field snapshots are checked against `apps.get_models(include_auto_created=True)` and a
pinned graph digest before source projection reads a row. A new field, M2M, model, generated through table,
unmanaged model or model-bearing app fails closed until classified. The projection reuses
`backup.raw_projection` under its no-decrypt guard. Owner decision 22 deliberately reverses the older
portable-import rule: every `MachineOperator` assignment travels as live authority with `assigned_at` and
`assigned_by`, and a missing machine, operator or non-null assigner refuses the build.

**Lane D D2 derives its database dump only through a migrated, run-owned scratch database.** The loader
uses D1's row/field catalog and its reviewed concrete-column snapshot, deletes portable predicates in
reverse dependency order, and inserts raw rows in actual FK order while every database constraint remains
active. Migrations run in a child process whose Django `default` connection is the scratch database; this
is required because historical `RunPython` functions with unqualified managers would otherwise route their
data writes back to the live in-process `default` connection. It never sets `session_replication_role`;
only nullable edges inside an actual strongly connected component may use the two-pass NULL-then-update
path, and the component must become acyclic without them (a cycle of required edges still refuses; a
claim's required `revision`/`claim` edges with its nullable `current_*` pointers qualify). A stage form's
revision rows depend on the stage form row they name by `selector_id`. Global `MachineType` built-ins resolve by
`(makerspace IS NULL, slug)` only when the canonical `name`/`icon`/`is_builtin`/`managing_action`/
`capability_config` fingerprint equals the migrated target definition; tenant custom rows retain their PKs.
The tenant PII fence is explicitly closed under the matching `tenant_import` GUC for mapped raw insertion
and is dumped `open` with operation fields cleared. Immediately before `pg_dump`, `spaceworks_cache` must be
empty and every owned sequence is normalized to `max(pk), true` or `seqstart, false`. The server-matched
client from `backup/postgres_client.py` creates the custom `--no-owner --no-acl` dump; a second empty database
restores it and repeats catalog, FK-closure, open-fence, cache and raw mapped-value digest checks before the
candidate is atomically exposed. Object members are copied only from immutable capture staging and carry an
opaque member path plus original key, version ID, size, content type and SHA-256; ETag is never a digest.
Terminal evidence expiry instead carries a typed tombstone with no member path or bytes, an empty digest,
the terminal timestamp and the recorded expired size; import allocates/remaps a collision-safe final key
but creates no staged or promoted object journal row.
A photo deleted by abandoned-upload cleanup (phase 11) is simply absent: it contributes no row, no member
and no tombstone; a `cleaning` row refuses export like `expiring`, and import regenerates any private
key an `EvidenceAbandonedUploadReceipt` reserves even when storage reports it absent.

**Lane D D3 freezes one-shot recipients and source bytes as one immutable capture lineage (rewritten
P1b, #111 Q7).** `export_portable_tenant_dump --recipient <age key> [--recipient ...]` supplies the
tenant recipients for THIS export only. `tenant_dump_recipients.one_shot_tenant_recipients` canonicalizes
each key, refuses an invalid, duplicate or platform key and an empty set, and the request transaction locks
the makerspace row and stores the canonical `{public_recipient, fingerprint}` set on the capture
(`tenant_recipients`) with a `tenant_dump_requested` audit carrying only fingerprints. There is no
standing recipient state, no custody state, no alarm outbox and no recipient-change refusal: one-shot
keys cannot change after the request. If object deletion fails, the refused capture retains the private
unpublished key as a retry journal; `cleanup_refused_tenant_dump_artifacts_task` retries it hourly, and
only confirmed deletion clears the key.

Phase S uses a `copy_capture` source-gate purpose and exports one PostgreSQL `REPEATABLE READ` snapshot to a
full custom database image while copying the exact object closure under the same frozen source. Database and
object-ledger SHA-256 facts, gate owner/fencing token, source identity, PostgreSQL major, encryption mode,
catalog digest and completion time are committed before a live fenced release reopens the source. D2 then
works only from those staged bytes. Run-owned filesystem and scratch-database markers make crash cleanup
conservative: sweepers delete only marked Lane D resources, never an operator database or unmarked directory.
The final `spaceworks-tenant-dump-v1` manifest binds the parent database digest, parent object-ledger digest
and derivation-policy digest; companion slices are forbidden in this format. Publication also requires a
fail-closed negative proof that no external audit anchor exists for the tenant.
The attestation scheduler and final Lane D publication share the audit scope advisory lock, so anchor
activation/sealing/publication cannot race between the negative proof and the discoverability commit.

**Lane D D4 makes outer readability and tenant-DEK custody separate cryptographic facts.**
`outer_recipients` is the one-shot tenant set plus the platform recipient, always (superadmin is always
on). `tenant_dek_recipients` is always exactly the one-shot tenant set and never gains the platform
recipient. The age command builders consume those distinctly named sets directly; a missing or invalid
`BACKUP_AGE_RECIPIENT` refuses the build. `spaceworks-tenant-dump-v1` does not call the obsolete
`spaceworks-tenant-migration-v1` `archive_envelope.py` layout, whose platform-readable member contains
plaintext DEKs. `DERIVATION_POLICY_VERSION` is 6: the manifest's `source` block no longer records a
request-time superadmin decision.

A plaintext source is scanned across every registered mapped raw column and refuses if any non-empty value
has the PII-envelope prefix. Its manifest declares `source_pii_mode=plaintext`, an empty retained-key
inventory and a `present=false` content-ledger entry for `keys/tenant-deks.age`; that member must not exist.
An encrypted source refuses non-envelope mapped values, and the scratch plus restored-dump digest checks bind
the exact raw ciphertext. The source makerspace PK and every mapped-row PK are compared explicitly because
they form AES-GCM AAD and cannot be remapped. `MakerspaceEncryptionKey`, `PiiBlindIndex` and
`SearchKeyGeneration` remain DROP tables and are verified empty in `database.dump`.

For encrypted sources, D4 enumerates the source key rows from the restored immutable database image and
retains only exact active/rotated rows. Identity, makerspace, version, status, recorded broker coordinates,
wrapped bytes and wrapped-byte digest must equal that frozen enumeration; missing, duplicate, extra,
disabled-as-live and live-source-substituted rows refuse the build. The parent process handles only wrapped
bytes, non-secret inventory and resulting ciphertext. One short-lived helper receives wrapped rows over an
anonymous stdin pipe, disables the DEK cache, unwraps each row once through its recorded source broker and
streams a length-framed `(makerspace_id, version, status, DEK bytes)` payload to one age process addressed to
every `tenant_dek_recipient`; ciphertext returns through anonymous stdout. Failures terminate and reap child
processes, close pipes/caches, and remove partial ciphertext and staging before a generic secret-free error.
The bounded guarantee is only that no Lane-D-created persistent application output retains a plaintext DEK
after this operation. Python buffers, privileged host observation, process dumps, OS core dumps and swap
remain outside that application-level guarantee; cache clearing is best effort and is not secure zeroization.

Only `keys/tenant-deks.age`, its ciphertext size/digest and the non-secret retained-key inventory enter the
sanitized inner bundle. Its payload-member ledger is a positive allowlist: `database.dump`, the conditional
tenant-DEK envelope and opaque SHA-256-named private/public object members; `manifest.json` is admitted only as
the encrypted inner manifest at the sealing boundary. The inner bundle is streamed directly into `payload.age`
without a plaintext tar on disk. A canonical two-member outer tar then carries separately readable
`outer-manifest.json` plus that ciphertext. The outer manifest has an exact structural allowlist containing
only artifact/capture identities, recipient fingerprints, ciphertext size/digest, source-build/PostgreSQL
compatibility facts and content-ledger digest/count; its reader validates the canonical wrapper and re-hashes
`payload.age` before any caller may decrypt it. The plaintext derived directory is removed before derivation
commits. The derivation-policy version is bumped whenever this custody/layout contract changes, and publication
re-verifies the source mode, mapped findings, key inventory and content-ledger declaration against the immutable
capture.

**Lane D D5 reconstructs target cryptography only from tenant-held proof.** Before any target
state is changed, `tenant_dump_target_identities.py` accepts only absolute regular files that are mode `0600`
on a non-root read-only host mount. Raw identities in argv or environment are refused. Each file is streamed
to `age-keygen -y`, and the resulting canonical recipient/fingerprint set must equal the one-shot tenant-DEK
recipient set exactly; the platform-only outer identity therefore cannot pass. The path and identity bytes are
never copied into target operation storage or database state.

After restore, source broker rows, generic/event blind indexes and search generations must all be absent.
`tenant_dump_target_deks.py` binds the earlier identity preflight to the exact manifest and inner-ciphertext
digest, then starts one bounded process group. Only `tenant_dump_target_helper.py` opens the identity mounts,
streams the inner age plaintext, compares every `(makerspace_id, version, status)` record to the manifest and
feeds the iterator to `import_keys.install_streamed_deks`. That installer wraps under the configured target
broker while preserving the source makerspace PK and version and commits exactly one ACTIVE row. The parent
handles no plaintext DEK; helper failure kills its process group and the database transaction rolls back.
`dek_cache_disabled()` clears both sides of the sensitive scope. This is the same bounded application-level
retention guarantee as D4, not secure zeroization: the helper, target broker, Python buffers and privileged
target host can observe plaintext transiently, and process dumps or swap are not claimed to be protected.

The target creates a fresh generation bound to its own `PII_SEARCH_HASH_KEY`, rebuilds every generic and event
blind index, runs strict encryption readiness and performs authenticated deterministic sample decrypts while
the makerspace remains `IMPORTING`. The one-shot recipients prove possession at DEK install and are not
kept on the target: no recipient rows, reservations or custody states are created, and activation
(`target_cutover._require_lane_d_readiness`) re-runs encryption readiness only.

- **Phase 4's archive projection DECRYPTS mapped PII.** `archive.source_value` reads fields through
  `getattr`, and `ScopedPiiModelMixin.__getattribute__` decrypts — so a PORTABLE archive built on it
  contains **plaintext**, and the target then calls `parse_envelope()` on plaintext and aborts.
  PORTABLE needs a raw-column path (`row.__dict__[attname]` / `.values()`).
- **Do not reuse Phase 7's `PendingImportedMembership` / `ImportedUserReconciliation` for migration.**
  Both are makerspace-FK'd (so cannot hold a pre-tenant decision), the former rejects an empty email
  at the database level, and its adoption path discovers rows by `email__iexact` **on every social
  login**. The anonymous OIDC walk-in transition has the same shape. **Phase 7 built safe mechanisms
  whose safety depends on a target-authorized person having authored the input** — a foreign archive
  is not that person.
- **A Space Manager must never obtain a PORTABLE archive**, and authorizing the export *request* does
  not authorize the *closure*: a manager can plant unrelated global accounts into the user closure
  with an ordinary invitation or a membership for an existing username, and PORTABLE emits their
  email and phone. Phase 4 already forces `REDACTED` for Space Managers.
- **`REDACTED` is NOT a PII-free fidelity, and its name has already misled one review.** The line
  above is a narrow, true contrast — the **global-user closure** at `REDACTED` emits only `id` and
  `username` (`data_export/fields.py:9`), so platform account email/phone do not travel. But every
  field without an explicit disposition falls through to `Emitted()` (`fields.py:139`), so the
  scoped-PII mapped fields on makerspace-owned rows — requester/attendee names, emails and phones on
  `HardwareRequest`, `EventRegistration`, `Booking`, `MachineServiceRequest`, `MachineUsageEntry`,
  `EmailLog` — **are decrypted and emitted in plaintext**. That is deliberate, shipped and pinned by a
  byte-regression test (`tests/data_export/test_portable_external_refs.py:190` locks `requester_name`
  readable), so **do not "fix" it as a leak**. What it redacts is audit meta and custom-form answers.
  Owner decision 2026-08-22: behaviour unchanged, the label and disclosure copy now say so.
- **Verification must measure authority CONFERRED BY THE IMPORT**, not total effective authority —
  the latter is unsatisfiable for a legitimately linked target superadmin, since `rbac` grants
  superusers everything.

**The source gate uses transaction-scoped advisory locks, including through a transaction pooler;
it must NEVER wrap the application request or task connection in a transaction.** The drain guarantee
needs every tenant writer to hold a shared advisory lock that quiescence's exclusive acquisition must
wait on. Request/task boundaries therefore open a dedicated lock-only database connection, begin a
transaction there, acquire `pg_advisory_xact_lock_shared`, and keep that transaction open only for the
boundary lifetime. A direct PostgreSQL connection retains that transaction, and a transaction pooler pins
one backend until it ends, so no lock or unlock statement can land on a replacement backend. The normal
application connection remains outside `atomic()`: SMTP and other external calls still observe
`in_atomic_block == 0`, and an external failure cannot roll back an earlier attempts increment.
Before dispatch, the lock connection queries `pg_locks` on its own backend and refuses unless the exact
namespace/key lock is still granted; a runtime that cannot retain the transaction lock is never assumed safe.

Acquisition or transaction setup failure raises the typed `SourceMigrationGateUnavailable` before dispatch;
HTTP returns 503 and tasks fail, so an unknown or unsupported runtime refuses the write. Release is one
idempotent rollback/close per acquired reference, and nested boundaries retain independent shared references.
`assert_write_allowed` therefore supports three shapes: at a request/task boundary it reuses the
already-held dedicated lock transaction, INCLUDING inside nested application `atomic()` blocks (never
reacquiring on another connection behind a queued exclusive migration lock); without a boundary,
inside an existing `atomic()` it takes the shared lock in that transaction,
and a direct non-atomic call takes a temporary dedicated lock transaction. External I/O inside an
application lock-holding transaction stays banned; the separate lock-only transaction does not contain
application writes or external I/O.

**The gate may refuse a request; it may never CHANGE one.** `_makerspace_id()` resolved the tenant
with `get_public_makerspace()`, which raises `Http404` for an unknown, archived or non-public slug —
so a route that was going to answer 403 answered 404 instead, and the gate had silently rewritten an
authorization outcome (`test_every_refused_matrix_entry_returns_403[public-membership-request-POST]`
caught it). Every resolution helper the gate calls must be non-raising: unresolvable means "no tenant
known here", which falls through to the unscoped lock, never a rejection. Refusal requires a
*resolved* tenant — an unresolved one must not 423 either, or a single tenant's migration takes down
every unscoped POST on the deployment (login, refresh, password reset, the import control plane).
The shared lock still covers those requests, so the drain guarantee survives the fail-open refusal;
totality is then the AST coverage guard's job, not the middleware's.

**A new model needs BOTH a model classification and a user-edge decision, and the second is the one
that gets missed.** `SourceMigrationGate.actor` and then `TenantImportJob.actor` each failed
`test_complete_registry_is_valid` after being correctly registered as `OmittedModel` — the model
classification says nothing about the model's FKs to `accounts.User`, and a stray user edge would
pull that account into the PORTABLE global closure. Both are declared as excluded. This was missed
twice in consecutive parts; when adding a model, enumerate its user FKs as a separate step.

**Deployment-global uniqueness is now introspected, not hand-listed.** `projection_guards` scans
every model in `EXPORTED_MODELS` for uniqueness rules **not scoped by makerspace** — field-level
`unique=True` included, which is how `boxes.QrCode.payload` slipped through and blew up a same-
deployment round trip on `boxes_qrcode_payload_key`. All **39** discovered rules carry an explicit
disposition in `unique_values.py`. Eight are **preserve-unless-collision** (`QrCode.payload`,
`Box.code`, and the six private-bucket `object_key` columns): preservation is the default because a
regenerated QR payload silently invalidates a label physically stuck to a box, and regeneration is
per-colliding-value, never per-model, is added to `regenerated_fields` so the pre-commit uniqueness
check covers it, and is **counted in the operator report** so the regeneration is visible.

**A raw cursor returns `jsonb` as a STRING.** Django's psycopg2 backend decodes JSON at the *field*
layer, not the connection layer, so `ReferenceState`'s temp-table reads handed back `detail` as text.
Every consumer had only ever tested the record for existence, so it went unnoticed until the first
caller read into it. `get()` now parses it. Expect the same anywhere this codebase reads `jsonb`
through `connection.cursor()`.

**A same-deployment round trip can never observe key PRESERVATION, and that is the harness, not the
rule.** Source and target share one database and one bucket in tests, so every carried object key
and QR payload collides with its own source row. A preservation test must first remove the source
row and object *after* the archive is built — which is exactly what a target deployment that has
never seen the key looks like. The collision check itself consults the **object store** (`head_object`),
not the row table, because the constraint being protected is storage-key uniqueness in the target
bucket; that also catches an orphaned object squatting a key.

The same rule governs a **non-regenerable** identity, and there the harness cannot simply let the
collision happen: `unique_values` marks two policies whose "generator" only raises —
`events.EventCheckInEvent.operation_id` and `events.EventAttendanceCertificate.serial`, both PRESERVE,
both meant to STOP an import rather than remint an immutable value. A collision cannot occur between
two real deployments (`pairing` refuses a same-deployment move outright), so a test that meets one has
modelled the world wrong. `SimpleImportCase.release_non_regenerable_identities()` drops the local rows
carrying such an identity — through the `app.allow_immutable_delete` hatch, because
`EventCheckInEvent` is trigger-immutable and cannot be re-stamped — and it is driven off a
`_refuses_collision` marker so a future refuse-policy is covered without touching the harness. Call it
after the source objects are captured and before materialization.

**A DROP disposition is enforced at BOTH ends, and they are not redundant.** PORTABLE export omits a
drop-disposition row entirely (`admission.export_row_policy`) — `MembershipRequest.invite_email` is a
stranger's email address, and a row that can never become live has no business travelling to a
foreign deployment. The importer still refuses such a row, because the archive is not always one your
own export produced: a crafted or older archive is precisely what that guard exists for. Export-side
omission is PORTABLE-only, so the Space Manager's REDACTED export is unchanged.

**Closure admission, as built.** The export computes the exact global-user closure **after** the
retain/drop/stage dispositions are applied, canonicalizes it, and binds a source-superadmin approval
to its **digest** — if the closure changes, the approval is void and the export refuses rather than
disclosing someone new. An unapproved identity's PII is omitted and replaced with an opaque inert
reference; if a retained non-null relationship cannot be reconstructed without it, the export aborts.
Two adversarial tests plant an invitation and an active Member membership for an unrelated global
account and assert on the **archive bytes** that a blanket approval discloses neither.

**Do not discover a field by guessing its vocabulary.** `target_state._state_field_name()` scanned
every concrete field for one whose `choices` contained `IMPORTING`/`ACTIVE`/`ABORTED`. That existed
only while the lifecycle column was hypothetical; it crashed the moment a field with `choices=None`
appeared (`getattr(field, "choices", ())` returns `None`, not the default, when the attribute exists
and is None) and it would have bound to the wrong column the first time another field shared those
values. `Makerspace.lifecycle_state` is real — name it.

**One genuinely pre-existing flake was fixed, not papered over.** The encryption tests corrupt
ciphertext by flipping a base64url character, but non-canonical endings can decode to identical
bytes because the difference lives only in discarded padding bits — so roughly 1 in 16 corruptions
decoded cleanly and no rollback happened. The decoder now requires canonical base64url. Our own
encoder always emits canonical output, so stored envelopes are unaffected.

**Import staging is asynchronous; the request only receives bytes (2026-10-16).** `POST .../imports`
streams the `archive` part through `import_upload.ImportArchiveUploadHandler` straight into
`BACKUP_OPS_DIR/tenant-imports/` (one write, size-capped while streaming), creates a `PENDING` job with
`tenant_migration.import_upload_received`, and answers 202. The handler is installed in
`initialize_request()` because the superadmin permission can read `request.data` before `post()`, and
`dispatch()` deletes every file the handler wrote that no committed job owns. Decryption, the digest check
and manifest validation run in `stage_import_job_task`, which alone moves a job
`PENDING → AWAITING_IDENTITY | READY | FAILED` and records `import_created` or `import_staging_failed`.
Rules that must hold:

- **One owner per staging run.** The task claims a 6-hour `PeriodicTaskRun` lease named
  `tenant-import-staging:<job id>`; its `last_run_at` is the attempt token.
- **Paths are fenced, content is not.** Every create, rename or unlink of the archive, its sidecar or the
  fixed `.rows.age.part` happens inside one short transaction that locks the lease row, then the job row,
  and re-checks token, existence, `PENDING` and expiry. Bytes go through an already-open descriptor. Expiry
  cleanup keeps the same lease-then-job order, so a stale or out-raced attempt can never write, publish or
  delete another attempt's file, and no file outlives its job.
- **The identity endpoints read a rows-only sidecar.** Staging seals every decrypted member except
  `objects/**` (carried DEKs are never on disk) to the target's own age recipient as
  `<archive>.rows.age`. Identity GET/POST refuse a `PENDING` job before any archive I/O (409
  `import_staging`). Only a job staged before this change, which has no sidecar, still reads the full archive.
  `schedule_import_archive_unlink` removes the archive, the sidecar and the part together.
- **Brokerless deployments never stage in a request.** With `CELERY_TASK_ALWAYS_EAGER` the view does not
  dispatch; `resume_stale_pending_import_jobs` (run by the existing finalization-recovery task) stages
  `PENDING` jobs older than two minutes with no live lease, so the cron service does the work. A failed
  enqueue also leaves the job `PENDING` for that sweep. It never fails the job, because the error does not
  prove the message was lost.
- **Brokerless runs are scheduled and fenced.** Claiming `READY -> MATERIALIZING` stores the
  requester's `actor_id` and `target_identity` in `run_request`; `actor` remains the uploader.
  Eager-mode views return 202 without dispatch. `resume_stalled_materializations` (every
  deployment, two-minute grace) re-dispatches persisted requests whose run lock is free: without a
  broker it is the only executor, and with one it recovers a run that lost its lock connection
  before commit. It probes the lock first and skips live runs. A missing,
  deleted or demoted requester fails with `forbidden` and `tenant_migration.import_run_refused`
  before archive I/O. Every materializing execution, with or without a broker, holds an advisory
  transaction lock in namespace `734311` on a dedicated psycopg2 connection for its lifetime;
  `SET LOCAL idle_in_transaction_session_timeout = 0` protects that idle lock transaction.
  While holding the job row lock, it rechecks lock retention through `pg_locks` before claiming
  a fresh `run_attempt` UUID. The commit transaction checks that token and rechecks lock retention
  before committing. No claimed token means no failure transition or cleanup; superseded attempts
  cannot commit or clean shared objects, and failure transitions match their token. A concurrent
  object-journal insert uses a savepoint and adopts the matching winner's `target_key` and
  regeneration flag. Finalization keeps its existing promotion leases; cleanup deletes nothing
  new, and terminal scrubbing clears both run fields.
- **The staff console uploads resumable chunks.** `POST .../imports/uploads` starts an `UPLOADING`
  job with a declared `upload_total_bytes` (1 byte through 20 GiB), an empty private 0600 archive
  in the 0700 imports directory, and `import_upload_started`. The single multipart `POST .../imports`
  remains available; its whole body must still fit the request timeout.
- **One bounded parse before locking.** `PATCH .../imports/<id>/archive` accepts only
  `application/offset+octet-stream`. `OffsetChunkParser` requires an integer `Content-Length` in
  `1..8388608` and reads exactly that many bytes, refusing short reads. The view consumes
  `request.data` before locking, including when a permission causes an earlier parse. No network
  I/O runs in the transaction. Wrong media types return 415; invalid lengths/offsets and size
  overflow return 400. CORS permits `Upload-Offset`, and the chunk route uses its own
  `tenant_migration_upload` throttle (`THROTTLE_TENANT_MIGRATION_UPLOAD`, default `1200/min`).
- **The database offset owns progress.** Under the job row lock, the job must be `UPLOADING` and
  unexpired, and `Upload-Offset` must equal `upload_received_bytes`; mismatch is 409
  `offset_mismatch` carrying that authoritative byte count. A chunk cannot exceed the declared
  total. Its bounded local write, flush and fsync precede the received-count update and
  `import_upload_chunk_received` audit (`import_id`, `offset`, `chunk_bytes`, `format_version: 1`)
  in the same transaction. A rolled-back write may leave unacknowledged bytes, which a retry
  overwrites at the database offset; staging verifies the complete archive digest.
- **Expiry is sliding and rechecked while locked.** Start and each successful chunk grant 24 hours
  of idle time. Cleanup locks staging lease rows before job rows, then rechecks expiry and
  `target_makerspace IS NULL`; only still-expired pre-tenant jobs and their leases are deleted.
  A chunk that refreshed expiry while cleanup waited survives with its file. Object rollback
  stays outside the deletion transaction; uploading/pending jobs have no imported objects.
- **Completion is idempotent.** `POST .../imports/<id>/archive/complete` requires received equals
  total (otherwise 409 `upload_incomplete`), switches `UPLOADING` to `PENDING`, resets expiry to
  export retention, and records `import_upload_received`. Dispatch happens after commit and follows
  the same brokerless/recovery rule as multipart uploads. A fully received job already past
  `UPLOADING` returns 202 without another audit or dispatch. Staging, run and recovery claims never
  accept `UPLOADING`; identity GET/POST refuse it before archive I/O with 409 `import_staging`
  and "The encrypted archive is still being uploaded."
- **Client recovery uses server state.** Start immediately updates detail/list caches, even if the
  first chunk fails. The console sends 8 MiB slices, reconciles failed chunks through job GET and
  retries up to three times with backoff. A lost completion response is reconciled through GET;
  a non-uploading job has completed the upload. Interrupted cards require a file of the original
  size to resume; staging's digest check still refuses a different file of equal size. Uploading
  jobs are not polled. Detail and list caches refresh on success or failure.

Deployment prerequisite: nginx's `/api/` limit must be at least 10m (`c422fb1a`); ship that
change with chunked upload. It accommodates an 8 MiB chunk, not the legacy whole-archive POST.

## Organization accounts and organization-derived authority

### Organization self-service and governance (Lane F)

Self-creation is a global platform switch, default OFF, never a makerspace module.
Active verified unrestricted accounts create bounded private organizations under
an account-row lock. Immutable creation audits enforce the rolling daily limit
even after deletion. Initial membership grants global governance only, never
tenant actions, identity, links or ownership. Link governance remains superadmin-only.
Governance mutations require recent reauthentication, preserve the last active
member governor and recheck non-escalation on suspended-member reactivation.
Deletion refuses tenant links, retained domain references and artwork; disposable
memberships/invitations are removed only with an otherwise deletable organization.
Tenant/module purge never deletes shared organizations or foreign organizers.
Existing global retention and portability exclusions remain; this adds no org model,
tenant-owned field or object key.


- **Admission membership is not authority.** The always-present `organizations/audience.py`
  checks active direct memberships and active memberships in OWNER-linked servable
  makerspaces against explicit organization IDs. It ignores action grants and profile-publication
  consent and never widens RBAC. Events supplies its own live organizer/venue candidate set;
  bookings imports no events policy. Owner-link admin writes use the console mutation service,
  and the Organization inline is read-only to preserve makerspace-before-organization locks.

- **New makerspaces require an owner organization through installer, API, staff console and `/control/`.**
  These entry points share `organizations/services_owner.assign_owner_organization`: exactly one active
  existing organization ID or a new name, with organization creation, the owner link and their audit
  entries in the same transaction as makerspace creation. Lock order matches `change_link`: check
  `visible_spaces`, call `assert_write_allowed` (the shared migration gate), lock the makerspace with
  `select_for_update`, then lock the organization. New names always create a new organization with a
  unique slug. Installer setup asks for the organization name as its own required question and preserves an
  existing owner on reruns, rechecking under the makerspace lock. Existing ownerless makerspaces are
  untouched by migrations and remain usable; explicitly rerunning `setup_instance` can assign an owner (a migration-frozen
  space is skipped with a warning; only a brand-new space fails the whole setup).
  Tenant import and `seed_e2e` are the exceptions to the creation requirement: a tenant dump carries no
  organization rows, so an imported target is created ownerless, and the development seeder may create
  ownerless spaces. In `/control/` an owner failure after form validation (a concurrent deactivation, a
  migration gate) rolls the whole add back and returns to the add page with an error message, never a 500.
  An answers file saved before the organization question reaches `setup_instance` with an empty
  `--organization-name`, which defaults to the makerspace name.
- **An `Organization` is a platform entity, not a module.** It is creatable before any makerspace
  exists, spans makerspaces through `OrganizationMakerspace` (`owner | manager | affiliate`, at most
  one owner per space), and is therefore **not** a `module_registry` key: registry keys are
  capabilities stored in each makerspace's `enabled_modules`, and per-space enablement of a
  cross-space entity is incoherent. Always present, inert when unused.
- **Org grants confer ACTIONS, never IDENTITY.** This is the distinction that makes the whole
  feature safe, and every part of it is load-bearing:
  - `OrganizationMembership.granted_actions` is resolved into
    `rbac.makerspaces_for_action`, `effective_actions` and `can`; those are the canonical
    effective-action paths. The auth payload and locked role-service revalidation mirror that
    same filtered resolver, while completed-job collection alone inspects a direct organization
    grant for its deliberately narrower partition. None of these turns the grant into identity.
  - `_membership_for`, `membership_role`, `is_space_manager_identity` and `_membership_is_space_manager`
    stay membership-only, so an org admin holding `manage_inventory` across the org's spaces becomes a
    Space Manager nowhere.
  - `resolve_scope` / `scope_by_makerspace` stay membership-only too. They are **action-agnostic**, so
    unioning org scope there would let a single org action open every scoped list query in that space.
    Action-gated surfaces must prefilter with `scope_by_action` instead — that is what the events and
    bookings helpers now do, and what any other surface must do before org authority can reach it.
  - Staff-list endpoints keep listing `MakerspaceMembership` only: an org grant must never appear as a
    local staff row.
- **Mirroring memberships is impossible — do not try again.** `UniqueConstraint(makerspace, user)`
  (`uniq_makerspace_user`) allows exactly one membership row per user per space, so a mirrored org row
  cannot coexist with a local one, two orgs cannot both grant one user access to one space, and
  deleting one org's grant could strip locally-granted authority.
- **Org grants reach every servable linked makerspace, and both superadmin branches ignore them.**
  The superadmin is always on (#110), so there is no hidden space for a grant to proxy into. The
  servability filter lives in SQL inside `_organization_authority_memberships` (`servable_q`), so every
  present and future consumer inherits it.
- **`manage_machines` cannot be granted through an organization, at the RBAC layer.**
  `ORGANIZATION_GRANTABLE_ACTIONS` is `ROLE_GRANTABLE_ACTIONS - {MANAGE_MACHINES}` and every
  organization consumer filters through it **before** `expand_implied_actions`: `can`,
  `effective_actions`, action query scopes, staff-authority discovery and auth-payload projection.
  Therefore even a raw stored `["manage_machines"]` confers neither that action nor its implied
  `manage_printing` / `collect_service_request`. The organization admin form still rejects it as a
  second validation layer with an operator-facing error. `machines.role_scope.manage_scope_for`
  remains local-membership-derived; direct organization `manage_printing` is not type-manager
  authority.
- **Action-specific organization reach preserves 404 vs 403.** Role-set assignment, machine-service
  list/detail resolution, integration health, domain verification, asset warranty host/document
  resolution, the mixed warranty report, and procurement machine-type options resolve the union of
  local visibility and their explicitly accepted action scope. An unlinked or hidden/unservable
  tenant remains 404 through `_organization_authority_memberships`; a visible local actor lacking
  the action reaches the row and receives 403. The warranty report separately checks its accepted
  union (`EDIT_INVENTORY` or machine-derived authority), so visible actors with neither do not get a
  misleading 200/empty response. Dashboard and notification inbox remain deliberately
  membership-only.
- **Role mutations revalidate organization authority under locks.** After the makerspace and local
  membership/role are locked, `role_services` locks the relevant organization link, organization,
  and organization-membership rows and recomputes the filtered effective action set. Create,
  grant validation, rename/update and delete therefore cannot pass the org-aware view and then fail
  a local-only service check, nor race a concurrent organization authority change.
- **Native device payloads stay membership-only.** `X-Makerspace-Id` selection requires
  `validate_native_makerspace_scope()` to find an active local membership, so an organization-only
  space in a device payload would be advertised to the app and rejected on every selected request.
- **Auth payload contract:** every entry carries `source=membership|organization`. An org-derived entry
  has `role`, `role_id` and `role_slug` null with `role_name` naming the organization; a makerspace
  reached both ways appears **once**, as the membership entry, with the actions unioned. `user_payload`
  is deliberately O(1) in queries — resolve org spaces in one batched query, never per makerspace.
- **Purge scoping is the cross-tenant footgun.** Purging makerspace C deletes only
  `OrganizationMakerspace(makerspace=C)` and only `EventOrganizer` rows whose **event is hosted by C**.
  Never delete organizers via `organization__makerspaces=C`, and never delete the shared `Organization`
  or its memberships during a makerspace purge, however few links remain.
- **`Event.makerspace` remains BOTH venue and tenancy anchor.** Payments, PII key custody
  (`encryption/registry.py` scopes `events.EventRegistration` to `event.makerspace_id`), `host_waiver`,
  audit scope, storage quota and public venue routing all key on it. An organizer is attribution plus a
  narrow permission, never tenancy, and no organizer feature may move a number, a key, a quota or a
  route away from the venue.
- **Organization presentation is a global projection, not another tenant surface.** A public organization
  profile is opt-in (`public_profile_enabled`) and exposes only the explicit public serializer fields.
  Its event catalogue projects already-public, published, not-ended events and keeps each event's host
  makerspace visible; the host must remain servable, visible in the central directory and have the events
  module enabled. Switching either public-profile or host-module gate off hides the projection without
  deleting the organization, event or organizer bridge.
- **Organization governance is separate from makerspace RBAC.** `governance_actions` may authorize profile
  or membership administration, but never becomes a makerspace action and never changes a user's local
  role identity. Invitations store only a SHA-256 digest of a high-entropy, single-use bearer token; the raw
  token is returned once and must never enter list responses or audit metadata. Invitation creation and
  redemption both enforce non-escalation against the creator's current active authority under row locks;
  suspended memberships are never silently reactivated, and revoke/redeem races have one transactional
  winner.
- **Event organizer mutation has one service path.** `services_organizers.replace_organizers()` locks in
  `event -> makerspace` order, rechecks the events module and action-scoped event authority, requires an
  active membership in each newly assigned organization (superadmin excepted), replaces the bridge set
  atomically and emits one makerspace-scoped audit entry. It changes attribution only: the event's
  `makerspace_id`, routing, PII custody and quotas remain untouched.

## API client scopes and the protected-route registry

### Signed booking integration reads (BK-H)

`bookings.api_read` is an opt-in Bookings child without Events, Membership,
Reports or rail dependencies. `/api/v1/booking-integration/` always requires verified
HMAC, including when operator prefixes are overridden or public auth is optional.
Only tenant-bound active server clients qualify. `booking_resources:read` and
`bookings:read` independently authorize resource and reservation reads;
`bookings:attendance:read` requires reservation scope and adds only current
unreversed `arrived_at`, including retained completed arrivals. Read grant policy
is operator-only, outside browser and frozen legacy vocabulary. Resource grants
and user authority never authorize integration reads.

Core `apiclients/scope_registry_booking_reads.py` holds metadata without importing
Bookings. Live Bookings startup registers typed resource and reservation targets
in the existing read contract; cross-tenant/unresolved/hidden/unservable targets
deny. Tombstoning either domain removes only its own scopes, routes, prefixes and
features. All ten concrete GET/HEAD entries exclude legacy-v1. Explicit serializer
allow-lists omit contacts, answers, notes, credentials, forms and reservation money.
Only a released public page may add approved public price/currency, rule summaries,
published sections and backend image references through its nested allow-list; signed
resource authority never bypasses the canonical public visibility/release gates.
Names use scoped PII attributes with tenant relations loaded. Private resources
are readable by signed resource authority without making them publicly visible.

Reservation reads audit opaque principal/count/projection under the source fence;
failed audit cannot disclose data. Shared signed cursors bind client, tenant,
subject and attendance projection; responses are private/no-store. Booking grant
mutations retain the existing session-bound recent-reauth mixin; no second proof
system or user scope is introduced. Booking analytics routes are explicitly
allow-listed in `bookingAnalyticsRoutes.ts`, send route templates and empty
referrers, and exclude confirmation queries, private routes and credentials.

No model, field, User edge, object key, stored export or new PII storage is added.
Existing audit retention, target references and tenant purge apply; classification,
encryption, portability and the model-graph catalog pin remain unchanged by the read
projection. BK-F website data uses its canonical public release/visibility adapter.
Public detail/image/discovery routes remain public-scoped and never inherit server
booking or reservation scopes.

### Signed integration reads (Lane F)

`apiclients/read_contract.py` owns signature-marker permissions, typed tenant target
resolution, per-client throttling and signed keyset cursors. Live domain startup
registers adapters without queries; core imports no separable Events policy.
`read_prefixes.py` is safe during settings construction and makes signed reads
mandatory independently of optional public-client rollout. Only verified HMAC
receives the marker; user sessions, publishable keys and browser clients cannot.
Read scopes are operator-only, absent from browser and legacy-v1 authority. Targets
require exactly one live tenant and a subject belonging to it.
Participant scope requires event scope; attendance additionally requires participant
scope. Serializers use allow-lists and the scoped-PII model accessor for names,
never raw encrypted values, contacts, answers, credentials or money. Attendance
uses current status and immutable check-in history. Participant-read audit contains
opaque principal/count/projection only. Responses are private/no-store and cursors
bind client, tenant, subject and projection with 24h expiry. No new tenant model,
object key or purge ownership is introduced by these adapters.


- **`apps/apiclients/scope_registry*.py` is the single source of truth for what an `ApiClient` may
  reach**, and it is keyed on the **fully qualified versioned `view_name`** — never the bare name.
  Five inventory endpoints are exposed under both `/api/public/` and `/api/v1/public/`, so bare names
  collide.
- **Unknown-route denial is evaluated BEFORE any wildcard.** So neither `legacy:v1` nor `public:*` nor
  `admin:*` can ever authorize a route that is not registered. A protected route with no entry denies.
- **`legacy:v1` is frozen.** It authorizes exactly the entries marked `legacy_v1=True` at cutover. A
  route added later defaults to `False`: **legacy authority never auto-extends.** It exists because an
  empty `scopes` list used to authorize everything; migration `0004` preserved those clients without
  pretending their original read/write intent could be inferred. Tenant staff now explicitly grant only
  `public:read` and `public:write`; wildcards, every `admin:*`, `reports:read`, and `legacy:v1` remain
  global-superadmin-only. `ApiClient.issue()` requires a non-empty scope list, while `ApiClient.save()`
  keeps the compatibility fallback for `/control/` model forms and `seed_demo` direct construction.
- **Target resolution is independent of scopes, and an unresolved target denies.** The old
  `_path_makerspace()` returned the same `None` for "this path names no tenant" and "the tenant lookup
  failed" — a fail-open. `resolve_target` returns `(target, resolved)` so those are distinguishable.
- **The drift guard is measured per concrete `(view_name, method)` key of the protected routes.**
  Comparing view names alone would leave an obsolete authorization key behind when a handler drops a
  method or a route moves out from behind a protected prefix; a protected route whose methods cannot be
  derived at all is reported as its own drift class rather than silently skipped.
- **A widened `HMAC_PROTECTED_PATH_PREFIXES` must fail as a misconfiguration, not as blanket 401s.**
  A Django system check reports unregistered protected routes. Register checks with the
  **`app_configs` keyword** — Django calls them by keyword, and a mismatched parameter name makes
  `manage.py check`, `migrate` and `runserver` raise `TypeError` before startup. **pytest does not run
  system checks**, so a test must call the check the way Django does.
- **The HMAC signed message must stay unambiguous about the nonce.** The message is
  `METHOD \n PATH \n TIMESTAMP [\n NONCE] \n BODY`, so the nonce part exists only when `X-Nonce` is
  sent — which made a nonced request and a nonce-less request whose body is `NONCE + "\n" + body`
  encode to **identical bytes**, letting a captured signature be replayed without ever claiming the
  nonce. A nonce-less request whose first line is itself a well-formed nonce followed by a newline is
  therefore refused. The real fix is a fixed part count (always sign an empty nonce slot); it is
  specified as **protocol v2** because it changes the message for every existing nonce-less client,
  i.e. the default deployment.
- **The nonce namespace is `(client_id, nonce)` and is claimed exactly once per request**, shared
  across secrets. Never clear nonces on rotation.

## Container / deployment invariants

**The control plane reaches the bundled proxy only by operator opt-in.** `CONTROL_PLANE_PROXY` (default
`false`) is the only switch that routes `/control`, `/control/*` and `/mfa/control/*` through Caddy or the
website nginx; `CONTROL_PLANE_TUNNEL_PORT` (default empty, TLS layer only) is the only
way to publish the `127.0.0.1` HTTPS tunnel listener. Rules that must not regress:
- Values fail closed. Caddy imports `control-plane-{$CONTROL_PLANE_PROXY}.caddy`, so anything but
  `true`/`false` is a missing file and Caddy will not start; the nginx generator
  (`frontend/docker-entrypoint.d/40-control-plane.sh`) exits non-zero and so does the container. Compose must
  always pass a non-empty value: a Caddy placeholder default applies only to an UNSET variable.
- The browser's authority is never rewritten: Caddy keeps the incoming `Host` (no `header_up Host` /
  `X-Forwarded-Host` on these routes) and nginx sends `$http_host`. The MFA challenge binds its origin to
  `scheme://Host`, and Django's CSRF origin check compares the same, so dropping the port breaks the tunnel.
- `CONTROL_PLANE_ALLOW_CIDRS` matches the socket peer only (Caddy `remote_ip`, nginx `$remote_addr`, no
  `trusted_proxies`/realip), so a forged `X-Forwarded-For` cannot pass it. Both proxies answer 403.
- The tunnel listener terminates real TLS (Caddy internal CA) so Secure cookies, `SECURE_SSL_REDIRECT` and
  CSRF behave as on the public domain, strips `Strict-Transport-Security`, and serves nothing but the control
  plane and `/static/`. Its overlay is selected only for TLS layers, and the wrapper refuses it on Docker
  Engine < 28 (older engines expose `127.0.0.1`-published ports to neighbouring hosts); enumerating the
  alternative topology records never consults the engine.
- `.env` changes to these keys are applied with `scripts/apply-settings.sh`, which holds the update lock and
  `operation.lock`, pins every running application container's image ID before refreshing records, never
  pulls, and refuses build/SaaS layers and API-only behind an own proxy (`api-edge` has no route).
- `apply-settings.sh --control-plane on|off` (driven by installer option 6 /
  `scripts/control-plane-settings.sh`) rewrites those keys only AFTER taking both locks, and its rollback runs
  before releasing them: restore `.env`, then (once applying started) `refresh_compose_config` and Compose up,
  so the topology records never keep the failed `.env`'s digest. `refresh_compose_config` must therefore
  fail on the first failed record write, not report only the last one.

**The H1 host marker is a process boundary, and PostgreSQL grants are a separate authority
boundary.** Every application-image start must enter through
`backend/scripts/spaceworks_entrypoint.py` with one explicit role: `backend`, `worker`, `beat`, `cron`,
`migrate`, or `management`. The root-owned, fsynced marker is mounted from the separate host-state
directory read-only; it must never live at another writable alias under `BACKUP_OPS_DIR`. Missing,
unreadable, malformed, unknown-version/state, or database-identity-mismatched markers refuse startup.
Candidate preparation/health markers must classify that identity as a non-routable sibling; all other
states require the active classification. Candidate capability decisions use the live topology proof below,
not the pointer string or marker database name by themselves.
Sibling allocation is a two-stage durable transition: the supervisor first invalidates every armed nonce
and fsyncs a `candidate-preparation` **intent** marker carrying operation identity but no database name or
OID; only then may it create and independently query the sibling. It invalidates every armed nonce again
before atomically replacing intent with the **bound** marker through file fsync, same-directory rename and
parent-directory fsync. An interrupted allocation always rewrites intent and requires a new proven-empty
sibling. A pre-existing database is never adopted because its name matches, including after a crash between
the bound rename and parent-directory fsync; a supervisor-owned sibling may be destroyed and recreated only
after its durable run-owner marker matches. Intent never waits, retries or upgrades at the consume seam.
The state matrix is exact: `normal` and `acknowledged-normal` admit all roles;
`candidate-preparation` admits only `migrate`; `candidate-health` lets only `backend` proceed to the
single-use capability seam; and `quarantined-after-cutover` admits only `backend`. Role refusal happens
before the capability socket is contacted.

**The consume-only Unix socket is the sole writable launch-capability channel.** The root supervisor derives
the complete record from the fsynced candidate-health marker and appends/fsyncs it in the private host
journal: restore ID, sibling name/OID, endpoint plus queried database UUID (and
`pg_control_system().system_identifier` when permitted), outer artifact digest, capture ID, a random nonce,
the allowed role and expiry. Neither that record nor its facts enter Compose environment or command
arguments, and the private journal/signing key are never mounted in an application container. The entrypoint
denies the role first, queries the live database identity, then submits exactly one `consume` request through
the root-owned socket. The server authenticates the local uid, re-reads marker and pointer generation, matches
every fact, appends/fsyncs `consumed`, and only then signs a short Ed25519 launch grant. The entrypoint verifies
that grant with the read-only public key and immediately `exec`s. A crash anywhere after consumption spends
the nonce; replacement requires explicit `rearm` under the host operation lock. Expiry, every marker or
pointer transition/rollback, and terminal operation invalidate all armed nonces before their effect. The
host may issue a launch grant only against a BOUND marker whose database identity is verified against the
container's live query; an intent or half-bound marker is an immediate refusal and cannot consume a nonce.
The identity is never inferred from the pointer, Compose environment or any container assertion. The
socket exposes no read/list/write-filesystem operation. This replaces—do not implement alongside it—Lane D's
superseded `capability.pending → capability.consumed` file-rename protocol.

**Host effects resume from one fsynced append-only run ledger under one host lock.** The supervisor acquires
`/var/lib/spaceworks/ops/operation.lock` before preflight on every new run and resume and retains the `flock`
until exit. The descriptor is close-on-exec and is never inherited by a Docker-launched process. Every effect
has an exact `{run_id, artifact_sha256, phase, state, attempt, started_at, finished_at, detail}` `begun` record
fsynced before it runs and a `done` record fsynced after it completes; resume selects the first phase without
`done`. An interrupted `database-restore` attempt can resume only against a different, proven-empty sibling.

**Lane D target restore is one ordered, fail-closed H1-supervised operation.** Static preflight is read-only
and independently proves artifact/build/schema/PostgreSQL/encryption/tenant facts, object capacity, approval
input, exact current/source/scratch/sibling identities, privilege probes, provider isolation, the complete
writer set and pointer CAS before allocation. It then persists the offline state, excludes every image
writer, obtains and re-reads any external scheduler's zero-active fence receipt, and only then allocates a
distinct empty non-routable sibling. Restore is exactly `pg_restore --exit-on-error --no-owner --no-acl`;
the child receives a scrubbed environment and a temporary mode-`0600` pgpass file, never a password in
argv, `PGPASSWORD`, the run ledger or the raised error;
the maintenance owner and narrow runtime grants are re-established before any Django target command.
Target state uses the distinct `target_import` recovery mode—never `enter_quarantine()`, because quarantine
invalidates imported passwords. Object writes are pre-ledgered as `created_by_this_run` or
`accepted_existing`; only the former may be rolled back. Activation order is immutable: verify, pointer CAS,
set NORMAL against the explicitly queried new identity and fsync away the host gate, start every writer and
prove its marker, then fsync the final ledger record while the supervisor still owns the lock. A completed
cutover on re-entry requires both the pointer tuple and target database marker to match its ledger record.
Missing recovery singleton rows and unknown recovery modes are routing-denied, never treated as NORMAL.

**The Lane E compound cutover coordinator was deleted in P1b (2026-10-27).** It only ever restored a
partial archive (one carrying sovereign slices); with the superadmin always on no such archive exists, and
`backup_control_preflight` refuses one before any effect. Whole-server restore is `scripts/restore.sh`.

**Every legacy `scripts/restore.sh` `pg_restore --no-owner --no-acl` is followed immediately by shared
role/grant reprovisioning before the next Django command.** This includes failure rollback, interrupted-run
rollback, the temporary diff database and final replacement. The grant-only bootstrap derives the target
database path inside the privileged container, carries no password in argv or `PGPASSWORD`, and suppresses
driver exception detail so a credential-bearing DSN cannot reach host logs. The existing mode-`0600` pgpass
contract remains mandatory for the Lane D subprocess adapter.

**External schedulers participate through durable provider control-plane state.** The D7 adapter invokes
idempotent `stop`, `fence`, `status`, `restart` and `readiness` operations with exact run/database/generation
tuples. Fence must prove all catalogued jobs disabled and zero active work, and resume must re-read the same
receipt. Restart/readiness must prove the new generation and database marker, exact job set/cadence, and no
old-generation dispatch. Local container state, the host marker and assumed credential propagation are not
scheduler receipts; a timeout or tuple conflict leaves the restore resumable behind its gates.

**Cloud interpolation state is initialized once, not borrowed from later shells.**
`scripts/init-cloud-environment.py init-from-current-environment` captures every variable referenced by the
Cloud Compose file from that one invocation, refuses missing required values, atomically fsyncs the private
static file plus H1 pointer, records only names/value digests, and requires `docker compose config` under a
scrubbed environment to reproduce the committed database URL. Later production Compose calls remain behind
the committed wrapper and its static/topology digest checks.

**The database pointer and generation are one authority record.** Bundled and Cloud Compose use the single
root-owned `/var/lib/spaceworks/ops/database-pointer.env`, written by file fsync, atomic same-directory rename,
then parent-directory fsync. Cloud layers it after `/etc/spaceworks/cloud.env`; bundled layers it after the
installer's static `.env`. `scripts/spaceworks-compose.sh` is the only supported production Compose launcher:
it validates owner/mode, scheduler declaration and recorded configuration digests; refuses unregistered file
or env overlays; unsets inherited `DATABASE_URL` and `SPACEWORKS_DB_POINTER_GENERATION`; and supplies static
environment first and the pointer last. External orchestrators must instead keep URL plus monotonic generation
in one versioned secret/config object and use store-native compare-and-swap on the expected version. A stale
version, non-monotonic generation, missing durability, incomplete writer rollout or unsafe sibling lifecycle
is refused.

**Database identity is queried deployment state, never inferred from the pointer.** Migration 0021 seeds the
immutable singleton in the active database. The readable-main artifact projection deliberately deletes that
row under the immutable-delete GUC, so a restored sibling must receive one new
`{database_uuid, run_id, artifact_sha256, capture_id, created_at}` row after restore and before admission.
Connection host/port/database/TLS trust identity plus the queried UUID is authoritative. PostgreSQL's system
identifier is corroboration only; inability to call `pg_control_system()` falls back to the UUID rather than
dropping server identity. A pointer comparison without the singleton is always refused.

Bundled databases use distinct maintenance and runtime identities. The application runtime role is a
non-owner without superuser, role/database creation, replication, or row-security bypass authority.
Entering candidate preparation writes the restrictive marker first, then makes that role `NOLOGIN`,
terminates its sessions, and revokes table/sequence writes; the maintenance owner remains the only writer.
Candidate health establishes read-only grants before marker admission; quarantine changes the marker first
because it does not widen the admitted role set, then restores runtime writes; worker readmission happens
only after writable grants. This ordering and the grant
boundary cover raw SQL and `docker exec` paths that never execute the image entrypoint. A topology whose
provider cannot establish and probe this split is unsupported, not degraded to an advisory process check.

**Readiness remains reachable in quarantine and is bound to the host marker.** The readiness route is in
the recovery allowlist and verifies the live database name/OID, no pending Django migration, every declared
reservation row count/digest, every declared enabled database-fence definition, and every declared
not-restored row count/digest.
The `candidate-backend` recovery profile has no normal `migrate` dependency. Empty declarations are valid
before E9 creates those database objects; E9 must populate exact declarations before candidate cutover.
An external scheduler is outside the image/marker boundary, so its topology must declare either the same
host gate or durable provider-control-plane disablement unless the marker is `normal` or
`acknowledged-normal`. The topology
validator refuses an external scheduler declaring neither; Lane D additionally refuses to run external
mode without the provider callback adapter and its durable fence/status contract.

**Ordinary image processes run unprivileged.** `backend/Dockerfile` creates uid 10001 `app`, uses `COPY --chown`
(a later `chown -R /app` would duplicate the whole tree into a second layer) and drops `USER app`
before ENTRYPOINT/CMD. The only bundled overrides are the short-lived root
`orchestration-init`/`orchestration-ready` services: they run the fixed bootstrap entrypoint to provision
database grants and the root-owned marker, expose no network service, and carry no arbitrary application
command. Do not put migrations, Django management commands, or a shell into those privileged services.
Two paths must stay writable and owned by `app`: `STATIC_ROOT`
(`/app/staticfiles`, written by the boot-time `collectstatic`) and `/var/lib/celery`. In **dev** the
`./backend` bind mount is owned by the host user, and `makemigrations` has to write into it, so
`docker-compose.dev.yml` sets `user: "${DEV_UID:-1000}:${DEV_GID:-1000}"` on `backend` only —
worker/beat stay on the image uid because they only ever write to `/var/lib/celery`.

**Celery beat must be given an explicit `--schedule`.** It otherwise drops its shelve in the CWD:
under the dev bind mount that wrote a **root-owned `celerybeat-schedule` into the repo working tree**,
and post-hardening `/app` is not writable at all. Both the base and prod compose point it at the
`celerybeat_data` named volume so last-run timestamps survive a restart (otherwise every periodic task
re-fires on boot).

**Never split a shell command across lines in a YAML folded scalar (`>`).** A more-indented line keeps
its newline instead of folding to a space, and a newline inside `sh -c` terminates the command. Splitting
gunicorn's flags one-per-line made it run bare — silently falling back to its **127.0.0.1** default while
each flag became a failing command. The killer detail: the healthcheck probes `localhost`, so the
container reported **healthy** while nginx got connection-refused and every request 502'd. Keep the whole
invocation on one line. A healthcheck that probes localhost cannot detect a localhost-only bind.

**`mc cors set` is unusable — CORS lives on the MinIO server.** Modern `mc` sends S3 XML and rejects the
JSON the compose file used to write ("decoding xml: EOF", exit 1). Because `backend` has
`depends_on: createbuckets: service_completed_successfully`, that exit-1 left backend and frontend stuck
in `Created` — **`setup.sh` could never bring the app up**. Origins are now set with
`MINIO_API_CORS_ALLOW_ORIGIN` (comma-separated) on the `minio` service, fed by `MINIO_CORS_ALLOWED_ORIGINS`;
`createbuckets` provisions buckets/policies only and runs under `set -e`. The old
`MINIO_CORS_ALLOWED_ORIGINS_JSON` is gone from compose, both installers and the docs.

**Browser-facing storage URLs must name the real host, never `localhost`.**
`AWS_S3_PUBLIC_ENDPOINT_URL` / `PUBLIC_IMAGE_BASE_URL` are baked into presigned evidence upload/view URLs
and every public image `src`. The compose default (`http://localhost:9000`) makes a deployment work only
from the server console and show broken images to everyone else, so `setup.sh` writes both
from the answered web address. The compose default is kept (not made `:?` required) so existing
deployments don't hard-break on upgrade.

**`.dockerignore` patterns are root-anchored.** A bare `__pycache__`/`*.pyc` does not match nested
directories — every `apps/*/__pycache__` was shipping inside the image. Nested patterns need `**/`.

**Production compose defaults that are not optional:** ordinary long-running services carry
`restart: unless-stopped` (via the `x-restart` anchor) or the stack does not survive a host reboot, and a
capped `json-file` `logging` block (via `x-logging`) or container logs fill the host disk. Third-party
images are pinned to a verified release tag — **verify a tag actually resolves before pinning it**
(the old `minio/mc` release tags did not match the epoch in the image's `release` label).
**Object storage is Silo (`pgsty/silo`), the maintained fork of the archived MinIO server.** One
pinned image (`SILO_IMAGE_TAG`) serves both the `minio` service and the `createbuckets` job, because
it bundles `mc`. Keep the `minio` service and `minio_data` volume names: renaming the volume orphans
every existing install's objects, and `http://minio:9000` is baked into endpoint settings. Verified
2026-10-13: Silo reads a MinIO `RELEASE.2025-09-07` volume as-is — buckets, object versions,
versioning and the public-read policy survive with no migration step.

**GHCR retention must protect the whole OCI graph, and must fail closed.** `docker/build-push-action`
leaves provenance attestations on by default, so every published tag is an OCI **index** whose
platform manifest and attestation manifest are separate, **untagged** GHCR package versions. A
retention rule that keeps versions by tag alone therefore deletes exactly those children and leaves
every tag dangling — `docker pull` then fails with `manifest unknown` for every tag while the tag
list still looks healthy, so the registry appears fine until someone installs. This happened: it is
why `scripts/ghcr-retention.py` exists and why the decision is digest-based. Two rules follow.
**First, a kept root protects its children**: discover them with
`docker buildx imagetools inspect --raw <image>@<digest>` and retain every digest in
`.manifests[]`. **Second, discovery failure vetoes deletion for that entire package** — treating an
inspection error as "this index has no children" reproduces the outage precisely, so the veto is not
caution, it is the invariant. The cleanup step is `continue-on-error: true`, which means a broken
implementation that silently stops deleting is invisible in CI; the fixture-driven tests in
`backend/tests/test_ghcr_retention.py` are the only thing that can catch it, and they cover both
directions — children survive, and genuinely stale versions are still deleted. `release.yml` runs
`scripts/verify-release-images.sh` after cleanup so a release that orphaned its own images fails at
the release rather than at the next person's install.

**GitHub Release history is PERMANENT; container versions are not** (owner decision 2026-09-03).
`release.yml` used to keep only the current and immediately previous release, deleting every older
release *and its Git tag*. It no longer deletes either, and must not be changed back: a release row
and a tag cost nothing, while the history is the only record of what a given deployment was told to
install. The step is now named "Prune superseded container versions" to keep the two apart, because
**image** pruning stays — those consume real registry storage, and the digest-based rules above still
govern it. The one thing the release loop still computes is `previous_version`, taken from the first
listed tag that is not the current one: `ghcr-retention.py` needs it to keep the previous version's
images so the installer's rollback-to-previous-release path has something to fall back to. Deleting
releases would therefore not just lose history, it would eventually strand that rollback.

**Cloud-completeness rules (lane `cloud`, 2026-10-09).**

- **Internal plain-HTTP probes are exempt from the HTTPS redirect.** `SECURE_REDIRECT_EXEMPT`
  covers `/api/v1/health/`, `/api/v1/internal/` and `/api/v1/metrics/`. The TLS, SaaS and cloud
  stacks set `ENABLE_HTTPS=true`, and the compose healthchecks, Caddy's on-demand TLS ask and
  Prometheus all reach the backend port over plain HTTP. A 301 to `https://` there is a failure,
  not an upgrade: the backend never reports healthy and no custom-domain certificate is ever
  issued. Proxied browser traffic is already marked secure, so it is unaffected.
- **A secret read from a request header is compared with `constant_time_compare`, or as bytes.**
  `hmac.compare_digest(str, str)` raises `TypeError` on any non-ASCII character, so a stranger
  could turn the cron, Telegram-webhook or Razorpay 403/400 into a 500 at will.
- **Under Compose, a variable reaches Django only through an explicit `environment:` entry.**
  No service uses `env_file`. That is why `METRICS_TOKEN` and `SENTRY_*` were documented but
  inert until they were passed through.
- **`docs/environment-reference.md` lists every `ENV_SURFACE` name.**
  `tests/test_environment_reference_drift.py` holds it complete in both directions.
- **`/control/` edits to platform integration settings write an audit row.**
  `config/admin_audit.AuditedControlChangeMixin` covers the platform email, SMS, push, social,
  login-method and OIDC settings. The row's metadata names the changed fields and never
  their values.
- **The social-settings API and the `/control/` form share one lockout predicate.** It is
  `social_lockout.disabling_lockout_message`, so the API cannot clear a provider that the form
  would refuse to clear.
- **Production release deployment stays on the host.** The release workflow optionally runs the installed
  updater on `[self-hosted, spaceworks-prod]`, after image/release publication, only on main with
  `SPACEWORKS_DEPLOY=true`. The job has no checkout or action steps and passes the exact release through
  `--version`; manual updates may select the newest published main release. Both validate releases in
  `SPACEWORKS_REPOSITORY` and hold the portable update lock before backup/pull/deployment.
  `.spaceworks-version` advances only after readiness. Failed deployment attempts image rollback;
  forward database migrations remain applied and SQL backup restoration is an operator decision.
  Runner installation defaults to No, supports Linux/systemd only, and requires all external-contributor
  workflow approvals plus repository/workflow restrictions: Docker access is effectively root.
  See `docs/self-hosting.md#security` for the required operator settings.


## Addressed messaging channels

Canonical `NotificationEnvelope`/`NotificationDelivery` and `ChannelConfiguration`
own addressed sending. Old addressed enqueue/worker APIs are inert shims;
`MakerspaceMessagingSettings`, `WhatsAppTemplateBinding` and `MessagingDelivery` remain
for historical conversion/import compatibility until separately approved retirement.
Duplicate settings/template writes return 503 before routing reconciliation, then 410
with canonical API guidance. Retain historical migrations, including `0035_messaging_tenant_tie`.

SMS and WhatsApp address a verified person, never a room destination. Their independent
`sms` and `whatsapp` modules and matrix cells default off and never fall through to
`mobile.push`. Consent settings and recipient extraction live in core integrations,
including when `notifications` is off or tombstoned; disabling the optional inbox must
not disable consented SMS/WhatsApp. Inbox imports shared identity/owner selection without
changing its own feature/in_app gates, recipient behavior or member-wording precedence.
Member consent and delivery require `integrations.messaging.ties.has_tenant_tie`: a
non-revoked local membership or ownership of an existing tenant hardware request/direct
loan, booking, event registration, machine-service request or payment. Account-only owners
qualify. Ties are derived from current authenticated ownership, never consent history or
free-text contact fields. Inactive, restricted, suspended, deletion-pending, retired/stub
and platform accounts (including global superadmins) are excluded from the member audience.
A revoked local membership wins over old owned rows. Membership `receives_notifications`
opt-out still wins at delivery; account-only owners use the consent ledger, STOP suppression
and optional personal preferences. Staff recipients require their separate active local
staff identity, membership and role/source authority. Preferences never grant recipient authority.

Own sender configuration takes precedence, including partial, broken or unreadable credentials
(which make the channel unavailable rather than falling back). Platform notification sending
requires both the platform operator's channel switch and the tenant's `use_platform_sender`,
initially off. Provider ownership is reserved by a unique non-secret sender key. Configuration
generation, sender identity and credential version are snapshotted; rotation invalidates queued
authority. Ownership and callback credential versions are separate; rotation retires the previous
version, callbacks accept retired secrets for fourteen days, and the scheduler then wipes secrets
while retaining identity/version history. Conflicting imported senders remain under `activation_hold`
until explicitly reviewed. Tenant secrets are write-only in the API and absent from `/control/`.
Writing or clearing them (a channel-settings PATCH carrying `credentials`, including `{}`, and every
Mattermost/Discord installation POST) requires `require_recent_reauth` (ten-minute, session-bound
step-up, 403 `recent_reauth_required`), exactly as payment credential writes do; non-secret toggles
(`enabled`, `personal_enabled`, quotas, templates, `use_platform_sender`, ...) need no step-up.
The superadmin's global authority applies in every servable space; explicit local role authority
still applies to everyone else. Control-plane tenant display contains only configuration/effective-source state.

Consent is an append-only per-tenant/account/channel ledger. Live SMS consent requires the latest
row by id to be opted_in, with its encrypted phone snapshot AND verification timestamp matching
User, and its sender/configuration generation matching current configuration. Phone A -> B -> A
never resurrects consent after reverification; verification/login is not subscription. SMS opt-in
requires verification; opt-out does not require new phone proof. WhatsApp uses a separate signed
matching inbound endpoint proof; an SMS toggle cannot establish it. A delayed proof cannot lift a
newer STOP. Writes lock User, serializing identity changes and account departure. Database triggers
allow only mapped phone maintenance under the existing registered `app.pii_fence_operation`, and
DELETE under `app.allow_immutable_delete`; the purge flag never authorizes history UPDATEs.
Archive appends account_archive opted_out rows; purge deletes consent and addressed deliveries.
Account cleanup matches User IDs, never shared contacts, preserving other accounts' history and
global physical protection. Portable consent is inert (opted_out); imported configuration conveys
no authority and imported template bindings are inactive/reviewable pending provider review.

Suppressions are deployment-keyed phone/provider-alias HMACs, scoped to channel + physical sender,
never User ids. Suppressions explicitly record phone/alias kind so unmapped alias STOPs can be
queried without guessing from a digest. Each delivery snapshots the addressed phone HMAC for late
callbacks, even after User changes phone. STOP and provider opt-out commit durably with authenticated,
encrypted, deduplicated `NotificationIngress` before acknowledgement, including disabled/frozen
tenants; storage/protection failure returns an error for provider retry. Uncorrelated opt-out creates
a sender-wide hold. Inbound START never grants consent or lifts suppression. Explicit in-app
re-consent lifts only the resolved sender's current phone protection and mapped alias suppressions,
recording all lifted IDs. Shared sender protection survives tenant/channel purge; the other channel
and OTP remain independent.

WhatsApp's BSUID correlation barrier uses probing/confirmed/blocked and alias_known. A sender/phone
may submit only one logical probe before verified identity correlation, across tenants sharing a
platform sender. Other deliveries defer without spending attempts and expire after 72 hours without
confirmation. A new unmapped alias STOP blocks correlations whose alias is unknown; in-app re-consent
resets only blocked rows. Every operation affecting whether an alias STOP is matchable takes
`lock_whatsapp_sender(sender_key)` FIRST, before row locks: unmapped STOP, probe claim, verified
confirmation and blocked-row re-consent reset. This transaction-scoped PostgreSQL advisory lock
bounds exposure to one logical probe even with concurrent deliveries or missing callbacks.
Definitive provider non-acceptance releases a probing reservation so repaired credentials or a later
delivery can probe again; ambiguous outcomes and confirmed/blocked rows never do. An ambiguous
probe is never resubmitted, including after a worker crashes with an expired probe lease. Ambiguous
ordinary sends also remain held until evidence resolves the outcome.

Source adapters supply reviewed scalar feature/event/audience projections plus source ID and
revision. Contacts, free text, notes, remarks, private bodies and public/bearer tokens or links are
excluded from that projection; deliveries store no recipient phone or message body. Templates are
provider-approved and validated against the reviewed schema. Lifecycle Meta BODY variables use
positional text parameters constrained to approved keys and the current WABA; changing WABA requires
binding review. Browser writes cannot approve a template. Canonical payment-document media bindings
retain their private, short-lived provider-fetch grants. Authenticated inbound opens the WhatsApp
24-hour session window; exactly 24 hours and future timestamps are outside it. Replayed ingress uses
its original inbound time. Provider errors store closed-vocabulary codes only, never response text.

OTP remains platform-only on its original bool transport. Notification SMS requires a distinct
platform notification number; tenants may use neither the OTP AccountSid nor its number. The two
numbers must not share a Twilio Messaging Service. SMS estimates count GSM-7 extension septets and
UCS-2 UTF-16 units, use conservative 152/66 multipart limits, and cap at three segments using ASCII
'...' followed by a recount. Provider-billed segments remain separate from estimates.

Eligibility is read-only and runs both at enqueue and just before submission: servability,
channel module, feature/matrix, account/tenant tie, current domain source and scope, recipient
authority/reach, optional personal preference, verified phone or channel-specific endpoint proof,
live consent, resolved sender, suppression and approved audience binding. Deleted/moved sources
skip as source_changed; absent or revoked tenant ties skip as no_tenant_tie. Historical
no_membership outcomes remain readable in analytics. Diagnostic tests require settings authority
and target only the caller's own verified/consented phone; settings authority authorizes that test
recipient, while the selected event must still pass feature/matrix gates, consent and sender
protections. Staff SMS consent uses the same core own-account endpoints, restricted to an active
staff account's fixed tenant and its own verified phone. Member phone linking cannot verify a
separate staff account. Platform accounts cannot grant tenant consent. Explicit canonical channel
enables lift the same account/category/channel's legacy false preference in the same transaction;
conversion never clears an opt-out.

A source-backed envelope deduplication key and one channel leg per intent prevent duplicate
lifecycle fan-out. Quota reservation records quota_reserved_at exactly once; retries, duplicate
enqueue, replay and crash recovery never spend again. Managed sms/whatsapp limits count logical
messages, including eligible caller-only diagnostics. Canonical claims use short locking transactions
and a four-attempt budget; only explicit provider rejections may retry. Expired addressed leases and
ambiguous outcomes become held. Per-device push additionally fences completion by its UUID token.
Accepted means provider acceptance, not delivery. Progress rank is monotonic: acceptance never
lowers observed webhook progress, delivered/read evidence wins over failure in either arrival order,
and failed_at records every observed failure. Provider timestamps are never invented.

Tenant mutations acquire the shared cutover boundary, then the tenant source gate (reusing any
existing same-tenant boundary), then the WhatsApp sender lock, then User/configuration and
challenge/delivery/correlation/receipt rows; callback event rows precede delivery rows. Consent uses
gate -> sender -> tenant -> User -> suppression/correlation rows; recovery and STOP consent
annotations follow the same gate-before-sender order. Dedicated boundary connections span provider
I/O without holding a long application SQL transaction. Sender-only inbound protection requires no
tenant gate and commits before optional gated tenant updates. Sender locks precede row locks in
probe claim, callback confirmation, unmapped STOP and re-consent. Signed Meta references bind
configuration/generation/delivery/attempt. Exact sender/provider/tenant/generation/attempt mappings
and fingerprints constrain replay. Callback correlation uses the submitted phone hash and provider
message ID or echoed delivery ID and immutable mappings, never the user's later phone. Alias
confirmation is atomic with its mapping; phone-only confirmation requires no unmapped alias suppression.

Twilio callbacks admit form bodies only and validate every repeated parameter using the official
validator ordering and URL-port variants, plus AccountSid/sender-number binding. StatusCallback
includes #rc=5&rp=5xx,ct,rt; its fragment is excluded from verification. Meta validates the raw-body
HMAC and ignores foreign phone_number_id entries. Verification tries active credentials before
versions retired within 14 days; old secrets are then wiped. Ingress commits a minimal durable event
before processing; DB failures return 500. Early callbacks retry. Status writes hold the tenant
source gate but ignore module switches; sender-level STOP/alias protection is never abandoned.
21610 suppresses provider_opt_out; invalid-number errors suppress permanent_failure. Template
failures record template_rejected, never provider text. Twilio error protection and its server-owned
inbox payload marker commit together BEFORE the gated status transaction. The hashed status recipient
also protects early callbacks before delivery correlation. Status retries never replay that protection
after re-consent.

Beat and `run_scheduled_tasks` recover the canonical outbox, per-device push and durable ingress;
`messaging-recovery` recovers receipts, never the retired send loop. Replay uses original
receipt/provider time, never recovery time. Unresolved receipts back off and remain held; recovery
never retries a held send to discover its outcome.

Canonical retention is `integrations/notification_retention.py`, run hourly as
`canonical-messaging-retention` by both beat and `run_scheduled_tasks`; it is core, so it
runs with `notifications` tombstoned. Under the shared cutover lock it deletes, per tenant
inside the skip-and-count source-gate fan-out, sms/whatsapp/native_push
`NotificationDelivery` legs by derived status from `created_at`: 365 days when failed
without delivered/read evidence (or a push leg with a failed device child), otherwise 90 days
for accepted/sent/delivered/read/skipped. A leg is kept while retrying, held, retryable or
leased, while its envelope is unprocessed, while any push child is pending/sending/held,
while it is the probe of a `probing` correlation, while a media grant references it, while
any unprocessed receipt exists for its channel/sender, and while an sms/whatsapp leg with a
provider ID lacks its exact non-ambiguous `NotificationProviderReference` (the permanent
reference settles late callbacks for deleted legs). Push legs are skipped entirely when the
inbox app is not installed. `NotificationIngress` receipts are deleted deployment-wide only
when processed, protection-applied and processed more than 30 days ago; pending/held
receipts are never deleted. Until `NotificationCutover.reconciled_at` is set, no delivery or
receipt that is the canonical target of a `NotificationLegacyMapping` is deleted. Envelopes,
mappings, provider references, suppressions, aliases, correlations, consent, credential
versions and every frozen legacy table (`MessagingDelivery`, `MessagingWebhookEvent`, ...)
are never pruned by it. Communications reporting is read-only over canonical delivery facts
and immutable legacy mappings; email and push are counted once from physical/device ledgers.
Held sends, held ingress and original abandoned-receipt cohorts remain distinct. Reporting never
replays, activates or dispatches work.

Destructive integrations `0043` remains unsupplied until original mappings, push dispositions,
suppression/STOP replay and cross-lane sign-offs are verified; sending activation is an independent
explicit operator checkpoint on every upgraded deployment. Only integrations
`0046_fresh_install_sending` may activate without it, and only on a fresh install: no
`Makerspace`, at most one account and that one a superuser, no integrations notification history,
and an untouched receipt-only gate. It records `_install_branch` (`fresh_install_active` or
`upgrade_held`) in the cutover snapshot and logs it; a gate already reconciled or activated is never
touched. Do not widen that freshness test, and never let a populated database take the fresh branch. Old signed webhook URLs remain compatibility ingress throughout that
period. Follow [the rollout guide](notification-reconciliation-rollout.md) and
[operator setup and versioned routes](messaging-channels.md), rather than running
expand/convert/retire unattended.

## Public pages, shared handles and owner builders

Member, makerspace and global organization names share `PublicHandle` and its lowercase namespace,
owner checks, name locks and 30-day cooldown/reservation rules. Existing member detail, activity and
share APIs remain member-only. The universal resolver returns a live typed target; an unpublished
page or withdrawn consent is the same 404 as an unknown handle. Retired names recheck the current
owner and return temporary no-store redirects. No migration automatically claims a slug or publishes.

Makerspaces require `public_site_enabled`, canonical servability and a published revision.
Directory/sitemap inclusion keeps its existing separate visibility rule (`hidden_from_central_directory`). Organizations require active status and explicit profile consent,
independently of discoverability. Their pages, history, quota, assets and creator attribution are
deployment-global. A tenant link cannot export, purge or assign ownership of that global content.

The owner edits: active local staff with the fixed Space Manager identity for a makerspace; an
active organization profile governor for an organization; the existing exact event editorial/schedule
permissions for an event or series. Platform accounts are excluded from page editing, except the
platform superadmin on a makerspace's own page and its events' websites (owner decision #115). Delegated
account admission is not an authority grant. Pre-auth claim sessions never edit pages. All tenant
writers repeat the source fence and owner authority under locks; global organization writers select
no tenant and do not inherit a linked tenant's source freeze. Organization editors use platform
staff origins. GET of an empty editor creates no page; versioned save appends a draft, and explicit
publication selects the saved complete revision. Preview cannot publish.

Event `/e/<public_token>` resolves the venue, never an organizer's linked tenant. Basic public-event
gates apply even without an enhanced website. Existing event routes remain authoritative. EventPage
working content, selected draft and released snapshot are separate. Public programme reads and
images use the released snapshot with its frozen UTC anchor. Effective inherited occurrences must
fit that snapshot as well as working sessions; editing/removing a draft cannot evade a retained
publication's window. Page-owned session UUIDs and permanent slug aliases prevent reuse from
retargeting operational delays. Delay can update publication without publishing pending editorial
content; supplied identity/revision preconditions retain the frozen HTTP compatibility contract.

Both Host and browser Origin (or Referer) constrain public reads. Unknown or ambiguous hosts fail
closed. A verified tenant host can resolve only its tenant's maker/member handles and venue events.
New global organization pages, collections and gated assets require a platform Host; recognized
tenant browser origins remain allowed on the platform read host. Legacy organization read APIs
keep explicit global compatibility admission. New API-client page reads require `public:read` or
`public:*`, with no implicit `legacy:v1` admission. A tagged global handle success is distinct from
an unresolved tenant. Editor identity and public visibility are still checked after client admission.

Organization collections query live organizer attribution across venues, not only organization-linked
spaces. Linked-space cards retain directory gates. Upcoming events remain published/public/not ended;
the past archive is a minimal separate card projection with no registration CTA, website image or
expired website link. Public team entries use typed profile slots and current consent, never stored
member-name fallbacks. Inventory stats expose only the already-public exact-count subset. Member
counts and location require their own explicit opt-ins; presence geofences never become public maps.

Builder documents use bounded, validated sections and restricted Markdown; new links require HTTPS.
Legacy event prose can retain only the versioned escaped-literal mode. Current-reference private
asset streams repeat live visibility and origin checks with no-store; retained history alone grants
no public image access. All saved revisions pin their images. Makerspace/event bytes use tenant
quota; organizations have an independent 100,000,000-byte/50-asset allowance, including pending
deletions. Purge enlists exact owned keys before deleting rows. Retryable cleanup deletes staging
and final versions, then releases quota once; the module purge's legacy accounting skips those keys.
Organization content and foreign-hosted organizers survive tenant or Events purge.

Portable import omits exactly four nullable pointer edges from insertion ordering: draft/published
on MakerspacePublicPage and EventPage. Shell insertion uses NULL pointers; checked post-insert fixups
restore only the mapped draft. Other cycles still fail. Publication, EventPage release and member
count/location disclosure reset; namespace conflicts drop the incoming claim, never overwrite a
target. Global organization models and retired reservations remain deployment-only. Deployment
backup preserves IDs and publication; organization member-reference slots survive tenant exclusion
with a nullable profile link. Creator User references remain in the deployment component.

Database restore cannot rely on deferred triggers retroactively validating copied rows.
`backup/public_page_verification.py` independently checks pointer ownership, exact reference slots,
private-byte ownership, working/draft agreement, released/inherited windows and quota accounting
before normal restore validation, compound catalog verification or a slice's verified checkpoint.
Invalid state refuses the checkpoint. Semantic checks also run on readable-main/reconstruction
databases, use the candidate alias throughout and remain available with Events tombstoned.

All state changes emit summary-only audit records; no revision body or secret URL belongs in audit
metadata. The closed page `finish` wrapper action vocabulary is scanned; staff projection redacts its
dynamic metadata. Deleted revision/page identifiers are inert provenance. Crawler rewrites dispatch
handles to `/share/pages/` and short events to `/share/e/`, preserving legacy event/booking routes.
`e` is reserved in every route snapshot. Sharing uses ordinary canonical-URL QR codes, never inventory
QR rows. Public responses are no-store and draft previews are private/noindex.

Everything uses the Space Works theme, CSS-variable light/dark tokens, existing layouts/AppShell,
Gilroy 400–700, one Unbounded accent and lucide icons. Published cover/palette overrides precede
legacy owner artwork/theme; inherit preserves legacy values and explicit none removes a cover.
Brand seed choices go through accessible token derivation and never recolor fixed focus/status/staff
tokens. No new makerspace-page, organization or hackathon module key is introduced.

## Explicit managed and free deployment boundaries (cloud integration)

Missing selectors remain host/full. Managed privilege mode and product classification are separate inputs.
Free requires managed and never applies its resource restrictions under full. Full has no tick route/schema.
A managed binding is immutable and omitted from restored/portable tenant state; source identity cannot admit
another deployment as normal. Recovery admission is uncached. An active boundary retains its original
generation/physical session; only a new boundary acknowledges a successfully resumed generation.
Direct/session transport retains advisory locks; transaction pooling is unsupported. Maintenance secrets belong
only to finite qualified jobs. Shared libpq subprocesses use private temporary passfiles, never PGPASSWORD.

Managed deployment/compound backup, restore/cutover/slice-merge controls refuse before effects. Ordinary tenant
archives remain archive-and-purge custody records with no restore reader. Provider PITR/object durability,
portable recovery and H1 recovery are separate guarantees. Unversioned managed capture needs complete durable
writer/presign drain and reconciliation. Unknown writers/lost lock connections abort; age is not proof.

Storage identity/history floors survive credential rotation and cannot be reset/deleted to bypass migration.
POST can enforce upload-time byte ranges; PUT validates at finalization. New public-image staging is private;
legacy locators remain until drained. Promotion is create-only; accepted evidence rows remain immutable.
Provider configuration uses API_CLIENT_ENC_KEY and is write-only in API/admin. Free account-wide mail receipts
survive log/tenant deletion; uncertain acceptance remains charged until independent reconciliation proves otherwise.

Forwarded host requires independent ingress restriction, exact upstream Host and proxy-chain validation.
Tenant projections omit infrastructure identities and global/provider totals. Unknown usage is never zero.
Current implementation/acceptance limitations are explicit in the cloud guides and integration report.

Managed staging identity/owner/attempt/digest/expiry fields and selected slots are SQL-guarded; late-delete
receipts remain permanent and continue reconciling old storage identities after an audited empty-bucket
handoff. A writer holds its physical session lock before its boundary commits. Capture recovery proves
the global owner is gone, every writer lock is free and the provider-qualified transfer horizon has
drained; age alone proves none of those facts. Presigns are journalled before signature generation.
Unknown provider acceptance remains charged across new mail attempt keys. Only evidence-backed supervised
reconciliation may release it. Full never consults free accounting caps or free input limits.
