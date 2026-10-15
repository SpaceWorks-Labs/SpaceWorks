# Research: Events / Bookings Manager defaults, multi-role staff, dashboard access, per-machine assignment

Status: RESEARCH ONLY, nothing built. This is input to the PLAN §11 follow-up plan, which needs its own
Codex Stage-1 review and owner approval. Written 2026-10-15.

Code read: worktree `feature/design-revamp`. Its backend is byte-identical to `dev @ d3e5ed29`, and its
frontend differs from dev only in brand assets (`SpaceWorksLogo.tsx`, `icons.tsx`, `spaceWorksLogoPaths.ts`,
`lib/branding.ts`). Line numbers below are for that tree unless a citation says `yuyu:`, which means
`feature/yuyu-parity` read with `git show`.

**Owner brief, as updated 2026-10-15. This supersedes the single "Events & Bookings Manager" idea.**

- (a) Add TWO protected default roles, **"Events Manager"** and **"Bookings Manager"**, seeded in every
  makerspace like Space Manager, Inventory Manager, Machine Manager and Member. Each one holds everything
  needed to run its area, so nobody needs a custom role for events or bookings.
- (a′) One person can hold BOTH roles in the same makerspace. When any staff member signs in, the console
  shows exactly the sidebar sections that their combined permissions allow.
- (b) Super Admin, Space Manager, Events Manager and Bookings Manager all get the dashboard.
- (c) When a Space Manager creates a machine, they choose who manages or operates it, and can reassign it
  later. This must not need a custom role per machine.

---

## 0. Headline findings (read these first)

1. **Today a staff member has exactly ONE role per makerspace.** The constraint
   `uniq_makerspace_user(makerspace, user)` is at `makerspaces/models_memberships.py:105-108`, and
   `MakerspaceMembership.assigned_role` is a single FK at `:37-43`. Requirement (a′) therefore needs a
   schema change. The good news is that the resolution layer already merges actions from two sources
   (membership plus organization grants, `accounts/rbac.py:193-195` and `:246-249`). Adding "more roles"
   as one more source fits the existing shape.
2. **The dashboard already works for (b).** Holding `manage_events` or `manage_bookings` passes both the
   backend gate (`operations/views_dashboard_api.py:41-51`) and the frontend gate
   (`staffAccess.ts:105-107,123`), and each holder gets only their own tiles. Nothing needs to change,
   apart from optional richer widgets (§2).
3. **Per-machine assignment already exists as "tier 3" machine operators** (`machines.MachineOperator`,
   with levels `operate` / `manage` / `full`; `machines/access.py:1-22`, `:62-68`, `:235-250`). It is
   audited and makerspace-scoped, and it survives tenant migration (owner decision 22). Two things are
   missing for (c):
   - **Machine creation never asks for assignees.**
   - **The console never shows the Machines tab to someone whose only machine authority is an operator
     row.** The frontend gates the tab on `manage_machines` alone (`staffAccess.ts:153`). For a Member,
     `actions=[]`, so they land in the governance-only console with just the "organizations" tab
     (`:108`, `:120`), even though the backend's `can_see_machines` admits them
     (`machines/access.py:339-361`).

   Fixing those two gaps is the cheapest design that stays inside the invariants (§3.3, option A).
4. **"Everything needed to run events / bookings" is NOT just `manage_events` / `manage_bookings`.** Four
   things behind other actions would still block these managers:
   - booking rules: `MANAGE_MAKERSPACE`, in `bookings/views_admin_rules.py:35-40`
   - cloning a bookable resource: `MANAGE_MAKERSPACE`, in `yuyu: bookings/services_clone.py:34`
   - the Event-attendance and Booking-utilization reports: they default to `VIEW_AUDIT`
     (`operations/report_types.py:25`, `report_definitions_existing.py:30-31`)
   - custom-answer bindings on event badges and the registration-answers projection: `VIEW_AUDIT`
     (`yuyu: events/services_badges.py:130`, `events/serializers_event_details.py:115`)

   The owner has to decide whether to widen these roles or to re-key those checks (§4.4, Q1–Q3).
5. **`dev` has nothing newer than `d3e5ed29`.** `dev`, `origin/dev` and `d3e5ed29` are the same commit. The
   new events and bookings work is on **`feature/yuyu-parity`**: 25 commits, 626 files,
   +140k / −109k lines. That branch adds shared **resource staff-grant infrastructure** (event-scoped and
   per-bookable-space staff grants, plus an "Assigned resources" console tab). This matters directly for
   (c), and for conflicts with the revamp (§5).

---

## 1. The current role system

### 1.1 Defaults and how they are seeded

**What is defined (`makerspaces/roles.py:14-20`):**

- `DEFAULT_ROLE_DEFINITIONS` holds 3-tuples of `(legacy_role, name, actions)`:
  - `space_manager` gets 21 actions: `accept_request`, `assign_box`, `edit_inventory`,
    `issue_direct_loan`, `issue_request`, `manage_bookings`, `manage_events`, `manage_devices`,
    `manage_machines`, `manage_makerspace`, `manage_members`, `manage_member_cards`, `manage_printing`,
    `manage_qr`, `record_payment`, `reject_request`, `return_request`, `upload_evidence`, `view_audit`,
    `view_finance`, `view_inventory`.
  - `inventory_manager` gets 11 actions: the hardware lifecycle plus `manage_qr` and `view_audit`.
  - `machine_manager` gets only `manage_machines`.
- `MEMBER_ROLE_DEFINITION = (None, "Member", [], "member")` is a 4-tuple: no legacy value, no actions,
  and an explicit slug.

**What each seeded row looks like (`ensure_default_roles`, `roles.py:23-52`):**

- It is created with `get_or_create(makerspace, slug)`.
- It has `is_default=True` and `is_protected=True`.
- Its slug is the legacy value, or the explicit 4th element.
- It never overwrites an existing row ("administrator edits win").
- When a role is created, `grant_builtin_type_scope(role)` links any `MANAGE_MACHINES` role that is not a
  space-manager role to every built-in machine type (`machines/role_scope_grants.py:114-130`).

**Every path that seeds defaults:**

| Path | Where | Notes |
|---|---|---|
| New makerspace | `post_save` signal `ensure_default_roles_on_create` (`makerspaces/apps.py:42-50`, `:84-88`) | Runs in the same transaction as the insert. The comment there says "five protected defaults", which is already stale: today there are four. |
| Creation wizard | `makerspaces/creation_setup.py:47-52` | Calls `ensure_default_roles` again, then invites the first staff member by `role_slug`. The serializer hard-codes `ChoiceField(["space_manager","inventory_manager","machine_manager"])` (`admin_api/serializers_creation_setup.py:9`). |
| Tenant import target | `tenant_migration/tenant_dump_bootstrap.py:12-45` | Raw SQL insert of `(*DEFAULT_ROLE_DEFINITIONS, MEMBER_ROLE_DEFINITION)`, then the Machine Manager type scopes. It is generic over the tuple shape, so new defaults are picked up automatically. |
| Existing makerspaces | Data migrations only: `0039` (seed and backfill, with a frozen copy of the definitions), `0041` (Member role, with name/slug collision freeing), `0046`, `0052`/`0053`/`0054` (retire Print Manager and Guest Admin), and the additive action backfills `0069`, `0074`, `0078` | `ensure_default_roles` never runs for an existing makerspace, so **a 5th or 6th default needs its own data migration.** |
| `setup_instance`, `seed_demo`, `seed_e2e` | Roles come in through the signal. `seed_e2e.py:89,93` creates memberships with `role=` but no `assigned_role` (the legacy fallback). | No role-specific code. `apply_profile` / `apply_setup_areas` touch modules and features, not roles. |
| Space packs | `data_export/space_pack_configuration.py:32` exports the roles section by name; `makerspaces/space_pack_prepare.py:89-91` refuses "A pack cannot replace a built-in role." | **Risk:** a pack that carries a custom "Events Manager" role will start refusing once that name is a protected default. |

