# Design revamp — Space Works brand v1 + Yuyu-grade UX (PLAN v2.1)

Branch `feature/design-revamp` (worktree `.claude/worktrees/design-revamp`, cut from `dev` @ `d3e5ed29`).
Status: **v2 for Stage-1 review round 2.** v1 got REVISE (10 issues) — every one is answered in the
research specs below and summarised in §9.

## 0. Binding owner rules

1. **Only two sources.** All visual identity (colour, type, logo, icons, shape, voice) comes from
   `docs/brand/space-works-brand-guidelines-v1.pdf`. All layout / IA / interaction / states / microcopy
   structure comes from the Yuyu boards (`Yuyu — New Design.zip`, 4 boards, 28 screens). Nothing else.
   Where neither source covers something, the value is **derived from brand values** (mixes of Deep Ink
   and Warm Cream, OKLCH walks of a brand hue) and labelled "derived"; the one colour neither source
   gives in the brand — destructive red — follows Yuyu's danger-zone usage with a brand-warmth brick
   derived by the solver.
2. **Keep all functionality, re-themed.** No feature added, none removed. No backend behaviour, API,
   permission, module gate, workflow, state-machine or evidence rule changes. Dashboard widgets appear
   only where an existing endpoint already serves the data under the permission the actor already has.
3. **Every page is revamped** (all 42 staff tab keys, every public / member / auth / kiosk route),
   each built from one of a closed set of reusable layouts.
4. **Fonts** — *superseded 2026-10-15 by the approved brand kit: Gilroy 400–700 for all text and
   headings, Unbounded accent, Outfit retired (see `docs/brand/README.md`).* Original decision: brand guidelines followed 100 %, with **Outfit as the only
   non-brand font**. Official free **Gilroy** (ExtraBold 800, Light 300; Radomir Tinkov Free Font EULA —
   clause h permits `@font-face`, d/i permit embedding in software) for headings and display numbers;
   **Outfit** (OFL) for body/UI text in place of the unlicensed Gilroy weights; **Unbounded** (OFL, brand
   accent) for one accent phrase per layout. No other family anywhere (no monospace, no system stack
   beyond the generic fallback keyword). The unlicensed full-family gist is NOT used.
5. **Visual tie-breaks go to the brand, UX tie-breaks to Yuyu**: sidebar field = Citron (brand p.16 mock),
   control radius 10 px / cards 16 px (brand p.16), pills only for tags/status (brand); sidebar
   *structure*, switcher card, headers, tabs, rows, rails, settings rows, danger zone (Yuyu).

## 1. Specs (the plan's detail lives here — implementation lanes are briefed from these)

| Doc | Owns |
|---|---|
| `research/ui-brand-spec.md` | token table light+dark (solver-derived, every ratio shown), interaction fills, soft fills, status-pill palette, type stacks/scale, shape/motion, logo-in-product sizes, icons, call-site migrations (H.1–H.7), tenant-branding contract (H.5), contrast-guard changes (I) |
| `research/logo-extract/*.svg` | vector-exact logo extracted from the PDF content streams: symbol, stacked, horizontal, reversed, one-colour ink, app icon (verified against PDF pp.3/4/7) |
| `research/ux-yuyu-spec.md` | 30 Yuyu patterns with measurements, **10 reusable layouts (L1–L10)** with slot signatures, staff sidebar IA (§2), core screens S1–S24, UX quality bar (§4), Yuyu-doesn't-fit adaptations (§5) |
| `research/ux-screens-longtail.md` | every other screen (30 staff tabs, gates, 11 public pages, member tab bodies, stations, overlays) in batches A–J, layout variants (§11), **coverage table §14: every route + all 42 tab keys → spec + layout** |
| `research/shell-contracts.md` | 12 StaffApp gate cases + 45 workspace cases (Given/When/Then, file:line, covering test), test plan, request-queue URL contract, dashboard data availability, DataTable reflow, theme semantics |

Where this PLAN and a spec disagree, §0 rules win, then this PLAN, then the spec.

