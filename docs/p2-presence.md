# Phase 2 presence lane handoff

Branch: `lane/p2-presence`, base `9cc3c9cc`. No staging, commits, frontend changes,
Django execution, Docker execution or real provider requests in this lane.

## Behavior and implementation decisions

- Self check-in requires an active account, the `presence` module, a configured and
  enabled geofence, and a finite location reading inside its radius. Missing/denied
  location, disabled/unconfigured geofencing, poor accuracy (>50m), and outside readings
  return typed errors with staff-check-in guidance. Accuracy never widens the radius.
  Latitude, longitude and accuracy are validated and discarded: no coordinate fields,
  audit coordinates, distance records, or notification coordinates are stored.
- **GPS is a spoofable convenience control, not proof of identity or a security
  boundary.** Authorized staff can check a person in without location, including at a
  staffed kiosk using its authorized staff principal. This adds no station-only grant
  and never accepts a client-supplied `staff` bypass flag.
- Defaults are 60/120/180/240 minutes. Explicit tenant presets continue through the
  existing `validate_presence_presets` validator. Phase 3 synchronizes the central bootstrap
  default and installs presence on existing spaces through makerspaces/0096; new spaces opt in.
- `working` requires an owned `MemberProject` in this makerspace. Private projects are
  selectable but their titles never appear on the TV. Public title projection also
  honors the frozen profile consent, account/membership standing, and `show_projects`
  predicate. `visiting` is available to active members. Account-only visitors receive
  `guest`; revoked memberships cannot be bypassed by reclassifying their owner as a guest.
  Staff-recorded walk-ins reuse an existing walk-in account belonging to this space.
- `attending_event` is assigned only by `presence.event_attendance.event_attendance`.
  The single Events edit schedules it after commit for live QR/station ticket check-ins
  with no supplied historical timestamp. The hook reloads attendance and immutable
  check-in evidence, requires a currently running published event and a fresh server
  receipt (60 seconds), rejects offline sync/ordinary staff marks/historical evidence,
  and binds a session once per registration. No contact-to-account inference occurs.
  Errors, module-off and tombstone states never fail the committed event operation.
- A live check-in starts from now; identical starts reuse the same session. Renewals
  extend from now, increment a source revision, invalidate previous reminder envelopes,
  and retain claim-session deadlines. An expired session can renew during the 10-minute
  reminder window; older history requires a new geofenced check-in. Event renewals are
  additionally bounded by the event end and current attended/published state.
- `expire_presence_sessions_task` runs every minute under both Celery beat and the
  beat-less scheduler, closing rows at their actual expiry. It uses bounded tenant
  batches and the migration source gate. Expiry persists even if reminder creation
  fails; the next sweep retries the reminder. Stale reminders (>10 minutes) are marked
  skipped instead of being delivered after downtime.
- At expiry a revision-bound personal envelope uses `feature=stream=presence`,
  `event=expired`, `source_kind=presence.expiry`. Initial selections are `in_app` and
  `native_push`, no email fallback; existing explicit channel selections win. Delivery
  still applies account standing, module gates, tenant channel switches, opt-outs,
  native device grants and source eligibility through the frozen outbox contract.
  No room, email, Telegram callback, or new provider transport is introduced.
  The optional ten-minute advance reminder is intentionally not enabled.
- Both display settings default ON. `show_names=false` anonymizes everyone and removes
  all project/event titles. With names ON and personal opt-out ON, a person's hide flag
  anonymizes their row and removes its titles. With opt-out OFF, names are shown despite
  the flag. Anonymized labels are `A member` or `A guest`. Check-in responses expose
  `names_displayed` and `personal_opt_out_allowed` so the UI can explain mandatory names.
  Profile publication does not control whether the person's presence name is displayed.