**How protection is enforced:**

- `delete_role` refuses a role that is protected or still assigned (`role_crud.py:80-82`).
- Renaming a protected role changes its label but never its slug (`:56-62`).
- The Space Manager role must keep `manage_makerspace` (`role_authority.py:131-135`).
- The Member role may hold no actions (`:136-142`).
- DB check constraint `makerspacerole_default_has_legacy`: a default row needs a `legacy_role` OR
  `is_protected=True` (`models_roles.py:51-54`).
- `makerspacerole_legacy_uniq` is a partial unique constraint per makerspace on a non-null `legacy_role`.
- Name and slug are unique per makerspace, case-insensitively (`:40-46`).
- The custom-role quota counts only `is_default=False` (`limits_usage.py:94-97`), so new defaults cost
  no quota.

### 1.2 The action catalogue (every string)

`accounts/rbac_actions.py:12-50` defines:

- `manage_events`, `manage_bookings`
- `view_inventory`, `edit_inventory`
- `accept_request`, `reject_request`, `assign_box`, `issue_request`, `issue_direct_loan`,
  `return_request`, `upload_evidence`
- `collect_service_request`, `manage_qr`, `manage_printing`, `manage_machines`
- `scan_member_cards`, `manage_member_cards`, `manage_devices`, `manage_members`
- `view_finance`, `record_payment`, `view_audit`
- `transfer_stock` (forbidden on roles), `manage_staff` (forbidden on roles)
- `manage_makerspace` (superadmin-assignable)

How the catalogue is used:

- **Implied grants:** `manage_machines` ⇒ `{manage_printing, collect_service_request}`;
  `manage_members` ⇒ `manage_member_cards` ⇒ `scan_member_cards` (`:53-60`).
- **Organization-grantable:** everything role-grantable except `manage_machines` and `manage_devices`
  (`:141-143`).
- **The handover set** `HANDOUT_ACTIONS` (`:154-159`) is used only by `is_handout_only`.
- **The console catalogue** labels "Events" as `manage_events` and "Bookings" as `manage_bookings`
  (`admin_api/views_roles.py:33-34`). The frontend presets are in `panels/RoleEditor.tsx:9-17`, and they
  have no Events or Bookings preset.

### 1.3 What the events and bookings flows require today

**Backend, on `dev`:**

| Surface | Required action | Cite |
|---|---|---|
| Event list / detail / CRUD, registrations, check-in, collaborators, invites, feedback, series, series collaboration, ticket categories | `MANAGE_EVENTS` (plus organizer and series authority for org-hosted events) | `events/views_admin_event_*.py`, `views_admin_registrations.py:60-181`, `views_checkin.py:73`, `views_collaborators.py:40-176`, `views_invites.py:36`, `views_feedback_admin.py:50`, `views_series*.py`, `views_ticketing.py:77`, `organizer_authority.py`, `series_authority.py` |
| Eligible-member picker for registering someone | inherits event authority (deliberately NOT `MANAGE_MAKERSPACE`) | `views_admin_registrations.py:240-250` |
| Bookable spaces, bookings list / create / actions, recurrence, machine-type links | `MANAGE_BOOKINGS` | `bookings/views_admin_*.py`, `services_recurrence.py:23` |
| **Booking rules** (approval mode, lead times) | **`MANAGE_MAKERSPACE`** | `bookings/views_admin_rules.py:35-40`, `serializers_admin.py:29-30` |
| Event / booking email templates | `MANAGE_EVENTS` / `MANAGE_BOOKINGS`, or `MANAGE_MAKERSPACE` | `admin_api/views_email_templates_common.py:36-37` |
| Notification recipients and alerts | `manage_events` / `manage_bookings` | `integrations/staff_notifications.py:18-19`, `admin_api/views_notification_recipients.py:16-24` |
| Payment reconcile / waive / refund for event or booking money | `MANAGE_EVENTS` / `MANAGE_BOOKINGS` (domain authority, no `record_payment` needed) | `payments/reconciliation_authority.py:13-28` |
| Global search hits | the matching action plus the module | `admin_api/search.py:78-88` |
| **Event-attendance and booking-utilization reports** | **`VIEW_AUDIT`** (the default `required_action`) | `operations/report_types.py:25`, `report_definitions_existing.py:30-31` |
| Kiosk stations | Scanner and handover stations need `MANAGE_MAKERSPACE`, and the admin view refuses the event kind. Event station authority was **not verified** in this pass; check it in the follow-up plan. | INVARIANTS "Events program", `makerspaces/station_views_admin.py:75,84` |

**What `feature/yuyu-parity` adds on top:**

- Booking resource clone: `MANAGE_MAKERSPACE` (`bookings/services_clone.py:34`).
- Booking rules service: `MANAGE_MAKERSPACE` (`services_rules.py:81`).
- Booking report features: `VIEW_AUDIT` (`report_features.py:15`).
- Event badge custom-answer bindings and the answers projection: `VIEW_AUDIT`
  (`services_badges.py:130`, `serializers_event_details.py:115`).
- Event and booking staff-grant management: tenant `MANAGE_EVENTS` / `MANAGE_BOOKINGS`.
- Role and grant endpoints now need recent re-authentication (`RecentReauthenticationMixin` on
  `views_roles.py`, `views_memberships.py`, `views_member_memberships.py`, `views_users.py`, and both
  `views_staff_grants.py`).

**Frontend tab gating (`frontend/src/features/staff/staffAccess.ts`):**

- `events` needs `manage_events` (`:154`); `bookings` needs `manage_bookings` (`:166`).
- `dashboard` needs any of the actions listed at `:105-107`, which includes both of those.
- `reports` needs `view_finance`, `view_audit`, printing, or machines (`:141`). **An Events or Bookings
  Manager without `view_audit` does not get Reports.**
- `payments` needs `view_finance` or `record_payment` (`:169`).
- `emailtemplates` needs `edit_inventory`, printing, or `manage_devices` (`:145`). **An Events Manager does
  not get it**, even though the backend would allow event templates (`views_email_templates_common.py:36`).
  This is an existing parity gap.
- Module availability is decided only in `staffTabs.ts:28-32` (the `events` and `bookings` modules).
- The sidebar section map `TAB_GROUPS` is at `:55-65`.

**Module gates:**

- `events` and `bookings` are opt-in modules in `module_registry.py`.
- Sub-features (for example `bookings.staff_grants`, `events.certificate_designer` on yuyu) need their
  parent module.
- The superadmin owns `enabled_modules`. A Space Manager owns `enabled_features`.
- A new role grants nothing usable while its module is off. The tab is filtered out, and the dashboard
  tiles are hidden (`DashboardPanel.tsx:79`; backend `dashboard_programmes.py:13-21`).

### 1.4 What a migration adding the new protected defaults must do

There are two ways to identify the new rows.

**Option N1: new legacy enum values (recommended).**

- Add `MakerspaceMembership.Role.EVENTS_MANAGER = "events_manager"` and
  `BOOKINGS_MANAGER = "bookings_manager"`.
