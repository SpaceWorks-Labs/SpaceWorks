# Events programme — Lane B implementation handoff

Worktree `ev-b`, branch `lane/events-b`, checkpoint `72bf7be7`.
Only B-owned production/test paths and the requested session scratchpad were written.
No migrations, shared barrels, root registries/settings, dependency manifests, generated
API/schema/catalogue files, staging, commit, merge or push were performed.
Pre-existing untracked `frontend/src/test/staffActor.ts` is untouched.

## Built per approved plan

- **§7:** project draft/version writer, HTTPS links without network fetching, explicit
  AI/reuse declarations, team-leader submission, frozen versioned snapshots with roster,
  typed assets/links/tracks/prizes and content hashes. Resubmission invalidates D's old
  judging through its provider. Event-clock cutoff and deadline sweep preserve the last
  eligible snapshot; staff amendment requires a reason and cannot revive withdrawal or
  disqualification. D uses `transition_review_locked` rather than writing B status.
  Triage, withdrawal, integrity flags and every implemented state transition audit.
- **§8:** exact staging POST; multipart part sizing/signing/server `list_parts`;
  immutable verification copy; full streaming hash; explicit none/ClamAV scanning with
  recorded engine/database version; non-root resource-limited ffprobe launcher; canonical
  metadata-free images; conditional final creation/hash reconciliation; leased work and
  cleanup retries. Event-local quota, frozen lower-only caps, managed decimal 25 GB pool,
  canonical-size adjustment and confirmed-cleanup release have shared accounting hooks.
- **§8 reads:** G's bounded stream/range primitives, closed server-selected purposes,
  same authorization on HEAD, one-range 206/416, safe attachment disposition/no-store/
  nosniff, policy checks before storage and before releasing each chunk. Participant
  resumes can never use the gallery reader. D supplies live judge/gallery/sponsor policy.
- **§8 retention:** first-results/cancellation/fallback anchors, 365-day deadline,
  logical expiry distinct from deletion, all-version/multipart deletion, periodic
  absence verification, idle-upload and unattached-draft sweeps. Capture explicitly
  distinguishes missing ready bytes, expected expired absence and overdue-ready rows
  requiring retention finalization. Import helper preserves absolute expiry and hashes.
- **Maker formats:** opt-in `hackathon-maker-v1` registry; compound suffixes and every
  matrix extension/alias/subtype, including `.g1`–`.g30`; independent generated fixture
  inventory and drift guard. Legacy machine/service behavior stays in `maker_formats/legacy.py`
  behind the existing compatibility barrel. Explicit subtypes are strict; the G1 coarse
  `group=model` example without subtype uses bounded extension/slot content classification.
- **Member UI:** existing FormPageLayout/primitives, account-scoped TanStack Query keys,
  optimistic draft mutation/invalidation, links and per-item gallery choices, upload pause/
  retry metadata without URLs/secrets, multipart resume, asset status polling and original
  video playback/download fallback, bounded escaped source/toolpath inspection and
  formula-safe CSV preview/export. Track/prize choices and F form renderer are injected
  through explicit props. All UI uses existing Space Works tokens/fonts and Lucide.
- **Previews:** lazy worker adapters for three.js STL/OBJ/3MF, click-only OCCT STEP/IGES
  with a bundled WASM locator, and tracespace Gerber/drill/ZIP. ZIP expansion/mesh/output
  limits, worker timeout/cancel, texture/network-reference refusal, SVG-as-image rendering,
  theme-aware model canvas and large-file confirmation are implemented. Required vendor
  packages and real browser operation remain integration acceptance work below.

## Files and model manifest

- `backend/apps/maker_file_formats.py`: compatibility barrel.
- `backend/apps/maker_formats/`: registry, legacy policy, reservation/classification,
  binary/text/XML/ZIP/PDF/image validation, bounded S3 ranges and ZIP listing.
- `backend/apps/events/submissions/`: models, project/link/moderation/integrity writers,
  asset command/job/storage/scan/probe/quota/read/retention/lifecycle adapters, serializers,
  views, URL lists, portability and DB guard SQL.
- `frontend/src/features/events/hackathonSubmissions/`: editor/API/upload/media components,
  preview worker/bounds/vendor declarations and seven focused test files.
- Backend tests: `backend/tests/maker_formats/**`,
  `backend/tests/events/programme/{submissions,uploads}/**`.

Exact file inventory: `scratchpad/ev/B-files.txt` (LF; includes ignored tests/helpers).

