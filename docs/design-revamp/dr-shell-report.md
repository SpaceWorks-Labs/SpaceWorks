# dr-shell wave 2b verification report

Branch: `lane/dr-shell`. No staging, commits, merges or pushes.

## Implementation and accessibility decisions

`components/shell/` owns the shared staff/member shell. Navigation is outside `main`, with the existing skip target. Only logo/workspace/search and the user/status block are fixed; all navigation, including Settings and Platform, is in one independent scroll region. Presentation consumes the unchanged access/module selectors. Member destinations use URL navigation links with `aria-current="page"`, normal Tab navigation and a focusable `#main-content`, replacing the old tablist/roving-arrow contract. Member bodies are unchanged. The member tests now pin links, browser Back, gating and the skip target.

The superadmin picker stays outside the shell because S10 explicitly requires that boundary. Global routes have a no-workspace shell with a Choose a space switcher and only global destinations.

## Contract discrepancies and limitations

- **W14:** the baseline code treats an unknown nonempty segment as `requestedTab`, so it chooses the default tab even when a permitted stored tab exists. The routing expression is unchanged. The test explicitly pins this discrepancy rather than changing canonicalisation against the lane constraint. Bare routes still restore stored tabs (W26).
- **W36:** the old contract says JobTray is first in main. The explicit wave-2b request supersedes that placement: it is now a compact bottom-block pill. Its status pollers remain mounted, its dialog controls unmount when closed, and the dialog portals outside a mobile drawer’s inert layer.
- Browser geometry/contrast QA could not finish in this sandbox: installed Chromium fails its side-by-side startup; the headless shell reports fatal GPU context failures and closes its debugging socket. Both managed browser surfaces (iab/chrome) are unavailable. No actual scrolling/contrast pass is claimed; see verification below. The 1280×600 Sidebar unit test uses real getStaffAccess for the full-permission superadmin (40 permitted keys), keyboard-focusability and scrollIntoView calls. A separate map test covers all 42 presentation keys exactly once. The separate browser fixture uses the real superadmin selector (40 keys: organized and organization-analytics exclude superadmins) and checks actual Tab reachability, scroll geometry and axe at 1280×600 and mobile light/dark.
- The nested Codex CLI review gate could not run: `codex doctor` could not resolve configuration/home and could not reach the provider endpoint. No independent-review approval is claimed.

## Every shell case to test name

Paths below are under `frontend/src/features/staff/`. Additional sidebar pins are in `frontend/src/components/shell/Sidebar.test.tsx`.

