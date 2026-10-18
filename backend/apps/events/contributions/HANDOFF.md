# Events programme — Lane C implementation handoff

Worktree: `ev-c`; branch: `lane/events-c`. Built against G1 `72bf7be7` and the
approved plan's frozen fixtures. **This is a partial lane delivery, not integration
acceptance.** The completion work below must land before programme enablement.
No staging, commit, merge, push, migration, shared-file edit, generated schema edit,
Docker execution or Django test execution was performed. The pre-existing untracked
`frontend/src/test/staffActor.ts` was left untouched.

## Built per plan section

| Plan | Implemented |
| --- | --- |
| §4 / §12 | A common command boundary: source boundary, declared tenant/account fences before event locks, live authorization before and after locks, digest-bound receipts, safe audit metadata, integer-preserving typed errors, no-store reads and strict command input. No nullable joined `select_for_update`. |
| §6 contributions / §12B | Role-only draft/edit/submit, approval, owner date-review, withdrawal/revocation, posting/shift configuration, owner subject resolution without registration, canonical answer storage that rejects persisted numeric age in derived slots. F/P preparation happens before the command transaction; prepared application/derivation/save insertion happens under declared locks. |
| §6 grants | C-owned role/shift entitlement synchronization, live time/source/track queries, source-only revocation, manual-source preservation, future source container preservation, imported-role refusal and subset/scope adapter. G retains the existing grant-container lifecycle and manual-grant hooks. |
| §6 volunteering | Locked capacity, approval/waitlist/FIFO promotion, requirement hooks, overlap checks, separate shift attendance, server timestamps and bounded desk corrections, elapsed minutes/breaks, verification/adjustment history and self-verification refusal. Safe reference reminders at one week/two days/event-local day-of. |
| §6 assignments | Deterministic manual, balanced round-robin and weighted skill-match preview/allocation with capacity, availability and conflict exclusions. Persisted mappings carry the run UUID. Preview does not grant access. |
| §6 help / §12D | Team and mentor origins; raising never claims; parent-locked comments; claim/release/resolve/reopen; team cancellation releases the mentor; assigned priority window, skill/shift/conflict checks, duplicate limits, safe queue versus private detail projections. Fifteen-minute attention uses the latest open period, not the original creation time. |
| §6 rounds | Dynamic bounded configuration, one live round per production/practice scope, generation/UUID/expiry checks, ten-minute leases and 30-second client heartbeat, fresh-eyes/conflict reason policy, notes without prior ratings, away/nominations and deduplicated conditional help triggers. Encrypted session-scoped device drafts are cleared on scope exit and round close. |
| §6 office hours | Independent team-place allocation, eligible team ownership, future availability/mentor duty conflicts, redacted caller-owned conflicts, idempotent cancellation. Explicit `PATCH /shifts/{id}/` with `cancel_bookings:true`, a reason and schedule/state changes cancels and notifies booked teams before rescheduling; ordinary occupied-slot edits refuse. |
| §6 analytics/import/practice | Private response/handling/visit distributions, per-round coverage, expired leases, active mentors, away attention, quiet/long-visit nudges and low-n/zero-variance-safe generosity diagnostics. CSV/XLSX explicit-ID parser, formula/expansion/size bounds, encrypted expiring preview and digest-checked commit through A's team adapter. Practice help creates no outbox; production reads exclude practice. |
| §11 | Persisted safe-reference outboxes, after-commit enqueue, periodic recovery, bounded claims/retries and provider idempotency. Delivery adapters must revalidate current recipients and authority. No private help text or attachments are copied to room messages. |
| §13 / decisions 28–33 | Exported participant contribution, application, shifts, help and office-hour components; mentor queue/detail, rounds, assignment preview, analytics, volunteer hours and import/practice components. Existing layouts/primitives, CSS tokens and lucide icons; no artwork, font or palette imports. Required F/P form bridge and D consent slot preserve sole ownership. |

## Files

The exact file lists, all model declarations, FK/User edges, constraints and all 62
named route definitions are in [integration-manifest.json](integration-manifest.json).
This manifest is inert; it installs nothing. Registry inputs and exclusions are in
[manifest.py](manifest.py). The two domain model barrels are `contributions/models.py`
and `mentoring/models.py`; G must explicitly import them through its own barrel.

Main service files: `commands.py`, `sources.py`, `authority.py`, `role_workflow.py`,
`management_workflow.py`, `shift_workflow.py`, `attendance_workflow.py`,
`mentoring/{assignment_workflow,help_workflow,office_hours_workflow,round_workflow,
round_management,round_triggers,analytics,diagnostics,round_board,import_workflow}.py`.
Each domain owns its serializers, views, URL lists and notification workers.

Frontend: `frontend/src/features/events/contributions/**` and
`frontend/src/features/staff/mentorDesk/**`. These are exported components for G to
mount inside AppShell; this lane did not modify AppRoutes or EventDrawer tabs.

## Model manifest

27 concrete models, no migrations:

