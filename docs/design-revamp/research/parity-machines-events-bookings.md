# Functionality parity audit — machines, devices, handover, events, organized, bookings

Baseline: `d3e5ed29` (`dev`, pre-revamp). Compared against: the **working tree** of
`feature/design-revamp` (HEAD `bd48ab7a` + uncommitted polish), read 2026-10-15.

Method: started at `staffTabs.ts` / `StaffTabContent.tsx` in both versions (routing and permission
gates for these six tabs are **unchanged** — `StaffTabContent.tsx:87-90,116-145,209-210`), followed every
import, diffed each file, and for every old control grepped the new tree before classifying it.
Line numbers in "Old file:line" are from `git show d3e5ed29:<path>`; paths are relative to
`frontend/src/features/staff/`.

Status key:

- **PRESENT** — same capability, same or easier reach (restyled is still PRESENT).
- **BURIED** — still reachable, but now behind a tab, overflow menu, dialog, popover or toggle (where is stated).
- **CHANGED** — reachable, but behaviour, defaults or data differ in a way a user will notice (explained).
- **MISSING** — not reachable anywhere in the new tree.

Files that are byte-identical to the baseline and still mounted under the same gate are PRESENT by
construction: `WarrantyTab`/`WarrantySection`, `MaintenanceDocuments`, `MaintenanceFeedControl`,
`MaintenanceMeterFields`, `PublicMachineDisclosure`, `CertificationTypeForm`, `EventSeriesForm`,
`EventTicketTemplates`, `EventCategoriesField`, `OfflineCheckInOperator`, `PaymentReconcileActions`,
`StaffBookingForm` (one colour token only). `BookableSpaceMachineType.tsx` was dead code in the baseline
(never imported) and is out of scope.

---

## 1. Machines — index (`panels/MachinesPanel.tsx`, `machine/MachineTypeCards.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| M1 | Page title + "N machines total" counter | `panels/MachinesPanel.tsx:160,173-175` | PRESENT | `ListLayout` subtitle "N machines across M types" (`MachinesPanel.tsx:182`) |
| M2 | One card per reachable type, incl. nested-machine fallback types | `panels/MachinesPanel.tsx:94-103,221-229` | PRESENT | `MachineTypeCards` rows (`MachinesPanel.tsx:188-190`) |
| M3 | Card counters: machine count, "N running / in maintenance / offline" highlights; "counting…" / "count unavailable" | `machine/MachineTypeCards.tsx:66-104` | PRESENT | `MachineTypeCards.tsx` `StatusPill`s |
| M4 | Card shows the type's own `icon` (emoji/text) | `machine/MachineTypeCards.tsx:82` | CHANGED | Every card now shows a generic `Cog` icon; `machineType.icon` is never rendered on the index |
| M5 | Card links to `/admin/machines/<id>-<slug>` | `machine/MachineTypeCards.tsx:77-78` | PRESENT | `ListRow href` |
| M6 | Machine-type load error and machines load error text | `panels/MachinesPanel.tsx:189-190` | PRESENT | Warn callout with **Retry** (improved) |
| M7 | Consumable-pool load error shown at panel level on the index | `panels/MachinesPanel.tsx:195-197` | CHANGED | Only shown on a type page banner (`MachineTypePage.tsx:102`) or inside the collapsed Shared consumables `ErrorBlock`; the index `ListLayout` gets no pool callout |
| M8 | "Machine types and pricing" collapsible section | `panels/MachinesPanel.tsx:237`, `panels/MachineTypesPanel.tsx:146-166` | PRESENT | Still a `<details>`; header primary **Add machine type** opens + focuses it (`MachinesPanel.tsx:183-185`) |
| M9 | Create custom type: slug, name, icon, metering unit, requires-booking flag, material/colour presets, **Create type** (`createMachineType`) | `panels/MachineTypesPanel.tsx:140-160,40-64` | PRESENT | Same form |
| M10 | Edit custom type: name, icon, metering unit, requires-booking, presets, **Save type** (`updateMachineType`) | `panels/MachineTypesPanel.tsx:108-130` | PRESENT | Same; drafts now lifted so they survive collapse |
| M11 | Pricing per type: rate per unit, flat fee, enable payment, **Save pricing** (`setMachineTypePricing`) | `panels/MachineTypesPanel.tsx:70-100` | PRESENT | Same |
| M12 | Built-in type read-only row + read-only notice for non-configurers | `panels/MachineTypesPanel.tsx:161-163` | PRESENT | Same |
| M13 | Delegated "Who gets notified" recipient rules (gate `maintenanceEnabled && delegatedRecipientRulesEnabled`) — add recipient, scope, save, discard | `panels/MachinesPanel.tsx:239-241`, `NotificationRecipientEvent.tsx:120-141` | PRESENT | Same gate; Save/Discard now `SettingsEditorActions` |
| M14 | Shared consumables collapsible (gate `canManage && machineServiceEnabled`): space-wide pool create form | `panels/MachinesPanel.tsx:243-245`, `machine/SharedConsumablesSection.tsx:39-53` | PRESENT | Same, draft lifted |
| M15 | Shared pool cards: stock band, % remaining, scope badge, remaining/initial, **Adjust stock** (`/consumable-pools/<id>/adjustments`), public toggle (`PATCH /consumable-pools/<id>`) | `machine/SharedConsumablesSection.tsx:54-180` | PRESENT | Same |
| M16 | Sole-type actor: type page rendered inline **and** settings block (M8/M13/M14) beneath it | `panels/MachinesPanel.tsx:126-127,235-247` | BURIED | Settings block moved into the type page's **Settings** tab (`?view=settings`, `MachinesPanel.tsx:160-165`, `MachineTypePage.tsx:62,90`) |
| M17 | Unknown/unreachable type deep link → redirect to index; skeleton while resolving | `panels/MachinesPanel.tsx:132-147` | PRESENT | Same logic |
| M18 | `?machine=<id>` deep link opens drawer; close clears param | `panels/MachinesPanel.tsx:64-66,249` | PRESENT | Same |
| M19 | Dashboard work queues (`?work_queue=`): **All machines** link, overdue maintenance rows linking to drawer Maintenance tab, paginated | `panels/DashboardMachineQueue.tsx:28-37` | PRESENT | `ListLayout` (secondary **All machines**, rows, pagination) |
| M20 | Dashboard print-job rows → **Open printer queue** | `panels/DashboardMachineQueue.tsx:34` | CHANGED | Link now `?view=queue`, which lands on the **Pending** status sub-tab (see M37) even for the "Active prints" / "Ready to collect" queues |

