# Shell, queue, dashboard and table acceptance contracts

Research for `docs/design-revamp/PLAN.md` §3.4 / §4 phases 3–4, answering the Codex plan-review demand for
concrete acceptance contracts. **No app code was changed.** Paths are relative to the worktree root
(`frontend/src/...`, `backend/apps/...`); tests live only in the main checkout
(`C:\Users\shaan\Music\SpaceWorks\SpaceWorks\frontend\...`) and are cited as `[main] path:line`.

Abbreviations: **SW** = `features/staff/StaffWorkspace.tsx`, **SA** = `features/staff/StaffApp.tsx`,
**SH** = `StaffHeader.tsx`, **SD** = `StaffDock.tsx`, **SDP** = `StaffDockPopover.tsx`, **CP** =
`CommandPalette.tsx`, **MP** = `MakerspacePicker.tsx`, **USS** = `useStaffSession.ts`, **ACC** =
`staffAccess.ts`, **TABS** = `staffTabs.ts`, **STC** = `StaffTabContent.tsx` (all under
`frontend/src/features/staff/`). "moduleAllowedTabs" = `filterTabsByEnabledModules(getStaffAccess(...).allowedTabs, activeMakerspace)` (SW:75–80).

---

## 1. Shell invariants (Given / When / Then)

The rule behind all of them: **the new `AppShell`/`Sidebar` only consumes** `moduleAllowedTabs`,
`TAB_GROUPS`, `TAB_LABELS`, `staffTabPath`, `activeTab`, `routeTabDenied`. All of the gating and URL
canonicalisation in SW:75–115 and SA:52–151 stays where it is. The shell only renders it.

### 1A. Gate order outside the shell (StaffApp)

| # | Given | When | Then | Source | Covered by |
|---|---|---|---|---|---|
| S1 | session restoring | any staff URL | "Restoring session..." card, no shell | SA:52–54 | none, new test |
| S2 | MFA challenge pending | — | `MfaFlow` only, no shell | SA:56 | none |
| S3 | no user | — | `LoginPanel` (labels "Username"/"Password"); no sidebar | SA:58–68 | e2e `auth.spec` ([main] e2e/auth.spec.ts:7–14) |
| S4 | `must_change_password` | — | `ChangePasswordGate`, no shell; on change it invalidates `["staff","makerspaces"]` | SA:70–83 | none |
| S5 | superadmin and recovery `quarantined` | — | `RecoveryQuarantinePanel`, no shell | SA:89–99 | none |
| S6 | single-tenant locked and the makerspaces query is loading | — | "Checking makerspace access..." | SA:101–103 | none |
| S7 | single-tenant locked and no `activeMakerspace` | any `/admin/*`, including `/admin/platform-dashboard` | `StaffAccessDenied` | SA:105–115 | `[main] StaffApp.platform.test.tsx:32–37` |
| S8 | central, route slug present, list loading **or** route makerspace ≠ selected | `/m/b/admin/...` while A is selected | "Opening makerspace..." until USS sync sets selected=B | SA:117–123, USS:182–187 | none |
| S9 | central, selected≠null, list loading | — | "Restoring makerspace..." | SA:125–127 | none |
| S10 | central superadmin; selected is null **or** points at no listed space; route is not global | `/admin/inventory` | full-screen `MakerspacePicker` (outside the shell) | SA:129–151 | `[main] StaffApp.platform.test.tsx:27–30` |
| S11 | central superadmin, selected null or 999 | `/admin/platform-dashboard` | workspace renders, no picker (`globalRoute`) | SA:86–87,129,141 | `[main] StaffApp.platform.test.tsx:20–25` |
| S12 | central, any actor | `/admin/organizations` | treated as global: no picker even with selected=null | SA:87 | none |

### 1B. Workspace / shell rendering

