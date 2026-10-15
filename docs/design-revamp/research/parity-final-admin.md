# Final parity audit: admin, settings and platform

Audited 2026-10-16. OLD = `d3e5ed29`, NEW = HEAD of `feature/design-revamp` (`b348ee18`). Read-only: no app code was edited, no dev server run, nothing committed. Scope: audit log, accountability, reports (exports, schedules), members roster, member cards, claim codes, admission review, membership plans, staff and roles, makerspace picker, makerspace settings and every child editor, modules, platform admin, data exports, backups, tenant migration, organizations. Earlier checklist: `docs/design-revamp/research/parity-admin.md`.

## Summary

**166 capabilities checked: 99 PRESENT, 44 BURIED, 23 CHANGED, 0 MISSING.** No P0. One P1, nine P2, a P3 tail.

**Earlier restore list (`parity-admin.md`, 93 candidate items across its 7 parts): 51 verified fixed in HEAD, 13 accepted as a deliberate pattern (the earlier audit itself said no change needed), 1 informational, 28 still open (all P1 to P3 as listed below).** The restore lanes landed in `f0072148`, `a1847395`, `3c3e56f0`, `f41d0505`, `ee842122`, `908fabb1`, `10c35339`, `fda5aca4`.

Nothing is MISSING: every old capability in this area is reachable from a page. The earlier audit's four MISSING items (export-any-report grid, space code in chrome, delivery channel name, platform panel descriptions) are all restored.

### Mechanical checks that back the table

- **Gates unchanged.** `staffAccess.ts` has no diff against old. The `activeTab ===` render conditions in `StaffTabContent.tsx` and `StaffPlatformTabContent.tsx` diff clean (only `makerspaceName` was added to the payments props). `StaffApp.tsx` is unchanged. Every tab-level gate (`canViewAudit`, `canViewFinance`, `membership` module, `isSuperadmin`, `canManageMakerspace`, `staff.invitations`, `platform_hosting`) matches old.
- **No lost API call.** The set of `/admin`, `/auth`, `/platform`, `/member`, `/control` path literals in old vs new differs only by template-variable renames in front-desk and inventory files and by the settings page's own `archive-requests` read (same path the archive panel already used). Every `method:` and `body: JSON.stringify(...)` shape in the admin directories is identical (only added undo toasts duplicate a few).
- **No orphaned component.** Walking imports from `main.tsx`, the only new unreachable source files are `QueuesDisplay.tsx`, `QueuesSkeleton.tsx` and `StationUnlockForm.tsx` (front desk and kiosk, not this area) and the layout gallery. Only six files were deleted since old: the dock, dock popover, header, nav icons, `useDockAnchor` and `PublicInventoryHeader`. All 42 `STAFF_TAB_KEYS` appear in `SIDEBAR_SECTIONS` (`sidebarSections.ts:13-23`).
- **No URL parameter dropped.** Every `.get("...")`/`.set("...")` key used in old still exists; new keys were only added (`section`, `template_view`, `delivery_view`, `org`).
- **Phones.** The only `phone: "hidden"` / `max-md:hidden` in the app is the inventory quantity columns (`InventoryColumns.tsx:20`), outside this area. Header `secondary` actions are hidden below md only because they are re-listed in the overflow menu there (`PageHeader.tsx:10,29`), so nothing drops. Tab bars scroll (`Tabs.tsx`). The reports aside is `hidden xl:block` but a `<select>` picker replaces it below xl (`OperationsReportNavigation.tsx:19-31`).
- **Destructive confirms.** Nothing lost a confirmation. Gained: API client rotate/delete, saved report view delete, invitation revoke (staff and organization), room removal, kiosk station disable, disclosure approval revoke. Still without a confirm, same as old: saved-view delete (staff lists), payment Waive, Restore access on Accountability, waiver deactivate, term cancel, module uninstall (now with an Undo toast), Superadmin-access switch.
- Vitest was started on `src/features/staff` and `src/features/notifications` but the background run did not return output, so no test result is claimed.

## Restore list

### P0

