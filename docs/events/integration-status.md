# Events integration closure ledger

Baseline: branch `lane/events-g3`, commit `f1ef7736`, 2026-10-18. This records the checked-out
code and GF1's thirteen unfinished items. Other lanes run on sibling branches; their
unmerged work is not evidence in this checkout. **Keep every programme capability and
event config off.** This docs lane closes prose, not the runtime blockers below.

The original [G1 handoff](../events-programme-G1-handoff.md) describes the earlier contract-only
checkpoint, not this later mount/migration state. Current generated OpenAPI/client/catalogue
digest landed in `f1ef7736`; this lane neither regenerates nor certifies them. GF1 records
217 paths / 400 method entries, including C2 completion routes. Django resolution/schema
and actual provider behavior still need integrated execution.

Paths in the table are relative to `backend/apps/`; test paths are relative to `backend/`.
Tests named as proposed/missing are work requirements, not files claimed to exist or pass.

| GF1 item | State observed / required closure | Exact code and tests for integration owner |
| --- | --- | --- |
| 1. Migrations and drift guards | Seven migrations authored; schema/client generated. PostgreSQL forward/reverse/guards, real registry and complete test execution pending. | Migrations in [operator notes](operations.md#migration-and-key-preparation); `tests/events/programme/integration/test_migration_backfills.py`, `test_postgres_guards.py`, `test_registry_totality.py`, `test_mounted_routes.py`; `tests/tenant_migration/test_events_programme_roundtrip.py`. |
| 2. Canonical admission / ordinary registration / locks | A ports and guards exist; real registration/payment/waiver/ticket/QR bridge not installed. Legacy paths retain older locking/preparation. | `events/hackathons/admission_ports.py`, `admission_bridge.py`, `events/services_registration.py`, `services_event_details.py`, `services_lifecycle.py`, `services_website.py`, `staff_grant_locks.py`; admission/teams suites, `judging/test_postgres_fences.py`, `answer_derivations/test_account_fence.py` under `tests/events/programme/`. |
| 3. Affected-account preparation | Combined fence helpers exist; all certificate/print subject accounts and immutable-resource preparation are not proven. | `events/programme_locks.py`, `programme/commands.py`, `credentials/boundary.py`, `certificates/issuance.py`, `subjects.py`, `lifecycle.py`, `profile_photos/selection_workflow.py`, `snapshot.py`; credential/photo/certificate tests plus `answer_derivations/test_account_fence.py`. |
| 4. Date/lifecycle hooks | Event revision increments exist; complete date/series reopen/review/notices and cancellation/attendance adapters pending. | `events/services_event_details.py`, `services_series_update.py`, `hackathons/admission_dates.py`, `answer_derivations/lifecycle.py`; `tests/events/programme/answer_derivations/test_subject_lifecycle.py`, `contributions/test_role_date_reopen.py`. |
| 5. Portable answers/assets | Typed top-level remap/retention projection exists; nested canonical derivations/encrypted answers, final keys/work/versions need real import proof. | `tenant_migration/semantic_events_programme.py`, `pii_events_programme.py`, `row_planning.py`, `events/submissions/portability.py`, `answer_derivations/portability.py`; `tests/events/programme/answer_derivations/test_portability.py`, `tests/tenant_migration/test_events_programme_roundtrip.py`. |
| 6. Private project PII | Private export omissions are not encryption. Project JSON and ordinary-v2 answer storage need actual mapper/disclosure review before sensitive use. | `events/submissions/models_projects.py`, `programme/forms.py`, `registration_form_adapter.py`, `encryption/registry_events_programme.py`; `tests/events/programme/submissions/test_snapshot_workflow.py`; proposed `test_project_pii.py` and real A/C/F/P journeys. |
| 7. Storage/workers/purge | Per-event helper limits and typed object capture exist. Pool accounting, target rebuild, schedules and durable multipart/version purge obligations pending. | `events/submissions/ports.py`, `quota.py`, `asset_jobs.py`, `upload_deadlines.py`, `cleanup_schedule.py`, `retention.py`, `makerspaces/purge_events_programme.py`, `storage_keys_events_programme.py`, tenant materialization; `tests/events/programme/uploads/test_quota_accounting.py`, proposed `test_asset_concurrency.py`, snapshot/roundtrip/backup object tests. |
| 8. E/D durable recovery | Admission/contributor/broadcast/account jobs registered; certificate resumption, print cleanup and judging recovery not scheduled. Need retained-cleanup authority for frozen/MIGRATED_OUT sources. | `events/certificates/tasks.py::resume_batches/resume_certificates`, `print_cleanup.py::cleanup_expired`, `judging/lifecycle.py::sweep_notices`, `config/settings.py`, `operations/management/commands/run_scheduled_tasks.py`; certificate batch/print/render-race, judging publication, tombstone/source-freeze suites. |
| 9. Source deletion / erasure | Account SQL fence/envelope guards exist; profile/membership deletion must atomically clear both selection FKs and consents, preserve submitted evidence and run erasure hooks. | `events/profile_photos/models.py`, `selection_workflow.py`, `makerspaces/profile_images.py`, profile/membership deletion services, `accounts/saved_details/lifecycle.py`, `events/answer_derivations/workflow.py`, `encryption/account_models.py`; `tests/events/programme/profile_photos/test_selection.py`, `test_public_cards.py`, P lifecycle/vault independence tests; proposed profile-removal/print-photo race tests. |
| 10. Cross-lane providers/notices | Most A/B/C/D/F/P ports remain uninstalled. `programme_runtime.py` installs only a narrow subset; literal manifest does not deliver notices or establish entitlement-aware authority. | `events/hackathons/admission_ports.py`, `contributions/ports.py`, `authority.py`, `submissions/ports.py`, `boundary_adapter.py`, `api_runtime.py`, `judging/ports.py`, `certificates/subjects.py`, `profile_photos/policy.py`, `accounts/saved_details/{fields,prefill,subject_binding,resume_copy}.py`; all domain tests plus proposed integrated admission/sponsor/source race tests. |
| 11. Clone/seeds/rendering | Read catalogue installed; owned immutable artwork seed copying and badge image-layer rendering not completed. Clone adapters and authoritative print proofs pending. | `events/services_clone.py`, `judging/clone.py`, `certificates/seeds.py`, `rendering.py`, `badge_designs.py`, `print_workflow.py`; proposed `tests/events/programme/certificates/test_default_seed_rendering.py`, real physical scanner/PDF resource races. |
| 12. Owner decisions 34/35 | Reimbursement and full stage-triggered forms are **pending**, not dropped. Current six form keys/selector revisions are not staged forms. Decision 34 supersedes the plan's earlier travel exclusion. | Separate R/reimbursement/staged-forms lane must implement under approved reimbursement plan and provide exact files/tests/routes at merge; none found in this Events checkpoint. Do not invent evidence paths for absent implementation. |
| 13. Docs / independent review / acceptance | EV3-DOCS adds module/invariant/source/status/env/notice/runbook/traceability prose. Independent integrated review, all §16 tests and browser/physical QA remain pending. | Docs index [README](README.md), [AO ledger](acceptance.md); run complete GF1/lane file lists and exact registry/privacy/restore/tombstone/concurrency gates. This lane does not execute Docker/Django or certify sibling work. |

Additional integration findings to hand to the owning lane:

- **Enablement blocker:** `makerspaces/setup_areas.py::features_for()` includes all children
  of selected area parents. Choosing Events therefore includes all five new programme
  features. Exclude these until accepted or implement separate explicit opt-in; add a
  regression in `tests/makerspaces/test_setup_areas.py`. Registry false defaults alone
  do not protect setup. This docs lane cannot change the owning code.

- `config/settings.py` reads eleven new key/account settings; Compose/installer forwarding
  is absent in this checkpoint. No new backend UI delight/egg setting reads were found;
  `UI_DELIGHT_ENABLED`/`UI_EASTER_EGGS_ENABLED` are proposed wiring, not deployable env controls.
- B's `api_runtime.py` has no installed production storage/scan/probe/read providers, while
  `HackathonConfig.upload_policy` defaults to `maker` and the registry names
  `hackathon-maker-v1`. Reconcile by a tested provider; do not silently accept an unknown policy.
- `views_checkin.py` has the exclusive legacy/v2 resolve input, but the scanner confirmation
  entry must invoke `credentials.resolution.confirm`; a read-only resolver is insufficient.
- `event_authority.py` still reads stored grant permission arrays. Live entitlement-source,
  issuer, role/track/window/conflict checks must be installed before helper authority is trusted.
- `certificates/seeds.py` can read catalogue data, while badge image layers are rejected by
  `badge_designs.py`; catalogue existence is not proof of six-family printable installation.
- B2 real-export, parser-adversarial, actual vendor/WASM/browser and media-probe acceptance
  remain open. Authentic italic font approval is also pending; synthetic oblique is not accepted.

## Required evidence before enablement

Use `./scripts/dev.sh test` with the current checkout mounted, disposable PostgreSQL 16,
Redis and private storage. No two pytest processes may share a database; do not run the
full suite alongside a review that runs tests. Verify migrations/checks/raw SQL bypass,
last-seat/slot races, source/global/tenant/account fences, keys/erasure, broker recovery,
scan/probe/storage faults, import/backup/purge and optional-module profiles.

Run TypeScript, focused Vitest, real browser public-URL-to-application/team/video submission,
mentor/volunteer/judge/sponsor journeys, PDF/physical QR proofs and light/dark/mobile/zoom/
keyboard/reduced-motion/44px/contrast checks with the Space Works brand audit. Mocks and
jsdom axe do not prove those properties. The AO table requires passing test output and
browser evidence, not just test-file presence. Obtain independent integrated review and
the owner's final QA. Only the owner stages/commits under the agreed handoff, merges and
pushes; this lane performs none of those actions.
