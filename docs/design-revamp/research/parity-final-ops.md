# Final parity audit — ops (machines, printing, events, bookings, devices, handover pickups)

Baseline `d3e5ed29` (pre-revamp). Compared against HEAD `b348ee18` (working tree), read 2026-10-16. Read-only:
no app code touched. `npx vitest run` over `panels/machine`, `MachinesPanel.test`, `Booking*`, `Event*` = 26 files /
78 tests, all green.

Scope covered: `MachinesPanel`, machine types / pricing, `MachineTypePage` + both service consoles (printer and
generic), consumable pools (shared / type / machine), certifications, material catalogue, reminder policy,
`MachineDrawer` and all eight tabs, public machine settings, usage logging, devices, job pickups, staff events
(`EventsPanel`, `EventDrawer` + tabs, series, collaborators, collaboration inboxes, check-in online / offline /
PIN station, badges, tickets / invites / promos, roster, waivers via host-waiver status), staff bookings
(`BookingsPanel`, `BookingDrawer`, agenda, spaces, per-space rules, staff booking form, payments reconcile).
"Staff printing" has no panel of its own: the legacy `printing` tab path redirects to `machines`
(`staffTabs.ts:244`, byte-identical to baseline) and the printer queue/reports live in `PrinterServiceConsole`.
"Staff reschedule" never existed — the only reschedule is member-side (`features/bookings/BookingReschedule.tsx`,
mounted from `MyBookings.tsx:66-69`) and is public-member scope.

## Summary

**190 capabilities: 160 PRESENT / 17 BURIED / 13 CHANGED / 0 MISSING.**
**Earlier restore list (`parity-machines-events-bookings.md`): 14 of 14 items verified FIXED in HEAD, 0 still
open** (item 15 was "no restore needed"). Routing and permission gates for all seven tabs are unchanged:
`staffTabs.ts` has no diff, and the `StaffTabContent.tsx` diff only adds `progress`/`allowedTabs`/`makerspaceName`
props. The `can_*`, `canManage`, `machineServiceEnabled`, `printingEnabled`, `reportsEnabled`,
`machines.material_catalogue|structured_intake|public_detail`, `maintenance.meters|calendar_feed`,
`events.invites|ticket_types|promo_codes`, `bookings.recurring` and `offline_checkin_enabled` gates were diffed
line by line against baseline: none is looser or stricter. The only gate-adjacent differences are deliberate
improvements (Retire/Reactivate now hidden instead of disabled and confirm-protected; Wipe attendee data now
confirm-protected).

No P0. Two P1 items (both information-on-touch, not lost actions), the rest P2.

## Earlier restore list — verification

| # | Item | Verdict | Evidence (HEAD) |
|---|---|---|---|
| 1 | Service queue hid active jobs (M35/M36/M37/M46/M20) | FIXED | `ServiceConsoleSections.tsx:7-20` `ACTIVE` set + `initialStatus="active"` default; tabs Active/Pending/Accepted/In progress/Ready/Collected/Failed/Rejected/All with counts; neutral labels; `MachineTypePage.tsx:64` reads `?job_status=`; `DashboardMachineQueue.tsx:42` deep-links `?view=queue&job_status=<status>` |
| 2 | Event list tabs filtered one server page (E15/E6) | FIXED | `EventsPanel.tsx:72-78` tabs now call `list.setFilter("status", …)` (server-side); `list.query` carries `status` (`useUrlListState.ts` `query`) |
| 3 | Booking Calendar inherited Requests filters (B26) | FIXED | `BookingAgenda.tsx:14` own `useSpaceBookings(spaceId, { starts_at: today }, page, "starts_at")` |
| 4 | Machine create lost photo/warranty step (M27/M28) | FIXED | `MachineTypePage.tsx:100-104` dialog stays open until the form's `onDone`; `hideSubmit` hides the form's own buttons (`MachineCreateForm.tsx:155,225`) |
| 5 | Series extension-failure alert buried (E53) | FIXED | `EventSeriesDrawer.tsx:51` `banner` on every tab with **Extend now** |
| 6 | Recurring badge missing on occurrences (E20) | FIXED | `EventDrawer.tsx:64-65` chip, links to the series via `onOpenSeries` (`EventsPanel.tsx:85-86`) |
| 7 | Complete/Cancel event & series only in Settings | FIXED | `EventDrawer.tsx:84-85`, `EventSeriesDrawer.tsx:49-50` header overflow for published items; Settings DangerZones kept |
| 8 | Bookings list "New booking" dead end (B3) | FIXED | `BookingsPanel.tsx:63-71` space-picker modal → opens that space with the form up (`initialCreateOpen`) |
| 9 | Manual usage three clicks deep (M41-43/47) | FIXED (partly by design) | `MachineTypePage.tsx:111` header secondary **Log usage** on the Queue tab; reports stay a sub-tab |
| 10 | Pool-load error missing on index (M7) | FIXED | `MachinesPanel.tsx:187-188` index callout with Retry |
| 11 | Sole-type settings tab (M16) | VERIFIED | `MachineTypePage.tsx:69` `canConfigureMachineTypes \|\| settings`; `MachinesPanel.tsx:128-165` sole type renders inline with `settings` non-null, so a scoped maintainer without configure rights still gets the tab (recipients + shared consumables) |
| 12 | Saved-views "?" copy bug | FIXED | `SavedViewsMenu.tsx:44-45` "Save current view…" / "Manage views…" |
| 13 | Type icon on index cards (M4) | FIXED | `MachineTypeCards.tsx:25` `machineTypeIdentity` (icon text, `Cog` fallback), reused as the type page identity |
| 14 | Status sub-tab copy (M46) | FIXED | covered by #1 |