- TV data has exactly `display_name`, `status`, `since`, and optional public
  `project_title`/`event_title`. No identifiers, coordinates, contacts or history.
  Servability, module and origin/known-tenant-host checks run before cache access.
  The shared server cache is keyed `presence:tv:<makerspace_id>:<display_version>` only
  (no viewer identity) and lasts at most 30 seconds. `display_version` is a UUID bumped
  in the same transaction as every session, settings, preference, project, profile,
  event, registration, membership and account save touching a present person, so a
  committed change always reads a new key; a cache hit performs no presence query.
  Writes that bypass model signals (`queryset.update()`, e.g. the frozen
  `release_handle` consent withdrawal or series lifecycle bulk updates) are bounded by
  the 30-second TTL. Cache failures serve a fresh safe projection. Authenticated staff previews bypass the
  shared cache and return `no-store`; public responses use `max-age=0, s-maxage=0` so
  intermediaries cannot retain withdrawn names/titles. TV reads remain throttled.

## Models and migration

Only migration: `presence/0003_presence_programme.py`, chained from actual leaves
`presence/0002_claim_session_provenance`, `makerspaces/0094_public_profile_contract`,
and `events/0035_audience_organizations_and_staff_role_labels`.

- `PresenceSession`: adds required `account` FK, nullable membership, status,
  nullable project FK, nullable unique event-registration FK, hide flag, revision,
  expiry-reminder marker, and expired/staff-ended reasons. The existing required
  `member` FK remains for shipped history/claim consumers. Migration backfills account
  from member; a DB check requires both to agree. This is a compatibility bridge,
  not a second identity. Normal ORM creation fills the missing alias in `save()`.
- `PresenceSettings`: one row per makerspace; `show_names`,
  `allow_personal_opt_out`, and the derived display-cache UUID generation.
- `PresencePreference`: unique `(makerspace, account)` and `hide_on_display`.

The new fields contain references, booleans, enums and timestamps, not copied contact
PII. No new encryption mapping is necessary. Reminder content uses the already
encrypted `NotificationEnvelope` and `NotificationInboxRow` fields.

## Routes and API fields

Paths below are complete; existing member routes retain their no-trailing-slash form.
All methods have drf-spectacular request/response/error declarations.

| Method | Path | Input / output |
|---|---|---|
| GET | `/api/v1/public/makerspaces/<slug>/presence/now/` | Anonymous TV array; fields described above. |
| POST | `/api/v1/public/<slug>/presence-sessions` | `duration_minutes`, optional `status`, `project_id`, `hide_on_display`, `latitude`, `longitude`, `accuracy`; returns current session. |
| GET | `/api/v1/public/<slug>/presence-sessions/current` | `{active, session, presets, personal_opt_out_allowed, names_displayed}`; policy is present even without a session. |
| POST | `/api/v1/public/<slug>/presence-sessions/current/renew` | `duration_minutes`; returns renewed session. |
| POST | `/api/v1/public/<slug>/presence-sessions/current/end` | No body; `{active:false, session:null, personal_opt_out_allowed, names_displayed}`. |
| GET | `/api/v1/public/<slug>/presence-sessions/projects` | Paginated own project options `{id,title,public_visible}`. |
| GET, PATCH | `/api/v1/public/<slug>/presence-sessions/preferences` | `hide_on_display`; PATCH also changes current sessions. |
| GET | `/api/v1/admin/makerspace/<id>/presence-sessions/current` | Paginated present roster; account identity/name, role, status and session times; no contacts. |
| POST | `/api/v1/admin/makerspace/<id>/presence-sessions/check-in` | `account_id`, `duration_minutes`, optional status/project/hide fields; authorized staff bypass GPS. `account_id` must be on THIS makerspace's roster (a member or this space's walk-in); any other id is 404, so ids cannot probe other tenants. Account-only guests self-check-in. |
| POST | `/api/v1/admin/makerspace/<id>/presence-sessions/check-out` | `account_id` (a roster account, or an account with presence here); `{active:false, session:null}`. |
| GET, PATCH | `/api/v1/admin/makerspace/<id>/presence-sessions/privacy` | `show_names`, `allow_personal_opt_out`; requires `manage_makerspace`. |

Other member routes require an active signed-in account; existing claim sessions keep
their tenant/provenance and absolute expiry limits. Claim routes cannot edit durable
display preferences. Staff roster/check-in/out require scoped `manage_members` through
`accounts.rbac`. Roster now follows the repository's paginated-list convention.