## 2. Machines — type page (`machine/MachineTypePage.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| M21 | **← All machine types** back link (only on a selected type) | `panels/MachinesPanel.tsx:163-167` | PRESENT | `DetailLayout back` |
| M22 | Description line "Machines, consumables and the service queue for X" | `panels/MachinesPanel.tsx:168-172` | CHANGED | Replaced by meta: type, N machines, N running |
| M23 | Status filter select (all/idle/running/reserved/maintenance/offline) | `panels/MachinesPanel.tsx:177-186` | PRESENT | Status tabs (`MachineTypePage.tsx:64-68`) |
| M24 | Machine rows: thumbnail, name, model, location, status, usage hours; click opens drawer | `machine/MachineTypePage.tsx:94-113` | PRESENT | `DataTable` (`MachineTypePage.tsx:71-77`) |
| M25 | Both empty states require a successful load ("No machines registered" / "No machines match status") | `machine/MachineTypePage.tsx:88-93` | PRESENT | `EmptyState`s + `DetailLayout state` |
| M26 | Inline **Add machine** form: name, make & model (printer types), location (`createMachine`) — gate `canManage && can_create_machine` | `machine/MachineTypePage.tsx:73-79`, `machine/MachineCreateForm.tsx:113-157` | BURIED | Header primary **Add machine** → `FlowLayout` dialog (`MachineTypePage.tsx:92-94,101`) |
| M27 | Post-create step: machine photo upload, warranty (purchased on, expires on, vendor name, vendor contact → `PUT /admin/machines/<id>/warranty`), **Done** | `machine/MachineCreateForm.tsx:160-215` | CHANGED | Dialog's `onCreated` calls `setCreating(false)` (`MachineTypePage.tsx:93`), unmounting the step before it renders. Photo/warranty are only reachable afterwards via drawer Overview + Warranty tab |
| M28 | Single submit button in create form | `machine/MachineCreateForm.tsx:150-156` | CHANGED | Dialog now shows two primaries: the form's own "Add <type>" and the footer **Add machine** |
| M29 | Certifications (gate `can_create_machine`): list with validity/required flags, **View/Hide grants**, **Edit type**, **Deactivate** (confirm) , **New certification type** form (name, description, validity days, required for service/booking) | `machine/CertificationsPanel.tsx:15-28`, `machine/CertificationTypeForm.tsx:10-16` | BURIED | **Certifications** tab |
| M30 | Certification grants: list, **Renew**, **Revoke** with reason, grant form (paginated member select, notes), grant paging | `machine/CertificationGrants.tsx:19-43` | BURIED | Certifications tab → View grants |
| M31 | Material catalogue & job intake (gate `canConfigure && material_catalogue/structured_intake`): list, activate/deactivate, add material (name, colours), intake schema JSON save / load | `machine/MaterialCataloguePanel.tsx:19-36`, `machine/MachineTypePage.tsx:117` | BURIED | **Settings** tab |
| M32 | Reminder policy (gate `canConfigure`): cert lead days, maintenance lead days, grace days, **Save policy** | `machine/MachineReminderPolicy.tsx:18-19`, `machine/MachineTypePage.tsx:118` | BURIED | **Settings** tab |
| M33 | Type consumables section (gate `machineServiceEnabled && canManage`): type/machine pool create form (material, colour selector + custom colour, brand, quantity, threshold, public) | `machine/MachineTypePage.tsx:122-127`, `machine/ConsumablePoolCreateForm.tsx:84-144` | BURIED | **Consumables** tab (heading/intro text dropped) |
| M34 | Type pool stock list with Adjust stock / public toggle | `machine/MachineTypePage.tsx:128-131` | BURIED | **Consumables** tab |
| M35 | Printer queue list: title, planned grams, status; all statuses visible at once | `machine/PrinterServiceConsole.tsx:110-118` | CHANGED | **Service queue** tab → `ServiceQueueTabs` defaults to **Pending** (`ServiceConsoleSections.tsx:25`); accepted / printing / ready jobs are hidden until another sub-tab is clicked |
| M36 | Queue empty state | `machine/PrinterServiceConsole.tsx:110-118` (no empty text) | CHANGED | "No jobs waiting" is shown when **Pending** is empty even while jobs are accepted/printing/ready |
| M37 | Jobs in `rejected` / `collected` / other terminal states | `machine/PrinterServiceConsole.tsx:111` | BURIED | Only under the **All jobs** sub-tab (status list `ServiceConsoleSections.tsx:5-10` has no tab for them) |
| M38 | **Accept**, **Start**, **Complete**, **Collect**, **Reprint** | `machine/PrinterServiceConsole.tsx:151-155` | PRESENT | Row right side |
| M39 | **Reject** (pending) and **Fail** (in progress) | `machine/PrinterServiceConsole.tsx:151,153` | BURIED | Row `OverflowMenu` |
| M40 | Action form (printer, pool, grams, notes per action) → `POST /machine-service/requests/<id>/<action>` | `machine/PrinterServiceConsole.tsx:94-100,119,158-163` | CHANGED | Opens in a `Modal` (draft persistence kept) |
| M41 | Manual usage form (printer, pool, grams, minutes, outcome, % complete) → `typed-manual-usage` | `machine/PrinterServiceConsole.tsx:75-90,122-124,166` | BURIED | Service queue tab → **Manual usage** sub-tab → **Log usage** modal (3 clicks) |
| M42 | Manual usage history list | `machine/PrinterServiceConsole.tsx:124` | BURIED | Manual usage sub-tab |
| M43 | Printer reports metrics (gate `printingEnabled && reportsEnabled`) | `machine/PrinterServiceConsole.tsx:126-133` | BURIED | Service queue tab → **Printer reports** sub-tab |
| M44 | Non-printer service console: metering hint, planned/actual quantity, Accept/Start/Complete/Collect | `machine/MachineServiceConsole.tsx:93-113,142-145` | PRESENT | Same buttons; queue subject to M35/M36 filter default |
| M45 | Non-printer Reject / Fail | `machine/MachineServiceConsole.tsx:142,144` | BURIED | Row overflow |
| M46 | Non-printer status sub-tab labels | n/a | CHANGED | Shared tabs say "Printing" / "Ready" for laser cutters etc. (`ServiceConsoleSections.tsx:8`) |
| M47 | Non-printer manual usage form + list | `machine/MachineServiceConsole.tsx:115-120,157` | BURIED | Manual usage sub-tab → **Log usage** modal |
| M48 | Service query/mutation errors | `machine/PrinterServiceConsole.tsx:136`, `machine/MachineServiceConsole.tsx:122` | PRESENT | Same `ErrorBlock` + per-modal error |