## 2. Design system (summary — exact values in ui-brand-spec.md §A)

- **Vocabulary kept, values replaced**; `secondary` renamed **`brand`** (tenant-overridable action colour
  of stranger-facing surfaces, default = teal) and new **`emphasis`** = Workshop Orange (never tenant
  overridable, one bold moment per layout, attention counters). `accent` = Maker Teal = staff action,
  active nav, focus. `success` Citron, `warn` Warm Yellow, `info` Sky Blue, `danger` = **Yuyu's
  danger-zone red sampled from the board** (values in spec §A). Light canvas Warm Cream; dark built from
  Deep Ink (dark accent = the spec §A value, Teal + 34 % Cream, with ink labels, because brand teal on
  Deep Ink is 2.36:1). **All colour values, ratios and goldens are exactly those in ui-brand-spec §A/§I —
  this PLAN restates no hex values.**
- Solid `*-soft` tokens replace every alpha tint; translucent text banned; no orange text token.
- `{name}-ink` vs fixed `on-*` semantics preserved; every interaction fill (rest/hover/active) specified
  with label ratios (Codex 1); `success/warn/info/brand-ink` defined and fill-as-text call sites migrated
  (Codex 2).
- Tenant contract (Codex 3): tenant colour only drives `brand` on the 10 stranger-facing callers +
  public/member shells; staff console has zero `brand-*` classes (source guard).
- Type: `font-display` Gilroy ExtraBold, `font-sans` Outfit, `font-accent` Unbounded — **exactly three
  families, Outfit being the only non-brand face** (owner). No system monospace: `font-mono` is retired by
  migration (Codex 10) — spec H.6 group A (machine strings: secrets, digests, JSON, PINs, codes) moves to
  Outfit with `tabular-nums` + `slashed-zero` and wider tracking instead of a `font-code` family; B →
  `tabular-nums`; C → deleted.
- Icons: `lucide-react` as the implementation of the brand icon spec (24 grid, 2 px, round ends).
- Theme: existing light/dark toggle kept as is (no "System" option — not in sources, not existing).

## 3. Reusable layouts and primitives

Layouts (ux-yuyu-spec §1A): L1 `AppShell` (+ no-workspace mode), L2 `DashboardLayout`, L3 `ListLayout`,
L4 `DetailLayout` (+ drawer presentation), L5 `SettingsLayout`, L6 `FormPageLayout`, L7 `FlowLayout`
(+ dialog presentation), L8 `AuthLayout` / `CenteredCardLayout` (+ wide), L9 `PublicLayout` /
`PublicDetailLayout`, L10 `KioskLayout`. Shared section: `ScanWorkbench`. Layouts hold zero gating.
Primitives: Sidebar family, WorkspaceSwitcher, UserMenu, PageHeader, Tabs (URL-driven), StatCard,
ListRow + DateChip/IdentityChip, StatusPill (absorbs Badge/StatusBadge), Callout, SettingsSection/Row,
DangerZone, ActivityRail, Avatar, SegmentedControl, TicketCard; restyle desk-button family, inputs,
Modal, ConfirmDialog, DetailDrawer, DataTable (single-DOM CSS reflow, keeps sort/columns/density/
selection — shell-contracts §5), EmptyState, Skeleton, Pagination, Field, toasts. Each ≤ ~200 lines.

## 4. Implementation — parallel Codex lanes

Repo convention: Codex implements in **lane worktrees** (≤5 concurrent, `codex exec --sandbox
workspace-write`, unstaged), each followed by a Codex review-and-fix pass; Claude verifies every lane
against this plan + specs, fixes small issues directly, commits on the lane, merges lanes into
`feature/design-revamp` (owner authorisation required — see §8), then runs build + tests on the merged
tree. Lane branches: `lane/dr-<name>` cut from the current `feature/design-revamp` head.
Gitignored tests (`frontend/src/**/*.test.ts(x)`, `frontend/e2e/`, `backend/tests/`, plus
`frontend/vitest.config.ts`, `frontend/playwright.config.ts`) are copied from the main checkout into
each lane (they stay ignored); updated tests are synced back to the main checkout at the end.

