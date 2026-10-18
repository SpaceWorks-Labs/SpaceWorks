# Events programme — Lane D handoff

Worktree: `ev-d`; branch: `lane/events-d`; contract checkpoint: `72bf7be7`.
The approved plan, including owner decisions 1–33, remains binding.
No staging, commit, merge, migration, shared-barrel mounting or generated API edit was performed.
Pre-existing `frontend/src/test/staffActor.ts` is untouched.

## Built per plan

- **§7 definitions/judging:** event-owned tracks/prizes, anchored positive Decimal-weight criteria,
  draft/open/closed/finalized rounds, frozen config and project enrollment, versioned assignments,
  private score drafts, submitted 1–5 judgments, distinct top-three ballots, fixed six-point budgets
  for small batches, explicit skips/recusals and C conflict predicates. Deterministic minimum-cost
  capacity matching balances workloads and reports deficient coverage. Existing invalid/conflicted
  assignments do not satisfy coverage; a partially invalid ranking ballot loses its entire exposure
  and is reassigned rather than silently reweighted. Room/track scopes, submission currency and
  live judge entitlements are rechecked. The estimator uses the plan's ceiling formula.
- **§7 results:** priority-ordered criterion tie breaks with shared ranks, actual submitted-view
  counts, distributions, low-n/zero-variance diagnostics and optional frozen z-score ranking.
  Finalization needs coverage or a full-manager reason, integrity confirmation and explicit tie
  selection reasons. Immutable result/round/award snapshots retain prize labels. Corrections append
  revisions. A separate operational publication pointer supports import reset without deleting
  announcement history. Publish rechecks source calculations; only the first announcement calls
  A/B's retention-anchor adapter. Private C shortlist signals and sponsor proposals remain separate
  from scoring.
- **§7 + §12E gallery:** one initial publication, frozen typed file/link selections, explicit manager
  amendments/result-reference corrections, hide/unhide, live public allowlists and independent
  past-event gates. Any current active sealed teammate can withdraw immediately; a leader's explicit
  grant never publishes. Consent generations stop regrant from reviving old URLs. Expired bytes leave
  a card/hash with no download/player controls. Selected profile/photo cards come through E's live
  projection; no staff/account-vault fallback exists.
- **§7 + §12C sponsors:** sole `ParticipantSponsorResumeConsent` model/workflow for both participants
  and role-only contributors, immutable revision history, exact named sponsor/recruiting disclosure,
  owner-only grant/revoke, ready current asset/hash binding, replacement/delete revocation hook,
  own-track matching and bounded-stream reauthorization callbacks. A contributor with no matching
  frozen own-track project remains ineligible. Sponsors receive no private answers, scores, notes,
  unconsented participant directory or account-vault access.
- **§12/13/14/15 integration:** closed DRF command inputs, UUID/header replay checks through G's
  canonical receipt, audited state writes, typed errors, no-store views, exact frozen D URL names,
  source/fence/event/authority order, read-only F summaries, clone/config adapter, durable notice
  intents and retry sweep, literal model/route manifests and inert pages providers.
- **Frontend:** drawer-ready `JudgingPanel`, rubric/definition editor, coverage/estimator, result and
  gallery controls; delegated judge/sponsor consoles; public gallery/results; owner gallery privacy
  and résumé sharing. These use existing layouts/primitives, CSS tokens, Gilroy/one layout accent,
  lucide icons, named controls and keyboard alternatives. Query keys include actor/context/host/event;
  session/scope changes destroy drafts, denied access removes protected queries, stale commands retain
  edits for explicit review. File reads/previews and selected-photo rendering are injected from B/E.

## Exact files

All production files are new and inside §15 D ownership:

- `backend/apps/events/judging/`: model files/barrel, `calculations.py`, `assignment_planner.py`,
  `definitions_workflow.py`, `round_workflow.py`, `scoring_workflow.py`, `workflow.py`,
  `results_workflow.py`, `sponsor_consent_workflow.py`, `conflicts.py`, `sponsors.py`,
  `eligibility.py`, `ballot_invalidation.py`, `boundary.py`, `ports.py`, `lifecycle.py`, `clone.py`,
  `projections.py`, `errors.py`, `serializers.py`, `serializers_read.py`, `api_common.py`,
  `views_{definitions,scoring,results,sponsors,signals}.py`, `urls.py`, the two JSON manifests and this report.
- `backend/apps/events/submissions/gallery_*.py`: models, command/read serializers, consent/publication
  workflows, projection and HTTP adapters. No B-owned submission file or package initializer was edited.
- `backend/apps/events/programme_sections/{__init__,providers}.py`.
- `frontend/src/features/staff/hackathonJudging/**` and
  `frontend/src/features/events/hackathonGallery/**` (explicit `index.ts` exports).
- Tests: the eleven Python paths in `D-rerun-files.txt`; shared D fixture
  `backend/tests/events/programme/judging/domain-fixtures.json`; five beside-code frontend test files.

