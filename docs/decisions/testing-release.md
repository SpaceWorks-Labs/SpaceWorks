# Decisions: Testing and release process

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-384 — Decisions and handover rule
- **Area:** testing-release
- **Date:** 13 November
- **Decision:** Every repository commits `docs/decisions.md` (each decision with its reason, never deleted, superseded chains kept) and keeps a git-ignored `handover/` folder updated after each change. The application's public decisions file is generated from the private ledger without session mechanics.
- **Why:** Keep reasoning discoverable without exposing private notes.
- **Status:** current

### D-383 — Delivery pipelines documented
- **Area:** testing-release
- **Date:** 13 November
- **Decision:** The design system documents branch model, required checks, semver with version bumps, release notes and tags, and CI-only releases per stack, with a per-repo matrix of gaps.
- **Why:** One delivery convention for every product.
- **Status:** current

### D-382 — Design system versioning
- **Area:** testing-release
- **Date:** 13 November
- **Decision:** The design system has its own version (Space Works Design System v2.0, tagged v2.0.0 with a `VERSION` file) separate from the app version, which is only mentioned where it describes the app.
- **Why:** Avoid confusing the design-system release with the app release.
- **Status:** current

### D-379 — Every change ships with tests
- **Area:** testing-release
- **Date:** 13 November
- **Decision:** Product rules state that every change ships with its tests, per change type: bug-fix regression, endpoint allowed/refused/other-tenant/module-off/audit, area on/off, money, web and native parity, migrations, UI states, themes and reduced motion, and guard tests. The design system keeps a decisions file recording each design decision with its reason.
- **Why:** Prevent regressions and keep the reasoning discoverable.
- **Status:** current

### D-317 — Default card colours, sample card, loader, full release gate
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** The Aurora card template defaults use the brand palette (layout unchanged). A sample ID card ships on every install. A full backend regression plus the full frontend suite, with zero failures, is required once before pushing to the integration branch or opening the release PR.
- **Why:** Reason not recorded for the card defaults; the full gate overrides the targeted-tests preference for release.
- **Status:** current

### D-291 — Feature-completeness outcome fixes
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** Gaps found were fixed: a double-submit guard on web shop checkout (Idempotency-Key), guardian-consent re-check at event check-in, a `webhook_endpoints` limit key, MLH presets, the waiver gate reachable without guest passes, wallet credentials shown for event wallet passes, and event/volunteer money no longer rounded to 0.01 (per D-268). Real-tool sample files for some CAD and embroidery previews stay waived.
- **Why:** Closing the D-287 audit.
- **Status:** current

### D-287 — Feature-completeness audit before release
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** An audit walks the decisions and module docs and proves each shipped feature exists end to end (route, permission, UI, docs, test), with extra depth on Events, Organizations and ID cards; every gap is built or fixed before the test run. Outcome: 330 features, with the 25 partial, 1 missing and 1 contradicting item fixed.
- **Why:** Reason not recorded
- **Status:** current

### D-286 — Release gate: every test runs, all reds fixed
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** Before a release, every test file is assigned to exactly one chunk so none is left unrun, and backend, frontend, build, e2e, CI scripts (check_rules, check_docs incl. mermaid, check_version_bump), `makemigrations --check`, ruff, `manage.py check`, drift guards and dependency audits all pass. Each red is fixed at its root (product bug fixed, stale assertion updated with a reason, removed feature skip-marked with a reason; never delete a test), and smaller issues such as hook warnings, flaky tests and deprecation warnings are fixed too.
- **Why:** Reason not recorded
- **Status:** current

### D-280 — Every merge to main carries a higher version
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** Each push or merge to `main` must have a strictly higher semantic `VERSION` than the previous commit, with matching version strings and a `docs/release-<version>.md`. A `version-bump` check runs on pull requests into `main`, `release.yml` fails a push that did not bump the version or whose version already has a tag, and a bump helper updates all strings at once. `version-bump` is a required status check on `main`.
- **Why:** Prevents silently rebuilding an existing release.
- **Status:** current
- **Implemented in:** `VERSION`, `.github/workflows/release.yml`

### D-279 — Release is produced by the pipeline on merge to main
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** `.github/workflows/release.yml` runs on every push to `main`, creates the release without the "latest" flag, then marks it latest after images are verified and promoted; the installer takes only the newest non-draft, non-prerelease release. Release notes live in `docs/release-<version>.md`, and the final backend image is rescanned by digest after the pipeline builds it.
- **Why:** A hand-made draft release would collide with the pipeline.
- **Status:** current
- **Implemented in:** `.github/workflows/release.yml`, `docs/project/release-process.md`