| # | Given | When | Then | Source | Covered by |
|---|---|---|---|---|---|
| W1 | actor whose moduleAllowedTabs contain `dashboard` | shell renders | "Home"/Dashboard entry is present and links to `staffTabPath("dashboard",…)`. `TAB_LABELS.dashboard` stays "Dashboard": a "Home" label is shell copy only, and the palette still reads "Go to Dashboard" | ACC:105–107,123; TABS:146 | ACC logic: `[main] staffTabs.familyOnly.test.ts:33–35`; DOM: none |
| W2 | handout-only actor (e.g. `issue_request`+`return_request`+`upload_evidence`) | shell renders | **no** Home/Dashboard entry; nav groups only from `["requests","direct","handover","payments","notifications"]`, minus module-gated ones | ACC:112–123 | `[main] rbacF6.test.ts:25–31` (logic only) |
| W3 | collect-only actor (`["collect_service_request"]`), `machine_service` on | lands on `/admin` | redirected to Handover (`/m/<s>/admin/handover`); nav shows only Handover + Notifications; no Dashboard/Requests entry | ACC:119,132,201–203 | `[main] staffTabs.test.ts:165–174` (logic only) |
| W4 | central non-superadmin with no actions (governance-only) | any path | allowedTabs = `["organizations"]`; lands on `/admin/organizations` (never slug-scoped); no switcher-driven palette/JobTray when there is no activeMakerspace | ACC:108,120; TABS:144,160 | `[main] organizationGovernanceTab.test.ts:7–15` (logic) |
| W5 | single-tenant locked (any role) | shell renders | no makerspace switcher, no "Switch makerspace", no Organizations / Platform dashboard / Platform settings / Organized / Org analytics entries; "View public page" goes to `/` | SH:31–33,51,73; ACC:121,147,161,164,165 | `[main] organizationGovernanceTab.test.ts:17–20`, `organizationAnalyticsTab.test.tsx:39–75`, `staffTabs.moduleGates.test.ts:70–75` (logic); DOM: none |
| W6 | central, `makerspaces.length > 1`, not locked | shell renders | the switcher lists every listed makerspace and selecting one calls `chooseMakerspace(id)` | SH:51–63 | none |
| W7 | central, exactly one makerspace | shell renders | no switcher menu (the card is static) | SH:51 | none |
| W8 | superadmin, central | switcher open | "Switch makerspace" present; activating it calls `setSelected(null)`, which runs `chooseMakerspace(null)` → `navigate(/admin\|/guest-admin)` → picker (S10) | SW:126; USS:153–157; SH:73–77 | none |
| W9 | non-superadmin | switcher open | no "Switch makerspace" | SH:73 | none |
| W10 | superadmin who also holds a membership | shell renders | role label reads "Super Admin", not the membership role | SW:106–108 | none |
| W11 | route `guestOnly` **or** `handoutOnly` | tab content renders | `StaffTabContent` gets `guestOnly={guestOnly \|\| handoutOnly}` (narrow Requests: no Pending, no Active loans). Shell path-building (nav, palette, checklist) uses the **raw route** `guestOnly` | SW:152 vs SW:134,137,185 | none |
| W12 | actor without permission for a **known** tab (`STAFF_TAB_KEYS`), or the tab's module is off | `/m/lab/admin/qr-tools` | URL unchanged (no redirect); main shows "Access denied" with link "Go to <default label>" to the default tab path; **no** nav item carries `aria-current="page"`; tab content not mounted | SW:82–83,113,138–147,182 | none |
| W13 | the same denial but the tab is `requests` (e.g. machine-only actor) | `/m/lab/admin/requests?queue=pending` | `Navigate replace` to the default tab path **+ original search** (`/m/lab/admin/dashboard?queue=pending`) | SW:111–115 | none |
| W14 | unknown segment (not in `STAFF_TAB_KEYS`) | `/m/lab/admin/nope` | `Navigate replace` to the stored tab if allowed, else the default tab (`+ search`) | SW:82–89,113–114 | none |
| W15 | any allowed tab | `/m/lab/admin/inventory?id=4&ordering=-name` | query string survives canonicalisation (`activeTabPath + location.search`); the hash is **not** preserved | SW:114 | none |
| W16 | legacy alias | `/admin/printing` and `/m/f/admin/printing/12-laser` | resolve to `machines` and canonicalise to `/…/machines` and `/…/machines/12-laser` | TABS:243–244,200–202 | `[main] staffTabs.test.ts:14–17` (parse); canonical redirect: none |
| W17 | machines deep link | `/admin/machines/12-laser` | subpath kept through canonicalisation; any other tab drops trailing segments (`/admin/inventory/x` → `/admin/inventory`) | TABS:143,146–159,200–202; SW:95–102 | `[main] staffTabs.test.ts:98–132` (pure fn); SW render: none (SW:90–94 comment says so) |
| W18 | machine subpath on a **denied/other** resolved tab | `/admin/machines/12` for an actor without machines | the subpath is not carried to the fallback tab | TABS:200–202 | `[main] staffTabs.test.ts:129–131` |
| W19 | slug-scoped central console | nav link to `organizations` / `platform-dashboard` | href is `/admin/<tab>` (no `/m/<slug>`); every other tab is `/m/<slug>/admin/<path>` | TABS:144,155–158 | `[main] organizationGovernanceTab.test.ts:12` |
| W20 | superadmin, `platform-dashboard`, selected null | renders | workspace without activeMakerspace: no `CommandPalette`, no `JobTray`, no unread fetch; nav links are unscoped `/admin/<tab>` | SW:134,136; SD:70–73 | none |
| W21 | staff member of A and B; stored selected=A | first load at `/m/b/admin/inventory` | `hydrateUser` picks the route membership → selected=B and persisted | USS:57–71 | none |
| W22 | selected A | switcher → B | `persistSelectedMakerspace(B)` + `navigate(staffTabPath(currentTab, guestOnly, B.slug))`: tab kept, **subpath and query dropped**; if the tab is denied in B → W12 | USS:151–167 | none |
| W23 | route `guestOnly` (`/guest-admin`) | switcher → B | selection changes, **no navigation** | USS:160–166 | none |
| W24 | single-tenant locked | switcher action | `chooseMakerspace` is a no-op; selected forced to `tenant.makerspaceId` | USS:45,59–61,152 | none |
| W25 | central, unknown slug `/m/ghost/admin/x` | renders | canonical redirect to the **selected** space's slug path | SW:100–102,113 | none |
| W26 | bare `/m/lab/admin` | stored tab `"tobuy"` allowed | goes to `/m/lab/admin/to-buy`; stored legacy `"printing"` maps to machines; a stored tab not allowed → default | TABS:121–123,243–249; SW:84–89 | none |
| W27 | nav item clicked | — | `setTab(tab)` is called, so `persistStaffTab` stores it for W26; auth expiry clears it (`setTab("")`) | SDP:97–100; USS:50–52,84 | `[main] StaffDock.test.tsx:104–115` |
| W28 | `notifications` ∈ moduleAllowedTabs **and** activeMakerspace | shell renders | **exactly one** `GET /notifications/inbox/<id>/unread-count`, key `inboxUnreadKey(id)` = `["notifications-unread", id, "staff", recipient]` (shared with `PersonalInbox`, so mark-read updates the badge), 60 s refetch, `retry:false`, error → 0 | useUnreadNotifications.ts:6–19; personalQueryKeys.ts | `[main] StaffDock.test.tsx:125–134` |
| W29 | `notifications` absent, or no activeMakerspace | — | no unread request at all | SD:70–73 | `[main] StaffDock.test.tsx:136–145` |
| W30 | unread = N > 0 | — | N appears in the accessible name of the nav element that owns Notifications (today "Operate, 3 unread"); the visible badge shows `99+` above 99 and is `aria-hidden`; the Notifications link also shows the count | SD:20,167–169,208–212; SDP:104–108 | `[main] StaffDock.test.tsx:147–153` |
| W31 | mobile (<1024 px), drawer closed | — | the unread count is still exposed (menu-button accessible name, e.g. "Open navigation, 3 unread") **without a second fetch**. The query must live in the always-mounted shell, not inside the drawer, because PLAN §5 unmounts collapsed content | PLAN §3.4/§5; SD:70 | new |
| W32 | any shell | Tab from page top | first stop is "Skip to main content" → `#main-content`, which carries `tabIndex={-1}`. The nav sits **outside** `<main>` (today it is nested in `<main>`, SW:118,180: fix that, keep the id) | SW:119,135; SkipLink.tsx | e2e `a11y.spec` (axe) only |
| W33 | activeMakerspace | shell renders | `CommandPalette` mounted with `key={activeMakerspace.id}`; trigger accessible name contains "Search and commands"; **Ctrl/⌘K works on every viewport, drawer open or closed**, so the keydown listener (CP:41–52) must stay in an always-mounted component even if the trigger moves into the sidebar | SW:134; CP:41–63 | `[main] CommandPalette.test.tsx:33–53` |
| W34 | a dialog is open | Ctrl/⌘K | palette does not open over it | CP:46 | none |
| W35 | palette | search hits for tabs not in moduleAllowedTabs | hidden; quick-create filtered by `quickCreateCommands(actions, allowedTabs, isSuperadmin)` | CP:31–34 | `[main] CommandPalette.test.tsx:22–32,55–68` |
| W36 | activeMakerspace | any tab | `JobTray` rendered first in main | SW:136 | `[main] JobTray.test.tsx` (component) |
| W37 | `manage_makerspace` and activeTab `dashboard` | — | `SetupChecklist` keyed `${username}:${id}` above the content. (Quirk to pin: it also shows when a denied route fell back to dashboard, SW:137 does not check `routeTabDenied`) | SW:137 | `[main] SetupChecklist.test.tsx` (component) |
| W38 | any | — | `StaffListContext.Provider` (ownerName, canShare=`canManageMakerspace`, actions, isSuperadmin) wraps **all** tab content (Queues `can()`, SavedViewsMenu read it) | SW:118; RequestQueues.tsx:78–79 | indirect |
| W39 | tab not global and no activeMakerspace | — | `Panel "No makerspace"` | STC:75–77 | none |
| W40 | central | header / switcher | a "View public page" link to `/m/<slug>` (`/` when single-tenant) only when activeMakerspace exists | SH:31–33,68–72 | none |
| W41 | any signed-in shell | — | a **button** named "Sign out" calls `signOut` (logout, wipe offline scopes, clear selection, `queryClient.clear()`) | SH:79–81; USS:193–199 | e2e `helpers.ts:101` (visibility) |
| W42 | any | — | exactly **one `<h1>`** per page. Today it is the makerspace name in the header (SH:44–46). In the new shell, `PageHeader` owns the h1 and panels keep their `<h2>` (`Panel`, panels/shared.tsx:111–122). A tab must never render two headings with the same accessible name (see §2 a11y.spec) | SH:44; shared.tsx:115 | e2e `a11y.spec.ts:75–91` |
| W43 | route change while a nav popover/drawer is open | navigation completes | the popover/drawer closes; focus goes to the owning control or `#main-content`, never to `<body>` | SD:75–88 | `[main] StaffDock.test.tsx:88–102` (Escape) |
| W44 | responsive behaviour | jsdom tests | no unguarded `window.matchMedia` (jsdom has none; `[main] src/test/setup.ts` stubs nothing). Use Tailwind breakpoints for sidebar/drawer visibility | theme.ts:11 uses `?.` | — |
| W45 | `/guest-admin/<tab>`, central, activeMakerspace set | renders | **current behaviour, pin and don't fix in the shell PR**: `staffTabPath` prefers the slug over `guestOnly` (TABS:155–157), so SW canonicalises `/guest-admin/requests` → `/m/<slug>/admin/requests`. Single-tenant keeps `/guest-admin/...` | TABS:155–158; SW:100–114 | none, flag to owner |

