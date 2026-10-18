# Events programme — Lane F implementation handoff

Branch `lane/events-f`, worktree `ev-f`, contract baseline `72bf7be7`.
Only §15 F production paths and F domain tests were changed. No migrations,
shared barrels, generated schema/client, catalogue hash, staging or commits.
Pre-existing untracked `frontend/src/test/staffActor.ts` was left untouched.

## Built per approved plan

| Plan | Code delivered |
| --- | --- |
| §10 gap 4, §10A, §12A | Separate v2 schema/answer/condition engine behind the existing public validator. Legacy list behavior lives unchanged in `forms_schema/legacy.py`. Closed schema keys, earlier-field all/any/depth/clause limits, typed comparison operands, bounds, Other, email/phone/compound emergency contact, disclosure, profile mapping and save choices. Hidden answers are removed before validation/mapping/saving. Age slots require server derivation IDs and never store numeric age/source DOB. |
| Decisions 28/30 | F's sole model-free profile registry contains all 18 descriptors including nonpersistable age, sensitive defaults, canonicalization and receiving-form choice validation. P retains all vault/encryption/age ownership. Explicit DOB sources must agree; P compares resolved saved DOB to `explicit_dob_values`. |
| §12A.1/.3/.4 | Actual G registration adapter tests replay both raw answer spellings through F once. `forms_schema/registration.py` preserves ordinary compound error locations; new applications retain `fields` errors. Stale form/date descriptors use 409. Emergency-contact fixture errors match the literal nested paths. |
| §10 gap 5, §11 | Encrypted bounded composer payload, three original brand designs, typed max-three CTAs, immutable preview/count/revision, desktop/mobile HTML, self-only verified-email test, count/checkbox confirmation, DB scheduling at least five seconds ahead, due recovery and cancel. Existing v1 compose/queue remains; v2 cannot bypass preview via legacy queue. |
| §10 gaps 6/7/8 | Permission-filtered readiness/waiting summaries, event-day view state, canonical current attendance/15-minute arrivals, Next up component, deduplicated funnel and two local 14-day periods with explicit denominators/caveats/capacity. Domain calculations remain A/C/D-owned providers. |
| §10 gaps 11/12/13 | Bounded crop/rotation/straighten/brightness/contrast/undo/reset cover editor, server EXIF-free re-encoder, publishing questions and explicit website release, dirty bar/conflict preservation, and five approved accent presets. |
| §10 gaps 14/15 | Own organization leave with recent proof/CAS/sole-governor guard, own security allowlist feed, occurrence-authorized series guests, and platform-only growth/MFA/outbox aggregates with hidden-tenant exclusion. |
| §10 delight row 8 | Explicit revision-specific Excellent/Good/Okay/Poor control; no guessed historical numeric remapping. |
| §11 PDFs | Source-derived typed attachment registry, existing payment compatibility wrappers, active-owner immutable certificate PDF adapter, revoked notices navigation-only, 5 MiB/PDF/filename/hash checks, and strict payment-or-certificate media grants. Both notification provenance and actual host storage scopes are checked. One-use consumption commits before storage; live owner/revision/endpoint/generation/expiry checks run before bytes are returned. |

## Files and public adapters

- `backend/apps/forms_schema/{validation,legacy,schema_v2,conditions,answers_v2,submission,profile_fields,prefill,registration,openapi,serializers,__init__}.py`.
- Existing F Events broadcast files plus `programme/broadcast_{content,preview,schedule,test,views,urls}.py`.
- Operations files and exact contracts: [OPERATIONS-HANDOFF.md](OPERATIONS-HANDOFF.md).
- Attachment files: `integrations/{notification_attachment_sources,notification_certificate_media,notification_document_dispatch,models_notification_media,notification_media,notification_media_views}.py`; payment compatibility in `payments/document_delivery.py`.
- New `organizations/member_leave.py`, `accounts/security_activity.py`, `operations/{reports_events_programme,platform_insights}.py`.
- F-owned shared form wrappers and new `frontend/src/features/forms/**`; existing staff broadcast/analytics panels and `staff/eventProgramme/**`; account activity/organization leave/platform insights subtrees.
- New domain tests under `backend/tests/events/programme/{forms,attachments,communications,operations}/` and beside the frontend code. Test files are ignored by inherited repository rules; G must explicitly include them when eventually staging. F did not change `.gitignore`.

The exact changed-file inventory, complete literal ORM declaration manifest and
LF backend rerun list are in the requested scratch `ev/` directory as
`F-files.txt`, `F-model-manifest.json`, `F-rerun-files.txt`.