- Add 3-tuples to `DEFAULT_ROLE_DEFINITIONS`, so slug = legacy value, matching Inventory and Machine
  Manager.
- Effects:
  - The `membership.role` mirror (`role_assignments.py:55`, `membership_activation.py:67-91`,
    `staff_invitation_acceptance.py:95`, `services_staff.py:67`) shows a real value instead of `custom`.
    Label maps that key on it would show the right name: `MakerspaceEmailSettings.tsx:32,273`,
    `NotificationMuteMatrix.tsx:228`, `operations/report_schedule_rules.py:125`.
  - The test helpers keyed by `legacy_role` keep working.
  - Cost: an `AlterField` on both `MakerspaceMembership.role` and `MakerspaceRole.legacy_role` choices.
    Choices are not enforced in SQL; `0054` is the precedent.
  - Do NOT add these values to `_MEMBERSHIP_ROLE_ACTIONS`. No null-FK legacy membership can hold them,
    and the legacy fallback is frozen archaeology (INVARIANTS "Handover roles").

**Option N2: `legacy_role=NULL` with an explicit slug, like Member.**

- No enum change. The check constraint still passes because `is_protected=True`.
- Costs:
  - `assert_default_roles` and `test_seeded_defaults_match_frozen_rbac_mapping` build a dict keyed by
    `legacy_role`, so three `None` keys would collapse into one. Both tests must be re-keyed to slug.
  - The tuples become 4-tuples, which breaks every `for legacy_role, name, actions in ...` unpack
    (`tests/makerspaces/test_custom_roles_l1.py:37,136,190`).
  - Members show `role="custom"`.

**What the data migration must do (on either option):**

1. **Chain from the actual leaf.** That is `0087_remove_in_app_updates` on dev, but `0089` once
   `feature/yuyu-parity` lands (`0088_setup_event_audience`, `0089_organization_event_audience`). Run
   `ls backend/apps/makerspaces/migrations/` at build time.
2. **Backfill every existing makerspace**, archived and hidden ones included. The model has no tenant
   filter, and 0039/0041 seeded everything. Use
   `get_or_create(makerspace, slug, defaults={name, legacy_role, granted_actions, is_default=True, is_protected=True})`.
3. **Free name and slug collisions first, following the `0041` precedent** (`_free_value`, rename to
   `"<name> (custom)"` / `"<slug>-custom"`). A space that already made a custom "Events Manager" is
   likely. Slugs: a custom role's slug is `slugify(name)`, i.e. `events-manager` with a hyphen, which does
   not clash with `events_manager` under the CI-unique slug rule. **Names DO clash** (`Lower(name)`
   unique). Moving such a role's memberships onto the new default is an owner decision (Q4); the
   `0053` "Front Desk" precedent reused a role only when its actions matched exactly.
4. **Assign nobody automatically.** These are new jobs, unlike 0052/0053, which converted existing ones.
5. **No `RoleMachineTypeScope` rows.** The new roles have no `manage_machines`, so
   `grant_builtin_type_scope` is a no-op.
6. Write a `backwards` function that deletes only unassigned rows of these slugs and refuses or keeps
   assigned ones (`on_delete=PROTECT` on the membership FK).
7. **No new model, so no `data_export` classification change.** `MakerspaceRole` is already classified
   (`classification_domain.py:82`, `datasets.py:99`, `tenant_dump_field_snapshot.py:39`). Tenant import
   seeds target defaults generically (`tenant_dump_bootstrap.py`) and drops archived role rows
   (`authority_guards.py:80`). Imported memberships are reduced to the target Member role
   (`target_projection_references.py:25`). That behaviour is unchanged and must stay unchanged.

**Code and docs that change with the new defaults:**

- `roles.py` definitions.
- `models_memberships.Role` (N1).
- `serializers_creation_setup.py:9` choices, plus the wizard `CreationWizardSteps.tsx:35` and
  `usersModals/types.ts:15`.
- Optionally `views_users._SM_DELEGABLE_ROLES` and `urls_staff.py` routes. These are not required,
  because the role-assignment API covers it, and the comment at `urls_staff.py:19-28` shows these
  per-role routes are being retired.
- `RoleEditor.tsx` presets.
- The `MakerspaceEmailSettings.tsx` and `NotificationMuteMatrix.tsx` label maps.
- `apps.py:47` comment ("five").
- Docs:
  - `CLAUDE.md` **and** `AGENTS.md`, in the same commit: "seed **four** protected defaults" becomes six.
  - INVARIANTS "Custom editable per-makerspace roles (Part L)" (`docs/INVARIANTS.md:454`) still says
    "The 5 legacy roles" and is already stale.
  - `docs/RBAC-MEMBERS-FINANCE.md`, `docs/LANDING-PAGE-FEATURES.md`, `docs/README-HOSTING.md` mention the
    defaults.

**Tests that pin the current defaults:**

- `tests/makerspaces/test_custom_roles_l1.py:14,32-50,68` (`count() == 4`), `:136`, `:180-193`.
- `tests/makerspaces/test_rbac_f6_backfill.py:42` (`is_protected=True).count() == 4`).
- `tests/tenant_migration/test_projection_values_d8.py:276-277`. It is slug-derived and generic, so it
  should pass.
- Frontend: `RoleEditorF6.test.tsx` if presets change, and the wizard tests.

**New tests to add:**

- A fresh makerspace gets six protected defaults with the exact actions.
- The migration backfills and frees collisions.
- Rename keeps the slug, and delete is refused.
- A tenant-dump target seeds both new roles.
- A space pack carrying an "Events Manager" custom role is refused cleanly (or handled).

---

## 2. Dashboard gating today, and what (b) needs

**Backend `DashboardView` (`operations/views_dashboard_api.py:26-95`):**

1. The makerspace must be within the actor's scope (`scope_by_makerspace` plus servable).
2. A handout-only actor is refused (`:39-40`, `rbac.is_handout_only`).
3. The actor must hold ANY of: `view_inventory`, `manage_printing`, `manage_makerspace`,
   `manage_events`, `manage_bookings`, `manage_members`, `manage_machines`, `view_finance` (`:41-51`).
4. Which tile families are computed:

| Tile family | Computed when |
|---|---|
| Hardware | `view_inventory` or `manage_makerspace` |
| Machines | `manage_machines` / `manage_printing` / `manage_makerspace`, narrowed by `role_scope.manage_scope_for` |
| Events | `manage_events` |
| Bookings | `manage_bookings` |
| Failed emails | `manage_makerspace` |
| Pending payments | `manage_makerspace` or `view_finance` |
| Machine-only mode | only if the actor manages no events, bookings or finance (`:65-69`) |

5. Event and booking counts come from `dashboard_programmes.py`: upcoming published events, pending
   registrations, pending bookings, upcoming confirmed bookings. These need the module on, and are
   scoped again with `scope_by_action`.

**Frontend:**

- The `dashboard` tab rule is `!handoutOnly && (isSuperadmin || canSeeDashboard)` (`staffAccess.ts:123`),
  where `canSeeDashboard` is the same 8-action list (`:105-107`).
- Tiles are filtered by module, and by whether the tile's destination tab is in `allowedTabs`
  (`DashboardPanel.tsx:77-85`, `dashboardLinks.ts`).

**Result for (b): no change needed.**

| Actor | Dashboard | Tiles they see |
|---|---|---|
| Super Admin | yes (`has()` is true; backend `can` is true except in a hard-hidden space, where membership governs) | all |
| Space Manager | yes | all |
| Events Manager (`manage_events`) | yes | Upcoming events, Registrations awaiting approval |
| Bookings Manager (`manage_bookings`) | yes | Bookings awaiting approval, Upcoming bookings |
| Holder of both (after §1.5) | yes | the four programme tiles; actions are a union |