**Wave 1 — foundations (2 lanes, parallel):**
- `dr-tokens`: index.css tokens light/dark (§A.5 paste-ready), tailwind.config (colours, fonts, radii,
  shadows; drop `brutal*`/`blueprint`, blueprint body grid), components.css/chrome.css interaction states,
  `secondary→brand` mechanical rename (H.4, own commit), alpha-tint → soft, translucent-text bans (H.1),
  fill-as-text migrations (H.2), `text-bg`→`on-danger` (H.3), `font-mono` migration (H.6), StatusBadge
  map (H.7), `@font-face` for Gilroy/Outfit/Unbounded + font files + licence files, brandColours.ts +
  theme_contrast.py + MakerspaceThemeSettings (H.5), contrast-guard + golden test updates (§I).
  Docs in the same lane: INVARIANTS "One colour vocabulary" / type scale / buttons rewritten.
- `dr-brand-assets`: `SpaceWorksLogo` (symbol/stacked/horizontal/reversed variants from logo-extract,
  size floors per spec §F), favicon SVG + 16/32 PNG, apple-touch 180, OG 1200×630, member + kiosk PWA
  icons 192/512 (cream tile, symbol 62 %), `member-sw.js` + `offline.css` colours, `index.html`
  (`theme-color`, meta copy), `lib/branding.ts` default favicon (replace emoji), Unfold `COLORS` →
  teal scale + logo/favicon, `docs/brand/` rewrite (README, SVGs), `docs/banner.svg`,
  `docs/spaceworks-logo.png`, `lucide-react` install + replace `components/icons.tsx`/`staffNavIcons.tsx`.
  Gate after wave 1: build, vitest, contrast guards, visual check light/dark → whole app repainted,
  layouts unchanged.

**Wave 2a — primitives (1 lane, alone):**
- `dr-primitives`: every §3 primitive and restyle **except** the shell family (Sidebar*, WorkspaceSwitcher,
  UserMenu, JobTray pill, AppShell — owned by `dr-shell`). Exports a frozen prop contract
  (`components/ui/index.ts` barrel). vitest + axe per primitive. Merged before wave 2b starts.

**Wave 2b — layouts and shell (2 lanes, parallel, both cut from the head that contains `dr-primitives`):**
- `dr-layouts`: L2–L10 + presentations (FlowLayout dialog, DetailLayout drawer, CenteredCard wide) +
  `ScanWorkbench`. Owns `components/layouts/*` except `AppShell`.
- `dr-shell`: L1 `AppShell` (+ no-workspace mode) and the whole shell family; IA per ux-yuyu-spec §2
  with this correction: **only the logo + switcher + search trigger (top) and the user chip (bottom)
  are pinned; every nav item including the Settings and Platform blocks lives in the one scrollable nav
  region** (Codex r2-6); handout-only flat list + mobile bottom tabs; governance-only; machine-only;
  mobile drawer; replaces StaffHeader + StaffDock; **all 57 shell-contracts cases** as
  `StaffWorkspace.routing.test.tsx` + `StaffApp.shell.test.tsx`, plus a full-permission superadmin case
  at a 1280×600 viewport asserting every nav item is keyboard-reachable and scrolls into view;
  StaffDock.test → Sidebar.test; e2e helper updates (shell-contracts §2.2); `docs/SOURCE-MAP.md`.
  Gating code (`staffAccess.ts`, `staffTabs.ts`, `features.ts`, `memberTabs`, `publicHome.ts`) is
  consumed, never modified. Shared wiring files touched only here in wave 2: `StaffWorkspace.tsx`,
  `StaffApp.tsx`, `StaffTabContent.tsx`, `CommandPalette.tsx`, `JobTray.tsx`, `SetupChecklist.tsx`.