## 3. Machines — machine drawer (`machine/MachineDrawer.tsx` and its tabs)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| D1 | Header: status, Retired tag, type name, total hours | `machine/MachineDrawer.tsx:57-65` | PRESENT | `DetailLayout` status/meta + Usage StatCard |
| D2 | Tabs with gates: Maintenance (`maintenanceEnabled && can_operate`), Warranty (`can_edit`) | `machine/MachineDrawer.tsx:36-42,70-83` | PRESENT | Same `tabs` array |
| D3 | `detail_tab=Maintenance` deep link | `machine/MachineDrawer.tsx:30` | PRESENT | Same |
| D4 | Public detail disclosures (training, queue ETA) — gate `can_edit && machines.public_detail` | `machine/OverviewTab.tsx:79`, `machine/PublicMachineDisclosure.tsx:9-10` | PRESENT | Overview |
| D5 | Machine photo upload (`can_edit`) | `machine/OverviewTab.tsx:80-90` | PRESENT | Overview settings row |
| D6 | Edit name, location, firmware, camera feed URL, notes; **Save changes** (`updateMachine`) | `machine/OverviewTab.tsx:91-120` | PRESENT | Overview; Save/Discard bar shown only when `can_edit` |
| D7 | Status select + **Set status** (`can_operate`) | `machine/OverviewTab.tsx:121-133` | PRESENT | Overview; plus new header primary **Mark running/idle** |
| D8 | **Retire / Reactivate** (`can_retire` / `can_unretire`) | `machine/OverviewTab.tsx:134-137` | CHANGED | Moved to a `DangerZone` at the bottom of Overview; hidden (not disabled) without permission |
| D9 | Public listing toggle + "What's shown publicly" preview (`canManageMachines`) | `panels/MachinePublicSettings.tsx:56-80` | PRESENT | Overview `SettingsSection` |
| D10 | Operators list (username, access level) | `machine/OperatorsTab.tsx:51-63` | PRESENT | `ListRow`s |
| D11 | Operator **Remove** (`can_delegate`) | `machine/OperatorsTab.tsx:59-60` | BURIED | Row overflow |
| D12 | Add operator (member, access level) | `machine/OperatorsTab.tsx:65-90` | PRESENT | Same form |
| D13 | Consumables list: product/label, available or grams, Low flag, note | `machine/ConsumablesTab.tsx:150-157` | PRESENT | `ListRow` |
| D14 | Consumable **Unlink** (`can_edit`) | `machine/ConsumablesTab.tsx:155` | BURIED | Row overflow |
| D15 | Log consumable use per row (`can_operate`) | `machine/ConsumablesTab.tsx:158-168` | PRESENT | Same inline form |
| D16 | Link consumable form (measurement, product, label, starting grams, low threshold, note) | `machine/ConsumablesTab.tsx:79-121` | PRESENT | Same |
| D17 | Usage log list (hours, note, source, user, absolute timestamp) | `machine/UsageTab.tsx:38-52` | PRESENT | `ListRow`; timestamp now relative |
| D18 | Add usage (hours, note) | `machine/UsageTab.tsx:55-68` | PRESENT | Same |
| D19 | Maintenance calendar feed create/rotate/revoke (`maintenance.calendar_feed`) | `machine/MaintenanceTab.tsx:52`, `machine/MaintenanceFeedControl.tsx:7-11` | PRESENT | Same |
| D20 | Schedules: list + due state, Edit, Complete, Deactivate (confirm), New schedule incl. meter triggers | `machine/MaintenanceSchedules.tsx:91-185` | PRESENT | `ListRow` per schedule |
| D21 | Schedule completion form (summary, performed at, cost, parts, set idle) | `machine/MaintenanceTab.tsx:62-71,129-176` | PRESENT | Same |
| D22 | Log maintenance form (`can_operate && !retired`) | `machine/MaintenanceTab.tsx:72-74,209-251` | PRESENT | Same |
| D23 | History: summary, time, cost, parts note, attachments (view/delete/upload/retry finalize) | `machine/MaintenanceTab.tsx:75-105`, `machine/MaintenanceDocuments.tsx:62-110` | PRESENT | Same `<details>`; error state now has Retry |
| D24 | Documents list + **View** (signed URL) | `machine/DocumentsTab.tsx:49-60` | PRESENT | `ListRow` |
| D25 | Document **Delete** (`can_edit`) | `machine/DocumentsTab.tsx:62-63` | BURIED | Row overflow |
| D26 | Upload document (file, doc type) | `machine/DocumentsTab.tsx:69-85` | PRESENT | Same |
| D27 | Error logs list (severity, message, logged by, time) | `machine/ErrorsTab.tsx:32-46` | PRESENT | `ListRow` + pill; relative time |
| D28 | Add error log (severity, message) | `machine/ErrorsTab.tsx:48-62` | PRESENT | Same |
| D29 | Warranty tab (`WarrantySection`) | `machine/WarrantyTab.tsx:3-5` | PRESENT | Unchanged |