**Caveats:**

- With the `events` and `bookings` modules off, these managers get an empty dashboard. Copy is needed
  ("Turn on Events in Modules"). Only the superadmin can do that.
- `shell-contracts.md` §4 already defers "Coming up: events/bookings" lists. Events need an
  `ends_after` filter. Bookings need a makerspace-wide endpoint, because today it is only per space at
  `/admin/spaces/<pk>/bookings/`. If the revamp's S1 dashboard is meant to be useful for these roles,
  those two backend additions belong in the follow-up plan.
- The `event-attendance` and `booking-utilization` report tiles or links need `view_audit` today (Q2).

---

## 1.5. Can a staff user hold more than one role per makerspace? (owner update, a′)

### 1.5.1 Today: no. Where the single-role assumption lives

**Data model:**

- One membership row per (makerspace, user): `uniq_makerspace_user` (`models_memberships.py:105-108`).
- One role FK per membership: `assigned_role` (`:37-43`).
- A single legacy mirror `role` (`:36`).

**Resolution:**

- `rbac_actions.actions_for_membership(membership)` (`:163-185`) reads one `assigned_role`, and falls
  back to `_MEMBERSHIP_ROLE_ACTIONS[membership.role]` for a null FK.
- `rbac.effective_actions` (`rbac.py:180-195`) and `rbac.can` (`:226-251`) take the union of that ONE
  role with organization grants (`_org_actions_for`). **So union semantics already exist, with one
  source per kind.**

**Query-level twins (these filter memberships by the single FK):**

- `_action_scope_filters` (`rbac_actions.py:207-218`) uses `assigned_role__granted_actions__contains`,
  and is used by `makerspaces_for_action` (`rbac.py:103-133`) and by `rbac_superadmin.py:63-77`.
- `machines/role_scope_grants.makerspaces_granting_directly` (`:87-111`).
- `role_grants_directly` (`:43-62`), which reads the stored grant of one role.
- `machines/role_scope_resolution._scope_for_membership` (`:20-40`): one role, giving one scope.
- `manage_scopes_for` / `manage_scopes_for_memberships`, which map role ids to makerspace or membership.
- Notification recipient rules of kind `role` filter on `assigned_role_id`
  (`admin_api/recipient_rule_common.py:89-97`, `recipient_rule_access.py:131-170`,
  `recipient_rule_validation.py:59-66`, `integrations/recipients_resolution.py:132`).
- Report schedule recipients by role slug (`operations/report_schedule_rules.py:107-125`).

**Identity derivations (each reads ONE role):**

- `rbac_memberships._membership_is_space_manager` (`:21-30`, `legacy_role == "space_manager"`), used by
  `is_space_manager_identity`.
- `serializers_payload._can_configure_machine_types` (`:59-68`).
- `serializers_payload._is_machine_only` / `_stores_printing` (`:88-121`).
- `role_scope_grants.is_machine_only` (`:10-24`).
- `rbac.is_handout_only` (`rbac.py:218-223`). This one works on effective actions, so it is already
  union-safe.

**Mutations (each sets ONE role):**

- `role_assignments.assign_role` (`:36-70`, audit `staff.role_assigned` with old and new role id).
- `can_assign_role` non-escalation, which uses `actions_for_membership(target)`.
- `role_authority._locked_actor_actions` locks only the actor's one role (`:30-43`).
- `yuyu: makerspaces/resource_grant_locks.lock_tenant_authority` locks `[row.assigned_role_id ...]`.
- Delete-role refusal checks `memberships.filter(assigned_role=role)` (`role_crud.py:80`).
- Staff creation (`services_staff.attach_staff_membership`), invitation acceptance, membership activation
  and import adoption.

**Auth payload (`accounts/serializers_payload.py` + `org_payload.membership_makerspace_entry`):**

- Each makerspace entry carries `actions` (sorted union of role and org), `role_id`, `role_name`,
  `role_slug`, `role` (legacy mirror), `is_machine_only` and `can_configure_machine_types`
  (`org_payload.py:28-43`). Every role field is singular.

**Frontend:**

- `StaffApp.tsx:153-162` picks `activeMembership` and passes `activeMembership.actions` and
  `is_machine_only` into `StaffWorkspace`.
- `getStaffAccess(actions, ...)` derives every tab from action strings (`staffAccess.ts:77-205`), so it is
  role-agnostic. It is already correct for a union.
- The workspace header shows ONE `role_name` (`StaffWorkspace.tsx`, `activeRoleName`).
- `MembersPanel.tsx:72` and `rolesApi.ts:98` PATCH a single `role_id`
  (`/admin/memberships/<id>/role`, `admin_api/urls_memberships.py:55,94`).

**Scale of the change:**

- `assigned_role` appears 179 times across 58 non-migration backend files and 140 test files.
- `actions_for_membership(` is called from 18 modules. Because it is the central resolver, extending it
  covers most call sites automatically. The query-level twins and identity helpers above are the ones
  that need hand edits.

### 1.5.2 Designs for "one person holds both"

**Design M1: multi-role membership, where actions are a union (RECOMMENDED).**

- Keep `assigned_role` as the **primary** role. It keeps carrying identity:
  - the legacy `role` mirror
  - space-manager identity
  - the Member role that every join, claim and walk-in activates onto
  - tenant-migration remapping to Member
- Add a through model `makerspaces.MembershipAdditionalRole(membership FK CASCADE, role FK PROTECT,
  assigned_by FK SET_NULL, assigned_at)`, with `UniqueConstraint(membership, role)` and a DB check (or
  trigger) that `role.makerspace_id == membership.makerspace_id`.
- Effective actions = primary ∪ additional ∪ org.

**Recommended rule: additional roles may not hold `manage_makerspace`, and may not be the Member role.**

- This keeps every identity derivation single-sourced on the primary: `is_space_manager_identity`,
  `_can_configure_machine_types`, the `MANAGE_MAKERSPACE` target-protection in `can_assign_role`, the
  Space-Manager-must-keep-`manage_makerspace` rule, and break-glass staff creation.
- Rule enforcement:
  - The protected Space Manager role can only be primary.
  - A role that later gains `manage_makerspace` while attached as additional is refused at
    `update_role`, OR `actions_for_membership` ignores `manage_makerspace` from additional roles.
    The second is preferable as fail-closed defence in depth.

**What M1 changes:**

