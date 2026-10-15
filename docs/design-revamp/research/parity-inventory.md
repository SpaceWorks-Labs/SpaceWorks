# Functionality parity audit: Inventory area (staff console)

Read-only research, 2026-10-15. **Old** = `d3e5ed29` (`dev`, pre-revamp). **New** = `feature/design-revamp`
working tree, including the uncommitted polish edits. Old paths are relative to
`frontend/src/features/staff/panels/` unless noted. The line numbers are old-file lines from `git show d3e5ed29:<path>`.

## Scope and method

- **Routing did not change.** `StaffTabContent.tsx` and `StaffTabLoaders.tsx` mount the same component for every inventory tab, with the same
  permission gates in both versions: `inventory`, `needsfix`/`categories`/`stocktake`/`bulk` (canEditInventory),
  `containers`/`qr`/`scanner` (canManageQr), `transfers` (canEditInventory || superadmin), `tobuy`, `ledger`,
  `warranty` (canEditInventory || canSeePrinting). The only loader diff is outside this area (platform panels).
  Every loss happens **inside** the page components.
- Each capability was traced through the new component and the layout primitives it uses: `ListLayout`, `DetailLayout`,
  `FlowLayout`, `ListFilters`/`FilterPopover`, `OverflowMenu`, `DangerZone`, `ActionControl`.
- **One cross-cutting finding affects several rows:** `Action.confirms` only appends an ellipsis to the label
  (`components/ui/ActionControl.tsx:10`, `OverflowMenu.tsx:25`, `types.ts:9`). It does **not** open a confirmation.
  Every `DangerZone` label ends in "…" but runs immediately unless its caller opens its own `ConfirmDialog`.
- **The second cross-cutting finding:** `ListFilters` puts `controls` inside a closed `FilterPopover`. Ledger and Warranty don't pass
  `activeCount`, so the popover badge shows 0 even when a filter inside it is on.

Status key: **PRESENT** means it is visible as before, or in an equivalent visible slot. **BURIED** means it can still be reached, but behind an overflow menu, a drawer, a tab, a popover
or an extra click. **CHANGED** means the behaviour or data differs. **MISSING** means it can't be reached anywhere in the UI.

---

## 1. Inventory: items list (`InventoryWorkspace.tsx`, abbreviated IW)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Page title "Inventory" | IW:218 | PRESENT | `ListLayout` header, plus a subtitle and an item-count meta (new IW:212-213) |
| 2 | Search box ("Filter table") | IW:221-224 | PRESENT | `ListViewControls` search (new IW:217) |
| 3 | **Add item** button | IW:227 | PRESENT | Header primary (new IW:205,212) |
| 4 | Show archived / Show active toggle | IW:228 | PRESENT | "Archived" tab (new IW:216) |
| 5 | Low stock / All stock toggle | IW:229 | PRESENT | "Low stock" tab |
| 6 | Out-of-stock dashboard filter note + "Clear dashboard filter" | IW:238 | PRESENT | "Out of stock" tab. The filtered-empty state has "Clear filters" |
| 7 | "Clear selected result" (`?id=` deep link) | IW:239 | PRESENT | Chip "Remove Selected result" (`ListViewControls.tsx:15`) |
| 8 | **Enable QR** (bulk PATCH `public_self_checkout_enabled`) + confirm | IW:230,124-146,280 | PRESENT | Bulk bar shown on selection; the ConfirmDialog is kept (new IW:219,247) |
| 9 | **Disable QR** (bulk) + confirm | IW:231 | PRESENT | Bulk bar |
| 10 | Export CSV (selection-aware label "Export CSV (n)") | IW:232,149-157 | BURIED | Header secondary "Export" menu. The bulk bar has "Export selected" (CSV only) |
| 11 | Export XLSX (selection-aware) | IW:233 | CHANGED | Only in the header "Export" menu. With rows selected it exports **only the selection**, but the label doesn't say so. No XLSX option in the bulk bar |
| 12 | Saved views menu | IW:237 | PRESENT | `ListViewControls` views slot |
| 13 | Server sort by column header | IW:240 | PRESENT | DataTable headers, plus a 4-option sort select |
| 14 | Columns: image, name (click opens edit), mode + Archived badge, total, available + Available/Limited/Unavailable badge, issued, damaged, lost | IW:196-207 | PRESENT | `InventoryColumns.tsx:11-16` |
| 15 | Row **Edit** button | IW:210 | BURIED | Row overflow. Clicking the name still opens the drawer |
| 16 | Row **To Fix** (opens the qty modal, or the asset chooser for individual items) | IW:211,158-165 | BURIED | Row overflow "Move to repair shelf…" (`InventoryColumns.tsx:19`) |
| 17 | Row **Archive**, with ConfirmDialog "Archive X? It will be hidden…" | IW:212,279 | CHANGED + BURIED | Moved to the row overflow and **the confirmation is gone**: the item archives instantly and an undo toast follows (`InventoryColumns.tsx:21`). The old `ConfirmDialog` and its `archiveTarget` state were deleted |
| 18 | Row **Back to inventory** (unarchive) | IW:212 | BURIED | Row overflow, even on the Archived tab where it's the main action |
| 19 | Row **To Buy** (gate `canUseToBuy`) | IW:213 | BURIED | Row overflow "Add to To buy…" |
| 20 | Row selection checkboxes | IW:240 | PRESENT | DataTable `selectedIds` |
| 21 | Pagination (24/page) | IW:241 | PRESENT | `ListLayout.pagination` |
| 22 | Load error, To Buy confirmation message, bulk-QR result message, export error | IW:242-245 | PRESENT | State error with retry. The status line and ErrorText are in the `detail` slot (new IW:223) |
| 23 | Empty titles ("No active/archived inventory") | IW:240 | PRESENT | `empty` / `filteredEmpty` |
| 24 | **Reorder suggestions panel**: list of items at their reorder point, "Draft order for N" (POST reorder→procurement, gate `canUseToBuy`), pagination, "No products are at their reorder points" | IW:219; `ReorderSuggestions.tsx`(old):19-32 | BURIED | Now a warn callout "N items are running low" with a "Review suggestions" button that opens a drawer. It is **hidden when there are 0 suggestions**, and it is also hidden whenever the inventory list is empty or filtered to empty, because it sits inside `body.table` (new IW:220) |
| 25 | Quick-create hook (`useQuickCreate("item")`) | IW:55 | PRESENT | new IW:54 |
| 26 | "Add to To Buy" modal (quantity) | IW:259-267 | PRESENT | new IW:227-235 |
| 27 | "Move to Fix Shelf" modal (qty ≤ available) | IW:268-275 | PRESENT | new IW:236-243 (renamed "repair shelf") |
| 28 | "Choose Asset to Fix" modal (individual items) | IW:276-278 | PRESENT | new IW:244-246 |

