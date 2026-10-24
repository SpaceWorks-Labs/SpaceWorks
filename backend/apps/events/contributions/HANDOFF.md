# Events programme - Lane C2 implementation handoff

Worktree `ev-c`, branch `lane/events-c`, on top of owner-committed C1 `27b89c6e`.
C2 implements the remaining C-owned domain work. This is **not integration acceptance**:
the exact shared hooks and required runtime verification are listed under UNFINISHED.
No staging, commit, merge, push, app migration, shared-file edit, generated schema/client
edit, Docker execution or Django test execution was performed.

## Built per approved plan section

| Plan | C2 completion |
| --- | --- |
| section 4 / section 12 | Commands fence declared accounts before event locks and lock each declared account's live authority before domain rows. Auto-approval and FIFO promotion refuse changed, unfenced issuers. Target mentor fences cover bulk allocation, activation, explicit help assignment and office-hour booking. Existing 62 frozen route names/paths/methods are unchanged. |
| section 6 roles / section 12B / decisions 28-30 | Posting auto-approval runs the same live issuer, F/P approval/CoC, requirement, frozen-source and source-entitlement policy as manual approval. Explicit owner decline, manager rejection/completion, imported-role reconfirmation and staff answer reopening are implemented. Reconfirmation returns to a fresh owner draft; it grants nothing. Reopening archives canonical answers/reason/old lock, calls P's new-revision hook, clears approval/consent and closes mentor mappings/claims and future bookings. Active-sibling collisions return a typed error. No computed age is persisted. Owner-only date-source export delegates to P. Draft volunteer/mentor applications qualify for B's own resume workflow, without attendee registration or sponsor consent. |
| section 6 requirements / volunteering | Exact training/briefing exception records keep private reasons; waiver/CoC are never override kinds. The requirement port receives only the applicable exception IDs and must still enforce real evidence. FIFO safely skips withdrawn requirements, uses the current fenced issuer and preserves manual entitlements. Existing attendance/correction/verified-hours services retain immutable evidence; correction/audit tests added. |
| section 6 assignments | Persisted run records contain every mapping and every uncovered team, including zero-coverage outcomes; replay uses the original run. Collection POST proposes; `/assign/` activates the bulk result. Proposed -> active -> ended commands recheck live eligibility, capacity and conflicts. Mapping reads now include typed team/mentor/run/interval fields. |
| section 6 help / section 12D | Configurable category priority/skills/open limit, bounded claim TTL and request expiry. Generation/UUID-bound renewal, command-time expiry checks, source-fenced bounded expiry worker, terminal expiry and stale-claim release. Comments cannot bypass deadlines. Attention deduplicates by open period; stale-period/expired notices do not dispatch. Existing claim/office-hour/round races are retained; expiry-versus-renewal race added. |
| section 6 configuration / rounds / analytics | Own or authorized-manager mentor skills/private affiliation/capacity/availability editing, booking-safe schedule changes and explicit off-duty empty schedules. Own declared conflicts and manager affiliation configuration with private scoped reads. Explicit nominations require a completed non-away visit. Personal bounded nudge mute, round coverage/attention and private low-n/zero-variance diagnostics. Round UI configures shared forms, fresh-eyes/conflict policy and conditional help triggers. |
| section 6 import/export/admission / section 9 | Bounded CSV/XLSX explicit-ID exports require full manager plus tenant VIEW_AUDIT; formula/control-like cells are inert and no contacts/DOB sources enter mapping exports. A/G admission port requires an explicit real contributor ticket/capacity policy and returns a same-event/member/ticket admitted registration. C creates no attendee row. E's certificate subject resolver requires independently verified/adjusted positive work minutes and returns versioned evidence under subject fences; display roles and imported roles do not establish eligibility. |
| section 11 / section 13 / decisions 31-33 | Space Works primitives/layouts, existing theme classes/tokens, lucide, shared F form-builder/renderer slots. Posting/shift/office-hour setup, mentor settings/conflicts, help categories, assignment lifecycle, role lifecycle/overrides/admission, owner decline/withdraw/export, help renewal/contact, round nomination/setup/triggers, attention/mute and CSV/XLSX controls. PATCH editors send edited fields. G retains AppShell/route mounting, E photo/card selection and ARTWORK ownership. No borrowed assets/fonts/palette or automatic photo choice. |

## Files

[integration-manifest.json](integration-manifest.json) contains the complete production,
frontend, test/helper, field/FK/User-edge, constraint and route inventories.
[manifest.py](manifest.py) supplies registry, task and adapter inputs; it installs nothing.
All changes stay inside `contributions/**`, `mentoring/**`, their section 15 frontend/test
counterparts, plus the two expressly requested scratchpad rerun lists.

Main additions:

- Contributions: `role_policy.py`, `models_policy.py`, `requirements_workflow.py`,
  `models_admission.py`, `admission_adapter.py`, `certificate_subjects.py`,
  `views_completion.py`, `urls_completion.py`.
- Mentoring: `models_operations.py`, `help_expiry.py`, `configuration_workflow.py`,
  `serializers_configuration.py`, `import_export.py`, `views_configuration.py`,
  `views_completion.py`, `urls_completion.py`.