**Wave 3 — every screen (5 lanes, parallel, cut from the head containing wave 2):**
Before launch Claude writes `docs/design-revamp/OWNERSHIP.md`: every frontend file that any wave-3 screen
spec touches, mapped to **exactly one** lane (generated from the specs' component paths + a grep of their
imports; any file claimed twice is assigned to one lane and the other lane consumes it unchanged). Gitignored
test files belong to the lane that owns the component they test. Lanes may not edit files outside their
list; Codex prompts include the list. Resolved overlaps (Codex r2-3): delivery logs / suppressions (A8)
→ `dr-screens-admin` only; member account (C6, `/member/account`) → `dr-screens-public` only;
`features/payments/PaymentDocuments.tsx` and other payment components shared by staff Payments (A1) and
member Payments (H4) → `dr-screens-desk` only, `dr-screens-public` consumes them unchanged.
- `dr-screens-desk`: Dashboard (S1; only widgets shell-contracts §4 marks available — activity rail behind
  the Audit tab, due-back behind `issue_request` + Requests; others omitted; StatCard numbers are `ink`,
  an `emphasis` count is shown as an orange pill with ink label, never orange text — Codex r2-10),
  Requests (S2; URL contract shell-contracts §3 + §10.3 below), request detail + issue/return flow (S3;
  evidence/QR/remark hard rules untouched), Direct handout (S4), Job pickups, Payments family (A1) incl.
  shared payment components.
- `dr-screens-inventory`: Inventory list + item detail (S5–S6), Categories, Containers, Needs-fix,
  Stocktake, Transfers, To-buy, Ledger, Warranties, QR tools, Scanner, Bulk import (A2–A6, A10, A15–A16,
  B2–B3, E1–E2).
- `dr-screens-admin`: Members (S7), Staff & roles (S8), Makerspace settings family (S9, sub-nav via
  in-page anchors — no routing change), Email templates, delivery logs + suppressions (A8, B1), API
  access, Exports, Backups, Usage, Modules, Migration, Platform, Organizations + analytics, picker,
  create-makerspace flow (C1–C5, C7, D1–D4, E3–E4).
- `dr-screens-ops`: Machines (S10) + devices + service consoles, Events (S11–S12) + organized, Bookings
  (S13), Reports (S14), Audit (S15), Accountability, Member cards, Notifications (A7, A9, A11–A13, A17,
  B4–B5).
- `dr-screens-public`: Member area + tab bodies + account (S16, H1–H6, C6), public catalogue/item/event
  pages (S17–S19), all other public pages (G1–G11), auth (S20–S22, E5, Batch F), kiosk + stations
  (S23, I1–I4).
  Each screen lane: build/vitest/axe green on its own; delight checklist (§5) applied.

**Ignored-test hand-off (Codex r2-7).** The `feature/design-revamp` worktree holds the **canonical
ignored-test tree** (seeded once from the main checkout). Each lane is seeded from the canonical tree at
its cut point and records the seed (file list + SHA-256 manifest). When Claude merges a lane, it copies
into the canonical tree only the ignored test files the lane added or changed relative to its seed
manifest; a file changed by two lanes is merged by hand, never overwritten. The next wave's lanes are
seeded from the reconciled canonical tree.
**Deletions and renames propagate too (Codex r3):** at merge Claude diffs the lane's ignored-test tree against its seed
manifest and classifies every path as added / modified / **deleted** (a rename = delete + add, e.g.
`StaffDock.test.tsx` → `Sidebar.test.tsx`). Deletions are applied to the canonical tree. Conflicts: modify-vs-modify
is merged by hand; **delete-vs-modify** is resolved by hand (keep the modification only if the component it tests still
exists, else delete), and both outcomes are recorded in `docs/design-revamp/seeds/reconcile-<lane>.txt`. After each
reconciliation `npx tsc -b` + `npx vitest run` must be green on the canonical tree, which catches any stale test that still
imports a deleted component. Final step (wave 4): sync the canonical tree back to the main checkout **including
deletions** (by manifest diff, never a blind copy), listing every added / changed / removed test file in the final report.