---

## 2. Test plan

### 2.1 New workspace-level tests (render real `StaffWorkspace`/`StaffApp` + real `staffAccess`/`staffTabs`)

Harness `[main] frontend/src/features/staff/StaffWorkspace.routing.test.tsx` (≤300 lines; split
`StaffWorkspace.nav.test.tsx` if it grows):
- `MemoryRouter initialEntries=[url]` + `Routes` with `/admin/*`, `/m/:slug/admin/*`, `/guest-admin/*` rendering
  `StaffWorkspace`, plus a `<LocationProbe>` that prints `pathname+search`.
- `vi.mock("../../lib/api", () => ({ staffRequest }))`. `staffRequest.mockImplementation(path => path.endsWith("/unread-count") ? {count:N} : {count:0,results:[]})`.
- `vi.mock("./StaffTabContent", () => ({ StaffTabContent: (p) => <p data-testid="tab">{p.activeTab}|{String(p.guestOnly)}</p> }))`
  so panel traffic stays out (and so W11 is assertable). Also stub `JobTray`/`SetupChecklist` to markers.
- Fixtures: `space(id, slug, {enabled_modules, enabled_features})`, `user(makerspaces)`, plus actor presets: `manager`
  (Space Manager set), `machineOnly` (`["manage_machines"]`, isMachineOnly), `handout`, `collectOnly`,
  `governance` (`[]`), `superadmin`.

Assert, one `it` per row: W1–W5, W10–W20, W25–W30, W32–W33 (trigger present, `key` remount on space
change), W37–W39, W42, W45. Concretely:
1. **Home visibility**: manager sees a link to `/m/lab/admin/dashboard`. Handout and collectOnly do not. `testid=tab` shows `handover` for collectOnly at `/m/lab/admin`.
2. **Denied vs unknown vs requests**: `/m/lab/admin/qr-tools` for `["view_inventory"]` keeps the URL and shows the "Access denied" heading, with `link "Go to Dashboard"` href `/m/lab/admin/dashboard`, and `queryAllByRole("link", {current:"page"})` empty. `/m/lab/admin/nope?x=1` gives probe `/m/lab/admin/dashboard?x=1`. `/m/lab/admin/requests?queue=pending` for machineOnly gives probe `/m/lab/admin/dashboard?queue=pending`.
3. **Module-off denial**: manager + events module off at `/m/lab/admin/events` gives "Access denied".
4. **Alias + subpath**: `/m/lab/admin/printing/12-laser` gives probe `/m/lab/admin/machines/12-laser`. `/m/lab/admin/inventory/zzz` gives `/m/lab/admin/inventory`.
5. **Global**: superadmin, no activeMakerspace, `/admin/platform-dashboard`: no palette trigger, no unread call, nav `Organizations` href `/admin/organizations`.
6. **Single tenant**: `singleTenantLocked` + manager: no switcher, no "Switch makerspace", no `Organizations` link, public link href `/`. Nav hrefs are `/admin/<path>`.
7. **Stored tab**: `localStorage[STAFF_ACTIVE_TAB_KEY]="tobuy"` + `procurement` on, at `/m/lab/admin`, gives `/m/lab/admin/to-buy`. With `"printing"` it gives `/machines`. With a disallowed value it gives `/dashboard`.
8. **Unread**: one call to `/notifications/inbox/7/unread-count`. The owner element's name contains "3 unread". None without the `notifications` module.
9. **Landmarks/a11y**: `navigation "Staff sections"` is not inside `main`. `#main-content` has `tabindex=-1`. Exactly one `heading level 1`. `expectNoA11yViolations`.
10. **Handout narrowing**: handout at `/m/lab/admin/requests` gives `testid=tab` = `requests|true`.

