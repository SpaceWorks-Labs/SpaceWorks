# Front-desk functionality parity audit (dashboard, requests, direct, payments, notifications)

Read-only research. **Old** = commit `d3e5ed29` (`dev`, pre-revamp). **New** = the `feature/design-revamp`
working tree on 2026-10-15, including the uncommitted polish edits. Old line numbers are from
`git show d3e5ed29:<path>`. New paths are relative to `frontend/src/` unless stated otherwise.

Status key:

- **PRESENT**: same capability, reachable at the same depth or shallower.
- **BURIED**: still reachable, but behind an overflow, collapse, drawer, tab or extra click. Where it now lives is given.
- **CHANGED**: reachable, but its behaviour or shape changed. The change is explained.
- **MISSING**: unreachable in the new UI. I grepped the new tree before marking anything MISSING.

Entry points checked in both versions: `features/staff/StaffTabContent.tsx` (`staffTabs.ts` is byte-identical;
`StaffTabContent` only adds `progress`, `makerspaceName` and `inventoryTabAvailable` props), plus
`StaffWorkspace.tsx`, and in the new tree `StaffShell.tsx` and `sidebarSections.ts`. All five pages are
first-level sidebar items in the new shell: Home, Inbox, Requests, Direct handout and Payments.

---

## 1. Dashboard

Old: `features/staff/panels/DashboardPanel.tsx` (tiles only), `StaffWorkspace.tsx:136-137` (job tray and setup
checklist mounted above the tab content), `components/ui/JobTray.tsx`, `features/staff/SetupChecklist.tsx`.
New: `panels/DashboardPanel.tsx`, `DashboardWidgets.tsx`, `DashboardQuickAdd.tsx`, `DashboardStats.ts`,
`components/layouts/DashboardLayout.tsx`, `components/shell/JobTrayPill.tsx`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| D1 | All 17 count tiles visible at once in a grid (upcoming events, registrations awaiting approval, bookings awaiting approval, upcoming bookings, overdue loans, pending requests, awaiting issue, problem reports, out of stock, pending/active prints, ready to collect, failed emails, stocktakes awaiting approval, warranties expiring, maintenance overdue, pending payments) | `panels/DashboardPanel.tsx:43-61, 112-141` | BURIED | Only the first 4 tiles show, ranked attention-first (`DashboardPanel.tsx:28-30`). The rest sit inside a collapsed "Everything else" section (`DashboardLayout.tsx:23, 31-33`). In full scope mode a typical space has 8–12 tiles, so 4–8 are hidden behind one click. |
| D2 | Tile gating: machine scope mode, module filter, `email` module for failed emails, payments tab for pending payments, `printing` and `maintenance` modules | `DashboardPanel.tsx:113-121` | PRESENT | `DashboardPanel.tsx:19-27`, identical predicates |
| D3 | Each tile deep-links to its filtered list (`dashboardHref`) | `DashboardPanel.tsx:126-129` | PRESENT | `StatCard` `href` (`DashboardPanel.tsx:52-53`). `dashboardLinks.ts` is unchanged. |
| D4 | Tone semantics: `danger` red for overdue, problems, out of stock, failed email and maintenance; `warn` for queues; `secondary` for money; filled tile when action is needed | `DashboardPanel.tsx:34-92, 123-137` | CHANGED | Tiles are either `attention` (a "Needs attention" pill) or `neutral` (`DashboardPanel.tsx:53`), so the danger/warn distinction is gone. New: the top danger item is promoted to a warn banner callout with a "Review" link (`:32-40, 54-55`). |
| D5 | Loading/error text shown above the tiles while the rest of the page stays usable | `DashboardPanel.tsx:110-111` | CHANGED | `QueryContent` replaces the whole body with a skeleton or an ErrorBlock with retry (`LayoutFrame.tsx:37-46`). The setup checklist (`progress`) and the quick-add header are also hidden while the counts query fails. |
| D6 | Setup checklist: progress for profile, hours, first item, staff invited and modules | `StaffWorkspace.tsx:137`, `SetupChecklist.tsx:8-24` | PRESENT | Rendered as the dashboard `progress` slot (`StaffWorkspace.tsx:135`, `SetupChecklist.tsx:22-44`). It now has a progress bar and a "next step →" link. |
| D7 | Setup checklist: full step list with Done/To do, links, and "· ask an administrator" for steps the user can't open | `SetupChecklist.tsx:22` | BURIED | Behind the "All setup steps" toggle (`SetupChecklist.tsx:37-41`) |
| D8 | Dismiss the setup checklist, remembered per browser (localStorage) | `SetupChecklist.tsx:18` | PRESENT | "Hide" button (`SetupChecklist.tsx:29`) |
| D9 | Checklist is gated on `canManageMakerspace` and shown on the dashboard only | `StaffWorkspace.tsx:137` | PRESENT | `StaffWorkspace.tsx:135` |
| D10 | Background-jobs tray: a `<details>` at the top of the main content on every page, with a running count | `StaffWorkspace.tsx:136`, `JobTray.tsx:23-33` | CHANGED | A pill in the sidebar footer (`StaffShell.tsx:61`, `JobTray.tsx:37-46`) that opens a modal. Below the `lg` breakpoint the sidebar only exists inside the hamburger drawer (`AppShell.tsx:47-52`), so on phones and tablets the tray is buried. |
| D11 | Per-job status polling, "Retry status" and "Dismiss" | `JobTray.tsx:6-21` | PRESENT | `JobTray.tsx:9-30`. A `JobPoller` keeps polling while the modal is closed. |