**Wave 4 — integrate and verify:** copy-voice pass, empty/loading/error states audit against the
UX quality bar, `docs/` final (brand README, INVARIANTS, SOURCE-MAP, PROJECT-HISTORY line, CLAUDE.md +
AGENTS.md byte-identical stack line), full checks (§6), Stage-4 Codex review, owner QA.

## 5. Delight / fidelity checklist (gate for every screen lane)

From Yuyu: one primary per header (never pointing at the current screen); numbers in context
("5 / 120", "In 9 days", "2 min ago"); dashed empty cards pointing at the next control; inline Undo via
toast where an undo already exists (no new reversal endpoints); ticket card with perforation for member
card / event ticket; kiosk full-colour result card + "Next" + online/queued pill + "3 / 5" counter;
floating tilted product cards on the auth brand panel; labelled rating tiles; "Add to calendar /
Save" half-button pairs where those actions exist. Typographic marks only (✓ → ↗ ·) — **no emoji** (the
📦 favicon fallback and any emoji in UI strings are removed).
From the brand: logo clear space H÷4, gap H÷6, symbol ≥48 px / lockup ≥180 px; the sidebar uses the
**stacked** master (light: `lockup-stacked`, dark: `lockup-stacked-reversed`) per spec §F.3 because the
horizontal lockup cannot meet its floor in the sidebar; the assembled `lockup-horizontal-reversed.svg`
is **not a brand master and is not used anywhere**; favicons <48 px use the symbol master, tested at
16/32 px (brand p.6 "below 48 px test a dedicated small-size asset"). No logo recolour/stretch/effects, lowercase wordmark,
"Space Works" in copy, one Unbounded moment per layout, no orange text on cream, every status = colour +
word/icon, icons 24/2 px rounded, voice "Say / Skip" rules, sentence case.

## 6. Verification

- **Per lane:** `npm run build` (tsc + vite + PWA verify) and `npm test` (vitest + axe) in the lane, using
  the seeded `vitest.config.ts`.
- **On the merged tree after each wave:** the same, plus the isolated backend guards
  `./scripts/dev.sh test tests/test_frontend_theme_contrast.py tests/makerspaces/test_theme_contrast.py`
  (one isolated stack at a time).
- **Browser e2e via the repo runner, not the dev server:** `./scripts/dev.sh e2e` seeds `seed_e2e`, builds
  the **production preview** (`vite preview`, `E2E_PREVIEW_PORT` default **5173**; the kiosk service worker
  exists only there) and runs Playwright with `E2E_BASE_URL`. Before trusting any result, confirm the
  backend container mounts this worktree: `docker inspect spaceworks-backend --format '{{range
  .Mounts}}{{.Source}} -> {{.Destination}}{{"
"}}{{end}}'`. If it mounts another checkout, bring the dev
  stack up from this worktree first.
- **Existing specs:** `a11y`, `auth`, `request-lifecycle`, `hard-rules`, `public-visibility`,
  `offline-handover`.
- **New route sweep:** `e2e/revamp-routes.spec.ts` (ignored test, canonical tree). It is generated from the
  coverage table (`ux-screens-longtail.md` §14):
  - It visits **every** staff tab key reachable by the seeded superadmin, plus a handout-only and a
    machine-only actor.
  - It visits every public, member, auth and kiosk route.
  - For each one, in **light and dark**, at **375 / 768 / 1440**, it asserts:
    - axe WCAG 2.1 AA, including contrast, with zero violations;
    - no horizontal page scroll;
    - one `h1`;
    - the screen's primary action is visible and named as its spec says;
    - its tabs, filters and row actions are keyboard-reachable;
    - no `font-mono`, `font-code` or emoji in the rendered text.
  - Screens that need data use the seeded fixtures. Screens the seed can't reach are listed in the report
    as manually checked.
- **Visual check:** a browser-pane check of each layout and of the per-screen delight checklist (§5),
  done by Claude, with screenshots in the wave report.