### D-264 — Open items fixed in parallel, non-overlapping batches
- **Area:** testing-release
- **Date:** 11 November
- **Decision:** The 0.12.0 open items (none High or Blocker) are fixed in batches with no file overlap: backend, UI console gaps, i18n/copy, tests/runtime verification and payments with the 3-decimal migration.
- **Why:** Avoids merge conflicts across concurrent work.
- **Status:** current

### D-261 — Every audit finding is fixed regardless of severity
- **Area:** testing-release
- **Date:** 10 November
- **Decision:** Every finding from release audits and build reports is fixed whatever its severity, including full 3-decimal currency support, except items that are explicit maintainer decisions or external-only actions. A consolidated open-items list is worked until empty.
- **Why:** Low-severity leftovers accumulate into release risk.
- **Status:** current

### D-253 — Review findings: notices, renewals, wallet passes, installer signature, labels
- **Area:** testing-release
- **Date:** 10 November
- **Decision:** Shop notices check the shop module when emitted (nothing is written while Shop is off); `raise_renewal` returns "skipped" when the membership module is off; Apple wallet passes are voided only when revoked or converted (an expired pass shows as expired); the installer refuses with a clear message when cosign is present but signature assets are missing; stored "Lending" choice labels become "Inventory loans"/"Inventory" via label-only migrations.
- **Why:** Findings from the release test review.
- **Status:** current

### D-246 — Condition tests for the whole app
- **Area:** testing-release
- **Date:** 10 Nov 2026
- **Decision:** Condition tests cover every module and feature, not only new ones: backend (module/capability on and off, role allowed/refused, validation, idempotency, cross-space isolation, money and session rules, audit and notifications) and frontend (per-role visibility under module on/off, loading/empty/error states, key flows). Tests are added, never deleted.
- **Why:** Reason not recorded
- **Status:** current

### D-245 — Backup and restore audit; README banner
- **Area:** testing-release
- **Date:** 10 Nov 2026
- **Decision:** Backup and restore are audited end to end (in-app encrypted backups, offsite copies, host backup and `restore.sh`, pre-update dumps, tenant migration): every new model, field, migration and trigger is captured and restored, scoped-PII fields stay encrypted, and wallet/integration secrets never enter tenant exports. The README gets a professional SVG banner with the official logo, rounded corners and light and dark variants.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** docs/backup-and-restore.md, docs/banner.svg

### D-244 — All tests are committed and never deleted
- **Area:** testing-release
- **Date:** 10 Nov 2026
- **Decision:** All backend and frontend tests are committed and none are deleted: `backend/tests/<app>/` mirrors `backend/apps` one-to-one, frontend tests sit beside components, with `frontend/e2e/`. A test that cannot pass because its feature is not in the release is kept with an explicit `pytest.mark.skip(reason=...)`. Every feature gets condition coverage (module on/off, each role allowed/refused, happy path, validation, idempotency, cross-space isolation, money rules), and CI runs the committed suites.
- **Why:** The maintainer wanted full conditional coverage kept in the repo.
- **Status:** current
- **Implemented in:** backend/tests, frontend/e2e, .github/workflows/tests.yml

### D-238 — Release finish choices
- **Area:** testing-release
- **Date:** 10 Nov 2026
- **Decision:** The 0.12.0 release is prepared as a draft GitHub release with install.sh, bundle, `SHA256SUMS` and cosign signature, left unpublished for the maintainer. Version is 0.12.0 final, built as roughly 20 per-phase commits that each build on their own.
- **Why:** Publication from main stays with the maintainer.
- **Status:** current

### D-227 — Final-audit minor fixes
- **Area:** testing-release
- **Date:** 10 Nov 2026
- **Decision:** A "co-organizer" means a holder of `edit_details` on the event or series (helpers excluded); machine-pool included hours are zero while `machines` is off; sweep limits bound rows acted on, not rows examined; lookup endpoints reuse the `member_card_resolve` throttle; incident assignees must hold active membership (else 400); receipts-payments is refused wholesale for non-session callers; guest passes are re-windowed on an event move; dark surfaces keep the teal-lift recipe over black.
- **Why:** Reason not recorded
- **Status:** current

