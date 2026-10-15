## Must fix

For strict functional parity:

- **P2 — Restore “Show all request queues.”** HEAD only presents one queue at a time.
- **P2 — Restore “Show all accountability sections.”** Clearing `section` now opens Overdue instead of the combined view.
- **P2 — Restore navigation shortcuts.** The member portal’s Arrow/Home/End shortcuts and staff dock’s arrow navigation have no replacement.

**No P0/P1 loss, missing endpoint/method pair, newly dead API caller, or removed confirmation was found.** Individual domain operations remain reachable. The three findings above are presentation and keyboard capabilities; they may be deliberate redesign decisions.

Audited **`d3e5ed29` → `08de077b360208a8c3bda93bdc5517456c8c8dcb`**. HEAD advanced during the audit; the additional changes were reviewed. All paths below are relative to **`frontend/src/`**.

The read-only comparison covered 594 old and 739 new source files, 610 old and 620 new matching API calls, all 56 route declarations, extracted controls/action labels, URL-state readers, confirmation sites, and permission predicates. Generated files, tests, styles, and cosmetic class changes were excluded. This was static analysis, without browser execution.

## 2. Endpoint/method pairs removed

**None found.** Compared literal paths, interpolated paths, helper-built paths, and action-dependent methods. Generic request wrappers were traced to their supplied paths.

| Capability | Old file:line | HEAD status/file:line | Severity P0/P1/P2 | Suggested minimal fix |
|---|---|---|---|---|
| Pending, accepted, active, and historical request reads | `features/staff/panels/RequestQueues.tsx:94`, `:105`, `:116`, `:127` | Preserved through `useRequestQueues.ts:18`–`:21`; GET paths retain the same suffixes | — | None |
| Request accept/reject, box assignment, issue, return, and due-date changes | `features/staff/panels/RequestQueues.tsx:134` | Shared POST dispatcher remains at `RequestQueues.tsx:97`; action-specific paths remain supplied by handlers | — | None |
| Remaining API inventory | All 610 extracted old call sites | No OLD-only endpoint/method pair after accounting for moved callers and shared helpers | — | None |

## 3. Mounted callers and dead code

**No newly dead API-calling component was found.** Several old presentation components became dead code, but their operations have mounted replacements.

| Capability | Old file:line | HEAD status/file:line | Severity P0/P1/P2 | Suggested minimal fix |
|---|---|---|---|---|
| Pending-request Accept/Reject/Set due | `features/staff/panels/QueuesDisplay.tsx:6`; mounted from `RequestQueues.tsx:200` | Old renderer unused; replacement actions in `RequestQueues.tsx:168`, `:177`, `:219`, rendered through `QueuesList.tsx:65` | — | None for functionality |
| Accepted-request assignment and issue | `features/staff/panels/QueuesDisplay.tsx:10`; `RequestQueues.tsx:206` | Mounted replacement at `RequestQueues.tsx:170`; quick form remains in its menu at `:178` | — | None |
| Return and renewal | `features/staff/panels/QueuesDisplay.tsx:14`; `RequestQueues.tsx:212` | Mounted replacement at `RequestQueues.tsx:173`; renewal remains at `:220` | — | None |
| Request history | `features/staff/panels/QueuesDisplay.tsx:18`; `RequestQueues.tsx:217` | Old `HistoryPanel` unused; History tab/query preserved at `requestTabs.ts:1` and `useRequestQueues.ts:21` | — | None |
| Evidence photos and timeline | `features/staff/panels/QueuesList.tsx:44`, `:78`, `:81` | Reachable through `QueuesList.tsx:52`, `:53`, `:70` → `RequestDetail.tsx:30` | — | None |

## 4. Routes, tab keys, and URL parameters

All old route paths and staff tab keys remain. No old query-state key was removed outright. Two old **combined-view meanings** are no longer honoured.