| Area | Change |
|---|---|
| `rbac_actions.actions_for_membership` | Union over `membership.additional_roles` (prefetch). Same tenant-match fail-closed per role, unknown/forbidden stripped, expand implied. |
| `_action_scope_filters` / `makerspaces_for_action` / `rbac_superadmin` / `makerspaces_granting_directly` | Add `Q(additional_roles__role__granted_actions__contains=[a], additional_roles__role__makerspace=F("makerspace"))`, with `.distinct()` or an `Exists` subquery. |
| `role_scope_resolution` | A membership's scope is the **union** of its roles' link sets. It is EXEMPT if the primary holds `manage_makerspace` (additional roles cannot). The batch stays at 2 queries over all role ids. |
| `role_grants_directly` / `is_machine_only` / payload `_stores_printing` | Read the union of stored grants. |
| `_locked_actor_actions`, `resource_grant_locks` | Lock the primary and the additional roles, in ascending pk order, after the membership row. This keeps the makerspace → role order that `role_scope_services` relies on (`role_scope_services.py:88-96`). |
| `can_assign_role` | Non-escalation checks the target's **union**, and the actor's ceiling is unchanged. |
| `delete_role` | Refuse while any additional-role row references the role. PROTECT does this anyway; map it to `RoleConflict`. |
| New service + API | `add_additional_role` / `remove_additional_role` (locked, `MANAGE_MAKERSPACE`, non-escalation). Audit `staff.role_added` / `staff.role_removed` with `{membership_id, role_id, role_slug}`. Recent re-auth (yuyu boundary). OpenAPI entry. |
| Membership revocation | Revoking the membership already makes actions empty (`status != active`). Additional rows can stay; they are inert. Optionally clear them for hygiene. |
| Recipient rules (kind `role`) and report schedules by role | Match primary OR additional. |
| Payload | Add `role_ids` / `role_names` (primary first) next to the existing singular fields. Keep the singular fields for compatibility. `actions` already becomes the union. |
| Frontend | `getStaffAccess` is unchanged (it is action-driven). Header shows "Events Manager + Bookings Manager". `MembersPanel` / `UsersPanel` get a multi-select "Additional roles" control. |
| `data_export` | New model: classify it (`classification_domain.py`), decide the `assigned_by` User FK (`references_core.py`), add to the dataset (`members/roles.csv`-style or a new CSV) and the field snapshot. Drift guards refuse the build otherwise (CLAUDE.md rule). |
| Tenant migration | `DROP` rows (`target_projection_rows.py`), the role FK `DROP_ROW`, `authority_guards` entries "Dropped role authority". This is consistent with "every imported membership is reduced to Member" and with `RoleMachineScope` being dropped. Add it to the dump catalog pin. |
| Backup / restore | A deployment backup captures every table. Restore needs nothing new. |
| Archive / purge | CASCADE from membership and makerspace. Nothing to collect from S3. |
| `is_handout_only` | Union-safe already. A handover role plus an Events Manager role correctly stops being handover-only. |

**Design M2: an auto-composed combined role.**

- When someone is given both, create or reuse a role whose actions are the union. It could be a seeded
  third protected default, "Events & Bookings Manager" (this was the owner's first idea), or a
  generated role per combination.
- No schema change, and `rbac.can` is untouched.
- Problems:
  - Composite roles do not track their components. Editing "Events Manager" does not update the
    composite.
  - The number of combinations grows as 2ⁿ.
  - It clutters the roles list.
  - "Holds both roles" is not literally true in the UI or the audit trail.
  - Generated roles are `is_default=False`, so they hit the custom-role quota.
  - Machine scope would have to be copied.
- Acceptable only as the stop-gap of seeding a fixed third default. It fails "one person can hold both"
  in spirit.

**Design M3: a role picker (holds many, acts as one at a time).**

- The user selects an active role per session. `rbac.can` would need a request-scoped "active role", for
  example a header carried through every API call, the payload and the offline and native clients.
- This directly contradicts "the console shows exactly the sections their **combined** permissions
  allow".
- It adds a new authority input that every guard must honour. **Rejected.**

**Design M4 (noted, not recommended): two membership rows.** Impossible, because of
`uniq_makerspace_user`, and it would break every `.filter(makerspace, user).first()`.

**Recommendation: M1**, with the primary-carries-identity rule. Why:

- It is the only design that meets (a′) literally.
- It reuses the union pattern the RBAC module already has for org grants.
- It leaves `can()`'s signature and every action-driven frontend gate untouched.
- Its blast radius is concentrated in roughly 10 resolver and lock functions, plus one new model and its
  registry entries.

On sidebar sections: after M1, the sidebar is a pure function of `moduleAllowedTabs` (ux-yuyu-spec §2.1),
so an Events + Bookings Manager automatically gets exactly the Home/Inbox, Events and Bookings
destinations. ux-yuyu-spec §2.2 currently groups `events` and `bookings` under "Community" together with
`members` and `cards`. If the owner wants separate "Events" and "Bookings" sections, that is a
presentation-map change only (Q7).

---

## 3. Machine scoping today, and per-machine assignment (c)

### 3.1 Role → machine scope, end to end

**Models (`machines/models_role_scope.py`, migration `machines/0019`):**

- `RoleMachineTypeScope(role, machine_type)` and `RoleMachineScope(role, machine)`, each unique per pair.
- `clean()` rejects cross-tenant links. A global built-in type is allowed.

**Resolution (`role_scope_resolution.py`):**

- `_scope_for_membership`: a null `assigned_role` is EXEMPT (legacy fallback); a tenant mismatch is
  NOTHING; a role holding `manage_makerspace` is EXEMPT; otherwise the role id is used.
- `manage_scopes_for(actor, ids)` takes 2 queries. A superadmin with no membership is EXEMPT.
- Coverage is "type linked OR machine linked". **No links means no machines (fail closed).**

**The three access tiers (`machines/access.py`):**

- Tier 1: `MANAGE_MACHINES` within scope.
- Tier 2: the type's `managing_action`, which must be granted DIRECTLY (`grants_directly`), because
  `manage_machines` implies `manage_printing`.
- Tier 3: `MachineOperator`.

**Queries (`role_scope_queries.py`):**

- `scoped_q`, `scoped_related_q` and `scoped_service_requests` always AND the makerspace.

**Writes (`role_scope_services.set_role_machine_scope`, `:76-142`):**

- Lock order: makerspace `FOR NO KEY UPDATE`, then the role `FOR UPDATE`, then a locked revalidation that
  the actor holds `MANAGE_MAKERSPACE`.
- The link set is replaced wholesale, with ids validated against this makerspace's types and machines
  (including retired machines).
- Audit `role.machine_scope_changed {before, after}`. This is a separate event from `role.updated`.

**Seeding:**

- Migration `0020` backfilled types onto existing `MANAGE_MACHINES` roles.
- `ensure_default_roles` → `grant_builtin_type_scope` runs on creation.
- The tenant-dump bootstrap re-seeds the Machine Manager type scopes.

**API and UI:**

- `admin_api/urls_memberships.py:114-116` `roles/<id>/machine-scope`, served by `RoleMachineScopeView`
  (re-auth on yuyu).
- `panels/RoleMachineScopeEditor.tsx` is embedded in `RoleEditor.tsx:77`.
- The tab is gated on `can_see_machines`, so a scoped-to-nothing role gets no tab.

**Tenant migration:** role scopes are DROPPED (`target_projection_rows.py:31-32`). `MachineOperator`
rows are PRESERVED (`:26`, `authority_guards.py:55,92-96`, owner decision 22).

### 3.2 Tier 3 machine operators: already a per-machine assignment

**Model:** `MachineOperator(machine, user, access_level ∈ {operate, manage, full}, assigned_by,
assigned_at)`, with `unique_together(machine, user)` (`machines/models_catalog.py:164-191`).

**What each level allows:**

| Level | Allows |
|---|---|
| `operate` | Set status, log usage, log errors. |
| `manage` | Everything in `operate`, plus edit fields and documents, and see warranty and maintenance (`scope_manageable_machines_for_actor`). |
| `full` | Everything in `manage`, plus retire and delegate `operate`/`manage`. Cannot mint another `full` (`can_assign_operator`, `:235-250`). |

- Un-retire stays with machine admins.

**Safety:**

- Every check re-verifies a LIVE active membership (`is_active_member`), so a revoked member's row is
  inert.
- The list scope unions operator machines (`scope_machines_for_actor`, `:253-301`).

**Writes:**

- `services.assign_operator` / `remove_operator` lock the Machine row, refuse retired machines, and
  require the target to be an active member.
- Audit: `machine.operator_assigned`, `machine.operator_updated` (with `old_access_level`),
  `machine.operator_removed`.

**API:**

- `machines/<pk>/operators` (GET/POST) and `machines/<pk>/operators/<user_pk>` (PATCH/DELETE)
  (`admin_api/views_machine_operators.py`, `urls_machines.py:122-132`).
- `.../operator-candidates` lists every active member (`views_machine_candidates.py`).

**UI:** `panels/machine/OperatorsTab.tsx`, shown in the machine drawer.

**Gaps against (c):**

- **G1: creation does not take assignees.** `MachineListCreateView.post` (`admin_api/views_machines.py:111-147`)
  creates the machine only. Its `machine.created` audit is recorded *after* the atomic block. That is
  harmless, but should move inside if creation starts writing operator rows.
- **G2: an operator-only person cannot reach the console.** The auth payload has no machine-assignment
  signal. `staffAccess` shows `machines` only when `manage_machines` is present (`:153`), and an
  action-less user is `governanceOnly` (`:108`). The backend `can_see_machines` would admit them. Even a
  scoped Machine Manager sees an extra operator machine only because they already have the tab.
- **G3: `notifications` needs `actions.length > 0`** (`staffAccess.ts:125`), and machine maintenance
  alerts route by `MANAGE_MACHINES` role scope, not by operator. So an operator gets no maintenance or
  service alerts.
- **G4: operator endpoints are not behind the yuyu recent-reauthentication boundary**, unlike role and
  grant changes. If operators become the main assignment mechanism, apply the same mixin for parity.
- **G5: candidates are every active member**, including plain community members. Some owners may want
  "staff only" (Q8).

### 3.3 Designs for (c)

**Option A: promote tier-3 operators to "Managed by" (RECOMMENDED).**

- Add optional `assignees: [{user_id, access_level}]` to machine create. Write them in the same
  `transaction.atomic()` as the machine through `services.assign_operator`, so locks, validation and
  audit are shared and there is no new authority path.
- On the machine detail, restyle `OperatorsTab` as the PLAN §11 "Managed by" panel with Reassign. Reassign
  is a PATCH or DELETE plus POST. Optionally add one atomic `PUT machines/<pk>/operators` (replace set)
  that audits each delta.
- Close G2: add a server-derived `has_machine_assignments` / `can_see_machines` flag to the membership
  payload entry (batched, one query). There are two ways to make the frontend use it:
  - `getStaffAccess` shows `machines` when `canManageMachines || machineAssigned`, and an action-less
    assignee gets a narrow console (`machines`, plus `notifications` if G3 is solved). Mirror the yuyu
    `grantOnly` branch.
  - Or, once yuyu lands, register a `machine_operator` source in
    `makerspaces/resource_grant_sources.py`, so these machines appear in the shared "Assigned resources"
    workspace exactly like event and booking grants. **This is the better long-term fit** (one
    "assigned to me" surface for all three domains).
- **Invariants:**
  - Tier 1 and tier 2 are untouched, and `rbac.can` is untouched.
  - Fail-closed machine scoping is untouched.
  - An operator row names one machine of one makerspace, and live membership is rechecked.
  - Tenant migration already preserves these rows (decision 22).
  - No new model, so no `data_export` or drift-guard work, apart from snapshot changes if a field is
    added.
- **Migration impact:** none for the basic version.
- **Trade-off:** operator levels are not the action vocabulary. An operator never gets `MANAGE_MACHINES`
  (no machine creation, no type configuration, no shared consumable pools, no tier-1 service queue for the
  type). That is correct for "who runs this machine". If the owner wants assignees to run the
  *service queue* (accept, start or complete jobs) for their machine, check which service-workflow
  guards admit operators today; `access.py` tier 3 covers operate/edit/retire, while service actions go
  through tier 1. Extending that to `full` / `manage` operators is a scoped follow-up (Q9).

**Option B: an auto-created per-machine scoped role.**

- On create, mint a hidden role "‹Machine› manager" holding `manage_machines` and one `RoleMachineScope`
  link, then assign it to the chosen people.
- Problems:
  - With single-role memberships, this **replaces** the person's existing role (for example an Inventory
    Manager would lose inventory). So it depends on M1, and it would then accumulate one additional
    role per machine.
  - It pollutes the roles list and uses custom-role quota.
  - It is dropped by tenant migration (role scopes are DROP), whereas operators survive.
  - The audit is split across `role.created`, `role.machine_scope_changed` and `staff.role_added`.
  - It duplicates tier 3.