Session responses include `started_at`, `expires_at`, `ended_at`, `end_reason`,
`active`, `status`, `project_id`, `hide_on_display`, `names_displayed`, and
`personal_opt_out_allowed`. Member inputs deliberately cannot supply an event ID/status.

## Registry entries

- New opt-in `presence` module, with no membership dependency, so account-only guests
  work when membership is disabled. Module purge removes sessions, settings and
  preferences; whole-tenant purge deletes presence before protected memberships.
  Retention registration survives tombstoning. Hardware/member presence guards skip
  only the presence factor when this module is off; membership and waivers still apply.
- Data export: explicit field allowlists for all three models; tenant datasets for
  sessions/settings/preferences; account FK edges and preference subject selector.
  Session tenant ownership no longer depends on the nullable membership relation.
- Tenant migration: literal field snapshots, explicit DROP for all three presence
  models, source-local audit targets, updated membership-dependency declaration, and
  conservative authority-source/field registrations. Source exports retain history;
  importing never resurrects source presence or its display consent. The schema digest
  pin was **not** changed.
- API client scopes for every new public member/TV method; claim-route classifications;
  slug target registration for source-gate/origin resolution. Staff paths carry the
  existing authoritative `makerspace_id` target. There are no new anonymous writes or
  provider callbacks to exempt.
- Source-gate task and fanout entries for expiry. Both scheduler registries use the
  same minute interval and omit the task when presence is tombstoned.
- Notification feature/event defaults and `NotificationSource` registration. Shared
  delivery providers and frozen envelope/resolution fields are unchanged.
- Audit presentation entries for renewal, preferences, privacy settings, expiry,
  reminder queued/skipped; existing start/end/revocation entries remain in place.

## Integrator requests

1. **DONE in Phase 3:** `backend/apps/makerspaces/validators.py` uses
   `DEFAULT_PRESENCE_PRESETS = [60, 120, 180, 240]`; bootstrap, configuration editors and
   the presence API share the default while preserving explicit tenant presets.
2. Update `docs/INVARIANTS.md`: replace the advisory-geofence paragraph near line 1389
   with v2's hard self-check-in rule, spoofability caveat and staff alternative; remove
   the earlier assertion that disabling `presence.geofence` cannot block check-in.
   Record the module, guest identity, expiry/outbox, privacy matrix and TV cache rules.
3. Update `docs/MODULES.md` for opt-in `presence`, its guest support, behavior when off,
   and its purge contents. Update `docs/SOURCE-MAP.md` for the new presence modules and
   `docs/PROJECT-HISTORY.md` for this lane. No edits to these owner-controlled docs here.
   Refresh stale descriptive copy in `capability_definitions.py` (geofence) and
   `separability/tombstones.py` (presence now has its own module key).
4. Wire the frontend to the API shapes above, including the mandatory-name disclosure
   and paginated staff roster. **Phase 3 rollout done:** makerspaces/0096 installs presence
   on every existing row, including archived tenants, preserving other choices with a no-op reverse.
   New makerspaces opt in. Current-session and roster responses now expose top-level name/opt-out
   policy even when empty; MakerspaceSettingsPanel mounts privacy for Space Managers with presence on.
5. On the Django host, check migrations, generate OpenAPI with spectacular
   `--format openapi-json`, regenerate the frontend client, and recompute
   `tenant_dump_catalog.CATALOG_SCHEMA_SHA256` from the **merged** model graph.
6. Run `./scripts/dev.sh test tests/p2_presence` and relevant existing presence, claim,
   event-check-in, export/migration, module/purge, scheduler and tombstone suites.
   The Claude verifier updated `tests/presence/test_geofence_c7.py`, `test_presence_m3.py`
   and `test_guard_m3.py` (plus a new `tests/presence/fence_helpers.py`) to the hard
   geofence; like all backend tests they are gitignored and must be carried over from
   this worktree. Preset/bootstrap tests must assert `[60, 120, 180, 240]` after Phase 3.
   Then run the final integrated variation matrix. This lane makes no runtime pass claim.