## Restore list (new findings), ordered P0 → P2

### P0
None. Every capability that existed pre-revamp is reachable from a mounted page; no destructive action lost a
confirmation (Reject/Fail/Revoke/Deactivate/Cancel/Wipe all still confirm or take a reason first; registration
Cancel/Reject/Correct-attendance, invitation/promo Revoke and payment Waive never had one — unchanged).

### P1
1. **Exact timestamps on traceability records are unreachable on touch devices.** Maintenance history
   (`performed_at`), manual/automatic usage log, error log and the Ready-to-collect "finished" time now render only
   `<RelativeTime>` ("5 days ago"); the exact value is the `title` tooltip (`RelativeTime.tsx:27`), which phones and
   tablets never show. Old: `MaintenanceTab` `formatDateTime(log.performed_at)`, `UsageTab`/`ErrorsTab`
   `formatDate(entry.created_at)`, `HandoverConsole` finished time (absolute). New:
   `panels/machine/MaintenanceTab.tsx:87`, `UsageTab.tsx:41`, `ErrorsTab.tsx:35`,
   `HandoverConsole.tsx` (`finished <RelativeTime>`). Why it matters: the product's core concern is traceability;
   "when exactly was this serviced / logged / handed over" is the record. Fix: give `RelativeTime` an `exact` prop
   (renders "5 days ago · 12 Oct 2026, 14:05") and pass it at those four call sites (and the roster/overview
   `created_at` meta). One shared-component change, no per-screen work.
   (Classified P1 because it is data loss on phones for audit-grade records; it is information, not an action.)

### P2
2. **Registrations "Add registration" is a tab + a toggle on event day** (E36). Old: form visible in the roster.
   `EventRegistrationRoster.tsx:60` (toggle, only when published and registration open). Door staff do this often.
   Fix: render the form expanded by default when `event.status === "published" && registration_open` and the roster
   is empty/short, or add a header `actions.secondary` "Add registration" on the Registrations tab.
3. **Complete event / Complete series / Cancel are one overflow deep** (E29, E30, E58, E59). `EventDrawer.tsx:84-85`,
   `EventSeriesDrawer.tsx:49-50`. Old: visible buttons. Routine on event day. Fix (optional): promote **Complete
   event** to the header primary once `ends_at` has passed.
4. **Events list empty copy is wrong when a search/status tab returns nothing.** `EventsPanel.tsx:98-99` sets
   `isEmpty` from `events.data.count === 0`, so a zero-result search or an empty Drafts tab shows "Your events will
   appear here. Create your first event." (the specific in-body messages at line 102 are unreachable). Fix: pass
   `filtered={Boolean(list.values.q || list.values.status)}` and a `filteredEmpty` message with a **Clear filters**
   action, as `BookingsPanel.tsx:49-52` already does.
5. **Organized events still filters one server page client-side** (O6). `OrganizedEventsPanel.tsx:15-16`
   Upcoming/Past tabs filter the current 50-row page; default tab is All so nothing is lost, but "Upcoming" can look
   empty while page 2 has upcoming events. Fix: server `ends_at` range params, or relabel "on this page".
6. **Roster phone card order.** `EventRegistrationRoster.tsx:64-82` sets no `phone` roles, so the Badge checkbox is
   the card title and Name becomes a "Name …" detail line. Everything is reachable; scan order is poor. Fix:
   `{key:"badge", phone:"lead"}`, `{key:"name", phone:"title"}`.
7. **Service-queue Reject/Fail, operator Remove, Unlink, Document Delete, booking Reject/Cancel/No-show, payment
   Waive are in overflow menus** (M39, M45, D11, D14, D25, B22, P1). Matches the Yuyu rule and is not a restore;
   noted for completeness. Waive has no confirmation in old or new.
8. **Failed jobs are not in the default Active tab** (`ServiceConsoleSections.tsx:7`), yet **Reprint** only appears on
   failed jobs. The Failed tab shows a count badge, so it is discoverable; consider including `failed` in Active.
9. **Dashboard "pending bookings / upcoming bookings" links drop their `status` filter.** `dashboardLinks.ts:6-7`
   links `bookings?status=pending`, but `BookingsPanel.tsx:16` only models `q/ordering/page` (the status filter lives
   per space under the `booking-<id>.` prefix). Identical in the baseline — not a regression; flagged because the
   tile promises a pending list.
10. **Series tab keeps the events toolbar** (search/sort/saved views do not apply to series) — cosmetic.
11. **PIN station page now blocks unlock while offline** (`EventCheckInStationPage.tsx:49` `disabledReason:
    "Reconnect to unlock this station."`). Unlock needs the server, so this only changes the message; the old page
    simply failed with "invalid or outside its event window". Keep.
12. **Index "Add machine type" does nothing if the page is in its error state** (`MachinesPanel.tsx:183-186`
    queries `#machine-type-settings`, which is not rendered while the query state is an error). Edge case; the
    Retry callout is the path out.

## Capability table