### D-186 — Documentation completion gate
- **Area:** testing-release
- **Date:** 5 November
- **Decision:** Every module and capability switch has a precise "when it is off" entry, user manuals exist per role, an operator manual leads with self-hosting, and a logging and audit reference is generated from the audit presentation catalogue.
- **Why:** Docs must match the final screens and the separation audit.
- **Status:** current
- **Implemented in:** `docs/MODULES-OFF.md`, `docs/USER-MANUALS.md`, `docs/audit-action-reference.md`

### D-148 — Public repo carries no planning material; README is a guide
- **Area:** testing-release
- **Date:** 31 October
- **Decision:** The root README is a short guide (poster banner, what you can do, screenshot gallery, hosting, quick start, links) and detailed reference moves into `docs/`. Plans, prompts, hand-offs and research notes are not committed; patterns in the ignore file keep them out. History is not rewritten.
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `docs/README.md`

### D-134 — End-of-release feature audit
- **Area:** testing-release
- **Date:** 28 October
- **Decision:** At the end of each release a full feature audit runs: a live walkthrough of every module as each role with modules on and off, a code and decision trace per module (switch, audit log, finance, notifications, permissions, docs), and end-to-end browser tests for key flows. Gaps become fixes before the PR.
- **Why:** Reason not recorded.
- **Status:** current

### D-122 — Version numbering
- **Area:** testing-release
- **Date:** 27 October
- **Decision:** Releases bump the root `VERSION` file and the OpenAPI version setting together, regenerate the schema and the generated API types, and add a changelog entry.
- **Why:** A consistency test enforces that the version appears in both places.
- **Status:** partly superseded by D-146
- **Implemented in:** `scripts/bump-version.sh`, `scripts/ci/check_version_bump.py`

### D-121 — Release PR contents
- **Area:** testing-release
- **Date:** 27 October
- **Decision:** Each release PR carries the local test results per area, release notes and a versioned changelog entry, an upgrade guide (image switch, removed features, new settings, migrations, steps) and a security summary. Showcase screenshots are added to the README.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `docs/upgrade-to-0.11.0.md`, `docs/security-summary-0.11.0.md`, `docs/release-0.11.0.md`

### D-108 — Pull-request CI is checks only
- **Area:** testing-release
- **Date:** 26 October
- **Decision:** CI on pull requests into main runs fast checks only (frontend build, type check and lint, Django system check, migrations check, OpenAPI drift, the 300-line rule, `CLAUDE.md` equals `AGENTS.md`) and is a required status check. The full local regression must be green, with pass counts in the release PR description, before merging.
- **Why:** The maintainer kept checks-only CI after weighing that it cannot catch behaviour regressions.
- **Status:** partly superseded by D-238
- **Implemented in:** `.github/workflows/checks.yml`, `scripts/ci/check_rules.py`

### D-106 — README banner and screenshots
- **Area:** testing-release
- **Date:** 25 October
- **Decision:** The README gets a wide banner and product screenshots (light and dark, brand tokens) saved under `docs/readme/`, done last so they show every merged feature.
- **Why:** Reason not recorded.
- **Status:** partly superseded by D-168

### D-88 — Production readiness gate
- **Area:** testing-release
- **Date:** 24 October
- **Decision:** Before every release push a gate checks a security review of the release diff, upgrade from the current main with a seeded old database, production compose from built images (fresh and upgrade), query-count guards and no N+1, hardening (DEBUG off, env-only secrets, no debug routes, PII-free logs, rate limits), clean dependency audits and AGPL-compatible licences, a backup and restore drill, and docs that match the code. Any failure blocks the push.
- **Why:** The maintainer asked that everything be production-ready.
- **Status:** current

### D-81 — Final audit before each push
- **Area:** testing-release
- **Date:** 22 October
- **Decision:** Before each release push a full audit covers the UI against the brand language (light/dark, all device sizes, accessibility), the mascot and easter egg rules, every module and capability on and off, every recorded decision, and end-to-end browser journeys per module on a seeded showcase space. Failures are fixed before the push.
- **Why:** Reason not recorded.
- **Status:** current

### D-67 — Source file size and doc parity gate
- **Area:** testing-release
- **Date:** 21 October
- **Decision:** Before release every non-generated, non-migration source file stays within 300 lines, split with the barrel pattern, and `CLAUDE.md` is byte-identical to `AGENTS.md`.
- **Why:** Keeps modules small and lets other tools read the same rules.
- **Status:** current
- **Implemented in:** `scripts/ci/check_rules.py`