- **Not recommended.**

**Option C: per-membership machine scope on the Machine Manager role.**

- Move or extend the scope from role to membership:
  `MembershipMachineScope(membership, machine | machine_type)`. People share the "Machine Manager" role,
  and each person's reach is set per machine.
- Changes `_scope_for_membership`, all batch resolvers, `role_scope_services` (new lock order: makerspace,
  membership, role), payload `is_machine_only`, notifications delegated-recipient scope, tenant
  migration (new DROP model) and data_export (new model).
- This is the most powerful option: it gives full `MANAGE_MACHINES` authority, service queue included,
  per machine. It also rewrites the most heavily guarded invariant in the repo, the ~430-line "Machine
  scoping" section, including the five service surfaces that once bypassed scope.
- **Only worth it if Q9 says assignees must run the full tier-1 lifecycle.**

**Option D: yuyu `ResourceStaffGrant` for machines (`MachineStaffGrant` + invite).**

- Same infrastructure as event and booking grants, with a typed permission vocabulary, invites,
  `source="machine_grant"` and the shared lock helper.
- Problems:
  - It duplicates `MachineOperator`.
  - Resource grants are DROPPED and omitted at both export fidelities, which contradicts decision 22's
    preservation of operator rows. Two parallel per-machine authorities would have to be reconciled.
- Better: take only the *discovery* half (register operators as a source), which is option A's second
  route.

**Recommendation: option A.** That means create-time assignees, a "Managed by" / Reassign panel,
server-derived console visibility (via the yuyu resource-grant source registry once merged), re-auth
parity, and an operator-aware maintenance alert as an optional follow-up. Choose C only if the owner
needs per-person **full** machine-manager authority, including the service queue.

---

## 4. Risks, invariants touched, files, tests, owner questions

### 4.1 Invariants touched

| Change | What it touches |
|---|---|
| New defaults | Hard Rule "Auth & RBAC … seed **four** protected defaults" (CLAUDE.md/AGENTS.md); INVARIANTS Part L (`:454`, already stale); "Handover roles" (do NOT add to `_MEMBERSHIP_ROLE_ACTIONS`). |
| M1 | Part L "authority is action-based via the assigned role" now becomes "via assigned roles". Tenancy: every additional role must be same-tenant, enforced in the DB and failing closed in resolution. Non-escalation and lock ordering (makerspace → membership → roles ascending). The data_export "new model must be classified" rule. Tenant-migration authority guards (`AUTHORIZATION_SOURCES` in `tenant_migration/authority_guards.py` **goes silently blind if code moves out from under it**; add the new resolver files). `tests/makerspaces/test_tenant_servability_guard.py` pins two function bodies to `accounts/rbac.py`, so keep the edits in `rbac_actions.py` / `rbac_memberships.py`. |
| Option A | "Machine scoping" tier 3 (unchanged semantics). Console parity ("navigate from server-scoped responses only"). Decision 22. |