Old paths are relative to `frontend/src/features/staff/` at `d3e5ed29`. New locations are HEAD. Status: PRESENT =
same capability, one click or less extra; BURIED = needs ≥2 extra clicks or moved into an overflow though it was
visible and frequent; CHANGED = behaviour/copy/data differs in a way a user would notice; MISSING = unreachable.
"Phone" is confirmed per row: no capability in this area uses `hidden`/`max-md:hidden`/`md:block`-only rendering
(grepped); the only phone demotion is `PageHeader` moving `actions.secondary` into the "More actions" menu below
768px (New series, New booking on lists; Log usage on the queue tab; All machines on dashboard queues) — each is
still reachable there, and Log usage also has its own button on the Manual usage sub-tab.

### 1. Machines index (`panels/MachinesPanel.tsx`, `machine/MachineTypeCards.tsx`)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| M1 | Title + "N machines" counter | `MachinesPanel.tsx:160,173` | `MachinesPanel.tsx:182` subtitle | PRESENT | |
| M2 | One card per reachable type incl. nested-machine fallback | `MachinesPanel.tsx:94-103` | `MachinesPanel.tsx:96-105,189` | PRESENT | |
| M3 | Card counters + running/maintenance/offline highlights, "counting…" / "count unavailable" | `MachineTypeCards.tsx:66-104` | `MachineTypeCards.tsx:129-140` | PRESENT | |
| M4 | Card shows the type's own icon | `MachineTypeCards.tsx:82` | `MachineTypeCards.tsx:25,80` | PRESENT | fixed since earlier audit |
| M5 | Card links to `/machines/<id>-<slug>` | `MachineTypeCards.tsx:77` | `ListRow href` `:79` + click capture `MachinesPanel.tsx:167-171` | PRESENT | |
| M6 | Type/machines load error + retry | `MachinesPanel.tsx:189` | `MachinesPanel.tsx:186-187` | PRESENT | Retry added |
| M7 | Pool-load error on the index | `MachinesPanel.tsx:195` | `MachinesPanel.tsx:188` | PRESENT | fixed |
| M8 | "Machine types and pricing" section | `MachineTypesPanel.tsx:146` | `MachineTypesPanel.tsx:157`; header primary `MachinesPanel.tsx:183` | PRESENT | |
| M9 | Create custom type (slug, name, icon, unit, requires-booking, presets) | `MachineTypesPanel.tsx:140` | same file `:~140-160` | PRESENT | |
| M10 | Edit custom type + Save type | `MachineTypesPanel.tsx:108` | `MachineTypesPanel.tsx:124-131` | PRESENT | |
| M11 | Pricing per type + Save pricing | `MachineTypesPanel.tsx:70` | `PricingEditor` `:133` | PRESENT | |
| M12 | Built-in read-only row + read-only notice | `MachineTypesPanel.tsx:161` | `MachineTypesPanel.tsx:~170,176` | PRESENT | |
| M13 | Delegated "who gets notified" rules (gate `maintenanceEnabled && delegatedRecipientRulesEnabled`) | `MachinesPanel.tsx:239` | `MachinesPanel.tsx:163` | PRESENT | gate unchanged |
| M14 | Shared consumables section (gate `canManage && machineServiceEnabled`) | `MachinesPanel.tsx:243` | `MachinesPanel.tsx:164` | PRESENT | gate unchanged |
| M15 | Pool cards: band, %, scope, remaining, Adjust stock, public toggle | `SharedConsumablesSection.tsx:54-180` | `SharedConsumablesSection.tsx:59-190` | PRESENT | |
| M16 | Sole-type actor: type page + settings | `MachinesPanel.tsx:126,235` | `MachinesPanel.tsx:128-165`, `MachineTypePage.tsx:69` | BURIED | settings are the page's **Settings** tab (1 click); verified present for scoped maintainers |
| M17 | Unknown type deep link → index, skeleton while resolving | `MachinesPanel.tsx:132` | `MachinesPanel.tsx:134-148` | PRESENT | |
| M18 | `?machine=<id>` opens drawer, close clears it | `MachinesPanel.tsx:64` | `MachinesPanel.tsx:66-68,166` | PRESENT | |
| M19 | Dashboard queues (`?work_queue=`): All machines, overdue maintenance rows → drawer Maintenance tab, paging | `DashboardMachineQueue.tsx` | `DashboardMachineQueue.tsx:31-44` | PRESENT | |
| M20 | Dashboard print rows → open printer queue | `DashboardMachineQueue.tsx:34` | `DashboardMachineQueue.tsx:42` | PRESENT | now lands on the matching `job_status` sub-tab |