## 4. Devices (`panels/DevicesPanel.tsx`, `DeviceIdentitySection.tsx`, `DeviceEnrollmentModal.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| V1 | Create device inline (name, kind generic/printer/label printer) → enrollment grant | `panels/DevicesPanel.tsx:26`, `panels/DeviceIdentitySection.tsx:25-33` | BURIED | Header primary **Add device** → dialog (`DevicesPanel.tsx:31,48-50`) |
| V2 | Device table: name, kind, state (Active/Offline/status), last seen | `panels/DevicesPanel.tsx:31-38` | PRESENT | Rows: kind + relative last seen in meta, Online/Offline/Revoked pill |
| V3 | Pagination Previous/Next + "Page N \| count devices" | `panels/DevicesPanel.tsx:41-45` | PRESENT | `pagination` |
| V4 | 60 s auto-refresh of list and detail | `panels/DevicesPanel.tsx:17,23` | PRESENT | Same |
| V5 | List error + **Retry devices**; detail error + **Retry detail** | `panels/DevicesPanel.tsx:27-29,47-48` | PRESENT | `opsQueryState` error/retry |
| V6 | Select device → identity section below table | `panels/DevicesPanel.tsx:34,49` | CHANGED | Opens in a drawer |
| V7 | Fingerprint + key version | `panels/DeviceIdentitySection.tsx:55` | PRESENT | Section description |
| V8 | Rename + offline threshold, **Save identity** | `panels/DeviceIdentitySection.tsx:56-60` | PRESENT | Save/Discard bar appears when dirty |
| V9 | **Issue enrollment / Rotate key / Reactivate device** | `panels/DeviceIdentitySection.tsx:62-64` | PRESENT | Enrollment settings row |
| V10 | **Revoke device** + confirm | `panels/DeviceIdentitySection.tsx:65,69-71` | PRESENT | `DangerZone` + same `ConfirmDialog` |
| V11 | One-time enrollment modal: purpose, expiry, enrollment id, token, **Copy enrollment**, close discards | `panels/DeviceEnrollmentModal.tsx:7-19` | PRESENT | `FlowLayout` dialog, footer "I've copied it" |

## 5. Handover — job pickups (`panels/machine/HandoverConsole.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| H1 | List of completed jobs (`?status=completed`): title, requester, machine, finished time | `machine/HandoverConsole.tsx:64-82` | PRESENT | `ListRow`s; relative time |
| H2 | Payment line: Paid/Unpaid/Waived + currency amount | `machine/HandoverConsole.tsx:23-31,77-81` | PRESENT | `StatusPill` |
| H3 | **Hand over** → `POST /machine-service/requests/<id>/collect` | `machine/HandoverConsole.tsx:42-48,83-90` | PRESENT | Same; toast added |
| H4 | Loading / error / empty, collect error | `machine/HandoverConsole.tsx:56-62,97-101` | PRESENT | Layout states + callout |