### 1a. Add item (old modal `ItemModal`, `InventoryPanelParts.tsx` abbreviated IPP:24-49)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 29 | Add-item modal over the list | IW:247 | CHANGED | A full-page `FormPageLayout` replaces the whole list while it's open (new IW:208). It adds a public-catalogue preview |
| 30 | Fields: name, tracking mode, category, description, borrowing terms, storage location, product master fields (SKU/supplier/reorder point/qty), total qty, available qty, Public, Self checkout, Show count, visibility mode | IPP:31-42 | PRESENT | `InventoryItemFields.tsx` |
| 31 | "Photo can be added after saving", then auto-reopen in edit | IPP:43; IW:98 | PRESENT | Same, plus a toast |
| 32 | Kit components editor (gate `loans.kit_checklist`) | IW:248 | PRESENT | new IW:209 |

### 1b. Edit item (old modal, new right-hand drawer `InventoryItemDetail.tsx` with tabs)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 33 | Edit modal with Save/Cancel | IW:250; IPP:29 | CHANGED | Drawer, Details tab. The Save/Discard bar appears **only when the form is dirty** |
| 34 | All item fields (as #30, without quantities) | IPP:31-42 | PRESENT | Details tab |
| 35 | Kit editor | IW:251 | PRESENT | Details tab |
| 36 | Item photo uploader (`/admin/inventory/{id}/image`) | IW:252 | PRESENT | Details tab |
| 37 | **Adjust quantities** (± available/damaged/lost + reason, then POST `adjust-quantity`) | IW:253; IPP:51-62 | BURIED | "Stock" tab |
| 38 | Product QR history (`/qr-history`) | IW:254; IPP:64-88 | BURIED | "QR & assets" tab (opens automatically there) |
| 39 | Individual assets block (tracking = individual) | IW:255 | BURIED | Both the "Stock" and "QR & assets" tabs (rendered twice) |
| 40 | Lending history (gate `canViewAudit`) | IW:256 | BURIED | "History" tab |
| 41 | Chain of custody (gate `canViewAudit`) | IW:257 | BURIED | "Custody" tab, which still needs an inner "Open" click |
| 42 | (new) Archive from the drawer | — | CHANGED | A danger zone labelled "Archive…" that **archives without confirmation** (new IW:225; `InventoryItemDetail.tsx:46`) |

### 1c. Individual assets (`IndividualAssets`, IPP:90-156)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 43 | Inline QR thumbnail per asset | IPP:127 | BURIED | A "Show QR" `<details>` disclosure in the QR column |
| 44 | Tag, serial, container, status, QR payload/#id | IPP:129-131 | PRESENT | Table columns. The payload is inside the disclosure |
| 45 | **Edit asset** (inline `AssetEditForm`) | IPP:135-148 | BURIED | Row overflow "Edit", which opens a modal |
| 46 | Asset QR history | IPP:138 | BURIED | Row overflow "QR history", which opens a modal |
| 47 | To Fix / Move back to inventory (`/admin/assets/{id}/fix-status`) | IPP:139-143 | PRESENT | Visible row button |

---

## 2. Categories (`Categories.tsx`, abbreviated C)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Inline add form (name, slug, order, icon, **Add category**) | C:182-190 | BURIED | Header primary "Add category" opens a modal with the same 4 fields |
| 2 | Columns: name, slug, order, icon, # products; sortable | C:93-143 | PRESENT | Same |
| 3 | Inline edit (Edit, then inputs, then Save/Cancel) | C:148-166 | PRESENT | "Edit" still visible |
| 4 | Delete + confirm "will detach N products" | C:167-174,208-223 | BURIED | Row overflow. The confirm is kept. This is rare, so the overflow is acceptable |
| 5 | Create/update/delete/load errors | C:191-196 | PRESENT | Create error is in the modal. Update/delete errors are in the detail slot |
| 6 | Empty state | C:203-204 | PRESENT | With an "Add category" action |

---

## 3. Containers (`ContainersPanel.tsx`, abbreviated CP; new = `ContainersPanel.tsx` + `ContainerDetail.tsx`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Container list: label, location, Inactive badge | CP:30-35,70-73 | PRESENT | `ListRow`s with code identity, location meta and an Active/Inactive pill. New: search plus All/Active/Inactive tabs |
| 2 | Empty hint "Create one in QR tools" | CP:33-35 | CHANGED | Now a **header primary** "Create in QR tools" linking to `/admin/qr-tools`. But QR tools has **no create-container control** in either version. `POST /admin/qr/boxes` (`boxes/urls.py:6`, `CreateBoxQrView`) has no UI anywhere. The primary is a dead end (a gap from before the revamp, now made prominent) |
| 3 | **Edit** container (label, location, active, kit components, then POST `/move`) | CP:75,81-90 | BURIED | Click the row to open the drawer, then the "Details" tab (third tab). The Save bar appears only when dirty |
| 4 | Contents (products, asset units, sub-containers) | CP:76,92-108 | BURIED | Click the row to open the drawer; "Contents" is the default tab |
| 5 | Scan history | CP:77,110-118 | BURIED | Drawer, "History" tab |
| 6 | Per-asset "Show QR" (POST `/admin/assets/{id}/qr`) | CP:136 | PRESENT | Drawer Contents, visible button |
| 7 | Per-asset Warranty (`WarrantySection`, editable if canEditInventory) | CP:137-143 | BURIED | Asset-row overflow "Warranty" |
| 8 | Loading/error | CP:27-28 | PRESENT | Layout state |

---

## 4. To be fixed / repair shelf (`NeedsFixShelf.tsx`, abbreviated NF)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Explainer text | NF:49-52 | PRESENT | Header subtitle, plus 2 stats |
| 2 | Row: name, "N to fix" badge, available/total | NF:58-66 | PRESENT | `ListRow` |
| 3 | Quantity input (defaults to all) | NF:68-79 | PRESENT | Prefilled and validated |
| 4 | **Move back to inventory** (POST `needs-fix` action=repair) | NF:80-82 | PRESENT | Relabelled "Repaired"; a toast follows |
| 5 | **Scrap** (action=scrap) | NF:83-85 | BURIED + CHANGED | Row overflow, and a confirm dialog was added |
| 6 | Empty, error, load | NF:53-56,90-91 | PRESENT | |

---

## 5. Stocktake (`StocktakeSessionPanel.tsx` SS, `StocktakeDiscipline.tsx` SD, `StocktakeCountSection.tsx` CS)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Policy & schedule section shown inline (gate `stocktake.discipline` + canConfigure) | SS:57 | BURIED | Header overflow "Count policy and schedule" opens a drawer (`SettingsLayout`) |
| 2 | Policy: blind by default, variance threshold, Save | SD:134-138 | PRESENT | Inside the drawer (Save bar when dirty) |
| 3 | Schedule create (name, every N days, first due) | SD:139-144 | PRESENT | Inside the drawer |
| 4 | Schedule list with Pause/Enable | SD:145-146 | PRESENT | Inside the drawer. New: a callout on the page when a schedule is due |
| 5 | Count visibility (blind) select | SS:58 | PRESENT | Moved into the "Start count" modal |
| 6 | Status filter select | SS:59 | PRESENT | Tabs (relabelled "Needs approval", "Ready to apply") |
| 7 | Inline start form (notes, container, **Start stocktake**) | SS:60-75 | BURIED | Header primary "Start count" opens a modal. On success it now opens the new session page |
| 8 | Row: `#id`, status, notes, `Container #n` | SS:79-97 | CHANGED | Shows notes/container label/started/lines count/status. **`#id` dropped** |
| 9 | "Count items" toggle (draft/counting) | SS:84-86 | PRESENT | "Continue" opens the full session page |
| 10 | **Complete** (counting) | SS:87-89 | BURIED | Only as the session-page header primary. No longer on the list |
| 11 | **Approve** (gate superadmin, or canConfigure + threshold) | SS:90-92 | BURIED | Session page only |
| 12 | **Apply** adjustments (gate) | SS:93-95 | BURIED + CHANGED | Session page only. A confirm "Apply N adjustments?" was added |
| 13 | Pagination, create/action errors | SS:76-77,102 | PRESENT | |
| 14 | Count form: type, product, asset, container, counted, condition, notes, **Record count** | CS:112-171 | PRESENT | Inside `ScanWorkbench` controls |
| 15 | **Scan QR** (camera, then `resolve-scan`) | CS:169,174,82-105 | PRESENT | `ScanWorkbench` "Start scanning", plus a paste field |
| 16 | Lines table (item, container, expected, counted, variance, condition, notes) | CS:175-198 | PRESENT | DataTable, plus a "Lines counted / Variances" stat row. New: completed sessions open read-only |

---

## 6. Transfers (`StockTransferPanel.tsx` ST, `StockTransferTable.tsx` STT)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | "Transfers are managed by inventory staff. This view is read-only." notice | ST:176-179 | MISSING | Non-creators just see no primary button and no explanation. No equivalent copy is left in the new tree |
| 2 | Inline create form | ST:181-260 | BURIED | Header primary "New transfer" opens a 2-step `FlowLayout` dialog |
| 3 | Source/destination **makerspace** selectors (superadmin) | ST:189-202 | CHANGED + BURIED | Dialog step 1. In the old page the source selector also **switched which makerspace's transfer history the table showed**. That switch now happens only inside the create dialog |
| 4 | Source container (disabled for cross-makerspace) / destination container | ST:203-219 | PRESENT | Dialog step 1 |
| 5 | Lines: product (with available), qty, Add line | ST:222-234 | PRESENT | Dialog step 2 |
| 6 | Remove line | ST:235 | BURIED | Per-line overflow |
| 7 | Reason, cross-makerspace explainer, validation errors | ST:241-256 | PRESENT | Step 2: callout plus a "Read the details" disclosure |
| 8 | **Create transfer** | ST:257 | PRESENT | Step 2 "Move stock" |
| 9 | History column **ID (#n)** | STT:306,317 | MISSING | Not shown anywhere |
| 10 | Source / destination labels, reason, created | STT:318-321 | PRESENT | `ListRow` meta (created is now relative) |
| 11 | Lines count | STT:322 | CHANGED | Now "N units transferred" (sum of quantities), not the line count. A status pill was added |
| 12 | Pagination, loading, error, empty | ST:271; STT:298-300 | PRESENT | |

---

## 7. To buy / procurement (`ProcurementPanel.tsx` PP, `ProcurementPanelRows.tsx` PR, `ProcurementReceipts.tsx`, `ProcurementMoveModal.tsx`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Explainer | PP:131-133 | PRESENT | Subtitle |
| 2 | Inline add form: name, qty, link, est. cost, vendor, actual cost, machine type (server-required logic), kind (gate `canChooseKind`), **Add** | PP:135-161 | BURIED | Header primary "Add item" opens a modal with all fields |
| 3 | Metrics: visible estimated total, open budget, received actual | PP:166-168 | PRESENT | Stats |
| 4 | Status filter (default Requested) | PP:169-175 | PRESENT | Tabs |
| 5 | Export CSV / XLSX | PP:178-179 | BURIED | Header overflow |
| 6 | Grouping by machine type | PP:200-223 | PRESENT | Section headings |
| 7 | Columns: item name + "Auto - low stock" badge, qty, est. cost, purchaser | PR:320-326 | PRESENT | Row title/meta |
| 8 | Kind column | PR:319 | BURIED | Drawer meta |
| 9 | Link column | PR:322 | BURIED | Drawer "Open supplier link ↗" |
| 10 | **Vendor** (inline editable) | PR:324 | CHANGED | Read-only in the meta. Editing moved to the drawer |
| 11 | **Actual unit cost** (inline editable) | PR:325 | BURIED | Drawer |
| 12 | Ordered at / Received at | PR:327-328 | BURIED | Drawer |
| 13 | **Receipts** (view, upload, delete) | PR:329 | BURIED | Drawer. Receipt delete moved to an overflow and gained a confirm |
| 14 | **Status** (inline select, any value incl. Cancelled) | PR:330-334 | CHANGED | Row has a status pill and a one-click next step: Approve, then Mark ordered, then Mark received. Any other value (incl. **Cancelled**) only via the drawer select |
| 15 | Moved-to state / link to inventory | PR:335 | BURIED | Drawer |
| 16 | **Move** (received, not moved) | PR:338 | PRESENT | Row button "Move to inventory", plus a page banner "Move them" |
| 17 | **Save** row edits (PATCH) | PR:339 | BURIED | Drawer Save bar (when dirty) |
| 18 | **Delete** | PR:340 | BURIED + CHANGED | Row overflow. A confirm was added (old had none) |
| 19 | Move modal (hardware create/top-up, printing spool/printer) | `ProcurementMoveModal.tsx` | PRESENT | `FlowLayout` dialog, same forms |
| 20 | Create/update/delete/export errors | PP:162,233-236 | PRESENT | Per-row and in the modal |

New on this page: a reorder-suggestions callout (when the inventory tab is available).

---

## 8. Ledger (`Ledger.tsx` L, `LedgerParts.tsx`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Headline "N items out" + scope + "N records" | L:91-95 | PRESENT | Stats "Items out on this page" / "Records". Scope goes in the header meta |
| 2 | **All makerspaces** toggle (superadmin, `/admin/ledger`) | L:97-109 | BURIED | Inside the "Filters" popover |
| 3 | Search (holder, email, item, box) | L:113 | PRESENT | Filter search |
| 4 | Source filter | L:114-119 | PRESENT | Tabs: All / Reviewed / Self-checkout / Direct |
| 5 | **Overdue only** | L:120-123 | BURIED + CHANGED | Inside the "Filters" popover. `activeCount` isn't passed, so the popover badge stays at 0 while it's on |
| 6 | Export CSV / XLSX | L:124-125 | BURIED | Header overflow. Export errors now surface |
| 7 | Sortable column headers (item, holder, qty, since, due, source, makerspace) | L:139-145 | BURIED | A sort select plus an Asc/Desc button **inside the Filters popover** |
| 8 | Row data: item, box, unit tags/serials, holder, qty, out since, due, source, makerspace | L:149-173 | PRESENT | `ListRow`. Due becomes a pill ("Overdue N days" / "Due …"). "Out since" is relative |
| 9 | Overdue row highlight | L:152,164 | CHANGED | Danger pill only; no row tint |
| 10 | Pagination | L:181-191 | PRESENT | |
| 11 | Loading skeleton, error, empty | L:128-132 | PRESENT | |

---

## 9. Warranty (`WarrantyPanel.tsx` W; `WarrantySection.tsx`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Scope text + "N hosts total" | W:70-71 | PRESENT | Subtitle/meta |
| 2 | Status filter | W:74-83 | PRESENT | Tabs (unknown is now "Not covered") |
| 3 | Expires before (date) | W:84-87 | BURIED | Filters popover (no active count) |
| 4 | Missing docs | W:88-96 | BURIED | Filters popover |
| 5 | **Host kind badge** (asset / machine / printer) | W:130-132 | MISSING | Not rendered. Row identity is a generic circle icon |
| 6 | Host label, serial, vendor, purchased, expires, status badge, doc count | W:133-141 | PRESENT | `ListRow` (expires is relative) |
| 7 | **Manage** (gate `canManageRow`: asset needs canEditInventory, printer never) | W:142-156 | PRESENT | Visible "Manage" opens a drawer with `WarrantySection` |
| 8 | WarrantySection: purchased, expires, vendor, contact, Save/Create, doc view/upload/remove | `WarrantySection.tsx`:112-170 | PRESENT | Save bar shows when dirty or there's no warranty yet. Doc remove gained a confirm |
| 9 | Pagination, loading, error, empty | W:100-104,165-173 | PRESENT | |

---

## 10. QR tools (`QrTools.tsx` Q; new adds `useQrBatchBuilder.ts`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Makerspace name card | Q:152-155 | MISSING | Context only; the workspace switcher shows it. Trivial |
| 2 | **New batch** | Q:156-158 | BURIED | Only on the batch-list view. **Not available inside a batch**: you have to go "← All batches" first |
| 3 | Batch dropdown, auto-selecting the most recent batch | Q:33-37,160-163 | CHANGED + BURIED | Now a batch list page (`?batch=`). No auto-select (the `useEffect` was removed), so every visit takes an extra click |
| 4 | Create-batch modal (title) | Q:245-248 | PRESENT | |
| 5 | Inventory item select (name / mode / available) | Q:168-175 | PRESENT | Now filtered by the Item/Units segment |
| 6 | Tracking-mode label; "needs Asset units module" notice | Q:176-181 | PRESENT | |
| 7 | Generate unit QRs (count ≤200, label prefix) | Q:184-190 | BURIED | "Units" segment |
| 8 | Reprint existing unit QR | Q:191-203 | BURIED | "Reprint a unit" segment |
| 9 | **Add/reprint item QR** | Q:209-213 | PRESENT | "Item" segment (default) |
| 10 | Batch title, label count, **Download all (ZIP)** | Q:222-227 | PRESENT | Detail header primary |
| 11 | Batch label grid (QR image, label, target) + empty + errors | Q:229-241 | PRESENT | |

---

## 11. Scanner (`ScannerPanel.tsx` S; new adds `useStaffScanner.ts`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Payload input (Enter) + **Resolve** | S:188-198 | PRESENT | `ScanWorkbench` Find |
| 2 | **Scan camera** | S:199,288 | PRESENT | "Start scanning" |
| 3 | Resolving / error / success notes | S:201-203 | PRESENT | New: a recent-scans list |
| 4 | Target heading (box/product/asset) | S:207-211 | PRESENT | |
| 5 | QR `#id` + status line | S:212 | CHANGED | Status pill only; **QR id dropped** |
| 6 | View contents (box) | S:214-216,277-284 | PRESENT | |
| 7 | **Revoke QR** (allowed_actions) | S:217-221 | CHANGED | Moved to a DangerZone at the bottom, and a ConfirmDialog was added |
| 8 | Rename & rebind (product QR; manage_qr+edit_inventory or superadmin) | S:222-248 | PRESENT | |
| 9 | Move to makerspace (asset QR; superadmin) | S:227-269 | PRESENT | |
| 10 | Checkout/return/direct hint | S:270-275 | PRESENT | |

---

## 12. Bulk import (`BulkImport.tsx` B; new adds `BulkImportResults.tsx`)

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Upload CSV/TSV/XLSX | B:102-113 | PRESENT | Upload step, plus drag-drop |
| 2 | Paste table, "Map pasted table" | B:115-117 | PRESENT | Upload step, then "Match columns" |
| 3 | Column mapping (modal) | B:145-161 | PRESENT | "Match columns" step |
| 4 | Edit mapping | B:118 | PRESENT | "Back" from Review |
| 5 | Preview | B:119 | PRESENT | Map step "Preview" (a file now previews via a background job) |
| 6 | **Apply rows** | B:120 | CHANGED | Only reachable after Preview, and **blocked when any row has errors** ("Fix N errors to continue"). The old flow could apply and let the server skip bad rows |
| 7 | **Apply file job** (direct apply) | B:121 | CHANGED | Now requires a preview job first |
| 8 | Advanced JSON: Preview / Apply | B:124-131 | PRESENT / CHANGED | "Use JSON instead" disclosure. Apply only through the Import step |
| 9 | Progress bar, job-tray tracking | B:50,132,163-173 | PRESENT | |
| 10 | File parse error message | B:110 | CHANGED | Replaced by generic copy; the parser's actual message is dropped (new B:103) |
| 11 | Summary metrics + per-row table | B:175-200 | PRESENT | Error rows sorted first. New: "View inventory →" after import |

---

## 13. Navigation into these pages

| # | Capability | Old location | New status | New location / what's needed |
|---|---|---|---|---|
| 1 | Ledger in the "Operate" dock group, label "Ledger" | `staffAccess.ts`(old):56 | CHANGED + BURIED | Under the sidebar Inventory "More (n)" disclosure, renamed **"Stock ledger"**. That label is misleading: the page lists loans currently out, not stock movements (`sidebarSections.ts:16,26`) |
| 2 | Categories, containers, warranty, QR tools, scanner, bulk import | dock group popovers | BURIED | Inventory "More (n)" disclosure. Warranty moved from Insights to Inventory |
| 3 | Inventory, needs-fix, stocktake, transfers, to-buy | dock group popovers | PRESENT | Visible Inventory section items |

---

## Status counts

| Page | PRESENT | BURIED | CHANGED | MISSING |
|---|---|---|---|---|
| Inventory list + add + edit + assets (47) | 28 | 14 | 5 | 0 |
| Categories (6) | 4 | 2 | 0 | 0 |
| Containers (8) | 3 | 4 | 1 | 0 |
| Needs-fix (6) | 5 | 0 | 1 | 0 |
| Stocktake (16) | 10 | 4 | 2 | 0 |
| Transfers (12) | 6 | 2 | 2 | 2 |
| To buy (20) | 8 | 9 | 3 | 0 |
| Ledger (11) | 6 | 3 | 2 | 0 |
| Warranty (9) | 6 | 2 | 0 | 1 |
| QR tools (11) | 6 | 3 | 1 | 1 |
| Scanner (10) | 8 | 0 | 2 | 0 |
| Bulk import (11) | 7 | 0 | 4 | 0 |
| Navigation (3) | 1 | 1 | 1 | 0 |
| **Total (170)** | **98** | **44** | **24** | **4** |

Rows marked "X + Y" are counted once, under the more severe of the two statuses (MISSING > CHANGED > BURIED); the
"+" note in the table names the other status. Row 12-8 ("PRESENT / CHANGED") is counted as CHANGED.

**Bottom line:** almost nothing is actually gone. Only 4 small read-outs/notices are unreachable. The owner's
"functionality is lost" impression comes from **44 BURIED** controls (plus several CHANGED rows that are also buried): every row action collapsed into a `⋯`
menu, inline editors moved into drawers and tabs, and filters moved into a closed popover. It also comes from a
few silent **behaviour changes**: archive no longer confirms, bulk import refuses partial applies, and stocktake
approve/apply left the list.

---

## Restore list (ordered by severity)

Placement follows the Yuyu pattern: **one header primary per page**; **frequent actions visible** (a row
button, a toolbar control or a tab); **rare actions in the overflow**.

### P0: behaviour regressions (fix first)

1. **Archive has no confirmation, but its label promises one.** Old: `InventoryWorkspace.tsx`:279
   (`<ConfirmDialog title="Archive item" … onConfirm={() => archive.mutate(archiveTarget)}>`, with `archiveTarget`
   state at IW:56). New: the row overflow (`InventoryColumns.tsx:21`) and the drawer `DangerZone`
   (`InventoryItemDetail.tsx:46`, `InventoryWorkspace.tsx:225`) archive immediately. **Restore** the `archiveTarget`
   state plus the ConfirmDialog in `InventoryWorkspace.tsx`, and route both entry points through it. **Also decide
   system-wide** whether `Action.confirms` should open a confirm in `ActionControl`/`OverflowMenu`. Today it only
   appends "…", so every "…" label is a broken promise unless its caller wires its own dialog. (Alternative: keep
   undo-only, and then drop the "…" from the DangerZone label.)
2. **Bulk import can no longer apply a partially valid file.** Old: `BulkImport.tsx`:120-121 ("Apply rows" and
   "Apply file job" always enabled). New: `BulkImport.tsx:115` disables Import when `errors > 0`. Product
   decision. If partial apply is intended, enable Import with a warning ("N rows with errors will be skipped").
   **Also restore** the parser's error text (old B:110 `catch((exc) => setError(exc.message))`; new B:103 swallows it).

### P1: frequent daily actions that became BURIED

3. **Stocktake Complete / Approve / Apply are no longer on the list.** Old: `StocktakeSessionPanel.tsx`:87-95
   (row buttons). New: only on the session page (`nextAction`, new SS:70-75,90). **Restore**: in the list row's
   `right` slot, render `nextAction(row)` as a visible ghost button whenever it returns an action. Keep
   "Continue/Open count" for draft/counting rows. Keep the Apply ConfirmDialog.
4. **Ledger "Overdue" is hidden in a popover that shows no active badge.** Old: `Ledger.tsx`:120-123 (visible
   checkbox). **Restore** as a visible control: either add an "Overdue" tab beside the Source tabs (it's a
   separate param, so a second tab group or a toggle chip), or move the checkbox out of `controls` into the
   toolbar. In any case pass `activeCount` (overdue + all-makerspaces) to `ListFilters`. The same fix applies to Warranty's
   Expires-before/Missing-docs (new `WarrantyPanel.tsx:63-64`).
5. **Inventory row actions are all in `⋯`.** Old: `InventoryWorkspace.tsx`:208-214 (Edit, To Fix, Archive/Back to
   inventory, To Buy as visible buttons). **Restore** one context-aware visible row action next to the overflow in
   `InventoryColumns.tsx`:
   - **Archived tab**: a visible "Restore" (`unarchive.mutate`, old IW:212).
   - **Low stock / Out of stock tabs** (when `canUseToBuy`): a visible "Add to To buy" (`openToBuy`, old IW:213).
   - **All tab**: keep "Edit" as the name link. "Move to repair shelf" and "Archive" stay in the overflow.
6. **To-buy row editing moved to a drawer.** Old: `ProcurementPanelRows.tsx`:324-341 (inline vendor, actual cost,
   status select, receipts, Save, Delete). New: the one-click status advance stays visible; everything else is in the
   drawer. **Restore**: when "Mark received" is clicked, open the drawer (or a small modal) to capture the actual unit
   cost and a receipt, because those are recorded at exactly that step. Show the receipt count in the row meta. Add
   "Cancel request" to the row overflow (it can only be set via the drawer select today).
7. **QR tools makes you pick a batch on every visit.** Old: `QrTools.tsx`:33-37 (`useEffect` auto-selects
   `batches.results[0]`) and Q:156-158 ("New batch" always visible). **Restore** the auto-select (or "Continue
   latest batch" as the list's callout) in `useQrBatchBuilder.ts`. Add "New batch" as the batch detail
   header's **secondary** action (`QrTools.tsx:28-29`), and render `createDialog` in the detail view too.
8. **Containers primary is a dead end.** New `ContainersPanel.tsx:18-21` points to QR tools, which cannot create
   containers in either version. **Fix**: change the primary to "New container", backed by `POST /admin/qr/boxes`
   (`apps/boxes` `CreateBoxQrView`; schema in `generated/api.ts:485`), or demote it to plain empty-state copy.
   Also add a row overflow "Edit" that opens the drawer on `containerTab=details` (old visible "Edit", CP:75).

### P2: buried but acceptable; restore cheaply for parity

9. **Reorder suggestions vanish when the inventory list is empty.** Old: always shown at the top (IW:219). New:
   inside `body.table` (new IW:220), so it isn't rendered for empty or filtered-empty lists. **Move**
   `<ReorderSuggestions>` to the `ListLayout` `callout` slot or above the body.
10. **Inventory export of a selection.** Old IW:232-233 labelled "Export CSV (n)" / "Export XLSX (n)". **Restore**
    "Export Excel" in the bulk bar, and make the header Export menu labels say "(n selected)" when there's a selection.
11. **Ledger sort and "All makerspaces"** (old L:97-109,139-145): put the sort select outside the popover
    (the `ListViewControls` `sort` slot). Expose "All makerspaces" as a header secondary toggle for superadmins.
12. **Transfers, superadmin history switch** (old ST:189-195 drove which makerspace's history is listed): add a
    "Makerspace" select to the list toolbar, superadmin only, separate from the dialog. **Restore the
    read-only notice** for non-creators (old ST:176-179) as a `callout`.
13. **Navigation**: rename sidebar "Stock ledger" back to "Ledger" (or "On loan") and promote it, plus Scanner,
    from "More" to visible Inventory items (`sidebarSections.ts:16,26`). Both are daily-use pages.
14. **Individual assets**: Edit and QR history are in the overflow, and the QR is behind a disclosure
    (old IPP:127,135-138). That's acceptable. Consider "Edit" as a visible ghost button, since asset tag/serial/container
    corrections are routine during stocktake.

### P3: MISSING read-outs (trivial)

15. **Transfer `#id`** (old `StockTransferTable.tsx`:306,317): add `#${transfer.id}` to the row meta. Also
    consider restoring the "N lines" count next to "N units".
16. **Warranty host kind** (old `WarrantyPanel.tsx`:130-132): add `row.host_kind` (Asset / Machine / Printer)
    to the row meta, or use a kind-specific identity icon.
17. **Scanner QR id** (old `ScannerPanel.tsx`:212): add `QR #${resolved.qr.id}` beside the status pill.
18. **Stocktake session `#id`** (old SS:82): add it to the row meta and session header meta.
19. **QR tools makerspace card** (old Q:152-155): no action needed; the shell shows the workspace.