### 2. Machine type page (`machine/MachineTypePage.tsx`, consoles)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| M21 | Back to all machine types | `MachinesPanel.tsx:163` | `MachineTypePage.tsx:~102` `back` | PRESENT | |
| M22 | "Machines, consumables and the service queue for X" line | `MachinesPanel.tsx:168` | meta: type · N machines · N running | CHANGED | copy only |
| M23 | Status filter (all/idle/running/reserved/maintenance/offline) | `MachinesPanel.tsx:177` | `MachineTypePage.tsx:71` status tabs | PRESENT | |
| M24 | Machine rows: thumbnail, name, model, location, status, usage hours → drawer | `MachineTypePage.tsx:94` | `MachineTypePage.tsx:~73-85` `DataTable` | PRESENT | phone card via table roles |
| M25 | Both empty states require a successful load | `MachineTypePage.tsx:88` | `MachineTypePage.tsx:~77-78` + `state` | PRESENT | |
| M26 | Add machine (name, make/model for printers, location) — gate `canManage && can_create_machine` | `MachineTypePage.tsx:73` | header primary `MachineTypePage.tsx:110` → `FlowLayout` dialog `:99-104` | PRESENT | gate unchanged |
| M27 | Post-create photo + warranty step, Done | `MachineCreateForm.tsx:160` | `MachineCreateForm.tsx:163-224`; dialog stays open `MachineTypePage.tsx:100-104` | PRESENT | fixed |
| M28 | Single submit in create form | `MachineCreateForm.tsx:150` | `hideSubmit` `:155` | PRESENT | fixed |
| M29 | Certifications list, View/Hide grants, Edit, Deactivate (confirm), New type (gate `can_create_machine`) | `CertificationsPanel.tsx` | **Certifications** tab `MachineTypePage.tsx:68` | PRESENT | |
| M30 | Grants: Renew, Revoke (+reason, confirm), grant form, paging | `CertificationGrants.tsx` | same, `CertificationGrants.tsx` | PRESENT | |
| M31 | Material catalogue + intake schema (gate `canConfigure && material_catalogue/structured_intake`) | `MaterialCataloguePanel.tsx` | **Settings** tab `MachineTypePage.tsx:96` | PRESENT | gate unchanged |
| M32 | Reminder policy (gate `canConfigure`) | `MachineReminderPolicy.tsx` | **Settings** tab `MachineTypePage.tsx:97` | PRESENT | |
| M33 | Type/machine pool create form (gate `machineServiceEnabled && canManage`) | `MachineTypePage.tsx:122` | **Consumables** tab `MachineTypePage.tsx:91` | PRESENT | intro text dropped |
| M34 | Type pool stock list, Adjust stock, public toggle | `MachineTypePage.tsx:128` | `MachineTypePage.tsx:92` `ConsumablePoolList` | PRESENT | |
| M35 | Printer queue lists every job | `PrinterServiceConsole.tsx:110` | `ServiceConsoleSections.tsx:7-20` Active default + counts | PRESENT | fixed |
| M36 | Queue empty state | (none) | `ServiceConsoleSections.tsx:~24` per-tab copy | PRESENT | fixed |
| M37 | Terminal jobs (collected/failed/rejected) | `PrinterServiceConsole.tsx:111` | own tabs + All jobs | PRESENT | fixed |
| M38 | Accept / Start / Complete / Collect / Reprint | `PrinterServiceConsole.tsx:151` | `PrinterServiceConsole.tsx:151-156` | PRESENT | |
| M39 | Reject (pending), Fail (in progress) | `PrinterServiceConsole.tsx:151,153` | row `OverflowMenu` `:152,154` | BURIED | accepted (Yuyu rule); still open a reason form |
| M40 | Action form → `POST /machine-service/requests/<id>/<action>` | `PrinterServiceConsole.tsx:119` | `Modal` `:131`, same payload | CHANGED | modal, draft persisted in lifted drafts |
| M41 | Manual usage form → `typed-manual-usage` | `PrinterServiceConsole.tsx:122` | Manual usage sub-tab + header **Log usage** `MachineTypePage.tsx:111`, modal `ServiceConsoleSections.tsx:46` | BURIED | 2 clicks from the Machines tab, 1 from Queue |
| M42 | Manual usage history | `PrinterServiceConsole.tsx:124` | Manual usage sub-tab | BURIED | |
| M43 | Printer reports (gate `printingEnabled && reportsEnabled`) | `PrinterServiceConsole.tsx:126` | Printer reports sub-tab | BURIED | gate unchanged |
| M44 | Generic console: hint, Accept/Start/Complete/Collect | `MachineServiceConsole.tsx:93` | `MachineServiceConsole.tsx:~35-58` | PRESENT | |
| M45 | Generic Reject / Fail | `MachineServiceConsole.tsx:142` | overflow | BURIED | accepted |
| M46 | Non-printer status labels | n/a | `ServiceConsoleSections.tsx:8-13` In progress / Ready | PRESENT | fixed |
| M47 | Generic manual usage form + list | `MachineServiceConsole.tsx:115` | Manual usage sub-tab | BURIED | same as M41 |
| M48 | Service query/mutation errors | `PrinterServiceConsole.tsx:136` | `ErrorBlock` + modal error | PRESENT | |