## 6. Events — list and create (`EventsPanel.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| E1 | 403 "Permission required" / module-unavailable states | `EventsPanel.tsx:68-70` | PRESENT | `denied` empty state (`EventsPanel.tsx:73,90`) |
| E2 | Search | `ListViewControls.tsx:10` (old) | PRESENT | Toolbar search |
| E3 | Sort (starts first/last, title) | `EventsPanel.tsx:73` | PRESENT | `ListSort` |
| E4 | Saved views: choose, save current, previous/more pages, manage (share/make private/delete) | `SavedViewsMenu.tsx` (old `:34-43`) | BURIED | **Views** overflow; Manage → modal. Copy bug: items read "Save current view?" and "Manage views?" |
| E5 | "Clear selected result" (`id` filter) | `ListViewControls.tsx:9` (old) | PRESENT | Removable chip |
| E6 | Status filter (draft/published/cancelled/completed) | `EventsPanel.tsx:74` | BURIED | Inside the filter popover |
| E7 | Cross-makerspace event invitations inbox (accept/decline) | `EventsPanel.tsx:76`, `CollaborationInbox.tsx:45-53` | BURIED | Warn callout **Review** (only when an invite is `invited`) or "Review collaborations" button → drawer (`EventCollaborationReview.tsx`) |
| E8 | Recurring-series invitations inbox (accept/decline) | `EventsPanel.tsx:77`, `EventSeriesCollaborationInbox.tsx:48` | BURIED | Same drawer |
| E9 | One-time / Recurring creation toggle | `EventsPanel.tsx:78` | PRESENT | Header **New event** (primary) / **New series** (secondary) |
| E10 | Inline create-draft form (all `EventFields` / `EventSeriesFields`) + **Create event/series** | `EventsPanel.tsx:79-86` | BURIED | Separate `FormPageLayout` page with live preview (`EventsPanel.tsx:79-84`) |
| E11 | Create errors | `EventsPanel.tsx:84` | PRESENT | Same text |
| E12 | After create, open the new event / series | `EventsPanel.tsx:52-55,61-64` | PRESENT | Same |
| E13 | Recurring series list (title, next occurrence, buffered count, status) → series drawer | `EventsPanel.tsx:87` | BURIED | **Series** tab |
| E14 | Events table: title, date range, location, status, capacity ("Unlimited"), "N confirmed · N pending" | `EventsPanel.tsx:91-101` | PRESENT | Rows show all of it ("x / cap going", pending line, progress bar) |
| E15 | All events on the current page shown together | `EventsPanel.tsx:94` | CHANGED | Rows are split by **client-side** Upcoming / Drafts / Past tabs over one server page (`EventsPanel.tsx:75`): events on the page outside the tab are hidden ("No events in this section on this page"); a cancelled future event only appears under Past; combining with the status filter can empty every tab |
| E16 | Pagination with total | `EventsPanel.tsx:102-106` | PRESENT | `pagination` |
| E17 | Quick-create "event" | `EventsPanel.tsx:47` | PRESENT | Opens the create page |
| E18 | `?event=` deep link | `EventsPanel.tsx:42-45` | PRESENT | Same |