`[main] StaffApp.shell.test.tsx` (extends the `StaffApp.platform.test.tsx` pattern: mock `useStaffSession`, keep the
**real** `StaffWorkspace`, stub `StaffTabContent`): S7–S12, W8 (click "Switch makerspace" calls `chooseMakerspace(null)`),
W21–W24 (assert `chooseMakerspace` args and the "Opening makerspace..." state), W41.

### 2.2 Existing tests that pin old shell DOM, and the change each needs

| Test | What it pins today | Required change |
|---|---|---|
| `[main] StaffDock.test.tsx` (8 cases) | landmark name; group **buttons** + popover **links**; `aria-expanded`; Escape returns focus to the group button; `aria-current="page"` only on the active row; one unread fetch; no fetch without permission; "Operate, 3 unread" button name | Becomes `Sidebar.test.tsx` with equivalent pins: (1) `navigation "Staff sections"` renders only groups holding permitted tabs (the `queryByRole(... "Operate")` absences carry over as section names). (2) The section holding the active tab is expanded; others collapsed, with their links **unmounted**, and the toggle carries `aria-expanded`. (3) Expanding another section works (decide whether it is single-open or multi-open; the dock was single-open). (4) Escape on a mobile drawer closes it and restores focus to the menu button. (5) Only the active link has `aria-current="page"`; `activeTab=""` gives none. (6)/(7) unread-fetch cases unchanged. (8) The owner element's accessible name = `"<Section>, 3 unread"` and the Notifications link text contains `3`. Delete `useDockAnchor`/`StaffDockPopover` with it |
| `[main] CommandPalette.test.tsx` | trigger `button /Search and commands/`; Ctrl/⌘K; listbox nav; navigation targets | **No change** if `CommandPalette` keeps trigger + listener. If the trigger is split out for the sidebar, keep the accessible name, keep the listener in an always-mounted component (W33), and add one case: "Ctrl+K opens while mobile drawer closed" |
| `[main] ThemeToggle.test.tsx` (5 cases) | button names "Switch to light/dark mode", "Light"/"Dark"; OS-follow; no write until click; cross-tab | **No change** if `ThemeToggle` stays as-is for public pages (14 importers) and the user menu gets a new `ThemePreference` control (§6). Add `ThemePreference.test.tsx` |
| `[main] e2e/helpers.ts:92–102` `staffLogin` | `/sign out/i` **button visible** after login | If "Sign out" moves into a user menu: wait on `getByRole("navigation", { name: "Staff sections" })` (visible at the 1280 px "Desktop Chrome" viewport, `playwright.config.ts`) instead. Keep "Sign out" a `button` inside a **disclosure** (not `role=menu`, which would make it `menuitem`) |
| `[main] e2e/helpers.ts:104–107` `openRequestsTab` | waits for text "Pending review" | Wait for `getByRole("tab", { name: /Pending/, selected: true })` (or keep "Pending review" as the tabpanel heading; pick one) |
| `[main] e2e/a11y.spec.ts:75–91` | `getByRole("heading", { name: <tab title>, exact: true })` for 7 panels | Playwright strict mode **fails on 2 matches**. If `PageHeader` h1 repeats the panel `h2` title, use `{ level: 1 }` and drop the duplicate `Panel` title. Add a 375 px project/test for the drawer shell (light+dark) |
| `[main] e2e/auth.spec.ts:16–20` | `getByText(makerspaceName).first()` visible | Still holds if the switcher card shows the name at ≥1024 px. Add an assertion on the landmark |
| `[main] e2e/request-lifecycle.spec.ts:12–33` | pending row, then **same page** accepted row ("Assign + issue"), then `section` "Active loans" "Return" | Click tab "Ready for handover" after Accept, and tab "Active loans" after issue (or `goto ?queue=active`). Replace `locator("section").filter({hasText:"Active loans"})` with the `tabpanel` |
| `[main] e2e/hard-rules.spec.ts:13–15` | probe (accepted) row found on the default requests page | `goto(.../requests?queue=accepted)` or click "Ready for handover" first |
| `[main] e2e/offline-handover.spec.ts:124–126` | "Failed kiosk handovers" section reachable from `openRequestsTab` | No change if the recovery panel stays **outside** the tab panel (RequestsPanel.tsx:6), as §3 proposes |
| `[main] QueuesDrilldown.test.tsx:11–19` | `?queue=pending\|accepted` gives that heading, no "Active loans"/"History", **exactly one** queue request | Keep the "exactly one list request per selected tab" assertion (Q-N1). Extend `it.each` to `active`/`history`; heading text → tab/tabpanel names |
| `[main] StaffApp.platform.test.tsx` | mocks `StaffWorkspace` | unchanged |
| `[main] staffTabs*.test.ts`, `rbacF6`, `organizationGovernanceTab`, `devicesTab`, `memberCardsTab`, `organizationAnalyticsTab` | pure gating | unchanged (gating code is not modified, PLAN §5). They are the regression net for W1–W5 logic |
| `[main] DashboardPanel*.test.tsx` | one `mockResolvedValue` answers **every** request; panel rendered **without** `allowedTabs`/actions | New widgets must **fail closed** when `allowedTabs`/actions props are absent (§4 D0), or these tests start receiving the dashboard object as an audit/active-loans page |