### 3. Machine drawer (`machine/MachineDrawer.tsx` + tabs)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| D1 | Header: status, Retired tag, type, total hours | `MachineDrawer.tsx:57` | `MachineDrawer.tsx:~48-52` | PRESENT | |
| D2 | Tab gates: Maintenance (`maintenanceEnabled && can_operate`), Warranty (`can_edit`) | `MachineDrawer.tsx:36` | `MachineDrawer.tsx:~34-40` | PRESENT | unchanged |
| D3 | `detail_tab=Maintenance` deep link | `MachineDrawer.tsx:30` | `MachineDrawer.tsx:~27` | PRESENT | |
| D4 | Public detail disclosures (`can_edit && machines.public_detail`) | `OverviewTab.tsx:79` | `OverviewTab.tsx:78` | PRESENT | |
| D5 | Machine photo upload (`can_edit`) | `OverviewTab.tsx:80` | `OverviewTab.tsx:80` | PRESENT | |
| D6 | Edit name/location/firmware/camera URL/notes + Save | `OverviewTab.tsx:91` | `OverviewTab.tsx:81-87` | PRESENT | Save/Discard bar |
| D7 | Status select + Set status (`can_operate`) | `OverviewTab.tsx:121` | `OverviewTab.tsx:91-100` + header primary Mark running/idle | PRESENT | |
| D8 | Retire / Reactivate | `OverviewTab.tsx:134` | `DangerZone` `OverviewTab.tsx:109-114` | CHANGED | hidden not disabled without `can_retire/can_unretire`; now confirm-protected |
| D9 | Public listing toggle + preview (`canManageMachines`) | `MachinePublicSettings.tsx:56` | `OverviewTab.tsx:106` | PRESENT | |
| D10 | Operators list | `OperatorsTab.tsx:51` | `OperatorsTab.tsx:~38` | PRESENT | |
| D11 | Operator Remove (`can_delegate`) | `OperatorsTab.tsx:59` | row overflow | BURIED | accepted |
| D12 | Add operator (member, access level) | `OperatorsTab.tsx:65` | `OperatorsTab.tsx:~45-70` | PRESENT | |
| D13 | Consumables list, Low flag | `ConsumablesTab.tsx:150` | `ListRow` | PRESENT | |
| D14 | Consumable Unlink (`can_edit`) | `ConsumablesTab.tsx:155` | row overflow | BURIED | accepted |
| D15 | Log consumable use per row (`can_operate`) | `ConsumablesTab.tsx:158` | same inline form | PRESENT | |
| D16 | Link consumable form | `ConsumablesTab.tsx:79` | same | PRESENT | |
| D17 | Usage log list | `UsageTab.tsx:38` | `UsageTab.tsx:41` | CHANGED | timestamp relative only (see P1-1) |
| D18 | Add usage | `UsageTab.tsx:55` | same | PRESENT | |
| D19 | Maintenance calendar feed (`maintenance.calendar_feed`) | `MaintenanceFeedControl.tsx` | unchanged file | PRESENT | |
| D20 | Schedules: due state, Edit, Complete, Deactivate (confirm), New incl. meters | `MaintenanceSchedules.tsx:91` | `MaintenanceSchedules.tsx` | PRESENT | |
| D21 | Schedule completion form | `MaintenanceTab.tsx:129` | same | PRESENT | |
| D22 | Log maintenance (`can_operate && !retired`) | `MaintenanceTab.tsx:209` | same | PRESENT | |
| D23 | History, attachments (view/delete/upload/retry) | `MaintenanceTab.tsx:75` | `MaintenanceTab.tsx:84-100` | CHANGED | performed time relative only (P1-1) |
| D24 | Documents list + View | `DocumentsTab.tsx:49` | `ListRow` | PRESENT | |
| D25 | Document Delete (`can_edit`) | `DocumentsTab.tsx:62` | row overflow | BURIED | accepted |
| D26 | Upload document | `DocumentsTab.tsx:69` | same | PRESENT | |
| D27 | Error logs list | `ErrorsTab.tsx:32` | `ErrorsTab.tsx:35` | CHANGED | time relative only (P1-1) |
| D28 | Add error log | `ErrorsTab.tsx:48` | same | PRESENT | |
| D29 | Warranty tab | `WarrantyTab.tsx` | unchanged | PRESENT | |

### 4. Devices

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| V1 | Create device (name, kind) → enrollment grant | `DevicesPanel.tsx:26` | header primary **Add device** → dialog | PRESENT | |
| V2 | Device list name/kind/state/last seen | `DevicesPanel.tsx:31` | rows + pill | PRESENT | |
| V3 | Pagination | `DevicesPanel.tsx:41` | `pagination` | PRESENT | |
| V4 | 60 s auto-refresh | `DevicesPanel.tsx:17` | same | PRESENT | |
| V5 | List/detail error + retry | `DevicesPanel.tsx:27` | `opsQueryState` | PRESENT | |
| V6 | Select device → identity | `DevicesPanel.tsx:34` | drawer | CHANGED | placement only |
| V7 | Fingerprint + key version | `DeviceIdentitySection.tsx:55` | same | PRESENT | |
| V8 | Rename + offline threshold, Save identity | `DeviceIdentitySection.tsx:56` | Save/Discard bar | PRESENT | |
| V9 | Issue enrollment / Rotate key / Reactivate | `DeviceIdentitySection.tsx:62` | same | PRESENT | |
| V10 | Revoke + confirm | `DeviceIdentitySection.tsx:65` | `DangerZone` + `ConfirmDialog` | PRESENT | |
| V11 | One-time enrollment modal, Copy enrollment | `DeviceEnrollmentModal.tsx` | dialog | PRESENT | |

### 5. Handover job pickups (`panels/machine/HandoverConsole.tsx`)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| H1 | Completed jobs: title, requester, machine, finished time | `HandoverConsole.tsx:64` | `HandoverConsole.tsx:~42-48` | CHANGED | finished time relative (P1-1); search + stats added |
| H2 | Payment line Paid/Unpaid/Waived + amount | `HandoverConsole.tsx:23` | `paymentInfo` pill | PRESENT | |
| H3 | Hand over → `POST …/collect` | `HandoverConsole.tsx:42` | same, toast added | PRESENT | |
| H4 | Loading / error / empty / collect error | `HandoverConsole.tsx:56` | layout states + callout | PRESENT | |