| Capability | Old file:line | HEAD status/file:line | Severity P0/P1/P2 | Suggested minimal fix |
|---|---|---|---|---|
| **Combined request queues**, including clearing `queue` | `features/staff/panels/RequestQueues.tsx:82`, `:195`, `:199` | `requestTabs.ts:26` resolves an empty queue to the first visible tab; `useRequestQueues.ts:15` enables only the selected queue | **P2** | Restore an explicit All queues mode using the former combined rendering |
| **Combined accountability view** with absent/empty `section` | `features/staff/panels/AccountabilityPanel.tsx:20`, `:21`, `:57` | `AccountabilityPanel.tsx:21`–`:27` defaults to Overdue; sections render individually | **P2** | Add All sections and preserve empty `section` as that mode |
| React Router paths | `AppRoutes.tsx:89` | Same 56 route declarations; route block at `AppRoutes.tsx:99` | — | None |
| Staff route/tab keys | `features/staff/staffTabs.ts:1`; `staffAccess.ts:1` | Both registries retained | — | None |
| Legacy request `id`, `history`, and queue pagination parameters | `features/staff/panels/RequestQueues.tsx:81` | Still interpreted by `requestTabs.ts:20` and `useRequestQueues.ts:7` | — | None |
| Other old search-param readers and list-state defaults | Old `useSearchParams`/`useUrlListState` inventory | Retained or forwarded to extracted components/hooks; no additional missing key found | — | None |

## 5. Vanished controls and handlers

Renamed controls and actions moved into menus, drawers, or detail pages were excluded.

| Capability | Old file:line | HEAD status/file:line | Severity P0/P1/P2 | Suggested minimal fix |
|---|---|---|---|---|
| **“Show all request queues”** | `features/staff/panels/RequestQueues.tsx:195` | No equivalent combined-view handler; only individual tabs at `RequestQueues.tsx:204` | **P2** | Restore the combined-view action described in §4 |
| **“Show all accountability sections”** | `features/staff/panels/AccountabilityPanel.tsx:57` | No All action among `AccountabilityPanel.tsx:21`–`:26` | **P2** | Restore the combined-view action described in §4 |
| **Member navigation ArrowLeft/ArrowRight/Home/End shortcuts** | `features/members/MemberPortalTabs.tsx:34`, `:48` | Navigation destinations remain, but `MemberPortalTabs.tsx:35` delegates to ordinary shell links; `components/shell/SidebarItem.tsx:9` and `BottomTabs.tsx:9` have no equivalent keyboard handler | **P2** | Add equivalent navigation shortcut handling to the replacement navigation |
| **Staff dock arrow navigation** between groups and entries | `features/staff/StaffDock.tsx:139`, `:145`; `StaffDockPopover.tsx:73` | Dock removed; replacement `components/shell/SidebarItem.tsx:9` lacks equivalent arrow handling | **P2** | Restore arrow navigation in the sidebar/disclosures |

No additional vanished button/link action was found after tracing its replacement handler.

## 6. Destructive-action confirmations

**No lost confirmation found.** All 26 old `ConfirmDialog`/`confirm()` sites were accounted for, including non-destructive confirmation variants sharing those dialogs.