| Case | File | Test name |
| --- | --- | --- |
| S1 | `StaffApp.shell.test.tsx` | S1 restoring wins before all other gates and shows no shell |
| S2 | `StaffApp.shell.test.tsx` | S2 MFA renders alone before login |
| S3 | `StaffApp.shell.test.tsx` | S3 signed-out users get Username/Password without shell |
| S4 | `StaffApp.shell.test.tsx` | S4 password-change gate invalidates protected makerspaces and clears must-change flag |
| S5 | `StaffApp.shell.test.tsx` | S5 superadmin quarantine wins before workspace loading |
| S6 | `StaffApp.shell.test.tsx` | S6 single-tenant loading checks access before entering shell |
| S7 | `StaffApp.shell.test.tsx` | S7 single-tenant missing workspace denies %s |
| S8 | `StaffApp.shell.test.tsx` | S8 opens route workspace until list and selection synchronize (%j) |
| S9 | `StaffApp.shell.test.tsx` | S9 restores selected workspace while list loads |
| S10 | `StaffApp.shell.test.tsx` | S10 picker remains outside shell for invalid selection %s |
| S11 | `StaffApp.shell.test.tsx` | S11 platform global route bypasses picker for selection %s |
| S12 | `StaffApp.shell.test.tsx` | S12 Organizations is global for superadmin=%s |
| W1 | `StaffWorkspace.nav.test.tsx` | W1 Home is shell copy while the palette retains Dashboard |
| W2 | `StaffWorkspace.nav.test.tsx` | W2 handout-only navigation is flat and limited to its five destinations |
| W3 | `StaffWorkspace.nav.test.tsx` | W3 collect-only lands on Job pickups with only Inbox beside it |
| W4 | `StaffWorkspace.nav.test.tsx` | W4 governance-only is global and has no palette or job tray |
| W5 | `StaffWorkspace.nav.test.tsx` | W5 single-tenant hides switching and cross-venue/platform tabs and uses public root |
| W6 | `StaffWorkspace.nav.test.tsx` | W6 W9 central switcher lists every makerspace, calls selection and excludes superadmin reset |
| W7 | `StaffWorkspace.nav.test.tsx` | W7 one makerspace is a static workspace card |
| W8 | `StaffApp.shell.test.tsx` | W8 Switch makerspace forwards null through chooseMakerspace |
| W9 | `StaffWorkspace.nav.test.tsx` | W6 W9 central switcher lists every makerspace, calls selection and excludes superadmin reset |
| W10 | `StaffWorkspace.nav.test.tsx` | W10 superadmin role wins over a local membership role |
| W11 | `StaffWorkspace.routing.test.tsx` | W11 narrows content for handout actors while path building keeps raw guestOnly |
| W11 | `StaffWorkspace.routing.test.tsx` | W11 raw guest route also narrows content |
| W12 | `StaffWorkspace.routing.test.tsx` | W12 preserves URL and renders denial without selected nav or content: %s |
| W13 | `StaffWorkspace.routing.test.tsx` | W13 denied Requests redirects with the original search |
| W14 | `StaffWorkspace.routing.test.tsx` | W14 baseline discrepancy: unknown route defaults even with stored %s |
| W15 | `StaffWorkspace.routing.test.tsx` | W15 canonicalisation preserves query and drops hash |
| W16 | `StaffWorkspace.routing.test.tsx` | W16 canonicalises printing alias %s |
| W17 | `StaffWorkspace.routing.test.tsx` | W17 preserves only machine subpaths: %s |
| W18 | `StaffWorkspace.routing.test.tsx` | W18 never carries denied machine subpaths onto the fallback |
| W19 | `StaffWorkspace.routing.test.tsx` | W19 global links stay unscoped and local links use the slug |
| W20 | `StaffWorkspace.nav.test.tsx` | W20 no-workspace global routes have only global links and no unread/search/jobs |
| W21 | `useStaffSession.shell.test.tsx` | W21 route membership overrides stored selection during hydrateUser |
| W22 | `useStaffSession.shell.test.tsx` | W22 switch persists B, keeps tab and drops machine subpath plus search |
| W23 | `useStaffSession.shell.test.tsx` | W23 guest switching changes selection without navigating |
| W24 | `useStaffSession.shell.test.tsx` | W24 locked tenant forces its makerspace and switching is a no-op |
| W25 | `StaffWorkspace.routing.test.tsx` | W25 unknown slug canonicalises to selected workspace |
| W26 | `StaffWorkspace.routing.test.tsx` | W26 bare workspace restores stored %s |
| W27 | `StaffWorkspace.nav.test.tsx` | W27 clicking navigation persists the tab through setTab |
| W27 | `useStaffSession.shell.test.tsx` | W27 setTab persists and auth expiry clears the remembered destination |
| W28 | `StaffWorkspace.nav.test.tsx` | W28 W30 W31 one shared unread query feeds Inbox and the closed-drawer trigger |
| W28 | `StaffWorkspace.nav.test.tsx` | W28 unread key and polling options are shared with PersonalInbox; cache updates refresh the badge |
| W28 | `StaffWorkspace.nav.test.tsx` | W28 unread failures show zero and are not retried |
| W29 | `StaffWorkspace.nav.test.tsx` | W29 does not fetch unread when space or module is absent (%s) |
| W30 | `StaffWorkspace.nav.test.tsx` | W28 W30 W31 one shared unread query feeds Inbox and the closed-drawer trigger |
| W30 | `StaffWorkspace.nav.test.tsx` | W30 large unread counts display 99+ while the accessible name retains the real count |
| W31 | `StaffWorkspace.nav.test.tsx` | W28 W30 W31 one shared unread query feeds Inbox and the closed-drawer trigger |
| W32 | `StaffWorkspace.nav.test.tsx` | W32 skip link is first and nav is outside the focusable main region |
| W33 | `StaffWorkspace.nav.test.tsx` | W33 Ctrl/Cmd K opens with the mobile drawer closed |
| W33 | `StaffWorkspace.nav.test.tsx` | W33 Ctrl K closes the navigation drawer before opening the palette |
| W34 | `StaffWorkspace.nav.test.tsx` | W34 palette does not open above another dialog |
| W35 | `StaffWorkspace.nav.test.tsx` | W35 palette omits forbidden hits and filters quick create |
| W36 | `StaffWorkspace.nav.test.tsx` | W36 job tray is in the sidebar bottom block (wave 2b overrides former first-in-main position) |
| W37 | `StaffWorkspace.routing.test.tsx` | W37 checklist stays above content even on a denied route falling back to dashboard |
| W38 | `StaffWorkspace.routing.test.tsx` | W38 all tab content receives the StaffListContext authority |
| W39 | `StaffTabContent.shell.test.tsx` | W39 a non-global tab with no active makerspace renders the real No makerspace panel |
| W40 | `StaffWorkspace.nav.test.tsx` | W40 public-page link exists only with an active space |
| W41 | `StaffApp.shell.test.tsx` | W41 user-menu Sign out forwards the real session signOut |
| W41 | `StaffWorkspace.nav.test.tsx` | W41 Sign out stays a button in the user disclosure and calls signOut |
| W41 | `useStaffSession.shell.test.tsx` | W41 signOut logs out, wipes offline scopes, clears selection and query cache |
| W42 | `StaffWorkspace.nav.test.tsx` | W42 shell supplies exactly one h1 without duplicating the panel title |
| W43 | `StaffWorkspace.nav.test.tsx` | W43 route navigation closes drawer and focuses main |
| W44 | `StaffWorkspace.nav.test.tsx` | W44 renders when matchMedia is absent |
| W45 | `StaffWorkspace.routing.test.tsx` | W45 pins guest-admin canonicalisation singleTenantLocked=%s |