F validator contract: `validate_submission(schema=...,payload=...,subject=...)`
returns `ValidatedForm` with visible/omitted IDs, profile candidates, effective
choices, base versions and private derivation sources. `snapshot` refuses pending
derivations; `snapshot_with_derivations(server_ids)` produces the persistent age
references. This is validation only: P prepares encryption and domain services
recheck ownership/fences before writes. Ordinary G registration uses
`validate_registration_member_input` as its adapter callback. Legacy raw service
callers continue through `validate_answers`.

F's editor OpenAPI is closed and excludes read-only event context. New domain
examples live in `programme/openapi_examples.py` and
`tests/events/programme/forms/fixtures/f-expanded-form-v3.json`; G's frozen fixture
bytes were not modified. Every new view has request/response/error declarations.

## Model manifest — no app migrations authored

| Model | Change / G disposition |
| --- | --- |
| `events.EventBroadcast` | Existing mapped subject/body remain encrypted; packed body contains markdown+CTAs. Add version, render schema, brand design, available_at, confirmed preview, scheduled status/check/index. See broadcast report and literal JSON manifest. |
| `events.EventBroadcastPreview` | New campaign FK CASCADE, creator User SET_NULL, content/revision hashes, recipient count, timestamp. No content/recipient list/object bytes. G installs content immutability and same-parent confirmation checks. |
| `events.EventFormRevision` | New immutable definition history with event/form key/typed selector/revision/schema/creator. Exact constraints and selector remapping in operations handoff. No submitted answers or DOB. |
| `organizations.OrganizationLeaveReceipt` | New global owner-operation replay receipt; omit tenant artifacts, expire after 30 days, remove before User erasure, allow organization deletion to dispose of it. |
| `integrations.NotificationMediaGrant` | Existing payment FK becomes nullable; add strict certificate FK and exactly-one check; storage Makerspace FK, source revision, recipient ID snapshot, integration generation/identity snapshots. Ephemeral source authority remains omitted from artifacts. Old pre-upgrade grants fail closed until expiry. |

The planned `events.EventCommandReceipt` remains G-owned. F resolves it lazily by
its frozen model/field names. No duplicate receipt or account/vault model exists.
No new object store prefix, new submission asset, new account PII column, or new
module key was introduced. Certificate PDFs remain E-owned immutable artifacts.

## Routes

Thirteen new named relative paths exactly match `routes-v3.json`:
readiness/live/publishing; form detail/validate; series guests; broadcast
detail/preview/test/schedule; member organization leave/security activity;
platform insights. Use `programme/urls.py` and `broadcast_urls.py` lists; they are
inert until G mounts and registers policies. Existing broadcast list/create,
queue/cancel and notification-media names remain unchanged.

The new funnel uses the existing analytics route with report key
`event-programme`, not a competing analytics endpoint. Cover/preset operations
provide adapters for G's existing image/event update paths. Account extras and
platform insights must mount independently of Events tombstoning.

## Tests and review evidence

- All 69 touched Python source/test files pass `py_compile`; all 93 touched
  production files meet the 300-line ceiling. The final inventory has 119 files.
  No Docker, Django, pytest, migrations or system checks ran.
- New frontend tests cover forms/conditions/compound inputs/save choices,
  broadcasts, live/funnel/publishing/dirty state, cover processing and extras;
  [frontend handoff](../../../../frontend/src/features/staff/eventProgramme/HANDOFF.md)
  records the final exact `tsc -b` and Vitest commands/results. TypeScript passed;
  seven frontend test files passed all 46 tests. After the final iframe font-loading
  change, TypeScript and the four broadcast tests passed again. Server preview
  documents now declare the real four Gilroy font faces; real-browser font loading
  remains in the explicit G visual acceptance work below.
- `git diff --check` passed; CLAUDE/AGENTS remain byte-identical; the index is empty.
- Independent implementation-agent reviews found and drove fixes for source
  provenance, policy changes during storage, numeric overflow, impossible choice
  bounds, condition parity, editor revisions/context, security action names,
  common envelopes and authorized v2 answer projection. Review notes are in
  scratch `ev/F-parent-independent-review.md` and
  `ev/F-operations-independent-review.md`; historical notes must be read with
  the final dispositions, not as claims of runtime test execution.
- `codex doctor` could not resolve home/config and required provider connectivity.
  A separate CLI code-review pass was unavailable and is not claimed.

## CROSS-LANE — ready-to-install work before runtime enablement

1. **G:** import/model/migrate/classify the five models above and planned shared
   receipt; immutable/frozen-content/selector-remap rules, User edges, nullable
   attribution erasure, global receipt removal before User erasure, 30-day receipt
   cleanup and media omission. Add the leave
   receipt to `organizations/services_governance.py::assert_deletable` disposable
   set so a successful leave does not prevent later organization deletion.
