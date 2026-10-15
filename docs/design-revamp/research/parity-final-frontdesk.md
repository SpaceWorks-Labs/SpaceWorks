# Final parity audit: front desk

Read-only. **Old** = commit `d3e5ed29`. **New** = working tree at HEAD (`b348ee18`). Paths are relative to
`frontend/src/` unless stated. Earlier checklist: `parity-front-desk.md` (18 restore items, re-verified below).

**Summary: 134 capabilities with an old counterpart. PRESENT 91, BURIED 24, CHANGED 19, MISSING 0.**
**Earlier restore list: 16 of 18 verified fixed, 2 still open** (#6 reject-broken-units discoverability, #12 setup
checklist hidden when the dashboard query fails). **No P0. Two P1** (phone loses every visible unread/queue signal;
a handout-only role with no accept/issue authority lands on a "no access" page). No gate is looser than the old UI.
One gate is stricter (request queue tabs) and matches the backend, see G1.

Evidence: `cd frontend; npx vitest run` over `requestTabs`, `RequestQueues`, `RequestsPanel.callout`,
`DashboardPanel`, `DirectLoans`, `PaymentsPanel`, `Sidebar` all pass (49 tests).

---

## Gate audit (old to new)

| Gate | Result |
| --- | --- |
| `features/staff/staffAccess.ts`, `staffTabs.ts`, `paymentAccess.ts`, `paymentsApi.ts`, `setupChecklistState.ts`, `panels/dashboardLinks.ts`, `quickCreate.ts`, `QueuesInvalidation.ts`, `handover/types.ts` | Byte-identical to `d3e5ed29` (empty `git diff`). |
| `StaffTabContent.tsx` | Only adds `progress`, `allowedTabs`, `makerspaceName`, `inventoryTabAvailable`. Every tab condition (`requests`, `direct`, `handover`, `payments`, `notifications`, `dashboard`) is unchanged. |
| Dashboard tile predicates | `DashboardPanel.tsx:19-27` identical to old `DashboardPanel.tsx:113-121`. |
| Guided issue / return buttons | Same actions: `issue_request`+`assign_box`+`upload_evidence`; `return_request`+`upload_evidence` (`RequestQueues.tsx:158-164`). |
| Pending / Active hidden for handout-only | Unchanged (`requestTabs.ts:16`, old `RequestQueues.tsx:95,117`). |
| **G1 Request queue tabs: STRICTER** | `requestTabs.ts:9-17`: Pending needs `accept_request`; Ready, Active, History need `issue_request`. Old showed them to anyone with `canSeeHardware`. This mirrors `queue_views.py:72,101,130,166` (`_require_action`) and `permissions.py:28-38` (`CanViewHandoverQueue` = `ISSUE_REQUEST`), so the old tabs only ever 403'd for those roles. Documented in a code comment and `shell-contracts.md:161`. No UI capability is lost, but see P1-2. |
| Dashboard widgets (new) | Due back needs `issue_request` + `requests` tab (`DashboardPanel.tsx:62-64`); Recent activity needs the `audit` tab (`:65`). Tighter than anything old, no old counterpart. |

---

## Restore list (P0 to P2)

### P0

None. Every old front-desk capability is reachable on a page. No destructive action lost a confirmation
(old Reject needed a reason dialog, still does; old Waive, Revoke claim code and Delete saved view never had a confirm).

### P1

**P1-1. Phones lose every visible queue/unread signal.**
- Lost: the old dock showed a red unread count on the Operate group at the bottom of every screen
  (`StaffDock.tsx:208-212`). New: the hamburger only carries it in its `aria-label` (`components/shell/MobileTopBar.tsx:69`,
  `unread` is passed in but never drawn). The Requests pending+ready badge (`StaffShell.tsx:35-37`) and the Inbox badge
  (`StaffShell.tsx:34`) exist only inside the drawer. Non-handout staff on a phone have no bottom bar (`StaffShell.tsx:59`).
- Why: a desk phone is how new requests are noticed. Handout-only roles still get bottom tabs with visible numbers (`BottomTabs.tsx:11`).
- Fix: in `MobileTopBar.tsx`, draw a small count pill on the Menu button when `unread > 0` (data already in props);
  extend `AppShell.tsx:43` to also sum badges on `requests`.