## Additional tests

- `components/shell/Sidebar.test.tsx`: landmark, current page, labelled icons, unread name, Escape/focus restoration, unmounting disclosures, per-user expansion, active expansion, all-permitted-key 1280×600 keyboard/scroll contract, axe.
- `features/members/MemberPortalTabs.test.tsx`: same URLs and module gates, normal-link accessible contract, browser Back, invalid routes and mobile More/Escape.
- `components/ui/JobTray.test.tsx`: new pill case proves polling continues when closed and dialog controls unmount.
- Existing `CommandPalette.test.tsx` and `ThemeToggle.test.tsx` are unchanged and run with the full suite; the new workspace tests cover the relocated trigger, closed/open drawer shortcut and dialog guard.
- `e2e/helpers.ts`: staffLogin opens the visible user disclosure before waiting for the real Sign out button. Existing panel heading expectations remain valid because shell h1 titles include scope and do not duplicate panel h2 names. Queue e2e expectations stay unchanged because queue bodies were not restyled.
- `e2e/fixtures/staffShellHarness.tsx`: shared mocked-network test support; keeps real staffAccess/staffTabs and StaffWorkspace.
- `e2e/shell-fixture.html`, `e2e/fixtures/shellBrowser.tsx`, `e2e/shell-browser-check.mjs`: standalone browser geometry/contrast fixture (Vite on 127.0.0.1:5178; Chrome executable via SHELL_CHROME). These do not require or change the real backend.

## Deleted files

- `features/staff/StaffHeader.tsx`
- `features/staff/StaffDock.tsx`
- `features/staff/StaffDockPopover.tsx`
- `features/staff/useDockAnchor.ts`
- `features/staff/staffNavIcons.tsx`
- Ignored test `features/staff/StaffDock.test.tsx`, replaced by `components/shell/Sidebar.test.tsx`. No other test was deleted.

## Ignored-test handoff

Added: `StaffWorkspace.routing.test.tsx`, `StaffWorkspace.nav.test.tsx`, `StaffApp.shell.test.tsx`, `useStaffSession.shell.test.tsx`, `StaffTabContent.shell.test.tsx`, `components/shell/Sidebar.test.tsx`, and the e2e fixture/check/support files above.

Updated: `MemberPortalTabs.test.tsx`, `MemberArea.test.tsx`, `MemberAreaPortal.test.tsx`, `MemberAreaBranding.test.tsx`, `MemberAreaAdmission.test.tsx`, `JobTray.test.tsx`, `e2e/helpers.ts`, and local `vitest.config.ts` (four workers, retaining real test timeouts). Only member tests whose DOM queries used the former tab role were adjusted; business assertions were retained.

The exact local handoff hashes and deletion are recorded in `seeds/dr-shell-handoff.sha256`.

## Verification

- `npx tsc -b`: passed (Windows uses `npx.cmd`).
- `npx vitest run`: **271 files, 1,071 tests passed** (139.20 s).
- Focused current Sidebar suite: **6 passed**, including the real full-permission superadmin selector at 1280 x 600.
- `npm run build`: passed, including kiosk and member PWA verification.
- `git diff --check`: passed; the index is empty.
- All forbidden gating files and `components/layouts/` are unchanged. Every new shell source file is under 200 lines; MemberArea is 202 lines (below the hard ceiling).
- Chromium geometry/contrast check: **blocked by browser startup/GPU/CDP failures**, not reported green. The test/fixture is included for a working browser host. Full backend/browser e2e was not run; the requested mocked-network frontend suites were run in full.
- Nested CLI review: unavailable as described above. Local code/contract inspection completed; no independent-review approval is claimed.

Command logs are in the ignored `frontend/e2e/dr-shell-results/` directory.