2. **G:** install exact route origin/claim/delegated/API-client/source policies,
   URLs, event/version/accent/date writers and generated schemas centrally. Use
   `notification_media.media_source_targets` in
   `makerspaces/origin_scope_notification_media.py` to declare both notification
   and storage scopes before middleware locks; final sources must not expand
   locks after domain locks. Register certificate_id media audit references.
3. **G/A/C/D/B/E:** install the form/readiness/respondent/answer projectors from
   `programme/providers.py`; preserve compound round permissions and nested
   selectors. Series v2 answers stay null with an explicit diagnostic until the
   live disclosure/age projector exists. No raw derivation references are exposed.
4. **P/A/C/G:** use F's sole validator/registry and receiving-form prefill helper;
   P resolves saved DOB, checks explicit DOB consistency, prepares keys/ciphertext
   outside domain locks and persists typed derivations/intents under predeclared
   fences. A/C retain their own admission, draft, lock and partial-merge policies.
5. **E/G:** register `notification_certificate_media.register_certificate_resolver`
   for contribution/award subjects. It returns a `CertificateDocument` binding
   certificate/event/origin/storage-host/owner/revision/hash/bytes/private key.
   The built-in resolver covers existing attendance certificates including
   collaborative provenance. No badge PDF source exists.
6. **G:** install broadcast scheduled recovery/autodiscovery, v2 personal source
   revision checks, and generic email `html_body` forwarding. Exact functions,
   models, tasks and regression paths are in scratch `F-broadcast-report.md`.
7. **G:** register the event-only funnel report/typed union, invoke cover sanitizer
   before final attachment, preserve cover alt text through the owning image/page
   revision path, expose `member_leave.project_leave_state` in the existing member
   organization read payload, and mount exported F UI/Next up/accent/word-feedback
   components in the existing shell/drawer/pages. Save never implies release.

## UNFINISHED — scheduled acceptance work, not silently deferred

| Owner / before integration | Exact work and tests |
| --- | --- |
| G model/registry step 2 | Shared `events/models_programme.py`, organization/integration barrels, all centrally authored migrations and §14 registries. Apply migrations, `manage.py check`, dry-run migration drift; run `F-rerun-files.txt`. |
| G domain/provider steps 3–4 | `events/apps.py`, `urls_programme.py`, `config/urls.py`, `event_permissions.py`, `event_authority.py`, `models_event.py`, `services_core.py`, report/notification/source registries. Wire the explicit callbacks above; add integration route/privacy tests. |
| G/P/A/C encrypted answer integration | Ordinary registration adapter and new application/role consumers must prepare keys and bind derivations/intents before writes. Run frozen admission/bootstrap/emergency bytes, first-use/no-membership, key failure, stale date/form and rollback tests. Syntax checks cannot establish encryption or concurrency safety. |
| G/E certificate media integration | Extend E's resolver for all certificate subjects, register typed certificate audit/retention/source targets and exercise all supported document providers. Run `test_default_pdfs.py`, `test_media_binding.py`, all existing `tests/billing_docs/test_r2_*.py`; add real host/via freeze and certificate one-use/revoke races. |
| G non-lane form consumer wiring | `events/feedback_validation.py`, existing public/admin/registration serializers/services, bookings/membership/machine/maintenance/service form consumers use the F version dispatcher and appropriate admission adapter. Legacy list tests are retained; add actual v2 consumer replays. F did not edit those shared files. |
| G UI/control mounting | `frontend/src/AppRoutes.tsx`, staff EventDrawer/tab/Overview/home/platform/account consumers, existing event feedback controls and `/control/` dashboard integration. Mount F exports and protected session boundary; permission loss must clear cached/private drafts/blobs as described in frontend handoff. Verify keyboard/mobile/light/dark/reduced motion, canvas controls, protected data withdrawal and exact server failures. |
| G/F QA step 5 | Execute all 37 LF-listed backend test files in the isolated correct worktree. Add real PostgreSQL CAS/idempotency/PII/source freeze races in `tests/events/programme/integration/`; no backend runtime pass is claimed here. |
| G/orchestrator review and owner QA | Independent CLI review once tooling is available, full browser functional/axe/contrast checks and Space Works Impeccable audit. Resolve findings before programme acceptance. The running integrated UI and provider network behavior were not visually or end-to-end verified in this lane. |

Locally oversized PDFs retain the shipped bounded retry behavior (existing billing
regressions assert it); unsupported/definitively rejected provider attachments
fall back to authenticated navigation, while ambiguous/retryable provider failures
do not immediately duplicate text. G acceptance must preserve that distinction.