## Contract change requests

The frozen `NotificationFeature` vocabulary lacks `presence`. Exact requested addition:
add `PRESENCE = "presence", "Presence"` to
`backend/apps/integrations/notification_enums.py` and the corresponding integrations
choice-field migration on the merged graph. Let the existing personal selection API
enumerate/accept this category without changing any request/response field or signature.
The current lane works around it with literal `presence` catalog entries, a registered
source, and default web/push selections in the existing preference model. Delivery can
work now, but the shared preference editor cannot display/edit that category until the
vocabulary is extended. No frozen contract source was edited.

## Validation and deferred work

Local validation is syntax/AST parsing, file-size checks and `git diff --check` only.
Tests are in the gitignored `backend/tests/p2_presence/` directory and were not run.
They cover service/API boundaries, privacy/cache withdrawal, guest/walk-in identity,
event post-commit/idempotency/replay rules, expiry/retry/envelopes, actual inbox delivery,
channel opt-outs, module/tombstone guards, import DROP and tenant isolation.

Optional advance reminders are not enabled. Central-preset synchronization and existing-space
rollout landed in Phase 3, and the privacy settings section is mounted. Shared notification preference
vocabulary and runtime verification remain; merged schema/digest checks belong to integration.

## Files changed

The implementation file inventory follows below. Test files are explicitly included
because Git intentionally ignores them.

```text
backend/apps/accounts/claim_routes.py
backend/apps/accounts/claim_routes_p2_presence.py
backend/apps/apiclients/scope_registry_p2_presence.py
backend/apps/apiclients/scope_registry_routes.py
backend/apps/audit/presentation_catalog.py
backend/apps/audit/presentation_catalog_p2_presence.py
backend/apps/data_export/classification.py
backend/apps/data_export/datasets.py
backend/apps/data_export/references.py
backend/apps/data_export/subject_selectors.py
backend/apps/events/services_checkin.py
backend/apps/integrations/notification_catalog.py
backend/apps/integrations/notification_catalog_p2_presence.py
backend/apps/makerspaces/lifecycle_purge.py
backend/apps/makerspaces/module_purge_plans.py
backend/apps/makerspaces/module_registry_catalog.py
backend/apps/makerspaces/module_registry_p2_presence.py
backend/apps/makerspaces/origin_scope_routes.py
backend/apps/operations/management/commands/run_scheduled_tasks.py
backend/apps/presence/apps.py
backend/apps/presence/cache.py
backend/apps/presence/display.py
backend/apps/presence/event_attendance.py
backend/apps/presence/geofence.py
backend/apps/presence/guard.py
backend/apps/presence/migrations/0003_presence_programme.py
backend/apps/presence/models.py
backend/apps/presence/notifications.py
backend/apps/presence/policy.py
backend/apps/presence/privacy.py
backend/apps/presence/purge.py
backend/apps/presence/schedule.py
backend/apps/presence/schema.py
backend/apps/presence/serializers.py
backend/apps/presence/services.py
backend/apps/presence/services_claim.py
backend/apps/presence/signals.py
backend/apps/presence/tasks.py
backend/apps/presence/urls.py
backend/apps/presence/urls_admin.py
backend/apps/presence/views.py
backend/apps/presence/views_public.py
backend/apps/presence/views_staff.py
backend/apps/tenant_migration/audit_references_targets.py
backend/apps/tenant_migration/authority_guards.py
backend/apps/tenant_migration/catalog_p2_presence.py
backend/apps/tenant_migration/gate_policy_tasks.py
backend/apps/tenant_migration/membership_dependencies.py
backend/apps/tenant_migration/tenant_dump_field_snapshot.py
backend/apps/tenant_migration/tenant_dump_model_catalog.py
backend/config/settings.py
backend/tests/p2_presence/conftest.py
backend/tests/p2_presence/test_display_api.py
backend/tests/p2_presence/test_events_tasks.py
backend/tests/p2_presence/test_sessions.py
docs/p2-presence.md
```