- Frontend: `ContributorSetupPanel`, `PostingEditor`, `ShiftEditor`, `MentorSettingsPanel`,
  `MentorConflictForm`, `MentorAttentionPanel`, `MentorAssignmentLifecycle`, `RoleLifecycleActions`,
  `MentorRoundSetup`, `RoundHelpTriggers`, `setupFields`, member `RoleOwnerActions`,
  and `completion.test.tsx`; existing lane components supply integration slots.

## Model manifest - G authors all migrations

**32 concrete models: C1's 27 plus five new models.** Domain barrels explicitly import them.

| New model | Ownership/history and important fields |
| --- | --- |
| `EventRoleAnswerRevision` | Event/host; assignment FK, nullable actor User edge, encrypted canonical answers/reason, schema version, previous lock timestamp; append-only. P owns the corresponding frozen-source revision. |
| `EventRequirementOverride` | Event/host; assignment FK, optional shift FK, nullable actor User edge, exact training/briefing reference and encrypted reason; append-only. No waiver/CoC override vocabulary. |
| `EventContributorAdmission` | Event/host; assignment OneToOne, real registration PROTECT FK, explicit capacity policy and nullable actor User edge; append-only. Not a replacement registration. |
| `MentorAssignmentRun` | Event/host; run UUID, mode, typed mapping/team/mentor IDs, unsatisfied team IDs, nullable creator User edge; append-only and unique(event, creator, run). |
| `MentorAttentionPreference` | Event/host, member User edge, mute deadline; unique(event, member), portable omission. |

Changed declarations: help-type claim/expiry policy and bounds; mentor profile capacity bounds;
mentor mapping ended-state shape; help request UUID/generation/lease expiry/terminal deadline/
open-period generation and claim metadata shape. G must reset transient claims on portable
import/deployment recovery and leave imported roles inert. Add all new append-only, source,
field/User-edge, cross-event, encryption, uniqueness, lifecycle and purge guards. Typed JSON
remaps for run decisions/uncovered teams and canonical revision derivation IDs are listed in
the manifest. No C model owns object bytes or sponsor-consent authority.

## Routes

The original **62** frozen routes are retained. Their OpenAPI annotations now include the
expanded admin posting/shift configuration, assignment run/mapping, help lease, round policy
and attention response fields. G alone regenerates schema/client snapshots.

**18 C2 proposals remain deliberately unmounted** pending G contract ratification:

- `contributions.urls_completion.ADMIN`: role complete, reject, reopen-answers,
  reconfirm, requirement-overrides, admit (POST).
- `contributions.urls_completion.MEMBER`: owner role decline (POST), export (GET/HEAD).
- `mentoring.urls_completion.urlpatterns`: mentor profile GET/PATCH; help-type
  collection GET/POST and detail GET/PATCH; conflict GET/POST; mute POST;
  nominations POST; help renew POST; mapping activate/end POST; team export GET/HEAD.

Exact names, paths, methods and view classes are in `completion_route_proposals` in the JSON
manifest. Every view includes input/response/error annotations and the existing auth/throttle/
no-store boundary. No general arbitrary-action route or sponsor-consent alias was introduced.

## Tests and evidence

- `py_compile`: **95 production/test/helper Python files passed**. This is syntax validation,
  not Django model loading, migrations or PostgreSQL execution.
- Every lane production Python/TS/TSX file remains at most 300 lines.
- `npx tsc -b`: passed.
- Focused Vitest: **3 files / 19 tests passed**, including original frozen consumers,
  shared-builder use, retained input, rescheduling, mentor capacity, private diagnostics,
  import defaults, invitation decline, mapping activation, triggers and axe checks.
- Backend: **21 actual `test_*.py` files written, not executed**. The ten new files are
  `contributions/test_{role_lifecycle_completion,role_date_reopen,contributor_admission_certificates,requirement_fifo_hours}.py`
  and `mentoring/test_{assignment_lifecycle,help_expiry,conflict_configuration,import_export,office_changes,notifications_triggers_diagnostics}.py`.
  Existing role forms/subject tests were extended/corrected. Test ports substitute A/P/F/G
  and do not certify their production crypto, capacity or authority adapters.
- Independent read-only backend review completed; identified issuer/fence, mentor cleanup,
  uniqueness, expiry, schema and direct-service exception-test findings were corrected.
  The reviewer did not execute Django tests. `codex doctor` still reports unavailable
  config/home/provider connectivity, so no independent CLI runtime review is claimed.
- `git diff --check` passed; index remains empty.
- Both LF-only rerun lists at the requested scratchpad `ev/` root contain all 21 backend
  test paths relative to `backend/`: `C2-rerun-files.txt` and appended/deduplicated
  `C-rerun-files.txt`. Tests are ignored by this checkout's existing gitignore; G must collect
  the actual files on disk. No pytest configuration was changed.

## CROSS-LANE needs

C2 supplies concrete adapters and unmounted URL lists. The integration work below is assigned
to **G before integration acceptance**, with A/P/E/F/B/D/ARTWORK as indicated. The previous
C1 shared authority, F/P forms, canonical D sponsor consent, provider reauthorization,
E photo/card and AppShell requirements remain binding.