`model_manifest.json` is the literal AST field/FK/constraint inventory; regenerate it
only from these model files. `integration_manifest.json` declares every User edge,
object/version/size/expiry field, uniqueness policy, JSON ID slot, private field,
coordination exclusion and purge order. G imports the explicit `submissions/models.py`
barrel into its own barrel. **Twelve concrete models, one abstract field mixin:**

`HackathonSubmission`, `SubmissionSnapshot`, `SubmissionLink`, `SnapshotAsset`,
`SnapshotLink`, `SnapshotTrack`, `SnapshotPrize`, `SubmissionIntegrityFlag`,
`SubmissionAsset`, `HackathonParticipantAsset`, `EventAssetUsage`, `SubmissionAssetWork`.

G must install `db_guards.installation_sql()` after A/B/D tables. It supplies immutable
snapshot/reference guards, same-event/team ownership checks, immutable ready/hashed
asset content and non-revival. This SQL has been syntax-reviewed only, not executed.
Purge must clear current-snapshot pointers, delete D/E dependents and amendment snapshots
newest-first under the existing purge GUC; self-PROTECT cannot be ignored.

## Routes

The 22 B-named paths are supplied in `urls_member.py`, `urls_admin.py`, `urls_public.py`
under their existing `/api/v1/member/`, `/admin/`, `/public/` mounts. They implement the
frozen team submission/save/submit/withdraw, amend/triage, team asset creation/status/
parts/resume/complete/abort, member/admin download/preview, public gallery asset, and
participant-resume collection/detail/from-saved/complete/abort/download paths. One path
serves each method set. `test_route_contract.py` compares names and paths to G1 bytes.
Views carry drf-spectacular request/response/auth/error annotations; G generates the final
schema only after mounting. No consent route/model/writer is duplicated from D.

## Tests and observed outcomes

- `py_compile`: **74 touched Python files passed**; no Docker/Django/pytest was run.
- `npx tsc -b`: passed before the final documentation-only handoff.
- Focused Vitest: **7 files / 22 tests passed**. Includes preview resource/security limits,
  idle/large/timeout/cancel behavior, safe links, upload destination/receipt boundaries,
  original-video confirmation, and draft/submission controls. One preview state ran axe;
  jsdom cannot establish real color contrast or browser/vendor compatibility.
- All touched production Python/TypeScript files are at most 300 lines.
- `git diff --check`: passed; index remains empty.
- `codex doctor`: configuration/home resolution and provider reachability failed. A
  separate CLI review was unavailable; no independent-review pass is claimed.

The requested LF list is `scratchpad/ev/B-rerun-files.txt`: thirteen actual backend test
files relative to `backend/`. Helpers and sample builders must travel with those files.
**These new backend tests are gitignored by the existing root policy.** G owns the narrow
ignore exception or explicit inclusion; B did not edit `.gitignore` or stage files.

## CROSS-LANE needs — G integration steps 2–4

1. **G:** import models, author migrations from the actual Events leaf and install the
   SQL guards; register every manifest disposition, object locator, retention adapter,
   source/PII fence, route/API-client/origin/claim policy, audit action and scheduler.
   Use exact `actual_bytes`, direct retention fields and required-finalization semantics;
   do not query `object_retention_state`. Reset process leases after deployment recovery.
2. **G + A/C/F/D:** install `SubmissionBoundaryAdapter` with the predeclared ordered
   source/account/PII/event/child context, live gate, team/participant/config/project/
   judging providers and canonical EventCommandReceipt. Team reads/edits/submission and
   role-only resume eligibility are explicit A/C provider calls. F returns the complete
   canonical project dictionary, omitting hidden answers; drafts allow incomplete answers,
   final submission runs required slot/form/attendance/CoC/track/prize checks. Internal
   `asset_worker`/`deadline_lock` uses lifecycle authority; `asset_publish` rechecks the
   active owner/feature/source before making bytes ready. No key work under event locks.
3. **D:** install live exact-snapshot/grant/window/conflict/track/gallery/sponsor predicates,
   admin purpose selection and public opaque-ID resolver. Implement `invalidate_snapshot_locked`
   and `invalidate_resume_locked`: D alone writes canonical consent/history, including
   replacement/deletion revocation. Consume `snapshot_assets.require_ready_for_snapshot`
   and B's review-transition writer. Reuse preview/video components with D-gated readers.
4. **P:** implement the `saved_resume_provider.prepare`/`copy_to_event` adapter used by
   `resume_copy.py`/`asset_jobs.py`. Preparation is outside event locks and returns only
   trusted filename/size/hash plus an opaque provider preparation. Copy must recheck
   owner/key/version before/after server copy; no vault key enters Events or HTTP.