None. No capability is unreachable, no destructive action lost its confirmation, and no gate changed. (The earlier audit's two P0-class items, the email template Save firing on an empty draft and loan charge settings hiding behind the payments-rail query, are both fixed: `EmailTemplateEditor.tsx:163-165`, `MakerspacePaymentSettings.tsx:88-90`.)

### P1

**1. Errors from drawer actions on a member are invisible.**
- Lost: the red error line for a failed role change, Can refer / Can verify toggle or Verify/Unverify. Old rendered it beside the roster (`MembersPanel.tsx:90,144`). NEW those actions live in the member drawer (`MemberRow.tsx:51-56`, `DetailLayout presentation="drawer"` at `:48`), but the error still prints in the list body behind it (`MembersPanel.tsx:98,170`).
- Why it matters: a rejected role change (for example a role above the actor's ceiling) just snaps the select back with no message. Role and verification changes are routine desk work.
- Fix: give `MemberRow` an `error?: string` prop and render it as `<p role="alert" className="text-sm text-danger">` at the top of the drawer `main` (`MemberRow.tsx:50`). In `MembersPanel.tsx:128-139` pass `membershipErrorText(changeRole.error ?? capabilities.error ?? verify.error)` (only one drawer can be open).

### P2

**2. Reports landing view has no KPIs.** Old showed the seven inventory StatCards, the bar and the table above everything (`OperationsReports.tsx:153-184`). NEW only on the "Summary" report (`OperationsReports.tsx:183-214`), while the default is most-lent (`:56`). Fix: default `selectedReport` to `"summary"` when the catalog lists it (set it in the `useEffect` at `:74-78` before falling back to the first available report).

**3. A catalog failure blanks the whole Reports page.** Old kept printer and machine-service panels, which do not need the catalog, and showed the error inline (`OperationsReports.tsx:145`). NEW passes the catalog state to `DetailLayout` (`:119-121`), so the `printingOnly` print-manager view loses its panels too; the inline message at `:175` is unreachable. Fix: pass `state={{ status: "ready" }}` and keep the inline message plus a Retry.

**4. Payment reconciliation shows two tables.** `payment-reconciliation` is not in any specialist list (`OperationsReportSelection.tsx:5-7`), so the generic preview (`SelectedReportPreview.tsx:25-35`) renders next to `OperationsReportsPayments`. Fix: add it to `FINANCE` at `OperationsReportSelection.tsx:6` (the generic panel is already suppressed when a specialist owns the key, `:30`).

**5. Card status (Active / Revoked) has no visible state.** Old: visible toggle buttons (`MemberCardsPanel.tsx:55-71`). NEW: a SegmentedControl in the closed Filters popover with no badge (`MemberCardsPanel.tsx:71-73`). Fix: pass `activeCount: status === "revoked" ? 1 : 0` in `filters`, or move the control to `filters.toolbar`.

**6. Delivery log filters are hidden and show no state.** Old: five inline filters (`DeliveryLogScreen.tsx:40-54`). NEW: all inside a closed popover, including the Status control, with no `activeCount`, `chips` or `onClear` (`DeliveryLogScreen.tsx:77-91`). Fix: add the three props (one chip per non-empty filter calling `update(key, "")`), and lift the Status SegmentedControl into `filters.toolbar` or `views`. The "Show failed" callout (`:62-71`) is a partial shortcut.

**7. Live email preview is not visible while editing.** Old: always rendered under the form (`EmailTemplateEditor.tsx:204`). NEW: separate Preview tab (`EmailTemplateEditor.tsx:168-171`), and its error text is generic (`EmailTemplateEditorParts.tsx` `PreviewPane`). Template-syntax errors are what authors need. Fix: render `PreviewPane` in the `aside` below `MergeFields` at xl (`:174`), keep the tab below xl, and show `preview.error.message`.

**8. API client Legacy v1 warning and scopes are hidden in the drawer.** Old: shown on the row (`ApiClientListCard.tsx:148-149`). NEW: count pill only (`ApiClientListCard.tsx:116`), warning `Callout` inside the drawer (`:127`). Fix: add a warn `StatusPill` "Legacy v1" in the row `right` slot when `hasLegacy` (`:108`) and show the first few scope labels in `meta`.

**9. Dashboard "failed emails" link lands unfiltered (pre-existing, not a regression).** `dashboardLinks.ts:15` sends `status=failed&recent_days=7`, but `DeliveryLogScreen.tsx:35-37` keeps filters in local `useState` (old was the same, `DeliveryLogPanel` to `DeliveryLogScreen`). Fix: back `filters` and `page` with `useUrlListState` so dashboard links arrive filtered.

**10. Settings-family tabs are two clicks away.** Email templates, Delivery log, API access, Data export, Backups, Usage, Modules and Migration appear in the sidebar only after the Settings family is open (`sidebarSections.ts:50-58`); old reached each from the Admin popover in one click. Staff & roles was already pinned (`:54`). Optional fix: list these children on the General settings landing, or keep the family open for `manage_makerspace` actors.

### P3 (grouped)

- **Generic error copy replaced server messages:** accountability (`opsPresentation.ts:33-37`), member cards, exports, usage, modules, platform panels (`adminPresentation.ts:4-8`), report panels (`OperationsReportState.tsx:41-44`), settings editors (`SettingsQueryState.tsx:10-14`), mute matrix, channel preferences. Audit, Users and delivery already append the message. Fix: append `error.message` / `StructuredApiError.detail` in `opsQueryState`, `adminQueryState` and `SettingsQueryState`.
- **Pagination hides the total on a single page** (`Pagination.tsx:16-18`); the audit "X total" read-out is gone for small sets.
- **Theme editor wording:** a contrast failure shows "Enter a #RGB or #RRGGBB colour" (`MakerspaceThemeSettings.tsx:83`) where old said "Choose a lighter or darker primary fill"; derived-link read-out dropped.
- **Reminders sit under Lending** (`MakerspaceSettingsPanel.tsx:171`); Lending and other sections render empty when their modules are off. "View public site" shows even when the public site is off (`:207`).
- **Terms drawer:** a terms-load error hides the Start-term form (`MemberTermsDialog.tsx:54`; old kept the form).
- **Members "Requests" tab badge** is the total request count, not pending (`MembersPanel.tsx:106`).
- **printingOnly Reports:** the aside nav and phone picker render but do nothing (`OperationsReports.tsx:127,132`); phone picker also drops `unavailable_reason` (`OperationsReportNavigation.tsx:24`). Report tables lost the old height cap (`OperationsReportTable.tsx:24-34`).
- **Platform dashboard links** are plain `<a href>` (`PlatformDashboardPanel.tsx:36,42,59`); old used router `Link` for in-app URLs. Works, but reloads the SPA.
- **Chrome:** no visible unread dot on the phone top bar (`MobileTopBar.tsx:9`, aria-label only); Ctrl+K labels still come from `TAB_LABELS` and differ from the sidebar (`CommandPalette.tsx:33-36` vs `sidebarSections.ts:24-28`); the setup checklist is hidden while dashboard data loads (`DashboardLayout.tsx:44` is inside `QueryContent`); non-superadmin multi-space menu has no current-space marker (`StaffShell.tsx:49`).
- **Settings details:** Space pack profile picker error hides the select (`SpacePackProfilePicker.tsx:13`); Stripe application-fee field has an aria-label but no visible label (`PlatformStripeConnectPanel.tsx:86`); archive request history and Withdraw are one click deeper in the modal (`MakerspaceSettingsPanel.tsx:213-215`); Superadmin access still has no confirm on an action the superadmin cannot undo (as old).
- **Organization analytics** can no longer target an organization missing from the user's list (`OrganizationAnalyticsPanel.tsx:24-50`, old `:27-38`).
- **Accountability** opens on Overdue even when the actionable tab is Repeat offenders or Restricted; offender figures are one meta string rather than columns (`AccountabilityPanel.tsx:91-94`). Report schedules cannot be deep-linked and show no count on the "Schedule…" button (`OperationsReports.tsx:124`).

## Earlier restore list: status of each item

| Earlier part | Items | Fixed | Accepted / info | Still open |
|---|---|---|---|---|
| 1 Audit, accountability, reports | 13 | 5 (audit chips, export grid, timestamp, menu labels, Accountability in sidebar) | 2 | 6 (summary KPIs, catalog error blank page, duplicate payment table, generic errors, pagination total, small presentation nits) |
| 2 Members, cards | 13 | 3 (roster payments, Member details, menu labels) | 5 | 5 (drawer errors, card filter state, requests badge, terms error, generic errors) |
| 3 Staff, picker, chrome | 18 | 11 | 2 | 5 (role delete pending, phone unread dot, setup checklist, label divergence, profile picker) |
| 4 Settings shell and editors | 9 | 4 (parent GET gate, archive pending, safety copy, print badge) | 2 (MFA link, info) | 3 (theme copy, server error text, layout nits) |
| 5 Payments, notifications, integrations | 10 | 9 | 0 | 1 (generic error copy in mute matrix and channel setup) |
| 6 Email templates, delivery log, API | 12 | 5 (Save guard, secret reveal, delivery channel, custom badge, explainer) | 2 | 5 (delivery filters, live preview, legacy v1, generic errors, failed_emails link) |
| 7 Exports, backups, migration, modules, platform, orgs | 18 | 14 | 1 | 3 (generic errors, Stripe fee label, org analytics ID) |
| **Total** | **93** | **51** | **14** | **28** |

## Capability table

Status: PRESENT, BURIED (2+ extra clicks or only in a drawer, tab or overflow where it was visible before), CHANGED (behaviour, copy that carries meaning or default differs), MISSING. Old refs are at `d3e5ed29` (from `parity-admin.md` where the file has not been rewritten); new refs are at HEAD. Paths are under `frontend/src/features/staff/` unless a bare filename belongs to the same folder as the previous row.


### Chrome and navigation

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| All 42 STAFF_TAB_KEYS reachable and gated as before | staffAccess.ts ALL_TABS; old StaffDock TAB_GROUPS | sidebarSections.ts:13-23, StaffShell.tsx:30-31; staffAccess.ts is byte-identical to old; StaffTabContent / StaffPlatformTabContent `activeTab ===` gates diff clean | PRESENT | Every key is in SIDEBAR_SECTIONS. No gate looser or stricter. |
| Accountability reachable | old Insights popover | sidebarSections.ts:19 (visible Insights item) | PRESENT | Restored from "More" (a1847395). |
| Staff & roles one click while Settings family is collapsed | StaffDockPopover Admin group | sidebarSections.ts:50-58 | PRESENT | Pinned beside the "Settings" item. |
| Settings-family tabs (emailtemplates, email-logs, api, exports, backups, usage, modules, migration) | Admin dock popover, 1 click | sidebarSections.ts:21,55-58 (children appear only once a Settings-family tab is active) | BURIED | Two clicks (Settings, then the child) from any other tab; also in the Ctrl+K palette. Infrequent, so P2. |
| Superadmin "Switch makerspace" | StaffHeader.tsx:73-77 (primary button, `isSuperadmin && !singleTenantLocked`) | StaffShell.tsx:48-51 workspace menu, :62 user menu | CHANGED | Moved into workspace switcher and user menu. Same gate (menu is empty when singleTenantLocked). |
| Non-superadmin multi-space switch | StaffHeader.tsx:51-64 select | StaffShell.tsx:49 workspace menu | CHANGED | Select became a menu; no current-space marker in the list. |
| Space code (public_code or slug) and role read-out | StaffHeader.tsx:41-43 | StaffShell.tsx:52 | PRESENT | Restored (f0072148). |
| Public inventory link | StaffHeader public link | StaffShell.tsx:47,50,59 | PRESENT | Menu and footer link. |
| Authenticator and recovery-code page (/mfa) | MakerspaceSettingsPanel.tsx:103 | StaffShell.tsx:62 user menu "Account & two-step sign-in" | CHANGED | Moved off the settings page. |
| Theme toggle, Sign out | StaffHeader | UserMenu.tsx:12, StaffShell.tsx:62 | PRESENT | Also in the phone top bar user menu (MobileTopBar.tsx:15). |
| Unread inbox count | StaffDock.tsx:208-212 | StaffShell.tsx:34 sidebar badge; MobileTopBar.tsx:9 aria-label only | CHANGED | No visible badge on phones until the drawer is opened. P3. |
| Job tray / running jobs | StaffWorkspace.tsx:136 | StaffShell.tsx:61,65 | PRESENT | Sidebar pill at lg+, inline pill below lg. |
| Ctrl+K command palette | CommandPalette.tsx | StaffShell.tsx:60,68 | PRESENT | Labels still come from TAB_LABELS ("Dashboard") while the sidebar says "Home". P3. |
| Setup checklist | StaffWorkspace old :137 (independent of dashboard data) | StaffWorkspace `progress` prop -> DashboardLayout.tsx:44 | CHANGED | Now inside QueryContent, so hidden while dashboard data loads or errors. P3. |
| Superadmin makerspace picker: list, search, "Superadmin access: Off" badge, sign out, control-plane link | MakerspacePicker.tsx:21-76 | MakerspacePicker.tsx:38-58, controlPlaneUrl :11 | PRESENT | Real link and old copy restored (3c3e56f0). Same as old: no platform dashboard or org links on the picker. |

### Audit log (tab audit)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Audit list with sort Newest/Oldest/Action (only when makerspaceId) | AuditLog.tsx:46, ListViewControls.tsx:11 | AuditLog.tsx:36 | PRESENT | Unchanged condition. |
| Saved views: pick, save (name, share), manage (share, delete) | SavedViewsMenu.tsx:35-51 | SavedViewsMenu.tsx:40-67 | BURIED | Behind a "Views" overflow menu. Labels now read "Save current view…" / "Manage views…" (:44-45). Delete still has no confirm, as before. |
| Seven filters (makerspace, action, actor, target type and id, from, to) | AuditLogFilters.tsx:50-56 | AuditLog.tsx:38 popover; chips AuditLog.tsx:27-28,38 | BURIED | In the Filters popover, but active filters now show as removable chips (a1847395). |
| Verify these entries: start, status poll, verdict, coverage, retry | AuditVerificationStatus.tsx:62-118 | AuditLog.tsx:31 header meta | PRESENT | Unchanged logic. |
| Row: action label, actor, target, timestamp | AuditLog.tsx:54-58 | AuditLog.tsx:42-44 | PRESENT | Absolute time shown with relative beneath (:44). |
| Raw action key and projected metadata, "(some details withheld)" | AuditLog.tsx:55,59 | AuditLogDetails.tsx:10-16 | BURIED | Per-row "View details" disclosure; present in the phone card (Details column). |
| List error text | AuditLog.tsx:50 (server message) | AuditLog.tsx:32 (includes server message) | PRESENT | Fixed. |
| Pager "Page N - X total" | AuditLog.tsx:63-73 | AuditLog.tsx:47, Pagination.tsx:16-18 | CHANGED | Renders nothing for a single page, so the total disappears for small sets. P3. |

### Accountability (tab accountability)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Four sections visible together | AccountabilityPanel.tsx:57-182 | AccountabilityPanel.tsx:21-27,68-74 (4 StatCards + 4 tabs, default Overdue) | CHANGED | One list at a time. Accepted pattern; stat cards link to tabs. |
| Deep link section=overdue / problems | AccountabilityPanel.tsx:20-21 | AccountabilityPanel.tsx:21-27 useOpsTabs("section") | PRESENT | Still resolves. |
| Overdue loans list with days overdue | AccountabilityPanel.tsx:61-78 | AccountabilityPanel.tsx:76-81 | PRESENT | Adds an "Open loan" link. |
| Problem report triage (outcome, quantities, note, Save) | ProblemReportCard.tsx:19-63 | ProblemReportCard.tsx:30-66 | PRESENT | Full note behind a "Problem details" toggle (:31-33). |
| Repeat offenders list and account-less callout | AccountabilityPanel.tsx:93-159 | AccountabilityPanel.tsx:86-99 | BURIED | Tab; figures in one meta string, no columns. |
| Restrict (superadmin) reason modal | AccountabilityPanel.tsx:134-144,185-214 | AccountabilityPanel.tsx:95-96,108-138 | PRESENT | Reason still required. Gate `isSuperadmin` unchanged. |
| Restore access (superadmin), no confirm | AccountabilityPanel.tsx:146,172-176 | AccountabilityPanel.tsx:97,104 | PRESENT | No confirm before or after. |
| Restricted requesters list | AccountabilityPanel.tsx:161-181 | AccountabilityPanel.tsx:101-104 | BURIED | Tab "Restricted". |
| Load error shows server message | AccountabilityPanel.tsx:59 | opsPresentation.ts:33-37 | CHANGED | Generic "Couldn't load accountability". P3. |

### Reports (tab reports)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Date range, presets, grain, All-makerspaces toggle (superadmin) | OperationsReports.tsx:107-142 | OperationsReports.tsx:133-172 | PRESENT | New 7/30/Quarter presets. |
| Report picker (desktop aside, phone select) | OperationsReports.tsx:115-125 | OperationsReportNavigation.tsx:19-31 | PRESENT | Phone select disables unavailable reports without the reason text. P3. |
| Retention months, payment status, charge type filters | OperationsReports.tsx:146-149 | OperationsReports.tsx:176-180 | PRESENT |  |
| Saved report views (name, share, columns, open, delete) | ServerReportViews.tsx:26-43 | OperationsReports.tsx:181-182 | PRESENT | Delete now confirms. |
| Inventory summary KPIs, bar, table | OperationsReports.tsx:153-184 | OperationsReports.tsx:183-214 | BURIED | Only when "Summary" is selected; default report is most-lent (:56), so the landing view has no KPIs. P2. |
| Export the selected report (primary + CSV/XLSX) | OperationsReportExports.tsx:54-68 | OperationsReports.tsx:122-126 | PRESENT | Primary is labelled "Export" without its format. |
| Export any report (grid) | OperationsReportExports.tsx:54-68 (inline grid) | OperationsReports.tsx:126 overflow "Export any report", drawer :234-237 | BURIED | Restored via overflow-to-drawer (f0072148). |
| Export error with server message | OperationsReportExports.tsx:69-73 | OperationsReports.tsx:233 | PRESENT | Restored. |
| Scheduled reports: list, run now, pause/resume, edit, delete (confirm), new | ReportSchedules.tsx:71-160 | OperationsReports.tsx:124,238-240 drawer; ReportSchedules.tsx unchanged | BURIED | Header "Schedule…" opens a drawer; edit/pause/delete in row menu; not deep-linkable. Gate `!printingOnly && !aggregate && reportsEnabled` unchanged. |
| Schedule form (15 fields incl. thresholds) | ReportScheduleForm.tsx:134-211 | ReportScheduleForm.tsx (unchanged) | PRESENT |  |
| Specialist panels (hardware x9, finance x4, coverage x9, members, payments, FabLab, machines, events, bookings, maintenance) | OperationsReports.tsx:187-215 | OperationsReportSelection.tsx:5-32 | BURIED | Shown one at a time by selection instead of stacked. All still reachable from the picker. |
| Selected-report generic preview + definition/limitations | SelectedReportPreview.tsx:6-33 | SelectedReportPreview.tsx:25-35 | CHANGED | payment-reconciliation is not in the specialist set (OperationsReportSelection.tsx:5-7), so the generic table renders beside the specialist table. P2. |
| Catalog error / empty catalog | OperationsReports.tsx:145,94-215 (inline; other panels still render) | OperationsReports.tsx:119-121 (DetailLayout state replaces the page) | CHANGED | A failed catalog hides printer and machine-service panels that never needed it. P2. |
| printingOnly mode | OperationsReports.tsx:98-103,188-215 | OperationsReports.tsx:122-129 | CHANGED | Aside nav and phone picker still render and do nothing. P3. |
| Per-panel error text | OperationsReportState.tsx:41 | OperationsReportState.tsx:41-44 | CHANGED | Generic copy, no server message. P3. |
| Report tables (scroll box max-h-80) | OperationsReportTable.tsx (old) | OperationsReportTable.tsx:24-34 | CHANGED | No height cap. P3. |

### Members (tab members)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Roster list, search, sort (Username, Username desc, Status) | MembersPanel.tsx:48-51,96-118 | MembersPanel.tsx:56-59,120-139, ListViewControls.tsx:11-13 | PRESENT | Row is a ListRow (MemberRow.tsx:33). |
| Roster status filter (All / Active / Revoked) | MembersPanel.tsx:97 (visible select) | MembersPanel.tsx:118 (FilterPopover, `activeCount` wired) | BURIED | Count badge shows when set. |
| Roster saved views | SavedViewsMenu.tsx:35-51 | SavedViewsMenu.tsx:40-67 | BURIED | Views menu; labels fixed. |
| Pending payment amount + Mark offline + Waive on the row (canViewFinance) | MembersPanel.tsx:173 | MemberRow.tsx:39-40 (pending only) | PRESENT | Restored (f0072148). Settled payments show only in the drawer (MemberRow.tsx:60). "Waive" sits in a "Payment actions" overflow (PaymentReconcileActions.tsx), no confirm, as before. |
| Record witnessed acceptance | MembersPanel.tsx:176 | MemberRow.tsx:41 | PRESENT | Same gate (active && waiver_required && !waiver_current). |
| Verify / Unverify | MembersPanel.tsx:176 | MemberRow.tsx:44 overflow, :55 drawer | BURIED |  |
| Terms dialog (plan select, start term, cancel term) | MembersPanel.tsx:146,176; MemberTermsDialog.tsx:58-109 | MemberRow.tsx:44,56; MemberTermsDialog.tsx:50-105 | BURIED | Drawer. A terms-load failure replaces the whole drawer including the start-term form (MemberTermsDialog.tsx:54). P3. |
| Can refer / Can verify checkboxes | MembersPanel.tsx:176 | MemberRow.tsx:53-54 (drawer) | BURIED | Click row to open. |
| Role select per member | MembersPanel.tsx:176 | MemberRow.tsx:43,51 (drawer; "Member details" in row menu) | BURIED | Gate `manageable` unchanged. |
| Revoke membership (reason required) | MembersPanel.tsx:116,145,176 | MemberRow.tsx:45,62; MembersPanel.tsx:175 | PRESENT | Reason dialog intact. |
| Member vouchers | MembersPanel.tsx:173 | MemberRow.tsx:59 | BURIED | Drawer only. |
| Errors from role, capability and verify changes | MembersPanel.tsx:90,144 (beside the row) | MembersPanel.tsx:98,170 (list body, behind the open drawer) | CHANGED | A failed role/capability/verify change from the drawer is invisible while the drawer is open. P1. |
| Invite member (email + role) | MembersPanel.tsx:88,124 | MembersPanel.tsx:113,172-174 | PRESENT | Header primary opens a dialog; error shown in dialog. |
| Requests / Invitations tab: state filter, sort, approve (role, plan), decline or cancel with reason, application answers, vouchers, admission payment | MembersPanel.tsx:124-139; MembershipAdmissionReview.tsx:22-33 | MembersPanel.tsx:143-159; MembershipAdmissionReview.tsx:21-33 | BURIED | One click (tab). Tab badge is the total count, not pending count. |
| Invitation requests: invite from request with role, decline | InvitationRequestsSection.tsx:47-88 | InvitationRequestsSection.tsx:47-85 | PRESENT | Under Requests tab. |
| Membership plans: list, create, edit, activate/deactivate, renewal fields | MembersPanel.tsx:141; MembershipPlansSection.tsx:119-173 | MembersPanel.tsx:108,161; MembershipPlansSection.tsx:120-169 | BURIED | Tab, gate `membershipEnabled && canManageMakerspace` unchanged. |
| Present now list | MembersPanel.tsx:142 | MembersPanel.tsx:107,162-168 | BURIED | Tab. |
| Membership waiver publish / deactivate | MembersPanel.tsx:143; MembershipWaiverPanel.tsx:28-31 | MembersPanel.tsx:109,169 | BURIED | Tab, gate `canManageMakerspace` unchanged. Deactivate has no confirm, as before. |
| Settlement dialog (method, reference, received at) | SettlementDialog.tsx:43-98 | SettlementDialog.tsx:42-86 | CHANGED | Inline panel became a modal; button reads "Save receipt". |
| Member claim codes (issue, one-time code + QR, list, revoke) | DirectLoans.tsx:263 | DirectLoans.tsx:227 tab `claim-codes` | BURIED | Owned by the front-desk area audit; present. |

### Member cards (tab cards)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Cards list: number, name, status, prints, photo columns, row select | CardsTable.tsx:34-106 | CardsTable.tsx:29-98 | PRESENT |  |
| Print sheet (selected or all active) | MemberCardsPanel.tsx:72-83 | MemberCardsPanel.tsx:62-63 | PRESENT | Header primary. |
| Row Print | CardsTable.tsx:78-85 | CardsTable.tsx:73-79 | PRESENT |  |
| Row Reissue (reason) and Revoke (warns photo deleted) | CardsTable.tsx:88-93; CardDialogs.tsx:4-114 | CardsTable.tsx:82-84; MemberCardsPanel.tsx:97-126 | BURIED | Row overflow; dialogs intact. |
| Active / Revoked card toggle | MemberCardsPanel.tsx:55-71 (visible buttons) | MemberCardsPanel.tsx:71-73 (inside closed FilterPopover, no `activeCount`) | BURIED | Nothing shows that "Revoked" is selected. P2. |
| Scan a card, issue cards, card layout | MemberCardsPanel.tsx (single page) | MemberCardsPanel.tsx:52-59,64 (tabs cards / issue / scan / layout) | BURIED | Tabs; "Scan a card" also a header secondary. |

### Staff & roles (tab users)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Staff list with makerspace select and role filter | Users.tsx:175-182 | Users.tsx:189-207 (toolbar, outside the query body) | PRESENT | Picker survives a failed list (908fabb1); server message shown (:178,186). |
| Tab reset when switching makerspace | n/a (no tabs) | Users.tsx:176,179 | PRESENT | Never a blank body. |
| Add staff (membership + role) | Users.tsx add flow | Users.tsx:185, AddStaffModal.tsx | PRESENT | Disabled with a reason when no assignable role. |
| Change role | UsersTable.tsx | UsersTable.tsx:44,56-67 | PRESENT | Visible row button. |
| Restore access with confirm | UsersTable.tsx:50-53; Users.tsx | UsersTable.tsx:43; Users.tsx:270-278 | PRESENT | Visible only on non-active rows (restored). |
| Restrict (reason) / Reset password / Revoke role with confirm | UsersTable.tsx:50-53 | UsersTable.tsx:45-49; Users.tsx:240-291 | BURIED | Overflow menu; dialogs and ConfirmDialog intact. |
| Create makerspace (superadmin) and wizard | Users.tsx | Users.tsx:185 secondary; usersModals/CreateMakerspaceModal | PRESENT | Phone: header secondary goes to the overflow menu (PageHeader.tsx:10,29). |
| Roles tab: list, new role, edit, delete with confirm | RoleManager.tsx:54 | RoleManager.tsx:37; RoleEditor.tsx drawer + DangerZone | BURIED | Tab; delete in row menu and drawer. Gate `canManageRoles` unchanged. |
| Role editor: name, actions, machine-scope | RoleEditor.tsx; RoleMachineScopeEditor.tsx | same | PRESENT | Save disabled until capabilities load (new guard). |
| Staff invitations: invite, resend, revoke, copy link | StaffInvitations.tsx:28-47 | StaffInvitations.tsx:28-47 | BURIED | Tab; revoke in overflow now asks to confirm (908fabb1). Expired state shown. |
| Invitations tab gate (`staff.invitations` feature and canManageRoles) | Users.tsx:208 | Users.tsx:173,222 | PRESENT | Unchanged. |

### Makerspace settings: shell and section mounts (tab settings)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Every settings editor renders even if the parent GET /admin/makerspaces/{id} fails | MakerspaceSettingsPanel.tsx:43-46,102-262 (prop fallback, errors never shown) | MakerspaceSettingsPanel.tsx:200-208 (`state: ready`, error as header meta with Retry) | PRESENT | Fixed (10c35339). Each editor falls back to the `makerspace` prop. |
| Section nav (General, Branding & public site, Features, Lending, Membership, Bookings, Machines & materials, Money, Notifications, Email & integrations, Privacy & evidence) | single scroll | MakerspaceSettingsPanel.tsx:154-198; SettingsLayout.tsx:35 (nav when 5+ sections) | PRESENT | Phone: shared jump select (e3441bf0). |
| View public site | n/a | MakerspaceSettingsPanel.tsx:207 | PRESENT | Added. Shows even when the public site is disabled. P3. |
| Superadmin access switch + re-enable block | MakerspaceSettingsPanel.tsx:54,98,141-166 | MakerspaceSettingsPanel.tsx:57-77,122-135 | PRESENT | Safety sentence about platform/database access restored (:126). Still no confirm, as before. |
| Staff email notifications switch | MakerspaceSettingsPanel.tsx:69-80,174-194 | MakerspaceSettingsPanel.tsx:79-105,136-143 | PRESENT | Adds a toast with Undo. |
| Public print status lookup policy (Token only / Email lookup) | MakerspaceSettingsPanel.tsx:82-93,207-228 | MakerspaceSettingsPanel.tsx:107-118,144-153 | PRESENT | Badge tone restored (:145). |
| Archive request: request form, pending card, Withdraw, resolved history | MakerspaceSettingsPanel.tsx:248-251; MakerspaceArchiveRequestPanel.tsx:83-168 (inline) | MakerspaceSettingsPanel.tsx:209-215 DangerZone + Modal; MakerspaceArchiveRequestPanel.tsx | BURIED | Danger zone now says "pending" and relabels to "View pending request" (fda5aca4). Withdraw and history are one click deeper in the modal. Gate `canManageMakerspace` unchanged. |
| General: default loan days, loan policy (loans.enabled), public site, location | MakerspaceGeneralSettings.tsx, MakerspaceLocationSettings.tsx | MakerspaceSettingsPanel.tsx:155-157; MakerspaceGeneralSettings.tsx:88,101-102 | PRESENT | Gates unchanged. |
| Profile and opening hours editor (canManageMakerspace) | MakerspaceProfileSettings.tsx:77 | MakerspaceSettingsPanel.tsx:158; MakerspaceProfileSettings.tsx:81-88 | PRESENT | Save/Discard appear only when changed (SettingsEditorActions.tsx). |
| Branding: registered name, display name, logo, cover | MakerspaceBrandingSettings.tsx:70-134 | MakerspaceBrandingSettings.tsx:65-134 | PRESENT |  |
| Brand theme colours + contrast report | MakerspaceThemeSettings.tsx:63-76 | MakerspaceThemeSettings.tsx:76-87 | CHANGED | Contrast failures show the "Enter a #RGB or #RRGGBB colour" line instead of "Choose a lighter or darker primary fill"; derived-link read-out gone. P3. |
| Public stats toggles | MakerspacePublicStatsSettings.tsx | MakerspaceSettingsPanel.tsx:161 | PRESENT |  |
| Subdomain (platform_hosting === true) and custom domain | MakerspaceSettingsPanel.tsx:239-246 | MakerspaceSettingsPanel.tsx:162-163 | PRESENT | Gate unchanged. |
| Features and Space packs (canManageMakerspace && packs.import; profile picker superadmin) | MakerspaceSettingsPanel.tsx:122-128 | MakerspaceSettingsPanel.tsx:166-168 | PRESENT |  |
| Booking and event reminders | MakerspaceSettingsPanel.tsx:232 | MakerspaceSettingsPanel.tsx:171 | CHANGED | Sits under "Lending" instead of Bookings. P3. |
| Kiosk stations (canManageMakerspace && inventory.kiosk): create, reveal PIN, rotate PIN, disable | MakerspaceSettingsPanel.tsx:130-132; KioskStationSettings.tsx:84 | MakerspaceSettingsPanel.tsx:172; KioskStationSettings.tsx:88-92 | BURIED | Row overflow. Disable now asks to confirm (f41d0505). |
| Membership settings, admission recipe and conditions, geofence | MakerspaceMembershipSettings.tsx:57; MakerspaceGeofenceSettings.tsx | MakerspaceSettingsPanel.tsx:175 | PRESENT | Admission gated by `membership` module as before. |
| Booking settings and booking rules (bookings module) | MakerspaceSettingsPanel.tsx:231-235 | MakerspaceSettingsPanel.tsx:178-179 | PRESENT | Same gate. |
| Filament (materials) low-stock threshold | MakerspaceSettingsPanel.tsx:236 | MakerspaceSettingsPanel.tsx:181 | PRESENT |  |
| Stripe payment keys and currency | MakerspacePaymentSettings.tsx | MakerspacePaymentSettings.tsx:144 | PRESENT | Same fields; Save only when changed. |
| Loan deposit, cap and blocking settings (charges.loans) | MakerspacePaymentSettings.tsx:176-178 (independent of the rail) | MakerspacePaymentSettings.tsx:88-90, returned outside the payment query (:169) | PRESENT | Fixed (10c35339): survives a 404 from a tombstoned payments rail and any payment-settings error. |
| Billing documents (canManageMakerspace) | MakerspaceSettingsPanel.tsx:121 | MakerspaceSettingsPanel.tsx:184 | PRESENT |  |
| Notification timing (canManageMakerspace && notifications module) | MakerspaceSettingsPanel.tsx:134 | MakerspaceSettingsPanel.tsx:187 | PRESENT |  |
| Mute matrix, channel preferences, recipient picker, recipient events | MakerspaceSettingsPanel.tsx:252-260 | MakerspaceSettingsPanel.tsx:188; NotificationMuteMatrix.tsx; NotificationMuteTable.tsx:21 | PRESENT | Table captions restored (f41d0505); phone columns pinned. |
| Rooms (notification destinations): add, edit, test, remove | MakerspaceSettingsPanel.tsx:256-259; DestinationRow.tsx:58-60 | MakerspaceSettingsPanel.tsx:189; DestinationRow.tsx:49 | BURIED | Remove is in the row overflow and now confirms; remove error shown (NotificationDestinations.tsx:75). |
| Email (SMTP) settings: save, clear saved password | MakerspaceEmailSettings.tsx | MakerspaceSettingsPanel.tsx:192; MakerspaceEmailSettings.tsx:87-107,145,186 | PRESENT | Own cache key handling fixed. |
| Notification recipients (managers who get email) | MakerspaceEmailSettings.tsx | MakerspaceEmailSettings.tsx:188-227 | PRESENT | Error now names "notification recipients". |
| Chat webhook settings | MakerspaceWebhookSettings.tsx | MakerspaceSettingsPanel.tsx:192; MakerspaceWebhookSettings.tsx:134 | PRESENT |  |
| Telegram alerts (superadmin) | ApiClientsPanel.tsx:153 (api tab) | MakerspaceSettingsPanel.tsx:193; ApiClientsTelegramSettings.tsx:25 | CHANGED | Moved from the API tab to Settings. Same `isSuperadmin` gate; own query key `["api-settings", id, "telegram"]`. |
| Integration health, Email log link, Telegram test jump | IntegrationHealthPanel.tsx | MakerspaceSettingsPanel.tsx:194; IntegrationHealthPanel.tsx:77-94 | PRESENT | Telegram test scrolls to the card (superadmin only). |
| Evidence retention + abandoned-upload cleanup (canManageMakerspace) | MakerspaceSettingsPanel.tsx:247; EvidenceRetentionPanel.tsx:104-109 | MakerspaceSettingsPanel.tsx:197; EvidenceRetentionPanel.tsx:72,100-105 | PRESENT |  |
| Editor-level server error text (E12, O10, Q11, S13, W6, Y2, Z9 in the earlier audit) | MakerspaceArchiveRequestPanel.tsx:197-203; EvidenceRetentionPanel.tsx:20-23 | SettingsQueryState.tsx:10-14 | CHANGED | Generic "Couldn't load X. Try again." P3. |

### Email templates, delivery log, API access

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Template list (streams, audiences, machine-type overrides) | EmailTemplatesPanel.tsx:69-79 | EmailTemplatesPanel.tsx; EmailTemplateEditor.tsx:159 back to list | BURIED | List then editor (list to detail), one extra click per template. |
| Edit subject, plain, HTML bodies; insert merge fields | EmailTemplateEditor.tsx:156-204 | EmailTemplateEditor.tsx:159-175 (Edit tab, MergeFields aside :174) | PRESENT |  |
| Save template | EmailTemplateEditor.tsx:156-158 | EmailTemplateEditor.tsx:163-165 (disabled until detail loads) | PRESENT | P0 guard added: Save no longer PATCHes an empty draft. |
| Live preview with render errors | EmailTemplateEditor.tsx:204 (always under the form) | EmailTemplateEditor.tsx:168,171 (Preview tab) | BURIED | Only on the Preview tab; preview error text is generic. P2. |
| Reset to default / fall back to space default (confirm) | EmailTemplateEditor.tsx | EmailTemplateEditor.tsx:167 (overflow), ConfirmDialog just after the DetailLayout | BURIED | Overflow, with ConfirmDialog. |
| Built-in default reference | EmailTemplateEditor.tsx | EmailTemplateEditor.tsx:168,171 (Default tab) | BURIED | Tab. |
| Delivery log filters (channel, status, family, event, destination) | DeliveryLogScreen.tsx:40-54 (inline) | DeliveryLogScreen.tsx:77-91 (FilterPopover, no `activeCount` or `chips`) | BURIED | Status is a SegmentedControl inside the closed popover; no visible state. P2. |
| Delivery row: family, event, channel, destination, attempts, error, retry | DeliveryLogScreen.tsx:66 | DeliveryLogScreen.tsx:93-98 | PRESENT | Channel text restored (3c3e56f0). |
| Send test delivery to a destination | DeliveryLogScreen.tsx | DeliveryLogScreen.tsx:63-64,105-110 | PRESENT | Header primary. |
| Suppressed addresses (list, suppress, remove) | SuppressionAdmin | DeliveryLogScreen.tsx:69 tab, :92 SuppressionAdmin embedded | BURIED | Tab. |
| Dashboard deep link failed_emails (status=failed) | dashboardLinks.ts:15 (never honoured, local useState) | dashboardLinks.ts:15; DeliveryLogScreen.tsx:35-37 | CHANGED | Pre-existing, not a regression: filters are local state, so the link lands unfiltered. P2. |
| API clients: create (name, scopes, origins), request access (non-managers) | ApiClientCreateCard.tsx:90-109 | ApiClientsPanel.tsx:126-148; ApiClientCreateCard.tsx | PRESENT | Gates `canManageMakerspace` unchanged. |
| API client scopes edit, Save scopes | ApiClientListCard.tsx:151-155 | ApiClientListCard.tsx:125-128 (drawer) | BURIED | Row opens a drawer. |
| Rotate secret and Delete client | ApiClientListCard.tsx:156-157 (no confirm) | ApiClientListCard.tsx:119-134 (overflow + ConfirmDialog) | BURIED | Gained a confirm. |
| Show-once secret after create/rotate | ApiClientsPanel.tsx:99-105,130 | ApiClientsPanel.tsx:43-46,105,130-131 (Modal) | PRESENT | Fixed (3c3e56f0): rotated secret opens in a modal. |
| Legacy v1 warning and scope list | ApiClientListCard.tsx:148-149 | ApiClientListCard.tsx:108,116,127 (drawer Callout, count pill) | BURIED | Hidden until the drawer is opened. P2. |
| Developer reference (origins, base URL) | ApiClientsPanel.tsx | ApiClientsPanel.tsx:172 section | PRESENT |  |

### Data export, backups, usage, tenant migration

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Request a data export (disabled while one runs) | DataExportsPanel.tsx:42-61 | DataExportsPanel.tsx:46 | PRESENT | Header primary with disabled reasons. |
| Export disclosure (omitted data, member contact details, referenced users) | DataExportsPanel.tsx:42-61 (always visible) | DataExportsPanel.tsx:19,52,61-80 | PRESENT | Open by default again (3c3e56f0); can be collapsed. |
| Export history, status, row count, failure reason, Download | DataExportsPanel.tsx | DataExportsPanel.tsx:55-60 | PRESENT |  |
| Create makerspace archive; list archives; Download | BackupRestorePanel.tsx:42 | BackupRestorePanel.tsx:49; BackupArchiveRows.tsx | PRESENT | Header primary. |
| Archive disclosure ("outside purge guarantees") | BackupRestorePanel.tsx:76 (warn tone) | BackupArchiveRows.tsx:5 | PRESENT | Warn tone restored (a1847395). |
| Daily backup schedule and retention settings (superadmin) | BackupRestorePanel.tsx:49-62 | BackupRestorePanel.tsx:61; BackupScheduleSettings.tsx | PRESENT | Deployment section. |
| Create full deployment archive (superadmin) | BackupRestorePanel.tsx:62 | BackupRestorePanel.tsx:50,63 | PRESENT | Primary when the backup module is off, otherwise a button in the Deployment section. |
| Restore from a backup (pick archive, recovery kind) | BackupRestorePanel.tsx:34,84 | BackupRestorePanel.tsx:72-74; BackupRestoreDialog.tsx | BURIED | Danger zone at the bottom plus dialog; disabled with a reason when no archive is available. |
| Restore decision (proceed / reset / abort) | BackupRestorePanel.tsx:35,64,93 | BackupRestorePanel.tsx:66; RestoreDecision.tsx | PRESENT | Shown inline while a restore is active. |
| Usage and limits | TenantUsagePanel.tsx | TenantUsagePanel.tsx | PRESENT | Generic load error. P3. |
| Migration stages (disclosure, pin deployments, export, import, verify, cutover) | TenantMigrationPanel.tsx:39-47 (all visible) | TenantMigrationPanel.tsx:15-21,57-69 (stepper) | BURIED | Stepper resumes at the furthest stage from server state (ee842122), steps are clickable (:60), so cutover controls are one click, not five. |
| Migration attestation sits with the identity decisions | TenantMigrationImports.tsx old:138-153 | TenantMigrationImports.tsx (materialise block under decisions) | PRESENT | Fixed (ee842122). |
| Pairings, import and closure list errors inline | TenantMigrationPanel.tsx old:49 | TenantMigrationPanel.tsx:64-65; TenantMigrationImports.tsx:51-52 | PRESENT | Failure of one list no longer blocks the flow. |
| Revoke disclosure approval | TenantMigrationDisclosure.tsx:108 | TenantMigrationDisclosure.tsx:110-111 | PRESENT | Gained a confirm. |

### Modules and platform

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Install / uninstall modules per group, "Turns on", "Also installs", blocked reason | ModulesPanel.tsx:28-205 | ModulesPanel.tsx:28-71; ModuleSettingsRows.tsx:17-37 | PRESENT | Switch per module; toast with Undo; no confirm before or after. |
| "Always on" group and core module badge, "Required by" read-out | ModulesPanel.tsx:103-104,188-190 | ModulesPanel.tsx:52; ModuleSettingsRows.tsx:25,35 | PRESENT | Restored (a1847395). |
| Deployment apps and env line (Copy) | ModulesPanel.tsx | ModuleSettingsRows.tsx:39-50 | PRESENT |  |
| Platform settings: email, sign-in providers, Stripe Connect (platform_hosting) | StaffPlatformTabContent.tsx:37-39 (stacked) | PlatformSettingsPanel.tsx:7-12 | BURIED | Tabs, one click. Stripe tab gate `platform_hosting` unchanged. |
| Platform email and Stripe descriptions | PlatformEmailPanel.tsx:75-77; PlatformStripeConnectPanel.tsx:73-75 | PlatformConfigurationSection.tsx:12 | PRESENT | Restored (a1847395). |
| Stripe application fee basis points field | PlatformStripeConnectPanel.tsx:86-95 (no visible label) | PlatformStripeConnectPanel.tsx:86,96 | CHANGED | Unchanged; aria-label only plus a helper line (:96). |
| Platform dashboard: tenant counts, usage, scheduler, backup, delivery | PlatformDashboardPanel.tsx:20-60 | PlatformDashboardPanel.tsx:21-64 | PRESENT | Failed-email counts also in overflow stats. |
| Problems list (checks, Inspect, "Checked <time>") | PlatformDashboardPanel.tsx:36-47 | PlatformDashboardPanel.tsx:31-37 | PRESENT | Survives a dashboard failure (3c3e56f0). |
| Inspect / Open usage page / Backup settings links | PlatformDashboardPanel.tsx:27,44 (react-router Link for non-/control URLs) | PlatformDashboardPanel.tsx:36,42,59 (plain `<a href>`) | CHANGED | Full page reload instead of in-app navigation, and the hrefs carry no makerspace slug. Still works. P3. |
| Run checks now | PlatformDashboardPanel.tsx | PlatformDashboardPanel.tsx:22 | PRESENT | Header secondary (phone: overflow). |

### Organizations

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Organization list and select | OrganizationsPanel.tsx | OrganizationsPanel.tsx:58-66 | PRESENT |  |
| Create organization (superadmin) | OrganizationsPanel.tsx | OrganizationsPanel.tsx:33,39-41,59-60 | PRESENT | Header primary and overflow. |
| Organization profile form | OrganizationProfileForm.tsx | OrganizationsPanel.tsx:50; OrganizationProfileForm.tsx | PRESENT |  |
| People: list, governance and makerspace actions, edit, remove | OrganizationMemberships.tsx:28-29 | OrganizationsPanel.tsx:45,52; OrganizationMemberships.tsx | PRESENT | Tab gated on `manage_organization_members` (fixed). Governance and makerspace actions on separate lines (a1847395). |
| Invitations: create link (copy once), list, revoke | OrganizationInvitations.tsx:58 | OrganizationInvitations.tsx | PRESENT | Revoke gained a confirm. |
| Linked spaces: link, change reach, unlink (confirm) (superadmin) | OrganizationSetup.tsx:34 | OrganizationSetup.tsx:36-38 | BURIED | Unlink in row overflow, ConfirmDialog intact. |
| Public page link | OrganizationsPanel.tsx | OrganizationsPanel.tsx:36 | PRESENT |  |
| Organization analytics: pick org, report, breakdown, total | OrganizationAnalyticsPanel.tsx:27-38 | OrganizationAnalyticsPanel.tsx:24-50 | CHANGED | Org select lists only orgs from useOrganizations; the old type-any-ID fallback is gone. P3. |

### Counts by section

| Section | PRESENT | BURIED | CHANGED | MISSING | Total |
|---|---|---|---|---|---|
| Chrome and navigation | 9 | 1 | 5 | 0 | 15 |
| Audit log (tab audit) | 4 | 3 | 1 | 0 | 8 |
| Accountability (tab accountability) | 5 | 2 | 2 | 0 | 9 |
| Reports (tab reports) | 7 | 4 | 5 | 0 | 16 |
| Members (tab members) | 6 | 12 | 2 | 0 | 20 |
| Member cards (tab cards) | 3 | 3 | 0 | 0 | 6 |
| Staff & roles (tab users) | 8 | 3 | 0 | 0 | 11 |
| Makerspace settings: shell and section mounts (tab settings) | 25 | 3 | 4 | 0 | 32 |
| Email templates, delivery log, API access | 7 | 9 | 1 | 0 | 17 |
| Data export, backups, usage, tenant migration | 12 | 2 | 0 | 0 | 14 |
| Modules and platform | 7 | 1 | 2 | 0 | 10 |
| Organizations | 6 | 1 | 1 | 0 | 8 |
| **Total** | **99** | **44** | **23** | **0** | **166** |