### 6. Events list and create (`EventsPanel.tsx`)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| E1 | 403 / module-unavailable | `EventsPanel.tsx:68` | `EventsPanel.tsx:81,98-99` | PRESENT | |
| E2 | Search | `ListViewControls.tsx` | `ListViewControls.tsx` | PRESENT | |
| E3 | Sort | `EventsPanel.tsx:73` | `EventsPanel.tsx:101` | PRESENT | |
| E4 | Saved views (choose/save/manage/page) | `SavedViewsMenu.tsx` | **Views** menu `SavedViewsMenu.tsx:40-47` | PRESENT | copy fixed |
| E5 | Clear selected result (`id`) | `ListViewControls.tsx:9` | chip `ListViewControls.tsx` | PRESENT | |
| E6 | Status filter | `EventsPanel.tsx:74` | status tabs `EventsPanel.tsx:72-78` | PRESENT | server-side |
| E7 | Cross-space invitations inbox accept/decline | `CollaborationInbox.tsx` | callout **Review** + drawer `EventCollaborationReview.tsx:15-19` | PRESENT | non-pending history via "Review collaborations" button |
| E8 | Series invitations inbox | `EventSeriesCollaborationInbox.tsx` | same drawer | PRESENT | |
| E9 | One-time / Recurring creation | `EventsPanel.tsx:78` | header **New event** / **New series** | PRESENT | New series is in "More actions" on phones |
| E10 | Create-draft form (all fields) | `EventsPanel.tsx:79` | `FormPageLayout` `EventsPanel.tsx:88-93` | PRESENT | with live preview |
| E11 | Create errors | `EventsPanel.tsx:84` | `EventsPanel.tsx:91` | PRESENT | |
| E12 | Open the new event/series after create | `EventsPanel.tsx:52` | `EventsPanel.tsx:51-68` | PRESENT | |
| E13 | Series list → series page | `EventsPanel.tsx:87` | **Series** tab `EventsPanel.tsx:102` | PRESENT | |
| E14 | Table: title, dates, location, status, capacity, confirmed/pending | `EventsPanel.tsx:91` | `ListRow` `EventsPanel.tsx:102` | PRESENT | |
| E15 | All events on the page together / empty states | `EventsPanel.tsx:94` | status tabs + `isEmpty` `:98` | CHANGED | server-side tabs fixed the hiding; empty copy wrong for zero-result search/tab (P2-4) |
| E16 | Pagination with total | `EventsPanel.tsx:102` | `EventsPanel.tsx:103` | PRESENT | |
| E17 | Quick-create "event" | `EventsPanel.tsx:47` | `EventsPanel.tsx:49` | PRESENT | |
| E18 | `?event=` deep link | `EventsPanel.tsx:42` | `EventsPanel.tsx:43-46` | PRESENT | |

### 7. Event detail (`EventDrawer.tsx` now a full page with tabs)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| E19 | Status badge | `EventDrawer.tsx:61` | `EventDrawer.tsx:77` | PRESENT | |
| E20 | "Recurring · series" badge | `EventDrawer.tsx:61` | `EventDrawer.tsx:64-65,78` | PRESENT | fixed; links to series |
| E21 | Capacity, registration open/closed | `EventDrawer.tsx:61` | meta `:78` + At a glance | PRESENT | |
| E22 | Effective registration cutoff | `EventDrawer.tsx:62` | `EventAtAGlance` (Overview tab) | PRESENT | |
| E23 | Event photo upload | `EventDrawer.tsx:63` | Settings tab | PRESENT | |
| E24 | Category + add category | `EventCategoriesField.tsx` | Settings tab | PRESENT | |
| E25 | Edit all fields + diffed Save | `EventDrawer.tsx:64` | `EventSettings` + `saveOccurrence` `EventDrawer.tsx:51-59` | PRESENT | Discard added |
| E26 | Terminal events read-only | `EventDrawer.tsx:68` | banner `:86` | PRESENT | |
| E27 | Occurrence overrides: Reset field | `EventDrawer.tsx:70` | Settings tab | PRESENT | |
| E28 | Publish + confirm | `EventDrawer.tsx:72` | header primary `:80` | PRESENT | |
| E29 | Complete + confirm | `EventDrawer.tsx:73` | header overflow `:84` + Settings "Finish this event" | BURIED | one overflow deep (P2-3) |
| E30 | Cancel event + confirm | `EventDrawer.tsx:73` | header overflow `:85` + DangerZone `:87` | BURIED | accepted |
| E31 | Lifecycle/update error text | `EventDrawer.tsx:75` | `EventDrawer.tsx:104` | PRESENT | |
| E32 | Invitations (`events.invites`) | `EventInvitesPanel.tsx` | **Tickets & invites** tab | PRESENT | gate unchanged |
| E33 | Ticket types (`events.ticket_types`) | `EventTicketsPanel.tsx` | same tab | PRESENT | |
| E34 | Promo codes (`events.promo_codes`) | `EventPromosPanel.tsx` | same tab | PRESENT | |
| E35 | Registrations roster + count | `EventRegistrationRoster.tsx:51` | **Registrations** tab | PRESENT | |
| E36 | Staff register-a-member form | `EventRegisterMember.tsx` | `EventRegistrationRoster.tsx:60` toggle | BURIED | tab + toggle (P2-2) |
| E37 | Badges: preview, PDF, template, save | `EventBadgeActions.tsx` | same component | PRESENT | |
| E38 | Per-row badge checkbox | `EventRegistrationRoster.tsx:66` | `:65` | PRESENT | |
| E39 | Payment reconcile (record/waive) per row | `EventRegistrationRoster.tsx:67` | `:66` | PRESENT | Waive in overflow |
| E40 | mailto/tel contact | `EventRegistrationRoster.tsx:68` | `:67` | PRESENT | |
| E41 | Cancel registration, Approve, Reject, Promote, Mark attended, Correct attendance | `EventRegistrationRoster.tsx:70-77` | `:74-81` | PRESENT | |
| E42 | Roster paging | `EventRegistrationRoster.tsx:81` | `:84` | PRESENT | |
| E43 | Check-in operator (published/completed) | `EventRegistrationRoster.tsx:57` | **Check-in** tab `EventDrawer.tsx:69,93-94`; header primary Open check-in | PRESENT | |
| E44 | Scan online QR | `EventCheckInScanner.tsx` (camera immediately) | `ScanWorkbench` `EventCheckInScanner.tsx:113-119` | CHANGED | camera started by user; manual code + Undo added; resolve→confirm two-step kept |
| E45 | Resolved guest card, Confirm, Scan another, blocked reasons | `EventCheckInScanner.tsx` | same logic `:97-108` | PRESENT | |
| E46 | Offline: download/refresh roster, scan, sync, wipe (`offline_checkin_enabled`) | `OfflineCheckInOperator.tsx` | same + wipe in `DangerZone` with confirm | PRESENT | |
| E47 | PIN station: create/rotate/disable/open/copy/reveal | `EventStationSettings.tsx` | Check-in tab | PRESENT | |
| E48 | Feedback survey builder, Save, Open/Close | `EventFeedbackPanel.tsx` | **Feedback** tab | PRESENT | |
| E49 | Responses + certificate actions | `EventFeedbackResponses.tsx` | same tab | PRESENT | |
| E50 | Organization organizers | `EventOrganizers.tsx` | **Team** tab | PRESENT | |
| E51 | Partner makerspaces | `EventCollaborators.tsx` | **Team** tab | PRESENT | |
| E62 | Public PIN station page (`/event-check-in/:token`) | `features/events/EventCheckInStationPage.tsx` | same route, `KioskLayout`; unlock needs connection; Lock station asks before discarding unsynced check-ins | CHANGED | deliberate; routes `AppRoutes.tsx:95,122` intact |