### 4.2 Files that would change

**(a) defaults:**

- `backend/apps/makerspaces/roles.py`
- `makerspaces/models_memberships.py` (N1 enum)
- a new `makerspaces/migrations/00xx_events_bookings_manager_roles.py` (enum `AlterField` + backfill +
  collision freeing)
- `admin_api/serializers_creation_setup.py`
- `admin_api/views_users.py` and `urls_staff.py` (optional)
- `makerspaces/apps.py` (comment)
- Frontend: `panels/RoleEditor.tsx`, `panels/usersModals/CreationWizardSteps.tsx`, `usersModals/types.ts`,
  `MakerspaceEmailSettings.tsx`, `NotificationMuteMatrix.tsx`
- Docs: `CLAUDE.md`, `AGENTS.md`, `docs/INVARIANTS.md`, `docs/RBAC-MEMBERS-FINANCE.md`
- Plus whatever Q1–Q3 decide: `bookings/views_admin_rules.py`, `services_rules.py`, `services_clone.py`;
  `operations/report_definitions_existing.py`; `events/services_badges.py`;
  `events/serializers_event_details.py`; `staffAccess.ts` (reports / emailtemplates gates)

**(a′) M1:**

- Model and migration: `makerspaces/models_roles.py` (or a new `models_role_additional.py`), a migration
- RBAC: `accounts/rbac_actions.py`, `rbac_memberships.py`, `rbac_superadmin.py`
- Machines: `machines/role_scope_resolution.py`, `role_scope_grants.py`
- Roles: `makerspaces/role_authority.py`, `role_assignments.py`, `role_crud.py`, a new
  `role_additional_services.py`
- Yuyu: `makerspaces/resource_grant_locks.py`
- Payload: `accounts/serializers_payload.py`, `org_payload.py`, `schemas_auth.py`
- Admin API: `admin_api/serializers_memberships.py`, `views_memberships.py`, `urls_memberships.py`,
  `recipient_rule_*.py`
- Notifications and reports: `integrations/recipients_resolution.py`, `staff_notifications.py`,
  `operations/report_schedule_rules.py`
- data_export: `classification_domain.py`, `references_core.py`, `datasets.py`
- Tenant migration: `target_projection_rows.py`, `target_projection_references.py`,
  `authority_guards.py`, `tenant_dump_field_snapshot.py`, `tenant_dump_model_catalog.py`
- Frontend:
  - `lib/api/types.ts`
  - `StaffWorkspace.tsx` (role label)
  - `MembersPanel.tsx`
  - `panels/rolesApi.ts`
  - Users / Staff & roles panel
  - regenerate `frontend/openapi-schema.json` and `src/generated/api.ts`

**(c) option A:**

- Backend: `admin_api/views_machines.py` (create assignees), `machines/serializers_machines.py`,
  `machines/services.py` (bulk replace, optional), `admin_api/views_machine_operators.py` (re-auth mixin),
  `accounts/serializers_payload.py` / `org_payload.py` (assignment flag) or a yuyu
  `machines/apps.py` source registration
- Frontend: `staffAccess.ts`, `StaffApp.tsx`, `panels/machine/MachineCreateForm.tsx`,
  `panels/machine/OperatorsTab.tsx` (→ "Managed by"), `machinesApi/*`
- Docs: `docs/INVARIANTS.md` (Machine scoping, tier 3 note)

### 4.3 Tests

**Update:**

- `tests/makerspaces/test_custom_roles_l1.py` (counts, tuples, frozen-mapping parity)
- `tests/makerspaces/test_rbac_f6_backfill.py:42`
- `frontend/.../staffAccess` tab tests: `rbacF6.test.ts`, `staffTabs.moduleGates.test.ts`,
  `staffTabs.familyOnly.test.ts`
- `DashboardPanel.test.tsx` (Events/Bookings Manager fixtures)
- `RoleEditorF6.test.tsx`
- `MachineCreateForm.test.tsx`
- tenant-migration catalog/snapshot pins (`test_tenant_dump_catalog_d1.py`, `test_authority_guard.py`)
  if M1 lands

**Add:**

- Seeding and backfill for both roles, collision rename, protected delete/rename.
- Holding both roles: `rbac.can` for both actions; `makerspaces_for_action` includes the space;
  payload `actions` is the union, `role_names` lists both.
