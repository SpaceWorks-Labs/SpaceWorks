# Final parity audit: Inventory area (staff console)

Read-only research, 2026-10-16. **Old** = `d3e5ed29`. **New** = HEAD `b348ee18` (clean tree, no uncommitted edits in this area).
Paths are relative to `frontend/src/features/staff/panels/` unless prefixed. Old line numbers come from `git show d3e5ed29:<path>`.
Earlier checklist: `docs/design-revamp/research/parity-inventory.md` (19 restore items).

**Summary:** 167 capabilities traced: **146 PRESENT, 9 BURIED, 12 CHANGED, 0 MISSING**. Restore list: **0 P0, 1 P1, 9 P2** (P2 #9 and #10 are informational).

Earlier restore list (19 items): **17 verified fixed**, **1 partly fixed** (#3, stocktake Complete), **1 n/a** (#19, no action was asked). Nothing from the old P0/P1 set is still open except the partial #3.

Method notes: every old file in the area was diffed against its new counterpart, and every mounted route was traced through `StaffTabContent.tsx` (the file is unchanged for these tabs; `staffAccess.ts` and `staffTabs.ts` are untouched since `d3e5ed29`, so **no gate changed**). I ran `npx vitest run` on the inventory, QR, scanner, transfer, stocktake, bulk-import, reorder and archive tests: 12 files, 35 tests, all green.

Two facts that changed since the earlier audit and drive most of the "fixed" verdicts:

- `Action.confirm` now exists and opens a `ConfirmDialog` (`components/ui/types.ts:11`, `ActionControl.tsx:11,29-31`, `OverflowMenu.tsx:36,46-48`). Earlier, `confirms` only appended an ellipsis. `DangerZone` forwards it (`DangerZone.tsx:10`).
- `Action.confirms` without `confirm` still only appends "…". Every remaining "…" label in this area was checked: each one opens its own dialog or modal (Move to repair shelf, Add to To buy, Scrap, Delete to-buy item, Delete receipt, Delete category, Apply adjustments, Revoke QR). None runs immediately.

---

## Restore list

### P0 — capability unreachable, destructive action lost its confirmation, or a gate changed

**None.** Checked specifically:

| Destructive or hard-to-undo action | Confirmation now | Where |
|---|---|---|
| Archive item (row, drawer) | `ConfirmDialog` plus undo toast | `InventoryColumns.tsx:32-33`, `InventoryItemDetail.tsx:46` |
| Bulk Enable/Disable public QR | `ConfirmDialog` | `InventoryWorkspace.tsx:251` |
| Scrap units | `ConfirmDialog` (new, old had none) | `NeedsFixShelf.tsx:46` |
| Delete category (old confirm kept) | `ConfirmDialog` | `Categories.tsx:188` |
| Delete to-buy item (new confirm) | `ConfirmDialog` | `ProcurementPanelRows.tsx:116` |
| Cancel to-buy request | `confirm` object | `ProcurementPanelRows.tsx:98-99` |
| Delete receipt, remove warranty doc (new confirms) | `ConfirmDialog` | `ProcurementReceipts.tsx:90`, `WarrantySection.tsx` (diff) |
| Revoke QR (new confirm) | `ConfirmDialog` | `ScannerPanel.tsx:99,104` |
| Apply stocktake adjustments (new confirm) | `ConfirmDialog` | `StocktakeSessionPanel.tsx:84` |
| Bulk import apply | Review step before apply | `BulkImport.tsx:117` |

Gates compared with old, all unchanged: Inventory (`canViewAudit`, `canUseToBuy`), needsfix/categories/stocktake/bulk (`canEditInventory`), containers/qr/scanner (`canManageQr`), transfers (`canEditInventory || isSuperadmin`), warranty (`canEditInventory || canSeePrinting`, row `canManageRow` identical), Stocktake approve/apply predicates (`StocktakeSessionPanel.tsx:72-73` equal old `:90-95`), Stocktake policy (`discipline && canConfigure`), Scanner rebind/move predicates (`useStaffScanner.ts:175-180` equal old), kit editor (`loans.kit_checklist`), asset-units QR gate.

### P1 — frequent need, degraded or buried

**1. Evidence-trail histories show only relative time ("3 days ago"); the exact timestamp is only a hover tooltip.**
- Old: custody and loan timeline `... on {formatDate(event.at)}` (`LoanTimeline.tsx` old EventList), lending history `formatDate(entry.issued_at)` (`InventoryPanelParts.tsx` old `:158-181`), product/asset QR history `formatDate(scan.created_at)` (old `:81`), container scan history `new Date(...).toLocaleString()` (`ContainersPanel.tsx` old `:115`), receipts and to-buy ordered/received `formatDateTime` (old `ProcurementReceipts.tsx`, `ProcurementPanelRows.tsx:87-88`).
- New: all of these render `<RelativeTime>` (`ActivityItem.tsx:9`, `InventoryPanelParts.tsx:62,125`, `ContainerDetail.tsx:88`, `ProcurementReceipts.tsx:68`, `ProcurementPanelRows.tsx:107`, `Ledger.tsx:107`). `RelativeTime.tsx:27` puts the absolute value in `title=`, which phones and keyboards never show. Beyond 2 days it reads "5 days ago".
- Why it matters: SpaceWorks exists to prove who held what and when. The admin audit log was already fixed this way (`AuditLog.tsx:44` shows `toLocaleString()` plus relative, commit `a1847395`). These inventory-side trails were not.
- Minimal fix: give `RelativeTime` an `absolute` prop that renders `"{relative} · {toLocaleString()}"` (or `ActivityItem` a second line), and pass it from `ActivityItem` (custody timeline, covers `EventList`), `QrHistory`, `LendingHistory`, container history, and the receipt/ordered/received rows. Ledger "Out since" and transfer "created" are the same pattern; do them in the same sweep.

### P2 — minor, optional

**2. Stocktake "Complete count" is only on the session page.** Old: row button (`StocktakeSessionPanel.tsx` old `:87-89`). New: `StocktakeSessionPanel.tsx:103` hides `nextAction` for any row where `canCount(status)`, so counting rows show only "Continue". Approve and Apply were restored to the list; Complete was not. Fix: `const next = row.status === "counting" || !canCount(row.status) ? nextAction(row) : undefined`, and keep "Continue" beside it.

**3. Chain of custody tab still needs an inner "Open" click.** `InventoryItemDetail.tsx:43` mounts `ChainOfCustodyBlock`, whose `useState(false)` (`LoanTimeline.tsx:51`) keeps it collapsed behind a second control, although the person already chose the "Custody" tab. Fix: add `defaultOpen` to `ChainOfCustodyBlock` (same pattern as `QrHistory defaultOpen`) and pass it here.

**4. Inventory sort on phones offers 4 options, the table headers offer 8.** `InventoryWorkspace.tsx:221` gives the toolbar select only name and available. On desktop the DataTable headers sort by total, issued, damaged, lost and mode (`InventoryColumns.tsx:15-20`); on phones headers are screen-reader only when `ordering` is supplied (`DataTable.tsx:70-71`). Old table sorted every column on every width. Fix: add `total_quantity`, `issued_quantity`, `damaged_quantity`, `lost_quantity`, `tracking_mode` (both directions) to the `sorts` prop. (Damaged and lost are hidden on phone cards by `max-md:hidden`, `InventoryColumns.tsx:20`; I confirmed with the Tailwind 4.3 compiler that `max-md:hidden` is emitted after `max-md:flex`, so it wins over the `detail` role's flex. They stay reachable in the drawer Stock tab.)

**5. Bulk import: a stale file-job result can show on a pasted-table review.** `BulkImport.tsx:64` returns the `activeJob` result whenever `activeJob` exists, and `activeJob = jobQuery.data ?? jobMutation.data` (`:62`). If the user previews a file, clicks Back, switches to pasted text and previews, `jobMutation.data` is still set and the old file's result is shown instead of `syncMutation.data`. Found by reading, not reproduced. Fix: call `jobMutation.reset()` in the paste-table `onChange` (`:124`) and in `submitRows`, or choose `syncMutation.data` when `source !== "file"`.

**6. Sidebar names disagree with page titles.** `sidebarSections.ts:25-26` labels "Items", "Repair shelf", "QR tools"; the pages are titled "Inventory" (`InventoryWorkspace.tsx:215`), "To be fixed" (`NeedsFixShelf.tsx:33`), "QR labels" (`QrTools.tsx:24`); `TAB_LABELS` still says "Inventory", "To-be-fixed", "QR Tools". Wayfinding only. Pick one name per page.

**7. Inventory view tabs are mutually exclusive.** Old let "Show archived" and "Low stock" combine; the four tabs (`InventoryWorkspace.tsx:219`) do not. The dashboard deep link `?archived=all&out_of_stock=true` still queries "active and archived" (`:64`) but the page no longer says so (old note `IW:238`). Add a one-line note when `archived=all`.

**8. Scanner keeps the empty-state card next to a resolved result.** `ScannerPanel.tsx:19-24` puts the result in `controls` rather than the workbench `result` slot, so "Scan a QR code or find an item to get started." (`ScanWorkbench.tsx:54`) renders above a resolved target. Cosmetic.

**9. Still one or two clicks deeper than before, all rare, all acceptable:** row "Move to repair shelf" (`InventoryColumns.tsx:30`, was a visible "To Fix"), asset "QR history" (`InventoryPanelParts.tsx:107`) and the QR image behind "Show QR" (`:102`), container-asset "Warranty" (`ContainerDetail.tsx:109`), Stocktake "Count policy and schedule" (`StocktakeSessionPanel.tsx:93`), to-buy Export (`ProcurementPanel.tsx:140`), to-buy vendor/actual cost/status editing in the drawer (`ProcurementPanelRows.tsx:108-110`, with Mark received opening it pre-set, `:278-281`). No change needed.

**10. Informational, not a regression:** bulk import can no longer apply without a preview, and JSON/file applies run only from the Review step (`BulkImport.tsx:117`). The earlier P0 (error rows blocking apply) is fixed: the button reads "Import N valid rows, skip M" (`:114`). Container creation has no parent-container field though `POST /admin/qr/boxes` accepts `parent_id` (`backend/apps/boxes/api_views_qr.py:69`); there was no create UI at all before.

---

## Verification of the earlier restore list

| # | Item | Verdict | Evidence in HEAD |
|---|---|---|---|
| 1 | Archive confirmation | FIXED | `InventoryColumns.tsx:32-33`, `InventoryItemDetail.tsx:46`, `ActionControl.tsx:11,29`, `OverflowMenu.tsx:36,46` |
| 2 | Bulk import partial apply and parser message | FIXED | `BulkImport.tsx:114-115` (enabled with `result`, "skip N"), `:103` (parser message kept) |
| 3 | Stocktake Complete/Approve/Apply on the list | PARTLY FIXED | Approve and Apply on rows `StocktakeSessionPanel.tsx:103-105`; Complete count still session-only (`:90`). See P2 #2 |
| 4 | Ledger Overdue and Warranty filters visible | FIXED | `Ledger.tsx:104` (toggle in `views` slot, `aria-pressed`), `WarrantyPanel.tsx:63` (Missing docs), `:65-66` (`activeCount` and chip for Expires before) |
| 5 | Visible context row action | FIXED | `InventoryColumns.tsx:23-27` (Restore on Archived, "Add to To buy…" on low/out tabs) |
| 6 | To-buy receive captures cost and receipt; Cancel; receipt count | FIXED | `ProcurementPanelRows.tsx:87-90`, `:285`, `:289-290` |
| 7 | QR labels auto-select latest batch; New batch inside a batch | FIXED | `useQrBatchBuilder.ts:32-38`, `QrTools.tsx:30,108` |
| 8 | Containers primary creates; row Edit | FIXED | `ContainersPanel.tsx:21,32-33`, `ContainerCreateModal.tsx` (POST `/admin/qr/boxes`, payload matches `CreateBoxQrSerializer`) |
| 9 | Reorder suggestions visible on empty/filtered list | FIXED | `InventoryWorkspace.tsx:205,217,226`; `ReorderSuggestions.tsx:12-27` (callout slot) |
| 10 | Export selection labels, Excel in bulk bar | FIXED | `InventoryWorkspace.tsx:206,216,222` |
| 11 | Ledger sort outside popover; All makerspaces | FIXED | `Ledger.tsx:92,100-103` (secondary action also reaches phones through `PageHeader.tsx:10,27`) |
| 12 | Transfers makerspace switch and read-only notice | FIXED | `StockTransferPanel.tsx:22-26` |
| 13 | Sidebar Ledger and Scanner promoted | FIXED | `sidebarSections.ts:16`; label "Ledger" comes from `TAB_LABELS` (`staffAccess.ts:18`) |
| 14 | Asset Edit visible | FIXED | `InventoryPanelParts.tsx:106` |
| 15 | Transfer #id and line count | FIXED | `StockTransferTable.tsx:9` |
| 16 | Warranty host kind | FIXED | `WarrantyPanel.tsx:68,75-77` (label plus icon) |
| 17 | Scanner QR id | FIXED | `ScannerPanel.tsx:31` |
| 18 | Stocktake session #id | FIXED | `StocktakeSessionPanel.tsx:89,100` |
| 19 | QR tools makerspace card | N/A | Context only; the workspace switcher shows it |

---

## Capability table

Status key as in the brief. "PRESENT" includes one click into a drawer tab or a header menu when the thing is occasional.

### 1. Inventory list, add, edit

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Page header and item count | `InventoryWorkspace.tsx:218` | `InventoryWorkspace.tsx:215-216` | PRESENT | Subtitle and count added |
| Search | `:221-224` | `:220` (`ListViewControls`) | PRESENT | |
| Add item | `:227` | `:208,215` | PRESENT | Header primary, reachable on phones |
| Archived toggle | `:228` | `:219` tab | PRESENT | |
| Low stock toggle | `:229` | `:219` tab | PRESENT | |
| Out-of-stock dashboard filter and clear | `:238` | `:219` tab | PRESENT | `archived=all` no longer announced (P2 #7) |
| Clear selected result (`?id=`) | `:239` | `ListViewControls.tsx:15` chip | PRESENT | |
| Bulk Enable QR plus confirm | `:230,280` | `:222,251` | PRESENT | Bulk bar on selection, fixed bar on phones (`ListLayout.tsx:36`) |
| Bulk Disable QR plus confirm | `:231` | `:222,251` | PRESENT | |
| Export CSV and XLSX, selection aware | `:232-233` | `:216,222` | PRESENT | Header "Export" menu (phones: overflow) says "(n selected)"; bulk bar has both |
| Saved views | `:237` | `ListViewControls.tsx:13` | PRESENT | |
| Column sort | `:240` | `InventoryColumns.tsx:15-20`, `InventoryWorkspace.tsx:221` | CHANGED | Phones get 4 options (P2 #4) |
| Row columns (image, name, mode+Archived, total, available+badge, issued, damaged, lost) | `:196-207` | `InventoryColumns.tsx:13-20` | PRESENT | Issued/damaged/lost hidden on phone cards; reachable in drawer Stock tab |
| Row Edit | `:210` | `InventoryColumns.tsx:14,29` | PRESENT | Name link plus overflow |
| Row To Fix | `:211` | `InventoryColumns.tsx:30` overflow | BURIED | Rare; acceptable (P2 #9) |
| Row Archive with confirm | `:212,279` | `InventoryColumns.tsx:32-33` | PRESENT | Confirm kept, undo toast added |
| Row Back to inventory | `:212` | `InventoryColumns.tsx:26` "Restore" | PRESENT | Visible on Archived tab |
| Row To Buy (`canUseToBuy`) | `:213` | `InventoryColumns.tsx:27,31` | PRESENT | Visible on low/out tabs, overflow otherwise |
| Row selection | `:240` | `InventoryWorkspace.tsx:223` | PRESENT | |
| Pagination 24 | `:241` | `:224` | PRESENT | |
| Load/To-buy/bulk/export messages | `:242-245` | `:223,227` | PRESENT | |
| Empty titles | `:240` | `:218` | PRESENT | |
| Reorder suggestions plus Draft order | `:219` | `:205,217,226`, `ReorderSuggestions.tsx` | PRESENT | Callout plus drawer; `canProcure` unchanged |
| Quick-create hook | `:55` | `:55` | PRESENT | |
| Add to To buy modal | `:259-267` | `:231-239` | PRESENT | Stepper input |
| Move to repair shelf modal | `:268-275` | `:240-247` | PRESENT | |
| Asset chooser for individual items | `:276-278` | `:248-250` | PRESENT | |
| Add item surface | `:247` modal | `:211`, `InventoryPanelParts.tsx:25-33` | CHANGED | Full-page `FormPageLayout` with catalogue preview |
| Add fields (name, mode, category, description, terms, location, master data, quantities, public flags, visibility) | `InventoryPanelParts.tsx:31-42` | `InventoryItemFields.tsx:14-37` | PRESENT | Same fields, regrouped |
| Photo after save and auto-open | `IPP:43`, `IW:98` | `IW:96`, `InventoryItemFields.tsx:39` | PRESENT | Toast added |
| Kit editor on add | `IW:248` | `IW:212` | PRESENT | |
| Edit surface with Save/Cancel | `IW:250` | `InventoryItemDetail.tsx:25,35` | CHANGED | Drawer; Save/Discard bar only when dirty |
| Edit fields | `IPP:31-42` | `InventoryItemDetail.tsx:32` | PRESENT | |
| Kit editor on edit | `IW:251` | `InventoryItemDetail.tsx:33` | PRESENT | |
| Item photo uploader | `IW:252` | `InventoryItemDetail.tsx:34` | PRESENT | Details tab |
| Adjust quantities | `IW:253`, `IPP:51-62` | `InventoryItemDetail.tsx:39`, `IPP:35-47` | PRESENT | Stock tab, reason required |
| Product QR history | `IW:254` | `InventoryItemDetail.tsx:41` | PRESENT | QR & assets tab, opens by default |
| Individual assets block | `IW:255` | `InventoryItemDetail.tsx:40-41` | PRESENT | On Stock and QR tabs |
| Lending history (`canViewAudit`) | `IW:256` | `InventoryItemDetail.tsx:42` | CHANGED | Relative time only (P1 #1) |
| Chain of custody (`canViewAudit`) | `IW:257` | `InventoryItemDetail.tsx:43` | CHANGED | Inner "Open" click and relative time (P1 #1, P2 #3) |
| Archive from drawer | none | `InventoryItemDetail.tsx:46` | PRESENT | New, with confirm |
| View public page link | none | `InventoryItemDetail.tsx:29` | PRESENT | New |

### 2. Individual assets

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| QR thumbnail per asset | `IPP:127` | `IPP:102` | BURIED | Behind "Show QR" disclosure; QR payload stays in it |
| Tag, serial, container, status | `IPP:129-131` | `IPP:99-101` | PRESENT | |
| Edit asset | `IPP:135-148` | `IPP:106,111-113` | PRESENT | Visible button opens modal |
| Asset QR history | `IPP:138` | `IPP:107,114` | BURIED | Overflow; rare |
| To Fix / Move back | `IPP:139-143` | `IPP:104-105` | PRESENT | Same status rules |

### 3. Categories

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Add (name, slug, order, icon) | `Categories.tsx:182-190` | `Categories.tsx:172,176-186` | PRESENT | Header primary opens a modal |
| Columns and sort | `:93-143` | `:97-147` | PRESENT | Phone sort chips appear (no `ordering` prop) |
| Inline edit | `:148-166` | `:149-166` | PRESENT | |
| Delete with "detach N products" confirm | `:167-174,208-223` | `:168,188-203` | PRESENT | Overflow; rare |
| Errors | `:191-196` | `:186-187` | PRESENT | |
| Empty | `:203-204` | `:174` | PRESENT | |

### 4. Containers

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| List with label, location, Inactive | `ContainersPanel.tsx:30-35,70-73` | `ContainersPanel.tsx:29-32` | PRESENT | Search and All/Active/Inactive tabs added |
| Create container | none (dead link) | `ContainersPanel.tsx:21,33`, `ContainerCreateModal.tsx` | PRESENT | New, `POST /admin/qr/boxes` |
| Edit (label, location, active, kit) | `CP:75,81-90` | `ContainersPanel.tsx:32`, `ContainerDetail.tsx:54-64` | PRESENT | Row overflow "Edit" or row click then Details tab; Save bar when dirty |
| Contents | `CP:76,92-108` | `ContainerDetail.tsx:65-81` | PRESENT | Default tab |
| Scan history | `CP:77,110-118` | `ContainerDetail.tsx:83-91`, `ContainersPanel.tsx:32` | CHANGED | Relative time only (P1 #1) |
| Show QR per asset | `CP:136` | `ContainerDetail.tsx:108` | PRESENT | |
| Asset warranty | `CP:137-143` | `ContainerDetail.tsx:109,113` | BURIED | Overflow; rare |
| Loading/error | `CP:27-28` | `ContainersPanel.tsx:24` | PRESENT | |

### 5. Repair shelf

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Explainer | `NeedsFixShelf.tsx:49-52` | `:33,36` | PRESENT | |
| Row name, "N to fix", available/total | `:58-66` | `:37-39` | PRESENT | |
| Quantity (default all) | `:68-79` | `:40-41` | PRESENT | Validated stepper |
| Move back to inventory | `:80-82` | `:42` "Repaired" | PRESENT | Toast added |
| Scrap | `:83-85` | `:43,46` | PRESENT | Overflow plus new confirm; rare, destructive |
| Empty/error/load | `:53-56,90-91` | `:34-35,45` | PRESENT | |

### 6. Stocktake

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Policy and schedule (`discipline && canConfigure`) | `StocktakeSessionPanel.tsx:57` | `:83,93` | BURIED | Header overflow then drawer; rarely changed |
| Blind-by-default and variance threshold plus Save | `StocktakeDiscipline.tsx:25-29` | `StocktakeDiscipline.tsx:28-31` | PRESENT | |
| Schedule create | `SD:30-35` | `SD:33-39` | PRESENT | |
| Schedule list Pause/Enable | `SD:36` | `SD:40-41` | PRESENT | Due date relative (P1 #1 pattern) |
| Due schedule prompt | none | `StocktakeSessionPanel.tsx:94` | PRESENT | New callout |
| Count visibility select | `SS:58` | `:80` | PRESENT | Start dialog |
| Status filter | `SS:59` | `:98` | PRESENT | Tabs |
| Start stocktake (notes, container) | `SS:60-75` | `:76-82` | PRESENT | Header primary, opens session after create (`:50`) |
| Row `#id`, status, notes, container | `SS:79-97` | `:99-102` | PRESENT | `#id` restored |
| Count items | `SS:84-86` | `:105` "Continue"/"Open count" | PRESENT | |
| Complete (counting) | `SS:87-89` | `:71,90` | BURIED | Session page only (P2 #2) |
| Approve (gate) | `SS:90-92` | `:72,103-104` | PRESENT | Gate identical |
| Apply (gate) | `SS:93-95` | `:73,103-104,84` | PRESENT | Gate identical, confirm added |
| Pagination and errors | `SS:76-77,102` | `:85,106` | PRESENT | |
| Count form (type, product, asset, container, counted, condition, notes, Record) | `StocktakeCountSection.tsx:112-171` | `StocktakeCountSection.tsx:112-173` | PRESENT | Inside `ScanWorkbench` |
| Scan QR (camera, `resolve-scan`) | `CS:169,174,82-105` | `CS:112,82-103` | PRESENT | Camera plus paste-and-Find |
| Lines table | `CS:175-198` | `CS:177-187` | PRESENT | Stat row added, completed sessions read-only |

### 7. Stock transfers

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Read-only notice for non-creators | `StockTransferPanel.tsx:176-179` | `StockTransferPanel.tsx:22` | PRESENT | |
| Create form | `:181-260` | `:21,31-101` | PRESENT | Header primary, two-step dialog |
| Makerspace selectors (superadmin) | `:189-202` | `:23-26,38-51` | PRESENT | Toolbar switch picks which space's history lists; dialog picks source/destination |
| Source and destination container | `:203-219` | `:52-68` | PRESENT | |
| Lines (product with available, qty, add, remove) | `:222-239` | `:79-91` | PRESENT | Remove is per-line overflow |
| Reason, cross-makerspace explainer, validation | `:241-256` | `:93-100`, `useStockTransfer.ts:162-172` | PRESENT | |
| Create transfer | `:257` | `:35` "Move stock" | PRESENT | |
| History `#id`, endpoints, reason, created, lines | `StockTransferTable.tsx:36-44` | `StockTransferTable.tsx:6-10` | PRESENT | Created is relative; hover shows exact |
| Pagination, loading, error, empty | `:271`, `:298-300` | `:27-30` | PRESENT | |

### 8. To buy

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Add form (name, qty, link, est., vendor, actual, machine type, kind) | `ProcurementPanel.tsx:135-161` | `:137,152-179` | PRESENT | Header primary opens a modal; `canChooseKind` and machine-type rules unchanged |
| Metrics | `:166-168` | `:145` | PRESENT | |
| Status filter, default Requested | `:169-175` | `:67,146` | PRESENT | Tabs incl. All and Cancelled |
| Export CSV/XLSX | `:178-179` | `:140` | BURIED | Header overflow; occasional |
| Grouping by machine type | `:200-223` | `:147` | PRESENT | |
| Name, "Auto - low stock", qty, est., purchaser | `ProcurementPanelRows.tsx:80-86` | `:93-94` | PRESENT | |
| Kind, link | `:80-82` | `:103-104` | PRESENT | Drawer |
| Vendor, actual unit cost | `:84-85` | `:108-109` | PRESENT | Drawer; vendor read-only in row meta |
| Ordered/received dates | `:87-88` | `:107` | CHANGED | Relative time (P1 #1) |
| Receipts view/upload/delete | `:89` | `:94,112`, `ProcurementReceipts.tsx` | PRESENT | Count in row, delete confirms |
| Status (any value) | `:91-93` | `:83-84,96,110` | PRESENT | One-click next step; any status in drawer; Cancel in overflow |
| Moved-to state | `:95,107-115` | `:111,121-129` | PRESENT | Link now deep-links `?item=` |
| Move to inventory | `:98` | `:96`, banner `ProcurementPanel.tsx:141` | PRESENT | `ProcurementMoveModal` forms unchanged |
| Save row edits | `:99` | `:114` | PRESENT | Bar when dirty |
| Delete | `:100` | `:100,116` | PRESENT | Overflow; confirm added |
| Errors | `:162,233-236` | `:113,117`, `ProcurementPanel.tsx:180-181` | PRESENT | |
| Reorder suggestions | none | `ProcurementPanel.tsx:152` | PRESENT | New |

### 9. Ledger

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| "N items out", scope, records | `Ledger.tsx:91-95` | `:91,97` | PRESENT | |
| All makerspaces (superadmin) | `:97-109` | `:92` | PRESENT | Header secondary; phones via overflow |
| Search | `:113` | `:99` | PRESENT | |
| Source filter | `:114-119` | `:98` | PRESENT | Tabs, URL `?source=` |
| Overdue only | `:120-123` | `:104` | PRESENT | Visible toggle |
| Export CSV/XLSX | `:124-125` | `:93` | BURIED | Header overflow; error now shown |
| Sort by item, holder, qty, since, due, source, makerspace | `:139-145` | `:100-103,112-114` | PRESENT | Select plus direction toggle |
| Row data (item, box, unit tags, holder, qty, since, due, source, makerspace) | `:149-173` | `:105-108` | CHANGED | "Out since" relative (P1 #1); due is a pill with date |
| Overdue emphasis | `:152,164` | `:108` | CHANGED | Danger pill, no row tint |
| Pagination 50 | `:181-191` | `:109` | PRESENT | |
| Loading/error/empty | `:128-132` | `:94-95` | PRESENT | |

### 10. Warranty

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Scope text and host count | `WarrantyPanel.tsx:70-71` | `:58` | PRESENT | |
| Status filter | `:74-83` | `:62` | PRESENT | Tabs |
| Expires before | `:84-87` | `:64-66` | PRESENT | Popover with active count and chip |
| Missing docs | `:88-96` | `:63` | PRESENT | Visible toggle |
| Host kind | `:130-132` | `:68,75-77` | PRESENT | Label and icon |
| Label, serial, vendor, purchased, expires, status, docs | `:133-141` | `:67-69` | PRESENT | |
| Manage (`canManageRow`) | `:142-156` | `:39-43,70,72` | PRESENT | Drawer with `WarrantySection`; gate identical |
| WarrantySection fields, save, doc view/upload/remove | `WarrantySection.tsx:112-170` | same file | PRESENT | Doc removal confirms |
| Pagination, loading, error, empty | `:100-104,165-173` | `:59-61,71` | PRESENT | |

### 11. QR labels

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Makerspace name card | `QrTools.tsx:152-155` | workspace switcher | PRESENT | Context only |
| New batch | `:156-158` | `:24,30` | PRESENT | On list and inside a batch |
| Batch choice and auto-select latest | `:33-37,160-163` | `useQrBatchBuilder.ts:32-38`, `QrTools.tsx:24-27` | PRESENT | Opens latest batch once; "All batches" shows list |
| Create-batch dialog | `:245-248` | `QrTools.tsx:19-22` | PRESENT | |
| Item select | `:168-175` | `QrTools.tsx:34-41` | PRESENT | Filtered by the label-type control |
| Mode label and asset-units notice | `:176-181` | `:42-47` | PRESENT | |
| Generate unit QRs (count ≤200, prefix) | `:184-190` | `:50-56` | PRESENT | "Units" segment |
| Reprint unit QR | `:191-203` | `:57-69` | PRESENT | "Reprint a unit" segment |
| Add/reprint item QR | `:209-213` | `:75-79` | PRESENT | "Item" segment (default) |
| Batch title, count, Download ZIP | `:222-227` | `:28-30` | PRESENT | Header primary |
| Label grid, empty, errors | `:229-241` | `:85-107` | PRESENT | |

### 12. Scanner

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Payload input plus Resolve | `ScannerPanel.tsx:188-198` | `ScannerPanel.tsx:19` | PRESENT | `ScanWorkbench` Find |
| Scan camera | `:199,288` | `ScanWorkbench.tsx:42,65` | PRESENT | |
| Resolving/error/success notes | `:201-203` | `ScannerPanel.tsx:21-23` | PRESENT | Recent-scans list added |
| Target heading | `:207-211` | `:26-30` | PRESENT | |
| QR `#id` and status | `:212` | `:31` | PRESENT | |
| View contents (box) | `:214-216,277-284` | `:33-35,91-98` | PRESENT | |
| Revoke QR | `:217-221` | `:99,104` | PRESENT | Danger zone plus new confirm |
| Rename and rebind | `:222-248` | `:36-40,47-62` | PRESENT | Gate identical |
| Move asset to makerspace | `:227-269` | `:41-45,63-83` | PRESENT | Superadmin, gate identical |
| Checkout/return hint | `:270-275` | `:84-89` | PRESENT | |

### 13. Bulk import

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Upload CSV/TSV/XLSX | `BulkImport.tsx:102-113` | `:120-123` | PRESENT | Drag-drop added |
| Paste table, map | `:115-117` | `:124`, `:117` | PRESENT | |
| Column mapping | `:145-161` | `:130-131` | PRESENT | "Match columns" step |
| Edit mapping | `:118` | `:113` Back | PRESENT | |
| Preview | `:119` | `:106,117` | PRESENT | |
| Apply rows, partial apply | `:120` | `:107,114-115` | PRESENT | "Import N valid rows, skip M" |
| Apply file job | `:121` | `:107,117` | CHANGED | Needs a preview job first |
| Advanced JSON preview/apply | `:124-131` | `:125-128,79-90` | CHANGED | Apply only from Review |
| Progress and job tray | `:50,132,163-173` | `:54,132`, `BulkImportResults.tsx:4-7` | PRESENT | |
| File parse error message | `:110` | `:103` | PRESENT | Parser text kept |
| Summary metrics and row table | `:175-200` | `BulkImportResults.tsx:8-21` | PRESENT | Errors sorted first |

### 14. Navigation and mounting

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Inventory, ledger, scanner, repair shelf, stocktake, transfers, to-buy reachable | dock groups (`staffAccess.ts:56`) | `sidebarSections.ts:16` | PRESENT | Visible sidebar items; bottom tabs plus More on phones |
| Categories, containers, warranty, QR tools, bulk import reachable | dock popovers | `sidebarSections.ts:16` `more` | BURIED | Behind "More (5)"; occasional-use pages |
| Route mounting and gates | `StaffTabContent.tsx` | unchanged for these tabs | PRESENT | `inventoryTabAvailable` prop added for reorder |
| Item deep link `?item=`, `?itemTab=` | none (modal) | `InventoryWorkspace.tsx:188-204`, `InventoryItemDetail.tsx:20-21` | PRESENT | Linked item fetched with `archived=all` |
| Inventory sidebar labels | dock labels | `sidebarSections.ts:25-26` | CHANGED | "Items", "Repair shelf", "QR tools" vs page titles (P2 #6) |