---

## 3. Request queues URL contract

### 3.1 Current state (`panels/RequestQueues.tsx`)

1. URL state via `useUrlListState({ queue:"", id:"", search:"", ordering:"-created_at", pendingPage, acceptedPage, activePage, historyPage:"1", history:"false" })` (:81), plus implicit `columns`/`density` (useUrlListState.ts:17). Page keys accept only `^[1-9]\d{0,5}$` (:10). Default values are **deleted** from the URL (:27). `setFilter` resets **all** page keys (:25,33); `setPage` does not (:37). Updates push history entries (`setSearchParams`).
2. `queue` ∈ {`pending`,`accepted`}; anything else reads as "" (all queues) (:82). `history=true` reveals History, and only when `queue` is empty (:83,128,217).
3. Lists, each `usePaginatedQuery` with a shared `id`, `ordering` and debounced `search` (usePaginatedQuery.ts:61, fixed page size 24):
   - Pending `/admin/makerspace/<id>/pending-requests`, key `["pending",id]`, enabled `!guestOnly && (!queue||queue==="pending")` (:88–98).
   - Ready `/accepted-requests`, key `["accepted",id]`, enabled `!queue||queue==="accepted"` (:99–109).
   - Active `/active-loans`, key `["active",id]`, enabled `!queue` (:110–120). **Rendered only when `!guestOnly`** (:210).
   - History `/request-history`, key `["request-history",id]`, enabled `showHistory && !queue` (:121–131). Rendered for guestOnly too (:217).
4. `guestOnly` here = `guestOnly || handoutOnly` (SW:152). Narrow view = Ready + History only.
5. Row actions: Pending `Accept`/`Reject`/`Set due` (QueuesDisplay.tsx:6). Ready `Assign + issue`/`Set due` (:10) + `Guided issue` if `issue_request && assign_box && upload_evidence` (RequestQueues.tsx:206). Active `Set due`/`Return` (QueuesDisplay.tsx:14) + `Guided return` if `return_request && upload_evidence`, + `StaffLoanRenew` if `loans.renewals` (RequestQueues.tsx:212). History has no actions. `View timeline` if `canViewAudit` (QueuesList.tsx:44).
6. Shared controls: "Show all request queues" (when queue set, :195), `ListViewControls` sort (Newest/Oldest/Due first) + SavedViews for entity `requests` (:196), "Search requests" field (:197).
7. Mutations: one `useMutation` POSTing `/admin/requests/<pk>/{accept,reject,assign-box,issue,return-due,return}`. `onSuccess` → `invalidateRequestQueues` invalidates `["pending",id]`, `["accepted",id]`, `["active",id]`, `["request-history",id]` always, plus inventory views (accept/issue/return), `["needs-fix-shelf",id]` (issue/return) and `["ledger",id]`/`["ledger","all"]` (issue/return/return-due) (QueuesInvalidation.ts:10–33). The wizards and dialogs call a global `invalidateQueries()` (handover/HandoverWizard.tsx:50–51, IssueDialog.tsx:40, ReturnDialog.tsx:63). Renew invalidates `["active",id]` (StaffLoanRenew.tsx:12).
8. `KioskReplayRecoveryPanel` ("Failed kiosk handovers") renders **below** the queues whenever `canSeeHardware` (RequestsPanel.tsx:6).
9. Inbound deep links: dashboard tiles `?queue=pending` / `?queue=accepted` (dashboardLinks.ts:8–9). Staff search hits `?id=<pk>&history=true` (backend/apps/admin_api/search.py:70). Saved views restore any of the defaults keys (useUrlListState.ts:39).
10. Backend authority: Pending requires `ACCEPT_REQUEST` on the space + `request_workflow` (queue_views.py:63–81). Ready, Active and History require `ISSUE_REQUEST` + `request_workflow` (:92–179; view_helpers.py:58–61). Today the frontend fetches Pending for any non-guest and Ready/Active for any `canSeeHardware` actor, so an accept-only reviewer gets 403/404 panels.
11. Live hints don't refresh `["pending"|"accepted"|"active",id]` keys (live.ts:30 hints don't occur in those keys). Only `request-history` matches. Existing gap: preserve it, don't widen it.

### 3.2 Proposed mapping (tabs Pending / Ready for handover / Active loans / History)

Keep the URL param name **`queue`** as the tab key and extend its domain:
`queue ∈ {pending, accepted, active, history}`. The tab label "Ready for handover" maps to `accepted`, so dashboard links
need no change. Keep `history` in the `useUrlListState` defaults (read-only legacy) so old saved views restore.
Keep all four page keys, so each tab keeps its own page and legacy URLs carrying them still work.

Resolution order (pure function `resolveRequestTab(values, visibleTabs) → tab | "resolve-id"`, unit-testable):

| # | Incoming URL (legacy or new) | Resolved tab |
|---|---|---|
| R1 | `queue=<t>` with `t` visible to the actor | `t` |
| R2 | `queue=<t>` with `t` hidden (e.g. handout + `pending`/`active`) or unknown | first visible tab (R7) |
| R3 | no `queue`, `id=N` (incl. search-hit `id=N&history=true`) | **resolve-id**: fetch the visible lists with `&id=N` (each is id-filtered, so cheap) and select the first non-empty in order pending → accepted → active → history. While resolving show `role=status` "Finding request #N…". If none, use the History tab with the empty state "Request #N isn't in a queue you can see." `history=true` must **not** short-circuit this: a search hit for an active loan would otherwise land on History and show nothing |
| R4 | no `queue`, no `id`, `history=true` | `history` |
| R5 | no `queue`/`id`/`history`, exactly one non-default `<x>Page` key | the tab owning that page key (legacy all-queues pagination link) |
| R6 | nothing | first visible tab (R7) |
| R7 | default order | `pending` if visible, else `accepted` |