## 7. Events — event detail (`EventDrawer.tsx`; now a full page with tabs)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| E19 | Status badge | `EventDrawer.tsx:61` | PRESENT | Header status |
| E20 | "Recurring · <series title>" badge on an occurrence | `EventDrawer.tsx:61` | MISSING | Not rendered anywhere (`series_summary` is only read for a heading in `EventSettings.tsx:17,27`) |
| E21 | Capacity and Registration open/closed | `EventDrawer.tsx:61` | PRESENT | Meta "x / cap going" + At a glance card |
| E22 | Effective registration cutoff | `EventDrawer.tsx:62` | PRESENT | At a glance |
| E23 | Event photo upload | `EventDrawer.tsx:63` | BURIED | **Settings** tab |
| E24 | Category select + add category | `EventDrawer.tsx:66`, `EventCategoriesField.tsx:22-23` | BURIED | **Settings** tab |
| E25 | Edit all event fields (title, starts, ends, time zone, location, capacity, audience, tags, price, cancellation cutoff, registration cutoff modes, description, approval, public, custom form) + **Save changes** (diffed PATCH) | `EventDrawer.tsx:64-69`, `EventFormFields.tsx:57-73` | BURIED | **Settings** tab; Discard added |
| E26 | "Terminal events are read-only" | `EventDrawer.tsx:68` | PRESENT | Warn banner |
| E27 | Occurrence overrides: **Reset <field>** | `EventDrawer.tsx:70` | BURIED | **Settings** tab |
| E28 | **Publish** (draft) + confirm | `EventDrawer.tsx:72` | PRESENT | Header primary |
| E29 | **Complete** (published) + confirm | `EventDrawer.tsx:73` | BURIED | **Settings** tab → "Finish this event" |
| E30 | **Cancel event** (published) + confirm | `EventDrawer.tsx:73` | BURIED | **Settings** tab → DangerZone |
| E31 | Lifecycle/update error text | `EventDrawer.tsx:75` | PRESENT | Same |
| E32 | Invitations (gate `events.invites`): email, max uses, expires, one-time code reveal, list + revoke, paging | `EventInvitesPanel.tsx:15-24` | BURIED | **Tickets & invites** tab |
| E33 | Ticket types (gate `events.ticket_types`): name, price, audience, capacity, sales start/end, list, paging | `EventTicketsPanel.tsx:17-28` | BURIED | **Tickets & invites** tab |
| E34 | Promo codes (gate `events.promo_codes`): type, code, percent/amount, max redemptions, expiry, reveal, list + revoke, paging | `EventPromosPanel.tsx:17-28` | BURIED | **Tickets & invites** tab |
| E35 | Registrations roster with count | `EventDrawer.tsx:79`, `EventRegistrationRoster.tsx:51-52` | BURIED | **Registrations** tab (Overview also shows 5 latest + stat cards) |
| E36 | Staff "register a member" form (member search, ticket picker, invite code, promo, phone, email, custom answers) — gate published && registration open | `EventRegistrationRoster.tsx:56`, `EventRegisterMember.tsx:116-180` | BURIED | Registrations tab → **Add registration** toggle |
| E37 | Attendee badges: Preview, Download PDF (n), allow attended, template (paper, orientation, card w/h, printed fields, QR), **Save template** | `EventBadgeActions.tsx:66-82` | PRESENT | Registrations tab, same component |
| E38 | Per-row badge checkbox | `EventRegistrationRoster.tsx:66` | PRESENT | `DataTable` column |
| E39 | Name + payment reconcile (record / waive) | `EventRegistrationRoster.tsx:67` | PRESENT | Same |
| E40 | mailto / tel contact | `EventRegistrationRoster.tsx:68` | PRESENT | Same |
| E41 | Row actions: Cancel registration, Approve, Reject, Promote, Mark attended, Correct attendance | `EventRegistrationRoster.tsx:70-77` | PRESENT | Same buttons |
| E42 | Roster paging | `EventRegistrationRoster.tsx:81` | PRESENT | Same |
| E43 | Check-in operator inside the roster (gate published/completed) | `EventRegistrationRoster.tsx:57` | CHANGED | Moved to a **Check-in** tab (`showCheckIn={false}` on roster); header primary **Open check-in** when published |
| E44 | **Scan online** QR scanner (camera opened immediately) | `EventCheckInOperator.tsx:29`, `EventCheckInScanner.tsx` (old `:99-180`) | CHANGED | `ScanWorkbench`: camera is user-started ("Start scanning"), manual code entry and **Undo** added |
| E45 | Resolved guest: name, status, payment, waiver missing, blocked reason, **Confirm attendance**, **Scan another** | `EventCheckInScanner.tsx` (old `:117-166`) | PRESENT | Workbench result card |
| E46 | Offline check-in: Download/Refresh roster, Scan offline, Synchronize, Wipe attendee data (gate `offline_checkin_enabled`) | `EventCheckInOperator.tsx:30`, `OfflineCheckInOperator.tsx:135-143` | PRESENT | Check-in tab |
| E47 | PIN station: create/rotate PIN, open station, copy URL, disable, reveal PIN with password | `EventStationSettings.tsx:41-46` | PRESENT | Check-in tab |
| E48 | Feedback survey: title, thank-you, certificate toggle, question builder, **Save survey**, **Open/Close responses** | `EventFeedbackPanel.tsx:54-61` | BURIED | **Feedback** tab (header primary for completed events) |
| E49 | Feedback responses list + paging; certificate Download/Prepare, Revoke, Reissue | `EventFeedbackResponses.tsx:16-25`, `EventCertificateActions.tsx:18-26` | BURIED | **Feedback** tab |
| E50 | Organization organizers checkbox list + Save | `EventOrganizers.tsx:32-45` | BURIED | **Team** tab |
| E51 | Partner makerspaces: list with status, remove, add by slug | `EventCollaborators.tsx:74-100` | BURIED | **Team** tab |

## 8. Events — series detail (`EventSeriesDrawer.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| E52 | Status, N active occurrences, revision | `EventSeriesDrawer.tsx:43` | PRESENT | Header status + meta |
| E53 | "Automatic extension needs attention (<code>)" alert | `EventSeriesDrawer.tsx:44` | BURIED | Only rendered inside the **Settings** tab (`EventSeriesDrawer.tsx:51`); the default Occurrences tab gives no warning |
| E54 | Series photo upload | `EventSeriesDrawer.tsx:45` | BURIED | **Settings** tab |
| E55 | Edit future occurrences (all series fields incl. ticket templates) + **Save future occurrences** | `EventSeriesDrawer.tsx:46`, `EventSeriesForm.tsx:47-65`, `EventTicketTemplates.tsx:11-20` | BURIED | **Settings** tab; Discard added |
| E56 | **Publish series** | `EventSeriesDrawer.tsx:47` | PRESENT | Header primary (draft) |
| E57 | **Extend now** | `EventSeriesDrawer.tsx:47` | PRESENT | Header primary (published) |
| E58 | **Complete series** | `EventSeriesDrawer.tsx:47` | BURIED | **Settings** tab |
| E59 | **Cancel series** | `EventSeriesDrawer.tsx:47` | BURIED | **Settings** tab → DangerZone |
| E60 | Occurrences list → open one occurrence | `EventSeriesDrawer.tsx:49` | PRESENT | Default **Occurrences** tab |
| E61 | Series partners (list, add by slug) | `EventSeriesDrawer.tsx:50`, `EventSeriesCollaborators.tsx:41-42` | BURIED | **Team** tab |

## 9. Organized events (`panels/OrganizedEventsPanel.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| O1 | Intro "managed through your organization roles" | `panels/OrganizedEventsPanel.tsx:24-26` | PRESENT | Subtitle |
| O2 | Loading skeleton / error + **Retry** / empty | `panels/OrganizedEventsPanel.tsx:28-42` | PRESENT | `opsQueryState` |
| O3 | Columns: title, date range, location, status, registration totals breakdown, organizers name + slug | `panels/OrganizedEventsPanel.tsx:45-95,122-138` | PRESENT | Row meta/right (`OrganizedEventsPanel.tsx:21-37`) |
| O4 | Pagination "Page X of Y" (page size 50) | `panels/OrganizedEventsPanel.tsx:98-108` | PRESENT | `pagination` |
| O5 | Open the host makerspace's event detail | `panels/OrganizedEventsPanel.tsx:110-117` | PRESENT | Full event page (all tabs from §7) |