| Capability | Old file:line | HEAD status/file:line | Severity P0/P1/P2 | Suggested minimal fix |
|---|---|---|---|---|
| Change answer type, clearing choices | `features/forms/CustomFormBuilder.tsx:147` | Same dialog at `:147` | — | None |
| Create/rotate/revoke calendar subscription | `features/members/MemberCalendarActions.tsx:59`, `:75` | Both browser confirmations retained at the same lines | — | None |
| Reject/cancel/no-show booking | `features/staff/BookingDrawer.tsx:149` | Shared action dialog at `BookingDrawer.tsx:104` | — | None |
| Deactivate bookable space | `features/staff/BookingDrawer.tsx:159` | Dialog at `:114` | — | None |
| Cancel event | `features/staff/EventDrawer.tsx:85` | Dialog at `:107` | — | None |
| Cancel recurring series | `features/staff/EventSeriesDrawer.tsx:53` | Dialog at `:67` | — | None |
| Unlink makerspace/change organization reach | `features/staff/OrganizationSetup.tsx:36` | Dialog at `:38` | — | None |
| Quiesce/archive/recover migration source | `features/staff/TenantMigrationExports.tsx:140`, `:143`, `:155` | Confirmation calls at `:152`, `:155`, `:167`; typed-name dialog in `MigrationConfirmation.tsx:10` | — | None |
| Activate/abort migration target | `features/staff/TenantMigrationImports.tsx:165`, `:168` | Confirmation calls at `:154`, `:157`, using `MigrationConfirmation.tsx:10` | — | None |
| Delete category | `features/staff/panels/Categories.tsx:208` | Dialog at `:188` | — | None |
| Revoke device | `features/staff/panels/DeviceIdentitySection.tsx:69` | Dialog at `:73` | — | None |
| Reset email template | `features/staff/panels/EmailTemplateEditor.tsx:196` | Dialog at `:175` | — | None |
| Archive inventory item | `features/staff/panels/InventoryWorkspace.tsx:279` | Action confirmation in `InventoryColumns.tsx:32` and `InventoryItemDetail.tsx:46`, rendered by shared action controls | — | None |
| Disable/enable public QR | `features/staff/panels/InventoryWorkspace.tsx:280` | Dialog at `:251` | — | None |
| Delete report schedule | `features/staff/panels/ReportSchedules.tsx:151` | Dialog at `:152` | — | None |
| Delete role | `features/staff/panels/RoleManager.tsx:60` | Dialog retained at `:60` | — | None |
| Restore access/revoke staff role | `features/staff/panels/Users.tsx:255`, `:264` | Dialogs at `:270`, `:279` | — | None |
| Revoke/renew certification | `features/staff/panels/machine/CertificationGrants.tsx:46` | Dialog at `:47` | — | None |
| Deactivate certification type | `features/staff/panels/machine/CertificationsPanel.tsx:30` | Dialog at `:32` | — | None |
| Delete maintenance attachment | `features/staff/panels/machine/MaintenanceDocuments.tsx:116` | Dialog retained at `:116` | — | None |
| Deactivate maintenance schedule | `features/staff/panels/machine/MaintenanceSchedules.tsx:193` | Dialog at `:182` | — | None |

`confirms: true` alone only adds an ellipsis. The preserved cases above were checked through to an actual dialog or browser confirmation.

## 7. Permission gates

No loosened authorization gate was found. Two presentation gates became tighter; neither establishes a lost authorized API operation from this frontend-only audit.

| Capability | Old file:line | HEAD status/file:line | Severity P0/P1/P2 | Suggested minimal fix |
|---|---|---|---|---|
| Request queue visibility | `features/staff/panels/RequestQueues.tsx:95`, `:106`, `:117`, `:128` | **Tightened:** `requestTabs.ts:9`–`:17` additionally requires `accept_request` for Pending and `issue_request` for Accepted/Active/History. Old `guestOnly` restrictions remain | **P2 — gate delta** | Retain only if these are the intended queue-read permissions; otherwise restore visibility for separately authorized roles |
| Item-detail “Request from the catalogue” link | `features/inventory/PublicItemPage.tsx:60` | **Tightened:** requires `request_workflow` at `PublicItemPage.tsx:59`. Catalogue remains reachable through shared navigation at `PublicPageChrome.tsx:10` | **P2 — gate delta** | No operational fix needed; remove the extra gate only if exact link parity is required |
| Staff access and module-filtered route eligibility | `features/staff/staffAccess.ts:85`; `staffTabs.ts:1` | Existing access/module registries retained; replacement sidebar consumes the filtered set at `sidebarSections.ts:40` | — | None |
| Inventory audit/history visibility | `features/staff/panels/InventoryWorkspace.tsx:256`, `:257` | Same `canViewAudit` gate in `InventoryItemDetail.tsx:20`, `:42`, `:43` | — | None |
| Broadcast composition | `features/staff/panels/NotificationInbox.tsx:7` | Same member-management plus feature predicate, extracted into `canBroadcast` at `NotificationInbox.tsx:9` | — | None |
| Machine configuration, certifications, service and consumables | `features/staff/panels/machine/MachineTypePage.tsx:73`, `:116`, `:117`, `:120` | Same authority/module predicates retained at `MachineTypePage.tsx:65`, `:94`, `:96`, `:110`; visibility now selects tabs | — | None |
| Member portal module eligibility | `features/members/MemberPortalTabs.tsx:9` | Same `memberTabs` predicate at `MemberPortalTabs.tsx:10` | — | None |

No other old permission/feature/module check was found guarding a different capability after following extracted components and their props.