- Contributions: `EventRolePosting`, `EventRoleAssignment`, `EventGrantEntitlement`,
  `EventSponsor`, `EventSponsorTrack`, `EventShift`, `EventShiftSignup`,
  `EventShiftAttendance`, `EventContributionHours`, `EventContributionHoursEntry`,
  `EventShiftAttendanceCorrection`, `EventContributorNotice`.
- Mentoring: `MentorProfile`, `MentorTeamAssignment`, `EventHelpType`,
  `EventHelpRequest`, `EventHelpAction`, `EventHelpComment`, `OfficeHoursBooking`,
  `OfficeHoursChange`, `MentorRound`, `MentorRoundLock`, `MentorRoundCheckin`,
  `MentorConflict`, `MentorNomination`, `MentorImportPreview`, `MentorNotificationIntent`.

Every model inherits host/event/version; entitlement overrides the event FK to
nullable and adds series for existing manual series grants. Roles/shifts remain
event-only. Null/non-null sponsor active-role uniqueness is split correctly.
Source alternatives, live uniqueness, capacity parents, attendance ordering and
the help claimed-by shape have explicit constraints in the manifest.

All scoped PII fields use `ScopedPiiModelMixin`; exact fields are in `PII_FIELDS`.
G must register them before runtime use. C owns no object bytes. The presentation FK
points to E's `EventMemberPresentation`; sponsor organization is a global reference,
not tenant ownership. Track IDs are typed-in-purpose JSON references requiring G's
portable remapper and same-event validation. There is **no C sponsor-consent model,
consent writer, `allow_resume` flag or cached positive consent projection**.

G must install append-only/frozen/cross-row guards and lifecycle classifications.
Portable archives exclude entitlements, leases, import preview credentials and both
outboxes. Imported roles must be explicitly marked inert; credential omission must
never turn an imported approved role back into live authority. Deployment recovery
must invalidate transient leases/claims rather than revive them.

## Routes

62 frozen C route names and paths match G1 by stdlib inspection. URL lists:

- `contributions/urls_member.py`: 15; mount under `/api/v1/member/`.
- `contributions/urls_admin.py`: 14; mount under `/api/v1/admin/`.
- `contributions/urls_public.py`: 1; mount under `/api/v1/public/`.
- `mentoring/urls_member.py`: 9; mount under `/api/v1/member/`.
- `mentoring/urls_admin.py`: 23; mount under `/api/v1/admin/`.

Views have drf-spectacular input/output/error annotations. G owns actual mounting,
all origin/claim/delegated/API-client/source policies and final OpenAPI generation.
The backend contract test checks the exact HTTP method sets as well as names/paths.
No owner approve/verify-hours aliases or contribution consent routes were added.

## Tests and evidence

- `py_compile` of all new production/test/helper Python files: passed after fixing
  a nullable-field edit that also touched `Q(...__isnull=True)` expressions.
- Source file ceilings: every new Python/TS/TSX source is at most 300 lines.
- Stdlib inspection: 27 models, 62 unique frozen C names/paths, explicit User/FK
  fields and LF-only rerun list. This is not a Django model/schema check.
- `frontend: npx tsc -b`: passed.
- `npx vitest run --config vitest.local-junction.config.ts --configLoader runner
  src/features/events/contributions/contributions.test.tsx
  src/features/staff/mentorDesk/mentorDesk.test.tsx`: 2 files / 10 tests passed.
  Includes axe checks for the queue and assignment controls, canonical fixture
  consumers, complete API paths, account cache isolation, retry UUIDs, retained
  text on error and practice import defaults.
- Eleven backend test files are written, **not executed**. They include real
  PostgreSQL races for last shift place, one help claim, last office-hour place
  and round lease generation, plus fences, replay, privacy and role-only forms.
  Test ports isolate A/P/G dependencies; they do not certify production account
  fences, key preparation or grant-container integration.
- The exact LF list is `scratchpad/ev/C-rerun-files.txt` at the user-specified
  scratchpad root, relative to `backend/`. Backend tests are ignored by this
  checkout's existing gitignore; they exist on disk and must be collected by G.
- `git diff --check`: passed; staging index remains empty.
- `codex doctor`: config/home resolution and provider reachability failed.
  An independent CLI review was unavailable and is not claimed as passed.

## CROSS-LANE needs — before enabling or accepting integration

1. **G:** register/import the manifest, centrally author/apply migrations, install
   encryption/field/User-edge/portability/uniqueness/source/authority guards, wire
   routes and regenerated schema/client. Implement `ports.ProgrammePorts` and call
   `ports.install()` only with the complete adapter. Uninstalled runtime refuses 503.
2. **G/P:** combined fences must cover declared actor and subject accounts before
   event locks. `lock_authority_locked` must lock memberships/grants/organizations
   without locking `User` or `AccountPiiKey`. The shipped
   `makerspaces/resource_grant_locks.lock_tenant_authority` locks `User` under the
   event and cannot be used unchanged. Add opt-in already-locked grant-container
   create/reuse/display-union operations; preserve Bookings' existing behavior.