New capabilities with no old counterpart (not counted): **Quick add** header primary (`DashboardQuickAdd.tsx`),
**Overdue** and **Due within 3 days** sections (`DashboardWidgets.tsx:41-63`), and a **Recent activity** rail gated on the
audit tab (`DashboardWidgets.tsx:17-39`). The old global `StaffDock` became the sidebar; `CommandPalette` is still mounted
(`StaffShell.tsx:65`).

**Dashboard: PRESENT 6, BURIED 2, CHANGED 3, MISSING 0.**

---

## 2. Requests

Old: `panels/RequestsPanel.tsx`, `panels/RequestQueues.tsx`, `panels/QueuesList.tsx`, `panels/QueuesDisplay.tsx`,
`panels/QueuesModals.tsx`, `QueuesAcceptModal.tsx`, `QueuesAssignIssueModal.tsx`, `QueuesReturnRequestModal.tsx`,
`QueuesModalShared.tsx`, `handover/HandoverWizard.tsx`, `StaffLoanRenew.tsx`, `panels/LoanTimeline.tsx`,
`ListViewControls.tsx`, `SavedViewsMenu.tsx`, `kiosk/KioskReplay*.tsx`.
New: the same files plus `panels/requestTabs.ts`, `useRequestQueues.ts`, `RequestDetail.tsx`, `RequestEvidence.tsx`,
`RequestFlowDialog.tsx`, `components/layouts/ListLayout.tsx`, `ListFilters.tsx`, `ListSort.tsx`.
(`handover/IssueDialog.tsx`, `ReturnDialog.tsx` and `AssignBoxDialog.tsx` were not imported anywhere in either version.)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| R1 | All queues on one scrolling page: Pending review, Ready for handover, Active loans, plus a History panel | `RequestQueues.tsx:198-217` | CHANGED | Four tabs, one queue at a time (`requestTabs.ts:1-5`, `RequestQueues.tsx:187-203`). |
| R2 | Per-queue result counts visible at the same time (each panel's `Pagination count`) | `RequestQueues.tsx:201, 207, 213` | CHANGED | Only the active tab's count shows, through its pagination. The tabs carry no `count`, although `Tabs` supports one and Direct/Payments use it. The sidebar Requests badge shows pending + awaiting issue (`StaffShell.tsx:35-37`). |
| R3 | Who sees which queue. Pending: everyone except handout-only. Ready: everyone with the tab. Active: everyone except handout-only. History: everyone. The tab is granted by any of `accept_request`, `reject_request`, `assign_box`, `issue_request`, `issue_direct_loan` or `return_request` (`staffAccess.ts:102, 173`). | `RequestQueues.tsx:95, 106, 117, 128, 198, 205, 210, 217` | **MISSING** (role-dependent) | `visibleRequestTabs` (`requestTabs.ts:6-9`) now requires `accept_request` for Pending and `issue_request` for Ready, Active and History. A custom role with only `return_request` gets "You don't have access to request queues", **so it can no longer reach Active loans to record a return.** Roles with only `reject_request`, `assign_box` or `issue_direct_loan`, and reviewers without `issue_request`, lose the other queues they could see before. |
| R4 | `?queue=` single-queue deep link, plus a "Show all request queues" button | `RequestQueues.tsx:195` | CHANGED | The `?queue=` value selects a tab. Old links stay readable (`resolveRequestTab`, `requestTabs.ts:11-18`). |
| R5 | Search (requester name, email, phone, purpose), debounced and kept in the URL | `RequestQueues.tsx:197` | PRESENT | Toolbar search (`RequestQueues.tsx:197`). The placeholder hint listing the searchable fields was lost; it now just reads "Search requests". |
| R6 | Sort: Newest, Oldest, Due first | `ListViewControls.tsx:11` (old) | PRESENT | `ListSort` "Sort:" select (`ListViewControls.tsx:12`) |
| R7 | Saved views: pick one from a visible select | `SavedViewsMenu.tsx:35` (old) | BURIED | "Views" overflow menu (`SavedViewsMenu.tsx:40-46`) |
| R8 | Save current view (name, share-to-makerspace when `canShare`) | `SavedViewsMenu.tsx:39, 44-51` | BURIED | Views ▸ "Save current view?". The label has a stray "?" (`SavedViewsMenu.tsx:44`). |
| R9 | Manage saved views: share/make private, delete | `SavedViewsMenu.tsx:42` | BURIED | Views ▸ "Manage views?" modal (stray "?") (`SavedViewsMenu.tsx:45, 48-59`) |
| R10 | "Clear selected result" for the `id` deep-link filter | `ListViewControls.tsx:9` (old) | PRESENT | "Remove Selected result" chip (`ListViewControls.tsx:15`), plus "Clear filters" in the empty state |
| R11 | Per-queue pagination | `RequestQueues.tsx:201, 207, 213`, `QueuesDisplay.tsx:48` | PRESENT | `ListLayout` pagination per tab (`RequestQueues.tsx:203`) |
| R12 | Row shows #id, requester and status badge | `QueuesList.tsx:38-41` | PRESENT | `QueuesList.tsx:44-49` (`ListRow` and `StatusBadge`) |
| R13 | Row shows a `StatusStepper` | `QueuesList.tsx:48` | BURIED | Detail drawer › Overview (`RequestDetail.tsx:31`) |
| R14 | Row shows purpose (`requested_for`) | `QueuesList.tsx:50` | PRESENT | Row meta (`QueuesList.tsx:46`) |
| R15 | Row shows "Accepted by / Issued by" with role | `QueuesList.tsx:51, 111-118` | BURIED | Drawer aside (`RequestDetail.tsx:44-45`) |
| R16 | Row shows requester contact email and phone | `QueuesList.tsx:52-57` | BURIED | Drawer aside "Contact" (`RequestDetail.tsx:42`) |
| R17 | Row shows the rejection reason | `QueuesList.tsx:58-62` | BURIED | Drawer Overview (`RequestDetail.tsx:35`) |
| R18 | Row shows the due date/time or "No return due time set", plus "reminder sent" | `QueuesList.tsx:63-66` | CHANGED | The row shows a relative due time with an "Overdue ·" prefix (`QueuesList.tsx:47`). "Reminder sent" and "no due date" appear only in the drawer (`RequestDetail.tsx:28, 46`). |
| R19 | Row lists every item × requested qty, with its shelf (storage location) | `QueuesList.tsx:67-74` | CHANGED | The row lists the first 2 items plus "+N more" (`QueuesList.tsx:45`). Shelf locations show only in the drawer Items list (`RequestDetail.tsx:32-34`). |
| R20 | Row shows a damaged/missing/to-fix summary | `QueuesList.tsx:91-104` | BURIED | Drawer "Items needing attention" (`RequestDetail.tsx:36-37`) |
| R21 | View issue photo and each return photo (signed URL opened in a new tab, error inline) | `QueuesList.tsx:75-89` | BURIED | Row overflow ▸ "View photos" → drawer Evidence tab → a per-photo "View …" button loads it inline, with "Open ↗" (`QueuesList.tsx:40`, `RequestEvidence.tsx`) |
| R22 | View/Hide loan timeline (gated on `canViewAudit`) | `QueuesList.tsx:44, 90` | BURIED | Row overflow ▸ "View timeline" → drawer Timeline tab (`QueuesList.tsx:39`, `RequestDetail.tsx:30`). `LoanTimeline.tsx` content is unchanged, rendered as an `ActivityRail`. |
| R23 | Pending: **Accept**, one click on the row | `QueuesDisplay.tsx:7` | BURIED | The row shows "Review" (`QueuesList.tsx:49`), which opens the drawer. Accept is the drawer footer primary (`RequestQueues.tsx:157`, `QueuesList.tsx:54`). That is 2 clicks to reach the dialog. |
| R24 | Accept dialog: per-line quantity 0..requested, at least one unit, partial accept | `QueuesAcceptModal.tsx:28-85` | PRESENT | Same form inside `RequestFlowDialog` (`QueuesAcceptModal.tsx`) |
| R25 | Pending: **Reject** with a required reason, one click on the row | `QueuesDisplay.tsx:7`, `QueuesModals.tsx:50-81` | BURIED | Only the drawer footer secondary (`RequestQueues.tsx:200`). It is not in the row overflow, so it takes 2 clicks. |
| R26 | **Set due** (datetime-local, default `default_loan_days`) on Pending, Ready and Active | `QueuesDisplay.tsx:7, 11, 15`, `QueuesModals.tsx:17-48` | BURIED | Row overflow and drawer overflow ▸ "Set due" (`RequestQueues.tsx:165-166`) |
| R27 | Ready: **Assign + issue** compact form. Box field (Scan, available-container select, manual code), issue photo, remark, asset-QR scan list (exact count), **reject broken units with a disposition** (needs-fix or remove), kit checklist | `QueuesDisplay.tsx:11`, `QueuesAssignIssueModal.tsx:65-95, 118-119` | BURIED | It is the row primary only when the user lacks the guided-issue gates. Otherwise it is row overflow ▸ "Assign + issue" (`RequestQueues.tsx:158-160, 167`). The guided wizard has no "reject broken units", so for most staff that capability now sits only in the overflow. |
| R28 | Ready: **Guided issue** wizard (gated on `issue_request` + `assign_box` + `upload_evidence`) | `RequestQueues.tsx:206` | PRESENT | Row primary "Start handover" (`RequestQueues.tsx:159`). It is also the header primary when exactly one request is ready (`:189`). |
| R29 | Active: **Return** compact form. Return photo next to the issue photo, box field, remark, returned/damaged/missing per quantity line, **per-asset outcome including "Not returned now"** (partial return), kit checklist | `QueuesDisplay.tsx:15`, `QueuesReturnRequestModal.tsx:80-108, 135` | BURIED | Row overflow ▸ "Compact return" when guided return is allowed (`RequestQueues.tsx:168`). It is the primary only otherwise. The per-asset "Not returned now" partial return exists only here. |
| R30 | Active: **Guided return** wizard (gated on `return_request` + `upload_evidence`) | `RequestQueues.tsx:212` | PRESENT | Row inline "Return" (`QueuesList.tsx:50`, `RequestQueues.tsx:161-163`) |
| R31 | Active: **Renew loan** (`loans.renewals` feature), inline on every active row | `RequestQueues.tsx:212`, `StaffLoanRenew.tsx` | BURIED | Only inside the detail drawer Overview, through `extra` (`RequestQueues.tsx:201`, `QueuesList.tsx:54`, `RequestDetail.tsx:38`). The row never renders `extra`. |
| R32 | History show/hide toggle | `QueuesDisplay.tsx:43` | CHANGED | History tab |
| R33 | History rows are read-only | `RequestQueues.tsx:217`, `QueuesDisplay.tsx:47` | PRESENT | No row primary. The overflow offers view details, timeline, photos and copy link. |
| R34 | Guided wizard content: box QR scan/manual check, borrower check with optional `ScanCardBox` (`scan_member_cards`), items and continuous asset scan, photo + remark (required for return) + kit, receipt with Print | `HandoverWizard.tsx:15-86` | PRESENT | `HandoverWizard.tsx`, now a `FlowLayout`. Adds a Compact view (all steps on one page), back-step navigation, a leave guard while a photo is uploaded, and a retry action. |
| R35 | "Box assigned, but issue failed" recovery message | `RequestQueues.tsx:189`, `HandoverWizard.tsx:84` | PRESENT | `RequestQueues.tsx:152`, `HandoverWizard.tsx` error callout with "Retry issue" |
| R36 | **Failed kiosk handovers** panel, always expanded under the queues | `RequestsPanel.tsx:6`, `kiosk/KioskReplayRecoveryPanel.tsx:17-43` | CHANGED | A `CollapsibleSection` titled "Failed kiosk handovers · N" in the ListLayout `detail` slot, below the list and pagination (`RequestsPanel.tsx:7`, `RequestQueues.tsx:204`, `KioskReplayRecoveryPanel.tsx:19-21`). It auto-opens only when the current filter's count is above 0. |
| R37 | Recovery contents: Unresolved/Resolved/All filter, per-failure Review/expand, failure detail and guidance, preview/open failed evidence, "Acknowledge — no change occurred" with confirm, "Correct online" with Station URL, previous/next pages | `KioskReplayRecoveryPanel.tsx:20-41`, `KioskReplayResolution.tsx:28-45`, `KioskReplayDetail.tsx:26-27` | PRESENT | Same components, restyled (`ListRow` + `StatusPill`) |
| R38 | Non-hardware actor message ("Machine-service queues are managed from Machines.") | `RequestsPanel.tsx:6` | PRESENT | `RequestsPanel.tsx:7`, an empty `ListLayout` |
| R39 | **Hard rule: issue needs box QR + issue photo** (+ exact asset-QR count and the kit checklist) | `QueuesAssignIssueModal.tsx:87-92`, `HandoverWizard.tsx:38` | PRESENT | Validation is byte-identical. The compact form's `submitAssign` refuses without the box code, photo, kits and scan count. The wizard's `ready` (unchanged) disables "Confirm issue" in both guided and compact view. |
| R40 | **Hard rule: return needs return photo + remark** | `QueuesReturnRequestModal.tsx:99-100`, `HandoverWizard.tsx:38` | PRESENT | Unchanged. The compact form refuses without the photo or remark. The wizard's `ready` requires `remark.trim()` in return mode. |
| R41 | Per-queue load errors | `RequestQueues.tsx:202, 208, 214` | PRESENT | Layout error state with retry (`RequestQueues.tsx:177-180`) |

New capabilities with no old counterpart (not counted): a request detail drawer with Overview/Evidence/Timeline tabs,
"Copy link" per row, deep-link probing of `?id=` across queues (`useRequestQueues.ts`), and a header primary for a
single ready request.

**Requests: PRESENT 17, BURIED 16, CHANGED 7, MISSING 1.**

---

## 3. Direct handout

Old: `DirectLoans.tsx`, `DirectLoanList.tsx`, `DirectLoanIssueFields.tsx`, `DirectLoanReturnModal.tsx`,
`useDirectLoanReturn.ts`, `MemberClaimCodes.tsx`, `handover/DirectHandoverWizard.tsx`.
New: the same files plus `DirectLoanCompactWork.tsx`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| H1 | "Guided handout" button | `DirectLoans.tsx:206` | PRESENT | Header primary "New handout" (`DirectLoans.tsx:222`). It also appears in the empty state. |
| H2 | **Counter form always on the page**: borrowing-member select | `DirectLoans.tsx:208-215` | BURIED | New handout → wizard → "Compact view" toggle (`DirectLoans.tsx:204-205, 230`, `DirectHandoverWizard.tsx` `compactWork`). The guided step 0 has its own borrower select. |
| H3 | Record witnessed waiver acceptance (`/admin/memberships/<id>/waiver/witness`) | `DirectLoanIssueFields.tsx:75` | BURIED | Compact view only. The guided wizard has no equivalent. |
| H4 | Walk-in member creation (`WalkInMemberForm`) | `DirectLoanIssueFields.tsx:80` | BURIED | Compact view only. The guided wizard has no equivalent. |
| H5 | Container (optional): select, Scan, membership check | `DirectLoans.tsx:216-226`, `DirectLoanIssueFields.tsx:105` | BURIED | Compact view only. The guided wizard always sends `container_id: null`. |
| H6 | Product item lines: add, remove, quantity, tracking-mode hint | `DirectLoans.tsx:227-235`, `DirectLoanIssueFields.tsx:153` | BURIED | Compact view (guided step 1 has per-product quantity inputs instead) |
| H7 | Tool QR: scan, scanned chips with Remove, pasted payloads (one per line) | `DirectLoans.tsx:236-242`, `DirectLoanIssueFields.tsx:199` | BURIED | Compact view. Guided step 1 has continuous scan and a manual check, but no multi-line paste. |
| H8 | Issue photo + issue remark (default "Issued from direct handout.") | `DirectLoans.tsx:243-250` | BURIED | Compact view, or guided step 2 |
| H9 | Kit checklist (`loans.kit_checklist`) | `DirectLoans.tsx:251` | BURIED | Compact view or guided step 2 |
| H10 | "Issue direct handout" submit, with the "Upload an issue photo…" and "Add at least one item…" hints | `DirectLoans.tsx:252-257` | BURIED | Compact view footer action (`DirectLoans.tsx:230`, `compactAction`). Hints are in `DirectLoans.tsx:211-212`. |
| H11 | Guided wizard: member-card scan, borrower select, continuous tool scan, quantities, photo, remark, kit, receipt + Print | `handover/DirectHandoverWizard.tsx` (old) | PRESENT | `DirectHandoverWizard.tsx`, now a `FlowLayout` with a step rail and result panel |
| H12 | Member claim codes for walk-ins: issue code + QR, active list, Revoke | `DirectLoans.tsx:263` | BURIED | "Claim codes" tab (`DirectLoans.tsx:224, 227`) |
| H13 | Loans list: one mixed list of all statuses | `DirectLoans.tsx:264`, `DirectLoanList.tsx:53` | CHANGED | "On loan" and "Returned" tabs using the server `?status=` filter (`DirectLoans.tsx:91-96, 224`; the backend supports it, `direct_loan_views.py:43`). The active tab shows a count. |
| H14 | Row: target, Lent/Returned status, container, due, issued by, items | `DirectLoanList.tsx:58-76` | PRESENT | `DirectLoanList.tsx:52-59` |
| H15 | Row: "Return" button on checked-out loans | `DirectLoanList.tsx:69-73` | PRESENT | Inline (`DirectLoanList.tsx:63`) |
| H16 | View issue photo / View return photo (signed URL, new tab) | `DirectLoanList.tsx:80-88` | BURIED | Row overflow (`DirectLoanList.tsx:64-67`) |
| H17 | Return notes shown on returned rows | `DirectLoanList.tsx:90` | PRESENT | Row meta (`DirectLoanList.tsx:59`) |
| H18 | Pagination | `DirectLoans.tsx:265` | PRESENT | `DirectLoans.tsx:228` |
| H19 | Return dialog on one screen: kit checklist, return photo, outcomes (quantity buckets and per-asset), return QR (required when `return_scan_required`) + scanner, notes | `DirectLoanReturnModal.tsx` (old, single form) | CHANGED | A 3-step `FlowLayout`: Check items → Photo and QR → Return notes. Every field is kept, and integer/bounds validation is stricter. |
| H20 | **Hard rule: direct issue needs uploaded issue evidence + eligible tool/borrower** | `DirectLoans.tsx:140-146` | PRESENT | `canIssue` is unchanged (`DirectLoans.tsx:141-147`). The wizard's `ready` requires borrower + items + evidence + kits. |
| H21 | **Hard rule: direct return needs return photo + notes** (+ scan when required, + every unit resolved) | `DirectLoanReturnModal.tsx:106-112`, `useDirectLoanReturn.ts:57-59` | PRESENT | `canSubmit` is unchanged and its guard tightened (`DirectLoanReturnModal.tsx:108-114`). The Submit button is disabled until it passes. |
| H22 | `?create=request` quick-create opens the guided flow | `DirectLoans.tsx:38` | PRESENT | `DirectLoans.tsx:37` |

**Direct: PRESENT 9, BURIED 11, CHANGED 2, MISSING 0.**

---

## 4. Payments

Old: `PaymentsPanel.tsx`, `paymentAccess.ts`, `SettlementDialog.tsx`, `PaymentRefundDialog.tsx`,
`RefundReceiptAmendDialog.tsx`, `PaymentDueBadge.tsx`, `payments/PaymentDocuments.tsx`.
New: the same files plus `PaymentsFilters.tsx` and `PaymentsRows.tsx`.

There is no manual "create a charge" or "record payment" form on this page in either version. "Recording" a
payment means **Mark offline** with a `ManualSettlement` receipt (P10). Billing-document settings live in
Settings in both versions (`MakerspaceSettingsPanel.tsx:183` new). The embedded `PaymentReconcileActions` (used on
Members, Bookings, Events and Admission) also moved **Waive** into an overflow menu (`PaymentReconcileActions.tsx` new).
That is outside this page and noted for completeness.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| P1 | Receipts and credit notes (staff, `!forRecording`): list, Download PDF, paging | `PaymentsPanel.tsx:143`, `PaymentDocuments.tsx:37-55` | BURIED | Header secondary "Receipts & credit notes" opens a drawer (`PaymentsPanel.tsx:113, 126-128`). On mobile the secondary folds into the header overflow (`PageHeader.tsx:10, 27`). |
| P2 | Sort (due date ±, newest/oldest, amount ±) | `PaymentsPanel.tsx:144` | PRESENT | `PaymentsFilters.tsx:5-6` |
| P3 | Saved views (entity `payments`) | `PaymentsPanel.tsx:144` | BURIED | "Views" overflow menu (see R7–R9) |
| P4 | Status filter select (All, Pending, Paid online, Paid offline, Waived, Canceled; recorders see Pending/Paid offline only) | `PaymentsPanel.tsx:151-157` | CHANGED | Tabs: To collect, Paid online, Paid in person, Waived, Cancelled, All. The active tab shows a count, and recorder restriction is kept (`PaymentsPanel.tsx:94-101, 119`). |
| P5 | Due filter (Upcoming, Due today, Overdue; picking one forces Pending) | `PaymentsPanel.tsx:146-150` | BURIED | Filters popover ▸ "Due" segmented control, shown only on the To collect tab (`PaymentsFilters.tsx:11-13`) |
| P6 | Subject filter | `PaymentsPanel.tsx:158-164` | BURIED | Filters popover (`PaymentsFilters.tsx:14-19`) |
| P7 | Columns: Subject, Type, Status, Due, Amount, Refunded, Received (+ "(corrected)"), Created | `PaymentsPanel.tsx:92-105` | CHANGED | Type is merged under Subject as a second line, so the `subject_type` column key is gone and saved column choices that included it silently drop it. Status is a pill, Created is relative, and Corrected is a pill (`PaymentsRows.tsx:14-20`). |
| P8 | Column chooser and density (`DataTable listState`) | `PaymentsPanel.tsx:204-213` | PRESENT | `PaymentsPanel.tsx:123-124` |
| P9 | Row selection + bulk **Mark offline** / **Waive** (only when every selected row allows it) | `PaymentsPanel.tsx:166-175` | PRESENT | `ListLayout` bulk bar "Mark paid in person" / "Waive" (`PaymentsPanel.tsx:102-104, 121`) |
| P10 | Row **Mark offline** → settlement receipt (method, reference, received at) | `PaymentsPanel.tsx:115-117, 176-190` | PRESENT | Inline "Mark paid" (`PaymentsRows.tsx:31`). `SettlementDialog` is now a modal `FlowLayout` with an inline error. |
| P11 | Row **Waive** (subject authority) | `PaymentsPanel.tsx:118-120` | BURIED | Row overflow (`PaymentsRows.tsx:24`) |
| P12 | **Correct receipt** (amend the settlement, append-only) | `PaymentsPanel.tsx:123-127, 191-199` | BURIED | Row overflow (`PaymentsRows.tsx:25`), then the same `SettlementDialog` titled "Correct the receipt" |
| P13 | **Refund** / **Release deposit** dialog (amount, reason, offline method/reference/date, refund history) | `PaymentsPanel.tsx:128-132, 215-223` | BURIED | Row overflow (`PaymentsRows.tsx:26`). The dialog keeps its fields; its submit label is now "Refund <amount>". |
| P14 | **Correct refund #N** (manual refunds) | `PaymentsPanel.tsx:133-135, 224-226` | BURIED | Row overflow (`PaymentsRows.tsx:27-29`) |
| P15 | 409 "already reconciled" conflict message + refetch | `PaymentsPanel.tsx:76-81, 201` | PRESENT | Warn callout (`PaymentsPanel.tsx:156`) |
| P16 | Mutation, amend and load errors | `PaymentsPanel.tsx:200-203` | PRESENT | `PaymentsPanel.tsx:114-115, 155-157` |
| P17 | Pagination (24 per page) | `PaymentsPanel.tsx:214` | PRESENT | `PaymentsPanel.tsx:122` |
| P18 | Permission gates: `paymentAccess` record/waive/refund per subject, and `forRecording` mode | `paymentAccess.ts`, `PaymentsPanel.tsx:37-38` | PRESENT | Unchanged |
| P19 | Selection resets when filters or the makerspace change | `PaymentsPanel.tsx:52` | PRESENT | `PaymentsPanel.tsx:52` |

**Payments: PRESENT 9, BURIED 8, CHANGED 2, MISSING 0.**

---

## 5. Notifications (inbox + announcement composer)

Old: `panels/NotificationInbox.tsx`, `notifications/PersonalInbox.tsx`, `BroadcastComposer.tsx`.
New: the same files (`BroadcastComposer.tsx` is unchanged).

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| N1 | Inbox rows: family, date, title, full summary, unread highlight | `PersonalInbox.tsx:56-64` | PRESENT | `PersonalInbox.tsx` `ListRow`, grouped by Today/Yesterday/Earlier/Older. The summary is clamped to 2 lines and expands with "Read message". |
| N2 | Unread count | `PersonalInbox.tsx:40` | PRESENT | Header meta, the Unread tab count and the sidebar Inbox badge |
| N3 | "Unread only" checkbox | `PersonalInbox.tsx:42-43` | CHANGED | Unread/All tabs, default All (`PersonalInbox.tsx:46`) |
| N4 | Family filter (11 families) | `PersonalInbox.tsx:44-49` | BURIED | Filters popover (`PersonalInbox.tsx:76`) |
| N5 | Mark all read | `PersonalInbox.tsx:50-51` | PRESENT | Header primary (`PersonalInbox.tsx:73`) |
| N6 | Open link (internal paths only) | `PersonalInbox.tsx:62` | PRESENT | `PersonalInbox.tsx:93`. Opening now also marks the row read. |
| N7 | Mark read per row | `PersonalInbox.tsx:63` | PRESENT | `PersonalInbox.tsx:94`. Clicking the row also marks it read. |
| N8 | Previous/Next paging driven by `next`/`previous` | `PersonalInbox.tsx:66-68` | CHANGED | Numbered `Pagination` that assumes `pageSize: 24`. This is only correct if the inbox endpoint pages at 24. |
| N9 | 60-second auto-refresh | `PersonalInbox.tsx:29-31` | PRESENT | Unchanged |
| N10 | **Member announcement composer**, inline on the page (gated on `manage_members` + `membership.broadcasts`) | `NotificationInbox.tsx:7` | BURIED | Header secondary "Send announcement" opens a modal (`NotificationInbox.tsx:11-14`). On mobile it is in the header overflow. |
| N11 | Composer fields: Plan, Plan status (current/lapsed), Certification, Title (required, 200), Message (required, 12000); Send; "queued for N eligible members" | `BroadcastComposer.tsx:26-38` | PRESENT | Same component inside the modal |
| N12 | Load and mutation errors | `PersonalInbox.tsx:54` | PRESENT | Layout error state with retry, plus an ErrorBlock |

**Notifications: PRESENT 8, BURIED 2, CHANGED 2, MISSING 0.**

---

## Hard-rule verification (UI flow)

| Rule | Compact path | Guided path | Verdict |
|---|---|---|---|
| A reviewed request cannot be issued without a **box QR scan + issue photo** | `QueuesAssignIssueModal.tsx` `submitAssign`: box code, `evidenceId`, kits and exact asset scans. The only change is the `Modal`→`RequestFlowDialog` wrapper. | `HandoverWizard.tsx` `ready` = box + borrower check + evidence + items/assets + kits. "Confirm issue" is disabled until it passes, including in the new Compact view. | **Enforced** |
| Self/direct handout cannot be issued without **issue evidence + an eligible tool** | `DirectLoans.tsx:141-147` `canIssue` | `DirectHandoverWizard.tsx` `ready` | **Enforced** |
| Hardware cannot be returned without a **return photo + remark** | `QueuesReturnRequestModal.tsx` `submitReturn`; for direct loans, `DirectLoanReturnModal.tsx` `canSubmit` + `useDirectLoanReturn.submitReturn` | `HandoverWizard.tsx` `ready` requires `remark.trim()` in return mode | **Enforced** |

Caveat that is unchanged from the old version: the compact `BoxCodeField` still accepts a container picked from the
dropdown or typed manually as well as a scan. The guided `HandoverBoxScan` resolves the QR and checks its makerspace.
The backend `assign-box` remains the authority.

---

## Totals

| Page | PRESENT | BURIED | CHANGED | MISSING |
|---|---|---|---|---|
| Dashboard | 6 | 2 | 3 | 0 |
| Requests | 17 | 16 | 7 | 1 |
| Direct handout | 9 | 11 | 2 | 0 |
| Payments | 9 | 8 | 2 | 0 |
| Notifications | 8 | 2 | 2 | 0 |
| **Total (105)** | **49** | **39** | **16** | **1** |

---

## Restore list (severity-ordered)

The Yuyu rule applied below: one header primary; frequent actions visible inline on the row; rare actions in the overflow.

### High

1. **Request queue visibility regression (R3).** `visibleRequestTabs` in `panels/requestTabs.ts:6-9` gates
   Ready, Active and History on `issue_request`, and Pending on `accept_request`. Restore the old rules from
   `RequestQueues.tsx:95, 106, 117, 128` (d3e5ed29): Pending for non-handout actors; Ready and History for
   everyone with the Requests tab (`canSeeHardware`); Active for non-handout actors. At minimum, Active must be
   visible to `return_request` holders, because without it a returns role cannot reach the only place a reviewed
   loan is returned. If tabs must stay action-gated, gate per tab on the action that tab's work needs:
   Pending on `accept_request || reject_request`, Ready on `issue_request || assign_box`, Active on
   `return_request || issue_request`, and History on any hardware action. Add a test next to `requestTabs.test.ts`.
2. **Accept / Reject inline on Pending rows (R23, R25).** Old: `PendingActions` (`QueuesDisplay.tsx:7`), which put
   Accept, Reject and Set due on the row. New: `QueuesList.tsx:49` hard-codes a "Review" button for pending rows.
   Render `primary(row)` there instead (Accept is already returned by `RequestQueues.tsx:157`). Add `{ label: "Reject",
   tone: "danger" }` to the pending `menu` (`RequestQueues.tsx:165-169`) so Reject is one overflow click away. Keep
   "View details" in the overflow and row click for review. Accept is the most frequent pending action.
3. **Renew loan on Active rows (R31).** Old: `StaffLoanRenew` inline per row (`RequestQueues.tsx:212`). New: it exists
   only in the drawer via `extra`. Add a "Renew loan" item to the active-tab `menu` (`RequestQueues.tsx:168`) that calls
   the same `/admin/makerspace/<id>/loans/<rid>/renew` mutation. Alternatively, render `extra?.(row)` in the row `right`
   slot (`QueuesList.tsx:50-51`). The overflow is the Yuyu-correct home.
4. **Direct-handout counter form (H2–H10).** Old: the full form was always on the page (`DirectLoans.tsx:208-261`). New:
   New handout → wizard → "Compact view". Worse, the **walk-in member form, witnessed-waiver button and container
   field exist only in compact view**; the guided wizard sends `container_id: null` and cannot create a walk-in.
   Options, from least to most work: (a) make the wizard remember the last view (Guided or Compact) in
   localStorage, so desk staff land in the form; (b) add the borrower extras (`WalkInMemberForm` and the witnessed
   waiver from `DirectLoanIssueFields.tsx:14-86`) to guided step 0, and `DirectLoanContainerField` to step 1.
   (b) is required for parity of the guided path.

### Medium

5. **Dashboard tiles hidden after four (D1).** `DashboardLayout.tsx:23, 31` collapses everything past `stats.slice(0, 4)`.
   Because `DashboardPanel.tsx:28-30` already ranks attention-first, open "Everything else" by default when any
   overflow stat has `tone: "attention"`, or render all attention tiles inline and collapse only neutral ones.
6. **Capabilities that exist only in the compact request forms (R27, R29).** "Reject broken units" with needs-fix/remove
   disposition (`QueuesAssignIssueModal.tsx:118-119`) and the per-asset "Not returned now" partial return
   (`QueuesReturnRequestModal.tsx:135`) are not in `HandoverWizard`. For most staff they now sit behind
   overflow ▸ "Assign + issue" or "Compact return". Either add both to the wizard's Items step (`HandoverItems.tsx`), or
   rename the overflow items so the capability is discoverable: "Issue with broken units…" and "Partial return…".
7. **Request rows lost scan-at-a-glance information (R15–R20).** Damaged/missing/to-fix flags, shelf locations and
   rejection reasons moved into the drawer. Add a danger `StatusPill` ("2 damaged · 1 missing") to the row `right`
   slot when any item has those quantities. On the Ready tab, add shelf locations to the row meta
   (`QueuesList.tsx:45`), because staff need them to fetch items before handover.
8. **Failed kiosk handovers are easy to miss (R36).** The panel now sits collapsed under the paginated list. Use the
   `ListLayout` `callout` slot on Requests: when the unresolved count is above 0, show a warn banner ("N failed kiosk
   handovers need review") whose action scrolls to or expands the section. The callout is one per screen, as
   `CalloutProps` documents.
9. **Request tab counts (R2).** Pass `count` on the Pending and Ready tabs (`RequestQueues.tsx:190`). The values
   `pending_requests` and `awaiting_issue` are already in the `["dashboard", id]` cache that `StaffShell.tsx:25-27`
   reads.

### Low

10. **Saved-view menu labels** "Save current view?" and "Manage views?" (`SavedViewsMenu.tsx:44-45`) should read "Save
    current view…" and "Manage views…".
11. **Search hint (R5).** Restore the old placeholder text "Search requester name, email, phone, or purpose" as the
    search label or placeholder (`RequestQueues.tsx:197`).
12. **Setup checklist hidden on dashboard error (D5).** Render `progress` outside `QueryContent` in `DashboardLayout.tsx:26-29`
    so a counts failure doesn't hide onboarding.
13. **Tile danger tone (D4).** `StatCard` supports `tone: "danger"`. Map tiles with `tone === "danger"` and value > 0 to it
    in `DashboardPanel.tsx:53` to restore the overdue/problem/out-of-stock signal.
14. **Job tray on mobile (D10).** Also show `JobTrayPill` in `MobileTopBar` while any job is running, so it isn't buried
    in the drawer.
15. **Inbox paging (N8).** Use `rows.data.next`/`previous`, or confirm the inbox endpoint pages at 24. Otherwise the
    numbered pager can show the wrong page count.
16. **Payments Type column key (P7).** Keep a hidden-by-default `subject_type` column, or migrate saved views, so
    existing column selections don't silently drop it.
17. **Payments Due filter (P5).** "Overdue" is a frequent desk filter. Consider rendering the Due segmented control
    inline on the To collect tab instead of inside the Filters popover.
18. **Hygiene.** A stray U+FEFF (BOM) now sits mid-file on line 2 of `panels/QueuesModals.tsx` and `panels/LoanTimeline.tsx`,
    because the new import was prepended above the old BOM. It is harmless whitespace to TS, but remove it.