## Model manifest — G owns migrations and registry installation

`model_manifest.json` contains **28 concrete models, 223 expanded fields, 10 explicit User edges**,
literal FK/constraint definitions, JSON ID slots, export/import/uniqueness/encryption/object policies,
required DB guards and purge dependencies. It is generated data; production Python/TS files stay under
300 lines. No D model owns object storage bytes or an account-scoped key.

- Definitions: `HackathonTrack`, `HackathonPrize`, `JudgingRound`, `JudgingCriterion`.
- Judging: `JudgingRoundProject`, `JudgeAssignment`, `JudgeScore`, `JudgeRankingBallot`,
  `JudgeRankingChoice`, `JudgeConflict`, `JudgingReason`.
- Results: `EventResultRevision`, `EventResultRound`, `EventAward`, `ResultAnnouncement`,
  `ResultPublicationState`, `SponsorWinnerProposal`, `JudgingNotice`.
- Sponsor consent: `ParticipantSponsorResumeConsent`, `SponsorResumeConsentHistory`.
- Gallery: `GalleryConsent`, `GalleryConsentItem`, `GalleryConsentRevision`, `GalleryPublication`,
  `GalleryEntry`, `GalleryEntryAsset`, `GalleryEntryLink`, `GalleryAmendment`.

PII mapping is required for `JudgingReason.body` and `JudgeScore.notes`, both scoped by
`makerspace_id`, nonsearchable. Histories/results are append-only. G must install PostgreSQL guards;
Python save/queryset protection alone is not sufficient. Operational publication/consent state resets
on tenant import; private evidence, hashes and immutable history remain. `JudgingNotice` and the
G-owned command receipts are portable coordination, not transferred authority or pending side effects.

## Routes / schema

`route_manifest.json`: **37 D paths / 69 method entries**; all 32 frozen D path/name/method contracts
are preserved. `judging.urls.urlpatterns` is ready for G to include once beneath `/api/v1/` after all
origin/claim/delegated/API-client/source policies are registered. Schema decorators and actual closed
serializers live beside each endpoint. POST/PATCH require `Idempotency-Key == operation_id`.

Five explicit domain additions complete otherwise unoperable lifecycle/read journeys:

1. GET/HEAD `admin/events/{pk}/gallery/` — manager publication status and internal hide/unhide IDs.
2. POST `admin/events/{pk}/gallery/amend/` — fresh, separately audited selection/URL after regrant.
3. POST `admin/events/{pk}/gallery/correct-result/` — audited result-reference correction.
4. POST `admin/events/{pk}/sponsors/{sponsor_id}/prizes/{prize_id}/propose/` — scoped proposal only.
5. GET/HEAD `admin/events/{pk}/judging-signals/` — full-manager private C shortlist board.

**B owns the frozen public gallery-asset route.** D does not duplicate it in its URL list. B/G should
mount the canonical name exactly once, using `gallery_views.GalleryAsset` or B's view delegating to
`gallery_projection.asset_download`. PDF/original streams never redirect; B owns Range/headers/storage.
No upload, grant-assignment, certificate or alternate account route was added by D.

## Verification

- `npx tsc -b`: **final rerun passed**.
- Focused vitest command below: **5 files / 20 tests passed**, including axe checks on judge editing,
  gallery files and owner privacy controls, unsafe URL/parser tests and scope-switch draft clearing.
- `py_compile`: **43 production + 11 test Python files passed**.
- Stdlib checks passed: manifest field/User-edge coverage, frozen D route/path/method equality,
  production file ceiling, whitespace, CLAUDE/AGENTS byte equality and LF rerun list.
- `git diff --check`: passed; staging index remains empty. New-file whitespace is checked separately.
- **No Docker, Django or pytest execution.** Backend behavior and DB triggers are not certified here.
- `codex doctor`: config/home resolution and required endpoint connectivity failed. An independent CLI
  review pass was unavailable; no review approval is claimed.

```text
npx vitest run --config vitest.local-junction.config.ts --configLoader runner src/features/events/hackathonGallery/parsers.test.ts src/features/events/hackathonGallery/GalleryCard.test.tsx src/features/events/hackathonGallery/PrivacyControls.test.tsx src/features/staff/hackathonJudging/JudgeConsole.test.tsx src/features/staff/hackathonJudging/definitionDraft.test.ts
```

The requested LF list is at:
`C:/Users/shaan/AppData/Local/Temp/claude/C--Users-shaan-Music-SpaceWorks-SpaceWorks--claude-worktrees-design-revamp/421e2760-7305-4de3-8892-b576425ad101/scratchpad/ev/D-rerun-files.txt`.
Backend tests, the D JSON test fixture and all five frontend test files remain ignored by the
repository's existing root rules; G/owner must explicitly include them when eventually staging.
D did not edit `.gitignore` or stage anything.

## CROSS-LANE — install before G acceptance

