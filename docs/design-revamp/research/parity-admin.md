# Parity audit: admin, settings and platform

Seven parts, merged verbatim from the parallel audits (2026-10-15).

---

Scope: staff tabs `audit`, `accountability`, `reports` (frontend/src/features/staff), OLD = d3e5ed29, NEW = working tree of feature/design-revamp.

## Navigation

| Tab | Gate (unchanged, staffAccess.ts:139-141) | Old reach | New reach | Status |
|---|---|---|---|---|
| audit | `canViewAudit` | Dock "Insights" group button -> popover -> "Audit" (old staffAccess.ts:62 TAB_GROUPS, StaffDock.tsx:162-190) | Sidebar section "Insights" -> visible item "Audit" (sidebarSections.ts:19) | PRESENT (one click fewer) |
| reports | `canViewFinance \|\| canViewAudit \|\| canSeePrinting \|\| canManageMachines` | Dock "Insights" popover -> "Reports" | Sidebar "Insights" -> visible item "Reports" (sidebarSections.ts:19) | PRESENT |
| accountability | `canViewAudit` | Dock "Insights" popover -> "Accountability" | Sidebar "Insights" -> "More (1)" disclosure -> "Accountability" (sidebarSections.ts:19 `more`, SidebarSection.tsx:22-28) | BURIED (P3) |

Routing in StaffTabContent.tsx is identical old/new: `accountability && canViewAudit` (new :193), `reports` with props printingOnly/canViewAudit/canManageMachines/canViewFinance=has("view_finance") (new :196-206), `audit && canViewAudit` -> `<AuditLog makerspaceId={activeMakerspace?.id}/>` (new :223). Dashboard deep links `section=overdue|problems` (dashboardLinks.ts:7,10) still resolve.

## audit — Audit log (panels/AuditLog.tsx)

Old: `Panel "Audit logs"` with inline ListViewControls (sort + SavedViewsMenu), inline AuditLogFilters grid, AuditVerificationStatus box, card list, prev/next pager. New: `ListLayout` (AuditLog.tsx:30-46) — verification moved into the header `meta`, sort+views in the toolbar (a whole ListViewControls/ListFilters nested in the `sort` slot), filter fields inside the closed `FilterPopover`, rows as a 4-column DataTable with a per-row "View details" disclosure (new AuditLogDetails.tsx). AuditLogFilters.tsx is unchanged. No gate changes; no destructive actions on this page.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page heading "Audit logs" | AuditLog.tsx:45 | PRESENT | Header "Audit log" + subtitle, AuditLog.tsx:31 |
| 2 | Sort select Newest / Oldest / Action (`ordering`), only when `makerspaceId` | AuditLog.tsx:46, ListViewControls.tsx:11 | PRESENT | Toolbar ListSort via ListViewControls (AuditLog.tsx:36, ListViewControls.tsx:13); also sortable "Activity"/"When" column headers (AuditLog.tsx:39-43) |
| 3 | "Clear selected result" (URL `id`) | ListViewControls.tsx:9 | PRESENT | Chip "Remove Selected result", ListViewControls.tsx:16 |
| 4 | Saved views: choose-a-view select -> restore list state (GET /admin/makerspaces/{id}/saved-views?entity=audit) | SavedViewsMenu.tsx:35-38 | BURIED | OverflowMenu "Views" -> view names, SavedViewsMenu.tsx:40-41 |
| 5 | Save current view (Modal: View name maxLength 80 required; "Share to this makerspace" checkbox gated `canShare`; POST saved-views) | SavedViewsMenu.tsx:39, 44-51 | CHANGED | "Views" menu -> item labelled **"Save current view?"** (SavedViewsMenu.tsx:44) — literal "?" where "…" was intended (byte-checked); modal unchanged (:60-67) |
| 6 | Previous views / More views paging | SavedViewsMenu.tsx:40-41 | BURIED | Menu items (:42-43) and pager inside Manage modal (:35-38, :56) |
| 7 | Manage saved views: Share to makerspace / Make private (PATCH `shared`, gate canShare), Delete (DELETE, no confirm) | SavedViewsMenu.tsx:42 | BURIED | "Views" -> **"Manage views?"** (same "?" typo, :45) -> Modal (:48-58). Delete still has no confirmation (same as old) |
| 8 | Saved-views load/mutation error | SavedViewsMenu.tsx:43 | PRESENT | :47 (load), :57 (mutation, inside modal) |
| 9 | Filter: Makerspace ID | AuditLogFilters.tsx:50 | BURIED | Inside "Filters" popover (AuditLog.tsx:37 -> ListFilters.tsx:25, FilterPopover.tsx) |
| 10 | Filter: Action (e.g. request.issued) | AuditLogFilters.tsx:51 | BURIED | Filters popover |
| 11 | Filter: Actor ID | AuditLogFilters.tsx:52 | BURIED | Filters popover |
| 12 | Filter: Target type | AuditLogFilters.tsx:53 | BURIED | Filters popover |
| 13 | Filter: Target ID | AuditLogFilters.tsx:54 | BURIED | Filters popover |
| 14 | Filter: From (date, local day start) | AuditLogFilters.tsx:55 | BURIED | Filters popover |
| 15 | Filter: To (date, exclusive next midnight) | AuditLogFilters.tsx:56 | BURIED | Filters popover |
| 16 | Active filter values visible on the page | AuditLogFilters.tsx:49-57 (always-open grid) | CHANGED | Only a count badge on "Filters". `chips` are computed (AuditLog.tsx:27-28) but never passed into `filters` (:36-37), so no visible/removable filter chips |
| 17 | "Verify these entries" — POST /admin/makerspace/{id}/audit-verifications with current filters, poll status_url every 3 s | AuditVerificationStatus.tsx:62-97 | PRESENT | Header meta slot (AuditLog.tsx:31); button demoted to `desk-button` (AuditVerificationStatus.tsx:92), adds "Starting verification…" |
| 18 | "Choose one makerspace to verify." hint | AuditVerificationStatus.tsx:98 | PRESENT | :100 |
| 19 | Verdict text (fully verified / incomplete / integrity problems / did not complete) | AuditVerificationStatus.tsx:99-100 | PRESENT | StatusPill with tone, :102 |
| 20 | Start error + status error with "Retry status" | AuditVerificationStatus.tsx:102-108 | PRESENT | :104-110 |
| 21 | Coverage gaps line | AuditVerificationStatus.tsx:109-111 | PRESENT | :111-113 |
| 22 | Coverage counts (rows, MAC-valid, verified batch, chain, anchor) | AuditVerificationStatus.tsx:112-118 | PRESENT | :114-120 |
| 23 | Refresh audit list once run is terminal | AuditVerificationStatus.tsx:83-86 | PRESENT | unchanged |
| 24 | Row: action_label | AuditLog.tsx:54 | PRESENT | "Activity" column, AuditLog.tsx:41 |
| 25 | Row: raw action key (mono) | AuditLog.tsx:55 | BURIED | Inside per-row "View details" disclosure, AuditLogDetails.tsx:13 |
| 26 | Row: actor "by X" | AuditLog.tsx:56 | PRESENT | Activity column (`actor_display ?? "System"`), AuditLog.tsx:41 |
| 27 | Row: target_type:target_id | AuditLog.tsx:57 | PRESENT | "Target" column, AuditLog.tsx:42 |
| 28 | Row: absolute local date-time | AuditLog.tsx:58, 106-114 | CHANGED | RelativeTime ("3 days ago"); absolute only as hover `title` (RelativeTime.tsx:27). Weak for a forensic log |
| 29 | Row: projected metadata `key: value · …` + "(some details withheld)" | AuditLog.tsx:59, 79-88 | BURIED | Per-row "View details" toggle, AuditLogDetails.tsx:10-16 |
| 30 | List error shows server message | AuditLog.tsx:50 | CHANGED | Generic "Couldn't load audit entries. Try again." + Retry (AuditLog.tsx:32) |
| 31 | Loading skeleton | AuditLog.tsx:51, 90-104 | PRESENT | Layout skeleton (QueryContent) |
| 32 | Pager: Previous / Next + "Page N — X total" | AuditLog.tsx:63-73 | CHANGED | Pagination (AuditLog.tsx:46): "a–b of X", "Page N of M"; renders **nothing** when ≤1 page, so the total count disappears for small result sets. pageSize 24 matches backend PAGE_SIZE |

## accountability — Accountability (panels/AccountabilityPanel.tsx)

Old: four stacked Panels on one page (Overdue loans, Reported problems, Repeat offenders, Restricted requesters); `?section=overdue|problems` narrowed to one section with a "Show all accountability sections" button. New: `ListLayout` with 4 StatCards + 4 tabs (`section` param, default "overdue", opsPresentation.ts:6-30); one list visible at a time. Gates unchanged (Restrict/Restore = `isSuperadmin`). Confirmations: Restrict still requires the reason Modal; Restore had no confirm before and has none now.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Data load GET /admin/makerspace/{id}/accountability | AccountabilityPanel.tsx:17 | PRESENT | :18 |
| 2 | Deep link `section=overdue/problems` | AccountabilityPanel.tsx:20-21 | PRESENT | useOpsTabs("section"), :21-27 |
| 3 | All four sections visible together + "Show all accountability sections" | AccountabilityPanel.tsx:57, 61-182 | CHANGED | No all-sections view; tabs, default "Overdue". 4 StatCards (:69-74) give the counts and link to tabs |
| 4 | Loading text | AccountabilityPanel.tsx:58 | PRESENT | Layout skeleton |
| 5 | Load error shows server message | AccountabilityPanel.tsx:59 | CHANGED | Generic "Couldn't load accountability" + Retry (opsPresentation.ts:33-36) |
| 6 | Overdue loans list | AccountabilityPanel.tsx:61-78 | PRESENT | Default tab "Overdue", :76-81 |
| 7 | Overdue row: label / "(unnamed)" | AccountabilityPanel.tsx:69 | PRESENT | ListRow title :77 |
| 8 | Overdue row: requester · direct handout/request | AccountabilityPanel.tsx:70 | PRESENT | meta :78 (+avatar) |
| 9 | Overdue row: "Nd overdue" badge | AccountabilityPanel.tsx:72 | PRESENT | StatusPill "Overdue N d" :79 (new "Open loan" link for request rows, :80) |
| 10 | "Showing the earliest overdue loans only." | AccountabilityPanel.tsx:75 | PRESENT | :81 |
| 11 | Empty "No overdue loans." | AccountabilityPanel.tsx:63 | PRESENT | :63 |
| 12 | Reported problems section | AccountabilityPanel.tsx:80-91 | BURIED | Tab "Problems" / StatCard "Open problems" (one click) |
| 13 | Problem card: label "(tool)" | ProblemReportCard.tsx:30 | PRESENT | ListRow title, ProblemReportCard.tsx:30 |
| 14 | Problem card: requester + absolute created_at | ProblemReportCard.tsx:31 | CHANGED | requester + RelativeTime, :31 |
| 15 | Problem card: full note text | ProblemReportCard.tsx:32 | BURIED | 2-line clamp in meta; full text behind "Problem details" toggle, :31-33 |
| 16 | Outcome radios No issue / Damaged / Missing / Needs fix | ProblemReportCard.tsx:35-40 | PRESENT | :34-39 |
| 17 | Per-item quantity inputs (number, min 0, max issued_quantity) when outcome ≠ no_issue | ProblemReportCard.tsx:42-58 | PRESENT | :41-58 |
| 18 | Triage note textarea | ProblemReportCard.tsx:60 | PRESENT | :60 (+ "Choose at least one item quantity" hint :61) |
| 19 | Save triage — POST /admin/makerspace/{id}/problem-reports/{id}/triage {outcome, resolutions, note}; disabled when actionable with no quantities | ProblemReportCard.tsx:19-25, 63 | PRESENT | :64-66 ("Saving…") |
| 20 | Triage error | ProblemReportCard.tsx:62 | PRESENT | :63 |
| 21 | After triage refresh accountability + inventory views + needs-fix shelf | AccountabilityPanel.tsx:26-30 | PRESENT | :32-36 |
| 22 | "Showing the oldest open reports only." | AccountabilityPanel.tsx:88 | PRESENT | :84 |
| 23 | Empty "No open problem reports from public returns." | AccountabilityPanel.tsx:82 | PRESENT | "No open problem reports." :63 |
| 24 | Repeat offenders section | AccountabilityPanel.tsx:93-159 | BURIED | Tab "Repeat offenders" |
| 25 | Account-less loans callout (incidents, items, damaged, missing) | AccountabilityPanel.tsx:94-106 | PRESENT | Offenders tab only, :86-90 |
| 26 | Offenders table columns Requester / Damaged / Missing / Total issues (units) / Status | AccountabilityPanel.tsx:115-133 | CHANGED | ListRow with one meta string (:91-94); figures present but no columns to scan/compare |
| 27 | Restrict (isSuperadmin, status active) -> reason Modal | AccountabilityPanel.tsx:134-144 | PRESENT | "Restrict…" button :95-96 (styled `desk-button`, was `desk-button-danger`) |
| 28 | Restore (offender, non-active) POST /admin/users/{id}/restore-access, no confirm | AccountabilityPanel.tsx:146 | PRESENT | "Restore access" :97 (no confirm, unchanged) |
| 29 | "Showing the top offenders only." | AccountabilityPanel.tsx:156 | PRESENT | :99 |
| 30 | Empty offenders text (two variants depending on account-less incidents) | AccountabilityPanel.tsx:107-112 | PRESENT | :64, :98 |
| 31 | Restricted requesters section | AccountabilityPanel.tsx:161-181 | BURIED | Tab "Restricted" |
| 32 | Restricted row: username + access_status | AccountabilityPanel.tsx:169 | PRESENT | ListRow title + StatusPill :101-103 |
| 33 | Restricted row: restriction_reason | AccountabilityPanel.tsx:170 | PRESENT | meta :103 |
| 34 | Restore access (isSuperadmin) | AccountabilityPanel.tsx:172-176 | PRESENT | :104 |
| 35 | Empty restricted text | AccountabilityPanel.tsx:163 | PRESENT | "No one is restricted here." :64 |
| 36 | Restrict modal: reason textarea (required), Cancel, Restrict disabled on blank — POST /admin/users/{id}/restrict {status:"restricted", reason} | AccountabilityPanel.tsx:185-214, 31-38 | PRESENT | :108-138, :37-44 |
| 37 | Restrict / restore error | AccountabilityPanel.tsx:183-184 | PRESENT | ErrorBlock in `detail` slot :106-107 (renders below the list) |

## reports — Reports (panels/OperationsReports.tsx)

Old: one long page — header Panel with filters, saved views and the inventory **summary**, then an **Exports** grid (every exportable report, CSV/XLSX buttons) + inline **Scheduled reports** panel (OperationsReportExports.tsx), the selected-report preview, and **every** specialist panel stacked (hardware ×9, finance ×4, coverage ×9, members, payments, FabLab ×5, printer service, machine service). New: `DetailLayout` (OperationsReports.tsx:116-234) with a report nav aside (new OperationsReportNavigation.tsx), header actions Export / "Schedule…" / overflow formats, and `ReportSelectionProvider` (new OperationsReportSelection.tsx) that renders **only the selected report's panel** (title->catalog key match or ALIASES; generic preview hidden when a specialist exists; specialists hidden when a HARDWARE key is viewed at grain ≠ day). `OperationsReportExports` component is no longer rendered anywhere (only its `useOperationsReportExport` hook is used). Schedules move to a drawer. Gates: all prop gates unchanged; schedules still `!printingOnly && !aggregate && reportsEnabled`.