## UNFINISHED - exact integration hooks and required verification

1. **G model/registry wiring and migrations.** Import both domain model barrels from
   `apps/events/models.py`; author migrations for the 32-model manifest and changed fields;
   install `manifest.py` encryption/append-only/User-edge/source/authority/portability/purge
   entries. `EventRoleAnswerRevision.answers` retains P derivation references and must be
   remapped with its frozen sources; never materialize computed age. Preserve independently
   owned evidence; omit transient claims/outboxes/import credentials/preferences. Run all
   21 files in `C2-rerun-files.txt` plus section 14 registry, portable round-trip/purge/restore and
   source/fence race tests. C cannot execute these without the central registration/migrations.
2. **G HTTP contract ratification/mounting.** Add the 18 `completion_route_proposals` to G's
   `tests/events/programme/contracts/fixtures/routes-v3.json` (or its ratified successor),
   origin target lookups, claim/delegated policy, API-client exclusions and source boundaries;
   mount `urls_completion.ADMIN`, `.MEMBER` and mentoring `.urlpatterns` in the corresponding
   shared barrels. Update the central contract tests and regenerate OpenAPI/client. Extend
   `test_contracts.py` against the ratified new fixture; its current 62-route guard intentionally
   remains unchanged. No C2 URL list is included by the original frozen modules.
3. **G/P/F role forms and requirements.** Install `ports.RoleForms.reopen_locked(subject,
   previous_version, locks)` to archive the current frozen DOB/as-of sources and begin a new
   owner-confirmed revision without KMS/account-row locking under event locks. Install
   `export_owner(subject, actor_id)` for owner-only DOB/date-source export. Implement the
   extended `require_requirements(..., override_ids=())` with exact live training/briefing
   exceptions and non-bypassable waiver/CoC evidence. Preserve F-only schema validation and
   P-only preparation/epoch/date checks. Run `test_role_forms.py`, `test_role_date_reopen.py`,
   `test_role_lifecycle_completion.py`, `test_requirement_fifo_hours.py` plus joint A/F/P
   date/fence/key/vault-delete/account-erase tests from section 16.
4. **G/A real contributor admission.** Install `ports().admissions.admit_locked` implementing
   `admission_adapter.ContributorAdmissions`. A/G must mark/configure the distinct contributor
   ticket, serialize both declared capacity policies using normal ticket/event counters,
   require real audience/waiver/CoC/money prerequisites and return an admitted registration
   of the requested event/member/ticket. Missing adapter returns 503. Run
   `test_contributor_admission_certificates.py` and real A last-place/retry/payment/waiver
   tests. C has no authority to add ticket-purpose/configuration fields in A/G-owned models.
5. **G/E thank-you issuance and selected-profile cards.** Register
   `certificate_subjects.resolve(event_id, assignment_id, locks)` as E's contribution source;
   E issues through its normal certificate service, freezes the returned evidence versions,
   revalidates them and handles hours/role changes via its revocation rules. Run
   `test_contributor_admission_certificates.py` and E issuance/retry/correction tests. Mount
   E's selected public profile/photo projection and print/card renderer; C never chooses a
   profile/photo or creates a staff profile. Joint E/B/D photo/consent URL-revocation tests
   and canonical D-only sponsor consent tests remain required.
6. **G/F tasks/provider boundary.** Schedule `mentoring.help_expiry.expire(event_id, limit=100)`
   every minute per live event via the shared task/scheduler inventory, alongside existing
   notification sweeps and escalation. Install after-commit enqueue, broker-loss recovery,
   tenant private-write preparation outside locks and provider idempotency/live recipient
   checks. Run `test_help_expiry.py`, `test_notifications_triggers_diagnostics.py`, existing
   race files, and real provider/source-freeze tests. Imported/restored claims must never
   revive leases or dispatch stale production notices.
7. **G frontend/ARTWORK mounting and browser acceptance.** Mount in AppShell:
   `VolunteerManager.setupTools=<ContributorSetupPanel renderFormBuilder={F bridge}>`,
   `renderRoleTools={RoleLifecycleActions}` for authorized managers;
   `MentorDeskPage.settingsTools` with `MentorSettingsPanel`, `HelpCategoryEditor` and
   `MentorConflictForm`; `attentionTools=<MentorAttentionPanel>`; `rounds` with
   `MentorRoundSetup`/`MentorRoundsPanel`; assignment `completionReady=true`, owner
   `RoleApplicationForm.completionReady=true` and `TeamImportPanel.canExport=true` only
   after the new contracts and live report authority are wired. Supply E card/photo and
   ARTWORK consumers rather than substitute assets. Run the three recorded frontend files
   plus integrated mobile/light/dark/keyboard/reduced-motion/contrast/browser journeys and
   the required Impeccable audit. No browser acceptance is claimed in this lane.

There is no remaining intentionally deferred C-owned domain implementation from the C1
UNFINISHED list. Integration remains blocked on the named shared hooks and unexecuted runtime
verification above; completion is not a claim that those hooks/tests have already landed.