**P1-2. Handout-only role without `accept_request`/`issue_request` lands on a "no access" page.**
- `getStaffAccess` lets `requests` through for `issue_direct_loan`, `return_request`, `assign_box` or `reject_request`
  (`staffAccess.ts:102,173`) and makes it the default tab for handout-only roles (`:201-202`). `visibleRequestTabs` then returns `[]`
  and the page says "You don't have access to request queues in this makerspace" (`RequestQueues.tsx:252-253`).
  A "direct handout desk" role (`view_inventory`, `issue_direct_loan`, `upload_evidence`, `record_payment`) therefore opens on a dead end
  while Direct handout is in the sidebar. Pre-existing (old: a 403 error panel), but the revamp made it a clean dead end.
- Fix: in `StaffShell.tsx` drop the `requests` nav item when `visibleRequestTabs(handoutOnly, actions, isSuperadmin)` is empty, and in `StaffWorkspace.tsx`
  choose the first tab that renders (Direct handout) as the default. Do not change `staffAccess.ts` (shared, pinned by tests).

### P2

1. **Setup checklist and quick-add disappear when the dashboard counts fail (earlier #12, open).** `progress` is rendered inside
   `QueryContent` (`components/layouts/DashboardLayout.tsx:41-44`; slot passed at `DashboardPanel.tsx:51`). Move `{progress}` above `<QueryContent>`.
2. **"Assign + issue (quick form)" does not say it can reject broken units (earlier #6, open).** `RequestQueues.tsx:167-170`; the capability
   (`QueuesAssignIssueModal.tsx` IssueItems) is only in that form, the guided wizard issues quantities as accepted (`HandoverItems.tsx:35`).
   Rename the overflow item "Issue with broken-unit check (quick form)" or add the field to `HandoverItems`.
   Partial return is NOT quick-form-only: the guided return already has "Not returned now" per asset (`HandoverItems.tsx:36-37`) and per-quantity buckets.
3. **Reject is two clicks.** Pending row: Accept is the inline primary (`RequestQueues.tsx:158`), Reject is the first overflow item
   (`QueuesList.tsx:51`, `RequestQueues.tsx:204`) or the drawer footer secondary (`RequestDetail.tsx:48`). Old had Accept, Reject, Set due as three row buttons
   (old `QueuesDisplay.tsx:6-9`). Deliberate per `ux-yuyu-spec.md:1115`; acceptable.
4. **Set due moved to the row overflow** (`RequestQueues.tsx:167-168`; old `QueuesDisplay.tsx:6-17`). Same dialog, one extra click. Renew is inline (`QueuesList.tsx:67`), which covers the common extension case.
5. **Requester email/phone only in the drawer** (`RequestDetail.tsx:42` "Contact"; old `QueuesList.tsx:52-57`). Staff ringing about an overdue loan
   need row-click then read. Consider adding the phone to the Active-tab row meta (`QueuesList.tsx:57-62`).
6. **Photos need 3 to 4 clicks** (overflow "View photos" to drawer Evidence to "View ..." to "Open"; old `QueuesList.tsx:75-89` was one click per photo).
   Rarely used; acceptable. Direct handouts keep one overflow click (`DirectLoanList.tsx:64-67`).
7. **Names disagree across three surfaces.** Sidebar "Job pickups" / "Inbox" / "Home" / "Items" (`sidebarSections.ts:24-28`), palette "Go to Job handover" / "Notifications" / "Dashboard"
   (`CommandPalette.tsx:33-34` uses `TAB_LABELS`, `staffAccess.ts:10-53`), page title "Ready to collect" (`panels/machine/HandoverConsole.tsx:37`). Typing "inbox", "home" or "pickups" in the palette matches nothing.
   Fix: have `CommandPalette` use the sidebar `LABELS`, or match both.
8. **Request tab counts read the dashboard cache without subscribing** (`RequestQueues.tsx:72-73`); they are blank until the dashboard has loaded and only
   Pending/Ready carry one. Same cache feeds the Requests sidebar badge (`StaffShell.tsx:35-37`), so a handout-only user (no dashboard tab) never sees it.
9. **Dashboard activity rail shows 3 items below 1280px** (`DashboardLayout.tsx:59`); "See all activity" is present (`DashboardWidgets.tsx:17-39`).
10. **Dead files:** `panels/QueuesDisplay.tsx` (old row buttons, `HistoryPanel`), `panels/QueuesSkeleton.tsx` and `FormFooter` in `QueuesModalShared.tsx` are imported nowhere. `handover/AssignBoxDialog.tsx`, `IssueDialog.tsx`, `ReturnDialog.tsx`, `HandoverDialogs.tsx` were already unmounted in the old tree. Delete in a hygiene commit.
11. **Money actions have no confirm** (unchanged): Waive (row + bulk, `PaymentsRows.tsx:26`, `PaymentsPanel.tsx:104`), Revoke claim code (`MemberClaimCodes.tsx`), Delete saved view (`SavedViewsMenu.tsx:69`). Not a regression; `OverflowMenu` supports `confirm` if desired.

---

## Earlier restore list: status

| # | Earlier item | State | Evidence |
| --- | --- | --- | --- |
| 1 | Request queue visibility (R3) | Fixed, by aligning to backend authority | `requestTabs.ts:9-17`; see G1 and P1-2 |
| 2 | Accept/Reject inline | Fixed (Accept inline, Reject overflow + drawer) | `RequestQueues.tsx:158,204`, `QueuesList.tsx:51,65-66` |
| 3 | Renew on active rows | Fixed | `RequestQueues.tsx:205`, `QueuesList.tsx:67` |
| 4 | Direct counter form and walk-in/waiver/container only in compact | Fixed | guided step 0 `DirectHandoverWizard.tsx:97` (`DirectLoanBorrowerExtras`), step 1 `:100` (container), compact view remembered `:20-26`; payload sends `container_id` `:56` |
| 5 | Dashboard tiles hidden after four | Fixed | `DashboardLayout.tsx:38,45-49` show all, nothing collapsed |
| 6 | Reject-broken-units / partial return only in quick forms | **Open (P2-2)** | partial return is in the guided flow; broken units is quick-form only |
| 7 | Row lost damaged/shelf/rejection info | Fixed | `QueuesList.tsx:8-12,60-61,64` |
| 8 | Failed kiosk handovers easy to miss | Fixed | warn callout `RequestsPanel.tsx:17-22`, `revealKey` opens the section |
| 9 | Request tab counts | Fixed (caveat P2-8) | `RequestQueues.tsx:193-194` |
| 10 | "Save current view?" labels | Fixed | `SavedViewsMenu.tsx:60-61` read "…" |
| 11 | Search hint | Fixed | `RequestQueues.tsx:201` placeholder "Search by name, email, phone or purpose" |
| 12 | Setup checklist hidden on dashboard error | **Open (P2-1)** | `DashboardLayout.tsx:41-44` |
| 13 | Tile danger tone | Fixed | `DashboardPanel.tsx:54` |
| 14 | Job tray on mobile | Fixed | `StaffShell.tsx:65` (`lg:hidden` pill above content) |
| 15 | Inbox paging assumes 24 | Verified correct | `backend/apps/notifications/views_inbox.py:54` `page_size = 24` |
| 16 | Payments Type column | Fixed | own column again `PaymentsRows.tsx:16` |
| 17 | Payments due filter inline | Fixed | `PaymentsFilters.tsx:15-23` (shown on To collect) |
| 18 | Stray BOMs | Fixed | no U+FEFF left in `QueuesModals.tsx` or `LoanTimeline.tsx` |

---

## Capability table

Status key as in the brief. "Phone" notes only where reachability differs.

### Shell (sidebar, top bar, bottom tabs, switcher)

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| S1 | Every permitted tab reachable (41 keys in `ALL_TABS` all appear in `SIDEBAR_SECTIONS`) | `StaffDock.tsx:55-63`, `staffAccess.ts:55-65` | `sidebarSections.ts:13-23,42-62` | PRESENT | Inventory extras (categories, containers, warranty, qr, bulk) sit behind "More (n)" (`SidebarSection.tsx:51-58`); Settings children open when a settings page is active (`sidebarSections.ts:50-59`) |
| S2 | Handout-only narrow set (requests, direct, handover, payments, notifications) | `staffAccess.ts:119` | `sidebarSections.ts:46`, `StaffShell.tsx:59` bottom tabs | PRESENT | Five items, so no "More" button (`BottomTabs.tsx:11,19`) |
| S3 | Unread notification count | `StaffDock.tsx:208-212` | `StaffShell.tsx:34`; phone: aria only `MobileTopBar.tsx:69` | CHANGED | Visible in sidebar/bottom tabs; **not visible on phones for non-handout staff (P1-1)** |
| S4 | Multi-membership makerspace picker | `StaffHeader.tsx:51-64` | `StaffShell.tsx:48-56`, `WorkspaceSwitcher.tsx` | PRESENT | Phone: in the drawer. Locked for one space or single-tenant (`:56`) |
| S5 | Superadmin "Switch makerspace" | `StaffHeader.tsx:73-77` | `StaffShell.tsx:50,62` | PRESENT | In the switcher menu, or the user menu when only one space exists |
| S6 | Public inventory link | `StaffHeader.tsx:68-72` | `StaffShell.tsx:47,59` (`footerLinks`) | PRESENT | Label now "View public page ↗"; also in switcher menu |
| S7 | Theme toggle | `StaffHeader.tsx:78` | `UserMenu.tsx:105` | PRESENT | Phone: top-bar user menu (`MobileTopBar.tsx:75`) |
| S8 | Sign out | `StaffHeader.tsx:79` | `UserMenu.tsx:106` | PRESENT | Phone: same menu |
| S9 | Username, role, space code | `StaffHeader.tsx:41-48,66` | `StaffShell.tsx:52,62` | PRESENT | |
| S10 | Background job tray on every page | `StaffWorkspace.tsx:136`, `JobTray.tsx:23-33` | `StaffShell.tsx:61,65`, `JobTray.tsx:31-46` | CHANGED | Sidebar pill + modal; `<lg` pill above content. Poll, Retry status, Dismiss kept (`JobTray.tsx:9-30`) |
| S11 | Command palette trigger, Ctrl/Cmd+K | `StaffWorkspace.tsx:134` | `StaffShell.tsx:57,68`, `Sidebar.tsx:17-20`, `MobileTopBar.tsx:73` | PRESENT | Also opens from inside the drawer (`AppShell.tsx:25-40`) |
| S12 | Skip link, main landmark | `StaffWorkspace.tsx:119,135` | `AppShell.tsx:49,53` | PRESENT | |
| S13 | Bottom navigation on phones | fixed dock for every role | drawer for everyone; bottom tabs only handout-only (`AppShell.tsx:58`) | CHANGED | Same two taps; see P1-1 for the lost badge |

### Command palette / global search

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| C1 | "Go to <tab>" commands for allowed tabs | `CommandPalette.tsx:33-34` | same | CHANGED | Labels no longer match sidebar names (P2-7) |
| C2 | Quick-create commands (request/direct, item, event, booking) | `:35` | same | PRESENT | `quickCreate.ts` identical |
| C3 | Server search `/admin/search`, hits filtered to allowed tabs | `:27-36` | same | PRESENT | |
| C4 | Arrow/Home/End/Enter keyboard model | `:70-77` | same | PRESENT | |
| C5 | Dialog-stack guard on Ctrl+K | `:46-48` | same | PRESENT | |
| C6 | Resets on makerspace/user change | `:55` | same | PRESENT | |

### Dashboard

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| D1 | All 17 tiles visible | `DashboardPanel.tsx:112-141` | `DashboardLayout.tsx:38,45-49` | PRESENT | First 4 as cards, rest as compact rows, none behind a disclosure |
| D2 | Tile gating (scope mode, modules, email, payments) | `:113-121` | `DashboardPanel.tsx:19-27` | PRESENT | Identical |
| D3 | Tile deep links to filtered lists | `:126-129` | `DashboardPanel.tsx:55` | PRESENT | `dashboardLinks.ts` unchanged; `queue=` values map to tabs |
| D4 | Tone semantics | `:34-92` | `DashboardPanel.tsx:54`, `StatCard.tsx:12-13` | CHANGED | Danger keeps its own pill; warn/queue tiles share "Needs attention". Top alert also a banner (`:32-40,56`) |
| D5 | Loading / error | `:110-111` | `LayoutFrame.tsx:38-46` | CHANGED | Error or skeleton replaces the whole body including `progress` (P2-1) |
| D6 | Setup checklist progress | `StaffWorkspace.tsx:137`, `SetupChecklist.tsx:22` | `StaffWorkspace.tsx:135`, `SetupChecklist.tsx:22-44` | PRESENT | Adds progress bar and next-step link |
| D7 | Full step list with Done/To do and "ask an administrator" | old `:22` | `SetupChecklist.tsx:37-41` | BURIED | Behind "All setup steps"; low frequency |
| D8 | Dismiss checklist, per browser | old `:18` | `SetupChecklist.tsx:29` | PRESENT | Button reads "Hide" (aria-label kept) |
| D9 | Checklist gate `canManageMakerspace` on dashboard only | `StaffWorkspace.tsx:137` | `StaffWorkspace.tsx:135` | PRESENT | |
| D10 | Machine work-queue pages from tiles (`?work_queue=`) | old `DashboardMachineQueue.tsx` | same file, mounted by `MachinesPanel.tsx:42` | PRESENT | Rows now deep link to `?view=queue&job_status=` (consumed at `MachineTypePage.tsx:64`) |

### Inbox (notifications)

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| N1 | Row: family, date, title, summary, unread highlight | `PersonalInbox.tsx:56-64` | `PersonalInbox.tsx:83-103` | PRESENT | Summary clamps to 2 lines, "Read message" expands |
| N2 | Unread count | `:40` | header meta `:73`, Unread tab count `:76` | PRESENT | |
| N3 | Unread-only | `:42-43` | Unread/All tabs, default All (`:47`) | CHANGED | |
| N4 | Family filter (11) | `:44-49` | Filters popover (`:77-79`) | BURIED | Phone: modal |
| N5 | Mark all read | `:50-51` | header primary (`:74`) | PRESENT | |
| N6 | Open link (internal only) | `:62` | `:94` | PRESENT | Also marks read |
| N7 | Mark read per row | `:63` | `:95` | PRESENT | |
| N8 | Paging | `:66-68` | numbered `Pagination` `:104` | CHANGED | Backend page size is 24, matches |
| N9 | 60 s refresh | `:29-31` | `:58,60` | PRESENT | |
| N10 | Announcement composer | `NotificationInbox.tsx:7` | header secondary opening a modal (`NotificationInbox.tsx:11-14`) | BURIED | Phone: header overflow |
| N11 | Composer fields and gate (`manage_members` + `membership.broadcasts`) | same | `NotificationInbox.tsx:9`, `BroadcastComposer.tsx` unchanged | PRESENT | |
| N12 | Load / mutation errors | `:54` | `:106`, layout error state | PRESENT | |

### Requests

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| R1 | Pending / Ready / Active / History | one scrolling page `RequestQueues.tsx:198-217` | tabs `requestTabs.ts:1-5`, `RequestQueues.tsx:193` | CHANGED | One queue at a time |
| R2 | Who sees which tab | old `:95,106,117,128` | `requestTabs.ts:9-17` | CHANGED | Stricter, backend-aligned (G1, P1-2) |
| R3 | `?queue=` deep link | `:195` | `requestTabs.ts:20-28` | PRESENT | Legacy `history=true`, `*Page` also read |
| R4 | `?id=` deep link | `:90`, filter | `useRequestQueues.ts` probe; `QueuesList.tsx:22` | CHANGED | Now also opens the detail drawer |
| R5 | Search name/email/phone/purpose, debounced, in URL | `:197` | `RequestQueues.tsx:201` | PRESENT | Placeholder restored |
| R6 | Sort Newest/Oldest/Due first | `ListViewControls.tsx:11` | `ListSort.tsx`, `RequestQueues.tsx:201` | PRESENT | |
| R7 | Saved views list | `SavedViewsMenu.tsx:35-38` | "Views" menu `SavedViewsMenu.tsx:56-62` | BURIED | |
| R8 | Save current view (+share) | `:39,44-51` | `:60`, modal `:76-83` | BURIED | |
| R9 | Manage views (share, make private, delete) | `:42` | `:61`, modal `:64-75` | BURIED | |
| R10 | Clear the selected-result filter | `ListViewControls.tsx:9` | chip `ListViewControls.tsx:15` | PRESENT | Plus empty-state "Clear filters" |
| R11 | Per-queue pagination | `:201,207,213` | `RequestQueues.tsx:207` | PRESENT | |
| R12 | Row: #id, requester, status | `QueuesList.tsx:38-41` | `QueuesList.tsx:44-66` | PRESENT | |
| R13 | Status stepper | `:48` | `RequestDetail.tsx:31` | BURIED | Drawer |
| R14 | Purpose | `:50` | `QueuesList.tsx:59` | PRESENT | |
| R15 | Accepted by / Issued by | `:51,111-118` | `RequestDetail.tsx:44-45` | BURIED | Drawer |
| R16 | Requester email/phone | `:52-57` | `RequestDetail.tsx:42` | BURIED | Drawer (P2-5) |
| R17 | Rejection reason | `:58-62` | `QueuesList.tsx:61` | PRESENT | |
| R18 | Due time, "no due set", reminder sent | `:63-66` | `QueuesList.tsx:62`, `RequestDetail.tsx:28,46` | CHANGED | Relative "Overdue ·/Due"; "no due"/"reminder sent" in drawer |
| R19 | Every item x qty with shelf | `:67-74` | `QueuesList.tsx:57,60`, `RequestDetail.tsx:32-34` | CHANGED | First two items; Ready rows list shelves; full list in drawer |
| R20 | Damaged / missing / to-fix summary | `:91-104` | `QueuesList.tsx:8-12,64`, `RequestDetail.tsx:36` | PRESENT | Danger pill on the row |
| R21 | View issue / return photos | `:75-89` | overflow `QueuesList.tsx:53` to drawer `RequestEvidence.tsx` | BURIED | Retention error text kept |
| R22 | Loan timeline (`canViewAudit`) | `:44,90` | overflow `QueuesList.tsx:52`, drawer tab | BURIED | `LoanTimeline.tsx` content unchanged |
| R23 | Accept (pending) | `QueuesDisplay.tsx:7` | row primary `RequestQueues.tsx:159` | PRESENT | |
| R24 | Accept dialog: per-line qty, at least one unit | `QueuesAcceptModal.tsx:28-85` | same form in `RequestFlowDialog` | PRESENT | Validation identical |
| R25 | Reject with required reason | `QueuesDisplay.tsx:7`, `QueuesModals.tsx:50-81` | overflow `QueuesList.tsx:51` or drawer footer | BURIED | P2-3 |
| R26 | Set due (pending, ready, active) | `QueuesDisplay.tsx:7,11,15` | overflow `RequestQueues.tsx:168` | BURIED | P2-4 |
| R27 | Assign + issue compact form incl. reject broken units, asset scans, kit | `QueuesAssignIssueModal.tsx:65-119` | overflow `RequestQueues.tsx:169` (primary when guided is not allowed, `:161-162`) | BURIED | Broken-unit rejection exists only here (P2-2) |
| R28 | Guided issue | `RequestQueues.tsx:206` | primary `RequestQueues.tsx:160-161`; header primary for a single ready request | PRESENT | |
| R29 | Return compact form, per-asset "Not returned now", kit | `QueuesReturnRequestModal.tsx:80-135` | overflow "Partial return (quick form)" `RequestQueues.tsx:170` | BURIED | Guided return has the same outcomes (`HandoverItems.tsx:35-41`) |
| R30 | Guided return | `RequestQueues.tsx:212` | primary `RequestQueues.tsx:162-164` | PRESENT | Row label "Return" (`QueuesList.tsx:65`) |
| R31 | Renew loan (`loans.renewals`) | `RequestQueues.tsx:212` | inline `RequestQueues.tsx:205`, `QueuesList.tsx:67` | PRESENT | Also in drawer |
| R32 | History toggle | `QueuesDisplay.tsx:43` | History tab | CHANGED | |
| R33 | History rows read-only | `RequestQueues.tsx:217` | `RequestQueues.tsx:167` (`menu` empty) | PRESENT | |
| R34 | Guided wizard: box QR, borrower check, `ScanCardBox`, items/asset scan, photo + remark, kit, receipt + Print | `HandoverWizard.tsx:15-86` | `HandoverWizard.tsx:16,40,86,94` | PRESENT | Adds Compact view, back, leave guard (`:77`) |
| R35 | "Box assigned, issue failed" recovery | `RequestQueues.tsx:189` | `HandoverWizard.tsx:88-90`, `RequestQueues.tsx:154-156` | PRESENT | Retry button |
| R36 | Failed kiosk handovers panel | `RequestsPanel.tsx:6` | callout `RequestsPanel.tsx:17-22` + collapsible `KioskReplayRecoveryPanel.tsx:27-28` | PRESENT | Opens when unresolved > 0 |
| R37 | Recovery: status filter, review, guidance, evidence preview, acknowledge, correct online, paging | `KioskReplay*.tsx` | same components restyled | PRESENT | Phone-safe wrapping |
| R38 | Non-hardware actor message | `RequestsPanel.tsx:6` | `RequestsPanel.tsx:10` | PRESENT | |
| R39 | HARD RULE issue needs box QR + issue photo | `QueuesAssignIssueModal.tsx:87-92`, `HandoverWizard.tsx:38` | `HandoverWizard.tsx:40` (`ready`), compact `submitAssign` unchanged | PRESENT | Enforced in both paths |
| R40 | HARD RULE return needs return photo + remark | `QueuesReturnRequestModal.tsx:99-100` | `HandoverWizard.tsx:40` (`remark.trim()` in return mode) | PRESENT | |
| R41 | Per-queue load errors | `:202,208,214` | `RequestQueues.tsx:179-182` | PRESENT | Retry |
| R42 | Per-queue result counts | `:201,207,213` | tab counts `RequestQueues.tsx:193-194` | CHANGED | Pending and Ready only; cache read (P2-8) |

### Direct handout, direct returns, claim codes

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| H1 | Start guided handout | `DirectLoans.tsx:206` | header primary `DirectLoans.tsx:184`, empty state `:188` | PRESENT | |
| H2 | Counter form always on page | `DirectLoans.tsx:208-261` | "Compact view" inside New handout (`DirectHandoverWizard.tsx:91`); choice remembered (`:20-26`) | BURIED | One click once, then it opens in compact |
| H3 | Witnessed waiver acceptance | `DirectLoanIssueFields.tsx:75` | `DirectLoanIssueFields.tsx:60-83`, guided `DirectHandoverWizard.tsx:97`, compact too | PRESENT | |
| H4 | Walk-in member creation | `:80` | `DirectLoanIssueFields.tsx:80`, guided `:97` | PRESENT | |
| H5 | Container (select, scan, membership check) | `:105` | `DirectLoanIssueFields.tsx:85-110`, guided `:100`, payload `:56` | PRESENT | |
| H6 | Item lines, qty, tracking hint | `:153` | compact `DirectLoanIssueFields.tsx:129-175`; guided qty steppers `:103` | PRESENT | |
| H7 | Tool QR scan, chips with Remove, pasted payloads | `:199` | compact `DirectLoanIssueFields.tsx:178-218`; guided continuous scan + manual check `:101-102` | PRESENT | Multi-line paste only in compact |
| H8 | Issue photo and remark | `DirectLoans.tsx:243-250` | guided step 2 `:105`; compact `DirectLoanIssueFields.tsx:220-256` | PRESENT | |
| H9 | Kit checklist | `:251` | `DirectHandoverWizard.tsx:50,105`, compact `DirectLoans.tsx:172` | PRESENT | |
| H10 | Submit with hints | `:252-257` | compact action `DirectLoans.tsx:192`; hints `:173-174`; guided "Confirm handout" | PRESENT | |
| H11 | Guided wizard: card scan, borrower, scan, quantities, photo, kit, receipt + Print | `DirectHandoverWizard.tsx` (old) | `DirectHandoverWizard.tsx:80-112` | PRESENT | |
| H12 | Member claim codes (issue, QR, active list, Revoke) | `DirectLoans.tsx:263` | "Claim codes" tab `DirectLoans.tsx:186,189` | CHANGED | One-click tab |
| H13 | Mixed loan list | `DirectLoans.tsx:264` | On loan / Returned tabs (`:35-36,186`), server `?status=` | CHANGED | |
| H14 | Row: target, Lent/Returned, container, due, issued by, items | `DirectLoanList.tsx:58-76` | `DirectLoanList.tsx:52-61` | PRESENT | |
| H15 | Return button on lent rows | `:69-73` | `DirectLoanList.tsx:63` | PRESENT | |
| H16 | View issue / return photo | `:80-88` | overflow `DirectLoanList.tsx:64-67` | BURIED | |
| H17 | Return notes on returned rows | `:90` | `DirectLoanList.tsx:59` | PRESENT | |
| H18 | Pagination | `DirectLoans.tsx:265` | `:190` | PRESENT | |
| H19 | Return dialog: kit, photo, per-asset/quantity outcomes, QR (required when `return_scan_required`), notes | `DirectLoanReturnModal.tsx` (old) | `DirectLoanReturnModal.tsx:196-317` three steps | CHANGED | All fields kept; stricter integer bounds (`:104-110`) |
| H20 | HARD RULE direct issue needs evidence + eligible tool/borrower | `DirectLoans.tsx:140-146` | `DirectLoans.tsx:128-132`, wizard `ready` `:52` | PRESENT | |
| H21 | HARD RULE direct return needs photo + notes | `DirectLoanReturnModal.tsx:106-112` | `DirectLoanReturnModal.tsx:109-115` | PRESENT | |
| H22 | `?create=request` opens the flow | `DirectLoans.tsx:38` | `DirectLoans.tsx:37` | PRESENT | |
| H23 | Tab gates (`issue_direct_loan`, `inventory.self_checkout`, `public_inventory`) | `staffAccess.ts:131`, `staffTabs.ts:108-110` | unchanged | PRESENT | |

### Job pickups (machine-service handover)

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| J1 | List finished jobs (`status=completed`) | `HandoverConsole.tsx:36-48` | `HandoverConsole.tsx:23-24` | PRESENT | Adds requester search and Waiting/Unpaid stats |
| J2 | Hand over (`/collect`) | `:42-48,83-90` | `:25-32,49` | PRESENT | Now toasts "Handed to ..." |
| J3 | Paid / Unpaid and amount | `:23-31,77-81` | `:12-16,48` | PRESENT | |
| J4 | Empty / error / collect-failed messages | `:57-62,97-101` | `:38,41,51` | PRESENT | |

### Payments

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| P1 | Receipts and credit notes (staff only): list, PDF, paging | `PaymentsPanel.tsx:143` | header secondary + drawer `PaymentsPanel.tsx:113,126-128` | BURIED | Phone: header overflow |
| P2 | Sort (6 orders) | `:144` | `PaymentsFilters.tsx:9` | PRESENT | |
| P3 | Saved views | `:144` | "Views" menu (via `ListViewControls`) | BURIED | |
| P4 | Status filter (incl. recorder restriction) | `:151-157` | tabs `PaymentsPanel.tsx:94-101` | CHANGED | To collect, Paid online, Paid in person, Waived, Cancelled, All; `forRecording` keeps Pending/Paid offline/All |
| P5 | Due filter (forces pending) | `:146-150` | segmented control on To collect `PaymentsFilters.tsx:15-23` | PRESENT | |
| P6 | Subject filter | `:158-164` | Filters popover `PaymentsFilters.tsx:10-14` | BURIED | |
| P7 | Columns incl. Type, Refunded, Received (+Corrected), Created | `:92-105` | `PaymentsRows.tsx:15-23` | PRESENT | Type is its own column again |
| P8 | Column chooser, density | `:204-213` | `PaymentsPanel.tsx:123` (`listState`) | PRESENT | |
| P9 | Bulk Mark offline / Waive when all selected allow it | `:166-175` | `PaymentsPanel.tsx:102-104,121` | PRESENT | |
| P10 | Row Mark offline with receipt (method, reference, received at) | `:115-117,176-190` | `PaymentsRows.tsx:33`, `SettlementDialog.tsx` | PRESENT | Label "Mark paid" |
| P11 | Row Waive | `:118-120` | overflow `PaymentsRows.tsx:26` | BURIED | |
| P12 | Correct receipt (append-only) | `:123-127,191-199` | overflow `PaymentsRows.tsx:27` | BURIED | |
| P13 | Refund / Release deposit | `:128-132,215-223` | overflow `PaymentsRows.tsx:28`, `PaymentRefundDialog.tsx` | BURIED | |
| P14 | Correct refund #N | `:133-135,224-226` | overflow `PaymentsRows.tsx:29-31` | BURIED | |
| P15 | 409 reconciled conflict + refetch | `:76-81,201` | `PaymentsPanel.tsx:76-81,156` | PRESENT | |
| P16 | Mutation / amend / load errors | `:200-203` | `PaymentsPanel.tsx:114-115,155,157` | PRESENT | |
| P17 | Pagination (24) | `:214` | `PaymentsPanel.tsx:122` | PRESENT | |
| P18 | Gates (`forRecording`, record/waive/refund per subject) | `paymentAccess.ts`, `:37-38` | identical files, `PaymentsPanel.tsx:36-37` | PRESENT | |
| P19 | Selection resets on filter/space change | `:52` | `PaymentsPanel.tsx:52` | PRESENT | |
| P20 | Phone: every column reachable | table | `DataTable.tsx:20-28,155-164` (every column becomes a labelled line) | PRESENT | Actions row last |

### Evidence capture

| # | Capability | Old | New | Status | Note |
| --- | --- | --- | --- | --- | --- |
| E1 | Upload photo from file (presign + PUT/POST) | `EvidenceUpload.tsx` | same logic, `:47-83` | PRESENT | Used by guided, compact, direct, return forms |
| E2 | Camera capture | `CameraCapture.tsx` | same, bottom-sheet on phones | PRESENT | Button full width on narrow columns (`EvidenceUpload.tsx:109`) |
| E3 | Upload status and error | `:120-127` | `EvidenceUpload.tsx:118-130` | PRESENT | |
| E4 | Retention-expired / error text when viewing | `evidenceUi.ts` | `RequestEvidence.tsx` uses `evidenceErrorText` | PRESENT | |

---

## New capabilities with no old counterpart (not counted)

Request detail drawer with Overview / Evidence / Timeline tabs and "Copy link"; header primary "Start handover" for a single ready
request; dashboard Quick add, Overdue and Due within 3 days, Recent activity; Requests sidebar badge; machine-type shortcuts in the
sidebar; "Account & two-step sign-in" user-menu link (`StaffShell.tsx:62`); kiosk failure callout; requester search on Job pickups.

## Phone summary (<768px)

No front-desk capability is hidden on phones. The only `md:`-only rendering in the area is the header `secondary` action
(`PageHeader.tsx:24`), and `mobileActions` re-lists it in the header overflow (`PageHeader.tsx:66,83`). Affected: "Receipts & credit notes",
"Send announcement", "All machines". The visible-signal loss is P1-1.