### 8. Series detail (`EventSeriesDrawer.tsx`)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| E52 | Status, active occurrences, revision | `EventSeriesDrawer.tsx:43` | `:45-46` | PRESENT | |
| E53 | Extension-failure alert | `EventSeriesDrawer.tsx:44` | banner `:51` | PRESENT | fixed |
| E54 | Series photo | `EventSeriesDrawer.tsx:45` | Settings tab | PRESENT | |
| E55 | Edit future occurrences + templates | `EventSeriesDrawer.tsx:46` | Settings tab `:55-59` | PRESENT | |
| E56 | Publish series | `EventSeriesDrawer.tsx:47` | primary `:48` | PRESENT | |
| E57 | Extend now | `EventSeriesDrawer.tsx:47` | primary `:48` + banner | PRESENT | |
| E58 | Complete series | `EventSeriesDrawer.tsx:47` | overflow `:49` + Settings | BURIED | accepted |
| E59 | Cancel series | `EventSeriesDrawer.tsx:47` | overflow `:50` + DangerZone `:53` | BURIED | accepted |
| E60 | Occurrences list → open one | `EventSeriesDrawer.tsx:49` | Occurrences tab `:61-63` | PRESENT | |
| E61 | Series partners | `EventSeriesCollaborators.tsx` | **Team** tab | PRESENT | |

### 9. Organized events

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| O1 | Intro text | `OrganizedEventsPanel.tsx:24` | subtitle `:18` | PRESENT | |
| O2 | Loading / error + Retry / empty | `OrganizedEventsPanel.tsx:28` | `opsQueryState` | PRESENT | |
| O3 | Title, dates, location, status, totals breakdown, organizers | `OrganizedEventsPanel.tsx:45` | `OrganizedEventsPanel.tsx:21-37` | PRESENT | |
| O4 | Pagination (page size 50) | `OrganizedEventsPanel.tsx:98` | `:25` | PRESENT | |
| O5 | Open host makerspace's event detail | `OrganizedEventsPanel.tsx:110` | `:17` full event page | PRESENT | |
| O6 | Whole page shown together | n/a | Upcoming/Past tabs `:15-16` filter one server page | CHANGED | default All; P2-5 |

### 10. Bookings list (`BookingsPanel.tsx`)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| B1 | 403 / module-disabled | `BookingsPanel.tsx:42` | `BookingsPanel.tsx:32-33` | PRESENT | |
| B2 | Quick-create "booking" | `BookingsPanel.tsx:33` | `BookingsPanel.tsx:21` opens picker | PRESENT | |
| B3 | Header New booking | n/a | `BookingsPanel.tsx:44,63-71` | PRESENT | fixed |
| B4 | Search, sort | `BookingsPanel.tsx:48` | `BookingsPanel.tsx:47-48` | PRESENT | |
| B5 | Saved views | `BookingsPanel.tsx:48` | Views menu | PRESENT | |
| B6 | Create space | `BookingsPanel.tsx:51` | header primary `:43` | PRESENT | |
| B7 | Name+location, type, approval, public, active | `BookingsPanel.tsx:14` | `BookingsPanel.tsx:53-61` | PRESENT | |
| B8 | Sortable "Space" header | `BookingsPanel.tsx:18` | dropdown only | CHANGED | |
| B9 | List error / loading / empty / filtered empty | `BookingsPanel.tsx:53` | `BookingsPanel.tsx:45,49-52` | PRESENT | |
| B10 | Pagination with total | `BookingsPanel.tsx:55` | `:62` | PRESENT | |
| B11 | Create-space form → opens new space | `BookingsPanel.tsx:56` | `BookableSpaceForm mode="create"` `:36-38` | PRESENT | page instead of modal |