Write side: clicking a tab sets `queue=<t>` and deletes `history` (canonical form). Pages reset as today (`setFilter`
semantics); search/ordering/id are kept. Legacy URLs are **not** rewritten (no redirect, which avoids
`Navigate` loops with SW canonicalisation). They only resolve. "Show all request queues" is removed.

Visibility (decision needed: **(a) parity** or **(b) tightened**, recommend (b)):
- (a) parity: hidden for `guestOnly||handoutOnly` = {pending, active}. Otherwise all four.
- (b) tightened to mirror backend 3.1#10: pending ⇔ `isSuperadmin || actions.includes("accept_request")`, and {accepted, active, history} ⇔ `… "issue_request"`. AND (a)'s handout rule. This only hides tabs that 403/404 today, but it is a visible behaviour change, so the owner should approve it.

### 3.3 Acceptance cases

- **Q1** `/m/lab/admin/requests` (manager) shows the Pending tab selected, and only `pending-requests?…` is requested.
- **Q2** `?queue=pending` and `?queue=accepted` (dashboard tiles) select Pending and Ready, one list request each. Pinned by `QueuesDrilldown.test.tsx`.
- **Q3** `?queue=active` and `?queue=history` select their tab. Each issues exactly one list request (history to `/request-history`).
- **Q4** `?history=true` selects History.
- **Q5** `?id=42&history=true`, where 42 is an active loan: selects Active loans and shows row #42. Where 42 is rejected: selects History.
- **Q6** `?id=999` with no match: History tab plus the "isn't in a queue you can see" message. No crash, and no infinite refetch.
- **Q7** Handout actor at `?queue=pending` or `?queue=active`: selects Ready. Never requests pending-requests or active-loans. The tab list is exactly [Ready for handover, History].
- **Q8** `?queue=bogus`: default tab.
- **Q9** `?activePage=3` alone: Active tab, page 3.
- **Q10** On Pending page 2, clicking Ready writes `?queue=accepted`, resets page keys, and keeps `search` and `ordering`. Browser Back restores Pending page 2.
- **Q11** Search typed on one tab persists across tab switches and filters the newly selected list.
- **Q12** Accept on Pending removes the row from Pending, and Ready's count/list is fresh when opened (invalidation keys unchanged, 3.1#7). Assign + issue: Active fresh, plus inventory/ledger/needs-fix invalidated as today.
- **Q13** "Failed kiosk handovers" visible under every tab.
- **Q14** Guided issue/return and Renew buttons appear under exactly the conditions in 3.1#5.
- **Q15** Saved view "requests" stored with `{queue:"",history:"true"}` restores to the History tab.
- **Q16** Tabs are `role=tablist`/`tab` (`aria-selected`, `aria-controls`, roving arrow keys), and the panel is `role=tabpanel` labelled by its tab. axe clean.
- **Q-N1** Network: never more list requests than the one selected tab (plus R3's id-filtered probes). No per-tab count badges, unless they come from data already fetched.

---

## 4. Dashboard data

**Today** `DashboardPanel` makes one call: `GET /admin/makerspace/<id>/dashboard`, key `["dashboard",id]`
(DashboardPanel.tsx:103–106). Server gate (`operations/views_dashboard_api.py:26–96`): it refuses handout-only
actors (:39–40,99–100) and requires one of view_inventory, manage_printing, manage_makerspace, manage_events,
manage_bookings, manage_members, manage_machines or view_finance (:41–51). Counters are narrowed by machine scope and
`machine_only` (:52–69; `dashboard_counts.py:41–70`). Tiles are filtered client-side by module, `allowedTabs` and
per-tile rules (DashboardPanel.tsx:113–121). It receives `allowedTabs` but **not `actions`/`isSuperadmin`**
(STC:89–91). Widgets that mirror action gates need those props added from STC (`actorActions`, STC:79).

**D0 (all widgets):** each widget is its own component, mounted only when its gate passes, and **hidden when
`allowedTabs` or `actions` is undefined** (fail closed, so the existing `DashboardPanel*.test.tsx`, which pass neither,
stay green and make no extra calls). Every "See all →" link uses `staffTabPath(tab, guestOnly, slug, singleTenantLocked)`.

| Widget | Endpoint (exists?) | Backend authority | Exact frontend gate to mirror | Hook today | Verdict |
|---|---|---|---|---|---|
| **Recent activity rail** | `GET /admin/audit-logs?makerspace=<id>` (`admin_api/urls_staff.py:51`; `views_users.py:228–246`), page size 24, `-created_at` | `scope_by_action(VIEW_AUDIT)` + `hide_from_superadmin` + archived spaces excluded. No module gate, no machine-scope narrowing (an actor holding view_audit already sees all of this on the Audit tab) | `moduleAllowedTabs.includes("audit")` (≡ `canViewAudit`, ACC:90,139; audit has no TAB_MODULES entry) **and** activeMakerspace | none exported. `AuditLog.tsx:37` uses `useStaffGet(["audit", query], …)`, so reuse it with `["audit", "makerspace=<id>"]`. Any key containing "audit" is invalidated on **every** live event (live.ts:46), so the rail stays current for free | **Available.** Render `actor_display` + `action_label` + `created_at` (relative) + `target_link` only. **Never `meta`** (use `meta_redacted` if anything) (`serializers_audit.py:24–38`). Show the first 5–8 rows |
| Activity (fallback for non-audit staff) | `GET /notifications/inbox/<id>?page=1` (`views_inbox.py:40–56`) | `IsAuthenticated` + `personal_space` + `scope_personal_notifications` (personal rows only) | `moduleAllowedTabs.includes("notifications")` (module `notifications`, ACC:125) | inline in `PersonalInbox.tsx:28`, key `["notifications-inbox", id, "staff", recipient, page, unread, feature]`. Reuse that **prefix** so mark-read invalidation stays coherent | Available (optional) |
| **Due back soon / overdue** (reviewed loans) | `GET /admin/makerspace/<id>/active-loans?page=1&ordering=return_due_at` (`queue_views.py:121–150`; `return_due_at` ∈ ordering_fields :125; PG ASC puts NULLs last, so undated loans trail) | `CanViewHandoverQueue` (active + ISSUE_REQUEST somewhere, `permissions.py:28–38`) + `ISSUE_REQUEST` on this space + `request_workflow` (:128–131). `scope_by_action(ISSUE_REQUEST)`. Not machine-scoped | `(isSuperadmin \|\| actions.includes("issue_request")) && moduleAllowedTabs.includes("requests")` (the latter adds `canSeeHardware` + `loans.enabled`). **`canSeeHardware` alone is insufficient**: an accept-only reviewer would 403 | `usePaginatedQuery({ key:["active", id], path, ordering:"return_due_at", page:1 })`. Same prefix as `invalidateRequestQueues` (QueuesInvalidation.ts:20) and `StaffLoanRenew` (:12), so issue/return/renew refresh it. Not live-refreshed (3.1#11) | **Available.** Split client-side into *Overdue* (`due < now`) and *Due within N days* (propose N=3), max 5 each, "See all →" to `requests?queue=active&ordering=return_due_at`. **Do not** print a headline count from this list: the tile `overdue_loans` comes from a different authority (VIEW_INVENTORY/MANAGE_MAKERSPACE, `views_dashboard_api.py:73–74`) and includes direct handouts via `PublicToolLoan.due_at` (`dashboard_counts.py:79–94`) |
| Due back (direct handouts) | `GET /admin/makerspace/<id>/direct-loans` orders `-checked_out_at` only, no due ordering (`direct_loan_views.py:31–46`). Needs `ISSUE_DIRECT_LOAN` + feature `inventory.self_checkout` | — | — | key `["direct-loans", id]` (DirectLoans.tsx:93) | **Needs new param, defer.** Verify whether direct-handout `HardwareRequest`s carry `return_due_at`. If not, they appear undated in the reviewed list |
| **Coming up: events** | `GET /admin/makerspaces/<id>/events/?status=published&ordering=starts_at` (`events/views_admin_event_list.py:36–59`) | `_visible_makerspace`: MANAGE_EVENTS + `require_module("events")` (`views_admin_event_detail.py:58–71`), queryset `scope_by_action(MANAGE_EVENTS)` | `moduleAllowedTabs.includes("events")` (manage_events + events module) | `useEvents(id, page, query)` (`eventsApi.ts:47–52`) | **Partial, defer.** No `ends_after`/upcoming filter: published-but-past events sort first, so page 1 can be all past. The dashboard's own definition is `published & ends_at > now` (`dashboard_programmes.py:28–31`). Correct list needs a backend param, which is out of scope. Ship the existing tile counts instead |
| **Coming up: bookings** | none makerspace-wide. Only per-space `GET /admin/spaces/<pk>/bookings/` (`bookings/urls_admin.py`) | MANAGE_BOOKINGS | `moduleAllowedTabs.includes("bookings")` | `useSpaceBookings(spaceId, …)` (bookingsApi.ts:101) | **Needs new endpoint, defer** (N+1 per space is not acceptable) |

Dashboard acceptance cases:
- **D1** `["manage_bookings"]` actor: no rail, no due-back list, and no audit-logs or active-loans request is made.
- **D2** Actor with `view_audit`: rail shows ≤8 rows with no raw `meta`, and "See all →" goes to the Audit tab.
- **D3** `["accept_request","view_inventory"]` (no issue_request): no due-back widget and no active-loans call, even though the Overdue tile may show.
- **D4** Manager with `loans.enabled` off: no due-back widget.
- **D5** Returning a loan from Requests, then reopening Home: due-back list is fresh with no reload (shared `["active",id]` prefix).
- **D6** machine-only (`scope_mode:"machine"`): the existing tile rules hold, and the widgets follow their own action gates (none of the three hold for a pure machine role).
- **D7** Handout and collect-only actors never reach the dashboard (W2/W3).
- **D8** Existing `DashboardPanel*.test.tsx` stay unchanged and green.

---

## 5. DataTable (stacked mobile layout)

Users (5): `BookingsPanel.tsx:54` (listState, server ordering, skeleton 5), `panels/Categories.tsx:198`
(local sort, no listState), `panels/InventoryWorkspace.tsx:240` (listState, server ordering, **selection**,
empty-header `image`/`actions` columns :196,208), `panels/memberCards/CardsTable.tsx:109` (optional selection,
"Actions" column), `PaymentsPanel.tsx:204` (listState, **selection**, `className:"font-semibold"` column :96).

Features the stacked layout must keep (DataTable.tsx):
1. Server ordering: `ordering` + `onOrderingChange` → header button toggles `key` ↔ `-key`, rows **not** reordered locally, `aria-sort` on the sorted header (:38,55,59–61,95).
2. Local sort for unpaginated users when `ordering` is undefined (:54–57,62–65; null-first asc, numeric-aware compare :154–161).
3. Column visibility + density from `listState` (`columns` CSV, `density` comfortable/compact → `py-2`/`py-1`), with a fallback to all columns when the saved set matches none (:45–48). The `ListColumns` control (:82) keeps a last column that can't be turned off (ListColumns.tsx:15).
4. Selection: per-row checkbox `Select row <id>`, header `Select all rows` with `indeterminate` (:44,50–52,88,124). **Select-all toggles only visible ids and preserves ids selected on other pages** (:72–76): that is the cross-page contract at component level. Inventory and Payments clear selection on `list.query` change, which includes the page (InventoryWorkspace.tsx:86, PaymentsPanel.tsx:52), so their effective behaviour is page-scoped. Keep both.
5. Loading: `skeletonCols` gives `SkeletonRows` (col count follows visible columns when listState is set), otherwise a spinner row; `aria-busy` (:83,109–116).
6. Empty: when not loading and data is empty, `EmptyState` (title/description/action) replaces the whole table, including `ListColumns` (:78).
7. Row identity `getRowId` (default `row.id`) (:142–144); `render` cells, `className` per column.

Implementation constraint: **one DOM, CSS-only reflow**. Rendering both a table and a card list duplicates every
cell, checkbox label ("Select row 41", `PaymentsPanel.test.tsx:104`) and text (breaks `getBy*`, axe
duplicate-label and Playwright strict mode). jsdom has no `matchMedia`, so don't switch layout in JS. When table
elements get `display:block/grid` under `md`, add explicit ARIA roles (`table`/`rowgroup`/`row`/`columnheader`/`cell`),
because Chromium/WebKit can drop table semantics on display change. Each stacked cell shows its header text as a
visible, `aria-hidden` label (screen readers keep the header association through the roles). Columns whose header
is empty (`image`, `actions`) render without a label, and actions stay last and full-width with 44 px targets.

Acceptance cases:
- **T1** At 375 px, no horizontal page scroll. Today `min-w-[640px]` (:83) forces scroll, so it must apply only at ≥md.
- **T2** At 375 px a sortable table still exposes its sort: either the thead stays visible as a compact sort bar, or a "Sort by" select shows the same options. Activating it calls `onOrderingChange("-name")` with row order unchanged (mirrors `DataTable.test.tsx:9–17`).
- **T3** Local-sort users (Categories) still reorder rows.
- **T4** Hidden columns (ListColumns) are absent from the stacked cards too. Compact density reduces card padding.
- **T5** Selection: `Select all rows` is reachable and indeterminate in stacked mode. Selecting on page 1, paging, then select-all on page 2 keeps page-1 ids at component level (new unit test).
- **T6** Empty and loading states render identically at every width.
- **T7** Existing `DataTable.test.tsx`, `ListColumns.test.tsx` and `PaymentsPanel.test.tsx:104` pass unchanged. Every role query (`cell`, `columnheader`, `checkbox`) still finds exactly one element per cell.
- **T8** axe clean in both layouts. Existing bug to fix while here: ListColumns renders **unnamed checkboxes** for empty-header columns (InventoryWorkspace `image`/`actions`); give them a fallback name (the column key) or exclude them from the picker.

---

## 6. Theme toggle

Today (`lib/theme.ts`):
1. Two values only, `Theme = "light"|"dark"` (:3), stored under `makerspace.theme` (:4).
2. Resolution order is session choice, then valid stored value, then OS `prefers-color-scheme` (:7–12). An invalid stored value counts as "system" (`[main] ThemeToggle.test.tsx:51–58`).
3. **OS-follow while unset**: `initializeTheme()` (called pre-render, `main.tsx:18`) listens to the media query and re-applies, and never writes storage (:18–24; test :23–33). An explicit choice wins over OS changes (test :34–41).
4. Cross-tab: a `storage` event for the key (or `null` = clear) resets the session choice and re-applies (:25–31).
5. `chooseTheme` writes storage + a session fallback for blocked storage (:38–43). **There is no way back to "system" once chosen.**
6. The UI reads the resolved class via `MutationObserver` (:45–53). `ThemeToggle` is binary (text "Light"/"Dark" or icon "Switch to light/dark mode") and has 14 importers on public pages, the picker and access-denied (`components/ThemeToggle.tsx`).

**Option A, keep the toggle** (minimum): put the existing `<ThemeToggle />` in the user disclosure. No `theme.ts` change, all tests unchanged.

**Option B, add "System"** (minimal diff, ~15 lines in theme.ts):
- `export type ThemePreference = Theme | "system"`. `sessionChoice: ThemePreference | undefined`. In `preferredTheme`, `"system"` → OS.
- `chooseTheme(pref)`: on `"system"`, `removeStorage(THEME_KEY)` (`safeStorage.ts:17`) and set `sessionChoice="system"` (so blocked storage still follows the OS), then `applyTheme()`. Other tabs get the existing `storage` event with `newValue=null`, which already resets them (:26).
- `currentPreference()` returns `sessionChoice ?? valid stored ?? "system"`. Add `subscribePreference` (a listener `Set` notified by `chooseTheme` and the storage handler). The class observer **cannot** detect dark→system when the OS is also dark, because the class doesn't change.
- A new `ThemePreference` control (radio group "Theme": Light / Dark / System) for the user menu. `ThemeToggle` stays as-is for public pages, still writing explicit values.
- New tests: initial "System" checked with no key; choosing System removes the key and then follows an OS change; System propagates cross-tab; with storage blocked, System still follows the OS. The existing 5 ThemeToggle cases stay green.

---

## Summary

The shell invariants come down to 12 StaffApp gates (S1–S12) and 45 workspace cases (W1–W45). All gating stays in
`staffAccess`/`staffTabs`/StaffWorkspace canonicalisation. The shell only renders `moduleAllowedTabs`.
Almost none of it is pinned at render level today: only pure-function tests, `StaffDock.test`,
`StaffApp.platform.test` and `CommandPalette.test`. Two new harnesses close that gap:
`StaffWorkspace.routing.test.tsx` (real gating, stubbed tab content, location probe) and `StaffApp.shell.test.tsx`.

Traps the shell PR could hit:
- The Ctrl/⌘K listener and the unread query must stay mounted while the mobile drawer is closed.
- "Sign out" must stay a button. `staffLogin` waits on it being visible.
- `a11y.spec` exact-heading queries break if `PageHeader` duplicates panel titles.
- `/guest-admin` currently canonicalises into `/m/<slug>/admin` (W45). Pin it and flag it; don't fix it in the shell PR.

Request queues: keep the param `queue`, extended with `active`/`history`. Legacy `history=true`, `?id=` search hits
and per-tab page keys resolve deterministically. A search hit needs id-probe resolution (R3), or it lands on the
wrong tab. Fetch only the selected tab. Tightening tab visibility to mirror backend `accept_request`/`issue_request`
is recommended but is an owner decision.

Dashboard widgets:
- Activity rail: audit-logs, gated on the `audit` tab. Available.
- Due back: active-loans ordered `return_due_at`, gated on `issue_request` plus the `requests` tab. Available.
- Upcoming events: need a date filter. Defer.
- Upcoming bookings: need a makerspace-wide endpoint. Defer.

DataTable: one DOM with CSS reflow and explicit roles. It keeps sort, column/density settings and visible-only select-all.
Theme: "System" is a ~15-line `theme.ts` change plus a new control. The binary toggle stays.
