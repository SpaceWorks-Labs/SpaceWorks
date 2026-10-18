# Lane F backend operations handoff

Scope: plan §§10 gaps 6/7/8/11/12/13/14/15 and §12A event form-editor surface.
No migration, shared barrel, generated schema, staging or commit was changed.

## Built

- `readiness.py` derives permitted setup/action rows. Uninstalled domain summaries
  appear as unavailable with no count, rather than claiming readiness. Unauthorized
  actions never invoke their count provider.
  Readiness/live/publishing include id/event_id/version/state/allowed_actions and
  fail closed if G's real aggregate version is absent.
- `live.py` uses current ATTENDED registrations and latest immutable attendance
  evidence, deduplicating repeated check-ins and excluding undone attendance.
  Fifteen-minute arrivals are bounded to 96 buckets; doors use event start.
- `operations/reports_events_programme.py` supplies a tenant/event-only report
  record: responded/going/checked-in/attributable feedback, defined denominators,
  null zero-denominator shares, 100% cap, 14 local dates with prior comparison,
  and canonical Events capacity helpers. Missing application integration is explicit.
- `publishing.py` calls existing update/publish/release services; save never implies
  website release. CAS/replay requires G's version writer and receipt model.
- `forms.py` enforces six form keys and exact nested selectors, event-bound provider
  resolution, compound round permissions, shared F validation, partial sample
  validation, immutable definition history, and replay by safe revision reference.
  Raw private DOB is never read/persisted by the editor preview.
  Editor writes reject server event_context and compare current form revision
  under lock even when the aggregate expected_version matches.
- `cover.py` canonicalizes bounded sniffed single-frame images to metadata-free PNG;
  `accent_presets.py` supplies exactly five approved palette names with contrast pairs.
- `series_guests.py` deduplicates member identity, retains separate account-less
  legacy rows, scopes every occurrence, composes status/attendance/occurrence filters,
  and exposes contacts/answers only with registration management plus tenant VIEW_AUDIT.
- `organizations/member_leave.py` implements owner-self withdrawal, exact timestamp
  CAS, recent proof recheck, sole-governor protection, immediate membership deletion,
  audit and durable UUID replay.
- `accounts/security_activity.py` exposes only own allowlisted action/id/time; never
  metadata, sessions' secrets, another actor's rows or arbitrary audit data.
- `operations/platform_insights.py` exposes platform-only 1–30-day growth/MFA/outbox
  counts, excludes hidden/unservable tenant data, and never reads message bodies.

## Model manifest for G

### events.EventFormRevision — F definition in programme/form_models.py

Fields: auto `id`; `event` FK events.Event CASCADE (`form_revisions`);
`form_key` CharField16 enum registration/application/volunteer/mentor/round/track;
`selector_kind` CharField8 enum none/posting/round/track default none;
`selector_id` nullable PositiveBigInteger; `revision` PositiveBigInteger;
`schema` nullable JSON (question configuration only); `created_by` nullable User
SET_NULL with no reverse accessor; `created_at` auto timestamp.

Unique `(event,form_key,selector_kind,selector_id,revision)` with
`nulls_distinct=False`; positive revision; selector null consistency and key/kind
consistency constraints. Python instance updates/deletes refuse. G must add a DB
content-immutability trigger and approved purge bypass. Allow only creator clearing
for the SET_NULL User edge if account deletion uses it. No answers/DOB, credentials,
private object keys or asset bytes. Same classification as Event.custom_form curated
configuration. Portable retention follows Events; export/restore remaps event and
selector_id by selector_kind (C posting/round or D track). User creator is attribution,
not authority; use existing nullable attribution User-edge disposition. No person
closure expansion. Clone copies current schema, not source receipts/history identity.

### organizations.OrganizationLeaveReceipt — F definition in member_leave.py