### 11. Space detail (`BookingDrawer.tsx`, `BookingAgenda.tsx`, `BookingRequests.tsx`, forms)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| B12 | Active badge + requester emails state | `BookingDrawer.tsx:73` | `BookingDrawer.tsx:156-157` | PRESENT | |
| B13 | Edit space (all fields, custom form, paged machine type) + Save | `BookableSpaceForm.tsx:85` | **Settings** tab `BookingDrawer.tsx:163-167`, `BookableSpaceFields.tsx` | PRESENT | every old label verified present |
| B14 | Deactivate space + confirm | `BookingDrawer.tsx:87` | Settings DangerZone `:159-161` + `ConfirmDialog` `:187` | PRESENT | |
| B15 | Inactive read-only note | `BookingDrawer.tsx:87` | `:167` | PRESENT | |
| B16 | Staff booking form (`is_active`; recurring `bookings.recurring`; cert override; custom fields) | `StaffBookingForm.tsx` | header primary `:158` → modal `:174-176` | PRESENT | gates unchanged |
| B17 | "Bookings (N)" + staff-only note | `BookingDrawer.tsx:90` | **Requests** tab | PRESENT | |
| B18 | Sort | `BookingDrawer.tsx:94` | `BookingRequests.tsx:~254` | PRESENT | |
| B19 | Filters status / starts after / ends before | `BookingDrawer.tsx:95` | `BookingRequests.tsx:~259-267` | PRESENT | |
| B20 | Card: name, time, status, mailto/tel, answers, reconcile | `BookingDrawer.tsx:119` | `BookingRequests.tsx:~270-281` | PRESENT | |
| B21 | Approve / Complete | `BookingDrawer.tsx:168,170` | `BookingRequests.tsx:~288-296` | PRESENT | |
| B22 | Reject / Cancel / No-show | `BookingDrawer.tsx:168-170` | row overflow `BookingRequests.tsx:71` (confirm dialog `BookingDrawer.tsx:177`) | BURIED | accepted |
| B23 | Action confirm dialog + errors | `BookingDrawer.tsx:145` | `BookingDrawer.tsx:177-186` | PRESENT | |
| B24 | Pagination | `BookingDrawer.tsx:143` | `Pagination` | PRESENT | |
| B25 | `?space=&booking=` deep link filters to one booking | `BookingDrawer.tsx:53` | `BookingDrawer.tsx:52,66` + **Show all bookings** `BookingRequests.tsx:27` | PRESENT | |
| B26 | (new) Calendar tab | n/a | `BookingAgenda.tsx:14` own query | PRESENT | fixed; Open booking → Requests |

### 12. Per-space rules, requester emails, reports, payments (added this pass)

| # | Capability | Old | New | Status | Note |
|---|---|---|---|---|---|
| S1 | Per-space booking rules (buffers, cutoff, approval, limits) + Save rules | `MakerspaceBookingRulesSettings.tsx` | same fields, `SettingsEditorActions`; mounted `MakerspaceSettingsPanel.tsx:179` (`bookings` module gate) | PRESENT | |
| S2 | Booking requester-email default toggle | `MakerspaceBookingSettings.tsx` | same, adds toast + undo; `MakerspaceSettingsPanel.tsx:178` | PRESENT | |
| R1 | Reports: bookings, events, machine service, usage, maintenance, printer service | `OperationsReports*.tsx` | same files (every old string present) | PRESENT | gates in `StaffTabContent.tsx:196-206` unchanged |
| P1 | Payment reconcile on rows: Mark offline, Waive | `PaymentReconcileActions.tsx` | `PaymentReconcileActions.tsx:53-72` | BURIED | Waive moved to overflow; still no confirm (same as old); `canRecordPayment/canWaive` gates unchanged |

## Counts

| Section | PRESENT | BURIED | CHANGED | MISSING |
|---|---|---|---|---|
| Machines index (M1-M20) | 19 | 1 | 0 | 0 |
| Type page (M21-M48) | 20 | 6 | 2 | 0 |
| Machine drawer (D1-D29) | 22 | 3 | 4 | 0 |
| Devices (V1-V11) | 10 | 0 | 1 | 0 |
| Handover (H1-H4) | 3 | 0 | 1 | 0 |
| Events list (E1-E18) | 17 | 0 | 1 | 0 |
| Event detail (E19-E51, E62) | 29 | 3 | 2 | 0 |
| Series (E52-E61) | 8 | 2 | 0 | 0 |
| Organized (O1-O6) | 5 | 0 | 1 | 0 |
| Bookings list (B1-B11) | 10 | 0 | 1 | 0 |
| Space detail (B12-B26) | 14 | 1 | 0 | 0 |
| Rules / reports / payments (S1-S2, R1, P1) | 3 | 1 | 0 | 0 |
| **Total (190)** | **160** | **17** | **13** | **0** |

Method note: earlier audit rated a tab or a one-click header-primary-to-dialog move as BURIED; this pass applies the
brief's definition (≥2 extra clicks, or an overflow demotion of a visible frequent action), which is why PRESENT
rose from 109 to 160 without 51 new restores — 14 items were genuinely fixed, the rest are reclassifications.