Report catalog (server, GET /admin/makerspace/{id}/reports/catalog or /admin/reports/catalog when aggregate; backend/apps/operations/report_definitions_*.py): summary, taken-items, active-loans, returns, damaged-missing, damaged-lost, qr-scans, most-lent, top-borrowers, recently-added, machine-usage (machines), event-attendance (events), booking-utilization (bookings), maintenance-activity (machines+maintenance), member-activity (membership), machine-service (machine_service), printer-service (printing), fablab-health, payment-reconciliation (view_finance), payment-cash-book (view_finance), payments-ledger / revenue-over-time / cash-book / accounting-journal (view_finance), member-retention, membership-revenue (membership + view_finance), audit-trail (csv only), loan-throughput, inventory-control, evidence-compliance, import-quality, procurement-performance (edit_inventory), communications-health (manage_makerspace), community-engagement, certification-coverage, module-operational-health (manage_makerspace).

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Heading "Reports" + "{Operations \| 3D printing} reporting for {scope}" + description | OperationsReports.tsx:94-104 | PRESENT | Header title/meta :116-117; section heading :134-142 |
| 2 | Start date | OperationsReports.tsx:107-110 | PRESENT | :145-148 (+ new presets 7/30/Quarter/Custom, :130-131) |
| 3 | End date | OperationsReports.tsx:111-114 | PRESENT | :149-152 |
| 4 | Report selector (catalog; unavailable entries disabled; "Loading reports…"/"No reports available") | OperationsReports.tsx:115-125, 59-69 | PRESENT | Aside nav: grouped buttons on desktop, grouped select on mobile (OperationsReportNavigation.tsx:19-31); shows `unavailable_reason`. Grouping is a regex heuristic (:4-11) |
| 5 | Selecting a report clears chosen columns | OperationsReports.tsx:117 | PRESENT | `selectReport` :113 |
| 6 | Grain select (catalog grains) | OperationsReports.tsx:126-131 | PRESENT | :153-158 |
| 7 | Superadmin "All makerspaces" toggle -> /admin/analytics + /admin/reports aggregate | OperationsReports.tsx:132-142, 52-55 | PRESENT | :159-169 |
| 8 | Catalog error shown inline while other panels still render | OperationsReports.tsx:145 | CHANGED | DetailLayout `state` error replaces the **whole page** (:118); printer/machine-service panels (which don't need the catalog) disappear; inline message at :172 is now unreachable |
| 9 | Empty catalog still shows remaining panels | OperationsReports.tsx:94-215 | CHANGED | `isEmpty` replaces the whole page with "No reports available yet…" (:119-120) |
| 10 | Retention months (member-retention, 1-120, blank = 3/6/12) | OperationsReports.tsx:146 | PRESENT | :173 |
| 11 | Report payment status filter (payment-reconciliation) | OperationsReports.tsx:148 | PRESENT | :175 |
| 12 | Report charge type filter (payment-reconciliation) | OperationsReports.tsx:149 | PRESENT | :176 |
| 13 | Saved report views block, gate `!aggregate && reportsEnabled && enabled_features has "reports.saved_views"` | OperationsReports.tsx:151-152 | PRESENT | :178-179 |
| 14 | Saved view: name (≤80, required) + "Share with makerspace (managers)" + Save — POST /admin/makerspaces/{id}/saved-report-views | ServerReportViews.tsx:26-30 | PRESENT | ServerReportViews.tsx:28-32 |
| 15 | Visible-columns checkboxes | ServerReportViews.tsx:31-33 | PRESENT | :33-35; now also applied to specialist tables (OperationsReportTable.tsx:24-28) |
| 16 | Open saved view (GET .../saved-report-views/{pk}) | ServerReportViews.tsx:36 | PRESENT | :38 |
| 17 | Delete saved view (DELETE), no confirm | ServerReportViews.tsx:37 | CHANGED | Now opens ConfirmDialog (:39, :45-46) — improvement |
| 18 | Saved-views paging + error | ServerReportViews.tsx:39-43 | PRESENT | :41-45 |
| 19 | Inventory summary StatCards (Products, Assets, Active loans, Available, Issued, Damaged, Missing) — GET {analytics}/summary; gate `!printingOnly && canViewAudit && reportsEnabled` | OperationsReports.tsx:153-165, 71 | BURIED | Only when report "Summary" is selected (:180); default selection is most-lent, so the landing view has no KPIs |
| 20 | Summary bar chart (units) | OperationsReports.tsx:166-173 | BURIED | Same, :193-200 |
| 21 | Summary metric/value table | OperationsReports.tsx:174-183 | BURIED | Same, :201-210 |
| 22 | "Module disabled" when reports module off | OperationsReports.tsx:185 | PRESENT | :212 |
| 23 | Exports grid: a card per exportable+available report with a button per allowed format — GET {reportsBase}/{key}/export?format=&start&end&grain[&months\|status\|subject_type] | OperationsReportExports.tsx:54-68 (rendered OperationsReports.tsx:190-201) | MISSING | `<OperationsReportExports>` is orphaned. Replaced by exporting the **selected** report only (rows 24-25); exporting another report now needs nav-select first |
| 24 | Export in first allowed format | OperationsReportExports.tsx:61 | CHANGED | Header primary "Export" (:121-122) exports `formats[0]` of the selected report; disabled with reason when not exportable |
| 25 | Export in the other format (XLSX) | OperationsReportExports.tsx:60-64 | BURIED | Header overflow "Export CSV"/"Export XLSX" (:124) |
| 26 | Export error shows server message | OperationsReportExports.tsx:69-73 | CHANGED | Generic "Couldn't export this report. Try again." at page bottom (:230) |
| 27 | Export filename `all-makerspaces-{key}.{fmt}` when aggregate | OperationsReportExports.tsx:47 | PRESENT | OperationsReportExports.tsx:25 (hook) |
| 28 | Scheduled reports panel inline (gate `!aggregate && reportsEnabled`, inside `!printingOnly`) | OperationsReportExports.tsx:78-80 | BURIED | Drawer opened by header secondary "Schedule…" (:123, :231-233) |
| 29 | Schedules intro text, loading, load error, empty | ReportSchedules.tsx:71-76 | PRESENT | In drawer, ReportSchedules.tsx:71-76 |
| 30 | Schedule row summary: report title, cadence · format · grain · window · destination · emails · roles · actions · non-empty · threshold | ReportSchedules.tsx:81-91 | PRESENT | Unchanged in drawer |
| 31 | Next run / last run (absolute) | ReportSchedules.tsx:92 | CHANGED | RelativeTime (:22) |
| 32 | "Download last delivery" link | ReportSchedules.tsx:93-97 | PRESENT | unchanged |
| 33 | Active/Paused badge | ReportSchedules.tsx:100 | PRESENT | StatusPill :100 |
| 34 | Run now — POST /admin/report-schedules/{id}/run-now; result status + download link | ReportSchedules.tsx:101, 109-116 | PRESENT | :101 ("Running…"), :110-117 |
| 35 | Edit schedule (inline form) | ReportSchedules.tsx:102, 117-130 | BURIED | Row OverflowMenu -> "Edit" (:102-103) |
| 36 | Pause / Resume — PATCH /admin/report-schedules/{id} {is_active} | ReportSchedules.tsx:103-105 | BURIED | Row OverflowMenu (:104-105) |
| 37 | Delete — DELETE /admin/report-schedules/{id} with ConfirmDialog | ReportSchedules.tsx:106, 151-160 | BURIED | Row OverflowMenu "Delete" (:106) still opens the page's own ConfirmDialog (:152-161) — confirmation retained |
| 38 | New schedule button (disabled when no schedulable reports) — POST /admin/makerspaces/{id}/report-schedules | ReportSchedules.tsx:145 | PRESENT | In drawer, :146 (+ disabled title) |
| 39 | Form: Report select (resets metric/grain/format) | ReportScheduleForm.tsx:134-158 | PRESENT | unchanged file |
| 40 | Form: Grain | ReportScheduleForm.tsx:159-163 | PRESENT | unchanged |
| 41 | Form: Format (allowed_formats) | ReportScheduleForm.tsx:164-168 | PRESENT | unchanged |
| 42 | Form: Cadence Daily/Weekly/Monthly | ReportScheduleForm.tsx:169-173 | PRESENT | unchanged |
| 43 | Form: Chat destination (GET /admin/makerspace/{id}/notification-destinations, active only; "Email only") | ReportScheduleForm.tsx:174-181 | PRESENT | unchanged |
| 44 | Form: Window (days), whole number | ReportScheduleForm.tsx:182-184 | PRESENT | unchanged |
| 45 | Form: Recipient emails (≤ MAX, validated) | ReportScheduleForm.tsx:185-187 | PRESENT | unchanged |
| 46 | Form: Recipient role slugs | ReportScheduleForm.tsx:188-190 | PRESENT | unchanged |
| 47 | Form: Recipient actions | ReportScheduleForm.tsx:191-193 | PRESENT | unchanged |
| 48 | Form: Send only when non-empty | ReportScheduleForm.tsx:194 | PRESENT | unchanged |
| 49 | Form: Threshold metric (catalog condition_metrics) | ReportScheduleForm.tsx:195-199 | PRESENT | unchanged |
| 50 | Form: Comparison > >= < <= = | ReportScheduleForm.tsx:200-202 | PRESENT | unchanged |
| 51 | Form: Threshold (numeric) | ReportScheduleForm.tsx:203 | PRESENT | unchanged |
| 52 | Form: Threshold currency (3 lowercase letters) | ReportScheduleForm.tsx:204 | PRESENT | unchanged |
| 53 | Form: Create/Save schedule, Cancel, validation message | ReportScheduleForm.tsx:205-211 | PRESENT | unchanged |
| 54 | Schedule mutation error | ReportSchedules.tsx:150 | PRESENT | :151 |
| 55 | Selected-report generic preview table (GET {analytics}/{key}?grain&start&end[&months\|status\|subject_type]; respects columns) + definition/limitations notes | SelectedReportPreview.tsx:6-33 (rendered OperationsReports.tsx:203) | CHANGED | :217; Panel now shown only when no specialist panel owns the key; definition/limitations render outside the Panel (SelectedReportPreview.tsx:28-34) |
| 56 | Most lent (bar times_lent + table); gate hardwareEnabled = canViewAudit && reportsEnabled | OperationsReportsHardware.tsx:35 | BURIED | Only when "Most lent" selected (OperationsReportsHardware.tsx:36 via SelectedReportPanel) |
| 57 | Top borrowers (bar requests + table) | OperationsReportsHardware.tsx:36 | BURIED | Only when selected (:37) |
| 58 | Damaged / missing (stacked bar) | OperationsReportsHardware.tsx:39 | BURIED | :40 |
| 59 | Damaged / lost (stacked bar) | OperationsReportsHardware.tsx:40 | BURIED | :41 |
| 60 | Recently added (line) | OperationsReportsHardware.tsx:41 | BURIED | :42 |
| 61 | Taken items (bar) | OperationsReportsHardware.tsx:42 | BURIED | :43 |
| 62 | Active loans (stacked by issued_at/status) | OperationsReportsHardware.tsx:43 | BURIED | :44 |
| 63 | Returns (stacked by closed_at/status) | OperationsReportsHardware.tsx:44 | BURIED | :45 |
| 64 | QR scans (pie by context) | OperationsReportsHardware.tsx:45 | BURIED | :46 |
| 65 | Finance panels payments-ledger / revenue-over-time (line + note) / cash-book / accounting-journal; gate `canViewFinance \|\| isSuperadmin` | OperationsReportsFinance.tsx:25 (rendered OperationsReports.tsx:205) | BURIED | One at a time by selection (OperationsReportsFinance.tsx:26 `reportKey`) |
| 66 | Coverage panels ×9 (loan-throughput … certification-coverage; line/bar/stacked + table + source/grain meta; per-report "Module disabled") | OperationsReportsCoverage.tsx:54-60 (rendered :206) | BURIED | One at a time (:55 `reportKey`) |
| 67 | Member activity (stat cards, bar, table, aggregate cards); gate hardwareEnabled | OperationsReportsMembers.tsx:13-51 (rendered :207) | BURIED | Only when "Member activity" selected (:14) |
| 68 | Payment reconciliation: note, per-currency count/total bars, "Settled by method" pie, table Currency/Subject/Status/Method/Payments/Total/Outstanding/Refunded, per-makerspace when aggregate; gate `canViewFinance \|\| isSuperadmin`, enabled reportsEnabled | OperationsReportsPayments.tsx:33-99 (rendered :208) | CHANGED | Only when selected (:35); table now DataTable + status pill (:75-88). Key `payment-reconciliation` is not in the specialist set (OperationsReportSelection.tsx:6,18), so the **generic preview also renders** -> duplicate table |
| 69 | FabLab health (stat cards, Events/Bookings/Machines/Maintenance state tiles, table); gate canViewAudit | OperationsReportsFablab.tsx:37 (rendered :212) | BURIED | Only when "FabLab health" selected (:38) |
| 70 | Machine usage (stats, top-10 bar, table; "Module disabled") | OperationsReportsMachineUsage.tsx:7-27 | BURIED | Only when selected |
| 71 | Events attendance (stats, status pie, attendance-rate bar, registrations line) | OperationsReportsEvents.tsx:7-31 | BURIED | Only when "Event attendance" selected (title matched via ALIASES) |
| 72 | Bookable space utilization (stats, utilization + no-show bars) | OperationsReportsBookings.tsx:7-30 | BURIED | Only when "Booking utilization" selected (ALIASES) |
| 73 | Maintenance activity (logs bar, cost bar; aggregate note) | OperationsReportsMaintenance.tsx:7-32 | BURIED | Only when selected |
| 74 | Printer service (hours stacked, grams bar, payment stacked, table); gate canManageMachines | OperationsReportsPrinterService.tsx:26-50 (rendered :214) | BURIED | Only when "Printer service" selected (or always in printingOnly mode) |
| 75 | Machine service (status totals, service-hours bar, failures bar, consumption); gate canManageMachines && machine_service | OperationsReportsMachineService.tsx:27-53 (rendered :215) | BURIED | Only when "Machine service" selected (or printingOnly) |
| 76 | printingOnly mode: printing heading, no summary/exports/schedules/hardware/finance/FabLab, printer + machine service shown | OperationsReports.tsx:98-103, 153, 188-215 | CHANGED | Same panels (selection disabled, :126) but the report nav aside and Export-less header still render; clicking nav entries has no visible effect |
| 77 | Per-panel error shows server message | OperationsReportState.tsx:41 | CHANGED | Generic "Couldn't load this report. Try again." + Retry (OperationsReportState.tsx:41-44) |
| 78 | Per-panel empty "No records." | OperationsReportState.tsx:42 | PRESENT | EmptyState "No activity in this period. Try a longer range." (:45) |
| 79 | Charts Bar / Line / StackedBar / Pie | OperationsReportCharts.tsx | PRESENT | Same components, chart palette tokens |
| 80 | Report table (scroll box max-h-80, sticky header) | OperationsReportTable.tsx (old ReportTable) | CHANGED | DataTable without height cap (OperationsReportTable.tsx:24-34); long reports now run the full page height |

### Counts

| Page | PRESENT | BURIED | CHANGED | MISSING | Total |
|---|---|---|---|---|---|
| Navigation | 2 | 1 | 0 | 0 | 3 |
| audit | 15 | 12 | 5 | 0 | 32 |
| accountability | 29 | 4 | 4 | 0 | 37 |
| reports | 41 | 27 | 11 | 1 | 80 |
| **Total** | 87 | 44 | 20 | 1 | 152 |

No permission/module gate changed in these three tabs, and no destructive action lost a confirmation. Report-schedule Delete keeps its own ConfirmDialog. Saved-report-view Delete gained one. Restrict still needs the reason Modal. Restore access and staff saved-view Delete had no confirm before and still have none. Nothing in scope relies on `Action.confirms`.

### Restore candidates

1. **P1 — Audit filters hidden with no visible state** (audit #9-16). The new code builds `chips` at AuditLog.tsx:27-28 but never passes them. Fix: pass `chips` into `filters={{…, chips}}` (ListFiltersProps.chips, ListFilters.tsx:29-32) so each active filter (actor, action, target, dates) shows as a removable chip. The seven AuditLogFilters fields (AuditLogFilters.tsx:50-56) can stay in the popover. If auditors use it heavily, also lift Action and From/To into the toolbar.
2. **P2 — Export-all grid removed** (reports #23-26). Old `OperationsReportExports` grid (old OperationsReportExports.tsx:54-68, mutation :36-50) is now orphaned. The header "Export" keeps one primary action for the selected report, which fits Yuyu. Two fixes:
   - Label the primary with its format ("Export CSV").
   - Bring back the server error text: render `exportReport.error.message` the way old OperationsReportExports.tsx:69-73 did, instead of the generic line at OperationsReports.tsx:230.
   - Optionally add an "Export another report…" overflow item that opens a picker. Do not re-render the full grid.
3. **P2 — Inventory summary KPIs no longer on the landing view** (reports #19-21). The old block was at OperationsReports.tsx:153-184. Fix: default `selectedReport` to "summary" when it is available, or render the 7 StatCards in the DetailLayout header/aside regardless of selection. Today the gate `selectedReport === "summary"` sits at new :180.
4. **P2 — Catalog error/empty blanks the whole Reports page** (reports #8-9). DetailLayout `state`/`isEmpty` (new :118-120) hides printer/machine-service panels that never depended on the catalog. Fix: pass `state: ready`, and show catalog errors inline. The old inline line at :145 is still present at new :172.
5. **P2 — Audit timestamp and metadata** (audit #28-29). Show the absolute `toLocaleString` date (old AuditLog.tsx:106-114) in the "When" column, with relative time as secondary text. Consider showing the meta line (old MetaLine :79-88) when a row has ≤2 keys, keeping the disclosure for longer meta.
6. **P2 — Accountability all-sections overview → tabs** (accountability #3, 12, 24, 31). This is acceptable under Yuyu because the StatCards link to the tabs. Superadmins act from the Repeat offenders and Restricted tabs, so consider defaulting to the first non-empty tab. Optional: restore the offender columns as a DataTable (old AccountabilityPanel.tsx:115-133) instead of the meta string at new :93.
7. **P2 — Report schedules in a drawer** (reports #28, 35-37). Opening from the header secondary "Schedule…" fits Yuyu, with Edit/Pause/Delete in a row OverflowMenu and Run now visible. Two optional additions:
   - Show a schedule count on the secondary button.
   - Open the drawer from a `?schedules=1` URL param so it can be deep-linked.
8. **P3 — Duplicate payment reconciliation** (reports #68). Add `payment-reconciliation` to the finance specialist list in OperationsReportSelection.tsx:6/18 (gated by `finance`). Without it, SelectedReportPreview renders a second table.
9. **P3 — Typos in the saved-views menu** (audit #5, #7). Labels "Save current view?" and "Manage views?" (SavedViewsMenu.tsx:44-45) should end with "…". The shared SavedViewsMenu also feeds Members, Events, Bookings, Inventory, Requests and Payments.
10. **P3 — Generic error text replaced server messages.** Affects audit #30 (AuditLog.tsx:32), accountability #5 (opsPresentation.ts:33-36) and reports #77 (OperationsReportState.tsx:41-44). Fix: include `error.message` under the generic sentence.
11. **P3 — Pagination hides the total on single-page results** (audit #32). Pagination.tsx:16-18 returns null, so the old "X total" (AuditLog.tsx:67-69) is gone. Pass the count to the header meta, or let Pagination show the count when `totalPages <= 1`.
12. **P3 — Small presentation regressions:**
    - ProblemReportCard note clamped to 2 lines; full text behind a toggle (ProblemReportCard.tsx:31-33).
    - Schedule next/last run shown as relative time.
    - Report tables have no height cap (OperationsReportTable.tsx:28).
    - In printingOnly mode the report nav is shown but does nothing (OperationsReports.tsx:125-126). Hide `aside` when `printingOnly`.
13. **P3 — Accountability sits under "More" in the sidebar** (Navigation). Consider promoting it to a visible Insights item (sidebarSections.ts:19). It is the target of the dashboard's overdue-loan and problem-report tiles, and those tiles still deep-link correctly.

---

Scope: staff tabs `members` (MembersPanel closure) and `cards` (MemberCardsPanel + memberCards/*); OLD = d3e5ed29, NEW = working tree.

## members — Members (MembersPanel.tsx)

Routing/gate unchanged: `MembersPanel({ makerspaceId, membershipEnabled, canManageMakerspace, canViewFinance, canRecordPayment })`. Structure changed from one long page of stacked Panels (roster, requests+invite, invitation requests, plans, presence, waiver) to a `ListLayout` with URL tabs (`?section=`) `members | requests | presence | plans (membershipEnabled && canManageMakerspace) | waivers (canManageMakerspace)` (MembersPanel.tsx:42-46,104-110). Gates per section are identical to old. Header primary "Invite member" (:113) opens a FlowLayout dialog; new stats row (:114). Roster rows moved to new `MemberRow.tsx`: a ListRow + OverflowMenu + per-member DetailLayout drawer. All mutations/API paths are byte-identical (:77-97 vs old :69-89). Revoke/Decline still open `MembershipReasonDialog` (reason required) — no reliance on `Action.confirms`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page title "Members" + explainer paragraph | MembersPanel.tsx:95,98 | PRESENT | PageHeader MembersPanel.tsx:113; paragraph kept :119 |
| 2 | Roster list, one row per membership (`GET /admin/memberships?makerspace_id&page&q&status&ordering&id`) | MembersPanel.tsx:48-51,99-118 | PRESENT | MembersPanel.tsx:56-59,120-139 → MemberRow ListRow MemberRow.tsx:33 |
| 3 | Row: display name (fallback username) | MembersPanel.tsx:173 | PRESENT | MemberRow.tsx:32-33 (adds avatar + email) |
| 4 | Row: assigned role name | MembersPanel.tsx:173 | PRESENT | MemberRow.tsx:34 meta |
| 5 | Row: membership status text | MembersPanel.tsx:173 | PRESENT | StatusPill MemberRow.tsx:36 |
| 6 | Row: waiver current / needed / not required | MembersPanel.tsx:173 | PRESENT | MemberRow.tsx:34 meta; also drawer SettingsRow :55 |
| 7 | Verified / Not verified badge (membershipEnabled) | MembersPanel.tsx:175 | PRESENT | MemberRow.tsx:37 |
| 8 | Vouchers list on the row (`MembershipVouchers`) | MembersPanel.tsx:173 | BURIED | Only inside member drawer MemberRow.tsx:56 (click row) |
| 9 | Payment summary (amount + status badge) per member (canViewFinance) | MembersPanel.tsx:173; PaymentReconcileActions.tsx:55-57 | BURIED | Only inside member drawer MemberRow.tsx:57; roster no longer shows who owes money |
| 10 | "Mark offline" → SettlementDialog → `reconcilePayment(mark-offline)` (canRecordPayment \|\| canManageMakerspace) | PaymentReconcileActions.tsx:60-67,81-91 | BURIED | Drawer → PaymentReconcileActions.tsx:60-67 → SettlementDialog now a FlowLayout modal |
| 11 | "Waive" → `reconcilePayment(waive)` (canWaive = canManageMakerspace) | PaymentReconcileActions.tsx:68-75 | BURIED | Drawer → second-level OverflowMenu "Payment actions" PaymentReconcileActions.tsx:68-69 (no confirm, same as old). Change is in the shared component, so also affects BookingRequests/EventRegistrationRoster/admission rows |
| 12 | "Record witnessed acceptance" (`POST /admin/memberships/{id}/waiver/witness`; active && waiver_required && !waiver_current) | MembersPanel.tsx:176 | PRESENT | Inline row button MemberRow.tsx:38 |
| 13 | "Can refer" checkbox (`PATCH …/capabilities {can_refer}`; active && membershipEnabled) | MembersPanel.tsx:176 | BURIED | Drawer SettingsRow MemberRow.tsx:50 |
| 14 | "Can verify" checkbox (`PATCH …/capabilities {can_verify}`) | MembersPanel.tsx:176 | BURIED | Drawer SettingsRow MemberRow.tsx:51 |
| 15 | Verify / Unverify (`POST …/verify` / `…/unverify`; membershipEnabled) | MembersPanel.tsx:176 | BURIED | Row OverflowMenu MemberRow.tsx:41 + drawer :52 |
| 16 | "Terms" → MemberTermsDialog (membershipEnabled) | MembersPanel.tsx:176,146 | BURIED | Row OverflowMenu MemberRow.tsx:41 + drawer :53; dialog MembersPanel.tsx:176 |
| 17 | Role dropdown per member (`PATCH /admin/memberships/{id}/role`; active && manageable) | MembersPanel.tsx:176 | BURIED | Drawer SettingsRow "Role" MemberRow.tsx:48 (read-only text when not manageable/inactive) |
| 18 | Revoke membership → MembershipReasonDialog (`POST …/revoke {reason}`; active && manageable) | MembersPanel.tsx:176,116,145 | BURIED | Row OverflowMenu (danger) MemberRow.tsx:42 + drawer DangerZone :59; reason dialog intact MembersPanel.tsx:175 |
| 19 | Roster search (q) | ListViewControls.tsx:10 | PRESENT | ListViewControls.tsx:11 via ListFilters search ("Search members") |
| 20 | Roster sort: Username / Username desc / Status | MembersPanel.tsx:96; ListViewControls.tsx:11 | PRESENT | ListSort ListViewControls.tsx:12 |
| 21 | Status filter All / Active / Revoked | MembersPanel.tsx:97 | BURIED | Inside closed FilterPopover (`controls`) MembersPanel.tsx:118; count badge shows when set |
| 22 | "Clear selected result" (id filter from search jump) | ListViewControls.tsx:9 | PRESENT | Chip "Remove Selected result" ListViewControls.tsx:15 |
| 23 | Saved views: pick a view to restore (was a visible select) | SavedViewsMenu.tsx:35-38 | BURIED | "Views" OverflowMenu SavedViewsMenu.tsx:40-41 |
| 24 | Save current view (modal: View name max 80, required; "Share to this makerspace" if canShare) | SavedViewsMenu.tsx:39,44-51 | CHANGED | In Views menu, label reads "Save current view?" (stray "?" instead of "…") SavedViewsMenu.tsx:44; modal unchanged :60-67 |
| 25 | Saved views paging Previous / More views | SavedViewsMenu.tsx:40-41 | PRESENT | Menu items :42-43 + manage modal :35-38 |
| 26 | Manage saved views: Share/Make private (canShare), Delete (owner's only; no confirm in either) | SavedViewsMenu.tsx:42 | BURIED | Views menu "Manage views?" → modal SavedViewsMenu.tsx:45,48-59 (same "?" typo) |
| 27 | Roster loading / error / empty read-outs | MembersPanel.tsx:119-121 | PRESENT | ListLayout skeleton/ErrorBlock+retry :111; EmptyState :140 |
| 28 | Roster pagination | MembersPanel.tsx:122 | PRESENT | MembersPanel.tsx:141 |
| 29 | Requests/Invitations panel (was on the page; title switches on membershipEnabled) | MembersPanel.tsx:124 | BURIED | Tab "Requests"/"Invitations" with count MembersPanel.tsx:106,143 |
| 30 | Invite role select (shared with Approve) | MembersPanel.tsx:124 | PRESENT | Invite dialog "Invite role" :174; separate visible "Approve as" select in Requests tab :148 (same `selectedRole` state) |
| 31 | Invite email + Invite (`POST /admin/makerspace/{id}/membership-invitations {invite_email, role_id}`) | MembersPanel.tsx:88,124 | PRESENT | Header primary "Invite member" → FlowLayout dialog MembersPanel.tsx:113,172-174 (error shown in dialog) |
| 32 | Request state filter (requested, invited, awaiting_vouches, awaiting_payment, expired, canceled, active, revoked) | MembersPanel.tsx:126 | PRESENT | MembersPanel.tsx:145 |
| 33 | Request sort Newest / Oldest / State | MembersPanel.tsx:127 | PRESENT | MembersPanel.tsx:146 |
| 34 | Roles load error | MembersPanel.tsx:129 | PRESENT | MembersPanel.tsx:149 |
| 35 | Approval plan picker "Approval plan (optional)" (membershipEnabled) | MembersPanel.tsx:130; MembershipPlanPicker.tsx | PRESENT | MembersPanel.tsx:150 (file unchanged) |
| 36 | Request row: username/invite email, kind, state | MembershipAdmissionReview.tsx:22 | PRESENT | ListRow MembershipAdmissionReview.tsx:21-24 (kind humanised "Invitation"/"Membership application"; state as pill) |
| 37 | Approve (`POST /admin/membership-requests/{id}/approve {role_id, plan_id?}`; manageable && reviewable && (state≠invited \|\| user)) | MembershipAdmissionReview.tsx:24; MembersPanel.tsx:71 | PRESENT | MembershipAdmissionReview.tsx:26; MembersPanel.tsx:79 |
| 38 | Decline / Cancel invitation / Cancel application → reason dialog (`POST …/membership-requests/{id}/revoke`) | MembershipAdmissionReview.tsx:25; MembersPanel.tsx:135 | PRESENT | MembershipAdmissionReview.tsx:27; MembersPanel.tsx:155 |
| 39 | "Application expires <full date-time>" | MembershipAdmissionReview.tsx:28 | CHANGED | Now relative time in meta MembershipAdmissionReview.tsx:24 (exact timestamp only as the RelativeTime hover `title`, RelativeTime.tsx:27) |
| 40 | Application answers disclosure (CustomAnswersView) | MembershipAdmissionReview.tsx:29 | PRESENT | MembershipAdmissionReview.tsx:30; CustomAnswersView only tone classes changed |
| 41 | Request vouchers | MembershipAdmissionReview.tsx:30 | PRESENT | :31 |
| 42 | awaiting_payment explanatory note | MembershipAdmissionReview.tsx:31 | PRESENT | :32 |
| 43 | Admission payment reconcile (canViewFinance && admission_payment; record = canRecordPayment\|\|canManageMakerspace; waive = canManageMakerspace) | MembershipAdmissionReview.tsx:32 | PRESENT | :33 (Waive now in "Payment actions" overflow, see #11) |
| 44 | Requests loading / error / empty / pagination | MembersPanel.tsx:136-139 | PRESENT | MembersPanel.tsx:156-159 |
| 45 | Invitation requests section + pending count (membershipEnabled; `listInvitationRequests`) | MembersPanel.tsx:140; InvitationRequestsSection.tsx:47-54 | PRESENT | Rendered under Requests tab MembersPanel.tsx:160; InvitationRequestsSection.tsx:47-54 |
| 46 | Invitation request row: name, email, phone, created date, message, status | InvitationRequestsSection.tsx:60-67 | CHANGED | ListRow :58-64; created date now relative (was absolute date) |
| 47 | Per-request role select + Invite (`inviteFromRequest(id, roleId)`) | InvitationRequestsSection.tsx:70-85 | PRESENT | :67-82 |
| 48 | Decline invitation request (`declineInvitationRequest`; no confirm in either) | InvitationRequestsSection.tsx:86-88 | PRESENT | :83-85 |
| 49 | Membership plans section (membershipEnabled && canManageMakerspace) | MembersPanel.tsx:141 | BURIED | Tab "Plans" MembersPanel.tsx:108,161 |
| 50 | Plan rows: name, interval label, amount, Active/Inactive | MembershipPlansSection.tsx:119-126 | PRESENT | ListRow MembershipPlansSection.tsx:120-123 |
| 51 | Plan Edit (loads form) | MembershipPlansSection.tsx:127 | PRESENT | :124 |
| 52 | Plan Activate / Deactivate (`updatePlan {is_active}`) | MembershipPlansSection.tsx:128-130 | PRESENT | :125-127 |
| 53 | Field: Plan name (max 120, required) | MembershipPlansSection.tsx:142 | PRESENT | :138 |
| 54 | Field: Interval (PLAN_INTERVALS) | MembershipPlansSection.tsx:145 | PRESENT | :141 |
| 55 | Field: Custom days (numeric, enabled only for custom_days) | MembershipPlansSection.tsx:150 | PRESENT | :146 |
| 56 | Field: Active checkbox | MembershipPlansSection.tsx:159-162 | PRESENT | :155-157 |
| 57 | Field: Amount (≤2 decimals) | MembershipPlansSection.tsx:163 | PRESENT | :159 |
| 58 | Field: Currency (3-letter ISO) | MembershipPlansSection.tsx:166 | PRESENT | :162 |
| 59 | Create plan / Save plan / Cancel edit + client validation (`createPlan`/`updatePlan`) | MembershipPlansSection.tsx:33-41,170-173 | PRESENT | :166-169 |
| 60 | Renewal: "Automatically open the next term after settlement" (auto_renew) | MembershipRenewalFields.tsx:25 | PRESENT | unchanged file, rendered MembershipPlansSection.tsx:171 |
| 61 | Renewal: Open renewal days before expiry (0-365) | MembershipRenewalFields.tsx:23,27 | PRESENT | unchanged |
| 62 | Renewal: Grace days (0-365) | MembershipRenewalFields.tsx:23,27 | PRESENT | unchanged |
| 63 | Renewal: Checkout retries (max 3) | MembershipRenewalFields.tsx:23,27 | PRESENT | unchanged |
| 64 | Renewal: Reminder days before expiry (≤10, 1-365) | MembershipRenewalFields.tsx:23,27 | PRESENT | unchanged |
| 65 | Renewal: Reminder days after expiry | MembershipRenewalFields.tsx:23,27 | PRESENT | unchanged |
| 66 | Currently present list (`GET …/presence-sessions/current`): name, role label, until | MembersPanel.tsx:142 | BURIED | Tab "Present now" DataTable MembersPanel.tsx:107,162-168 (count also in stats) |
| 67 | Current waiver panel (canManageMakerspace; `GET/PUT /admin/makerspaces/{id}/waiver`) | MembersPanel.tsx:143 | BURIED | Tab "Waivers" MembersPanel.tsx:109,169 (MembershipWaiverPanel.tsx unchanged) |
| 68 | Waiver field: version (max 64) | MembershipWaiverPanel.tsx:28 | PRESENT | unchanged |
| 69 | Waiver field: text | MembershipWaiverPanel.tsx:29 | PRESENT | unchanged |
| 70 | Publish waiver | MembershipWaiverPanel.tsx:30 | PRESENT | unchanged |
| 71 | Deactivate waiver (`{clear:true}`; no confirm in either) | MembershipWaiverPanel.tsx:31 | PRESENT | unchanged |
| 72 | Terms dialog: Plan select (active plans) + Start term (`startTerm`) | MemberTermsDialog.tsx:58-83 | PRESENT | Now a DetailLayout drawer MemberTermsDialog.tsx:50-81 |
| 73 | Terms list: plan, start–end dates, status, Cancel term (`cancelTerm`; no confirm in either) | MemberTermsDialog.tsx:84-109 | PRESENT | :82-105 |
| 74 | Terms load error shown alongside the Start-term form | MemberTermsDialog.tsx:110 | CHANGED | Drawer `state` error (:54) replaces whole body incl. Start-term form when terms fail to load |
| 75 | Mutation error banner (role, capability, verify, witness, invite, approve) | MembersPanel.tsx:90,144 | CHANGED | Rendered in list body MembersPanel.tsx:170 — when the action was taken inside the member drawer (role, can_refer/can_verify, verify), the error is behind the drawer and not visible |
| 76 | SettlementDialog: Method (cash/upi/bank_transfer/card_machine/cheque/other), Reference (opt, max 64), Received datetime (required, validated) | SettlementDialog.tsx:43-80 | PRESENT | SettlementDialog.tsx:48-85 inside FlowLayout modal |
| 77 | SettlementDialog submit "Confirm payment" / Cancel | SettlementDialog.tsx:81-98 | CHANGED | Footer "Save receipt" (or "Save correction" when titled) :42-44; inline panel became a modal; mutation error now shown in dialog :86 |

Out-of-closure items named in the brief (not imported by MembersPanel in either version): **MemberClaimCodes** is rendered by DirectLoans (old DirectLoans.tsx:263, on the page under the loan list; new DirectLoans.tsx:227 under tab `claim-codes`) — BURIED behind a tab; issue select, "Issue claim code", one-time code + QR, active list, Revoke (no confirm in either) are all PRESENT. The QR `<img>` background changed bg-white→bg-panel, which is harmless because the backend SVG paints its own white rect (`render_qr_label_svg`). **MemberReferrals** (MemberArea.tsx:189, member side) and **OrganizationMemberships** (OrganizationsPanel.tsx:50) are still rendered and belong to other parts. The roster has no member-history, restrict/unrestrict or bulk-action UI in either version, so those are not regressions.

## cards — Member cards (panels/MemberCardsPanel.tsx)

Gate unchanged (`membership` module via TAB_MODULES). The single page became URL tabs `?cardsTab=cards | issue | scan | layout` (MemberCardsPanel.tsx:52-55). Cards/Issue/Scan use ListLayout and Layout uses SettingsLayout (:57-59). Nothing was dropped when the files shrank. CardTemplateForm's state moved verbatim into `useCardTemplateDraft.ts` (lifted to the panel at :37 so a draft survives tab switches). IssueRoster's `useCardMemberships` + printed-name state moved up to the panel (:36,:38). ScanCardBox's input/button/camera/result markup moved into the shared `components/ui/ScanWorkbench.tsx` (input+Find form :46-50, camera :42,64, result :53). API hooks (memberCards/api.ts) are unchanged. Reissue and Revoke still open their own modal dialogs (`confirms:true` only adds "…", but the dialogs are the real confirmation).

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Title "Member cards" + description | MemberCardsPanel.tsx:48-53 | PRESENT | Header MemberCardsPanel.tsx:61 (copy shortened) |
| 2 | Card status toggle Active / Revoked (visible button group) | MemberCardsPanel.tsx:55-71 | BURIED | SegmentedControl inside closed FilterPopover (`filters.controls`) :71-73. No `activeCount`, so the popover shows no badge when "Revoked" is selected |
| 3 | Print sheet (selected N / all active) (`usePrintSheet` → `…/member-cards.pdf`) | MemberCardsPanel.tsx:72-83 | PRESENT | Header primary :62-63 ("Print all active" / "Print sheet (N selected)") |
| 4 | Cards list load error (server message) | MemberCardsPanel.tsx:86-90 | CHANGED | Generic "Couldn't load member cards. Try again." + retry (opsQueryState) :67 |
| 5 | Print/PDF build error | MemberCardsPanel.tsx:91-95 | PRESENT | ErrorBlock in `detail` slot :96 (renders below the list) |
| 6 | Column Card number (sortable) | CardsTable.tsx:34-39 | PRESENT | CardsTable.tsx:29-33 |
| 7 | Column Name (sortable) | CardsTable.tsx:40 | PRESENT | :34 |
| 8 | Column Status + revoked reason | CardsTable.tsx:41-55 | PRESENT | :35-48 |
| 9 | Column Prints: count · last printed date | CardsTable.tsx:56-66 | PRESENT | :50-59 (last printed now relative time) |
| 10 | Column Photo on file / none | CardsTable.tsx:67-72 | PRESENT | :61-66 |
| 11 | Row selection (active list only) feeding print sheet | CardsTable.tsx:101-106 | PRESENT | :93-98 |
| 12 | Row Print (`/admin/member-cards/{id}/print.pdf`) | CardsTable.tsx:78-85 | PRESENT | Visible row button :73-79 |
| 13 | Row Reissue → ReissueCardDialog (reason lost/stolen/damaged/renewed; `/admin/member-cards/{id}/reissue`) | CardsTable.tsx:88-90; CardDialogs.tsx:4-61 | BURIED | Row OverflowMenu :82-83; dialog unchanged MemberCardsPanel.tsx:97-111 |
| 14 | Row Revoke → RevokeCardDialog (optional reason; warns photo deleted; `/admin/member-cards/{id}/revoke`) | CardsTable.tsx:91-93; CardDialogs.tsx:63-114 | BURIED | Row OverflowMenu (danger) :84; dialog unchanged MemberCardsPanel.tsx:112-126 |
| 15 | Empty states (no active / no revoked cards) | CardsTable.tsx:114-119 | PRESENT | ListLayout empty with "Issue a card" action MemberCardsPanel.tsx:68-70; CardsTable :106-110 |
| 16 | Scan card section (was on the page) | MemberCardsPanel.tsx:115 | BURIED | Tab "Scan" + header secondary "Scan a card" :54,64,94 |
| 17 | Payload input + "Check card" (Enter submits) (`POST …/member-cards/resolve`) | ScanCardBox.tsx:35-56 | PRESENT | ScanWorkbench form "Card payload" + Find ScanWorkbench.tsx:46-50 |
| 18 | Camera scan resolves without echoing payload into the input | ScanCardBox.tsx:57-63,101-111 | PRESENT | ScanWorkbench.tsx:42,64 (onScan → lookup, input untouched) |
| 19 | Outcome read-out ok / revoked / inactive (live region) | ScanCardBox.tsx:69-77 | PRESENT | ResultPanel tone + OUTCOME_TEXT ScanCardBox.tsx:28; adds "Next card" and a 5-item "Recent card checks" log (outcome only) :16-21,38 |
| 20 | OK detail: card number, printed name, membership status, photo | ScanCardBox.tsx:78-94 | PRESENT | ScanCardBox.tsx:30-36 |
| 21 | Refused card withholds identity | ScanCardBox.tsx:13-18 | PRESENT | children only when outcome==="ok" :30 |
| 22 | Resolve error | ScanCardBox.tsx:95-99 | PRESENT | state error with server message :26-27 (input disabled until Retry) |
| 23 | Issue roster "Members without a card" (was on the page) (`GET /admin/makerspaces/{id}/memberships`) | MemberCardsPanel.tsx:116; IssueRoster.tsx:21-29 | BURIED | Tab "Issue" :54,95; the stat "Members without a card" links to it :66 |
| 24 | Roster row: name + membership status badge | IssueRoster.tsx:45-46 | PRESENT | IssueRoster.tsx:35-38 |
| 25 | Printed name (optional) input | IssueRoster.tsx:47-56 | PRESENT | :39-41 |
| 26 | Issue card (`POST …/member-cards/{membershipId}/issue`) | IssueRoster.tsx:57-66 | PRESENT | :42-44 (per-row "Issuing…") |
| 27 | Roster load error (server message) / empty message | IssueRoster.tsx:30-38 | CHANGED | Generic opsQueryState error; empty "Every active member has a card." :33-34 |
| 28 | Issue error | IssueRoster.tsx:70-74 | PRESENT | ErrorBlock :47 |
| 29 | Card layout section (was collapsed CollapsibleSection) | CardTemplateForm.tsx:54 | PRESENT | Tab "Card layout" → SettingsLayout CardTemplateForm.tsx:31 (equivalent click depth) |
| 30 | Page (A4 / LETTER / CR80) | CardTemplateForm.tsx:65-77 | PRESENT | SettingsRow :35-37 |
| 31 | Orientation (portrait / landscape) | CardTemplateForm.tsx:78-92 | PRESENT | :38-40 |
| 32 | Card width (mm) | CardTemplateForm.tsx:10,93-104 | PRESENT | :41-42 |
| 33 | Card height (mm) | CardTemplateForm.tsx:11 | PRESENT | :41-42 |
| 34 | Page margin (mm) | CardTemplateForm.tsx:12 | PRESENT | :41-42 |
| 35 | Gap between cards (mm) | CardTemplateForm.tsx:13 | PRESENT | :41-42 |
| 36 | Name font size (pt) | CardTemplateForm.tsx:14 | PRESENT | :41-42 |
| 37 | Other text size (pt) | CardTemplateForm.tsx:15 | PRESENT | :41-42 |
| 38 | Fields printed on the front (printed_name, card_number, makerspace, issued_at, membership_role) | CardTemplateForm.tsx:107-122 | PRESENT | :45-47 |
| 39 | Back-of-card text | CardTemplateForm.tsx:124-131 | PRESENT | :48-49 |
| 40 | Print the member photo (include_photo) | CardTemplateForm.tsx:19,133-145 | PRESENT | :50-51 |
| 41 | Print the card QR code (include_qr) | CardTemplateForm.tsx:20 | PRESENT | :50-51 |
| 42 | Print crop marks (crop_marks) | CardTemplateForm.tsx:21 | PRESENT | :50-51 |
| 43 | Save layout (`PUT member-card-template`); dirty draft not clobbered by refetch | CardTemplateForm.tsx:33-38,152-159 | PRESENT | Sticky SettingsActions "Save changes" + new "Discard", shown only when dirty :54-56; seed logic in useCardTemplateDraft.ts:12-17 |
| 44 | Template load error (server message) | CardTemplateForm.tsx:57-61 | CHANGED | Generic "Couldn't load the card layout." :32 |
| 45 | Template save error | CardTemplateForm.tsx:147-151 | PRESENT | `actions.error` :54 |

No card-template preview existed in the old code, so its absence is not a regression.

### Counts

| page | PRESENT | BURIED | CHANGED | MISSING | total |
|---|---|---|---|---|---|
| members | 54 | 17 | 6 | 0 | 77 |
| cards | 37 | 5 | 3 | 0 | 45 |
| **total** | 91 | 22 | 9 | 0 | 122 |

### Restore candidates

Nothing is MISSING: every capability and API call in both pages is still reachable. The candidates below are buried or changed items, most important first.

1. **P1 — Member payment status hidden from the roster** (members #9-#11). OLD `MemberRow` rendered `<PaymentReconcileActions …>` inline (MembersPanel.tsx:173), so "Mark offline" and "Waive" were on the row. NEW renders it only inside the drawer (MemberRow.tsx:57). Restore a compact read-out in the ListRow `meta`/`right` slot when `canViewFinance && member.payment?.status === "pending"`: an amount plus a "Pending" StatusPill. Make "Record payment" a row-level OverflowMenu item (gate `canRecordPayment || canManageMakerspace`) that opens SettlementDialog. Also consider putting `Waive` back as a visible button next to "Mark offline" in PaymentReconcileActions.tsx:68. The two-level menu (member drawer → "Payment actions" overflow) affects every caller of this shared component.
2. **P2 — Drawer actions hide their own errors** (members #75). `changeRole`/`capabilities`/`verify` errors render at MembersPanel.tsx:170, behind the open drawer. Pass the relevant `error` into `MemberRow` and render it inside the drawer `main` (MemberRow.tsx:47-58), or use DetailLayout's callout.
3. **P2 — Role change moved into the drawer** (members #17). OLD had an inline select per row (MembersPanel.tsx:176, `PATCH /admin/memberships/{id}/role`). The drawer placement fits the Yuyu "rare actions" rule, but add a "Change role" OverflowMenu item (MemberRow.tsx:39-43) that opens the drawer, so the action can be found from the row.
4. **P2 — Card status filter hidden in the popover** (cards #2). OLD had visible Active/Revoked toggle buttons (MemberCardsPanel.tsx:56-71). Move the `SegmentedControl` out of `filters.controls` into `filters.toolbar`/`sort`, or make Active/Revoked sub-tabs; at least pass `activeCount: status === "revoked" ? 1 : 0` (MemberCardsPanel.tsx:71).
5. **P2 — Card Reissue/Revoke moved to the row overflow** (cards #13-14). OLD CardsTable.tsx:88-93 had visible buttons. Overflow is acceptable for these rarer actions, and both still open their confirmation dialogs. Keep as is.
6. **P2 — Members status filter (Active/Revoked) inside FilterPopover** (members #21). OLD MembersPanel.tsx:97 was a visible select. It is acceptable because the badge count is wired (`activeCount`). Optionally show a removable chip when it is set (ListViewControls `chips`).
7. **P2 — Saved-view menu labels** (members #24, #26). SavedViewsMenu.tsx:44-45 read "Save current view?" / "Manage views?". This is almost certainly a typo for "…" (use `confirms: true` or "…"). Picking a saved view moved from a visible select (SavedViewsMenu.tsx:35-38) into the "Views" menu, which is acceptable.
8. **P2 — Can refer / Can verify / Verify / Terms / Vouchers moved off the row** (members #8, #13-16). OLD put them inline (MembersPanel.tsx:173-176). NEW has Verify and Terms in the row overflow, and refer/verify toggles and vouchers in the drawer. This matches Yuyu (settings as SettingsRow in the drawer), so no change is needed beyond #2.
9. **P2 — Sections now behind tabs** (members #29, #49, #66, #67; cards #16, #23). The requests queue, plans, presence, waivers, card scan and issue roster used to sit on one page. Tabs with counts are the intended Yuyu structure. Consider giving the "Requests" tab a count of pending items only (it currently shows the total `requests.data.count`, MembersPanel.tsx:106). Then a non-zero badge would mean there is work to do.
10. **P3 — MemberTermsDialog error state hides the Start-term form** (members #74). In MemberTermsDialog.tsx:54, only put the drawer into the `error` state when *plans* fail. Keep the terms-list error inline as the old code did (MemberTermsDialog.tsx:110 old).
11. **P3 — Server error detail replaced by generic copy** (cards #4, #27, #44). opsQueryState drops `error.message` for cards, memberships and template loads. Pass the server message through the `error` string if operators relied on it.
12. **P3 — Absolute dates became relative** (members #39 application expiry; #46 invitation-request date; cards #9 last printed). `RelativeTime` already exposes the absolute value as `<time dateTime>` plus a hover `title` (RelativeTime.tsx:27). The exact expiry is hover-only now, which is acceptable; no action needed.
13. **P3 — SettlementDialog button copy** (members #77). "Confirm payment" became "Save receipt", and the form is now a modal instead of an inline panel. Behaviour is unchanged, so no action is needed.

---

Scope: tab `users` (panels/Users.tsx and its closure), the superadmin MakerspacePicker, and all staff header/dock chrome. OLD = d3e5ed29, NEW = working tree of feature/design-revamp. Line refs are OLD `File:line` → NEW `File:line`.

## users — Staff & roles (panels/Users.tsx)

Routing and the gate are unchanged: `users` is allowed when `canManageMakerspace` (staffAccess.ts, same in both versions). The page used to be one `Panel` with the table, then StaffInvitations, then RoleManager inside a collapsed `<details>`. It is now a `ListLayout` (Users.tsx:179-288) with tabs Staff / Roles / Invitations (Users.tsx:170-174), a header primary "Add staff", a superadmin secondary "Create makerspace", and new stats (Staff count, Roles count, Users.tsx:183) plus tab counts. Every modal and ConfirmDialog is still mounted through `detail` (Users.tsx:224-288). Destructive actions still open the page's own ConfirmDialog. None of them relies on `Action.confirm`/`confirms`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page heading "Users" | Users.tsx:171 | PRESENT | Now "Staff & roles" h1 with subtitle, Users.tsx:180 |
| 2 | Empty state when the account has no makerspaces | Users.tsx:164-166 | PRESENT | Users.tsx:166-168 (ListLayout empty) |
| 3 | First-staff invitation banner after creating a makerspace: delivery status, read-only link (select on focus), "Dismiss invitation link" | Users.tsx:173 | PRESENT | Users.tsx:186 (inside body, so hidden while the active query is loading or errored) |
| 4 | Makerspace `<select>` (shown when >1 makerspace; resets the role filter) | Users.tsx:175-182 | CHANGED | Users.tsx:188-195 sits inside `body`, which `QueryContent` (LayoutFrame.tsx:39-45) replaces with a skeleton or ErrorBlock. If the selected space's memberships or roles request fails (e.g. a 403 on a space where the actor lacks manage rights), the selector disappears and the page is stuck on Retry. The old page kept the selector next to the error text |
| 5 | Role filter `<select>` ("All roles" plus the distinct role names in the current list) | Users.tsx:183-189, 84-92 | PRESENT | Users.tsx:196-202. Also shows on the Roles and Invitations tabs, where it does nothing |
| 6 | "Add staff" (disabled when no assignable role) | Users.tsx:191 | PRESENT | Header primary, Users.tsx:180, now with disabledReason |
| 7 | "Create makerspace", superadmin only (`isSuperadmin`) | Users.tsx:192 | PRESENT | Header secondary, Users.tsx:180. Visible on desktop; on mobile it is in the header overflow (PageHeader.tsx:10,24-27) |
| 8 | Inline error text (memberships, roles or restore error message) | Users.tsx:168,196 | CHANGED | A load error for the active tab's query now replaces the whole body with a generic "Couldn't load staff and roles. Try again." plus Retry (Users.tsx:181), and the server message is lost. Restore errors still show inline (Users.tsx:176,206) |
| 9 | Assignable-role ceiling (non-superadmin: roles without manage_makerspace whose actions are within the actor's own) | Users.tsx:74-82 | PRESENT | Users.tsx:76-84 |
| 10 | Refetch `/auth/me` and invalidate memberships and roles after any staff change | Users.tsx:94-100 | PRESENT | Unchanged block |
| 11 | Staff invitations section (gate: `canManageRoles && enabled_features.includes("staff.invitations")`) | Users.tsx:208 | BURIED | Now the "Invitations" tab, Users.tsx:173 (tab gate) and :218 (render gate). The gate is identical |
| 12 | Role manager (gate: `canManageRoles`), previously a collapsed `<details>` | Users.tsx:209-211 | PRESENT | "Roles" tab, Users.tsx:172,219-221. Still one click, as before |
| 13 | Tab state when the makerspace changes | n/a (no tabs) | CHANGED | `tab` (Users.tsx:46) is not reset in the select's onChange (Users.tsx:191). On Invitations or Roles, switching to a space without `staff.invitations` or without role rights leaves `tab="invitations"`/`"roles"`. Tabs.tsx:10 then marks Staff as selected while the body renders nothing: a blank page |
| 14 | UsersTable loading text "Loading staff..." | UsersTable.tsx:35 | PRESENT | UsersTable.tsx:35 (the ListLayout skeleton now shows first) |
| 15 | Empty / filtered empty "No staff / No memberships match this filter." | UsersTable.tsx:36 | PRESENT | UsersTable.tsx:36 |
| 16 | Column Username | UsersTable.tsx:41,43 | PRESENT | ListRow title plus avatar, UsersTable.tsx:40 (no column headers any more) |
| 17 | Column Email ("-" when blank) | UsersTable.tsx:44 | PRESENT | Meta, UsersTable.tsx:41 ("No email") |
| 18 | Column Role (assigned role name or prettified legacy role) | UsersTable.tsx:45,82-84 | PRESENT | Meta, UsersTable.tsx:41,75-77 |
| 19 | Column Makerspace | UsersTable.tsx:46 | PRESENT | Meta, UsersTable.tsx:41 |
| 20 | Column Access (badge: active=success, restricted=warn, else danger) | UsersTable.tsx:47,77-80 | PRESENT | StatusPill, UsersTable.tsx:42,70-73 |
| 21 | Row "Change role" (disabled when no assignable roles) | UsersTable.tsx:49 | PRESENT | Visible row button, UsersTable.tsx:43 |
| 22 | Change-role modal: Role select (defaults to current or first), Save role / Cancel, error; calls `assignRole` | UsersTable.tsx:58,63-75 | PRESENT | UsersTable.tsx:51,56-68 (unchanged) |
| 23 | Row "Restrict" | UsersTable.tsx:50 | BURIED | Row OverflowMenu, UsersTable.tsx:45 |
| 24 | Restrict modal: Status (Restricted/Suspended), Reason (required textarea), Apply; POST `/admin/users/{id}/restrict` | RestrictUserModal.tsx:26-36; Users.tsx:110-119 | PRESENT | Same file, unchanged; Users.tsx:112-121,236-245 |
| 25 | Row "Reset password" | UsersTable.tsx:51 | BURIED | Row OverflowMenu, UsersTable.tsx:46 |
| 26 | Reset-password modal: optional temporary password (min 8, blank = auto-generate), result screen with temporary password plus Copy/Copied, "won't be shown again", Close; POST `/admin/users/{id}/reset-password` | ResetPasswordModal.tsx:31-98; Users.tsx:128-138 | PRESENT | Unchanged apart from styling; Users.tsx:130-140,255-265 |
| 27 | Row "Restore" (disabled when access is active) | UsersTable.tsx:52 | BURIED | Row OverflowMenu with disabledReason "Access is already active.", UsersTable.tsx:47 |
| 28 | Restore ConfirmDialog; POST `/admin/users/{id}/restore-access` | Users.tsx:120-123,255-263 | PRESENT | Users.tsx:266-274 (page-owned ConfirmDialog kept) |
| 29 | Row "Revoke" (remove membership) | UsersTable.tsx:53 | BURIED | Row OverflowMenu (danger), UsersTable.tsx:48 |
| 30 | Revoke ConfirmDialog (names the role and makerspace; "Their account is not deleted"); DELETE `/admin/memberships/{id}` | Users.tsx:124-127,264-276 | PRESENT | Users.tsx:275-287 (page-owned ConfirmDialog kept) |
| 31 | Add staff: Username field (required) | AddStaffModal.tsx:34-36 | PRESENT | Unchanged |
| 32 | Add staff: Email field (type email) | AddStaffModal.tsx:37-39 | PRESENT | Unchanged |
| 33 | Add staff: First name | AddStaffModal.tsx:41-43 | PRESENT | Unchanged |
| 34 | Add staff: Last name | AddStaffModal.tsx:44-46 | PRESENT | Unchanged |
| 35 | Add staff: Password (required, new-password, hint "share it with the new staff member") | AddStaffModal.tsx:48-50 | PRESENT | Unchanged |
| 36 | Add staff: Role select (assignable roles) | AddStaffModal.tsx:52-57 | PRESENT | Unchanged |
| 37 | Add staff: Makerspace read-out (fixed to the page-level selection; superadmins choose the space with the page select) | AddStaffModal.tsx:58-60 | PRESENT | Unchanged |
| 38 | Add staff: submit disabled rule, field errors, general error; `createMembership(msId, staffPayload)` | AddStaffModal.tsx:30,62; Users.tsx:102-105 | PRESENT | Unchanged; Users.tsx:104-107 |
| 39 | Roles: loading / error / empty states | RoleManager.tsx:41-44 | PRESENT | RoleManager.tsx:41-45, plus a new capabilities-error row (:42) with Retry |
| 40 | Roles: "New role" button | RoleManager.tsx:37 | PRESENT | RoleManager.tsx:37 |
| 41 | Role row: name | RoleManager.tsx:48 | PRESENT | ListRow title, RoleManager.tsx:48 |
| 42 | Role row: Default/Custom tag | RoleManager.tsx:49 | PRESENT | StatusPill, RoleManager.tsx:51 |
| 43 | Role row: Protected tag | RoleManager.tsx:50 | PRESENT | StatusPill, RoleManager.tsx:51 |
| 44 | Role row: member count | RoleManager.tsx:51 | PRESENT | "N staff", RoleManager.tsx:49 (adds "N actions") |
| 45 | Role row: granted capability labels | RoleManager.tsx:52 | PRESENT | Meta, RoleManager.tsx:49 |
| 46 | Role row: Edit | RoleManager.tsx:53 | PRESENT | Row click (RoleManager.tsx:50) plus overflow Edit (:52) |
| 47 | Role row: Delete (disabled when protected, has members, or a delete is pending) | RoleManager.tsx:54 | BURIED | Row OverflowMenu Delete with disabledReasons (RoleManager.tsx:53), plus DangerZone in the editor drawer (RoleEditor.tsx:74; hidden for protected roles; not disabled while a delete is pending) |
| 48 | Delete-role ConfirmDialog (danger) → `deleteRole`; error shown | RoleManager.tsx:26-30,42,60-71 | PRESENT | RoleManager.tsx:26-30,43,60-71. The DangerZone path uses `confirms` (which only adds "…"), but its onDelete just sets `pendingDelete`, so the real ConfirmDialog still opens |
| 49 | Clone role | none | PRESENT | Never existed. The equivalent is the "Start from" presets (row 52) |
| 50 | Role editor container (Modal xl, Cancel disabled while saving) | RoleEditor.tsx:68 | PRESENT | DetailLayout drawer with "Discard", RoleEditor.tsx:72-73 |
| 51 | Protected-default note ("cannot be deleted; core capabilities are locked") | RoleEditor.tsx:70 | PRESENT | RoleEditor.tsx:76 |
| 52 | "Start from" presets (new role only): Space Manager, Inventory Manager, Machine Manager, Membership Coordinator, Treasurer, Front-desk cashier, Front Desk | RoleEditor.tsx:9-17,71 | PRESENT | RoleEditor.tsx:10-18,77 |
| 53 | Role Name input; name and granted_actions field errors | RoleEditor.tsx:72-74 | PRESENT | RoleEditor.tsx:78-80 |
| 54 | Capability checkboxes grouped by `capability.group` (h3 per group): label, description, disabled plus `lock_reason` when not grantable | RoleEditor.tsx:31-35,75 | PRESENT | RoleEditor.tsx:34-38,81 (card style; also shows the action code) |
| 55 | Save role (disabled: pending / blank name / !canManageRoles) → `createRole` / `updateRole` | RoleEditor.tsx:42-53,68 | CHANGED | RoleEditor.tsx:45-57,73. Saving is now also blocked until the capability catalog loads (`catalogState`, RoleManager.tsx:58). The old code would send `granted_actions: []` if the catalog failed to load, stripping every action. This is a safety improvement, not a regression |
| 56 | Hint for a new role with manage_machines ("save, then reopen to choose machines") | RoleEditor.tsx:78-83 | PRESENT | RoleEditor.tsx:84-89 |
| 57 | Generic save error | RoleEditor.tsx:84 | PRESENT | RoleEditor.tsx:90 |
| 58 | Machine scope editor: loading / error | RoleMachineScopeEditor.tsx:43-44 | PRESENT | Same lines (file unchanged apart from row styling at :128) |
| 59 | Machine scope: "not limited" note when `scoping_applies` is false | RoleMachineScopeEditor.tsx:47-56 | PRESENT | Same |
| 60 | Machine scope: intro text and red "Nothing selected — cannot manage any machine" warning | RoleMachineScopeEditor.tsx:68-80 | PRESENT | Same |
| 61 | Machine scope: Machine types checkboxes (Built-in / This makerspace) | RoleMachineScopeEditor.tsx:81-87 | PRESENT | Same |
| 62 | Machine scope: Individual machines checkboxes (Retired note) | RoleMachineScopeEditor.tsx:88-94 | PRESENT | Same |
| 63 | Machine scope: "Save machine scope", Saved indicator, error → `setRoleMachineScope` | RoleMachineScopeEditor.tsx:32-41,95-101 | PRESENT | Same (mounted in the drawer, RoleEditor.tsx:83) |
| 64 | Invitations: heading "Staff invitations" | StaffInvitations.tsx:26 | PRESENT | StaffInvitations.tsx:27 |
| 65 | Invite form: Email (required, type email) | StaffInvitations.tsx:28 | PRESENT | StaffInvitations.tsx:29 |
| 66 | Invite form: Role select (roles with at least one action, required) | StaffInvitations.tsx:24,29-31 | PRESENT | StaffInvitations.tsx:25,30-32 |
| 67 | "Invite staff" → POST `/admin/makerspaces/{ms}/staff-invitations` (expires_in_days 7) | StaffInvitations.tsx:20-21,32 | PRESENT | StaffInvitations.tsx:21-22,33 |
| 68 | Delivery status plus private accept link (read-only, select on focus) | StaffInvitations.tsx:34-36 | PRESENT | StaffInvitations.tsx:35-38, plus a new "Copy link" button |
| 69 | List / create / update errors; loading text | StaffInvitations.tsx:37-38 | PRESENT | StaffInvitations.tsx:39-40, plus a new empty state (:41) |
| 70 | Invitation row read-out: email · role · Accepted / Revoked / "Expires <date>" | StaffInvitations.tsx:40 | CHANGED | ListRow (StaffInvitations.tsx:42-44): pill Accepted / Revoked / "Unused", meta "Expires <RelativeTime>" on every row, including accepted and revoked ones. An expired unused invite is labelled "Unused", not expired |
| 71 | Row "Resend" → POST `.../{id}/resend` | StaffInvitations.tsx:42 | PRESENT | StaffInvitations.tsx:45 |
| 72 | Row "Revoke" → POST `.../{id}/revoke` (no confirm in either version) | StaffInvitations.tsx:43 | BURIED | Row OverflowMenu, StaffInvitations.tsx:46 |
| 73 | Invitations pagination Previous/Next | StaffInvitations.tsx:46 | PRESENT | StaffInvitations.tsx:47 |
| 74 | Create-makerspace wizard container (Modal; Cancel / Back / Next / "Create makerspace"; "Creating…"; close blocked while pending) | CreateMakerspaceModal.tsx:28-32 | PRESENT | FlowLayout dialog with a step rail, CreateMakerspaceModal.tsx:28-32. FlowLayout.tsx:34,51 keeps Cancel blocked while busy |
| 75 | Step indicator "Step N of 5: <label>" (Identity, Profile and hours, Modules and pack, First staff, Review) | CreateMakerspaceModal.tsx:7,33 | PRESENT | CreateMakerspaceModal.tsx:7,34, plus the FlowSteps rail (:29) |
| 76 | Step 1: Name (required, max 200) | CreationWizardSteps.tsx:13-15 | PRESENT | Same lines |
| 77 | Step 1: Public code (required, max 4, auto-uppercased) | CreationWizardSteps.tsx:13-15 | PRESENT | Same, plus native `pattern` [A-Z0-9]{4} and a hint |
| 78 | Step 1: Slug (required, max 50) | CreationWizardSteps.tsx:13-15 | PRESENT | Same, plus `pattern` and a hint "…/m/" |
| 79 | Step 1: Location (optional, max 200) | CreationWizardSteps.tsx:13-15 | PRESENT | Same |
| 80 | Step 1: platform-access / two-archive-recipients note (superadmin_access_enabled is always true) | CreationWizardSteps.tsx:16; forms.ts:17 | PRESENT | Same |
| 81 | Step 2: "Leave unchanged to use pack defaults" note | CreationWizardSteps.tsx:19 | PRESENT | Same |
| 82 | Step 2: Timezone (max 100, Intl-validated) | CreationWizardSteps.tsx:20-22; CreateMakerspaceModal.tsx:18-20 | PRESENT | Same |
| 83 | Step 2: Country code (2, uppercased) | CreationWizardSteps.tsx:20-22 | PRESENT | Same |
| 84 | Step 2: Currency (3, lowercased, validated) | CreationWizardSteps.tsx:20-22; CreateMakerspaceModal.tsx:21 | PRESENT | Same |
| 85 | Step 2 hours: "Set weekly opening hours" toggle plus explanation | MakerspaceHoursEditor.tsx:24-28 | PRESENT | MakerspaceHoursEditor.tsx:24-28 |
| 86 | Step 2 hours: per-weekday intervals (start/end HH:MM, Remove, "Add <day> interval", max 24) | MakerspaceHoursEditor.tsx:3-20,29-33 | PRESENT | Same |
| 87 | Step 2 hours: dated exceptions (date, intervals, "Remove exception N", "Add exception", max 366); validated by `validateHours` | MakerspaceHoursEditor.tsx:34-48; CreateMakerspaceModal.tsx:22-23 | PRESENT | Same |
| 88 | Step 3: Saved install profile select ("No saved profile" default) | SpacePackProfilePicker.tsx:12-18 | PRESENT | SpacePackProfilePicker.tsx:14-20 |
| 89 | Step 3: install-profile pagination (Previous/Next profiles when >24) | SpacePackProfilePicker.tsx:20-25 | PRESENT | SpacePackProfilePicker.tsx:22-27 |
| 90 | Step 3: install-profile load error (server message) | SpacePackProfilePicker.tsx:19 | CHANGED | `SettingsQueryState` (SpacePackProfilePicker.tsx:13) replaces the whole picker with a generic ErrorBlock plus Retry. The inner error branch (:21) is now dead code. The wizard can still continue with no pack |
| 91 | Step 3: "Core modules remain installed" note | CreationWizardSteps.tsx:27 | PRESENT | Same |
| 92 | Step 3: "Choose module families instead of defaults" toggle | CreationWizardSteps.tsx:28 | PRESENT | Same |
| 93 | Step 3: module checkboxes — Events, Bookings, Machines, Maintenance, Membership, Printing, Online payments, Reports, Notifications | CreationWizardSteps.tsx:8,29 | PRESENT | CreationWizardSteps.tsx:8,29 (card grid) |
| 94 | Step 4: optional-invite note, First staff email, First staff role (Space / Inventory / Machine Manager) | CreationWizardSteps.tsx:31-37 | PRESENT | Same |
| 95 | Step 5 Review: Name, Public address, Profile overrides, Modules, Saved pack, First staff | CreationWizardSteps.tsx:38 | PRESENT | Same |
| 96 | Client validation messages (role="alert") and server error | CreateMakerspaceModal.tsx:15-27,40 | PRESENT | CreateMakerspaceModal.tsx:15-27,42 |
| 97 | POST `/admin/makerspaces` (creation_setup.profile / modules / first_staff_invite, install_profile_id); invalidate makerspaces; show invite banner | Users.tsx:139-147; forms.ts:216-230 | PRESENT | Users.tsx:141-149; forms.ts unchanged |

New in this tab (no old counterpart, not counted): Staff/Roles stat cards and tab counts (Users.tsx:171-172,183), a live preview aside in the wizard (CreateMakerspaceModal.tsx:41), "Copy link" for invitations, and a "Delete role" DangerZone in the role drawer. Pre-existing gaps that did not regress: the `revoke` mutation error is never displayed (old Users.tsx:168, new :176), and `msId` defaults to `makerspaces[0]` rather than the shell's active makerspace (old :43, new :44).

## (picker) — Superadmin makerspace picker (MakerspacePicker.tsx)

The gate is identical (StaffApp.tsx is byte-identical to d3e5ed29). The picker shows when `!singleTenantLocked && isSuperadmin && (selected === null || no active makerspace) && !globalRoute` (StaffApp.tsx:129-151). The old page was a hand-built `<main>` card grid; it is now a standalone `DashboardLayout` (MakerspacePicker.tsx:31-42).

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Space Works badge | MakerspacePicker.tsx:30 | PRESENT | Header meta, MakerspacePicker.tsx:35 |
| 2 | "Super Admin" eyebrow | MakerspacePicker.tsx:31 | CHANGED | Replaced by a greeting/date eyebrow (MakerspacePicker.tsx:33). Nothing on the page says Super Admin any more |
| 3 | Title "Choose a makerspace to operate" | MakerspacePicker.tsx:32 | PRESENT | MakerspacePicker.tsx:33 |
| 4 | "Signed in as {username}" | MakerspacePicker.tsx:33 | PRESENT | Greeting eyebrow "Good …, {username}", MakerspacePicker.tsx:33 |
| 5 | Theme toggle | MakerspacePicker.tsx:36 | PRESENT | Header meta, MakerspacePicker.tsx:35 |
| 6 | Sign out | MakerspacePicker.tsx:37-39 | PRESENT | Header secondary, MakerspacePicker.tsx:36 (on mobile it is in the header overflow) |
| 7 | Loading "Loading makerspaces…" | MakerspacePicker.tsx:43-44 | PRESENT | Skeleton via `state`, MakerspacePicker.tsx:32 |
| 8 | Empty: "No makerspaces exist yet. Create one from the Django control plane." | MakerspacePicker.tsx:45-48 | CHANGED | MakerspacePicker.tsx:38: copy reads "Create one from Staff & roles or the control plane", and an "Open control plane" action with `href: "/control/"` was added. (a) ActionControl → RouteLink (RouteLink.tsx:11-12) does a client-side react-router navigation to `/control/`, which hits the catch-all `NotFoundPage` (AppRoutes.tsx:109) instead of the Django admin, and in dev `/control/` is served by the API origin. (b) "Staff & roles" cannot be reached without a selected makerspace, so that advice is a dead end |
| 9 | Card read-out: public_code (or slug) | MakerspacePicker.tsx:58-60 | PRESENT | ListRow meta, MakerspacePicker.tsx:40 |
| 10 | Card read-out: makerspace name | MakerspacePicker.tsx:61 | PRESENT | ListRow title, MakerspacePicker.tsx:38 |
| 11 | "Superadmin access: Off" warning badge | MakerspacePicker.tsx:62-66 | PRESENT | StatusPill, MakerspacePicker.tsx:42 |
| 12 | Select a makerspace ("Operate this makerspace →") → `chooseMakerspace` | MakerspacePicker.tsx:55,67 | PRESENT | Row click, MakerspacePicker.tsx:40-41 |

New: a "Find a makerspace" search over name, code and slug, with a filtered empty state (MakerspacePicker.tsx:27,30,37-38).

## (chrome) — Staff header, dock and workspace frame (StaffHeader.tsx, StaffDock.tsx, StaffDockPopover.tsx, staffNavIcons.tsx, useDockAnchor.ts, StaffWorkspace.tsx)

StaffHeader, StaffDock, StaffDockPopover, staffNavIcons and useDockAnchor were deleted. StaffWorkspace.tsx:158-205 now wraps the content in `StaffShell` (StaffShell.tsx), which renders `components/shell/AppShell`: a desktop Sidebar (logo, WorkspaceSwitcher, search, nav sections, footer links, JobTrayPill, UserMenu), a MobileTopBar plus SidebarDrawer below `lg`, and BottomTabs for handout-only staff. `staffTabs.ts` and `staffAccess.ts` are unchanged, so tab permissions and module gates are identical.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Space Works brand mark | StaffHeader.tsx:39 | PRESENT | Sidebar.tsx:15; mobile symbol MobileTopBar.tsx:10 |
| 2 | Active makerspace public_code (or slug) eyebrow; "No workspace" fallback | StaffHeader.tsx:41-43 | MISSING | The WorkspaceSwitcher shows name and role only (StaffShell.tsx:52; WorkspaceSwitcher.tsx:10-11). The code appears nowhere in the chrome |
| 3 | Active makerspace name (header h1) | StaffHeader.tsx:44-46 | PRESENT | WorkspaceSwitcher label (WorkspaceSwitcher.tsx:10) and MobileTopBar.tsx:11. No longer the page h1 |
| 4 | Role name (Super Admin takes precedence) | StaffHeader.tsx:47; StaffWorkspace.tsx:106-108 | PRESENT | Workspace subtitle (StaffShell.tsx:52) plus UserMenu role (StaffShell.tsx:62; UserMenu.tsx:10); computation unchanged at StaffWorkspace.tsx:146-148 |
| 5 | Active-makerspace `<select>` (`!singleTenantLocked && makerspaces.length > 1`, any staff) → `chooseMakerspace` | StaffHeader.tsx:51-64 | BURIED | WorkspaceSwitcher disclosure menu: one entry per makerspace (StaffShell.tsx:49; WorkspaceSwitcher.tsx:13-15). It takes an extra click and does not mark the current makerspace. The switcher is locked when `singleTenantLocked || makerspaces.length === 1` (StaffShell.tsx:53) |
| 6 | Username chip | StaffHeader.tsx:65-67 | PRESENT | UserMenu trigger, UserMenu.tsx:9 |
| 7 | "Public inventory" link (`/` when single-tenant, else `/m/{slug}`) | StaffHeader.tsx:31-33,68-72 | PRESENT | "View public page ↗": sidebar footer link (StaffShell.tsx:47,59; Sidebar.tsx:25) and in the switcher menu (StaffShell.tsx:50). On mobile it is inside the navigation drawer |
| 8 | "Switch makerspace" — visible primary button, superadmin and not single-tenant → `setSelected(null)` (back to the picker) | StaffHeader.tsx:73-77; StaffWorkspace.tsx:126 | BURIED | Inside the WorkspaceSwitcher menu (StaffShell.tsx:50), or inside the UserMenu when there is only one makerspace (StaffShell.tsx:62) |
| 9 | Theme toggle | StaffHeader.tsx:78 | BURIED | Inside the UserMenu disclosure, UserMenu.tsx:12 |
| 10 | Sign out | StaffHeader.tsx:79-81 | BURIED | Inside the UserMenu disclosure, UserMenu.tsx:13 |
| 11 | Command palette trigger ("Search and commands Ctrl/⌘ K") plus the global Ctrl/⌘K hotkey | StaffWorkspace.tsx:134; CommandPalette.tsx (old button) | PRESENT | Sidebar search button (Sidebar.tsx:17-20), mobile search icon (MobileTopBar.tsx:12-13), controlled palette (StaffShell.tsx:60,65-67); hotkey kept |
| 12 | Background JobTray ("Background jobs (N running)", per-job status, Retry status, Dismiss) at the top of the content | StaffWorkspace.tsx:136 | PRESENT | JobTrayPill in the sidebar footer (StaffShell.tsx:61; Sidebar.tsx:27), which opens a modal (JobTray.tsx pill branch). On mobile it is BURIED: MobileTopBar has no status slot, so it is visible only inside the drawer |
| 13 | SetupChecklist on Dashboard (`canManageMakerspace && activeTab === "dashboard"`) | StaffWorkspace.tsx:137 | CHANGED | Passed as `progress` (StaffWorkspace.tsx:178 → StaffTabContent → DashboardPanel → DashboardLayout.tsx:41-44). It now sits inside `QueryContent`, so it is hidden while the dashboard query is loading or errored. The gate is unchanged |
| 14 | Access-denied empty state with "Go to <tab>" | StaffWorkspace.tsx:138-147 | PRESENT | StaffWorkspace.tsx:163-173 (adds a "Page unavailable" h1) |
| 15 | Skip link and the `#main-content` focus target | StaffWorkspace.tsx:119,135 | PRESENT | AppShell.tsx:46,50 |
| 16 | Section navigation: 9 dock groups (Operate, Inventory, Machines, Events, Bookings, Members, Insights, Organizations, Admin) with icons and colour tones | StaffDock.tsx:27-36,55-63,162-215; staffNavIcons.tsx; staffAccess.ts:55-65 | CHANGED | Sidebar sections (sidebarSections.ts:82-92): Home, Front desk, Inventory, Machines, Community, Insights, Organizations ("Across venues"), Settings family, Platform. Per-tab lucide icons (:98-108); group colour tones dropped. All 42 tab keys are still reachable (mapping below) |
| 17 | Tab link per item → `staffTabPath(tab, guestOnly, slug, singleTenantLocked)` plus `setTab` | StaffDockPopover.tsx:90-101 | PRESENT | `path()` plus `onSelect` (StaffShell.tsx:29-31; sidebarSections.ts:114; SidebarItem.tsx:9-12) |
| 18 | Current-section indication (`aria-current` on the group and the row) | StaffDock.tsx:185; StaffDockPopover.tsx:94 | PRESENT | SidebarItem.tsx:9 `aria-current="page"`; the section auto-opens when it holds the active tab (SidebarSection.tsx:15-16) |
| 19 | Notifications unread badge (99+) on the group button and the Notifications row, plus accessible name | StaffDock.tsx:70-73,167-169,208-212; StaffDockPopover.tsx:104-108 | PRESENT | Inbox item badge plus aria-label (StaffShell.tsx:23,34; SidebarItem.tsx:10,16); BottomTabs.tsx:10-12 |
| 20 | Unread count visible on mobile (the dock was always on screen) | StaffDock.tsx:156,208-212 | CHANGED | MobileTopBar puts the count only in the hamburger's aria-label (MobileTopBar.tsx:8). There is no visual badge until the drawer is opened |
| 21 | Dock keyboard model: arrow-key roving between groups, ArrowUp/Down opens the popover at the first or last row, Escape closes and restores focus, close and refocus on route change | StaffDock.tsx:75-149; StaffDockPopover.tsx:55-79 | CHANGED | A plain link list with Tab order; More/Settings are disclosures. The drawer closes on route change and focuses main (AppShell.tsx:17-24). Functionally equivalent |
| 22 | Mobile access to navigation (bottom dock on every viewport) | StaffDock.tsx:152-160 | PRESENT | Below `lg`: hamburger → SidebarDrawer (MobileTopBar.tsx:8-9; AppShell.tsx:52). Still two taps to reach a tab, as with dock → popover |
| 23 | Handout-only navigation (dock showed the Operate group: requests, direct, handover, payments, notifications) | StaffDock.tsx:55-63; staffAccess.ts (baseTabs) | PRESENT | Flat section (sidebarSections.ts:115) plus BottomTabs on mobile (StaffShell.tsx:59; BottomTabs.tsx) |
| 24 | Navigation without an active makerspace (superadmin on platform-dashboard / organizations, governance-only accounts) | StaffWorkspace.tsx:180-187 (dock got every allowed tab) | CHANGED | Limited to `organizations` and `platform-dashboard` (StaffShell.tsx:30). The workspace card reads "Choose a space" and lists the makerspaces (StaffShell.tsx:53-56). This is safer: the other tabs bounced to the picker before |
| 25 | Platform views ("Platform dashboard", "Platform settings") for superadmins | staffAccess.ts:64 (Admin group) | PRESENT | Platform section (sidebarSections.ts:91) |
| 26 | Secondary tabs in Inventory / Community / Insights (categories, containers, ledger, warranty, qr, scanner, bulk, cards, accountability) | StaffDock popover (all tabs one level deep) | BURIED | Behind "More (n)" in each section unless the section has ≤4 items or holds the active tab (SidebarSection.tsx:14-28). The expanded state is remembered per user |
| 27 | Settings-family tabs (settings, users, emailtemplates, email-logs, api, exports, backups, usage, modules, migration) | staffAccess.ts:64 (Admin popover) | BURIED | A single "Settings" parent that links to the first allowed child. Children show only while a Settings-family page is active (sidebarSections.ts:119-122). "Staff & roles" therefore takes Settings → General → Staff & roles |
| 28 | Tab labels (TAB_LABELS) used consistently across dock, palette and access-denied | StaffDockPopover.tsx:103 | CHANGED | The sidebar renames 12 tabs (sidebarSections.ts:93-97): Home, Inbox, Job pickups, Items, Repair shelf, To buy, Stock ledger, QR tools, Org analytics, General, Staff & roles, Delivery log. CommandPalette (CommandPalette.tsx:33-36) and access-denied (StaffWorkspace.tsx:170) still use the old TAB_LABELS, so searching the palette for "Inbox" or "Staff" finds nothing |
| 29 | Help link / notifications bell / create-makerspace entry in the chrome | none | PRESENT | Never existed. Create makerspace is still only in the Users header (superadmin) |

New in the chrome (not counted): a Requests badge (pending + awaiting issue, read from the dashboard cache; StaffShell.tsx:35-37), machine-type children under Machines (:38-45), "Account & two-step sign-in" (/mfa) in the UserMenu (:62), and a search inside the switcher when it has more than 6 entries (WorkspaceSwitcher.tsx:14).

### Tab reachability (old dock group → new sidebar section); all 42 `STAFF_TAB_KEYS` present in both

| Tab key | Old dock group (staffAccess.ts:55-65) | New sidebar location (sidebarSections.ts:82-92) |
|---|---|---|
| dashboard, notifications | Operate | Home (unlabelled section): "Home", "Inbox" |
| requests, direct, handover, payments | Operate | Front desk ("Job pickups" = handover) |
| ledger, transfers, stocktake, tobuy | Operate | Inventory (transfers, stocktake, tobuy primary; ledger under More) |
| inventory, needsfix | Inventory | Inventory primary ("Items", "Repair shelf") |
| categories, containers, bulk, qr, scanner | Inventory | Inventory → More |
| warranty | Insights | Inventory → More |
| machines, devices | Machines | Machines |
| events, bookings | Events / Bookings | Community |
| organized | Events | Organizations |
| members | Members | Community |
| cards | Members | Community → More |
| reports, audit | Insights | Insights |
| accountability | Insights | Insights → More |
| organization-analytics | Insights | Organizations ("Org analytics") |
| organizations | Organizations | Organizations |
| users, settings, usage, emailtemplates, email-logs, api, exports, backups, migration, modules | Admin | Settings family (collapsed children) |
| platform-dashboard, platform | Admin | Platform |

Verified by script: the set difference between `ALL_TABS` and SIDEBAR_SECTIONS is empty, and so is the difference between `ALL_TABS` and the old TAB_GROUPS. The handout-only flat list equals `baseTabs` for handoutOnly. No tab is orphaned. Every component in scope is still rendered: MakerspacePicker, UsersTable, RoleManager, RoleEditor, RoleMachineScopeEditor, StaffInvitations, all four users modals, CreationWizardSteps, MakerspaceHoursEditor, SpacePackProfilePicker, CommandPalette, SetupChecklist and the shell components each have a live `<X` call site outside tests.

### Counts

| Page | PRESENT | BURIED | CHANGED | MISSING | total |
|---|---|---|---|---|---|
| users — Staff & roles | 84 | 7 | 6 | 0 | 97 |
| picker — MakerspacePicker | 10 | 0 | 2 | 0 | 12 |
| chrome — header/dock/workspace | 16 | 6 | 6 | 1 | 29 |
| **Total** | **110** | **13** | **14** | **1** | **138** |

### Restore candidates

1. **P1. Users: the makerspace selector disappears when a list request fails.** Old Users.tsx:175-182 kept the `<select>` beside the error text. New Users.tsx:188-195 is inside `body`, so `QueryContent` swaps it for an ErrorBlock (Users.tsx:181). If the default `makerspaces[0]` returns 403, the user cannot switch away. Fix: move the Makerspace select and the Role filter out of `body`, either into ListLayout `filters` as visible inline controls (not the buried popover) or into a toolbar above `QueryContent`. Also show the server's error message (old Users.tsx:168,196) in the ErrorBlock.
2. **P1. Users: blank page after switching makerspace while on the Invitations or Roles tab.** Users.tsx:46,191: `tab` survives `setMsId`. Fix: call `setTab("staff")` in the select's onChange (next to `setRoleFilter("all")`), or derive the active tab from `sectionTabs` (`sectionTabs.some(t => t.key === tab) ? tab : "staff"`) and use that for rendering and `state`.
3. **P2. Users row actions moved to the overflow menu: Restore, Restrict, Reset password, Revoke** (old UsersTable.tsx:50-53 → new :44-49). Overflow suits Revoke, Restrict and Reset password under Yuyu. "Restore" is the frequent action on a restricted or suspended row, so show it as a visible row button when `access_status !== "active"` and keep it in overflow otherwise. ConfirmDialogs for Restore and Revoke are intact (Users.tsx:266-287).
4. **P2. Chrome: superadmin "Switch makerspace" is buried** (old StaffHeader.tsx:73-77 was a primary button; new StaffShell.tsx:50/62 puts it inside a disclosure). Keep it in the WorkspaceSwitcher, but pin it as the first, labelled entry and mark the current makerspace in the list (old select at StaffHeader.tsx:51-64 showed the selection). Non-superadmin multi-space switching has the same issue (row 5).
5. **P2. Picker: "Open control plane" link is broken and the copy is misleading** (new MakerspacePicker.tsx:38). Give the action `external: true` or use an absolute API-origin URL so RouteLink renders a real `<a>` instead of a react-router `Link` to `/control/` (which hits NotFoundPage, AppRoutes.tsx:109). Restore the old copy from MakerspacePicker.tsx:47 ("Create one from the Django control plane"), since "Staff & roles" needs a selected makerspace.
6. **P2. Chrome: "Staff & roles" and the other Settings-family tabs collapse under "Settings"** (sidebarSections.ts:119-122). Reaching Users means loading General first. Either always show the Settings children for `manage_makerspace` actors, or have the Settings landing page (SettingsNav) list Staff & roles. Old route: Admin popover → Users (StaffDockPopover.tsx:90-110).
7. **P3. Users: Invitations moved from always-visible to a tab** (old Users.tsx:208 → Users.tsx:173,218). Acceptable under Yuyu (tab). Optionally add a header overflow "Invite staff" that opens the Invitations tab.
8. **P3. Invitation Revoke moved to the overflow menu with no confirmation** (StaffInvitations.tsx:46; old :43 had none either). Rare and destructive, so overflow is correct. Consider passing `confirm: { title: "Revoke invitation?", message: … }` now that OverflowMenu supports it (OverflowMenu.tsx:30,40).
9. **P3. Invitation row lost the "Expires <date>" vs Accepted/Revoked distinction** (old StaffInvitations.tsx:40). Show "Expires …" only for open rows and add an "Expired" pill when `expires_at < now` (new :43-44).
10. **P3. Role Delete is buried** (old RoleManager.tsx:54 → overflow :53 plus drawer DangerZone RoleEditor.tsx:74). Fine for a rare action and the ConfirmDialog is intact. Also disable the DangerZone action while `remove.isPending`, as the old button did.
11. **P3. Chrome: makerspace public_code read-out is missing** (old StaffHeader.tsx:41-43). Put it in the WorkspaceSwitcher subtitle, e.g. `${public_code ?? slug} · ${roleName}` (StaffShell.tsx:52).
12. **P3. Chrome: no visual unread badge on mobile** (old StaffDock.tsx:208-212). Add a dot or count on the MobileTopBar hamburger (MobileTopBar.tsx:8-9); the count is already passed as `unread`.
13. **P3. Chrome: JobTray is unreachable on mobile without opening the drawer** (old StaffWorkspace.tsx:136 rendered it inline). Render `status` (JobTrayPill) in MobileTopBar when jobs exist.
14. **P3. Chrome: SetupChecklist is hidden while dashboard data loads or errors** (old StaffWorkspace.tsx:137 rendered it independently). Render `progress` outside `QueryContent` in DashboardLayout.tsx:41-44.
15. **P3. Chrome: sidebar labels and TAB_LABELS have diverged** (sidebarSections.ts:93-97 vs staffAccess.ts TAB_LABELS used by CommandPalette.tsx:33-36). Use one label map, or have the palette match both labels.
16. **P3. Picker: the "Super Admin" identity label is gone** (old MakerspacePicker.tsx:31). Add it to the eyebrow or subtitle (new :33-34).
17. **P3. Wizard: the install-profile error hides the picker and the server message** (old SpacePackProfilePicker.tsx:19). Drop the `SettingsQueryState` wrapper (new :13) and keep the select usable with the inline error and Retry, or pass the server message through. The inner error branch (:21) is dead code.
18. **P3, pre-existing (not a regression). Users never shows `revoke` errors** (old Users.tsx:168 / new :176 omit `revoke.error`). Add it to `panelError`.

---

Scope: tab `settings` — `MakerspaceSettingsPanel.tsx` (old d3e5ed29, 271 lines → working tree, 208 lines), its inline rows, section structure, and every child editor listed in the brief (payments/billing/kiosk/notifications/integrations/email/webhooks/telegram only as a mount table).

## settings — Makerspace settings (MakerspaceSettingsPanel.tsx)

Routing is unchanged: `StaffPlatformTabContent.tsx:18-25` mounts `MakerspaceSettingsPanel` for `activeTab === "settings"` with the same `isSuperadmin` / `canManageMakerspace` props. OLD was one long `<Panel title="Makerspace settings">` stack of bordered boxes in a fixed order. NEW is `SettingsLayout` (`components/layouts/SettingsLayout.tsx`) with a header, a sticky `SettingsNav` anchor list (shown because there are 11 sections, `subnav="auto"` needs at least 5), 11 `SettingsSection` cards, and one `DangerZone` (archive). The children were turned into label-left `SettingsRow`s. Their editors now show Save/Discard only when the editor is dirty (`SettingsEditorActions`). Every child that rendered before still renders, under the **same gate**. Nothing is unreachable. The real changes are in loading/error handling, the archive flow and a few pieces of text.

New section map (`MakerspaceSettingsPanel.tsx:153-200`): **General** (General, Location, Profile) · **Branding & public site** (Branding+Theme, PublicStats, print recovery, Subdomain, CustomDomain) · **Features** (Features, SpacePacks) · **Lending** (Reminders, Kiosk) · **Membership** (Membership+Admission, Geofence) · **Bookings** (BookingSettings, BookingRules) · **Machines & materials** (Filament) · **Money** (Payment+Loans, BillingDocuments) · **Notifications** (staff email, Timing, MuteMatrix, RecipientPicker, Destinations) · **Email & integrations** (Email, Webhook, Telegram, IntegrationHealth) · **Privacy & evidence** (superadmin access, EvidenceRetention+AbandonedUpload) · DangerZone "Archive this makerspace" → Modal(ArchiveRequestPanel).

### A. Panel shell and inline rows

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| A1 | Page title "Makerspace settings" | MakerspaceSettingsPanel.tsx:101 | PRESENT | `SettingsLayout` header title, plus a new subtitle, MakerspaceSettingsPanel.tsx:149 |
| A2 | Settings fetch `GET /admin/makerspaces/{id}`. While it loaded or after it failed, the old page still rendered every section, using the `makerspace` prop as a fallback and disabling controls through `loading`. Load errors were never shown. | MakerspaceSettingsPanel.tsx:43-46, 102-261 | CHANGED | MakerspaceSettingsPanel.tsx:151-152 passes `state` to `SettingsLayout`, so `QueryContent` (LayoutFrame.tsx:37-47) **replaces the whole page** with a skeleton while loading and with one ErrorBlock + Retry on error. Every child editor is hidden until this one GET succeeds, including editors with their own endpoints (profile, loan policy, admission, kiosk, notifications, evidence retention, archive). Retry is new and good. The coupling is the regression. |
| A3 | Section navigation | n/a (single scroll) | PRESENT | `SettingsNav` anchor list, SettingsNav.tsx:1-20; shown because sections ≥ 5 (SettingsLayout.tsx:35) |
| A4 | "Manage my authenticator and recovery codes" link to `/mfa` | MakerspaceSettingsPanel.tsx:103 | BURIED | Removed from the page. Only reachable from the shell user menu "Account & two-step sign-in" (StaffShell.tsx:62) |
| A5 | Superadmin access On/Off badge | MakerspaceSettingsPanel.tsx:141-143 | PRESENT | StatusPill, MakerspaceSettingsPanel.tsx:122 (Privacy & evidence section) |
| A6 | Superadmin access explanation, including "It does not revoke the superadmin's platform/database access" | MakerspaceSettingsPanel.tsx:145-149 | CHANGED | SettingsRow helper, MakerspaceSettingsPanel.tsx:120. The sentence saying platform/database access is **not** revoked was dropped, so the helper now overstates what the switch does (P3 copy) |
| A7 | `reEnableBlocked` (superadmin viewing an Off space cannot turn it back on): button disabled + "Re-enable is controlled by the makerspace admin." | MakerspaceSettingsPanel.tsx:54, 98, 150-152 | PRESENT | MakerspaceSettingsPanel.tsx:58, 117, 123 (same logic) |
| A8 | "Turn off access" / "Turn on access" button → `PATCH /admin/makerspaces/{id}` `{superadmin_access_enabled}`. Old styled it primary when Off. No confirmation in either version. | MakerspaceSettingsPanel.tsx:56-67, 155-166 | PRESENT | MakerspaceSettingsPanel.tsx:60-71, 125-127. Always `desk-button` now; adds a success toast. Still no confirm on an action the superadmin cannot undo (it was not there before either) |
| A9 | Superadmin access error text | MakerspaceSettingsPanel.tsx:153 | PRESENT | MakerspaceSettingsPanel.tsx:124 (`role="alert"`) |
| A10 | Staff email notifications On/Off badge | MakerspaceSettingsPanel.tsx:174-176 | PRESENT | MakerspaceSettingsPanel.tsx:131 (Notifications section) |
| A11 | "Send staff emails" checkbox → PATCH `{staff_notifications_enabled}` | MakerspaceSettingsPanel.tsx:69-80, 185-194 | PRESENT | MakerspaceSettingsPanel.tsx:73-99, 132-135. Adds a toast with Undo |
| A12 | Staff email helper + error | MakerspaceSettingsPanel.tsx:178-183 | PRESENT | MakerspaceSettingsPanel.tsx:130, 136 |
| A13 | Public print status recovery badge. Tone was neutral for token_only and success for email lookup. | MakerspaceSettingsPanel.tsx:207-209 | CHANGED | MakerspaceSettingsPanel.tsx:139: StatusPill has no `tone`, so it is always neutral and the tone no longer separates the two policies (P3) |
| A14 | "Public print status lookup policy" select (`token_only` "Token only" / `email_unverified` "Email lookup") → PATCH `{public_print_status_lookup_policy}` | MakerspaceSettingsPanel.tsx:82-93, 218-228 | PRESENT | MakerspaceSettingsPanel.tsx:101-112, 140-144 (Branding & public site section). Helper text reworded, :138 |
| A15 | Print recovery error | MakerspaceSettingsPanel.tsx:214-216 | PRESENT | MakerspaceSettingsPanel.tsx:145 |
| A16 | "Notification channels" heading grouping MuteMatrix, RecipientPicker and Destinations | MakerspaceSettingsPanel.tsx:252-260 | PRESENT | Now the "Notifications" section title, MakerspaceSettingsPanel.tsx:185-189 (the group heading itself is gone) |
| A17 | Archive request panel shown inline at the bottom (when `canManageMakerspace`), including the **pending-request card, Withdraw and resolved history** | MakerspaceSettingsPanel.tsx:248-251; MakerspaceArchiveRequestPanel.tsx:83-105, 157-168 | BURIED | DangerZone "Request archival…" (MakerspaceSettingsPanel.tsx:198-200) opens a Modal (:201-203) that holds the whole panel. A pending request, its Withdraw button and the history are only visible after clicking "Request archival", and the DangerZone keeps offering "Request archival" while a request is already pending. Gate unchanged (`canManageMakerspace`). The DangerZone action passes no `confirm`, which is correct here because it only opens the modal |
| A18 | Header primary "View public site" → `/m/{slug}` | n/a | PRESENT | Added: MakerspaceSettingsPanel.tsx:150. It still shows when `public_site_enabled` is false (P3) |

### B. Child mount map (old vs new gate and section)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| B1 | MakerspaceBrandingSettings (no gate) | MakerspaceSettingsPanel.tsx:104-108 | PRESENT | Branding & public site, :160 (no gate) |
| B2 | MakerspaceGeneralSettings (no gate) | :109-113 | PRESENT | General, :155 |
| B3 | MakerspaceLocationSettings (no gate) | :114-118 | PRESENT | General, :156 |
| B4 | MakerspaceMembershipSettings (no gate) | :119 | PRESENT | Membership, :174 |
| B5 | MakerspaceProfileSettings (`canManageMakerspace`) | :120 | PRESENT | General, :157 (same gate) |
| B6 | MakerspaceFeatureSettings (no gate) | :122-126 | PRESENT | Features, :165 |
| B7 | SpacePacksPanel (`canManageMakerspace && enabled_features ⊇ packs.import`) | :127-128 | PRESENT | Features, :166-167 (identical expression) |
| B8 | MakerspaceGeofenceSettings (no gate) | :133 | PRESENT | Membership, :174 |
| B9 | MakerspacePublicStatsSettings (no gate) | :197-201 | PRESENT | Branding & public site, :160 |
| B10 | MakerspaceBookingSettings (no gate) | :231 | PRESENT | Bookings, :177 |
| B11 | MakerspaceReminderSettings (no outer gate; it gates internally on `events`/`bookings` modules) | :232 | PRESENT | **Lending**, :170. Event/booking reminders sit under "Lending", which is the wrong section (P3). Lending is an empty card when neither module nor kiosk is on |
| B12 | MakerspaceBookingRulesSettings (`enabledModules ⊇ bookings`) | :233-235 | PRESENT | Bookings, :178 (same gate) |
| B13 | MakerspaceFilamentSettings (no gate) | :236 | PRESENT | Machines & materials, :180 |
| B14 | MakerspaceSubdomainSettings (`settings.data?.platform_hosting === true`) | :239-241 | PRESENT | Branding & public site, :161 (same gate) |
| B15 | MakerspaceCustomDomainSettings (no gate) | :242-246 | PRESENT | Branding & public site, :162 |
| B16 | EvidenceRetentionPanel (`canManageMakerspace`) | :247 | PRESENT | Privacy & evidence, :196 (same gate) |
| B17 | MakerspaceArchiveRequestPanel (internal `canManageMakerspace` check) | :248-251 | BURIED | DangerZone + Modal, only when `canManageMakerspace` (:198-203). See A17 |
| B18 | MakerspaceThemeSettings (inside Branding) | MakerspaceBrandingSettings.tsx:160 | PRESENT | MakerspaceBrandingSettings.tsx:140 |
| B19 | MakerspacePublicSiteSettings (inside General) | MakerspaceGeneralSettings.tsx:116 | PRESENT | MakerspaceGeneralSettings.tsx:101. Rendered as a loose block with no SettingsRow label (P3) |
| B20 | MakerspaceLoanPolicySettings (inside General, `makerspace.enabled_features ⊇ loans.enabled`) | MakerspaceGeneralSettings.tsx:117 | PRESENT | MakerspaceGeneralSettings.tsx:102 (same gate) |
| B21 | MakerspaceHoursEditor (inside Profile) | MakerspaceProfileSettings.tsx:77 | PRESENT | MakerspaceProfileSettings.tsx:81-83 |
| B22 | MembershipAdmissionSettings (inside Membership, `enabled_modules ⊇ membership`, replacing the joining-policy select) | MakerspaceMembershipSettings.tsx:57 | PRESENT | MakerspaceMembershipSettings.tsx:79 (same gate) |
| B23 | MakerspaceLoanSettings (inside Payment, `featureEnabled(enabled_features, "charges.loans")`) | MakerspacePaymentSettings.tsx:176-178 | PRESENT | MakerspacePaymentSettings.tsx:169 (same gate), now inside the payment `SettingsQueryState` (same `/payment-settings` endpoint, so same failure mode) |
| B24 | AbandonedUploadCleanupSection (inside EvidenceRetention) | EvidenceRetentionPanel.tsx:104-109 | PRESENT | EvidenceRetentionPanel.tsx:100-105, now a sibling SettingsRow |
| B25 | SpacePackProfilePicker (inside SpacePacks, `isSuperadmin`) | SpacePacksPanel.tsx:68-71 | PRESENT | SpacePacksPanel.tsx:69-72 (same gate) |
| B26 | ImageUploader ×2 (logo, cover) | MakerspaceBrandingSettings.tsx:70-83 | PRESENT | MakerspaceBrandingSettings.tsx:65-78 |

**Out-of-scope children (another agent audits them). Only whether they are mounted:**

| Component | Old mount / gate | New section / line / gate | Mounted? |
|---|---|---|---|
| MakerspacePaymentSettings | :129, no gate | Money :182, no gate | yes |
| BillingDocumentsSettings | :121, `canManageMakerspace` | Money :183, same | yes |
| KioskStationSettings | :130-132, `canManageMakerspace && settings.data.enabled_features ⊇ inventory.kiosk` | Lending :171, same | yes |
| NotificationTimingSettings | :134, `canManageMakerspace && enabledModules ⊇ notifications` | Notifications :186, same | yes |
| NotificationMuteMatrix | :254, no gate | Notifications :187 | yes |
| NotificationRecipientPicker | :255, no gate | Notifications :187 | yes |
| NotificationDestinations | :256-259, no gate | Notifications :188 | yes |
| IntegrationHealthPanel | :135, no gate | Email & integrations :193 | yes |
| MakerspaceEmailSettings | :237, no gate | Email & integrations :191 | yes |
| MakerspaceWebhookSettings | :238, no gate | Email & integrations :191 | yes |
| ApiClientsTelegramSettings | **not on this page.** Was ApiClientsPanel.tsx:153 (`isSuperadmin`, `api` tab) | Email & integrations :192, `isSuperadmin`. **Moved here from the API tab** (no longer rendered in ApiClientsPanel) | yes (moved) |

### C. MakerspaceGeneralSettings (General section)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| C1 | "General" heading box | MakerspaceGeneralSettings.tsx:53-54 | PRESENT | Section "General" (panel :154) |
| C2 | Default loan days: number, min 1, id `default-loan-days`. PATCH `{default_loan_days: Number(v) \|\| 7}` | :34-41, 63-74 | PRESENT | SettingsRow "Default loan days" :67-85 (the inner label repeats the row label) |
| C3 | Default loan days help ("Default return window applied when a hardware request is issued") | :75-77 | PRESENT | Row helper :67 |
| C4 | "Save default days" button (always visible, disabled while loading/pending) | :79-85 | PRESENT | Save/Discard via SettingsEditorActions, shown only when dirty, :88 |
| C5 | Default loan days error | :87-89 | PRESENT | :90-92 |
| C6 | Public inventory On/Off badge | :92-97 | PRESENT | :95 |
| C7 | "Show public inventory" checkbox → PATCH `{public_inventory_enabled}` | :43-50, 98-107 | PRESENT | :94-97, plus a toast with Undo (:52-63) |
| C8 | Public inventory help ("hidden… does not delete any inventory data") | :108-110 | PRESENT | Row helper :94 |
| C9 | Public inventory error | :111-113 | PRESENT | :98 |

### D. MakerspacePublicSiteSettings (file unchanged except a tap-target class)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| D1 | "Publish public site" checkbox → PATCH `{public_site_enabled}`. Invalidates makerspace-settings, makerspaces, tenant-bootstrap, runtime-tenant, runtime-tenant-origin, public-makerspaces, member | MakerspacePublicSiteSettings.tsx:7-19 | PRESENT | same lines. No SettingsRow label, so it sits label-less in General after "Public inventory" (P3) |
| D2 | Help: directory visibility, embed keys, public machine pages | :20 | PRESENT | :20 |
| D3 | "Public home" select: auto/inventory/events/bookings/machines/membership → PATCH `{public_landing_page}` | :21-26 | PRESENT | :21-26 |
| D4 | Help: "If the selected family is disabled…" | :27 | PRESENT | :27 |
| D5 | Error | :28 | PRESENT | :28 |

### E. MakerspaceLoanPolicySettings (gate `loans.enabled`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| E1 | GET/PATCH `/admin/makerspace/{id}/return-policy`; heading "Loan policy" + text about renewals and borrow limits | MakerspaceLoanPolicySettings.tsx:22-43, 57-58 | PRESENT | :25-46; label/helper :49 |
| E2 | Loan period in days (`default_loan_days`, 1-365, required) | :14, 60-62 | PRESENT | :17, 63-65 |
| E3 | Maximum renewals (`loan_max_renewals`, 0-100) | :15 | PRESENT | :18 |
| E4 | Renewal length in days (`loan_renewal_days`, 1-365) | :16 | PRESENT | :19 |
| E5 | Maximum active loans, 0 = unlimited (`loan_max_active`, ≥0) | :17 | PRESENT | :20 |
| E6 | Maximum outstanding items, 0 = unlimited (`loan_max_items`, ≥0) | :18 | PRESENT | :21 |
| E7 | Escalate to staff after days overdue, 0 = off (`loan_escalate_overdue_days`, 0-365) | :19 | PRESENT | :22 |
| E8 | Renewal mode select: off / auto ("Automatic within policy") | :63-65 | PRESENT | :66-68 |
| E9 | Reminder offsets in hours (comma list, hint). Validation: ≤100 unique whole hours in −8760..8760, else a "Use up to 100 unique…" problem | :48-53, 66-68 | PRESENT | :51-56, 69-71 |
| E10 | "Save loan policy" button | :70 | PRESENT | Save/Discard shown only when dirty, :73 |
| E11 | Error / "Loan policy saved." status | :71-72 | PRESENT | :74-75 |
| E12 | Load error showed the server message; loading text | :44-45 | CHANGED | :47-48 `SettingsQueryState` shows a generic "Couldn't load loan policy. Try again." + Retry. The server message is lost (P3) |

### F. MakerspaceProfileSettings (gate `canManageMakerspace`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| F1 | Heading "Location & hours" + explanation (timezone; "Hours are informational until a workflow uses them"; currency shared with payment settings; country private) | MakerspaceProfileSettings.tsx:41-42 | CHANGED | Heading dropped. Explanation split across row helpers :67-81. The "hours are informational" caveat is gone (P3) |
| F2 | Timezone select (`timezone_choices`) | :63-67 | PRESENT | SettingsRow "Timezone" :67-71 |
| F3 | Country select ("Unspecified" + `country_choices` via Intl region names) | :68-73 | PRESENT | SettingsRow "Country" :72-77 |
| F4 | Default currency: text, maxLength 3, lower-cased, validated `^[a-z]{3}$` | :47, 74-76 | PRESENT | SettingsRow "Default currency" :51, 78-80 |
| F5 | Opening hours (MakerspaceHoursEditor) | :77 | PRESENT | SettingsRow "Opening hours" :81-83 |
| F6 | Diff-only PATCH `/admin/makerspace/{id}/profile` (`opening_hours`/`timezone`/`country`/`default_currency`), invalidating payment-settings, tenant-bootstrap and others | :28-37, 45-60 | PRESENT | :32-41, 49-64 |
| F7 | Validation error + API field errors (`StructuredApiError.body.fields`) | :79-80 | PRESENT | :85-86 |
| F8 | "Saved." status | :81 | PRESENT | :87 |
| F9 | "Save location & hours" button (disabled unless dirty) | :82 | PRESENT | Save/Discard (Discard is new), :88 |
| F10 | Loading text / error + Retry | :43-44 | PRESENT | :44 SettingsQueryState (+ duplicate :47-48). Generic message |

### G. MakerspaceHoursEditor (identical apart from a class)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| G1 | "Set weekly opening hours" checkbox | MakerspaceHoursEditor.tsx:24-27 | PRESENT | :24-27 |
| G2 | Rules text (always open without weekly hours, HH:MM, 24:00, split overnight) | :28 | PRESENT | :28 |
| G3 | Per-weekday fieldset: HH:MM start/end per interval, Remove, "Add {day} interval" (max 24) | :3-20, 29-33 | PRESENT | same |
| G4 | Dated exceptions: date input, intervals, "Remove exception N" | :34-46 | PRESENT | same |
| G5 | "Add exception" (max 366) | :47-48 | PRESENT | same |

### H. MakerspaceBrandingSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| H1 | "Branding" heading + description (logo/cover; wordmark fallback) | MakerspaceBrandingSettings.tsx:64-68 | PRESENT | Split into row helpers :65, 72 |
| H2 | Logo ImageUploader (`/admin/makerspace/{id}/logo`, fit contain) | :70-76 | PRESENT | SettingsRow "Logo" :65-71 |
| H3 | Cover image ImageUploader (`/admin/makerspace/{id}/cover`, wide) | :77-83 | PRESENT | SettingsRow "Cover image" :72-78 |
| H4 | Registered name input → PATCH `{name}`. Blocked when empty or unchanged | :36-43, 54-57, 86-104 | PRESENT | SettingsRow "Registered name" :79-97 |
| H5 | Registered name help | :105-108 | PRESENT | :98-101 (plus row helper) |
| H6 | "Save registered name" button | :109-117 | PRESENT | Save/Discard when dirty, :103 |
| H7 | Registered name error | :118-120 | PRESENT | :105-107 |
| H8 | Public display name input (placeholder = name) → PATCH `{public_display_name}`. Blank allowed | :45-52, 122-141 | PRESENT | SettingsRow "Public display name" :109-128 |
| H9 | Display name help naming the registered name | :142-145 | PRESENT | :129-132 |
| H10 | "Save display name" button | :146-154 | PRESENT | Save/Discard when dirty, :134 |
| H11 | Display name error | :155-157 | PRESENT | :136-138 |

### I. ImageUploader (as used by branding; diff is styling only)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| I1 | File picker (`image/jpeg,png,webp`); client size cap from `/config` `public_image_max_bytes`; presign POST → PUT/POST upload → attach | ImageUploader.tsx:20-100, 211 | PRESENT | same lines |
| I2 | "Camera" capture button (when supported) + CameraCapture | :219-225 | PRESENT | same |
| I3 | Preview (contain/cover) or "none" placeholder | :190-202 | PRESENT | same |
| I4 | "Remove" → `DELETE {endpoint}`. No confirm in either version | :174, 226-235 | PRESENT | same |
| I5 | Live status "Working..." / error | :239-245 | PRESENT | same |

### J. MakerspaceThemeSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| J1 | Heading "Public and member colours" | MakerspaceThemeSettings.tsx:42 | PRESENT | SettingsRow label :40 |
| J2 | Help: blank = product palette; button text automatic; link colours adapt to light/dark; staff console keeps product theme | :43 | CHANGED | :45 now says "Leave blank to use Maker Teal. Staff screens always use the Space Works palette." The automatic button-text and link-adaptation explanation was dropped (P3) |
| J3 | Primary fill input (`theme-primary`) | :45-47 | PRESENT | :47-49 (placeholder now #006e63) |
| J4 | Link colour seed input (`theme-accent`) | :48-50 | PRESENT | :50-52 |
| J5 | Light + dark previews with worst text/UI contrast ratios | :52-68 | PRESENT | :54-79 (adds example link, hover/active and soft swatches) |
| J6 | "Derived link colour: rgb(r, g, b)" numeric read-out | :63 | CHANGED | Replaced by a visual "Example link" :70. The numeric rgb value is no longer shown (P3) |
| J7 | Contrast errors + per-pair failures | :70-71 | PRESENT | :81-82 |
| J8 | Valid / invalid summary. Invalid said "Choose a lighter or darker primary fill…" | :72 | CHANGED | :83 now always says "Enter a #RGB or #RRGGBB colour…", which misleads when the hex is well-formed but fails contrast (P3) |
| J9 | Save error / "Colours saved." | :73-74 | PRESENT | :84-85 |
| J10 | "Save colours" → PATCH `{theme_config}` (only when valid and changed); invalidates tenant-bootstrap, runtime-tenant and others | :23-36, 76 | PRESENT | :25-38, Save/Discard :87 |

### K. MakerspacePublicStatsSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| K1 | Public stats page On/Off badge | MakerspacePublicStatsSettings.tsx:46-49 | PRESENT | :67 |
| K2 | "Publish public stats" checkbox → PATCH `{public_stats_enabled}` | :24-31, 60-69 | PRESENT | :26-44, 68-69 (+ toast with Undo) |
| K3 | Help with `/m/{slug}/stats` path; 404 when off | :51-55 | PRESENT | Row helper :66 + :70 |
| K4 | Public stats error | :56-58 | PRESENT | :71 |
| K5 | Public borrower names badge (warn when on) | :73-76 | PRESENT | :75 |
| K6 | "Publish borrower names publicly" → PATCH `{public_stats_show_holder_names}`. No confirm in either version | :32-39, 85-94 | PRESENT | :45-63, 76-77 (+ toast with Undo) |
| K7 | Borrower names help ("shown as Member when off") | :77-80 | PRESENT | Row helper :74 |
| K8 | Borrower names error | :81-83 | PRESENT | :78 |

### L. MakerspaceLocationSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| L1 | Heading + help (public label + Maps link) | MakerspaceLocationSettings.tsx:66, 71-73 | PRESENT | SettingsRow "Location" :55 |
| L2 | Badge "Maps link set" / "Text only" | :67-69 | PRESENT | :69-71 |
| L3 | Location label input | :81-89 | PRESENT | :79-87 |
| L4 | Google Maps link input + "Share → Copy link" hint | :90-99 | PRESENT | :88-97 |
| L5 | "Save location" → PATCH `{location, map_url}` (disabled unless changed) | :26-44, 75-77 | PRESENT | :28-46, Save/Discard :75 |
| L6 | "Open in Maps" external link | :102-111 | PRESENT | :100-108 |
| L7 | Error | :112-114 | PRESENT | :110-112 |

### M. MakerspaceGeofenceSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| M1 | Heading "Presence geofence" + On/Off badge + HTTPS help | MakerspaceGeofenceSettings.tsx:41 | PRESENT | SettingsRow :42-43 |
| M2 | "Enable geofence" checkbox (draft) | :41 | PRESENT | :43 |
| M3 | Latitude (decimal) | :42 | PRESENT | :44 |
| M4 | Longitude (decimal) | :42 | PRESENT | :44 |
| M5 | Radius (metres), number, min 1 | :42 | PRESENT | :44 |
| M6 | "Save geofence" → PATCH `geofence_enabled/latitude/longitude/radius_m` (disabled unless changed) | :25-38, 43 | PRESENT | :27-40, Save/Discard :45 |
| M7 | Error | :43 | PRESENT | :45 |

### N. MakerspaceMembershipSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| N1 | "Membership joining" select open / request / invite_only → PATCH `{membership_policy}`. Shown only when the `membership` module is OFF | MakerspaceMembershipSettings.tsx:30-35, 57-68 | PRESENT | :34-39, 79-90 (same gate) |
| N2 | Joining policy badge | :60 | PRESENT | :82 |
| N3 | Joining policy error | :62 | PRESENT | :84 |
| N4 | Member referrals badge + "Enable referrals" checkbox → PATCH `{referrals_enabled}` | :36-41, 69-78 | PRESENT | :40-54, 91-100 (+ Undo toast) |
| N5 | Lapsed members badge + "Lapsed members cannot borrow" → PATCH `{lapsed_members_cannot_borrow}`. Shown only when `settings.lapsed_members_cannot_borrow !== undefined` | :42-48, 79-88 | PRESENT | :55-70, 101-110 (same gate, + Undo toast) |
| N6 | Membership dues: number ≥0 step 0.01 → PATCH `{membership_dues_amount}` | :49-54, 89-103 | PRESENT | :71-76, 111-121 |
| N7 | "Save dues" button (always visible) | :100 | PRESENT | Discard/Save dues ActionControls shown only when changed, :122-127 (`type="button"` + `requestSubmit`) |
| N8 | Errors (referrals, lapsed, dues) | :74, 84, 94 | PRESENT | :96, 106, 116 |

### O. MembershipAdmissionSettings (gate `membership` module)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| O1 | Heading + help (recipes, snapshots, Closed) | MembershipAdmissionSettings.tsx:38 | PRESENT | SettingsRow "Membership admission" :40 |
| O2 | Admission recipe select (Custom + free_open, free_vouch, paid_approval, paid_invite_only, closed) → `admissionRecipeDraft` | :41-46 | PRESENT | :44-49 |
| O3 | Join mode select open/approval/invite_only/vouch/closed | :47 | PRESENT | :50 |
| O4 | Payment timing select after/before activation | :48 | PRESENT | :51 |
| O5 | Default admission plan select (active plans, amount + currency) | :49 | PRESENT | :52 |
| O6 | Joining fee (number ≥0, required) | :50 | PRESENT | :53 |
| O7 | Joining fee currency (3 letters, pattern) | :51 | PRESENT | :54 |
| O8 | Re-join dues select once / each_join | :52 | PRESENT | :55 |
| O9 | Application expiry (days) ≥1 | :53 | PRESENT | :56 |
| O10 | Plans load error (server message) | :55 | CHANGED | :58 SettingsQueryState generic "Couldn't load admission plans" + Retry (P3) |
| O11 | Paid recipe without a price → warning | :56 | PRESENT | :59 |
| O12 | Vouches required (≥1) | :60 | PRESENT | :63 |
| O13 | Minimum voucher tenure (days, ≥0) | :61 | PRESENT | :64 |
| O14 | Pending applicants per voucher (≥1) | :62 | PRESENT | :65 |
| O15 | Vouch expiry (days, ≥1) | :63 | PRESENT | :66 |
| O16 | "Vouches replace staff approval" checkbox | :65 | PRESENT | :68 |
| O17 | Membership application questions (CustomFormBuilder) | :67 | PRESENT | :70 |
| O18 | "Save admission settings" → `saveAdmissionSettings` (+ recipe); invalidates member and walk-in-admission | :25-32, 69 | PRESENT | :28-35, Save/Discard when draft/recipe :72 |
| O19 | Saved / error | :70-71 | PRESENT | :73-74 |
| O20 | Loading / load error | :33-34 | PRESENT | :36-37 (generic text) |

### P. MakerspaceFeatureSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| P1 | Heading + "Modules are set by the platform administrator…" | MakerspaceFeatureSettings.tsx:53-56 | PRESENT | SettingsRow label/helper :61 |
| P2 | Enabled-module badges | :57-59 | PRESENT | :65-67 |
| P3 | Per-module fieldsets (General + each module) of feature checkboxes from FEATURE_DEFINITIONS; disabled when the module is off, with "Module disabled by the platform administrator." | :63-84 | PRESENT | :71-92 |
| P4 | Toggle → PATCH `{enabled_features}` | :30-48 | PRESENT | :32-58 (+ Undo toast restoring the previous list) |
| P5 | Error | :60 | PRESENT | :68 |

### Q. SpacePacksPanel + SpacePackProfilePicker (gate `canManageMakerspace && packs.import`; profile part `isSuperadmin`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| Q1 | Heading + help (what packs contain, zero stock) | SpacePacksPanel.tsx:39-40 | PRESENT | SettingsRow :39 |
| Q2 | "Export configuration" → `exportSpacePack` | :20-21, 41 | PRESENT | :21-22, 42 |
| Q3 | Space pack JSON textarea | :42-45 | PRESENT | :43-46 |
| Q4 | "Preview import" → `importSpacePack` (dry run) | :22-23, 47 | PRESENT | :23-24, 48 |
| Q5 | "Apply reviewed pack" (needs a preview with changes; sends `base_checksum`); invalidates all queries. No confirm in either version (the preview is the review) | :24-33, 48 | PRESENT | :25-34, 49 |
| Q6 | "Download JSON" (client-side blob) | :49-54 | PRESENT | :50-55 |
| Q7 | Error / status message | :56-57 | PRESENT | :57-58 |
| Q8 | Preview list: N changes, per-change before/after `<details>` | :58-67 | PRESENT | :59-68 |
| Q9 | Saved install profile select (superadmin) | SpacePackProfilePicker.tsx:12-18 | PRESENT | SpacePackProfilePicker.tsx:14-20 |
| Q10 | Previous/Next profiles pagination (count > 24) | SpacePackProfilePicker.tsx:20-25 | PRESENT | :22-27 |
| Q11 | Profile list error | SpacePackProfilePicker.tsx:19 | CHANGED | :13 SettingsQueryState swaps the whole picker for a generic ErrorBlock (inline :21 is now dead code); the server message is lost (P3) |
| Q12 | New install profile name (≤120) + "Save platform profile" → `savePackProfile` | SpacePacksPanel.tsx:34-35, 72-75 | PRESENT | :35-36, 73-76 |

### R. MakerspaceBookingSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| R1 | "Booking requester emails" badge | MakerspaceBookingSettings.tsx:35-36 | PRESENT | :54 |
| R2 | "Email booking requesters" checkbox → PATCH `{booking_requester_notifications_enabled}` | :16-28, 43-46 | PRESENT | :18-46, 59-62 (+ Undo toast) |
| R3 | Help (default; each space may inherit/override) | :38-40 | PRESENT | Row helper :49 |
| R4 | Error | :41 | PRESENT | :57 |

### S. MakerspaceBookingRulesSettings (gate `bookings` module)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| S1 | Heading + help (buffers; cutoff 0) | MakerspaceBookingRulesSettings.tsx:59-60 | PRESENT | SettingsRow :62 |
| S2 | Active spaces from `GET /admin/makerspaces/{id}/spaces/?page_size=200`; one form per space | :51-55, 61-74 | PRESENT | :55-59, 65-72 |
| S3 | Minimum booking duration (minutes, ≥1) | :38, 138-152 | PRESENT | :142 |
| S4 | Maximum booking duration (minutes, ≥1) | :39 | PRESENT | :142 |
| S5 | Booking lead time (minutes, ≥0) | :40 | PRESENT | :142 |
| S6 | Maximum booking advance (days, ≥1) | :41 | PRESENT | :142 |
| S7 | Buffer before (minutes, ≥0) | :42 | PRESENT | :142 |
| S8 | Cleanup after (minutes, ≥0) | :43 | PRESENT | :142 |
| S9 | Cancellation cutoff (hours before start, ≥0) | :44 | PRESENT | :142 |
| S10 | Approval mode select instant / approve | :153-171 | PRESENT | :158-175 |
| S11 | "Save rules" → PATCH `/admin/spaces/{id}/booking-rules/` with per-field and row errors | :99-126, 173-182, 200-221 | PRESENT | Save/Discard when dirty :178; error parsing unchanged |
| S12 | Loading text, "No active bookable spaces." | :61-63 | PRESENT | :65-67 |
| S13 | List load error (server message) | :72 | CHANGED | :62 / :76 generic "Couldn't load booking rules." + Retry (P3) |

### T. MakerspaceReminderSettings (internal gates: `events` / `bookings` modules)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| T1 | Event reminders (`events` module): heading, help, "Event reminder lead hours" comma list | MakerspaceReminderSettings.tsx:44-56, 69 | PRESENT | SettingsRow "Event reminders" :46-58, 69 |
| T2 | Booking reminders (`bookings` module): same, plus the "requester emails must be enabled" note | :44-56, 70 | PRESENT | :46-58, 70 |
| T3 | Validation: unique whole hours 1-8760, ≤100, or blank to disable | :32-41 | PRESENT | :32-43 |
| T4 | "Save {domain} reminders" → PATCH `{event_\|booking_reminder_lead_hours}` | :20-31, 58-60 | PRESENT | Save/Discard when dirty :60 |
| T5 | Error / "Reminder policy saved." | :57, 61 | PRESENT | :59, 61 |

### U. MakerspaceFilamentSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| U1 | Heading + help (auto to-buy item; 0 = off) | MakerspaceFilamentSettings.tsx:59, 64-66 | PRESENT | SettingsRow :49 |
| U2 | Badge `{n}g` / Off | :60-62 | PRESENT | :62-64 |
| U3 | Threshold (g), number ≥0 step 0.01 | :72-83 | PRESENT | :72-83 |
| U4 | Invalid message "Enter zero or a positive gram value." | :70 | PRESENT | :70 |
| U5 | "Save threshold" → PATCH `{filament_low_stock_threshold_grams}` | :26-37, 84-90 | PRESENT | :28-39, Save/Discard :84 |
| U6 | Error | :67-69 | PRESENT | :67-69 |

### V. MakerspaceLoanSettings (gate `charges.loans`, inside Payment settings → Money section)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| V1 | Heading "Loans" + help (deposits raised at issue; late fees after grace) | MakerspaceLoanSettings.tsx:118-121 | PRESENT | SettingsRow label/helper :113 |
| V2 | Deposit mode select none / fixed / per_product | :123-132 | PRESENT | :124-133 |
| V3 | Deposit amount (enabled only for fixed; "Ignored" hint for per_product) | :133-145 | PRESENT | :134-146 |
| V4 | Late fee per day | :146-154 | PRESENT | :147-155 |
| V5 | Late fee cap ("0 means no cap") | :155-163 | PRESENT | :156-164 |
| V6 | Grace days | :164-172 | PRESENT | :165-173 |
| V7 | "Deposit blocks issue" checkbox (disabled without a deposit) + explanation | :173-185 | PRESENT | :174-186 |
| V8 | Client validation `validateLoanForm` (money ≤2 dp, whole days, valid mode) | :40-48, 101-105 | PRESENT | same |
| V9 | "Save loan settings" → PATCH `/admin/makerspace/{id}/payment-settings` (six loan fields) | :82-96, 188-190 | PRESENT | Save/Discard when dirty :189 |
| V10 | "Saved." / error | :191-195 | PRESENT | :190-195 |

### W. MakerspaceSubdomainSettings (gate `platform_hosting === true`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| W1 | Heading + help "Request a subdomain" | MakerspaceSubdomainSettings.tsx:66-71 | PRESENT | SettingsRow :65 |
| W2 | "Active" badge + "Active subdomain: {domain}" (from `is_platform_subdomain`) | :67, 74-77 | PRESENT | :70, 76-78 |
| W3 | Desired subdomain label + "Submit request" → POST `/admin/makerspace/{id}/subdomain-request` (blocked while one is pending) | :33-44, 79-100 | PRESENT | :82-101 |
| W4 | "Request pending review" | :103-105 | PRESENT | :105 |
| W5 | Submit error | :106-108 | PRESENT | :107-109 |
| W6 | Request load error (server message) | :109 | CHANGED | :65 / :110 generic "Couldn't load subdomain." + Retry (P3) |
| W7 | Request history: label, status badge, note, timestamp | :112-128 | PRESENT | :111-127. Absolute `toLocaleString` replaced by `RelativeTime` (P3) |

### X. MakerspaceCustomDomainSettings

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| X1 | Heading + help; status badge Pending/Verified/Failed/Active (self-host) | MakerspaceCustomDomainSettings.tsx:121-128 | PRESENT | SettingsRow :110; badge :122-124 |
| X2 | Domain input (`custom-domain`); clearing it un-hides | :140-155 | PRESENT | :134-149 |
| X3 | "Hide from central directory" (only when a domain is entered) | :158-170 | PRESENT | :152-164 |
| X4 | "Save domain" → PATCH `{frontend_domain, hidden_from_central_directory}`. Saving blank removes the domain with no confirm (same as before) | :67-84, 130-136 | PRESENT | Save/Discard when dirty :130 |
| X5 | Resulting URLs (`https://{d}/`, `/admin`) | :172-181 | PRESENT | :167-175 |
| X6 | DNS TXT record (host/type/value) | :182, 222-236 | PRESENT | :176, 216-229 |
| X7 | TLS/reverse-proxy note | :183-186 | PRESENT | :177-180 |
| X8 | Self-host "custom domain is active" message | :187-191 | PRESENT | :181-185 |
| X9 | "Verify domain" → POST `/admin/makerspace/{id}/verify-domain` + token display | :86-95, 193-203 | PRESENT | :187-197 |
| X10 | "Save the new domain before verifying DNS." | :207-209 | PRESENT | :201-203 |
| X11 | Verify detail + save/verify errors | :210-216 | PRESENT | :204-210 |

### Y. MakerspaceArchiveRequestPanel (gate `canManageMakerspace`; now inside the Modal)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| Y1 | Heading + explanation (superadmin must confirm; access lost; outcome by email) | MakerspaceArchiveRequestPanel.tsx:64-74 | BURIED | Inside the Modal (panel :201-203; file :65-75). The DangerZone shows a shorter consequence (panel :199) |
| Y2 | Load state / load error with code-mapped messages (`ERROR_MESSAGES`) | :76-81, 197-203 | CHANGED | :77 SettingsQueryState shows a generic "Couldn't load archive requests." The code mapping now applies only to create/withdraw errors (P3) |
| Y3 | Pending request card: Pending badge, reason, "Filed by … on …" | :83-104 | BURIED | Modal only (:80-102). The page does not show that a request is pending |
| Y4 | "Withdraw" → POST `/archive-requests/{id}/withdraw` (no confirm before or now) | :51-57, 90-97 | BURIED | Modal only, :88-95 |
| Y5 | Reason textarea (required, ≤2000, counter, "Do not include personal data") | :121-141 | BURIED | Modal only, :118-138 |
| Y6 | "Request archival" submit → POST `/archive-requests` (reason) | :40-50, 108-120, 143-149 | BURIED | Modal only, :145 (danger-styled now). Reached through DangerZone "Request archival…" → modal → submit |
| Y7 | Create/withdraw error with code mapping | :153-155 | PRESENT | Inside the modal (:150-152) |
| Y8 | Resolved history: status badge, requester/time, reason, resolution note, resolver/time | :157-195 | BURIED | Modal only, :154-192 |

### Z. EvidenceRetentionPanel (gate `canManageMakerspace`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| Z1 | Heading + help (rows immutable; bytes expire) | EvidenceRetentionPanel.tsx:57-60 | PRESENT | SettingsRow :53 |
| Z2 | Irreversibility warning note | :61-63 | PRESENT | :56-58 |
| Z3 | Retention days: number 30-3650, required | :64-76 | PRESENT | :59-71 |
| Z4 | "Save override" → PATCH `{object_retention_days}` (no confirm before or now) | :40-43, 77 | PRESENT | Save/Discard when dirty (also dirty when touched with no override), :72 |
| Z5 | "Use platform default" → PATCH `{object_retention_days: null}` | :78-85 | PRESENT | :73-80 |
| Z6 | Inherited/override read-out + "Automatic expiry is enabled/disabled" | :87-92 | PRESENT | :82-87 |
| Z7 | Update error | :93 | PRESENT | :88 |
| Z8 | Preview: N photo objects (MB) eligible as of …; "continues in bounded batches" | :94-103 | PRESENT | :89-98 (wrapped in SettingsQueryState) |
| Z9 | Load error with server detail (`errorText`) + Retry | :45-52 | CHANGED | :48-49 generic SettingsQueryState message + Retry (P3) |

### Z′. AbandonedUploadCleanupSection (inside EvidenceRetention)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| Z′1 | Heading + help (only never-used upload slots; legacy never eligible) | AbandonedUploadCleanupSection.tsx:31-36 | PRESENT | SettingsRow :106 |
| Z′2 | "Clean up never-used uploads for this space" → PATCH `{abandoned_upload_cleanup_enabled}` (no confirm before or now) | :37-45 | PRESENT | :109-117 |
| Z′3 | Abandoned upload age (days) 1-3650 | :46-58 | PRESENT | :118-130 |
| Z′4 | "Save age" → PATCH `{abandoned_upload_retention_days}` | :59 | PRESENT | Save/Discard when dirty (or touched with no override), :131 |
| Z′5 | "Use platform age" → `{abandoned_upload_retention_days: null}` | :60-67 | PRESENT | :132-139 |
| Z′6 | Platform age + deployment switch read-out | :69-74 | PRESENT | :141-146 |
| Z′7 | Preview: candidates, has_more, late-write receipts (due) | :75-82 | PRESENT | :147-154 |

### Helper files (new)
- `SettingsEditorActions.tsx` (9 lines) renders `SettingsActions` (Discard + "Save changes", `type=submit` unless `onSave`) only when `dirty || pending`. I checked every use in scope: each one without `onSave` sits inside its own `<form>`, so Save still submits. The one behaviour change everywhere: before, a Save button was always visible (usually disabled). Now it appears only after an edit, plus a new Discard.
- `SettingsQueryState.tsx` (15 lines) wraps `QueryContent`. Loading shows a skeleton; error shows a generic `Couldn't load {resource}. Try again.` + Retry. This is why server error text (`StructuredApiError.detail`, code maps) disappears from load errors in E12, O10, Q11, S13, W6, Y2 and Z9.
- `SettingsResetAction.tsx` (24 lines) is a DangerZone plus its own `ConfirmDialog`, for clearing secrets. None of the components in this part use it (Email, Payment and Webhook do: other agent). Because it opens its own ConfirmDialog, the `confirms`-only issue in DangerZone does not affect those resets.
- **Confirm check (per the correction):** destructive actions in this part had no ConfirmDialog in the OLD code, and none was dropped. The one DangerZone here (archive) only opens a Modal, so the missing `confirm` is harmless.

### Counts

| page | PRESENT | BURIED | CHANGED | MISSING | total |
|---|---|---|---|---|---|
| A. Panel shell & inline rows | 13 | 2 | 3 | 0 | 18 |
| B. Child mount map | 25 | 1 | 0 | 0 | 26 |
| C. General | 9 | 0 | 0 | 0 | 9 |
| D. Public site | 5 | 0 | 0 | 0 | 5 |
| E. Loan policy | 11 | 0 | 1 | 0 | 12 |
| F. Profile | 9 | 0 | 1 | 0 | 10 |
| G. Hours editor | 5 | 0 | 0 | 0 | 5 |
| H. Branding | 11 | 0 | 0 | 0 | 11 |
| I. ImageUploader | 5 | 0 | 0 | 0 | 5 |
| J. Theme | 7 | 0 | 3 | 0 | 10 |
| K. Public stats | 8 | 0 | 0 | 0 | 8 |
| L. Location | 7 | 0 | 0 | 0 | 7 |
| M. Geofence | 7 | 0 | 0 | 0 | 7 |
| N. Membership | 8 | 0 | 0 | 0 | 8 |
| O. Admission | 19 | 0 | 1 | 0 | 20 |
| P. Features | 5 | 0 | 0 | 0 | 5 |
| Q. Space packs + picker | 11 | 0 | 1 | 0 | 12 |
| R. Booking settings | 4 | 0 | 0 | 0 | 4 |
| S. Booking rules | 12 | 0 | 1 | 0 | 13 |
| T. Reminders | 5 | 0 | 0 | 0 | 5 |
| U. Filament | 6 | 0 | 0 | 0 | 6 |
| V. Loans | 10 | 0 | 0 | 0 | 10 |
| W. Subdomain | 6 | 0 | 1 | 0 | 7 |
| X. Custom domain | 11 | 0 | 0 | 0 | 11 |
| Y. Archive request | 1 | 6 | 1 | 0 | 8 |
| Z. Evidence retention | 8 | 0 | 1 | 0 | 9 |
| Z′. Abandoned upload | 7 | 0 | 0 | 0 | 7 |
| **Total** | **235** | **9** | **14** | **0** | **258** |

### Restore candidates

1. **P1 — Whole page blocked by one GET (A2).** OLD `MakerspaceSettingsPanel.tsx:43-46, 100-262` rendered every section with the `makerspace` prop fallback. NEW `MakerspaceSettingsPanel.tsx:151-152` gives `settings` state to `SettingsLayout`, so a slow or failed `GET /admin/makerspaces/{id}` hides every editor, including those with their own endpoints. Fix: keep the header-level ErrorBlock + Retry as a banner (or a `Callout` above the sections), but always render `sections` using `settings.data ?? makerspace`, as before. At minimum, render the editors that fetch independently (Profile, LoanPolicy, Admission, Kiosk, Notifications, EvidenceRetention, Archive).
2. **P2 — Archive pending request and history hidden behind the modal (A17, B17, Y1-Y8).** OLD showed `MakerspaceArchiveRequestPanel.tsx:83-105` (pending card + Withdraw) and `:157-168` (history) inline. NEW only shows them after clicking DangerZone "Request archival…". Fix (Yuyu): keep the DangerZone, but when a pending request exists, swap its action label to "View pending request" (or show a `Callout` warn row above it with Withdraw as a row button). Move "Resolved history" into a read-only SettingsRow under Privacy & evidence, or keep it in the modal but say in the DangerZone consequence that a request is pending. The request form stays in the modal.
3. **P3 — Superadmin access helper lost its safety clause (A6).** Restore old text `MakerspaceSettingsPanel.tsx:146-148` ("It does not revoke the superadmin's platform/database access") into the SettingsRow helper at new :120. Optional: add `confirm: {title, message}` on turning access off, because the superadmin cannot undo it. That would be new; the old code had none either.
4. **P3 — MFA link moved off the page (A4).** OLD `MakerspaceSettingsPanel.tsx:103` `<Link to="/mfa">`. Already reachable from the StaffShell user menu (StaffShell.tsx:62). If parity matters, add a "Your account" SettingsRow under Privacy & evidence with an `ActionControl` href `/mfa`.
5. **P3 — Theme copy and read-out regressions (J2, J6, J8).** Restore the contrast-failure wording from OLD `MakerspaceThemeSettings.tsx:72` ("Choose a lighter or darker primary fill") when `report.errors` is empty and only `report.failures` exist. Keep "Enter a #RGB…" for format errors only. Optionally restore the numeric "Derived link colour: rgb(…)" read-out (OLD :63) next to the new example link, and the automatic button-text/link-adaptation sentence (OLD :43).
6. **P3 — Print recovery badge tone (A13).** Pass `tone={policy === "token_only" ? "neutral" : "success"}` at new `MakerspaceSettingsPanel.tsx:139` (OLD :207).
7. **P3 — Server error text replaced by generic messages (E12, O10, Q11, S13, W6, Y2, Z9).** `SettingsQueryState.tsx` should take an optional `detail` (e.g. `error instanceof StructuredApiError ? error.detail : undefined`) so code-mapped and server messages (OLD `MakerspaceArchiveRequestPanel.tsx:197-203`, `EvidenceRetentionPanel.tsx:20-23`) still show.
8. **P3 — Layout nits.** Wrap `MakerspacePublicSiteSettings` (D1-D5) in a `SettingsRow label="Public site"`. Move `MakerspaceReminderSettings` from "Lending" to "Bookings", or to a new "Events & bookings" section (B11). Hide empty sections such as "Lending" when kiosk/events/bookings are all off. Restore the "hours are informational" caveat in the Profile helper (F1, OLD `MakerspaceProfileSettings.tsx:42`). Show absolute dates in subdomain history (W7) or a title tooltip on `RelativeTime`.
9. **Info for the other agent (not a loss here).** `ApiClientsTelegramSettings` moved from `ApiClientsPanel.tsx:153` (api tab) to Settings → Email & integrations (`MakerspaceSettingsPanel.tsx:192`), with the same `isSuperadmin` gate.

---

Scope: `settings` tab children — payments, billing documents, kiosk stations, notification timing/mutes/channels/recipients/rooms, integration health, email (SMTP + recipients), chat webhooks; plus ApiClientsTelegramSettings (moved from `api` tab). OLD = d3e5ed29, NEW = working tree.

## settings — Makerspace settings: payment / billing / kiosk / notification / integration editors (MakerspaceSettingsPanel.tsx children)

Routing: tab `settings` is gated `canManageMakerspace` (= `has("manage_makerspace")`, superadmin always true; staffAccess.ts:144) in both versions. OLD rendered every child as a flat stack in one `Panel` (MakerspaceSettingsPanel.tsx:101-262). NEW renders `SettingsLayout` with an anchor sub-nav (`subnav="auto"`, ≥5 sections) and ALL sections on one scrolling page (SettingsLayout.tsx:35-50). Sections relevant here: `lending` (Kiosk), `money` (Payments, Billing), `notifications` (Timing, Mute matrix + Channel prefs, Recipient picker, Rooms), `integrations` (Email, Webhooks, Telegram [new home], Integration health). Every child gate expression is byte-identical old→new. Most children are now wrapped in `SettingsQueryState` (QueryContent) and use `SettingsEditorActions` (Save/Discard only shown when dirty) and `SettingsResetAction` (DangerZone + its own real `ConfirmDialog`, SettingsResetAction.tsx:32-37).

### Mounts and gates

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | MakerspacePaymentSettings mount (unconditional, `makerspace={settings.data ?? makerspace}`) | MakerspaceSettingsPanel.tsx:129 | PRESENT | MakerspaceSettingsPanel.tsx:182, section "Money"; same gate (none) |
| 2 | BillingDocumentsSettings mount, gate `canManageMakerspace` | MakerspaceSettingsPanel.tsx:121 | PRESENT | :183 "Money"; identical gate |
| 3 | KioskStationSettings mount, gate `canManageMakerspace && (settings.data?.enabled_features ?? []).includes("inventory.kiosk")` | MakerspaceSettingsPanel.tsx:130-132 | PRESENT | :171 "Lending"; identical gate |
| 4 | NotificationTimingSettings mount, gate `canManageMakerspace && enabledModules.includes("notifications")` | MakerspaceSettingsPanel.tsx:134 | PRESENT | :186 "Notifications"; identical gate |
| 5 | "Notification channels" block: NotificationMuteMatrix + NotificationRecipientPicker + NotificationDestinations(`availableChannels={enabledModules}`), no gate | MakerspaceSettingsPanel.tsx:252-260 | PRESENT | :185-189 "Notifications" section; no gate, same props |
| 6 | IntegrationHealthPanel mount (unconditional) | MakerspaceSettingsPanel.tsx:135 | PRESENT | :193 "Email & integrations" |
| 7 | MakerspaceEmailSettings mount (unconditional) | MakerspaceSettingsPanel.tsx:237 | PRESENT | :191 "Email & integrations" |
| 8 | MakerspaceWebhookSettings mount (unconditional) | MakerspaceSettingsPanel.tsx:238 | PRESENT | :191 "Email & integrations" |
| 9 | Children render independently of the parent `/admin/makerspaces/{id}` query (each has its own query; parent loading/error never hid them) | MakerspaceSettingsPanel.tsx:100-262 | CHANGED | :151-152 `state={{status: settings.isLoading ? "loading" : settings.error ? "error" : "ready"}}` → QueryContent (LayoutFrame.tsx:39-43) renders NONE of the sections while the parent GET loads or if it fails. A failing makerspace GET now makes payments/notifications/integrations editors unreachable (retry only). |

### MakerspacePaymentSettings ("Money")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 10 | Heading "Stripe payments" + help "Secret credentials are encrypted; saved keys are never displayed again." | MakerspacePaymentSettings.tsx:84-87 | PRESENT | MakerspacePaymentSettings.tsx:85 SettingsRow label/helper |
| 11 | Effective-mode badge (Raw credentials / Stripe Connect / Unavailable) from GET `/admin/makerspace/{id}/payment-settings` | :89-91, :183-185 | PRESENT | :91-93 (StatusPill renders children) |
| 12 | Field "Stripe publishable key" (password, autocomplete new-password, placeholder "Stripe publishable key set" when set; sent only if non-empty) | :94-103, :47 | PRESENT | :96-105 |
| 13 | Field "Stripe secret key" (same pattern) | :104-113 | PRESENT | :106-115 |
| 14 | Field "Stripe webhook secret" (same pattern) | :114-123 | PRESENT | :116-125 |
| 15 | Default payment currency (unlabelled input, aria-label only, maxLength 3, lowercased; also refreshes `makerspace-profile`) | :124-130, :36-40 | PRESENT | :126-132 (still no visible label in either) |
| 16 | "Save payment settings" PATCH `payment-settings` {default_currency, keys if typed} — always visible | :133-135 | CHANGED | :135 SettingsEditorActions: "Save changes"/"Discard" appear only when dirty. Equivalent. |
| 17 | "Clear raw configuration" PATCH all three keys = "" (disabled unless any key set) — NO confirmation | :136-149 | CHANGED | :164-169 SettingsResetAction → DangerZone + real ConfirmDialog with consequence text. Improvement (confirmation added). |
| 18 | Stripe Connect block, gate `makerspace.platform_hosting`: status text + "Connect Stripe"/"Reconnect Stripe" POST `payment-settings/connect/onboard` → redirect to `authorize_url` | :151-161, :71-77 | PRESENT | :138-148. (No disconnect action exists in either version.) |
| 19 | Precedence help "A complete raw credential pair takes precedence over Connect…" | :162-164 | PRESENT | :149-151 |
| 20 | Combined error line (settings/save/clear/onboard) | :167-171 | PRESENT | :154-158 (load error now also shown by SettingsQueryState) |
| 21 | MakerspaceLoanSettings, gate `featureEnabled(makerspace.enabled_features, "charges.loans")` — rendered regardless of payment-settings query state (comment :172-175: must stay reachable for cash-only spaces without the payments rail) | :176-178 | CHANGED | :169 now INSIDE `<SettingsQueryState query={settings}>` (:85). While payment-settings loads, or if it errors, loan deposit/cap/blocking settings are hidden. The endpoint is registered under `_separable("payments_rail", …)` (backend/apps/admin_api/urls_platform.py:208-224) → 404 when the rail is tombstoned → loan settings disappear exactly in the cash-only case the old comment protects. Gate effectively changed. |

### BillingDocumentsSettings ("Money")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 22 | Heading "Receipts and accounting" + help "Gross-only acknowledgements…" | BillingDocumentsSettings.tsx:28-29 | PRESENT | BillingDocumentsSettings.tsx:30 SettingsRow |
| 23 | "Configure documents" disclosure (aria-expanded); GET `/admin/makerspace/{id}/billing-settings` only when expanded | :30, :13 | PRESENT | :33, :16 (already a disclosure in old) |
| 24 | Field "Number prefix" (maxLength 32) | :35-36 | PRESENT | :38-39 |
| 25 | Field "Issuer name" (maxLength 150) | :35-36 | PRESENT | :38-39 |
| 26 | Field "Issuer address" (input, maxLength 1000) | :35-36 | PRESENT | :38-39 |
| 27 | Field "Issuer identifier (no tax calculation)" (maxLength 64) | :35-36 | PRESENT | :38-39 |
| 28 | Field "Footer" (maxLength 1000) | :35-36 | PRESENT | :38-39 |
| 29 | "Accounting account codes (JSON)" textarea rows 6; JSON.parse on save (parse error → save.error) | :37, :19 | PRESENT | :40, :22 |
| 30 | Defaults help "income 4000, cash 1000, online 1010, loan-deposit liability 2100…" | :38 | PRESENT | :41 |
| 31 | "Save receipt settings" PATCH `billing-settings`, always visible; on success invalidates `operations-report/accounting-journal` | :39, :25 | CHANGED | :42 SettingsEditorActions (submit) only when dirty, + Discard. Equivalent. |
| 32 | Status "Receipt settings saved." | :40 | PRESENT | :43 |
| 33 | Loading / error lines | :32-33 | PRESENT | :34-36 (+SettingsQueryState) |

### KioskStationSettings ("Lending")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 34 | Heading "Kiosk stations" + help "A Station PIN only unlocks the kiosk…" | KioskStationSettings.tsx:61-62 | PRESENT | KioskStationSettings.tsx:61 SettingsRow |
| 35 | Create field "Name" (required, maxLength 160) | :65 | PRESENT | :67 |
| 36 | Create field "Kind" select Handover (default) / Scanner | :66-69 | PRESENT | :68-71 |
| 37 | "Create station" POST `/admin/makerspace/{id}/kiosk-stations/` {name, kind} | :70, :32-37 | PRESENT | :72 |
| 38 | Create error "The station could not be created." | :72 | PRESENT | :74 |
| 39 | One-time PIN read-out "PIN for X (shown once)" + station_url | :73-76 | PRESENT | :75-78 |
| 40 | Station list: name, kind badge, enabled/disabled badge | :78-81 | PRESENT | :84-86 ListRow (+ new empty state :80) |
| 41 | "Rotate PIN" / "Re-enable with new PIN" POST `/admin/kiosk-stations/{id}/rotate/` (no confirm in either) | :82 | PRESENT | :88 visible row button (now disabled while pending) |
| 42 | "Reveal PIN" (opens password form) — visible row button | :83 | BURIED | :90 inside OverflowMenu "Actions for {name}" |
| 43 | "Disable" DELETE `/admin/kiosk-stations/{id}/` — visible danger button, no confirm | :84 | BURIED | :91 OverflowMenu item (tone danger), no `confirm:` → still no confirmation dialog |
| 44 | Reveal form: "Your current password to reveal {name}" (password, required) + Reveal POST `/admin/kiosk-stations/{id}/reveal/` {current_password} + Cancel + error copy | :87-92 | PRESENT | :96-101 |

### NotificationTimingSettings ("Notifications")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 45 | Heading "Notification delivery times" | NotificationTimingSettings.tsx:21 | PRESENT | NotificationTimingSettings.tsx:23 SettingsRow label |
| 46 | Help "Times use {timezone ?? 'the makerspace timezone'}… Safety alerts remain immediate…" (timezone prop never passed in either) | :22 | PRESENT | :25 |
| 47 | "Quiet from" (type=time, required) | :24 | PRESENT | :27 |
| 48 | "Quiet until" (time, required) | :24 | PRESENT | :27 |
| 49 | "Daily digest at" (time, required) | :24 | PRESENT | :27 |
| 50 | Channel checkboxes: email, telegram, slack, mattermost, discord, native push, webhook | :25 | PRESENT | :28 |
| 51 | "Inbound bounce signing secret" (password, minLength 32, maxLength 200; help switches on `bounce_configured`; blank keeps, new value rotates — no confirm in either) | :26 | PRESENT | :29 |
| 52 | "Save delivery times" PATCH `/integrations/makerspace/{id}/timing-policy`, always visible | :29 | CHANGED | :32 SettingsEditorActions (submit) only when dirty. Equivalent. |
| 53 | Status "Delivery policy saved." + error line | :28, :30 | PRESENT | :31, :33 |

### NotificationMuteMatrix + new NotificationMuteTable ("Notifications")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 54 | Loading "Loading notification rules..." / error shows server message | NotificationMuteMatrix.tsx:47-53 | CHANGED | NotificationMuteMatrix.tsx:50-56 SettingsQueryState: skeleton / generic "Couldn't load mute matrix. Try again." + Retry (server message dropped) |
| 55 | Section "Advanced email recipient/event mutes" + help "Checked = muted… Return reminders cannot be individually muted." | :64-71 | PRESENT | :63 SettingsRow |
| 56 | Per catalog entry card "{Stream} · {Audience} emails" | :81-83 | PRESENT | :75-77 |
| 57 | Read-only notice "Advanced mutes are read-only while this feature's Email channel is disabled." | :84-88 | PRESENT | :78-82 |
| 58 | Target × event mute checkbox table; PATCH `/admin/makerspace/{id}/notification-rules` {changes:[…]} optimistic; disabled while pending or email off; aria-describedby | :89-152, :23-45 | PRESENT | NotificationMuteTable.tsx:8-20 (DataTable); sr-only `<caption>` dropped |
| 59 | Mute error alert | :158-162 | PRESENT | :89-93 |

### NotificationChannelPreferences (mounted inside NotificationMuteMatrix in both: old NotificationMuteMatrix.tsx:59 → new :62)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 60 | Mount (only when notification-rules loaded) | NotificationMuteMatrix.tsx:59 | PRESENT | NotificationMuteMatrix.tsx:62 |
| 61 | Heading "Notification channels" + help "Checked = enabled… affect staff email only…" | NotificationChannelPreferences.tsx:67-73 | PRESENT | NotificationChannelPreferences.tsx:69-75 |
| 62 | Feature × channel enable matrix; PATCH `notification-rules` {preferences:[…]} optimistic | :74-127, :34-61 | PRESENT | :77-88 DataTable (sr-only caption dropped) |
| 63 | "Delivery setup needed" warnings (Slack/Mattermost/Discord webhook missing; Telegram token or chat id missing) from GET `/admin/makerspace/{id}/api-settings` (DELIVERY_SETTINGS_KEY) | :128-141, :177-201 | PRESENT | :89-102, :136-160 |
| 64 | "Unable to check channel setup: {message}" | :142-144 | CHANGED | :76 SettingsQueryState → generic "Couldn't load channel setup. Try again." + Retry; also a skeleton block now renders above the matrix while api-settings loads |
| 65 | Preference update error alert | :145-149 | PRESENT | :104-108 |

### NotificationRecipientPicker + NotificationRecipientEvent ("Notifications"; non-delegated mount)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 66 | Heading "Who gets notified" + non-delegated help text | NotificationRecipientPicker.tsx:53-60 | PRESENT | NotificationRecipientPicker.tsx:57-64 (h3 + SettingsRow "Recipients") |
| 67 | Loading / empty "None of the modules with selectable recipients are installed." (load error was silent; now surfaced) | :62-67 | PRESENT | :58, :66-71 |
| 68 | "Area" select (FEATURE_LABELS) from GET `/admin/makerspace/{id}/notification-recipient-rules` | :72-89 | PRESENT | :76-93 |
| 69 | "Event" select | :90-103 | PRESENT | :94-107 |
| 70 | Empty-rules text "Nobody selected — everyone whose role covers this area is notified." | NotificationRecipientEvent.tsx:74-80 | PRESENT | NotificationRecipientEvent.tsx:75-81 |
| 71 | Managed-policy marker notice "Another policy also applies…" | :81-90 | PRESENT | :82-91 |
| 72 | Per-rule recipient type select: A role / A named member / All members / The person it is about | :158-172 | PRESENT | :148-162 |
| 73 | Role select "Choose a role…" (data.roles) | :173-183 | PRESENT | :163-173 |
| 74 | Member select "Choose a member…" (data.members username) | :184-196 | PRESENT | :174-186 |
| 75 | Remove recipient (draft-only, applied on save) | :197-203 | PRESENT | :187-193 |
| 76 | Per-rule ScopePicker (Machine types / Machines / Categories) | :101-108 | PRESENT | :102-109 |
| 77 | Save error + delegated "Each delegated rule needs at least one machine or machine type." | :112-117 | PRESENT | :113-118 |
| 78 | "Add recipient" | :119-128 | PRESENT | :120-129 |
| 79 | "Save recipients" PUT `notification-recipient-rules` {feature, event, rules}, always visible (disabled until drafts) | :129-136 | CHANGED | :130 SettingsEditorActions "Save changes" only when drafts !== null. Equivalent. |
| 80 | "Discard changes" | :137-141 | PRESENT | :130 Discard (now also clears error) |

### NotificationDestinations + notificationDestinations/{DestinationRow, DestinationForm, ScopePicker} ("Notifications")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 81 | Heading "Rooms" + help "Each room is one chat destination…" | NotificationDestinations.tsx:51-58 | PRESENT | NotificationDestinations.tsx:52-58 SettingsRow |
| 82 | Loading "Loading rooms…" (GET `/admin/makerspace/{id}/notification-destinations`) | :60-62 | PRESENT | :60 SettingsQueryState (error now surfaced) |
| 83 | Room row read-outs: label, channel, Configured/No credential, Paused, "Everything"/"N scoped" | DestinationRow.tsx:42-53 | PRESENT | DestinationRow.tsx:41-46 ListRow |
| 84 | "Edit" → inline DestinationForm (channel locked) | DestinationRow.tsx:28-39, :55-57 | PRESENT | :28-39, :47 |
| 85 | "Remove" DELETE `/admin/makerspace/{id}/notification-destinations/{id}` — visible danger button, no confirm; delete error never shown in either | DestinationRow.tsx:58-60; NotificationDestinations.tsx:41-45 | BURIED | DestinationRow.tsx:48 OverflowMenu item (tone danger), no `confirm:` → still no confirmation, now one click deeper |
| 86 | Empty copy "No rooms yet. Alerts still go to the webhook saved in Chat webhooks above…" | NotificationDestinations.tsx:78-83 | CHANGED | :76-81 copy now wrong: Chat webhooks lives in the LATER "Email & integrations" section (old order put it above) |
| 87 | "Add a room" (disabled when no installed chat module) | :94-101 | PRESENT | :92-99 |
| 88 | "No chat modules are installed for this makerspace." | :103-107 | PRESENT | :101-105 |
| 89 | Form "Channel" select (installed modules only; disabled on edit) | DestinationForm.tsx:78-92 | PRESENT | DestinationForm.tsx:78-92 (unchanged) |
| 90 | Form "Room name" (required, placeholder "Laser team") | :93-102 | PRESENT | :93-102 |
| 91 | Form "Telegram chat ID" (telegram only, required) + help "Add this makerspace's bot…" | :105-119 | PRESENT | :105-119 |
| 92 | Form "Incoming webhook URL" (password; "(leave blank to keep)" when set) | :121-133 | PRESENT | :121-133 |
| 93 | Form "Signing secret" (webhook only; minLength 16; required unless set) + HMAC help | :136-156 | PRESENT | :136-156 |
| 94 | Form "Payload format" v1 legacy / v2 structured (webhook only) | :158-162 | PRESENT | :158-162 |
| 95 | Form "Deliver to this room" checkbox | :163-170 | PRESENT | :163-170 |
| 96 | Form ScopePicker (Machine types / Machines / Categories; hidden when no options) | :172; ScopePicker.tsx:15-56 | PRESENT | :172; ScopePicker.tsx (only min-h-11 change) |
| 97 | Form "Save room" POST/PUT + error + "Cancel" | :40-66, :174-182 | PRESENT | same lines |

### IntegrationHealthPanel + IntegrationHealthRooms ("Email & integrations")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 98 | Heading "Integration health" + overall status badge (GET `/admin/makerspace/{id}/integration-health`) | IntegrationHealthPanel.tsx:77-78 | PRESENT | IntegrationHealthPanel.tsx:76 SettingsRow, badge :81 |
| 99 | Loading + inline error message, stale data kept visible | :80-81 | CHANGED | :76 SettingsQueryState wraps whole panel: any error (incl. a failed 60 s background refetch) replaces the panel and hides last-known data; inner ErrorBlock :85 is unreachable |
| 100 | "Email log" link → `email-logs` tab | :84 | PRESENT | :87 |
| 101 | "Telegram test" link → `api` tab (where the Telegram card lived) | :85 | CHANGED | :88 → `settings#integrations` = the page you are already on; React Router Link does not scroll to hash, and the Telegram card only renders for `isSuperadmin` → effectively a no-op button for everyone |
| 102 | Email metrics Total / Pending / Sent / Failed / Stalled | :91-98 | PRESENT | same block |
| 103 | Last email failure (subject, stream, relative time, error) / "No failed deliveries." | :99-111 | PRESENT | same |
| 104 | Deliveries by stream: Hardware / Printing last-sent | :114-119 | PRESENT | same |
| 105 | SMTP configured badge + detail | :121-123 | PRESENT | same |
| 106 | Telegram configured badge + detail | :125-127 | PRESENT | same |
| 107 | SMS configured badge + detail | :129-131 | PRESENT | same |
| 108 | Native push: configured, Enabled/Disabled, last failure | :133-140 | PRESENT | same |
| 109 | "Chat and webhook rooms" → IntegrationHealthRooms (per room + space-wide legacy: Not configured / Inactive / N failed / Healthy, last sent, last failure; empty text) | :142-149; IntegrationHealthRooms.tsx:42-117 | PRESENT | :151; IntegrationHealthRooms.tsx (badge component swap only) |
| 110 | Worker: Broker / Eager / Stale / Last seen | :151-161 | PRESENT | same |
| 111 | Auto-refresh every 60 s and on window focus | :67-68 | PRESENT | same |

### MakerspaceEmailSettings ("Email & integrations")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 112 | Heading "Email (SMTP)" + help "Configure the sender used for staff lifecycle notifications." | MakerspaceEmailSettings.tsx:136-139 | PRESENT | MakerspaceEmailSettings.tsx:138 SettingsRow |
| 113 | "SMTP host" | :161 | PRESENT | :150 |
| 114 | "SMTP port" (inputMode numeric; default 587; non-numeric → 587) | :162, :260 | PRESENT | :151 |
| 115 | "SMTP username" | :163 | PRESENT | :152 |
| 116 | "SMTP password" (password; placeholder "SMTP password set"; sent only if typed) | :164, :266 | PRESENT | :153 |
| 117 | "SMTP from email" | :165 | PRESENT | :154 |
| 118 | "Use STARTTLS (587)" checkbox (mutually exclusive with SSL) | :168-177 | PRESENT | :157-166 |
| 119 | "Use implicit SSL (465)" checkbox | :178-187 | PRESENT | :167-176 |
| 120 | "Save email settings" PATCH `/admin/makerspace/{id}/api-settings`, always visible | :142-149 | CHANGED | :145 SettingsEditorActions only when dirty. Equivalent. |
| 121 | "Clear SMTP password" PATCH {smtp_password:""} — no confirm | :150-157 | CHANGED | :186 SettingsResetAction (real ConfirmDialog). Improvement. |
| 122 | Load / save / clear error lines | :189-196 | PRESENT | :178-185 |
| 123 | "Notification recipients" heading + help "Unchecked managers will not receive…" | :202-206 | PRESENT | :188 SettingsRow |
| 124 | Per-manager checkbox (username, email - role label) from GET `/admin/makerspace/{id}/notification-recipients` | :219-243 | PRESENT | :198-222 |
| 125 | "Save recipients" PATCH `notification-recipients`, always visible | :208-215 | CHANGED | :194 SettingsEditorActions only when dirty. Equivalent. |
| 126 | Empty "No managers to notify yet." | :245-247 | PRESENT | :224-226 |
| 127 | Recipients load error shows server message | :248 | CHANGED | :227 generic and mis-labelled "Couldn't load email. Try again." |
| 128 | SMTP form state isolated from Telegram form (Telegram card on a different tab) | — (ApiClientsPanel.tsx:153 separate tab) | CHANGED | SMTP form (:64-75) and Telegram card (ApiClientsTelegramSettings.tsx:26-32) now on the same page sharing query key `["api-settings", id]`; saving either invalidates it and the other's `useEffect` resets its unsaved edits (superadmin only). The DELIVERY_SETTINGS_KEY comment (MakerspaceWebhookSettings.tsx:25-28) documents this exact hazard. |

### MakerspaceWebhookSettings ("Email & integrations")

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 129 | Heading "Chat webhooks" + help "…enable delivery separately in the notification channel matrix below…" | MakerspaceWebhookSettings.tsx:40-46 | CHANGED | :42 copy now wrong: the matrix is in the EARLIER "Notifications" section |
| 130 | Slack / Mattermost / Discord cards: Configured/Not configured badge + "Paste an incoming webhook URL. The saved URL is never displayed again." | :49-66, :115-123 | PRESENT | :48-65, :114-122 |
| 131 | "{Provider} incoming webhook URL" (password, autocomplete new-password) | :124-133 | PRESENT | :123-132 |
| 132 | "Save {Provider} webhook" PATCH `api-settings` {provider_webhook_url}, always visible | :135-142 | CHANGED | :134 SettingsEditorActions only when typed. Equivalent. |
| 133 | "Clear {Provider} webhook" PATCH "" — no confirm | :143-150 | CHANGED | :147 SettingsResetAction (real ConfirmDialog; one DangerZone per card). Improvement. |
| 134 | Save/clear errors, loading/error lines | :68-73, :152-161 | PRESENT | :67-72, :137-146 |

## api → settings — ApiClientsTelegramSettings (old entry: ApiClientsPanel.tsx)

Old: rendered on tab `api` inside ApiClientsPanel, gate `isSuperadmin` (ApiClientsPanel.tsx:153); `api` tab itself has no tab gate (staffAccess.ts default `true`). New: removed from ApiClientsPanel and rendered on tab `settings`, section "Email & integrations", gate `isSuperadmin` (MakerspaceSettingsPanel.tsx:192). Settings tab requires `canManageMakerspace`, which is always true for superadmin, so the effective gate is unchanged.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 135 | Telegram card placement | ApiClientsPanel.tsx:153 | CHANGED | MakerspaceSettingsPanel.tsx:192 (settings → Email & integrations); same `isSuperadmin` gate |
| 136 | Heading "Integration settings" | ApiClientsTelegramSettings.tsx:77 | PRESENT | ApiClientsTelegramSettings.tsx:70 renamed "Telegram" + new "Token saved / No token saved" pill :71 |
| 137 | "Telegram group chat ID" | :79-87 | PRESENT | :73-81 SettingsRow |
| 138 | "Telegram bot token" (password, placeholder "Telegram bot token set"; sent only if typed) | :88-98 | PRESENT | :82-92 SettingsRow |
| 139 | "Save integration settings" PATCH `/admin/makerspace/{id}/api-settings`, always visible | :101-107 | CHANGED | :94-96 SettingsActions only when dirty/error. Equivalent. |
| 140 | "Clear Telegram token" PATCH {telegram_bot_token:""} — no confirm | :108-115 | CHANGED | :115-118 DangerZone + own ConfirmDialog. Improvement. |
| 141 | "Send Telegram test alert" POST `/integrations/telegram/test-alert` {makerspace_id, message} | :117-123, :64-73 | PRESENT | :97-103 |
| 142 | Test result "Telegram delivered: yes/no - detail" + test error | :128-134 | PRESENT | :108-114 |
| 143 | Loading / load / save / clear errors | :124-127 | PRESENT | :104-107 (load error now generic) |

Reference only (not reached from settings): KioskReplayRecoveryPanel / KioskReplayDetail / KioskReplayResolution are mounted on the `requests` tab in both versions (old panels/RequestsPanel.tsx:6 → new RequestsPanel.tsx:7, rendered in the `detail` slot at RequestQueues.tsx:207). Diffs are cosmetic apart from the panel becoming a CollapsibleSection that starts collapsed when there are 0 failures (KioskReplayRecoveryPanel.tsx:20-22). Status filter, pagination, Review/detail, evidence preview, the "Acknowledge" confirmation step and "Correct online" are all intact. The delegated NotificationRecipientPicker on the Machines tab (MachinesPanel.tsx:163) is out of scope here.

Confirmation audit, destructive actions in scope:
- Clear raw Stripe config, Clear SMTP password, Clear {Slack|Mattermost|Discord} webhook and Clear Telegram token had NO confirmation in OLD. NEW opens a real `ConfirmDialog` for each (SettingsResetAction.tsx:35-37; ApiClientsTelegramSettings.tsx:117-118). None of these rely on `Action.confirms`.
- Remove room (DestinationRow.tsx:48) and Disable kiosk station (KioskStationSettings.tsx:91) are OverflowMenu items with neither `confirm:` nor `confirms`, so there is no dialog. OLD had none either, so this is not a regression, but both are now hidden one click deeper.
- Rotate kiosk PIN, rotate the bounce secret (timing form), and replace the webhook signing secret (room edit) have no confirmation in either version.
- No "disconnect payment provider" action exists in either version.

### Counts

| page | PRESENT | BURIED | CHANGED | MISSING | total |
|---|---|---|---|---|---|
| settings (payment/billing/kiosk/notification/integration children, rows 1-134) | 111 | 3 | 20 | 0 | 134 |
| api → settings (ApiClientsTelegramSettings, rows 135-143) | 6 | 0 | 3 | 0 | 9 |
| **total** | 117 | 3 | 23 | 0 | 143 |

### Restore candidates

1. **P0 (gate change): Loan settings now depend on the payment-settings query** (row 21). OLD `MakerspacePaymentSettings.tsx:176-178` rendered `<MakerspaceLoanSettings makerspaceId>` under `featureEnabled(enabled_features, "charges.loans")` no matter what state payment-settings was in. NEW `MakerspacePaymentSettings.tsx:169` sits inside `<SettingsQueryState query={settings}>` (:85), so a 404 from the `payments_rail`-separable endpoint (tombstoned rail) or any transient error hides deposit, cap and blocking settings. Fix: move the `charges.loans` → `<MakerspaceLoanSettings/>` render out of the wrapper, either as its own row in the "Money" section (MakerspaceSettingsPanel.tsx:181-184) or as a sibling after `</SettingsQueryState>`. Also consider hiding the Stripe row (not showing an error block) when the endpoint 404s.
2. **P2: One parent-query gate now hides every editor** (row 9). NEW `MakerspaceSettingsPanel.tsx:151-152` passes the parent `/admin/makerspaces/{id}` state to SettingsLayout, and QueryContent renders no sections on loading or error. OLD rendered every child independently (each owns its own query). Fix: mark only the rows that read `settings.data` as loading or error, or pass `status: "ready"` once the base `makerspace` prop is available. This is shared with the panel-shell audit.
3. **P2: SMTP and Telegram unsaved edits clobber each other** (row 128). NEW puts ApiClientsTelegramSettings (MakerspaceSettingsPanel.tsx:192) on the same page as MakerspaceEmailSettings. Both read and invalidate `["api-settings", id]`, and each form's `useEffect` re-seeds from `settings.data` (MakerspaceEmailSettings.tsx:64-75; ApiClientsTelegramSettings.tsx:26-32). Fix: give the Telegram card its own key, e.g. `["api-settings", id, "telegram"]`, following the DELIVERY_SETTINGS_KEY pattern (MakerspaceWebhookSettings.tsx:29-33). Use `exact: true` on each form's invalidation, or `setQueryData` from the PATCH response, so a prefix invalidation does not refetch the sibling form.
4. **P2: Remove room is buried with no confirmation** (row 85). OLD `notificationDestinations/DestinationRow.tsx:58-60` was a visible button. NEW `DestinationRow.tsx:48` keeps it in the OverflowMenu (correct per Yuyu for a rare destructive action) but should add `confirm: { title: "Remove room?", message: "Alerts stop reaching this room and its stored webhook URL is discarded; it cannot be shown again.", confirmLabel: "Remove room" }`. Also show `remove.error`, which NotificationDestinations.tsx:43-47 never displays.
5. **P2: Disable kiosk station is buried with no confirmation** (row 43). OLD `KioskStationSettings.tsx:84`, NEW `KioskStationSettings.tsx:91`. Keep it in the OverflowMenu, add `confirm: { title: "Disable station?", message: "The kiosk is locked out until the station is re-enabled with a new PIN." }`. "Reveal PIN" (row 42, NEW :90) is fine in the OverflowMenu as a rare action. Optionally add `confirm:` to "Rotate PIN" (:88), since rotating immediately invalidates the PIN on the device.
6. **P3: The "Telegram test" link is a no-op** (row 101). NEW `IntegrationHealthPanel.tsx:88` links to `settings#integrations`, the current page, and React Router does not scroll to the hash. The Telegram card exists only for superadmins. Fix: pass `isSuperadmin` in and render the link only then, with an onClick that scrolls `#integrations` (or the Telegram card) into view; or drop it.
7. **P3: Stale "above/below" copy after reordering** (rows 86, 129). NotificationDestinations.tsx:78 says "Chat webhooks above" and MakerspaceWebhookSettings.tsx:42 says "matrix below", but NEW puts "Notifications" (:185) before "Email & integrations" (:190). Fix: reword both to name the section ("in Email & integrations", "in Notifications"), or swap the section order to match OLD, where webhooks preceded the channel matrix.
8. **P3: An integration-health error blanks last-known data** (row 99). The `SettingsQueryState` wrapper at IntegrationHealthPanel.tsx:76 turns a failed 60 s background refetch into a full error block. Fix: use status `"error"` only when `!health.data`, and keep the inline ErrorBlock (:85) for refetch failures.
9. **P3: Generic or wrong error copy** (rows 54, 64, 127). Server messages are no longer shown for the mute matrix (NotificationMuteMatrix.tsx:50-56) or channel setup (NotificationChannelPreferences.tsx:76). The recipients error at MakerspaceEmailSettings.tsx:227 says "Couldn't load email"; it should say "notification recipients".
10. **P3, a11y read-out: sr-only table captions dropped** (rows 58, 62). OLD `<caption>` text was at NotificationMuteMatrix.tsx:91-94 and NotificationChannelPreferences.tsx:76-78. NEW DataTable usage (NotificationMuteTable.tsx:8, NotificationChannelPreferences.tsx:77) has no caption, so add an `aria-label` or caption.

---

Scope: staff tabs `emailtemplates`, `email-logs`, `api`. OLD = d3e5ed29, NEW = working tree of feature/design-revamp. Paths are under `frontend/src/features/` unless noted.

## emailtemplates — Email templates (staff/panels/EmailTemplatesPanel.tsx)

Routing and gates are unchanged. `StaffPlatformTabContent.tsx:26` renders the panel with no extra gate in both versions. Tab visibility is still `canEditInventory || canSeePrinting || has("manage_devices")` (`staffAccess.ts:145`), and the server gates each stream.

Structure changed. OLD showed a two-column page: a grouped template list on the left with the editor always open on the right. NEW is a ListLayout (one tab per stream) that drills into a DetailLayout editor at `?template=stream:audience:key`, with Edit, Preview and Default tabs at `?template_view=`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page title "Email templates" | EmailTemplatesPanel.tsx:61 | PRESENT | EmailTemplatesPanel.tsx:69. The header also gains a subtitle. |
| 2 | List query `GET /admin/makerspace/{id}/email-templates` | EmailTemplatesPanel.tsx:16-20 | PRESENT | EmailTemplatesPanel.tsx:19-23 |
| 3 | Loading state | EmailTemplatesPanel.tsx:62-63 | PRESENT | ListLayout `state` at EmailTemplatesPanel.tsx:70 |
| 4 | Error state showing the server message | EmailTemplatesPanel.tsx:64-65 | CHANGED | EmailTemplatesPanel.tsx:70. The server message is replaced by generic copy "Couldn't load email templates", and a Retry is added. |
| 5 | Empty state "No editable email templates are available." | EmailTemplatesPanel.tsx:66-67 | PRESENT | EmailTemplatesPanel.tsx:71 |
| 6 | Templates grouped by stream (eyebrow heading) | EmailTemplatesPanel.tsx:97-101 | PRESENT | Now one tab per stream with counts, plus an "All templates" tab (EmailTemplatesPanel.tsx:72-73). |
| 7 | Audience sub-heading inside a stream | EmailTemplatesPanel.tsx:102-106 | PRESENT | "To {audience}" h2 at EmailTemplatesPanel.tsx:75 |
| 8 | Template row button (label) that selects the template | EmailTemplatesPanel.tsx:123-143 | PRESENT | ListRow at EmailTemplatesPanel.tsx:76-79. It now navigates to the detail view, and the meta line gains "Sent when …". |
| 9 | "Edited" badge when the template or any machine-type override is edited | EmailTemplatesPanel.tsx:141 | PRESENT | StatusPill at EmailTemplatesPanel.tsx:78. The tone is warn only when the base template is overridden; a type-only override shows a neutral "Edited". |
| 10 | List and editor visible side by side, with the selected row highlighted | EmailTemplatesPanel.tsx:69-79, 134 | CHANGED | List and editor are separate views. You return through the back link "All templates" (EmailTemplateEditor.tsx:159) and lose the at-a-glance switching between templates. |
| 11 | Auto-select the first template and keep the selection valid after refetch | EmailTemplatesPanel.tsx:23-56 | PRESENT | EmailTemplatesPanel.tsx:25-63, plus deep-link support. |
| 12 | Machine-type selector: "Space default" option (gate `canEditSpaceDefault`) | EmailTemplateTypeSelector.tsx:25-27 | PRESENT | SegmentedControl at EmailTemplateTypeSelector.tsx:20-22 |
| 13 | Machine-type selector: one option per overridable type, with an Edited marker | EmailTemplateTypeSelector.tsx:28-36, 60 | PRESENT | " · Edited" text suffix at EmailTemplateTypeSelector.tsx:21 |
| 14 | Detail query `GET …/email-templates/{stream}/{audience}/{key}[/types/{id}]` | EmailTemplateEditor.tsx:71-74, 285-288 | PRESENT | EmailTemplateEditor.tsx:70-73, 178-181 |
| 15 | Detail loading and error (server message), with the form hidden until loaded | EmailTemplateEditor.tsx:156-158 | CHANGED | DetailLayout `state` at EmailTemplateEditor.tsx:162 shows generic error copy. The header actions stay live while loading or errored (see #21). |
| 16 | Template title (`detail.label`) | EmailTemplateEditor.tsx:214 | PRESENT | DetailLayout title at EmailTemplateEditor.tsx:159. Stream and audience are added as meta (line 161). |
| 17 | "Custom"/"Default" badge reflecting `is_active` (whether the custom template is in use) | EmailTemplateEditor.tsx:215 | CHANGED | The header status at EmailTemplateEditor.tsx:160 shows Edited/Default from `is_overridden`. The active-custom badge is gone; only the checkbox (#20) shows it. |
| 18 | "Edited" badge in the editor | EmailTemplateEditor.tsx:216 | PRESENT | EmailTemplateEditor.tsx:160 |
| 19 | Template description | EmailTemplateEditor.tsx:218 | PRESENT | EmailTemplateEditorParts.tsx:6, Edit tab only |
| 20 | "Use custom template" checkbox (`is_active`) and its help text | EmailTemplateEditor.tsx:220-226 | PRESENT | EmailTemplateEditorParts.tsx:7-12, Edit tab |
| 21 | Save, `PATCH {path}` with the draft | EmailTemplateEditor.tsx:120-130, 168-171, 187 | CHANGED | Header primary at EmailTemplateEditor.tsx:163, plus a dirty-only SettingsActions at line 171. **Regression:** the header Save renders even while `detail` is loading or errored, because PageHeader sits outside QueryContent (layouts/DetailLayout.tsx). Clicking it then PATCHes `emptyDraft` (blank subject and bodies, `is_active: true`), or the previous machine type's draft right after switching type. OLD returned early and never rendered Save without `detail.data`. Enter-to-submit from the form is also gone. |
| 22 | Subject input (tracks focus for merge-field insertion) | EmailTemplateEditor.tsx:173-176 | PRESENT | EmailTemplateEditor.tsx:151-152, Edit tab |
| 23 | Merge-field buttons (insert `{{ name }}` at the caret; tooltip shows the description) | EmailTemplateEditor.tsx:141-154, 231-244 | PRESENT | Aside at EmailTemplateEditor.tsx:172 and EmailTemplateEditorParts.tsx:16-29. Shown on the Edit tab only. |
| 24 | Plain text body textarea | EmailTemplateEditor.tsx:178-181 | PRESENT | EmailTemplateEditor.tsx:153-154. Monospace font dropped (cosmetic). |
| 25 | HTML body textarea | EmailTemplateEditor.tsx:182-185 | PRESENT | EmailTemplateEditor.tsx:155-156. Monospace font dropped. |
| 26 | Reset to built-in default / Fall back to space default, `POST {path}/reset` | EmailTemplateEditor.tsx:131-139, 188-190 | BURIED | Header OverflowMenu at EmailTemplateEditor.tsx:165. Uses `confirms: true` (ellipsis only), but onClick opens the component's own ConfirmDialog, so the confirmation is real. The "Resetting..." pending label is lost; the item is only disabled. |
| 27 | Reset confirmation dialog (danger tone, override-aware message) | EmailTemplateEditor.tsx:196-202 | PRESENT | EmailTemplateEditor.tsx:173-174 |
| 28 | View/Hide default toggle | EmailTemplateEditor.tsx:191 | BURIED | "Default" tab at EmailTemplateEditor.tsx:166, 169 |
| 29 | Default reference: subject and plain text, with a type-aware heading | EmailTemplateEditor.tsx:246-263 | PRESENT | EmailTemplateEditorParts.tsx:31-48, Default tab. `default_html` is not shown in either version. |
| 30 | Live preview, `POST …/email-templates/preview`, 400 ms debounce, visible under the editor while typing | EmailTemplateEditor.tsx:85-114, 204 | BURIED | "Preview" tab, also reachable from the header secondary "Preview" (EmailTemplateEditor.tsx:164, 169). You can no longer see the rendered result while editing. |
| 31 | Preview: subject, plain text, sandboxed HTML iframe | EmailTemplateEditor.tsx:265-283 | PRESENT | EmailTemplateEditorParts.tsx:50-69 |
| 32 | Preview "Rendering..." indicator | EmailTemplateEditor.tsx:270 | PRESENT | EmailTemplateEditorParts.tsx:51, 57 (skeleton on first load) |
| 33 | Preview error with the server message | EmailTemplateEditor.tsx:272 | CHANGED | EmailTemplateEditorParts.tsx:52 replaces the server message with generic copy (it keeps Retry), so template-syntax errors from the renderer are no longer shown. |
| 34 | Save and reset error messages | EmailTemplateEditor.tsx:193-194 | PRESENT | EmailTemplateEditor.tsx:170 |
| 35 | Send test email, delete template, locale | — | N/A | None of these existed in OLD, so there is nothing to restore. Enable/disable is #20. |

## email-logs — Delivery logs (staff/panels/DeliveryLogPanel.tsx → notifications/DeliveryLogScreen.tsx)

Routing is unchanged. The `EmailLogPanel` lazy loader (`StaffTabLoaders.tsx:32`) loads **DeliveryLogPanel**, which renders `DeliveryLogScreen`. The gate is still `activeTab === "email-logs" && canManageMakerspace` (`StaffPlatformTabContent.tsx:29`, `staffAccess.ts:146`).

`staff/panels/EmailLogPanel.tsx` was orphaned in OLD too: it was exported only through the `StaffPanels.tsx:5` barrel and rendered only by its test. Its content therefore counts as N/A, not a loss.

`PersonalInbox.tsx` contributes only the `Page` type here. It is rendered by the inbox tab and by MemberNotifications, outside this scope.

Structure changed. OLD had a single scroll: a filter grid, a test-send row, the delivery list, and then the SuppressionAdmin section. NEW is a ListLayout with two tabs (`?delivery_view=deliveries|suppression`). Filters sit in the FilterPopover, Send test is the header primary (modal), and suppression is the second tab.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Title "Delivery logs" | DeliveryLogScreen.tsx:38 | PRESENT | DeliveryLogScreen.tsx:62 |
| 2 | Explainer "Pending and sending rows are in flight; failed rows can be retried." | DeliveryLogScreen.tsx:39 | CHANGED | Replaced by a generic subtitle (DeliveryLogScreen.tsx:62). The in-flight and retry semantics are no longer explained. |
| 3 | Delivery query `GET /integrations/makerspace/{id}/delivery-logs?…`, refetched every 30 s | DeliveryLogScreen.tsx:23-24 | PRESENT | DeliveryLogScreen.tsx:44-45 |
| 4 | Channel filter (email, telegram, slack, mattermost, discord, webhook, native_push) | DeliveryLogScreen.tsx:41-43 | BURIED | Inside the closed FilterPopover, `filters.controls` (DeliveryLogScreen.tsx:80-82) |
| 5 | Status filter (pending, sending, sent, failed, skipped) | DeliveryLogScreen.tsx:44-46 | BURIED | SegmentedControl inside the popover (DeliveryLogScreen.tsx:78). The failure callout's "Show failed" also sets it (line 67). |
| 6 | Destination filter (list from `GET /admin/makerspace/{id}/notification-destinations`) | DeliveryLogScreen.tsx:25-26, 47-49 | BURIED | Popover (DeliveryLogScreen.tsx:83-85). Destination loading and error states are added (line 60-61). |
| 7 | Family filter (11 feature families) | DeliveryLogScreen.tsx:50-52 | BURIED | Popover (DeliveryLogScreen.tsx:86-88), with humanized labels |
| 8 | Event free-text filter (maxLength 64) | DeliveryLogScreen.tsx:53 | BURIED | Popover (DeliveryLogScreen.tsx:89) |
| 9 | Active filters visible at a glance | DeliveryLogScreen.tsx:40-54 (all inline) | CHANGED | `filters` is passed without `activeCount`, `chips` or `onClear` (DeliveryLogScreen.tsx:77-91). The closed popover therefore shows no count, and there are no removable chips. "Clear filters" exists only in the filtered-empty state (line 75-76). |
| 10 | Test target select ("Email to my account" or an active destination) | DeliveryLogScreen.tsx:56-58 | BURIED | Inside the "Send test" modal (DeliveryLogScreen.tsx:57-59, 104-109) |
| 11 | Send test, `POST /integrations/makerspace/{id}/delivery-test` | DeliveryLogScreen.tsx:31-33, 59 | PRESENT | Header primary opens the modal (DeliveryLogScreen.tsx:63-64, 52-54) |
| 12 | Test result line "Test {kind} #{id}: {status}…" | DeliveryLogScreen.tsx:60 | PRESENT | Toast (line 54) plus a status line with a "View in log" link (line 101) |
| 13 | Combined error alert (logs, retry, test, destinations) | DeliveryLogScreen.tsx:35, 62 | PRESENT | Split across: logs error in the ListLayout state (line 71-72), retry and test errors (line 102), destination error (line 61), and the test error inside the modal (line 106) |
| 14 | Loading state | DeliveryLogScreen.tsx:63 | PRESENT | DeliveryLogScreen.tsx:71 |
| 15 | Empty "No deliveries match these filters." | DeliveryLogScreen.tsx:64 | PRESENT | Unfiltered and filtered empties (DeliveryLogScreen.tsx:73-76) |
| 16 | Row: channel name | DeliveryLogScreen.tsx:66 | MISSING | The row title is now family · event (line 93). The channel appears only as an icon, ArrowUpRight for email and Info for every other channel (line 94). Telegram, Slack, Discord, Webhook and push rows look the same. |
| 17 | Row: destination label, or "Personal devices" | DeliveryLogScreen.tsx:66 | PRESENT | DeliveryLogScreen.tsx:95 |
| 18 | Row: status | DeliveryLogScreen.tsx:66 | PRESENT | StatusPill (DeliveryLogScreen.tsx:97) |
| 19 | Row: feature.event | DeliveryLogScreen.tsx:67 | PRESENT | Humanized title (DeliveryLogScreen.tsx:93) |
| 20 | Row: created timestamp (absolute) | DeliveryLogScreen.tsx:67 | PRESENT | RelativeTime, with the absolute time in a tooltip (DeliveryLogScreen.tsx:95) |
| 21 | Row: attempt count | DeliveryLogScreen.tsx:67 | PRESENT | DeliveryLogScreen.tsx:95 |
| 22 | Row: error text | DeliveryLogScreen.tsx:68 | PRESENT | DeliveryLogScreen.tsx:96 |
| 23 | Retry failed delivery, `POST …/delivery-logs/{kind}/{id}/retry` with `{generation}` (failed rows only) | DeliveryLogScreen.tsx:28-30, 69 | PRESENT | Row button "Retry" (aria-label "Retry failed delivery") at DeliveryLogScreen.tsx:98 |
| 24 | Pagination (Previous / Next) and "Page N · count deliveries" | DeliveryLogScreen.tsx:71-75 | PRESENT | `pagination` with pageSize 24 (line 99); the count shows as the Deliveries tab badge (line 68) |
| 25 | Failure summary callout (new) | — | N/A | Added at DeliveryLogScreen.tsx:65-67 |
| 26 | Email suppression section shown under the log | DeliveryLogScreen.tsx:77 | BURIED | "Suppressed addresses" tab (DeliveryLogScreen.tsx:69, 92) |
| 27 | Suppression explainer (hashes, stops all mail including retries) | SuppressionAdmin.tsx:22-23 | PRESENT | SuppressionAdmin.tsx:35. The "remove only after resolving" advice moved into the remove confirmation (line 49). |
| 28 | Suppression list `GET /integrations/makerspace/{id}/email-suppressions?page=` | SuppressionAdmin.tsx:15 | PRESENT | SuppressionAdmin.tsx:18 |
| 29 | Add form field: Email address (type email, maxLength 254, required) | SuppressionAdmin.tsx:25 | BURIED | Modal opened by the header primary "Suppress an address", shown only on the suppression tab (DeliveryLogScreen.tsx:63; SuppressionAdmin.tsx:28, 46-48) |
| 30 | Add form field: Reason (Hard bounce / Spam complaint) | SuppressionAdmin.tsx:26 | BURIED | Same modal (SuppressionAdmin.tsx:29) |
| 31 | "Suppress email" submit, `POST …/email-suppressions` | SuppressionAdmin.tsx:17-18, 27 | BURIED | Same modal (SuppressionAdmin.tsx:20-21, 30). Pending label and inline error added. |
| 32 | Suppression row: reason and date | SuppressionAdmin.tsx:32 | PRESENT | Humanized title plus RelativeTime (SuppressionAdmin.tsx:40-41) |
| 33 | Suppression row: address hash | SuppressionAdmin.tsx:33 | PRESENT | SuppressionAdmin.tsx:41 |
| 34 | Remove suppression, `DELETE …/email-suppressions/{id}` | SuppressionAdmin.tsx:19, 34 | CHANGED | Row button at SuppressionAdmin.tsx:43 now opens a ConfirmDialog (lines 49-50). This is an improvement: OLD had no confirmation. |
| 35 | Suppression pagination (Previous / Next) | SuppressionAdmin.tsx:36-40 | PRESENT | `Pagination` at SuppressionAdmin.tsx:44. totalPages is `count/24`, which assumes the API page size is 24. |
| 36 | Suppression loading and error | SuppressionAdmin.tsx:29-30 | PRESENT | QueryContent with Retry (SuppressionAdmin.tsx:24-25, 39); the remove error is at line 38 |
| 37 | Orphan `panels/EmailLogPanel` (status and recent_days filters, `GET/POST /admin/makerspace/{id}/email-logs[/{id}/retry]`) | EmailLogPanel.tsx:30-151 | N/A | Not rendered in OLD or NEW, so this is not a regression. Related, and also pre-existing: the dashboard deep link `failed_emails → {tab:"email-logs", filters:{status:"failed", recent_days:"7"}}` (`panels/dashboardLinks.ts:15`) lands on DeliveryLogScreen. That screen keeps its filters in local `useState` and ignores the URL, so the link opens unfiltered in both versions. |

## api — API access (staff/ApiClientsPanel.tsx)

Routing is unchanged (`StaffPlatformTabContent.tsx:10-17`). The tab renders with no gate in the router; the component switches on `canManageMakerspace` (manager: create and list clients; non-manager: request access and list own requests) and on `isSuperadmin` (api-settings query, origins read-out, Telegram card). Query gates are unchanged: requests when `!canManageMakerspace`, clients and scopes when `canManageMakerspace`, settings when `isSuperadmin`.

Structure changed. OLD used a two-column Panel (create card plus Telegram card on the left; access summary plus client list on the right). NEW is a SettingsLayout with three stacked sections: "New API client" (or "Request API access"), "Clients" (or "Your requests"), and "Developer reference". **ApiClientsTelegramSettings is no longer on this tab.**

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page title "API access" | ApiClientsPanel.tsx:129 | PRESENT | SettingsLayout header at ApiClientsPanel.tsx:125, with a subtitle added |
| 2 | Create-client card heading "API clients" (manager) | ApiClientCreateCard.tsx:50 | PRESENT | Section title "New API client" (ApiClientsPanel.tsx:126) |
| 3 | Create field: Client label | ApiClientCreateCard.tsx:52-58 | PRESENT | ApiClientCreateCard.tsx:52-58 |
| 4 | Create field: Allowed browser origins (textarea, one per line, placeholder example) | ApiClientCreateCard.tsx:59-66 | PRESENT | ApiClientCreateCard.tsx:59-66 |
| 5 | Create field: Scopes picker (grouped checkboxes with label, description, lock reason; non-grantable disabled), from `GET …/api-client-scopes` | ApiClientCreateCard.tsx:67-80; ApiClientScopePicker.tsx:32-60 | PRESENT | ApiClientCreateCard.tsx:67-80. The picker is restyled as cards and now also shows the raw scope value (ApiClientScopePicker.tsx:46). |
| 6 | Scopes loading and error | ApiClientCreateCard.tsx:70, 79 | PRESENT | Skeleton, and ErrorBlock with Retry (ApiClientCreateCard.tsx:70, 79) |
| 7 | "Create API client", `createApiClient` (label, origins, grantable scopes); disabled until label, origins and scopes are set | ApiClientsPanel.tsx:78-92; ApiClientCreateCard.tsx:82-88 | PRESENT | ApiClientsPanel.tsx:76-90; ApiClientCreateCard.tsx:82-88 |
| 8 | Create error | ApiClientCreateCard.tsx:89 | PRESENT | ApiClientCreateCard.tsx:89 |
| 9 | One-time secret reveal ("Copy this secret now — it will not be shown again") after create | ApiClientCreateCard.tsx:90-95 | PRESENT | ApiClientCreateCard.tsx:90-95, with a warn Callout |
| 10 | One-time secret reveal after **rotate** | ApiClientsPanel.tsx:99-105 → ApiClientCreateCard.tsx:90 | CHANGED | Still rendered in the create section (ApiClientCreateCard.tsx:90). OLD's side-by-side layout kept it in view next to the list. NEW stacks the create section above "Clients", so rotating a client lower in the list reveals the secret off-screen with no scroll or focus. Easy to miss a show-once secret. |
| 11 | Copy secret button (clipboard) | ApiClientCreateCard.tsx:97-103 | PRESENT | ApiClientCreateCard.tsx:97-103 |
| 12 | "Done" (dismiss the secret) | ApiClientCreateCard.tsx:104-106 | PRESENT | ApiClientCreateCard.tsx:104-106 |
| 13 | Request form (non-manager) heading "Request API access" | ApiClientCreateCard.tsx:116 | PRESENT | Section title (ApiClientsPanel.tsx:126) |
| 14 | Request field: Request label | ApiClientCreateCard.tsx:118-124 | PRESENT | ApiClientCreateCard.tsx:116-122 |
| 15 | Request field: Reason for API access | ApiClientCreateCard.tsx:125-131 | PRESENT | ApiClientCreateCard.tsx:123-129 |
| 16 | Request field: Allowed browser origins | ApiClientCreateCard.tsx:132-139 | PRESENT | ApiClientCreateCard.tsx:130-137 |
| 17 | "Submit API access request", `requestApiKey`, with validation | ApiClientsPanel.tsx:68-77; ApiClientCreateCard.tsx:141-147 | PRESENT | ApiClientsPanel.tsx:66-75; ApiClientCreateCard.tsx:139-145 |
| 18 | "Request submitted…" confirmation and request error | ApiClientCreateCard.tsx:148-153 | PRESENT | ApiClientCreateCard.tsx:146-151 |
| 19 | Telegram card: group chat ID field (gate `isSuperadmin`) | ApiClientsPanel.tsx:153; ApiClientsTelegramSettings.tsx:79-87 | CHANGED | Moved to the Settings tab, section "Email & integrations" (MakerspaceSettingsPanel.tsx:192, same `isSuperadmin` gate; ApiClientsTelegramSettings.tsx:73-81). It no longer appears on the API tab. |
| 20 | Telegram card: bot token field (password, "token set" placeholder) | ApiClientsTelegramSettings.tsx:88-98 | CHANGED | Moved with #19 (ApiClientsTelegramSettings.tsx:82-92). A "Token saved" / "No token saved" pill is added (line 71). |
| 21 | Telegram: "Save integration settings", `PATCH …/api-settings` | ApiClientsTelegramSettings.tsx:38-51, 101-107 | CHANGED | Moved. Now a dirty-only SettingsActions (ApiClientsTelegramSettings.tsx:94-96). |
| 22 | Telegram: "Clear Telegram token", `PATCH {telegram_bot_token:""}` | ApiClientsTelegramSettings.tsx:53-63, 108-115 | CHANGED | Moved. Now a DangerZone action (line 115-116) that opens its own ConfirmDialog (line 117-118). OLD had no confirmation. |
| 23 | Telegram: "Send Telegram test alert", `POST /integrations/telegram/test-alert`, plus the delivered yes/no result | ApiClientsTelegramSettings.tsx:64-73, 117-134 | CHANGED | Moved (ApiClientsTelegramSettings.tsx:97-114) |
| 24 | Access summary heading "Makerspace API access" | ApiClientsAccessSummary.tsx:19 | PRESENT | KeyValueCard title in the "Developer reference" section (ApiClientsAccessSummary.tsx:22; ApiClientsPanel.tsx:172) |
| 25 | Makerspace code read-out (`settings.public_code ?? makerspace.public_code`) | ApiClientsAccessSummary.tsx:20 | PRESENT | ApiClientsAccessSummary.tsx:23 |
| 26 | Allowed browser origins read-out (superadmin: CORS list or "No active client origins"; otherwise "Managed by superadmin") | ApiClientsAccessSummary.tsx:21-28 | PRESENT | ApiClientsAccessSummary.tsx:24. A loading and error wrapper and a "keep keys in a secret manager" Callout are added. |
| 27 | Client list heading "Existing clients" and loading state | ApiClientListCard.tsx:53-54 | PRESENT | Section "Clients" with QueryContent (ApiClientsPanel.tsx:148; ApiClientListCard.tsx:62) |
| 28 | Client row: label | ApiClientListCard.tsx:144 | PRESENT | ListRow title (ApiClientListCard.tsx:111) |
| 29 | Client row: client_id | ApiClientListCard.tsx:144 | PRESENT | ApiClientListCard.tsx:112 |
| 30 | Client row: Active / Inactive badge | ApiClientListCard.tsx:145 | PRESENT | StatusPill (ApiClientListCard.tsx:115). Inactive is now neutral instead of warn. |
| 31 | Client row: allowed origins, or "No browser origins configured." | ApiClientListCard.tsx:147 | PRESENT | ApiClientListCard.tsx:113 (the "Origins:" prefix is dropped) |
| 32 | Client row: full scope list "Scopes: a, b, c" | ApiClientListCard.tsx:148 | BURIED | The row shows only a count, "{n} scopes" (ApiClientListCard.tsx:116). The individual scopes are visible only as checked boxes in the "Edit scopes" drawer. |
| 33 | Client row: Legacy v1 warning (client holds `legacy:v1`) | ApiClientListCard.tsx:149 | BURIED | Callout appears only inside the Edit scopes drawer (ApiClientListCard.tsx:127). Nothing on the row flags a legacy client. |
| 34 | Client row: created date | ApiClientListCard.tsx:153 | PRESENT | RelativeTime with tooltip (ApiClientListCard.tsx:114) |
| 35 | Client row: last used (`last_seen_at`) or "never used" | ApiClientListCard.tsx:153 | PRESENT | ApiClientListCard.tsx:114 |
| 36 | Inline per-row scope picker (client-type-filtered options) | ApiClientListCard.tsx:150-151 | BURIED | "Edit scopes" row button opens a DetailLayout drawer (ApiClientListCard.tsx:117, 122-129) |
| 37 | "Save scopes", `updateApiClientScopes`; disabled unless grantable and changed | ApiClientsPanel.tsx:106-113; ApiClientListCard.tsx:155 | BURIED | Drawer footer primary (ApiClientListCard.tsx:125-126), with Discard added |
| 38 | "Rotate secret", `rotateApiClient` | ApiClientsPanel.tsx:99-105; ApiClientListCard.tsx:156 | BURIED | Row OverflowMenu (ApiClientListCard.tsx:119). Uses `confirms: true` (ellipsis only), but onClick opens the component's own ConfirmDialog (lines 130-134), so the confirmation is real and new. See #10 for where the secret appears. |
| 39 | "Delete", `deleteApiClient` | ApiClientsPanel.tsx:93-98; ApiClientListCard.tsx:157 | BURIED | Row OverflowMenu with danger tone (ApiClientListCard.tsx:120). Its own ConfirmDialog "Delete API client?" (lines 130-134) is new; OLD deleted on one click. |
| 40 | Errors: clients, scopes, scope update, delete, rotate | ApiClientListCard.tsx:74-78 | PRESENT | QueryContent with Retry (line 62); other errors as ErrorBlocks (lines 59, 68); update and scopes errors also inside the drawer (line 129) |
| 41 | Empty "No API clients yet." | ApiClientListCard.tsx:71-73 | PRESENT | EmptyState (ApiClientListCard.tsx:66) |
| 42 | Requests list (non-manager), `GET /admin/api-key-requests?makerspace=`: label, date, status, resolution note | ApiClientsPanel.tsx:43-47; ApiClientListCard.tsx:86-104 | PRESENT | ListRow (ApiClientListCard.tsx:71-73). Requests loading and error are added. |
| 43 | Empty "No API access requests yet." | ApiClientListCard.tsx:106-110 | PRESENT | ApiClientListCard.tsx:74 |

### Counts

| Page | PRESENT | BURIED | CHANGED | MISSING | Total |
|---|---|---|---|---|---|
| emailtemplates | 25 | 3 | 6 | 0 | 34 (+1 N/A) |
| email-logs | 21 | 10 | 3 | 1 | 35 (+2 N/A) |
| api | 31 | 6 | 6 | 0 | 43 |
| **Total** | **77** | **19** | **15** | **1** | **112 (+3 N/A)** |

### Restore candidates

1. **P0, email template Save is live while the detail is loading or errored.** NEW: `staff/panels/EmailTemplateEditor.tsx:163`. The header-primary Save calls `save.mutate()`, and `save` PATCHes `draft` (EmailTemplateEditor.tsx:114-116). Before `detail.data` arrives, `draft` is `emptyDraft` (blank subject and bodies). Right after a machine-type switch, `draft` still holds the previous type's content. OLD never rendered Save without `detail.data` (old EmailTemplateEditor.tsx:156-158). Fix: in the `actions.primary` slot of the same DetailLayout, set `disabled: !detail.data || detail.isFetching && !dirty` with a `disabledReason`, or omit the primary until `detail.data` exists. Also guard `save.mutationFn` on `detail.data`.
2. **P1, show-once API secret after rotate can appear off-screen.** OLD: ApiClientsPanel.tsx:99-105 sets `oneTimeSecret` and ApiClientCreateCard.tsx:90-109 shows it. Old ApiClientsPanel.tsx:130 kept that column beside the list. NEW: the reveal stays in the "New API client" section above "Clients" (ApiClientCreateCard.tsx:90; ApiClientsPanel.tsx:126-148). Fix: after a rotate, render the reveal next to the affected ListRow, or in a Modal or Callout banner that cannot be missed. Move focus to it, and keep "Copy" and "Done".
3. **P2, the delivery row no longer names its channel.** OLD: notifications/DeliveryLogScreen.tsx:66 (`{row.channel} · …`). NEW: DeliveryLogScreen.tsx:93-95 shows only an email-vs-other icon. Fix: add `words(row.channel)` to the ListRow meta, e.g. "Telegram · {destination} · {attempts} attempts · {time}".
4. **P2, delivery-log filters are buried and active filters are invisible.** OLD: DeliveryLogScreen.tsx:40-54 had all five filters inline. NEW: DeliveryLogScreen.tsx:77-91 puts them in the FilterPopover without `activeCount`, `chips` or `onClear`. Fix: keep the popover but pass `activeCount={Object.values(filters).filter(Boolean).length}`, `chips` (one per non-empty filter, calling `update(key, "")`) and `onClear`. Following Yuyu, also lift the most frequent filter (Status) out as a visible SegmentedControl or tabs in `filters.views`.
5. **P2, live email preview is no longer visible while editing.** OLD: EmailTemplateEditor.tsx:204 always rendered PreviewPane under the form. NEW: Preview tab only (EmailTemplateEditor.tsx:166, 169). Fix: on wide viewports, render `PreviewPane` in the DetailLayout `aside` on the Edit tab below MergeFields (aside at EmailTemplateEditor.tsx:172), or keep a compact rendered-subject read-out. Keep the Preview tab for narrow screens.
6. **P2, the Legacy v1 warning and the full scope list are hidden in the drawer.** OLD: ApiClientListCard.tsx:148-149. NEW: count pill only (ApiClientListCard.tsx:116); the Callout is inside the drawer (line 127). Fix: when `hasLegacy`, add a warn StatusPill "Legacy v1" on the row's `right` slot. Put the scope labels (or the first few plus "+n") in the row `meta`.
7. **P2, the Telegram integration card moved off the API tab.** OLD: ApiClientsPanel.tsx:153 (`isSuperadmin ? <ApiClientsTelegramSettings/>`). NEW: MakerspaceSettingsPanel.tsx:192, in the Settings tab's "Email & integrations" section, with the same gate. It works, but superadmins who used the API tab will not find it there. Optionally add a SettingsRow link "Telegram alerts → Settings › Email & integrations" in the API tab's "Developer reference" section (ApiClientsPanel.tsx:172) when `isSuperadmin`.
8. **P3, generic error copy hides server messages for template load, preview render and the template list.** OLD showed `error.message` (EmailTemplatesPanel.tsx:65, EmailTemplateEditor.tsx:157, 272). NEW: EmailTemplatesPanel.tsx:70, EmailTemplateEditor.tsx:162, EmailTemplateEditorParts.tsx:52. Template-syntax errors returned by the preview endpoint are what authors most need to see. Fix: pass the actual error to `ErrorBlock` in `PreviewPane` (EmailTemplateEditorParts.tsx:52), as SuppressionAdmin and the API cards do.
9. **P3, the "Custom"/"Default" badge for `is_active` is gone.** OLD: EmailTemplateEditor.tsx:215. NEW: the header status shows only Edited/Default from `is_overridden` (EmailTemplateEditor.tsx:160). Fix: add a second StatusPill ("Custom in use" / "Default in use", from `draft.is_active`) in the DetailLayout `status` or `meta`.
10. **P3, the delivery-log explainer copy was dropped.** OLD: DeliveryLogScreen.tsx:39. Fix: restore it as the ListLayout header `subtitle`, or as the description under the Deliveries tab.
11. **P3, template list and editor are no longer side by side.** OLD: EmailTemplatesPanel.tsx:69-79. NEW: list → detail with "All templates" back (EmailTemplateEditor.tsx:159). This is an acceptable Yuyu list→detail pattern. Only consider a next/previous template control if staff edit many templates in one sitting.
12. **Pre-existing, not a regression, P2.** The dashboard deep link `failed_emails` (`panels/dashboardLinks.ts:15`, `status=failed&recent_days=7`) is ignored by DeliveryLogScreen, whose filters are local `useState` (DeliveryLogScreen.tsx:36-37). The orphaned `panels/EmailLogPanel.tsx` is the only component that reads those URL params. Fix: back DeliveryLogScreen's `filters` and `page` with `useUrlListState` (as the old EmailLogPanel.tsx:32 did) so dashboard links land filtered. Then delete or retire the orphaned EmailLogPanel.

---

Scope: staff tabs `exports`, `backups`, `usage`, `migration`, `modules`, `platform`, `platform-dashboard`, `organizations`, `organization-analytics`. OLD = d3e5ed29, NEW = working tree of feature/design-revamp. All paths are under `frontend/src/features/staff/` unless noted.

Confirmation check (per the corrected brief): in this area, every new destructive `DangerZone`/`Action` caller opens its own dialog from `onClick` (`BackupRestoreDialog`, `useMigrationConfirmation`, `ConfirmDialog` in Stripe and org links). None depends on `confirms`, which only adds "…" to the label. No destructive action that had a confirmation in OLD lost it. Two kept their missing confirmation: organization invitation Revoke and disclosure Revoke approval.

## exports — Data export (DataExportsPanel.tsx)
Gate is unchanged: `activeTab === "exports" && canManageMakerspace` (StaffPlatformTabContent.tsx:45 old / :41 new). OLD was a `Panel` with an always-open disclosure, a request button and job cards. NEW is a `ListLayout` with the header primary, a warn banner callout, and `ListRow`s. The full disclosure is collapsed by default.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page heading "Makerspace data export" | DataExportsPanel.tsx:40 | PRESENT | Header title "Data export" + subtitle "…Not a backup." DataExportsPanel.tsx:44 |
| 2 | Disclosure block (3 paragraphs: omitted data, member contact details included, referenced-users id+username disclosure), always visible, headed "Read this disclosure before requesting an export" | DataExportsPanel.tsx:42-61 | BURIED | The banner callout shows only the lead "Exports include member names, emails and phone numbers." The full text is behind the callout action "Read what's included" (DataExportsPanel.tsx:50-51), rendered at :59-79. A user can request an export without ever expanding it |
| 3 | "Request redacted export" button → `requestDataExport` (POST `/admin/makerspace/{id}/data-exports`) | DataExportsPanel.tsx:63-71 | PRESENT | Header primary "Request export" DataExportsPanel.tsx:45-47 |
| 4 | Request disabled while an export is pending/running | DataExportsPanel.tsx:67 | PRESENT | :45-46. Also disabled while the list is loading or errored, with a `disabledReason` |
| 5 | Request error message | DataExportsPanel.tsx:72 | PRESENT | `ErrorText` :80 |
| 6 | Job tracker registration (`trackJob` "Data export") | DataExportsPanel.tsx:24 | PRESENT | :29 |
| 7 | Loading text | DataExportsPanel.tsx:75 | PRESENT | Layout loading state :48 |
| 8 | List load error showing server message | DataExportsPanel.tsx:76 | CHANGED | Generic "Couldn't load exports. Try again." + Retry (adminPresentation.ts:6). Server detail is no longer shown |
| 9 | Empty "No exports have been requested." | DataExportsPanel.tsx:77-79 | PRESENT | `empty` :49 |
| 10 | 1.5 s polling while a job runs | DataExportsPanel.tsx:18-19 | PRESENT | :23-24 |
| 11 | Row title "Redacted export" | DataExportsPanel.tsx:110 | PRESENT | `ListRow` title "Export" :52 |
| 12 | Row created timestamp (absolute) | DataExportsPanel.tsx:112 | PRESENT | `RelativeTime` + date identity :52-53 |
| 13 | Row status label (Queued / Building snapshot / Ready to download / Failed / Deadline exceeded) | DataExportsPanel.tsx:112,135-138 | PRESENT | `StatusPill` :53, labels :89-93 ("Ready") |
| 14 | Row total row count | DataExportsPanel.tsx:113 | PRESENT | :54 |
| 15 | "Download archive" on available rows → `issueDataExportDownload` | DataExportsPanel.tsx:116-120 | PRESENT | Row right button "Download" :56-58 |
| 16 | Failure detail on failed rows (`failure_detail`) | DataExportsPanel.tsx:122-126 | CHANGED | :55. For `deadline_exceeded`, fixed copy replaces the server `failure_detail` |
| 17 | Download error | DataExportsPanel.tsx:90 | PRESENT | :81 |

## backups — Backup & restore (BackupRestorePanel.tsx)
Gate is unchanged: `activeTab === "backups" && canManageMakerspace`, with `isSuperadmin` and `tenantBackupsEnabled = enabled_modules.includes("backup")` passed through (StaffPlatformTabContent.tsx:48-49 old / :44-45 new). OLD stacked two `Panel`s. NEW is a `SettingsLayout` with sections "This space" and "Deployment" (superadmin only), plus a superadmin `DangerZone` "Restore from a backup…". In OLD, restore was two buttons on each deployment archive row. In NEW it is a `BackupRestoreDialog` with archive select, kind select and type-"deployment" confirmation. Schedule moved to `BackupScheduleSettings.tsx` and archive rows to `BackupArchiveRows.tsx`. `RestoreDecision` is now its own file.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | "Makerspace backups" section, gated `tenantBackupsEnabled` | BackupRestorePanel.tsx:39-45 | PRESENT | Section "This space" BackupRestorePanel.tsx:54-58 |
| 2 | Not-installed note when backup module is off | BackupRestorePanel.tsx:46 | PRESENT | :58 |
| 3 | Archive disclosure (tenant and deployment variants), warn-toned box | BackupRestorePanel.tsx:41,51,75-77 | CHANGED | Same text, now a neutral surface box (BackupArchiveRows.tsx:4-6), used at BackupRestorePanel.tsx:55,60. The warning is less prominent |
| 4 | "Create makerspace archive" → `requestTenantBackup` | BackupRestorePanel.tsx:42 | PRESENT | Header primary :48-49 |
| 5 | Archive rows: scope label, date, status, size, failure detail | BackupRestorePanel.tsx:79-88 | PRESENT | BackupArchiveRows.tsx:7-13 (relative time, status pill) |
| 6 | Download on available archive → `issueBackupDownload` | BackupRestorePanel.tsx:84 | PRESENT | BackupArchiveRows.tsx:12 (per-row pending) |
| 7 | Empty "No backup archives yet." | BackupRestorePanel.tsx:80 | PRESENT | BackupArchiveRows.tsx:8 |
| 8 | 2 s polling while an archive is pending/running/promoting | BackupRestorePanel.tsx:97 | PRESENT | BackupRestorePanel.tsx:83 |
| 9 | "Deployment backup and restore" section, gated `isSuperadmin` | BackupRestorePanel.tsx:48-67 | PRESENT | Section "Deployment" :59-70 |
| 10 | Daily automatic deployment backup checkbox → `updateBackupSettings({automatic_backups_enabled})` | BackupRestorePanel.tsx:52-55 | PRESENT | `SettingsRow` "Daily full backup" switch, BackupScheduleSettings.tsx:10-11. Saves immediately; new toast |
| 11 | "Last successful archive" read-out | BackupRestorePanel.tsx:56 | PRESENT | BackupScheduleSettings.tsx:12 |
| 12 | Archive retention (days) number 1-3650, saved on blur (fallback 30) | BackupRestorePanel.tsx:57-60 | CHANGED | `SettingsRow` "Keep archives for" + explicit Save/Discard `SettingsActions` with 1-3650 integer validation, BackupScheduleSettings.tsx:14-17. Safer than the silent blur save |
| 13 | Settings `last_error` read-out | BackupRestorePanel.tsx:61 | PRESENT | BackupScheduleSettings.tsx:16 |
| 14 | "Create full deployment archive" → `requestDeploymentBackup` | BackupRestorePanel.tsx:62 | PRESENT | Inline button :63 when tenant backups are on; otherwise header primary :50 |
| 15 | Deployment archive rows + Download | BackupRestorePanel.tsx:63 | PRESENT | :64 |
| 16 | Per-row "Rollback here" → `requestRestore(id,"rollback_in_place")`, no confirmation | BackupRestorePanel.tsx:84 | CHANGED | Moved off the row. `DangerZone` "Restore from a backup…" :72-73 opens `BackupRestoreDialog` (archive select, "Roll back in place" kind, type `deployment`), BackupRestoreDialog.tsx:13-23. Disabled when no available deployment archive. Stronger confirmation, one more step |
| 17 | Per-row "Disaster restore" → `requestRestore(id,"disaster")`, no confirmation | BackupRestorePanel.tsx:84 | CHANGED | Same dialog, kind "Disaster recovery" BackupRestoreDialog.tsx:17 |
| 18 | Active restore detection + 3 s list / 1 s detail polling | BackupRestorePanel.tsx:27-29 | PRESENT | :37-39 |
| 19 | Restore review: stage, tables compared/differ, per-table `<details>` with live/archived counts, security-relevant/noisy flags, row-diff JSON | BackupRestorePanel.tsx:90-93 | PRESENT | RestoreDecision.tsx:11-21. Also now shows `error_detail` (:31) |
| 20 | Decision window countdown + Proceed / Proceed and reset authority / Abort safely → `decideRestore` | BackupRestorePanel.tsx:93 | PRESENT | RestoreDecision.tsx:22-30. Now disabled while pending; still no extra confirmation (same as OLD) |
| 21 | Single combined error "A backup operation failed. Refresh for the persisted status." | BackupRestorePanel.tsx:68-70 | CHANGED | Per-operation `ErrorText` with server messages and retries, :57,62,65,67-69,71 |
| 22 | Job tracker for tenant/deployment backups | BackupRestorePanel.tsx:30-31 | PRESENT | :40-41 |

## usage — Usage & limits (TenantUsagePanel.tsx)
Gate is unchanged: `activeTab === "usage" && canManageMakerspace`. OLD was a `Panel` with a table. NEW is a `DashboardLayout` with one main section that defaults to cards and has a "Show as table" toggle. `UsageTable` is still exported and still reused by the platform dashboard.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Title "Usage · {makerspace}" | TenantUsagePanel.tsx:26 | PRESENT | Title "Usage & limits", eyebrow = makerspace name, TenantUsagePanel.tsx:25 |
| 2 | Description (counts/allowances; quota reset) | TenantUsagePanel.tsx:28 | PRESENT | Subtitle :26 (first clause dropped) |
| 3 | "Refresh usage" button (`refetch`) | TenantUsagePanel.tsx:29 | PRESENT | Header secondary :27 |
| 4 | 60 s auto-refresh | TenantUsagePanel.tsx:25 | PRESENT | :24 |
| 5 | Loading status | TenantUsagePanel.tsx:31 | PRESENT | Layout state :28 |
| 6 | Error with server message | TenantUsagePanel.tsx:32 | CHANGED | Generic "Couldn't load usage. Try again." + Retry |
| 7 | Self-hosted "no managed limits" note | TenantUsagePanel.tsx:34 | PRESENT | :33 |
| 8 | Usage table: Resource / Used / Limit (or Unlimited) / Allowance used % / "Over limit" | TenantUsagePanel.tsx:6-22,35 | PRESENT | Default card view shows the same data (used of limit, % with progress bar, Over/Near limit pill) :34-45. The table is available via the section action "Show as table" :31, `UsageTable` :9-20 |
| 9 | `UsageTable` reused by platform dashboard | TenantUsagePanel.tsx:6 | PRESENT | Exported :9, used PlatformDashboardPanel.tsx:38 |

## migration — Tenant migration (TenantMigrationPanel.tsx)
Gate is unchanged: `activeTab === "migration" && isSuperadmin`. OLD was one page with four sections stacked and always visible: Disclosure, Exports (incl. cutover), Pairings, Imports. NEW is a `FlowLayout` with 6 local steps: 0 disclosure, 1 pin deployments, 2 encrypt export, 3 import & resolve, 4 verify & materialise, 5 cut over. The step lives in `useState(0)` (TenantMigrationPanel.tsx:22). It always opens at step 0, is not derived from server progress, and has no `onStepSelect`, so steps cannot be clicked. Each child returns `null` when inactive. Typed-name confirmations (MigrationConfirmation.tsx) replace OLD's `window.confirm`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | "Superadmin-only irreversible workflow" warning: workflow summary + "archived, not deleted; outside purge guarantee" | TenantMigrationPanel.tsx:28-38 | PRESENT | `Callout` "This is one-way." TenantMigrationPanel.tsx:29. The workflow summary is now the step list :13-20 |
| 2 | All stages visible at once on one page | TenantMigrationPanel.tsx:39-47 | CHANGED | One stage per step, reached only by Previous/Continue (:38-39). No server-derived resume point and no clickable steps. Cutover needs 5 "Continue" clicks each visit |
| 3 | Pairings loading text | TenantMigrationPanel.tsx:48 | PRESENT | Layout state :26 |
| 4 | Pairings error shown inline while the other sections stay usable | TenantMigrationPanel.tsx:49 | CHANGED | If `listPairings` fails with no cached data, the whole flow becomes an error block (:26). Disclosure, export and import are unreachable until retry |
| 5 | Disclosure heading + APPROVED / REVIEW REQUIRED pill | TenantMigrationDisclosure.tsx:51-58 | PRESENT | Step 1. TenantMigrationDisclosure.tsx:52-59 (pill now sentence case via tenantMigrationUi.tsx:31-37) |
| 6 | Disclosure explanation | TenantMigrationDisclosure.tsx:59-62 | PRESENT | :60-63 |
| 7 | Closure/approvals loading + error | TenantMigrationDisclosure.tsx:64-65 | PRESENT | :65-66 |
| 8 | VOID approvals with previously approved digest | TenantMigrationDisclosure.tsx:66-71 | PRESENT | :67-72 |
| 9 | Exact closure digest | TenantMigrationDisclosure.tsx:75-76 | PRESENT | :76-77 |
| 10 | Per-identity disclose/withhold checkbox (display name, email, phone, first/last, @username, user id, joined, decision label) | TenantMigrationDisclosure.tsx:79-103 | PRESENT | :80-104 |
| 11 | "{n} of {m} identities approved" read-out | TenantMigrationDisclosure.tsx:107 | PRESENT | :108 |
| 12 | "Revoke approval" → `revokeDisclosure` (no confirm) | TenantMigrationDisclosure.tsx:108 | PRESENT | :109 (still no confirm) |
| 13 | Acknowledgement checkbox | TenantMigrationDisclosure.tsx:112-118 | PRESENT | :113-119 |
| 14 | "Approve exact closure" → `approveDisclosure` | TenantMigrationDisclosure.tsx:120-122 | PRESENT | :121-123 |
| 15 | Approve/revoke errors | TenantMigrationDisclosure.tsx:125-126 | PRESENT | :126-127 |
| 16 | This deployment identity card (deployment id, fingerprint, age recipient, read-only identity JSON) | TenantMigrationPairings.tsx:57-67 | PRESENT | Step 2. TenantMigrationPairings.tsx:58-69 |
| 17 | "Use this deployment as source" | TenantMigrationPairings.tsx:66 | PRESENT | :67 |
| 18 | Fields: Migration/import job ID, Source tenant ID, Archive digest | TenantMigrationPairings.tsx:73-75 | PRESENT | :74-76 |
| 19 | Source / Target identity JSON textareas (target prefilled) | TenantMigrationPairings.tsx:78-79 | PRESENT | :79-80 |
| 20 | "Pin this deployment pairing" → `createPairing` + local JSON validation | TenantMigrationPairings.tsx:32-46,81-85 | PRESENT | :32-46,82-86 |
| 21 | Pinned pairings list (id, migration, archive digest, source→target fingerprints) | TenantMigrationPairings.tsx:87-95 | BURIED | Only on step 2 "Pin deployments" :88-97. OLD showed it next to the exports/imports that depend on it |
| 22 | Exports heading + explanation + "archived, not deleted" warning | TenantMigrationExports.tsx:86-95 | PRESENT | Steps 3 and 6. TenantMigrationExports.tsx:94-103 |
| 23 | Approved closure select | TenantMigrationExports.tsx:98-104 | PRESENT | Step 3 only :107-113 |
| 24 | Target age recipient input | TenantMigrationExports.tsx:105-108 | PRESENT | Step 3 only :114-117 |
| 25 | "Create encrypted migration export" → `createMigrationExport` | TenantMigrationExports.tsx:110-113 | PRESENT | Step 3 only :119-122 |
| 26 | Export job list: id, archive digest, status pill, failure, per-job error, retention notice, 1.5 s polling | TenantMigrationExports.tsx:44-52,115-134 | PRESENT | Steps 3 and 6 :51-59,125-144 |
| 27 | "Download one-use archive" → `issueMigrationDownload` | TenantMigrationExports.tsx:138 | PRESENT | Steps 3 and 6 :148 |
| 28 | "Quiesce {tenant}" → `quiesceSource`, `window.confirm` | TenantMigrationExports.tsx:139-141 | CHANGED | Step 6 only, `DangerZone` :150-152 → typed-name confirm dialog (MigrationConfirmation.tsx:10-16). Stronger, but hidden from the export step where the archive becomes available |
| 29 | "Source writes are frozen" status | TenantMigrationExports.tsx:135 | PRESENT | :145 |
| 30 | "Archive source {tenant}" → `archiveSource`, `window.confirm` | TenantMigrationExports.tsx:142-144 | CHANGED | Step 6 only, `DangerZone` :153-155 + typed-name confirm |
| 31 | Pinned pairing id + "Target ABORTED receipt" textarea | TenantMigrationExports.tsx:147-153 | BURIED | Step 6 only :158-164 |
| 32 | "Recover source {tenant}" → `recoverSource`, `window.confirm` | TenantMigrationExports.tsx:154-156 | CHANGED | Step 6 only, `DangerZone` :165-167 + typed-name confirm; disabled reason when the receipt is invalid |
| 33 | Download/quiesce/archive/recover errors | TenantMigrationExports.tsx:163 | PRESENT | :174 |
| 34 | Source cutover receipt output (copy to target) | TenantMigrationExports.tsx:164 | PRESENT | :175 (visible only while on steps 3/6) |
| 35 | Recover success message | TenantMigrationExports.tsx:165 | PRESENT | :176 |
| 36 | Import heading + explanation | TenantMigrationImports.tsx:36-38 | PRESENT | Step 4. TenantMigrationImports.tsx:38-41 |
| 37 | Encrypted archive file + Source archive digest inputs | TenantMigrationImports.tsx:40-41 | PRESENT | Step 4 :43-44 |
| 38 | "Create target import" → `createImport` | TenantMigrationImports.tsx:43-46 | PRESENT | Step 4 :46-49 |
| 39 | Import list loading/error | TenantMigrationImports.tsx:47-48 | CHANGED | Only rendered on step 4 (:50-51). On steps 5-6 a failed `listImports` shows no cards and no error |
| 40 | Import job card: source name, import id, lifecycle pill, IMPORTING/ACTIVE/ABORTED explanations, failure, detail error, retention notice, archived source deployment identity JSON, 1.5 s polling | TenantMigrationImports.tsx:58-136 | PRESENT | Steps 4-6 :62-142 |
| 41 | Per-person identity decisions (awaiting_identity/ready): per identity name/email/phone/source id; Identity resolution select (Create walk-in / Link existing); Target user ID (number, required for link); Membership select (Import / Do not import); "Submit all identity decisions" → `submitIdentityDecisions`; accepted / earlier-session notices | TenantMigrationIdentityDecisions.tsx:21-124 (rendered TenantMigrationImports.tsx:138) | PRESENT | Step 4 only. Rendered as a sibling after the card (TenantMigrationImports.tsx:181); component unchanged except the `active` gate (TenantMigrationIdentityDecisions.tsx:21,48) |
| 42 | Materialize target: Target tenant name / slug (optional), "I reviewed every per-person identity decision shown above" checkbox, "Run reviewed import" → `runImport` | TenantMigrationImports.tsx:139-153 | CHANGED | Step 5 only :144-158. The identity decisions it asks the operator to attest are "shown above" but live on step 4 and are not rendered here |
| 43 | Verification report (target makerspace id, linked / walk-ins / external refs, imported/resolved/dropped JSON) | TenantMigrationImports.tsx:155-157,180-194 | PRESENT | Steps 5-6 :160-162,186-200 |
| 44 | Source cutover receipt textarea | TenantMigrationImports.tsx:162 | BURIED | Step 6 only :167 |
| 45 | "Activate target {name}" → `activateTarget`, `window.confirm`, disabled until receipt + verification | TenantMigrationImports.tsx:164-166 | CHANGED | Step 6 only, `DangerZone` :168-170 + typed-name confirm |
| 46 | "Abort target {name}" → `abortTarget`, `window.confirm` | TenantMigrationImports.tsx:167-169 | CHANGED | Step 6 only, `DangerZone` :171-173 + typed-name confirm |
| 47 | "Pin the matching deployment pairing…" warning | TenantMigrationImports.tsx:173 | PRESENT | :176 (all import phases) |
| 48 | Activate/abort errors | TenantMigrationImports.tsx:174 | PRESENT | :177 |
| 49 | Target abort receipt output (copy to source) | TenantMigrationImports.tsx:175 | PRESENT | :179 |

## modules — Modules (ModulesPanel.tsx)
Gate is unchanged: `activeTab === "modules" && isSuperadmin`. OLD had collapsed group accordions with Install/Uninstall buttons, plus a Deployment panel. NEW is a `SettingsLayout` with one expanded section per group, a `ModuleSettingsRow` switch per module, and a Deployment section. OLD had no purge, capability or feature toggles and no confirmation for install/uninstall. NEW also has none of these and adds an undo toast.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Title + explanation (uninstall keeps data; delete is CLI-only) | ModulesPanel.tsx:78-83 | PRESENT | Header subtitle ModulesPanel.tsx:51 |
| 2 | Loading state | ModulesPanel.tsx:64 | PRESENT | Layout state :52 |
| 3 | Load error with server `detail` | ModulesPanel.tsx:65-71 | CHANGED | Generic "Couldn't load modules. Try again." + Retry |
| 4 | Group list as collapsed accordions (label + description; one open at a time) | ModulesPanel.tsx:88-128 | CHANGED | Every group is an always-expanded `SettingsSection` with description :55-61. Rows are more visible |
| 5 | Group badge: "Always on" for `always_on` groups, else "N of M installed" | ModulesPanel.tsx:103-109 | CHANGED | Title is always "{label} · N of M" (:55). The `always_on` indicator is dropped |
| 6 | Module label + description | ModulesPanel.tsx:178-179 | PRESENT | `SettingsRow` label/helper ModuleSettingsRows.tsx:23 |
| 7 | "Turns on: {workflows}" | ModulesPanel.tsx:180-182 | PRESENT | ModuleSettingsRows.tsx:32 |
| 8 | "Also installs: {pulls_in}" (not installed) | ModulesPanel.tsx:185-187 | PRESENT | ModuleSettingsRows.tsx:33 |
| 9 | "Required by {required_by}" read-out (installed or not) | ModulesPanel.tsx:188-190 | CHANGED | Shown only for installed modules, as "Turn off X first." (ModuleSettingsRows.tsx:20-21,34). Reverse dependencies of uninstalled modules are no longer shown |
| 10 | "Not shipped by this deployment." | ModulesPanel.tsx:191-193 | PRESENT | ModuleSettingsRows.tsx:22,34 (suppressed if the row is also blocked) |
| 11 | "Core" badge for core modules | ModulesPanel.tsx:196-197 | PRESENT | "Always on" pill ModuleSettingsRows.tsx:25 |
| 12 | Uninstall → POST `/admin/makerspace/{id}/modules/uninstall`, disabled when pending or required_by | ModulesPanel.tsx:198-206,47-52 | PRESENT | Switch off, ModuleSettingsRows.tsx:26-31 / ModulesPanel.tsx:28-29. No confirm (same as OLD); new undo toast :44-47 |
| 13 | Install → POST `/modules/install`, disabled when not available | ModulesPanel.tsx:207-215 | PRESENT | Switch on, same location |
| 14 | Invalidate modules / staff makerspaces / report-catalog / operations-report after change | ModulesPanel.tsx:56-61 | PRESENT | ModulesPanel.tsx:20-27 |
| 15 | Change error banner | ModulesPanel.tsx:84-86 | PRESENT | Per-row error :38,60 |
| 16 | One global pending flag locks all rows | ModulesPanel.tsx:120 | CHANGED | Per-module pending :16,33-39 (concurrent changes now possible) |
| 17 | Deployment panel explanation (startup env, restart) | ModulesPanel.tsx:134-139 | PRESENT | ModuleSettingsRows.tsx:41 |
| 18 | Deployment app rows: app_label, note, Shipped/Removed | ModulesPanel.tsx:141-154 | PRESENT | ModuleSettingsRows.tsx:42-44 |
| 19 | Copyable `env_line` | ModulesPanel.tsx:156-158 | PRESENT | ModuleSettingsRows.tsx:45 + new "Copy environment line" :46 |

## platform — Platform settings (OLD PlatformEmailPanel + PlatformSocialAuthPanel + PlatformStripeConnectPanel → NEW PlatformSettingsPanel.tsx)
OLD rendered all three panels stacked; Stripe was shown only when `activeMakerspace.platform_hosting` (StaffPlatformTabContent.tsx:35-41 old). NEW `PlatformSettingsPanel` (StaffPlatformTabContent.tsx:36 new) is a `SettingsLayout` with URL tabs `?section=email|sign-in|stripe`. Only one panel shows at a time; the Stripe tab keeps the same `platform_hosting` gate (PlatformSettingsPanel.tsx:9-11). Each panel runs in `embedded` mode through `PlatformConfigurationSection`. Embedded mode drops each panel's own title and subtitle (PlatformConfigurationSection.tsx:12-16). OLD had no SMTP test send, no per-provider "enabled" switch and no Stripe connect/disconnect flow, so none is expected.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Three panels visible together | StaffPlatformTabContent.tsx:35-41 | CHANGED | One tab per panel, PlatformSettingsPanel.tsx:9-16 (an extra click to reach Sign-in/Stripe) |
| 2 | Email panel title + description ("Instance-wide SMTP for password resets… when a makerspace has no SMTP configured") | PlatformEmailPanel.tsx:74-77 | MISSING | Embedded mode drops title/subtitle (PlatformConfigurationSection.tsx:12). The subtitle passed at PlatformEmailPanel.tsx:69 is never rendered; only the tab label "Email" and the generic page subtitle remain |
| 3 | SMTP configured read-out | PlatformEmailPanel.tsx:78-80 | PRESENT | `StatusPill` PlatformEmailPanel.tsx:73 |
| 4 | SMTP host | PlatformEmailPanel.tsx:84 | PRESENT | `SettingsRow` :75 |
| 5 | SMTP port (numeric, default 587) | PlatformEmailPanel.tsx:85 | PRESENT | :76 |
| 6 | SMTP username | PlatformEmailPanel.tsx:86 | PRESENT | :77 |
| 7 | SMTP password (write-only, "SMTP password set" placeholder) | PlatformEmailPanel.tsx:87 | PRESENT | :78 |
| 8 | From email | PlatformEmailPanel.tsx:88 | PRESENT | :79 |
| 9 | Use STARTTLS (587) | PlatformEmailPanel.tsx:91-99 | PRESENT | :81-89 (plain checkbox, not a `SettingsRow`) |
| 10 | Use implicit SSL (465) | PlatformEmailPanel.tsx:100-108 | PRESENT | :90-98 (plain checkbox) |
| 11 | "Save platform email settings" → PATCH `/admin/platform/email-settings` | PlatformEmailPanel.tsx:110-116 | PRESENT | `SettingsActions` when dirty, with Discard :71-72, PlatformConfigurationSection.tsx:14 |
| 12 | Save error | PlatformEmailPanel.tsx:117 | PRESENT | PlatformConfigurationSection.tsx:13 |
| 13 | Load error (server message) | PlatformEmailPanel.tsx:118 | CHANGED | Generic + Retry PlatformEmailPanel.tsx:70 |
| 14 | Social panel title + description | PlatformSocialAuthPanel.tsx:63-66 | PRESENT | Description paragraph kept PlatformSocialAuthPanel.tsx:66-68; title replaced by tab "Sign-in providers" |
| 15 | Google / Apple configured read-outs | PlatformSocialAuthPanel.tsx:67-70 | PRESENT | :69-72 |
| 16 | Google Web client ID | PlatformSocialAuthPanel.tsx:74 | PRESENT | `SettingsRow` :76 |
| 17 | Google iOS client ID | PlatformSocialAuthPanel.tsx:76 | PRESENT | :78 |
| 18 | Google Android client ID | PlatformSocialAuthPanel.tsx:77 | PRESENT | :79 |
| 19 | Apple Web Service ID | PlatformSocialAuthPanel.tsx:82 | PRESENT | :84 |
| 20 | Apple native app audiences (textarea, comma/newline list) | PlatformSocialAuthPanel.tsx:83-85 | PRESENT | :85-87 (plain label, not a `SettingsRow`) |
| 21 | Apple Team ID | PlatformSocialAuthPanel.tsx:87 | PRESENT | :89 |
| 22 | Apple Key ID | PlatformSocialAuthPanel.tsx:88 | PRESENT | :90 |
| 23 | Apple private key .p8 (write-only, "set" placeholder) | PlatformSocialAuthPanel.tsx:90-92 | PRESENT | :92-94 |
| 24 | "Save social sign-in settings" → PATCH `/admin/platform/social-auth-settings` | PlatformSocialAuthPanel.tsx:94-96 | PRESENT | `SettingsActions` when dirty :64-65 |
| 25 | Load/save error | PlatformSocialAuthPanel.tsx:97 | CHANGED | Save error kept; load error now generic + Retry :63 |
| 26 | Stripe panel title + description ("Platform credentials authorize direct charges…") | PlatformStripeConnectPanel.tsx:72-75 | MISSING | Embedded mode drops it (subtitle at PlatformStripeConnectPanel.tsx:73 is never rendered) |
| 27 | "Connect credentials configured" read-out | PlatformStripeConnectPanel.tsx:76-79 | PRESENT | :79 |
| 28 | Platform publishable key (write-only) | PlatformStripeConnectPanel.tsx:82 | PRESENT | `SettingsRow` :81 |
| 29 | Platform secret key (write-only) | PlatformStripeConnectPanel.tsx:83 | PRESENT | :82 |
| 30 | Platform webhook secret (write-only) | PlatformStripeConnectPanel.tsx:84 | PRESENT | :83 |
| 31 | Stripe Connect client ID | PlatformStripeConnectPanel.tsx:85 | PRESENT | :84 |
| 32 | Application fee basis points (0-10000; aria-label only, no visible label) | PlatformStripeConnectPanel.tsx:86-95 | PRESENT | :85-94. Still a bare input without a `SettingsRow` label |
| 33 | "Save Stripe Connect settings" → PATCH `/admin/platform/payment-settings` | PlatformStripeConnectPanel.tsx:98-104 | PRESENT | `SettingsActions` when dirty :67,75-76 |
| 34 | "Clear publishable key" → PATCH `{stripe_publishable_key:""}`, no confirm | PlatformStripeConnectPanel.tsx:105-111 | CHANGED | `DangerZone` below the form :77-78 → `ConfirmDialog` :98-100 (adds confirmation) |
| 35 | "Clear secret key" | PlatformStripeConnectPanel.tsx:112-118 | CHANGED | Same pattern :70 |
| 36 | "Clear webhook secret" | PlatformStripeConnectPanel.tsx:119-125 | CHANGED | Same pattern :71 |
| 37 | Application fee read-out + "Saved keys are never returned." | PlatformStripeConnectPanel.tsx:127-129 | PRESENT | :96 (+ "100 = 1%") |
| 38 | Load / save / clear errors | PlatformStripeConnectPanel.tsx:130-134 | CHANGED | Save/clear error kept (:75); load error generic + Retry (:74) |

## platform-dashboard — Platform dashboard (PlatformDashboardPanel.tsx)
Gate is unchanged: `activeTab === "platform-dashboard" && isSuperadmin && !singleTenantLocked` (StaffTabContent.tsx:71). OLD stacked five `Panel`s. NEW is a `DashboardLayout` with tenant-state stats, overflow stats, Problems / Tenant usage / Scheduler sections, and a rail for backup and delivery. A new danger banner surfaces the first "error" problem.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Title + "Hidden tenants are excluded…" | PlatformDashboardPanel.tsx:14-16 | PRESENT | Header PlatformDashboardPanel.tsx:15-16 |
| 2 | "Refresh dashboard and checks" (refetch both) | PlatformDashboardPanel.tsx:17 | PRESENT | Header secondary "Run checks now" :13,18 |
| 3 | Dashboard loading / error (server message); Problems rendered independently of dashboard failure | PlatformDashboardPanel.tsx:19-20,36-47 | CHANGED | Dashboard query drives the whole layout state (:14-15). If the dashboard fails, Problems is hidden even when `getPlatformProblems` succeeded. Error text is generic |
| 4 | "Checked {dashboard.checked_at}" | PlatformDashboardPanel.tsx:22 | PRESENT | Header meta :17 |
| 5 | Tenants by state counts | PlatformDashboardPanel.tsx:23 | PRESENT | Stats :20 (first 4 as cards, rest compact) |
| 6 | Backup: last result, last success, automatic on/off | PlatformDashboardPanel.tsx:25 | PRESENT | Rail `KeyValueCard` :49-52 |
| 7 | Offsite destinations (name, state, needs-attention, verified at) / none message | PlatformDashboardPanel.tsx:26 | PRESENT | :53-54 |
| 8 | "Backup settings" link → /admin/backup-restore | PlatformDashboardPanel.tsx:27 | PRESENT | :55 (`<a>`, full reload instead of router `Link`) |
| 9 | Failed emails / failed notifications | PlatformDashboardPanel.tsx:29 | PRESENT | Overflow stats :22-23 and Delivery rail :56-58 |
| 10 | "Platform settings" link → /admin/platform | PlatformDashboardPanel.tsx:30 | PRESENT | Rail seeAll :59 |
| 11 | Usage totals (collapsed `<details>`) | PlatformDashboardPanel.tsx:33 | PRESENT | Overflow stats :24 (now visible) |
| 12 | Problems loading / error | PlatformDashboardPanel.tsx:37-38 | PRESENT | :28 (generic + Retry) |
| 13 | Problems "Checked {problems.checked_at}" + 15-minute scheduler note | PlatformDashboardPanel.tsx:40 | CHANGED | Note kept :29. The problems' own `checked_at` is no longer shown (only the dashboard's in the header) |
| 14 | Problem rows: status badge, message, Inspect (router `Link`, or `<a>` for /control/) | PlatformDashboardPanel.tsx:41-45 | PRESENT | `ListRow` + pill + "Inspect" `<a>` :30-32; first error also in banner :19 |
| 15 | Scheduler freshness: description + table Task / Cadence / Last execution / Status (`#scheduler` anchor) | PlatformDashboardPanel.tsx:49 | PRESENT | :40-46 (status pill, relative time) |
| 16 | Tenant usage: per-tenant `<details>`, "Open usage page" link, `UsageTable` | PlatformDashboardPanel.tsx:50 | PRESENT | :35-39 |

## organizations — Organizations (panels/OrganizationsPanel.tsx)
Routing is unchanged; it is a global tab (staffTabs.ts:144). OLD was one `Panel`: superadmin create form, org `<select>` + pager, then Profile, Links (superadmin only), Memberships and Invitations stacked. It auto-selected the first org. NEW has three views. The list is a `DashboardLayout` of `ListRow`s with a pager. The detail is a `SettingsLayout` titled with the org name, with anchor tabs Profile/People/Invitations/Spaces and all sections rendered; `?org=` holds the selected org. Create is a `FlowLayout`. Auto-select happens only when `count === 1`. Memberships and Invitations are still gated on `governance_actions.includes("manage_organization_members")`; Links on `isSuperadmin`.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Superadmin "Create organization" inline form | OrganizationsPanel.tsx:26; OrganizationSetup.tsx:6-17 | BURIED | List header primary / detail overflow "Create organization" opens a `FlowLayout` (OrganizationsPanel.tsx:32,39,54,57; OrganizationSetup.tsx:7-19) with a public-page preview. One extra click |
| 2 | Create: Name (required, max 200) | OrganizationSetup.tsx:12 | PRESENT | OrganizationSetup.tsx:15 |
| 3 | Create: Slug (required, `[-a-zA-Z0-9_]+`, max 50) | OrganizationSetup.tsx:13 | PRESENT | :16 |
| 4 | Create submit → `useCreateOrganization`, selects new org | OrganizationSetup.tsx:10,14 | PRESENT | Footer next :12-13; OrganizationsPanel.tsx:32 |
| 5 | Create error | OrganizationSetup.tsx:15 | PRESENT | :17 |
| 6 | Panel description | OrganizationsPanel.tsx:27 | PRESENT | Subtitles OrganizationsPanel.tsx:34,54 |
| 7 | Orgs load error (server message) + Retry | OrganizationsPanel.tsx:29 | PRESENT | :55 (generic copy) |
| 8 | Empty "No organization access" | OrganizationsPanel.tsx:30 | PRESENT | :57 |
| 9 | Organization `<select>` (auto-selects first) | OrganizationsPanel.tsx:18-22,33-37 | CHANGED | Clickable `ListRow` list :58. Detail "All organizations" overflow appears only when count > 1 (:38). URL-persisted `?org=` |
| 10 | Org list Previous / Next | OrganizationsPanel.tsx:38-39 | PRESENT | `progress` pager :59 |
| 11 | Detail loading / error | OrganizationsPanel.tsx:42-43 | PRESENT | :41 |
| 12 | Profile heading + "Logo upload remains platform-managed" | OrganizationProfileForm.tsx:34-37 | PRESENT | OrganizationProfileForm.tsx:37-40 |
| 13 | Profile: Name (max 200) | OrganizationProfileForm.tsx:39-41 | PRESENT | `SettingsRow` :41-43 |
| 14 | Profile: Public slug | OrganizationProfileForm.tsx:42-44 | PRESENT | :44-46 (+ "/o/{slug}" helper) |
| 15 | Profile: Website (url) | OrganizationProfileForm.tsx:45-47 | PRESENT | :47-49 |
| 16 | Profile: Description | OrganizationProfileForm.tsx:48-50 | PRESENT | :50-52 |
| 17 | Profile: Publish profile + event catalogue checkbox | OrganizationProfileForm.tsx:51-54 | PRESENT | :53-56 |
| 18 | "Save profile" → `useUpdateOrganization` (gated `manage_organization_profile`) | OrganizationProfileForm.tsx:56 | PRESENT | Sticky `SettingsActions` when dirty :57 |
| 19 | View-only notice | OrganizationProfileForm.tsx:56 | PRESENT | :57 |
| 20 | Profile update error | OrganizationProfileForm.tsx:57 | PRESENT | :58 |
| 21 | Linked makerspaces heading + explanation (superadmin) | OrganizationSetup.tsx:27-28 | PRESENT | "Spaces" tab/section OrganizationsPanel.tsx:46,52; OrganizationSetup.tsx:29-30 |
| 22 | Makerspace select (excludes `superadmin_access_enabled === false`) | OrganizationSetup.tsx:29 | PRESENT | :31 |
| 23 | Relationship select (affiliate/manager/owner) | OrganizationSetup.tsx:30 | PRESENT | :32 |
| 24 | "Link or update relationship" → ConfirmDialog → `useChangeOrganizationLink` | OrganizationSetup.tsx:31,36 | PRESENT | :33,38 |
| 25 | Link list (makerspace · relationship) | OrganizationSetup.tsx:34 | PRESENT | `ListRow` + pill :36 |
| 26 | "Unlink" row button → ConfirmDialog | OrganizationSetup.tsx:34,36 | BURIED | Row `OverflowMenu` "Unlink" :36 → same ConfirmDialog :38 |
| 27 | Links Previous / Next | OrganizationSetup.tsx:35 | PRESENT | :37 |
| 28 | Links / change error | OrganizationSetup.tsx:33 | PRESENT | :35 |
| 29 | Members: name + email | OrganizationMemberships.tsx:26 | PRESENT | `ListRow` OrganizationMemberships.tsx:21-24 (+ joined date) |
| 30 | Members: status | OrganizationMemberships.tsx:27 | PRESENT | Pill :25 |
| 31 | Members: "Governance" column (`governance_actions`) | OrganizationMemberships.tsx:28 | CHANGED | Merged with granted actions into one comma list :24, so you can no longer tell org-governance rights from makerspace actions |
| 32 | Members: "Makerspace actions" column (`granted_actions`) | OrganizationMemberships.tsx:29 | CHANGED | Same merged list :24 |
| 33 | Members loading / error (server message) | OrganizationMemberships.tsx:16-17 | PRESENT | :17-18 (generic + Retry) |
| 34 | Members empty | OrganizationMemberships.tsx:18 | PRESENT | :19 |
| 35 | Members pager + count | OrganizationMemberships.tsx:35-41 | PRESENT | :27-33 |
| 36 | Invitations heading + "bearer link works once" | OrganizationInvitations.tsx:38-39 | PRESENT | OrganizationInvitations.tsx:38-39 |
| 37 | Invite: governance action checkboxes | OrganizationInvitations.tsx:41-43 | PRESENT | :41-43 |
| 38 | Invite: makerspace action checkboxes | OrganizationInvitations.tsx:44-46 | PRESENT | :44-46 |
| 39 | Invite: Expires in days (1-30) | OrganizationInvitations.tsx:47 | PRESENT | :47 |
| 40 | "Create invitation" → `useCreateOrganizationInvitation` | OrganizationInvitations.tsx:48 | PRESENT | :48; header primary "Invite someone" scrolls here (OrganizationsPanel.tsx:36) |
| 41 | Create invitation error | OrganizationInvitations.tsx:49 | PRESENT | :49 |
| 42 | One-time redeem URL + "Copy link" | OrganizationInvitations.tsx:51 | PRESENT | :51 |
| 43 | Invitation list: state + expires | OrganizationInvitations.tsx:55-57 | PRESENT | `ListRow` :57-61 (relative time, "Invitation #id") |
| 44 | Revoke active invitation → `useRevokeOrganizationInvitation` (danger-styled, no confirm) | OrganizationInvitations.tsx:58 | CHANGED | :61. Now neutral `desk-button`, still no confirmation |
| 45 | Invitations pager | OrganizationInvitations.tsx:61 | PRESENT | :62 |
| 46 | People/Invitations sections absent for users without `manage_organization_members` (components return null) | OrganizationMemberships.tsx:11; OrganizationInvitations.tsx:25 | CHANGED | The tabs "People"/"Invitations" and section headings are always listed (OrganizationsPanel.tsx:42-51), so view-only users get empty sections |

## organization-analytics — Organization analytics (panels/OrganizationAnalyticsPanel.tsx)
Gate is unchanged: `activeTab === "organization-analytics" && !isSuperadmin && !singleTenantLocked` (StaffTabContent.tsx:142). OLD had a free-number Org ID, a report select, then per-makerspace tables and a total table. NEW is a `DashboardLayout` with org and report selects in the header meta, up to 4 numeric totals as stat cards, a breakdown section and a total section. OLD had no charts, exports or makerspace selector. The line count dropped mostly through markup and skeleton consolidation; nothing moved elsewhere.

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| 1 | Title + description | OrganizationAnalyticsPanel.tsx:22-25 | PRESENT | Header OrganizationAnalyticsPanel.tsx:23 |
| 2 | Organization ID free number input (any id; server authorizes) | OrganizationAnalyticsPanel.tsx:27-38 | CHANGED | `<select>` of `useOrganizations` results with pager (:25-32,40-42). An org can only be chosen if it appears in the caller's organization list; arbitrary ID entry is gone |
| 3 | Report select (`reportDefinitions` where `aggregate_supported`) | OrganizationAnalyticsPanel.tsx:39-54 | PRESENT | :34-37 |
| 4 | "Select an organization" empty | OrganizationAnalyticsPanel.tsx:57-62 | PRESENT | :47 |
| 5 | Loading skeleton | OrganizationAnalyticsPanel.tsx:63,158-168 | PRESENT | Layout loading state :44 |
| 6 | Error with server message + Retry | OrganizationAnalyticsPanel.tsx:64-74 | CHANGED | Generic + Retry (:44, adminPresentation.ts:6) |
| 7 | "No makerspaces in this organization" empty | OrganizationAnalyticsPanel.tsx:75-80 | PRESENT | :46,60 |
| 8 | Breakdown by makerspace: per-space heading (name or "Makerspace #id") + table | OrganizationAnalyticsPanel.tsx:84-95,106-119 | PRESENT | :46-48,54-61 |
| 9 | Organization total table | OrganizationAnalyticsPanel.tsx:96-99 | PRESENT | :49-50; plus first 4 numeric totals as stat cards :19-21,44 |
| 10 | Dynamic columns from row keys; cell formatting (null "-", Yes/No, JSON) | OrganizationAnalyticsPanel.tsx:121-156,179-184 | PRESENT | `DataTable` :63-74 |
| 11 | "No records." per table | OrganizationAnalyticsPanel.tsx:129 | PRESENT | `emptyDescription` :66 |

### Counts

| page | PRESENT | BURIED | CHANGED | MISSING | total |
|---|---|---|---|---|---|
| exports | 14 | 1 | 2 | 0 | 17 |
| backups | 17 | 0 | 5 | 0 | 22 |
| usage | 8 | 0 | 1 | 0 | 9 |
| migration | 37 | 3 | 9 | 0 | 49 |
| modules | 14 | 0 | 5 | 0 | 19 |
| platform | 29 | 0 | 7 | 2 | 38 |
| platform-dashboard | 14 | 0 | 2 | 0 | 16 |
| organizations | 39 | 2 | 5 | 0 | 46 |
| organization-analytics | 9 | 0 | 2 | 0 | 11 |
| **total** | **181** | **6** | **38** | **2** | **227** |

### Restore candidates

1. **P1: migration stepper hides the cutover controls and has no resume point.** OLD showed every stage at once (TenantMigrationPanel.tsx:39-47). Quiesce, archive, recover, activate and abort (TenantMigrationExports.tsx:139-156, TenantMigrationImports.tsx:162-169) are now reachable only on step 6, after 5 "Continue" clicks each visit, because `step` is `useState(0)` (TenantMigrationPanel.tsx:22). Fix:
   - Pass `onStepSelect={key => setStep(stages.findIndex(s => s.key === key))}` to `FlowLayout`.
   - Derive the initial step from server state: active approval → pairings exist → export available → import awaiting_identity/ready → completed → IMPORTING with pairing.
   - Mark earlier steps `done`.
2. **P1: Materialise attestation is split from what it attests.** The "Run reviewed import" checkbox says "decisions shown above" (TenantMigrationImports.tsx:153), but `TenantMigrationIdentityDecisions` renders only on step 4 (TenantMigrationImports.tsx:181). The OLD card showed both together (TenantMigrationImports.tsx old:138-153). Either render a read-only decision summary on step 5, or move the Materialize block (new :144-158) into step 4 under the decisions.
3. **P2: a migration pairings failure blocks the whole flow.** TenantMigrationPanel.tsx:26 swaps the layout to an error block when `listPairings` fails. OLD showed `<ErrorText error={pairings.error}>` inline (old :49). Use `{status:"ready"}` plus the existing inline retry (new :30), so disclosure, export and import stay usable.
4. **P2: export disclosure is collapsed.** The 3-paragraph disclosure (DataExportsPanel.tsx old:42-61, headed "Read this disclosure before requesting an export") is behind "Read what's included" (new :50-51,59-79). Show the referenced-users and omitted-data paragraphs by default under the banner callout. Alternatively, open the disclosure as a confirm step on the header primary "Request export", using `confirm: { title, message }` on the Action at new :45.
5. **P2: platform dashboard failure hides Problems.** `state` comes from the dashboard query only (PlatformDashboardPanel.tsx:14-15). Problems should render independently, as in OLD (old :36-47). Use `{status:"ready"}` for the layout and an inline error/retry for the dashboard-derived sections, or move Problems out of the gated `QueryContent`.
6. **P2: migration import list errors are invisible on steps 5-6.** `imports.isLoading` and `imports.error` render only in the `phase === "import"` block (TenantMigrationImports.tsx:50-51). Move both outside that conditional (OLD :47-48).
7. **P3: missing panel descriptions in embedded platform tabs.** The Platform email description (old PlatformEmailPanel.tsx:75-77) and the Stripe description (old PlatformStripeConnectPanel.tsx:73-75) are dropped by `PlatformConfigurationSection` in embedded mode (PlatformConfigurationSection.tsx:12). Render `subtitle` as a `<p className="text-sm text-muted">` at the top of the embedded branch, or pass it as the section `description` in PlatformSettingsPanel.tsx:16.
8. **P3: org membership governance vs makerspace actions merged.** OLD had separate columns (OrganizationMemberships.tsx old:28-29). In the new `ListRow` meta (new :24), use two labelled lines: "Governance: …" and "Makerspace actions: …".
9. **P3: Org detail lists People/Invitations tabs without permission.** OrganizationsPanel.tsx:42-51 always includes them. Gate both tabs and sections on `detail.data.governance_actions.includes("manage_organization_members")`, as the components already do.
10. **P3: Unlink makerspace moved into an OverflowMenu.** It was a visible row button (OrganizationSetup.tsx old:34) and now sits in OverflowMenu (new :36). This follows Yuyu's rule for rare destructive row actions; the ConfirmDialog is retained, so no change is needed.
11. **P3: invitation Revoke has no confirmation.** This is unchanged from OLD (OrganizationInvitations.tsx old:58 / new :61), and the danger tone was dropped. Consider adding a ConfirmDialog, because a revoked bearer link cannot be restored.
12. **P3: disclosure "Revoke approval" has no confirmation.** This is unchanged (TenantMigrationDisclosure.tsx:108 / :109). Consider `confirm:` because revocation voids the export closure.
13. **P3: modules group read-outs.**
    - The `always_on` badge for always-on groups (ModulesPanel.tsx old:103-104) is gone; append "· Always on" in the section title at ModulesPanel.tsx:55 when `group.always_on`.
    - The "Required by …" read-out for not-installed modules (old :188-190) is gone; show it in `ModuleSettingsRow` whenever `required_by.length` (ModuleSettingsRows.tsx:20-34).
14. **P3: generic load errors replace server messages.** This affects exports, usage, modules, platform panels, platform dashboard and org analytics (old DataExportsPanel.tsx:76, TenantUsagePanel.tsx:32, ModulesPanel.tsx:68, PlatformEmailPanel.tsx:118, PlatformDashboardPanel.tsx:20, OrganizationAnalyticsPanel.tsx:67). `adminQueryState` (adminPresentation.ts:4-8) could append `query.error.message`, or a `StructuredApiError.detail`, when present.
15. **P3: backup archive disclosure lost its warn tone.** BackupRestorePanel.tsx old:76 is now neutral at BackupArchiveRows.tsx:5. Render it as `<Callout tone="warn">` to keep the "outside purge guarantees" warning prominent.
16. **P3: Stripe "Application fee basis points" has no visible label.** This is unchanged from OLD (PlatformStripeConnectPanel.tsx old:86-95 / new :85-94). Wrap it in `<SettingsRow label="Application fee (basis points)" helper="100 = 1%">`.
17. **P3: org analytics can no longer target an arbitrary org ID.** OrganizationAnalyticsPanel.tsx old:27-38 accepted any ID. Restore only if analytics grants can exist for orgs missing from `useOrganizations`. In that case, add a "Enter ID" fallback input next to the select (new :25-32).
18. **P3: platform dashboard problems lost their own timestamp.** "Checked {problems.checked_at}" (PlatformDashboardPanel.tsx old:40) is gone. Add it to the Problems note at new :29.