## 10. Bookings — spaces list (`BookingsPanel.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| B1 | 403 / module-disabled messages | `BookingsPanel.tsx:42-43` | PRESENT | Empty-state message |
| B2 | Quick-create "booking" → "Choose a space below…" hint | `BookingsPanel.tsx:33,47` | PRESENT | Subtitle swap |
| B3 | Header **New booking** | n/a (new) | CHANGED | Secondary button only swaps the subtitle text (`BookingsPanel.tsx:40`); no booking flow starts — a dead-end affordance |
| B4 | Search, sort (name, name desc, type) | `BookingsPanel.tsx:48` | PRESENT | Toolbar |
| B5 | Saved views | `BookingsPanel.tsx:48` | BURIED | **Views** overflow (see E4) |
| B6 | **Create space** | `BookingsPanel.tsx:51` | PRESENT | Header primary **New space** |
| B7 | Columns: name + location, type, approval, public, active | `BookingsPanel.tsx:14-25` | PRESENT | Row meta + pills |
| B8 | Clickable sortable "Space" column header | `BookingsPanel.tsx:18,54` | CHANGED | Sort only via the dropdown |
| B9 | List error, loading, empty | `BookingsPanel.tsx:53-54` | PRESENT | Layout states + filtered-empty |
| B10 | Pagination with total | `BookingsPanel.tsx:55` | PRESENT | `pagination` |
| B11 | Create-space modal (all space fields, Cancel) → opens new space | `BookingsPanel.tsx:56-65` | CHANGED | Full `FormPageLayout` page (`BookableSpaceForm` `mode="create"`); same fields and redirect |

## 11. Bookings — space detail (`BookingDrawer.tsx`, `BookableSpaceForm.tsx`, `StaffBookingForm.tsx`)

| # | Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|---|
| B12 | Active/Inactive badge + "Requester emails on/off" | `BookingDrawer.tsx:73-76` | PRESENT | Header status + meta (location added) |
| B13 | Edit space: name, type, capacity, machine type (paged), location, description, booking price, requester email, public, publish intervals, booker names, custom form builder; **Save changes** | `BookingDrawer.tsx:77-86`, `BookableSpaceForm.tsx:85-141` | BURIED | **Settings** tab; save bar only when dirty |
| B14 | **Deactivate space** + confirm | `BookingDrawer.tsx:87,159` | BURIED | **Settings** tab → DangerZone |
| B15 | "This space is inactive and read-only" | `BookingDrawer.tsx:87` | PRESENT | Settings tab |
| B16 | Staff booking form (gate `is_active`): paginated member select, start, end, recurring weekly count/interval (gate `bookings.recurring`), staff note, certification override reason, custom fields, **Create booking**, recurring results list | `BookingDrawer.tsx:89`, `StaffBookingForm.tsx:41-63` | BURIED | Header primary **New booking** → modal |
| B17 | "Bookings (N)" + staff-only note | `BookingDrawer.tsx:90-93` | BURIED | **Requests** tab |
| B18 | Sort (starts first/last, created first) | `BookingDrawer.tsx:94` | BURIED | **Requests** tab |
| B19 | Filters: status, starts after, ends before | `BookingDrawer.tsx:95-113` | BURIED | **Requests** tab |
| B20 | Booking card: name, time range, status, mailto/tel, custom answers, payment reconcile | `BookingDrawer.tsx:119-137` | BURIED | **Requests** tab (same content) |
| B21 | **Approve** (pending), **Complete** (confirmed & ended) | `BookingDrawer.tsx:168,170` | PRESENT | Visible row button in Requests tab |
| B22 | **Reject**, **Cancel**, **No-show** | `BookingDrawer.tsx:168-170` | BURIED | Row overflow |
| B23 | Booking action confirm dialog + errors | `BookingDrawer.tsx:145,149-158` | PRESENT | Same |
| B24 | Pagination | `BookingDrawer.tsx:143` | PRESENT | `Pagination` |
| B25 | `?space=&booking=` deep link filters to one booking | `BookingDrawer.tsx:53` | PRESENT | Opens Requests tab; **Show all bookings** added |
| B26 | (new) **Calendar** tab as default | n/a | CHANGED | `BookingAgenda` reuses the Requests query (`BookingDrawer.tsx:93`), so it silently inherits the status/date filters and the single-`booking_id` deep-link filter, starts at the oldest booking (past included) and is page-bounded — it is not a calendar of upcoming bookings |

---

## Counts

| Page | PRESENT | BURIED | CHANGED | MISSING |
|---|---|---|---|---|
| Machines index (M1-M20) | 16 | 1 | 3 | 0 |
| Machine type page (M21-M48) | 7 | 14 | 7 | 0 |
| Machine drawer (D1-D29) | 25 | 3 | 1 | 0 |
| Devices (V1-V11) | 9 | 1 | 1 | 0 |
| Handover (H1-H4) | 4 | 0 | 0 | 0 |
| Events list (E1-E18) | 11 | 6 | 1 | 0 |
| Event detail (E19-E51) | 15 | 15 | 2 | 1 |
| Series detail (E52-E61) | 4 | 6 | 0 | 0 |
| Organized (O1-O5) | 5 | 0 | 0 | 0 |
| Bookings list (B1-B11) | 7 | 1 | 3 | 0 |
| Space detail (B12-B26) | 6 | 8 | 1 | 0 |
| **Total (184)** | **109** | **55** | **19** | **1** |