- **Source-fidelity audit (owner, 2026-10-15):** after each wave merge and before owner QA, every screen is
  compared side by side against the two sources in the local `SpaceWorks-Design` checkout
  (`brand/space-works-brand-guidelines-v1.pdf` for colour/type/logo/icons/voice; `references/yuyu/*.png` for
  layout/UX). Deviations are fixed before the wave is marked done. The Yuyu boards are never committed to
  either repository (gitignored in SpaceWorks-Design; read from local disk only).
- **Process rules:**
  - Never run two pytest processes against one DB.
  - Never run the full suite concurrently with `codex review`.
  - Run at most one isolated test stack at a time (Docker memory).

## 7. Risks

- Shell rewrite vs routing invariants → 57 acceptance cases are written as tests before the dock is
  deleted (dr-shell lane).
- Wave-3 merge conflicts → strict file ownership per lane; shared files (StaffTabContent, AppRoutes,
  barrels) edited only in wave 2 or by Claude at merge.
- Tests outside git → copied per lane; final sync back to main checkout is a named step (owner action
  noted in the final report).
- Gilroy free EULA clause (f) "not make the Font available to any third party" vs a public repo: (d)/(h)/(i)
  permit embedding and web use; EULA shipped with the files; owner accepted.
- Free Gilroy has only Light/ExtraBold → all non-display text is Outfit by design.
- The requests deep-link quirk `/guest-admin/<tab>` → `/m/<slug>/admin/<tab>` (shell-contracts W45) is
  pinned, not fixed.

## 10. Codex round-2 resolutions (binding)

### 10.1 Tenant colours: never reject what is accepted today (r2-1)

The tenant label candidates are Deep Ink, Warm Cream, white, then **black**. Black is today's label,
kept for tenant colours only.

- **Degrade, don't reject.** If a derived pair fails, degrade the derived token instead of rejecting the
  colour:
  - soft → `panel`
  - link ink → `accent-ink`
  - hover / active → today's derivation
- **Rejection only for malformed values.**
- **Tests:**
  - a sweep over all 4,096 `#RGB`, with and without `accent_color`, asserting `valid` in both modes;
  - a parity test: every colour today's validator accepts (e.g. `#888`) is still accepted.
- Spec H.5 is patched to match.

### 10.2 Fonts and visuals (r2-2, r2-5)

- **Fonts:** spec D/H.6 is patched. There is no `font-code` and no monospace family. Machine strings use
  Outfit + `.code-text` (`tabular-nums slashed-zero`, tracking 0.02em). The source guard bans `font-mono`
  **and** `font-code`. Stacks are `"Gilroy", "Outfit", sans-serif` / `"Outfit", sans-serif` /
  `"Unbounded", "Gilroy", "Outfit", sans-serif`.
- **Colours:** every colour value comes from spec §A, including the dark accent and the Yuyu-sampled
  danger. The PLAN restates none, so the computed ratios and goldens are consistent.
- **Sidebar logo:** stacked masters (see §5). The dark public header uses the `symbol-reversed` master; the assembled
  reversed horizontal is never used, so no owner approval for it is pending.
- **Native code elements:** `code`, `kbd`, `samp` and `pre` are overridden in `@layer base` to Outfit with
  `.code-text` features (Preflight would otherwise give them a browser monospace). This is verified by computed-style
  checks, not utility-name guards (spec D).
- **Tenant tests:** spec §I is aligned with §10.1. `#777` and `#e91e63` are valid with a black label, the 400 path is
  exercised only with malformed values, and the bootstrap fallback uses a malformed stored value.

### 10.3 Request tabs: failure semantics (r2-9)

**Visibility.** A tab renders only if the actor holds the backend action its list endpoint requires:
- Pending: `accept_request`
- Ready, Active, History: `issue_request`

This mirrors the backend permission, so it hides only tabs that today render a 403 error. No readable
data is lost.

**Deep links with `?id=N`.**
- Probes run **only on visible tabs**, in this order: Pending → Ready → Active → History.
- Each probe requests `page=1` with only the id filter. It **ignores** the active page, search, ordering
  and history toggles, so a stale page or filter cannot hide the request.