Fields: auto `id`; `organization` FK Organization CASCADE (`leave_receipts`);
`actor` FK User PROTECT (`+`); `operation_id` UUID; `expected_version`
PositiveBigInteger; `created_at` auto timestamp. Unique
`(organization,actor,operation_id)`. Global coordination only; omit from both
tenant export fidelities/closure and import. Deployment backup may retain rows;
30-day bounded coordination cleanup is required. No objects or textual PII.
**Add this model to services_governance.assert_deletable's disposable set**;
otherwise its reverse FK would accidentally prohibit organization deletion.

### Shared G model requirement — no F duplicate

`commands.py` lazily resolves the planned events.EventCommandReceipt with exact
fields `event,actor,operation_uuid,request_sha256,response_reference,created_at`
and unique `(event,actor,operation_uuid)`. Request digest covers `{command,payload}`.
Responses contain only references/version/state, never author text, answers or
credentials. G owns model/import/migration and 30-day cleanup.

## Exact route lists and schemas

`programme/urls.py::admin_patterns`, relative to `/api/v1/admin/`:

- GET/HEAD `events/<pk>/programme/readiness/` — events-programme-admin-programme-readiness
- GET/HEAD `events/<pk>/programme/live/` — events-programme-admin-programme-live
- GET/HEAD/PATCH `events/<pk>/programme/publishing/` — events-programme-admin-programme-publishing
- GET/HEAD/PUT `events/<pk>/forms/<form_key>/` — events-programme-admin-form-detail
- POST `events/<pk>/forms/<form_key>/validate/` — events-programme-admin-form-validate

`series_patterns` relative to `/api/v1/admin/`: GET/HEAD
`event-series/<pk>/guests/` — events-programme-series-guests.
`account_patterns()` relative to `/api/v1/member/`: POST organizations/<pk>/leave/
— member-organization-leave; GET/HEAD security-activity/ — member-security-activity.
`platform_patterns()` relative to `/api/v1/admin/`: GET/HEAD platform/insights/
— admin-platform-insights. G should mount account/platform views independently of
Events tombstoning; factories are convenience lists, not runtime installation.

All views have explicit request/response/error serializers. Forms use the closed
VERSIONED_FORM_SCHEMA from the single forms_schema engine. `openapi_examples.py`
provides literal readiness/live/publishing/form examples attached to runtime
decorators. `analytics_serializers.EventProgrammeReportSerializer` supplies G's
closed domain report union member, via existing analytics-generic route with key
`event-programme`; no additional URL/name was invented.

## CROSS-LANE requirements — before G integration acceptance

1. G: import/migrate/classify the two F models plus planned shared receipt; implement
   triggers/retention/portable mappings, authority/source catalogues, route
   origin/claim/delegated/API-client policies, and independent account/operations mounts.
2. G: Event.version writer must cover update/publish/release. F fails closed with
   503 if missing or a mutating callback does not advance it. Shared
   lock_authority still locks User under event locks; reconcile that existing
   authority behavior with the vault-specific no-account-lock rule centrally.
3. A/C/D/B/E: register ReadinessProvider summaries for coc, team_limits, storage,
   rubric, judge_coverage, mentors, door_shifts, certificates, reviews, help,
   approvals. C/D own their calculations. summarize(event,actor) returns
   `{status,count}` or None when the event feature is inapplicable.
4. A: register_respondents callback returns `(is_hackathon, Respondent iterable)`
   with real submitted timestamps and member identity keys, excluding practice.
   It must remain callable with actor=None after the report runner's subject gate.
5. A/C/D: register_form(FormProvider(key,resolve,read,save_locked)). Resolver gets
   event/actor/selector/locked and returns an event-bound target; callbacks must
   enforce own feature/source/assignment rules and revision/version writes. Read
   gets target; save_locked gets target/schema inside the F transaction. Do not
   store answers in this definition history.