- Sidebar: exactly the Events + Bookings + Home/Inbox sections; no Settings, Inventory or Machines.
- Additional role cannot carry `manage_makerspace` (write refused AND resolution ignores it).
- Cross-tenant additional role is inert.
- Non-escalation when adding a role the actor does not hold.
- Lock-order deadlock regression next to `role_scope_services`.
- Revoking a membership nulls effective actions.
- Notification "role" rule matches an additional role.
- Machine-scope union across two `MANAGE_MACHINES` roles.
- `is_machine_only` false when an additional role adds `view_inventory`.
- Tenant import drops additional roles.
- data_export drift guard green.
- Option A:
  - create with assignees is atomic: an invalid assignee rolls back the machine, and both audits are
    present
  - reassign
  - operator-only member gets the Machines tab and only their machine (frontend + backend parity, "no tab
    that 403s")
  - revoked member's operator row is inert in the console
  - retired machine refuses assignment
- Dashboard: Events Manager sees exactly the two event tiles and Bookings Manager the two booking tiles,
  backend `DashboardView` 200 for both, 403 for an action-less member.

### 4.4 Owner questions that genuinely need a decision

1. **Bookings Manager and booking rules / resource cloning.** Today these are `MANAGE_MAKERSPACE`. Should
   a Bookings Manager edit approval mode and lead times and clone resources? Either re-key them to
   `MANAGE_BOOKINGS` (recommended: these are booking operations, not space settings), or leave them with
   the Space Manager.
2. **Reports.** Should the Event-attendance and Booking-utilization reports (and yuyu booking report
   features) be readable with `manage_events` / `manage_bookings`, instead of `view_audit`?
   Recommendation: yes, re-key those definitions. Granting `view_audit` would also open the full tenant
   Audit log and Accountability tabs.
3. **Registration answers and badge custom-answer bindings** (yuyu) need `VIEW_AUDIT`. Should an Events
   Manager see attendee custom answers? This is a privacy decision.
4. **An existing custom role named "Events Manager" or "Bookings Manager".** Rename it to
   "… (custom)" and leave its holders, or adopt it as the protected default when its actions match
   exactly?
5. **The multi-role rule.** Is the "primary role carries identity; additional roles may not include Space
   Manager / `manage_makerspace`" restriction acceptable? (Recommended.)
6. **Who can assign additional roles?** `MANAGE_MAKERSPACE` only (recommended), or also `manage_members`
   for action-less community roles, as today?
7. **Sidebar.** Separate "Events" and "Bookings" sections, or keep both under "Community" with
   Members, as ux-yuyu-spec §2.2 proposes?
8. **Machine assignees.** Staff only, or any active member (today: any active member)?
9. **What "manages a machine" means.** Is it operator `manage` / `full` (edit, docs, maintenance,
   warranty, retire, delegate; option A), or must assignees also run the machine's service queue and
   consumables like a scoped Machine Manager (option C)?
10. **Notifications for operators.** Should an assigned operator receive that machine's maintenance and
    service alerts?

### 4.5 Other risks

- **Merge ordering.** Both M1 and the new defaults touch `serializers_payload.py`, the
  `views_roles` / `views_memberships` files and `staffAccess.ts`, which yuyu-parity also changes. Build
  this on top of yuyu once it lands in `dev`.
- **Payload size.** `role_ids` / `role_names` are tiny. Keep `/auth/me` at O(1) queries by prefetching
  `additional_roles__role` together with `assigned_role`.
- **Native and offline clients** read `actions` only, so they are union-safe automatically.
- **Unused `role_slug` consumers**, such as the report-schedule `recipient_roles`, should match the
  additional roles as well, or schedules will silently skip co-holders.

---

## 5. Newer work outside `dev` and how it meets the revamp branch

**Fact:** `git log d3e5ed29..dev` and `git log d3e5ed29..origin/dev` are both empty.
`dev = origin/dev = d3e5ed29`, and the revamp worktree is based on it. The newer events and bookings work
lives on **`feature/yuyu-parity`** (25 commits, `316043ea..84fd2337`, last commit 2026-10-15 14:34). Its
lane branches are `lane/yuyu-C`, `lane/yuyu-E`, `lane/yuyu-F`, `lane/yuyu-BK-C/D/E/F`, and
`fix/ckpt1..3b`. Per memory, the owner has authorized merging that programme to dev after tests, so
PLAN §11 item 1 ("merge dev into the revamp") will most likely bring this in.

**What it adds (summary of commits):**

- **Events:**
  - Event-scoped staff grants on a shared resource-grant infrastructure (`ed0baa6b`).
  - Clone, answer edits, undo cancellation, ticket PNG and count visibility (`4f6511f1`).
  - Participating-organizations audience (`729d1ecb`).
  - Durable broadcasts, email invites, analytics, and PDF/CSV exports (`7c0cfe52`).
  - Badge layout designer, print after check-in, certificate designer (`01e7e016`).
  - Event website with speakers, programme, venue, sponsors, FAQs, embeds, share cards, sitemap and
    discover (`5cb8c199`, `lane/yuyu-C` only, merged into `lane/yuyu-BK-F`).
  - Staff event API reads, recent re-auth, org self-service, monitoring, web analytics and a Helm chart
    (`12a375b5`).
  - Three checkpoint fix rounds.
- **Bookings:**
  - Per-resource staff grants (`29fe334c`).
  - Ledger writes roll back with the booking (`9fa6c52d`).
  - Utilisation analytics and exports (`eb5d38fe`).
  - Clone resource, staff booking edits, undo cancel (`b90ce9de`).
  - Confirmation QR and staff arrival check-in (`bc117f87`).
  - Booker broadcasts and reminders (`db587eaa`).
  - Printable passes (`026eb8ee`).
  - Server-client booking API reads (`84fd2337`).
- **Installer:** area presets (`d3dbfa41`, `316043ea`).
- **Migrations:** makerspaces leaf `0089`; `events/0026_event_staff_grants`;
  `bookings/0012_booking_staff_grants`; `accounts/0027-0028`.
- **New frontend surfaces:**
  - About 40 new staff components (`Event*`, `Booking*`, `Granted*Panel`, `*StaffAccess`,
    `*StaffInvitePage`, broadcasts, analytics, designers).
  - New public and member pages (`PublicEventsPage`, `PublicEventDetailPage`, `MemberEventTicketPage`,
    `MyBookings`, `PublicBookingsPage`, `BookingConfirmation`).
  - A new "granted" tab ("Assigned resources") with a `grantOnly` console.

**Conflict-prone files against the revamp.** PLAN says the shell lane "consumes, never modifies" the
gating code, but yuyu modifies it:

| File | yuyu change | Revamp lane that touches it |
|---|---|---|
| `features/staff/staffAccess.ts` | adds the `granted` key and label, puts `granted` in the "Events" `TAB_GROUPS` group, new `hasEventGrants` / `hasBookingGrants` params, `grantOnly` branch | dr-shell builds `SIDEBAR_SECTIONS` from `ALL_TABS`; the "42 keys" count in ux-yuyu-spec §2.1 becomes 43 |
| `staffTabs.ts` | the module map for `granted` | dr-shell |
| `StaffApp.tsx` | single-tenant access via `event_grants` / `booking_grants`, `lockedMakerspaceId` prop | dr-shell (wave 2 shared wiring) |
| `StaffWorkspace.tsx`, `StaffTabContent.tsx`, `StaffTabLoaders.tsx`, `StaffHeader.tsx` | grant workspaces, new panels and loaders | dr-shell, dr-screens-* |
| `AppRoutes.tsx`, `App.tsx`, `main.tsx` | invite pages, web analytics | dr-shell / public screens |
| `EventsPanel.tsx`, `EventDrawer.tsx`, `BookingsPanel.tsx`, `BookingDrawer.tsx`, `MakerspaceSettingsPanel.tsx`, `OrganizationsPanel.tsx` | heavily extended | dr-screens-* restyles |
| `lib/api.ts`, `lib/api/client.ts`, `lib/api/types.ts` (re-auth, grant payload types), `generated/api.ts`, `openapi-schema.json` | regenerated | any lane regenerating the schema |
| `features/inventory/PublicEvent*`, `features/members/*` | new pages and sections | public and member revamp lanes |

**Recommendations:**

1. Merge yuyu into `dev` and then `dev` into the revamp **before** dr-shell finalises
   `SIDEBAR_SECTIONS`, or have dr-shell include `granted` up front.
2. Restyle the ~40 new event and booking components under PLAN §11.5 from the revamp layouts.
3. Build the role, multi-role and machine-assignment work (this document) after that merge, on the
   post-yuyu migration leaves and with its re-auth boundary.

---

## Summary (≤250 words)

**(a) Two new defaults.** "Events Manager" and "Bookings Manager" fit the existing seeding pattern. The
work is:

- 3-tuples in `roles.DEFAULT_ROLE_DEFINITIONS`, with new `MakerspaceMembership.Role` enum values
  (recommended over Member-style NULL legacy).
- A data migration that backfills every makerspace and frees name collisions (the `0041` precedent).
- Updates to the wizard choices, presets and label maps.
- CLAUDE.md/AGENTS.md "four defaults" becomes six.
- Fixing tests that pin `count()==4`.

"Everything to run events/bookings" needs owner decisions, because several checks sit behind other
actions: booking rules and clone need `MANAGE_MAKERSPACE`; the attendance and utilization reports and
event custom answers need `VIEW_AUDIT`.

**(a′) One person, both roles.** Today this is impossible: `uniq_makerspace_user` plus a single
`assigned_role` FK. Recommended design: M1, a primary role plus a `MembershipAdditionalRole` through
table, with actions resolved as a union. This extends RBAC's existing membership∪org pattern. Additional
roles may never carry `manage_makerspace`, and they are dropped on tenant import. The auto-composed role
(M2) and the role picker (M3) are rejected. The sidebar then follows automatically from `allowedTabs`.

**(b) Dashboard.** It already works for all four roles, each seeing only their own tiles.

**(c) Per-machine assignment.** This already exists as tier-3 `MachineOperator` rows (operate / manage /
full, audited, preserved by tenant migration). Recommended option A:

- assignees at machine creation
- a "Managed by" / Reassign panel
- a server-derived signal so operator-only staff see the Machines tab (today they cannot; the yuyu
  resource-grant source registry is the long-term route)
- re-auth parity

**Newer `dev`.** None: `dev` = `origin/dev` = `d3e5ed29`. The events and bookings work (25 commits) is on
`feature/yuyu-parity`. It modifies `staffAccess.ts`, `StaffApp.tsx` and `StaffWorkspace.tsx`, which
collide with the revamp's dr-shell lane, so merge it first.