5. **G storage:** install the typed pool callback `apply_locked(event,asset_uuid,operation,bytes)`
   for reserve/reserve_canonical/charge/release_temporary/release_all. Operations are
   idempotent per asset; provider accounting must not impose the ordinary base entitlement.
   Configure private versioned storage/conditional-copy/conditional completion capability,
   two-second SDK connect/read timeouts, browser origin allowlist/CORS/ETag exposure,
   24-hour incomplete multipart lifecycle and bounded clamd limits. Keep existing service names.
6. **G frontend/deployment:** install and lock `three`, `fflate`, `linkedom`, `occt-import-js`,
   `@tracespace/core`, their notices and required browser/WASM handling in G-owned manifests.
   Ambient declarations permit type checking here; they do **not** prove vendor API/bundle
   compatibility. Mount editor inside AppShell, supply format/cap/track/prize/F-form props.
   Install ffprobe; configure `(python,-m,apps.events.submissions.probe_sandbox)` in a non-root
   Linux worker. Register scan/deadline/idle/retention/cleanup jobs and cloud equivalents.

## UNFINISHED — follow-up lane B2, before G integration acceptance

These are required work, not waived or reported as passing. G must keep the feature off
and schedule B2 ahead of final integration acceptance under binding owner decision 29.

1. **B2 + G verification:** execute all files in `B-rerun-files.txt` after migration/guard
   installation, fix failures and run existing machine/service compatibility suites. Expand
   real PostgreSQL concurrency/fence/replay/lease/cleanup tests in
   `backend/tests/events/programme/uploads/test_asset_concurrency.py` and
   `submissions/test_snapshot_workflow.py`: quota initialization races, both crash sides
   of each storage phase, late storage writes after signed-upload expiry, source freeze,
   revoked ownership during publication and cleanup-accounting reconciliation. Current
   fake-storage and pure tests do not establish these real infrastructure properties.
2. **B2 real-export owner:** verify every research `(V)` family with licensed/local exports,
   recording tool/version and outcomes in `backend/tests/maker_formats/REAL-EXPORTS.md`.
   In particular newer proprietary SolidWorks/Inventor variants need verified subtype
   policies in `registry.py`/`signatures_binary.py`; current OLE2 policies do not pretend
   to certify unprovided newer binary exports. Synthetic opaque fixtures are not acceptance.
3. **B2 format hardening:** complete the remaining adversarial matrix in
   `backend/tests/maker_formats/{test_negative_content,test_zip_listing}.py`: expansion
   boundary/CD overlap/ZIP64 variants, every proprietary corrupt-container subtype,
   corrupt compressed Blender/STEP variants, hostile image cases and actual video
   no-stream/overlong/codec/container cases. Fix any checker/real-format incompatibility
   rather than weakening the policy to accept arbitrary bytes.
4. **B2 + G browser/package acceptance:** bundle and exercise `preview.worker.ts`,
   `MeshCanvas.tsx`, `AssetPreview.tsx`, `OriginalVideo.tsx`, `UploadEditor.tsx` and
   `SubmissionEditor.tsx` with actual installed vendors and a real storage upload.
   Confirm OCCT UMD/WASM and tracespace API compatibility, parser memory/expansion/time
   limits, interrupted resume/abort UX and stale URL revocation. Finish light/dark/mobile/
   keyboard/reduced-motion/44px/contrast checks and the required Impeccable audit.
5. **B2 + F/G data review:** explicitly settle and install scoped encryption/export
   classification for `HackathonSubmission.form_answers`, frozen `SubmissionSnapshot.project`
   form values and any sensitive triage/integrity notes. They are currently private JSON/
   text fields, **not encrypted by B**; no sensitive form integration is accepted until
   the agreed mapper and fence behavior is implemented and tested. Add tests in
   `backend/tests/events/programme/submissions/test_project_pii.py`.
6. **G/orchestrator:** complete independent review of this exact delta, correct findings,
   then run integrated owner QA once all programme lanes are assembled. No lane-local
   QA/review approval, complete programme readiness or production enablement is claimed.

Primary preview API references used during implementation:
[three.js STLLoader](https://threejs.org/docs/pages/STLLoader.html),
[3MFLoader](https://threejs.org/docs/pages/ThreeMFLoader.html),
[OCCT import API](https://github.com/kovacsv/occt-import-js/blob/main/README.md),
[tracespace core](https://www.npmjs.com/package/@tracespace/core).