| Owner | Concrete integration requirement |
| --- | --- |
| G | Import D's model barrel **and** `submissions.gallery_models`; centrally author migrations off the actual leaf. Install every manifest disposition, PII mapper, immutable/same-event/ballot/score guard, source/task/direct-service gate, authority and method policy before mounting URLs. No catalogue digest/generated API edits were made by D. |
| G/P | Install `ProgrammePorts.fences` with global→sorted tenant→sorted account shared fences before Event. D includes the actor account in the declared set. `lock_authority` must return a fresh actor and lock membership/grant/org sources without locking User/key rows. **Do not reuse legacy `resource_grant_locks.lock_tenant_authority`**, which locks User after Event. `assert_lock_context` attests cross-lane already-locked calls; plain HTTP objects confer no authority. |
| A/G | `require_programme` implements actual off-default hackathon/gallery/edition/module/servable gates; owner subject resolution admits eligible account-only participants. `lock_team` locks the A team parent before D consent children; `require_team_member` proves both live active membership and sealed roster, and leader eligibility for grants. A/B's `publish_retention_locked` sets first publication only and never extends retention on correction. |
| B | Map frozen `Snapshot`/`ParticipantAsset` values and live asset projections; supply own-track/judge file reads, frontend bounded downloads/previews and the canonical public asset mount. Invoke `eligibility.require_selections_locked` with authoritative `track_occupancy_locked` at submit. Invoke `lifecycle.invalidate_snapshot_locked` on supersession/disqualification and `sponsor_consent_workflow.revoke_asset_locked` on résumé replacement/delete **in the same transaction**. Stream callbacks recheck before storage and each ≤1 MiB chunk using G transport and bounded SDK timeouts. |
| C | Map approved/source-reissued/time-and-track-scoped judge/sponsor roles, canonical self/mentoring/affiliation/declared conflicts, named sponsor disclosure revisions and own-track memberships. `shortlist_signals` excludes practice rows, private notes and mentor identities; return only the typed production summary. Role-only consent delegates to D's sole model/workflow, never a C table/writer. |
| E | Map `public_member_card` and pages `role_cards` through current selected membership/profile/public-card scope, handle and photo consent. Wire E's card renderer into gallery/pages; no auto-selected or staff photo. |
| F/G | Consume `judging.projections.summary`; install `notify_intent` as a deduplicated source-backed outbox adapter and periodic `lifecycle.sweep_notices`. Revalidate publication/consent/role/recipient authority on dispatch/retry; broker failure leaves the committed intent. |
| G/Pages | Install `programme_sections.providers.install(adapter, register)` and `hackathonSectionRenderers` only with the actual shared registry. The pages adapter must prove effective-page release, group/section visibility and unexpired website independently of D's past-gallery gate. Base tracks/sponsors/schedule stay with pages. |
| G/frontend | Mount drawer/owner/public/delegated exports in the AppShell and existing navigation; pass actual actor/context/host scope, B readers and E renderers. Add public no-store byte routes to PWA exclusions. Wire D's clone adapter from the G-owned clone workflow with C's new-event sponsor map. |

## UNFINISHED — required before integration acceptance

1. **G verification, integration step 5:** run every path in `D-rerun-files.txt` after migrations,
   provider adapters and PII registration. This includes real-DB replay/authority tests and
   `judging/test_postgres_fences.py`'s blocking fence-before-Event assertion. Mocked live-policy tests
   do not replace actual PostgreSQL behavior.
2. **G+B+C contract follow-up, before acceptance:** add/run an integrated graph test at
   `backend/tests/events/programme/sponsors/test_integrated_subjects.py`: role-only contributor grant
   visible through the canonical owner endpoint, no matching-project sponsor download, later own-track
   eligibility, revoke from either owner surface denying an already-issued B stream, and replacement
   never inheriting consent. Use actual A/B/C providers and G fixtures, not a second consent model.
3. **G migrations/portability verification, before acceptance:** exercise the manifest DB guards via
   raw SQL; round/snapshot/role/track/sponsor splices; exactly-one gallery item shape; append-only result
   history; immutable submitted judgments; import public-pointer/consent resets; typed JSON remap/hash
   provenance and dependency-ordered purge. G owns these cross-cutting test files/registry edits.
4. **G/frontend QA, final programme acceptance:** real browser light/dark/mobile/zoom/keyboard/reduced
   motion/contrast/44px/Impeccable audit, including all newly mounted D surfaces and B/E readers/cards.
   Unit axe checks do not measure real-browser contrast. ARTWORK's final judge/gallery assets and the
   shared pages renderer acceptance remain programme integration work; no substitute assets were made.
5. **Orchestrator/G review owner, before acceptance:** independent review of this exact D delta,
   including `ports.py`, `boundary.py`, every workflow, manifests and tests. Resolve findings before
   enabling gates. The separate CLI gate was unavailable, and the owner alone merges/pushes.

These are explicit required follow-ups assigned to the integration owners, not accepted deferrals or
a claim that the integrated programme is deployable. D's provided adapters remain inert until installed.