The one MISSING capability is E20. The parity problem is mostly **reach**, not deletion: 55
capabilities moved behind a tab, overflow, dialog or toggle, and 19 changed behaviour. Several of
the CHANGED rows make data *look* absent when it is not: M35/M36 (service queue), E15 (event tabs)
and B26 (booking calendar).

---

## Restore list (severity-ordered)

Yuyu rule applied throughout: one header primary, frequent actions visible on the row or page,
rare or destructive ones in the overflow.

### High — operators will believe work or data is gone

1. **Service queue hides active jobs (M35, M36, M37, M46, M20).** `ServiceQueueTabs`
   (`panels/machine/ServiceConsoleSections.tsx:16-31`) defaults to `"pending"` and shows "No jobs
   waiting" when only Pending is empty. Restore the old behaviour from
   `d3e5ed29:…/PrinterServiceConsole.tsx:110-118` (every request listed): default to an
   **Active** tab (`pending + accepted + in_progress + completed`), keep All jobs, add the terminal
   statuses, and use neutral labels ("In progress", "Ready") for non-printer types. Have
   `DashboardMachineQueue` deep-link the matching tab (`?view=queue&job_status=in_progress|completed`).
2. **Event list tabs filter a single server page (E15, E6).** `EventsPanel.tsx:75` filters
   `events.data.results` client-side. Either push the tab to the API (status + `ends_at` range
   params on `useEvents`) or bring back the old single list (`d3e5ed29:…/EventsPanel.tsx:91-101`)
   under an **All** tab as the default, and make the status filter the tab set rather than a
   popover control.
3. **Booking "Calendar" tab inherits Requests filters (B26).** Give `BookingAgenda` its own
   `useSpaceBookings(spaceId, { starts_at: now }, page, "starts_at")` query, without the
   status or `booking_id` filters, or make **Requests** the default tab again. The Requests list
   *is* the old drawer body (`d3e5ed29:…/BookingDrawer.tsx:88-144`), so nothing else needs to
   come back.
4. **Machine create loses the photo/warranty step (M27, M28).** In `MachineTypePage.tsx:93`,
   stop calling `setCreating(false)` inside `onCreated`. Keep the dialog open so
   `MachineCreateForm`'s post-create block (`MachineCreateForm.tsx:160-215`) renders, and close it
   from that block's **Done**. Hide the form's internal submit button (as `DeviceCreateForm` does
   with `hidden`) so the footer is the only primary.

### Medium — reachable but at the wrong depth or without a signal

5. **Series extension-failure alert (E53).** Move the `last_generation_error_code` alert from
   the Settings tab body (`EventSeriesDrawer.tsx:51`) into `DetailLayout banner` (tone danger,
   action **Extend now**) so it shows on every tab, as it did at
   `d3e5ed29:…/EventSeriesDrawer.tsx:44`.
6. **Recurring badge on occurrences (E20).** Bring back the
   `Recurring · {event.series_summary.title}` chip from `d3e5ed29:…/EventDrawer.tsx:61` as a
   `DetailLayout status` sibling or a meta item. Ideally make it a link that opens the series
   (`setSelectedSeriesId`).
7. **Event Complete / Cancel, Series Complete / Cancel (E29, E30, E58, E59).** Keep the Settings
   DangerZones and also add `actions.overflow` entries on the detail header ("Complete event",
   "Cancel event"; "Complete series", "Cancel series") for published items. Ending an event is
   routine on event day, not a settings task.
8. **Bookings list "New booking" (B3).** Wire it to a space-picker step that opens the chosen
   space's `StaffBookingForm` modal, or remove the button and keep the quick-create hint only.
9. **Manual usage / Printer reports depth (M41-M43, M47).** On the Service queue tab, add
   **Log usage** as a `DetailLayout actions.secondary`, so logging takes one click from the type
   page instead of three. Keep reports as a sub-tab.
10. **Pool-load error on the index (M7).** Pass the pool error to the index `ListLayout callout`
    as `MachineTypePage` already does, restoring `d3e5ed29:…/MachinesPanel.tsx:195-197`.
11. **Sole-type settings (M16).** Acceptable as a **Settings** tab, but the tab only appears
    when `settings` is non-null. Verify a scoped maintainer with one type and no
    `canConfigureMachineTypes` still sees it (they need M13/M14).

### Low — polish and copy

12. **Saved-views menu labels.** Remove the stray "?" from "Save current view?" and "Manage views?"
    (`SavedViewsMenu.tsx`). This affects Events, Bookings and every other list.
13. **Type icon on the index cards (M4).** Use `machineType.icon` when set (old
    `MachineTypeCards.tsx:82`) and fall back to `Cog`.
14. **Machine status sub-tab copy (M46).** Covered by item 1.
15. **Overflowed destructive actions are fine.** Reject/Fail (M39, M45), Unlink (D14), Delete
    (D25), Remove (D11) and Reject/Cancel/No-show (B22) match the Yuyu rule. No restore is needed.