3. **G:** wire every event-authority discovery/query path to live entitlements,
   not cached grant.permissions. Use discovery mode only for event discovery;
   operations must pass the exact track scope. Backfill and maintain manual
   entitlements through existing grant lifecycle hooks without recursive union writes.
4. **A/F/P:** implement the ID-only team/audience/requirements and role form ports.
   F alone validates schema/answers; P alone prepares keys/derivations/intents and
   checks their bindings/epoch/deadline under locks. C's required `RoleFormBridge`
   must use F rendering and P prefill/defaults/status, including top-level role
   skills/availability and explicit CoC. No admission/contact fields enter role bodies.
5. **G/F:** install after-commit enqueue plus periodic sweep/escalation. Provider
   delivery must reauthorize each recipient/source/feature and deduplicate accepted
   deliveries by supplied key. Prepare tenant private-write key material outside
   event locks; prove no broker/KMS I/O occurs in the locked mapper phase.
6. **D/B/E:** D calls `subjects.require_resume_eligible` for contributor eligibility
   and remains the sole consent writer/read policy. B/D must replay old sponsor
   URL denial after revocation/replacement. E supplies selected-public-profile card
   projections and verified-hours certificate integration; C never selects an avatar
   automatically or manufactures a capacity-free attendee registration.
7. **G:** mount the exported consoles in AppShell with actor-derived scope and
   authority-filtered tools; supply A team context, F/P form bridges, D consent
   UI, E photo/card renderer and ARTWORK assets. Run integrated light/dark/mobile,
   keyboard, reduced-motion, contrast and Impeccable/browser acceptance.

## UNFINISHED — required C completion work before integration acceptance

These are real remaining implementation items, not completed work or merely tests
waiting to run. They are ready to assign to a C completion lane; that follow-up
has not been launched by this turn.

1. **Role lifecycle/policy closure:** posting `approval_required=False` automatic
   role approval with the issuer's authority locked in the proper order; explicit
   decline/completion; imported-role reconfirmation; staff reopening answers as a
   new revision with P's frozen DOB/date sources. Files:
   `contributions/{role_workflow,management_workflow,ports,serializers_management,
   views_admin}.py`; P's resolver/derivation adapter jointly. Extend
   `test_role_forms.py`; add `contributions/test_role_lifecycle_completion.py` and
   `contributions/test_role_date_reopen.py` covering CoC/no override, live issuer
   revocation, frozen/reopened dates, owner-only export and no persisted age.
2. **Assignment/queue completion:** proposed→active→ended assignment commands and
   complete bulk-run response/unsatisfied coverage persistence; help claim lease
   expiry/renewal and terminal expiry; authorized conflict declaration/configuration
   and mentor profile capacity/availability editing. Files:
   `mentoring/{assignment_workflow,help_workflow,policy,models_queue,serializers,
   views_operations}.py`, with coordinated frozen contract additions through G
   wherever a new named command is needed. Extend existing mentoring race tests;
   add `mentoring/test_assignment_lifecycle.py`, `test_help_expiry.py` and
   `test_conflict_configuration.py`. Never add direct state writers in views/tasks.
3. **Contributor configuration and remaining console controls:** posting/shift
   create/edit forms, training/briefing override reasons (never waiver/CoC bypass),
   mentor profile/help-category configuration, manager office-hour reschedule UI,
   explicit nominations, attention/mute controls and private diagnostic details.
   Files: new `frontend/src/features/staff/mentorDesk/{ContributorSetupPanel,
   MentorSettingsPanel,MentorAttentionPanel}.tsx`, existing `VolunteerManager.tsx`,
   `MentorRoundsPanel.tsx` and their backend serializers/views/workflows. Add focused
   component tests and backend override/office-change tests; use F's form builder
   and E/ARTWORK consumers, not a duplicate form system or replacement artwork.
4. **Import/export and contributor admission:** implement scoped CSV/XLSX export
   with formula-safe cells and the corresponding coordinated download route/UI;
   finish explicit contributor-ticket/capacity-policy admission and verified-hours
   certificate subject adapter with A/E/G. Files: new
   `mentoring/import_export.py`, `contributions/admission_adapter.py`,
   `contributions/certificate_subjects.py`, existing `TeamImportPanel.tsx` and
   relevant domain views. Add `mentoring/test_import_export.py` and
   `contributions/test_contributor_admission_certificates.py`. No synthetic attendee
   rows or certificate eligibility inferred merely from a display role.
5. **Verification gate:** G must execute all eleven actual rerun files after
   registration/migrations, plus joint A/F/P age/save/fence races, C/D/B canonical
   consent/read revocation, outbox/provider failures, portability/purge/restore and
   browser journeys. Add missing coverage for requirement withdrawal, FIFO skips,
   hours correction/audit, occupied-slot changes, round triggers, notification
   reauthorization and diagnostics. Perform independent review; fix findings and
   complete the intrinsic work above before accepting this lane as finished.