6. G: register report key event-programme, builder
   apps.operations.reports_events_programme.build_event_programme; FIELDS from that
   module; Events+Reports, tenant/event subject only, full-manager authority,
   preview-only/nonexportable/nonschedulable/nonaggregate. Add key to event subject
   adapter and typed OpenAPI union. Existing PII/PDF reports keep their current gates.
7. G: invoke canonical_cover before final image promotion using the existing
   bounded attachment transport. Current public_image_sniff only verifies image
   MIME; it does not strip metadata. Pages covers remain private revision assets.
8. G: expose membership_version(membership) in the member-self org payload. It is
   exact UTC epoch microseconds from updated_at; every governance writer must keep
   updating that timestamp. Add OrganizationLeaveReceipt to disposable deletion refs.
   `project_leave_state(organization,actor)` is the ready-to-install own-member
   projection: organization_id, membership_version, allowed_actions and sole_owner
   reason. Install it in the existing member organization read serializer; no GET
   alias was added. It does not expose a member/governor directory.
9. G/P: install `providers.register_answer_projector(callback)` for series-guest
   v2 answers. The callback receives event, actor, registration and snapshot only
   after manage_registrations+VIEW_AUDIT. It must apply current disclosure and
   server-derived age projection. Until installed, v2 answers return null with
   v2_projection_unavailable and a content-free diagnostic; legacy v1 remains.

## Tests and UNFINISHED

Six test files under backend/tests/events/programme/operations/: test_commands.py,
test_readiness_forms.py, test_cover_accent.py, test_live_funnel.py,
test_account_extras.py, test_series_guests.py. Covers replay/CAS/authority withdrawal,
permission-hidden counts, frozen partial-form preview, nested sample errors, EXIF,
malformed/animated/oversized images, preset allowlist, attendance undo/dedupe,
application union/local dates/zero ratios, own security allowlist, reauth/sole org
owner/replay, platform-only/hidden-space counts, and occurrence PII permissions.

Python syntax compilation passed for the owned Python source/test files.
No Django, Docker or pytest execution was performed, as the lane instructions
prohibit it. These tests must run on G's isolated environment **after** imports and
migrations. Production concurrency/source-freeze tests of the integrated shared
version/receipt/fence order remain G acceptance work; mocks do not certify those.
Cover transport integration, all domain provider wiring, report registry wiring,
model migrations/registries/triggers, and account/policy mounting above remain
explicit pre-integration work, not completed user-visible runtime surfaces.

Scheduled follow-up ownership before integration:

| Owner / integration point | Exact files and verification |
| --- | --- |
| G, model/registry step | `events/models_programme.py`, `organizations/models.py`, centrally authored app migrations, data-export/reference/unique/authority/source/retention registries; run all six operations tests after model setup |
| G, route/feature step | `events/urls_programme.py`, `config/urls.py`, existing protected-route/origin/claim/delegated/API-client registries; add `backend/tests/events/programme/integration/test_operations_routes.py` for exact names and foreign/hidden refusals |
| G + A/C/D/B/E/P, adapter step | `events/apps.py` installs callbacks declared in `programme/providers.py`; `events/report_subject.py`, `operations/report_definitions_events.py`, `operations/schemas_reports.py` register report; `events/views_admin_image.py` installs `programme/cover.py`; extend focused tests with real providers |
| G, account step | Existing member-self organization read serializer imports `organizations/member_leave.py::project_leave_state`; `organizations/services_governance.py::assert_deletable` adds disposable receipt; include reauth/permission-withdrawal test in `test_account_extras.py` |
| G, acceptance step | Run six listed test files plus add `backend/tests/events/programme/integration/test_operations_concurrency.py` for real PostgreSQL CAS/replay/lease/source-freeze/PII-fence races; reconcile existing shared User authority lock before certification |
| G, cleanup step | Existing deployment scheduler registers bounded 30-day cleanup for EventCommandReceipt/OrganizationLeaveReceipt; add `backend/tests/events/programme/integration/test_operations_receipt_retention.py`, including Events tombstone and org deletion |