- The first probe that finds the request selects its tab and opens it.

**Outcomes.**
- **Found:** the request opens on its tab.
- **All visible probes return empty:** "We couldn't find request #N in your queues." The current tab
  stays open.
- **Any probe fails (403/5xx/network) and none found:** "Couldn't open request #N. Try again." with a
  Retry button. This is distinct from not-found.
- **A probe fails but a later probe finds it:** it opens normally.

**Acceptance cases**, added to shell-contracts §3.3 and to `QueuesDrilldown.test` / `RequestQueues`
tests:
- an accept-only reviewer: only Pending is visible, and probes run only on Pending;
- an issue-only actor: Pending is hidden;
- `activePage=3` + `?id=N`, where N is on page 1, is found;
- a probe returns 403 on one tab and finds N on another;
- every probe returns 5xx, giving the retry state;
- the not-found state;
- old URLs (`queue=pending|accepted`, `?history=true`, page params) resolve to the same tab as today.

## 8. Owner decisions needed now

1. Authorise Claude to **merge `lane/dr-*` branches into `feature/design-revamp`** (CLAUDE.md reserves
   merges to the owner; this does not touch `dev`/`main`, which stay owner-only).
2. Plan approval.

## 9. Codex round-1 issues → where resolved

1 interaction fills → spec §A.3/B, H.1 · 2 standalone inks + fill-as-text sites → §A.2, H.2 · 3 tenant
contract → H.5 · 4 shell preservation tests → shell-contracts §1–2 · 5 URL acceptance cases →
shell-contracts §1B, §3 · 6 dashboard data → shell-contracts §4 (unavailable widgets omitted) ·
7 vitest/playwright configs + theme/brandColours tests → §4 lane setup, §6, spec §I · 8 request tabs +
DataTable behaviour → shell-contracts §3, §5 · 9 docs in owning phase → INVARIANTS in dr-tokens,
SOURCE-MAP in dr-shell · 10 asset/font inventory, font-mono, System theme → dr-brand-assets list, H.6,
"System" dropped.

## 11. Queued after wave 4 (owner request 2026-10-15) — separate plan + Stage-1 gate

1. **Last phase (owner decision 2026-10-15):** the new events/bookings pages live on `feature/yuyu-parity`
   (25 commits, 626 files, not yet in `dev`; `dev` == `d3e5ed29`). The revamp continues on `dev` now; after
   waves 2b–4, merge `dev` once yuyu-parity has landed there (or `feature/yuyu-parity` directly if the owner
   says so), re-run the wave-1 mechanical migrations (secondary→brand, font-mono, alpha tints) over its new
   files, resolve conflicts in the shell/staff files in favour of the revamp shell while keeping every
   yuyu-parity capability, and revamp its new pages with the same layouts/brand.
2. Two new protected default roles, **"Events Manager"** and **"Bookings Manager"** (owner update
   2026-10-15), seeded per makerspace like Space Manager / Inventory Manager / Machine Manager / Member, each
   holding everything to run its area so no custom role is needed. **One person can hold both** at the same
   makerspace (multi-role or composed-role design decided in the follow-up plan). On sign-in every staff
   member sees exactly the sidebar sections their combined permissions allow.
3. Dashboard access for Super Admin, Space Manager, Events Manager and Bookings Manager.
4. Per-machine assignment: a Space Manager assigns (and later reassigns) who manages each machine when it is
   created, without creating a custom role per machine.
These change RBAC, migrations and machine-scoping invariants, so they get their own plan
(research: `research/roles-events-machines.md`), Codex plan review and owner approval before implementation.
5. Every new screen from items 1–4 (dev's new events pages, the Events Manager / Bookings Manager role screens, the
   per-machine assignment flow — e.g. an "Assign people" step when a machine is created and a "Managed by"
   panel with Reassign on the machine detail) is built ONLY from the two owner sources: brand guidelines v1
   (visual) and the Yuyu boards (UX), composed from the revamp's layouts/primitives — no one-off pages.
