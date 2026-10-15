# UX spec: long-tail screens (Yuyu patterns across all of SpaceWorks)

Status: research only, no app code. Companion to `ux-yuyu-spec.md`, which covers the core screens and
**defines the closed set of page layouts**. This document covers every other screen, so that after the
revamp nothing is left in the old `Panel`-and-stacked-forms style.

Branch `feature/design-revamp`. Visual identity (colour, type, logo) comes from the brand spec and
`PLAN.md` §3. This doc covers layout, information architecture, interaction, states and copy structure only.

---

## 0. How to read this doc

### 0.1 Layouts are the closed set from `ux-yuyu-spec.md`

Every screen below is written as **"Layout X, slots filled by …"**. No screen gets its own page
structure. The layouts are:

`AppShell` (staff/member chrome) · `DashboardLayout` · `ListLayout` · `DetailLayout` ·
`SettingsLayout` · `FlowLayout` (wizard) · `AuthLayout` · `CenteredCardLayout` · `PublicLayout` ·
`PublicDetailLayout` · `KioskLayout`.

The slot names below are what this doc assumes each layout exposes. **Where `ux-yuyu-spec.md` names a slot
differently, its names win.** The mapping is one-to-one, so a rename does not change any screen spec.

| Layout | Slots assumed here |
|---|---|
| `DashboardLayout` | `greeting` (muted date/line), `title`, `actions` (1 primary pill + 1 outline), `callouts[]`, `stats[]`, `main` (sections), `rail` (activity / at-a-glance) |
| `ListLayout` | `title`, `subtitle`, `actions`, `callouts[]`, `stats[]`, `tabs` (underline, with count badges), `toolbar` (search, filters, saved views, bulk bar), `list` (card rows or `DataTable`), `pagination`, `rail?` |
| `DetailLayout` | `back` ("← All x"), `identity` (date/identity chip), `title`, `status` (pill), `meta` line, `actions`, `tabs`, `body`, `rail?` (at-a-glance, callout card) |
| `SettingsLayout` | `title`, `subtitle`, `subnav?` (in-page section list), `sections[]` of `SettingsRow` (label + helper left, field right, hairlines), `footer` (Discard / Save), `dangerZone?` |
| `FlowLayout` | `back`, `title`, `stepper` ("Step 2 of 4 · Map columns"), `step` body, `aside?` (live preview / summary), `footer` (Back · Next/Finish), **presentation `page` or `dialog`** (see §11 gaps) |
| `AuthLayout` | `form` (left), `brand` panel (right) |
| `CenteredCardLayout` | `logo` (top-left), `icon` tile, `eyebrow`, `title`, `body`, `primary` (full-width pill), `secondary` link, `footnote` ("Signed in as … · Switch account") |
| `PublicLayout` | `PublicShell` header (space brand, nav, Sign in), `hero` (eyebrow, title, intro), `toolbar?`, `content`, footer |
| `PublicDetailLayout` | `PublicShell` header, `hero`, `main`, `aside` (sticky action card), footer |
| `KioskLayout` | `station bar` (space avatar, station name, counter, online pill, "Lock station"), `stage` (scanner / PIN pad / result), `side` (result panel / recent list), no app chrome |

### 0.2 Conventions used by every screen here (so they are not repeated per screen)

- **One primary action per page.** Actions are ranked as primary (dark/teal pill), secondary (outline
  pill, at most one or two) and the rest in a **More menu** (`[More v]`, an outline icon button; it opens a
  menu of labelled items). Exports (CSV/XLSX) always go in More as "Export CSV" / "Export Excel".
- **Row actions:** one inline text action at the right of the row (Yuyu "Send invites", "Undo"). Every
  other row action goes in a row overflow `[...]` menu. Destructive items sit last in red and always
  confirm.
- **Inline Undo** (Yuyu mgr2/att11) is used for reversible one-click state changes that the API already
  supports reversing. Where the API has no reverse, use a confirm dialog and do not fake an Undo.
- **Contextual callout** (warm yellow, icon, bold lead sentence, action link on the right) replaces
  today's `bg-warn` boxes, read-only notices and disclosure paragraphs. There is at most **two per page**.
  Long legal or disclosure text goes behind "Read the details" (a disclosure that expands in place).
- **Danger zone** (red-outlined card, last on the page) collects every irreversible control on a
  settings-style page. Red buttons do not appear mid-page.
- **Stat cards** show label + big number (+ optional progress bar). Each one is tagged in this doc
  `[loaded]` (the number is already in the response the page fetches) or `[+query]` (needs one extra
  request to an **existing** endpoint, usually a filtered list `count`). No stat needs a backend change.
  If `[+query]` cost is a concern, drop that card. The layout copes with 2–4 cards.
- **Tabs** are underline tabs. A count badge appears only when the number is `[loaded]`. Tab state lives
  in the URL query (`?view=` / `?section=`), using the same mechanism `ListViewControls`/`useListState`
  already use. `StaffWorkspace` canonicalisation keeps `location.search`
  (`<Navigate to={activeTabPath + location.search} />`), so **no `staffTabs.ts` change is needed**. Only
  `machines` may carry a path segment, and that stays true.
- **States voice** (brand: clear, warm, specific, says the next step):
  - Empty: "No {things} yet. {Do the next thing}." The primary action is repeated as a button inside the
    empty card (dashed border, Yuyu org4/org6).
  - Filtered empty: "Nothing matches these filters." + "Clear filters" link.
  - Loading: skeleton rows or skeleton stat cards that match the final layout. No "Loading..." text
    except in `aria-live` status.
  - Error (load): "Couldn't load {things}. Check your connection and try again." + "Try again" button.
    The raw server message goes in a muted second line when it is useful.
  - Error (action): an inline message under the control that failed: "Couldn't {verb}. {reason}." Never
    a stack of `<p className="text-danger">` lines at the top of a panel. Today's multi-error pile-ups
    (e.g. Transfers renders 5 separate error lines) collapse into one message per failed control.
  - Success: a toast "{Thing} {done}." with Undo where reversible.
- **Status pills** are a soft tint plus a word, always (brand: never colour alone).
- **Copy rules:** sentence case; "Space Works" in prose; no raw enum values on screen
  (`paid_offline` → "Paid in person", `in_progress` → "Printing"); no `#123` IDs as primary labels;
  no feature-flag keys or app labels in user-facing text except on superadmin/deployment screens.
- **Accessibility carried forward:** keep existing accessible names that tests may pin (they live in the
  gitignored test trees in the main checkout). Examples: `aria-label="Personal notifications"`, the "QR
  payload" label, "Search and commands", "Sign out", "Station PIN". If a name must change, the matching
  test changes in the same commit.

### 0.3 Yuyu reference screens cited

| ID | Yuyu board / screen | Pattern it contributes |
|---|---|---|
| org1 | Organiser workspace · Home | greeting + date, "Your organisations" cards, dashed "+ New" card, "Coming up" date-chip rows, Recent activity rail |
| org2 | Organiser workspace · Events | title + 1 primary + 1 outline, yellow callout with link, 4 stat cards, underline tabs with counts, date-chip card rows, inline row action, dashed draft row, activity rail + "See all →" |
| org3 | Organiser workspace · New organisation | form left, **live public-page preview** right, primary + text "Cancel" |
| org4 | Organiser workspace · Members | "Invite someone" card (link field + status pill, Copy / New link / Revoke), person table with avatar, dashed empty "It's just you so far…" |
| org5 | Organiser workspace · Settings | settings sub-nav under the active item, label + helper left / field right, hairlines, Discard / Save, red danger-zone card |
| org6 | Organiser workspace · API access | "New API client" card with scope check-cards, dashed empty list, yellow "Keep keys in a secret manager" strip, dark code block with Copy, accordion reference |
| mgr1 | Managing an event · Overview | "← All events", date chip + title + status pill + meta, outline + primary pill, underline tabs, stat cards, "Latest …" list + "All guests →", "At a glance" key-value card, yellow callout card |
| mgr2 | Managing an event · Check-in | progress stat card, yellow callout with dark action, camera block + "Start scanning", "Find a guest" search, toggle rows, "Recent check-ins" with **Undo**, door-station card (Copy link / Show PIN / New PIN / red "Turn off station") |
| mgr3 | Managing an event · Page & programme | segmented control, column cards, dashed "+ Add session" |
| mgr4 | Managing an event · Series | upcoming-date cards (first highlighted), details form, agenda list, danger zone |
| auth2 | Sign in, invites & account · Set new password | small centred card, icon tile, strength meter + rule check, "Back to sign in" |
| auth3 | Confirm email | centred card, icon tile, bold address in body, full-width primary, "Not you? Use another account" |
| auth4 | Join organisation invite | overlapping avatar tiles, "You've been invited to join", role pill, one-time-link note, "Accept invite", "Signed in as … · Switch account" |
| auth5 | Co-organiser invite | coloured header band, scoped-permission note box, "Accept & open event" |
| auth6 | Account · Profile | title + subtitle, underline tabs Profile / Security, settings rows, "Member since …" + Save |
| auth7 | Account · Security | yellow "Two-step sign-in is off" callout with dark action, password rows, "Sign out everywhere" red-outline |
| att9 | Attending · You're in | ticket card with QR, "Add to calendar" + "Save ticket", cancel link |
| att10 | Attending · Station PIN | big title, 8 PIN boxes, numeric pad, disabled "Open check-in" until complete |
| att11 | Attending · Door scanner | station bar (counter, Online pill, Lock station), scanner frame, big green result panel with "Next guest" + "Undo", recent list, search + Find |

---

## 1. Batch index (implementation order)

Screens are grouped by layout so each batch composes the same primitives.

| Batch | Layout | Screens |
|---|---|---|
| **A** Operational lists | `ListLayout` | Payments, Ledger, Transfers, Stocktake, To buy, To-be-fixed, Notifications, Delivery logs, Accountability, Warranties, Organized events, Member cards, Devices, Data export, Categories, Containers, Job handover, Email templates (index) |
| **B** Detail / editor | `DetailLayout` | Email template editor, Stocktake session, Container detail (drawer), Device detail (drawer), Machine service / printer queue (tab body inside the core machine-type page) |
| **C** Configuration | `SettingsLayout` | API access, Modules, Platform settings, Backup & restore, Organizations (org workspace), Member account (`/member/account`), Staff MFA (`/mfa`) |
| **D** Read-only analytics | `DashboardLayout` | Platform dashboard, Usage & limits, Organization analytics, Makerspace picker (superadmin) |
| **E** Flows | `FlowLayout` | Bulk import, QR tools (print batch), Create makerspace, Tenant migration, Password recovery |
| **F** Gates and system cards | `CenteredCardLayout` | Change-password gate, MFA challenge, Access denied, Recovery quarantine, Reset password (legacy link), Org invitation redeem, 404, route/session loading, "No makerspace" |
| **G** Public pages | `PublicLayout` / `PublicDetailLayout` | Landing directory, About, Public machines, Public bookings, Public events list (only if the core spec leaves it out), Print request, Public stats, Public organization, Event feedback, Self-checkout, Archived payments, FamilyHome fallbacks |
| **H** Member tab bodies | `AppShell` (member) + `ListLayout` / `SettingsLayout` | Loans, Bookings, Events (+ partner events), Payments, Inbox, Account portal (profile, card, directory, referrals, certifications) |
| **I** Stations | `KioskLayout` | Event check-in station, Public desk kiosk, Scanner page, PWA offline page |
| **J** Overlays (no layout) | dialog / popover | Command palette, Job tray, Setup checklist, payment dialogs, device enrollment, column mapping, panel error boundary |

---

## 2. Batch A — Operational lists (`ListLayout`)

### A1. Payments — tab `payments`
- **Route** `/admin/payments` · `features/staff/PaymentsPanel.tsx` (+ `PaymentRefundDialog`, `SettlementDialog`,
  `RefundReceiptAmendDialog`, `payments/PaymentDocuments.tsx`). Gate: `view_finance` or `record_payment`
  (`forRecording` mode = record-only actor).
- **Job:** see what money is owed, record cash/bank receipts, waive or refund, find a receipt.
- **Yuyu:** org2 (stats + tabs + card rows), mgr1 ("At a glance"), mgr2 (Undo).
- **Layout:** `ListLayout`.
  - `title` "Payments", `subtitle` "Money owed to {space}, and how it was paid."
  - `actions`: primary **none by default** (nothing is created here). Outline secondary: "Receipts &
    credit notes" (opens a side drawer that hosts `PaymentDocuments`, instead of the inline show/hide
    section). More: Export CSV, Export Excel (if the export exists; today none is wired, so More is empty
    and hidden).
  - `callouts`: when `due_state=overdue` count > 0: "**{n} charges are overdue.** Oldest is {age} old." →
    "Show overdue".
  - `stats`: Pending (count) `[+query]` · Overdue `[+query]` · Paid this month `[+query]` (omit if no date
    filter exists; otherwise show Pending/Overdue/Waived). Hidden for `forRecording` actors, who see only
    Pending.
  - `tabs` (one tab per value of the existing single-valued `status` filter): **To collect** (pending) ·
    **Paid online** · **Paid in person** · **Waived** · **Cancelled** · **All**. Record-only actors see
    To collect · Paid in person (matching today's `forRecording` filter).
  - `toolbar`: Due (All / Due today / Upcoming / Overdue) as chips on the To collect tab only; Subject
    select; sort menu; saved views (existing `ListViewControls`). Bulk bar on select: "Mark paid in person
    ({n})" (primary in bar) · "Waive ({n})".
  - `list`: `DataTable` on desktop, stacked cards under `md`. Columns: Subject (label + type as muted
    meta), Due (`PaymentDueBadge` as soft pill), Amount (bold, right), Refunded (muted, only if > 0),
    Received (settlement summary, "corrected" pill). Row inline action: on pending → **"Mark paid"**
    (opens settlement dialog). Row overflow: Waive, Correct receipt, Refund / Release deposit, Correct
    refund #n.
- **Wireframe**
```
Payments                                            [Receipts & credit notes]
Money owed to Fab Lab, and how it was paid.
┌ ! 3 charges are overdue. Oldest is 12 days old.            Show overdue → ┐
┌Pending──┐┌Overdue──┐┌Waived───┐
│ 14      ││ 3       ││ 2       │
└─────────┘└─────────┘└─────────┘
 To collect 14 | Paid online | Paid in person | Waived | All
 [Due: All · Today · Upcoming · Overdue]  [Subject v]  [Sort v]  [Views v]
┌──────────────────────────────────────────────────────────────────────────┐
│[ ] Laser job #A12 · Machine service   Due in 2 days   ₹450    Mark paid [...]│
│[ ] Monthly dues · Membership          Overdue 12 d    ₹800    Mark paid [...]│
└──────────────────────────────────────────────────────────────────────────┘
                                              ‹ 1 2 3 ›
```
- **Mobile:** stats become a 2×2 grid; tabs scroll horizontally; rows stack as cards (subject, amount
  right, due pill under, "Mark paid" full-width).
- **Dialogs:** Settlement ("Record payment" / "Record payment for 3 charges"): method, reference
  (optional), received date, then **"Save receipt"** + Cancel. Refund: amount (prefilled with refundable
  balance), method/reference/date for manual rail, reason, then **"Refund ₹450"** (the verb carries the
  amount). Release deposit uses the same dialog with title "Release deposit". Amend: "Correct receipt",
  then "Save correction". All four use the `Modal` restyle with footer Cancel (outline) + primary.
- **States:** empty To collect: "Nothing to collect. Every charge here is paid or waived." · empty All:
  "No payments yet. Charges appear here when someone books, registers or borrows." · filtered: standard ·
  conflict (409): inline callout on the row "Someone else updated this charge. Refreshed." · load error:
  standard.
- **Undo:** none. Settlement writes an append-only receipt, so use the confirm dialog and do not fake an
  Undo.

### A2. Ledger — tab `ledger`
- **Route** `/admin/ledger` · `panels/Ledger.tsx`, `LedgerParts.tsx`. Gate `view_inventory`.
- **Job:** answer "what is out right now, with whom, and what is late?"
- **Yuyu:** org2 (stats + list), mgr1 (latest list).
- **Layout:** `ListLayout`.
  - `title` "Ledger", `subtitle` "Everything that's out right now."
  - `actions`: no primary (read-only). More: Export CSV, Export Excel. Superadmin: a toggle chip "All
    makerspaces" in `toolbar` (not a header action).
  - `stats`: Items out (sum of qty) `[loaded]` · Records `[loaded]` · Overdue `[+query overdue=1]`.
  - `callouts`: overdue > 0: "**{n} loans are overdue.**" → "Show overdue" (sets the existing Overdue
    toggle). If `accountability` is allowed, a secondary link "Open accountability →".
  - `tabs`: All · Reviewed · Self-checkout · Direct (the existing Source filter, promoted to tabs).
  - `toolbar`: search "Holder, email, item or box", "Overdue only" chip, sortable headers stay.
  - `list`: card rows. Left: an **identity chip** (initials of the holder, stable tone). Title = item
    name (+ "Box: X" meta, unit tags). Meta = holder · out since {date}. Right = qty + due pill ("Due
    Fri" / "Overdue 3 d" red-tinted). Row click: if the record maps to a request or direct loan, open it
    (core request detail). Otherwise no click.
- **Wireframe**
```
Ledger                                                              [More v]
Everything that's out right now.
┌Items out┐┌Records┐┌Overdue┐
│ 37      ││ 21    ││ 4     │
 All | Reviewed | Self-checkout | Direct
 [Search holder, email, item or box........]  (Overdue only)
┌ (AK) Arduino Uno ×2 · Box B-04           Out since 3 Oct   Due Fri ┐
┌ (RM) Soldering station                   Out since 1 Oct   Overdue 3 d ┐
```
- **States:** empty: "Nothing is out right now. Loans appear here the moment they're handed over." ·
  load error: standard.

### A3. Transfers — tab `transfers`
- **Route** `/admin/transfers` · `panels/StockTransferPanel.tsx`, `StockTransferTable.tsx`. Gate
  `edit_inventory` or superadmin.
- **Job:** move stock between containers or makerspaces, with a reason, and see the history.
- **Yuyu:** org2 list + org3 (form in its own surface, not above the list).
- **Layout:** `ListLayout` for history. The create form moves out of the page top into a **`FlowLayout`
  dialog** "New transfer" (two steps: *From and to* → *What's moving*, with Reason on step 2).
  - `title` "Transfers", `subtitle` "Stock moved between boxes and spaces."
  - `actions`: primary **"New transfer"** (hidden for read-only actors).
  - `callouts`: read-only actor: "**Transfers are managed by inventory staff.** You can see the history
    but not move stock." (replaces the warn box).
  - `list`: rows with a **direction chip** (→ icon) + "{qty} {product}" title, meta "{from} → {to} ·
    {reason}", right = date + actor initials.
  - Dialog step 1: Source container, Destination container (superadmin also gets Source/Destination
    makerspace, shown first). When cross-makerspace, an info callout replaces the long paragraph: "**This
    moves stock to {space}.** A matching product is created there if needed and stays private until they
    publish it." with "Read the details" for the asset-tracked limitation. Step 2: line editor (product +
    qty, "+ Add line" dashed row, remove via row `[...]`), Reason. Footer: Back · **"Move stock"**.
- **States:** empty: "No transfers yet. Move stock between boxes or spaces with New transfer." ·
  validation: inline per line ("Only {n} available").

### A4. Stocktake — tab `stocktake`
- **Route** `/admin/stocktake` · `panels/StocktakeSessionPanel.tsx`, `StocktakeCountSection.tsx`,
  `StocktakeDiscipline.tsx`. Gate `edit_inventory`; policy needs `canConfigure`.
- **Job:** start a count, count items (by scan), complete, approve, apply adjustments.
- **Yuyu:** org2 (session list with status), mgr4 (detail with sections), mgr2 (scan + recent with Undo).
- **Split:** today one page holds policy, schedules, a create form, every session and an inline count
  table. Split into:
  1. **Sessions list** — `ListLayout`.
  2. **Session detail** — `DetailLayout` (see B2), opened by `?session={id}` (query param, no route change).
  3. **Policy & schedules** — a `SettingsLayout` section reached from More: "Count policy and schedule"
     (opens as a side drawer holding settings rows). Shown only to `canConfigure`.
- **List slots:** `title` "Stocktake", `subtitle` "Count what's on the shelves and fix the numbers."
  `actions`: primary **"Start count"** (opens a small dialog: Container (All containers), Notes,
  Visibility (Use space policy / Blind / Show expected)). More: "Count policy and schedule".
  `callouts`: a schedule is due: "**Monthly cycle count is due today.**" → "Start it". `stats`: In
  progress `[loaded from list]` · Awaiting approval `[loaded]` · Applied this month `[+query]`. `tabs`:
  Active (draft+counting) · Needs approval (completed) · Ready to apply (approved) · Done (applied,
  cancelled). Rows: status pill, title = notes or "Count of {container|all containers}", meta = started
  {date} · {n} lines counted. Inline action by status: Counting → "Continue", Completed → "Approve",
  Approved → "Apply".
- **States:** empty: "No counts yet. Start a count to check the shelves against the system." · Needs
  approval empty: "Nothing waiting for approval."

### A5. To buy (procurement) — tab `tobuy`
- **Route** `/admin/to-buy` · `panels/ProcurementPanel.tsx`, `ProcurementPanelRows.tsx`,
  `ProcurementReceipts.tsx`, `ProcurementMoveModal.tsx`, `ReorderSuggestions.tsx`. Gate `canUseToBuy`;
  kind chooser for `manage_makerspace`.
- **Job:** keep a shopping list, track it from requested to received, then move it into inventory.
- **Yuyu:** org2 (tabs by lifecycle, rows with inline next-step action).
- **Layout:** `ListLayout`.
  - `title` "To buy", `subtitle` "What the space needs, from request to shelf."
  - `actions`: primary **"Add item"** (dialog: Name, Qty, Link, Est. unit cost, Machine type when
    required, Kind for space managers). More: Export CSV, Export Excel.
  - `callouts`: `ReorderSuggestions` becomes a callout: "**{n} items are running low.**" → "Review
    suggestions" (opens a drawer listing them with "Add to list"). Received but not moved: "**{n}
    received items aren't in inventory yet.**" → "Move them".
  - `stats` (all `[loaded]`, they are computed today): Estimated total (visible) · Open budget · Spent
    (received actual).
  - `tabs` (status): Requested · Approved · Ordered · Received · Cancelled · All, with counts `[loaded]`.
  - `toolbar`: group-by chip "By machine type" (on by default when grouping exists today).
  - `list`: replace the 14-column editable table (min-width 1180 px) with **card rows**: title = item ×
    qty, meta = vendor · est. ₹ · purchaser, right = status pill + **one next-step inline action** by
    status: Requested → "Approve", Approved → "Mark ordered", Ordered → "Mark received", Received →
    "Move to inventory". Editing vendor, actual cost, status and receipts happens in a **row drawer**
    ("Edit" in the row `[...]`), which also hosts receipts (View / Delete). Delete is the last overflow item
    and confirms.
- **Mobile:** this fixes today's horizontal scroll; cards are naturally stacked.
- **States:** empty: "Nothing on the list yet. Add the first thing your space needs." · load error:
  "Couldn't load the list. Try again." (replaces "Unable to load list.") · receipt errors inline in the
  drawer.

### A6. To-be-fixed shelf — tab `needsfix`
- **Route** `/admin/to-be-fixed` · `panels/NeedsFixShelf.tsx`. Gate `edit_inventory`.
- **Job:** repair or scrap units that came back broken.
- **Yuyu:** org2 rows with an inline action, mgr2 Undo.
- **Layout:** `ListLayout`.
  - `title` "To be fixed", `subtitle` "Units returned broken. Repair them back into stock, or scrap them."
  - `actions`: none (items arrive from returns).
  - `stats`: Units to fix `[loaded sum]` · Products affected `[loaded]`.
  - `list`: rows with a warm "{n} to fix" pill, meta "{available} available · {total} total". Right: a
    qty stepper (defaults to all), inline primary-text action **"Repaired"**, row `[...]` → "Scrap…"
    (confirm: "Scrap 2 × Multimeter? They're removed from inventory for good.").
  - After "Repaired": toast "2 × Multimeter back in stock." There is no Undo, because the API has no
    reverse action.
- **States:** empty: "Nothing on the shelf. Broken returns land here for repair." (success-tinted icon
  tile, not muted text).

### A7. Notifications (personal inbox + broadcast) — tab `notifications`
- **Route** `/admin/notifications` · `panels/NotificationInbox.tsx` → `notifications/PersonalInbox.tsx`,
  `staff/BroadcastComposer.tsx`. Gate any staff action.
- **Job:** catch up on what happened that needs me; managers can also send a member announcement.
- **Yuyu:** org1/org2 Recent activity rail (this page is its "See all →" destination).
- **Layout:** `ListLayout`.
  - `title` "Notifications", `subtitle` "{n} unread" (live; keep the unread count in an `aria-live`
    region and in the sidebar item's accessible name, as pinned today).
  - `actions`: primary **"Mark all read"** (disabled at 0). Outline secondary, managers with
    `membership.broadcasts`: **"Send announcement"**. It opens a dialog with the existing composer fields
    (Title, Body, Audience) and the button "Send announcement". The composer card is no longer pinned
    above the inbox.
  - `tabs`: Unread {n} · All.
  - `toolbar`: Family chips (Hardware, Printing, Events, Bookings, Maintenance, Members, Payments, Stock,
    Certifications, Devices, API access). Raw keys become labels.
  - `list`: activity-style rows (Yuyu rail, full width). Avatar/icon tile by family · **bold title** +
    summary (2 lines, clamp) · relative time ("2 min ago") · unread dot. Inline action "Open" when there is
    a safe link. Row click marks it read. Unread rows get a teal left rule, not a teal border box.
  - Date group headers: Today · Yesterday · Earlier this week · Older.
- **States:** empty Unread: "You're all caught up." · empty All: "No notifications yet. Activity from your
  space shows up here." · load error: standard.

### A8. Delivery logs (+ suppressions) — tab `email-logs`
- **Route** `/admin/email-log` · `panels/DeliveryLogPanel.tsx` → `notifications/DeliveryLogScreen.tsx`,
  `notifications/SuppressionAdmin.tsx`. Gate `manage_makerspace`. (`panels/EmailLogPanel.tsx` is still
  exported from `StaffPanels.tsx` but no route mounts it. Flag it for deletion as a separate cleanup, not
  in this revamp.)
- **Job:** check that alerts and emails went out, retry failures, send a test, manage suppressed
  addresses.
- **Yuyu:** org2 (tabs + rows + inline action), org6 (developer-ish surface kept calm).
- **Layout:** `ListLayout` with two tabs that split today's stacked sections.
  - `title` "Delivery logs", `subtitle` "Every email and alert this space sent, and whether it arrived."
  - `actions`: primary **"Send test"**. It opens a small dialog "Send a test to…" (Email to my account /
    each active destination) and the result shows as a toast with "View in log".
  - `callouts`: failed in the current filter > 0: "**{n} deliveries failed.**" → "Show failed".
  - `tabs`: **Deliveries** · **Suppressed addresses**.
  - Deliveries `toolbar`: Status chips (All, Sent, Failed, Pending, Skipped), Channel select, Destination
    select, Family select, Event text in More filters. `list` rows: channel icon tile · title
    "{Family} · {event}" humanised · meta "{destination or Personal devices} · {n} attempts · {time}" ·
    status pill (Sent / Failed / Skipped "blocked by Email module" / Sending) · inline **"Retry"** on
    failed rows. The error text shows under the row in muted red.
  - Suppressed tab: `actions` changes to primary "Suppress an address" (dialog). Rows: address, reason,
    date, inline "Remove".
- **States:** empty Deliveries: "Nothing sent yet. Send a test to check your setup." · filtered: standard ·
  empty Suppressed: "No suppressed addresses. Bounced or blocked addresses appear here."

### A9. Accountability — tab `accountability`
- **Route** `/admin/accountability` · `panels/AccountabilityPanel.tsx`. Gate `view_audit`.
- **Job:** follow up on overdue loans and reported problems, and restrict or restore repeat offenders.
- **Yuyu:** org2 (stats + tabs), mgr1 ("Latest …" lists).
- **Layout:** `ListLayout` with tabs that replace the four stacked `Panel`s and the "Show all
  accountability sections" button. The existing `section` list filter becomes the tab key.
  - `title` "Accountability", `subtitle` "Late, lost or damaged — and who it's tied to."
  - `stats` (each a tab shortcut): Overdue loans `[loaded count]` · Open problems `[loaded]` · Repeat
    offenders `[loaded]` · Restricted `[loaded]`.
  - `tabs`: Overdue · Problems · Repeat offenders · Restricted.
  - Overdue rows: identity chip (holder) · item · "Overdue {n} d" pill · inline "Open loan".
  - Problems rows: item · reporter · reported {date} · problem text (2-line clamp).
  - Repeat offenders rows: person · damage/loss counts · status pill · inline **"Restrict…"** (dialog
    with required reason; button "Restrict {name}") or **"Restore access"** if restricted.
  - Restricted rows: person · reason · since · inline "Restore access".
- **States:** Overdue empty: "No overdue loans. Nice." · Problems empty: "No open problem reports." ·
  Offenders empty (named): "No damage or loss on record against a named person." · Restricted empty: "No
  one is restricted here."

### A10. Warranties — tab `warranty`
- **Route** `/admin/warranty` · `panels/WarrantyPanel.tsx` (+ `WarrantySection`, `WarrantyStatusBadge`).
  Gate `edit_inventory` or printing/machines.
- **Job:** see what's covered, what's expiring, and what's missing documents.
- **Yuyu:** org2.
- **Layout:** `ListLayout`.
  - `title` "Warranties", `subtitle` "Coverage for {scope} in {space}."
  - `stats`: Active · Expiring soon · Expired · Missing docs. Each is `[+query]` filtered count. If that
    is too costly, keep only the total `[loaded]` in the subtitle.
  - `tabs`: All · Active · Expiring soon · Expired · Not covered (the existing status filter).
  - `toolbar`: "Expires before" date, "Missing docs" chip.
  - `list`: rows. Identity chip (machine or asset) · host name · vendor · purchased → expires · status
    pill · docs count. Inline "Manage" opens the existing `WarrantySection` in a **side drawer** instead of
    an inline expanded table row.
- **States:** empty: "No warranties recorded yet. Add one from a machine or asset." · filtered: standard.

### A11. Organized events — tab `organized`
- **Route** `/admin/organized-events` · `panels/OrganizedEventsPanel.tsx` (+ `EventDrawer`). Gate:
  non-superadmin, not single-tenant.
- **Job:** an organization organizer sees the events they run across venues.
- **Yuyu:** org2 exactly (date-chip rows, going/capacity progress).
- **Layout:** `ListLayout`.
  - `title` "Organized events", `subtitle` "Events you run with your organization, across spaces."
  - `tabs`: Upcoming · Past (client split by date on the loaded page, or a query param if the API
    supports it; otherwise a single list in chronological order with a "Past" divider).
  - `list`: **date chip** (MON/DD, tone by host space) · title · meta "{location or Online} · {host
    space}" · right: "{going} / {capacity} going" + thin progress bar, status pill. Row click opens the
    existing `EventDrawer`.
- **States:** empty: "No organized events. Events your organization runs will appear here." · load error
  with "Try again".

### A12. Member cards — tab `cards`
- **Route** `/admin/member-cards` · `panels/MemberCardsPanel.tsx`, `memberCards/*`. Gate member-card
  actions; module `membership`.
- **Job:** issue, print, reissue and revoke member cards; scan a card at the desk.
- **Yuyu:** org4 (invite card on top + table), mgr2 (scan block).
- **Split:** today one long page holds the cards table, a scan box, an issue roster and the card layout
  form. Use **tabs**: Cards · Issue · Scan · Card layout.
- **Layout:** `ListLayout`.
  - `title` "Member cards", `subtitle` "Printable cards that open the member area at the desk."
  - `actions`: primary **"Print sheet"** (label "Print sheet (3 selected)" when there is a selection,
    else "Print all active"). Secondary outline: "Scan a card" (jumps to the Scan tab).
  - `stats`: Active cards `[loaded]` · Members without a card `[loaded from roster]`.
  - Cards tab: status segmented control Active / Revoked (existing), `DataTable` with Card number, Name,
    Status pill, Prints, Photo (✓ / —). Row inline "Print". Row `[...]` "Reissue…" and "Revoke…"
    (existing dialogs, restyled).
  - Issue tab: org4-style list "Members without a card", each row with inline **"Issue card"**.
  - Scan tab: the shared **ScanWorkbench** section (§11.2) with the card result panel.
  - Card layout tab: a `SettingsLayout` body (settings rows) with Save.
- **States:** Active empty: "No cards yet. Issue one from the Issue tab." · Issue empty: "Every active
  member has a card." · Revoked empty: "No revoked cards."

### A13. Devices — tab `devices`
- **Route** `/admin/devices` · `panels/DevicesPanel.tsx`, `DeviceIdentitySection.tsx`,
  `DeviceEnrollmentModal.tsx`. Gate `manage_devices`; module `devices`.
- **Job:** register printers and label printers, see which are offline, enrol or revoke them.
- **Yuyu:** org4 (people table → device table), org6 (one-time secret handling).
- **Layout:** `ListLayout` + detail drawer.
  - `title` "Devices", `subtitle` "Printers and other hardware that talk to Space Works."
  - `actions`: primary **"Add device"** (dialog: Name, Kind (Generic / Printer / Label printer), then
    "Create device"; on success it opens the enrollment dialog straight away).
  - `stats`: Online · Offline · Revoked (`[loaded]` from the current page only, or `[+query]`).
  - `list`: rows. Kind icon tile · name · meta "Last seen 4 min ago" / "No heartbeat yet" · status pill
    (Online / Offline since {time} / Revoked). Row click opens a **drawer** (replaces the `aria-pressed`
    button + section below the table) with settings rows: Name, Offline threshold, then Save; actions
    "New enrollment token"; danger zone "Revoke device".
  - Enrollment dialog (org6 pattern): yellow strip "**Copy this now.** It won't be shown again." ·
    dark code block with the token and **Copy** · purpose and expiry as meta · footer primary "I've copied
    it" (replaces "Close and discard token").
- **States:** empty: "No devices yet. Add a printer to send jobs straight to it." · load error with
  "Try again".

### A14. Data export — tab `exports`
- **Route** `/admin/data-export` · `features/staff/DataExportsPanel.tsx`. Gate `manage_makerspace`.
- **Job:** get a readable archive of this space's records.
- **Yuyu:** org6 (warning strip + clients list), auth7 (callout with action).
- **Layout:** `ListLayout`.
  - `title` "Data export", `subtitle` "A readable copy of your space's records. Not a backup."
  - `actions`: primary **"Request export"** (disabled while one is running; tooltip "An export is already
    being built").
  - `callouts`: one yellow callout replaces the three-paragraph disclosure: "**Exports include member
    names, emails and phone numbers.** Handle the file like any personal data." → "Read what's included"
    (expands the full existing text, unchanged).
  - `list`: job rows. Icon tile · "Export · {date}" · meta "{rows} rows" · status pill (Queued /
    Building / Ready / Failed) · inline **"Download"** when ready. Failure detail as a muted red line.
  - Running jobs also show in the **Job tray**.
- **States:** empty: "No exports yet. Request one when you need a copy of your records." ·
  deadline-exceeded failure: "This export took too long. Try again at a quieter time."

### A15. Categories — tab `categories`
- **Route** `/admin/categories` · `panels/Categories.tsx`. Gate `edit_inventory`.
- **Job:** organise products into categories.
- **Yuyu:** org4 (simple table) + org3 (create in a focused surface).
- **Layout:** `ListLayout`.
  - `title` "Categories", `subtitle` "How items are grouped in the catalogue."
  - `actions`: primary **"Add category"**. A dialog replaces the always-visible 5-field inline row: Name,
    Slug ("Leave blank to use the name"), Icon, Order.
  - `list`: `DataTable` (Name, Products, Order, Icon) with inline "Edit" (same dialog) and row `[...]`
    "Delete…" (existing confirm: "Delete {name}? {n} items lose this category.").
  - Reorder: keep the numeric order field. Drag reordering is out of scope.
- **States:** empty: "No categories yet. Add one to group your catalogue." · load error: standard.

### A16. Containers — tab `containers`
- **Route** `/admin/containers` · `panels/ContainersPanel.tsx`. Gate `manage_qr`; module `containers`.
- **Job:** find a box, see what's in it and its scan history, edit its label or location.
- **Yuyu:** org2 list → mgr1 detail with tabs.
- **Layout:** `ListLayout`; each container opens a **detail drawer** with tabs (B3), replacing the inline
  Edit / Contents / History toggles inside each card.
  - `title` "Containers", `subtitle` "Boxes, bins and shelves with QR labels."
  - `actions`: primary **"New container"**, which links to QR tools (today: "Create one in QR tools"),
    labelled "Create in QR tools". More: none.
  - `toolbar`: search, Active / Inactive chips.
  - `list`: rows. Code chip (the container code in the identity chip) · label · meta location · Inactive
    pill when inactive · right: "{n} items" if loaded.
- **States:** empty: "No containers yet. Create labelled boxes in QR tools." with the button.

### A17. Job handover (machine service) — tab `handover`
- **Route** `/admin/handover` · `panels/machine/HandoverConsole.tsx`. Gate `collect_service_request` or
  `manage_machines`; module `machine_service`.
- **Job:** at the desk, hand finished jobs to the people who requested them.
- **Yuyu:** mgr2 "Recent check-ins" rows with an inline action; org2 rows.
- **Layout:** `ListLayout`.
  - `title` "Ready to collect" (today the panel title is "Awaiting collection"; the tab label "Job
    handover" stays in the nav), `subtitle` "Finished jobs waiting for their owners."
  - `stats`: Waiting `[loaded]` · Unpaid `[loaded]`.
  - `toolbar`: search by requester (client-side filter on the loaded list).
  - `list`: rows. Identity chip (requester initials) · job title · meta "{machine} · finished {relative}"
    · payment pill (Paid / Unpaid ₹x) · inline primary-text **"Hand over"**. When unpaid, the inline action
    becomes "Collect payment" and links to the payment, and "Hand over" moves to the row `[...]`, but only
    if the API allows handover while unpaid (today it does, so keep "Hand over" inline and show the unpaid
    pill as a warning).
  - After handover: the row collapses with toast "Handed to {name}." No Undo, because there is no API
    reverse.
- **States:** empty: "Nothing waiting. Finished jobs show up here for handover." · error (action): "Couldn't
  mark that job collected. It may have been handed over already."

### A18. Email templates (index) — tab `emailtemplates`
- **Route** `/admin/email-templates` · `panels/EmailTemplatesPanel.tsx`. Gate inventory, printing or
  devices.
- **Job:** find the email to customise.
- **Yuyu:** org2 list → mgr1/mgr3 detail.
- **Layout:** `ListLayout` index, then `DetailLayout` editor (B1). This replaces the 18rem left button
  column plus an always-mounted editor.
  - `title` "Email templates", `subtitle` "What people receive from {space}, in your words."
  - `tabs`: one per stream (Hardware, Printing, …) `[loaded]`.
  - `list`: grouped by audience (header "To members" / "To staff"). Rows: template name · meta "Sent when
    {humanised key}" · "Edited" pill if overridden (space default or any machine type).
  - Row click goes to `?template={stream}:{audience}:{key}` → editor.
- **States:** empty: "No editable templates here." (rare).

---

## 3. Batch B — Detail and editor (`DetailLayout`)

### B1. Email template editor
- **Route** `/admin/email-templates?template=…` · `panels/EmailTemplateEditor.tsx`,
  `EmailTemplateTypeSelector.tsx`.
- **Yuyu:** mgr1 (back + title + tabs), mgr3 (segmented control), org5 (Discard/Save).
- **Layout:** `DetailLayout`.
  - `back` "← All templates", `title` template label, `status` pill "Edited" / "Default", `meta`
    "{stream} · to {audience}".
  - `actions`: primary **"Save"**; outline "Preview" (scrolls/switches to the Preview tab on mobile).
    More: "Reset to default…" (confirm, existing copy "Reset email template?").
  - `tabs`: **Edit** · **Preview** · **Default**.
  - Scope selector (`EmailTemplateTypeSelector`) sits under the title as a segmented control "Space
    default | Laser cutter | 3D printer …" (mgr3).
  - Edit tab body: Subject, Plain text (tall), HTML (if present). `rail`: **Merge fields** list (click to
    insert at cursor; the description is a tooltip).
  - Preview tab: subject line, plain text, sandboxed HTML frame (unchanged security).
  - Default tab: read-only "Space default reference" or "Built-in default reference".
- **States:** unsaved changes: the footer shows "Unsaved changes" + Discard. Save error inline under Save.

### B2. Stocktake session (count)
- **Route** `/admin/stocktake?session={id}` · `StocktakeCountSection.tsx`.
- **Yuyu:** mgr2 (scan + find + recent with Undo), mgr1 header.
- **Layout:** `DetailLayout`.
  - `back` "← All counts", `identity` chip "#{id}", `title` notes or "Count of {container}", `status` pill,
    `meta` "Started {date} · {blind ? 'Blind count' : 'Expected shown'}".
  - `actions` by status: Counting → primary **"Complete count"**; Completed → **"Approve"**; Approved →
    **"Apply adjustments"** (confirm: "Apply {n} adjustments? Inventory numbers will change.").
  - `stats`: Lines counted `[loaded]` · Variances `[loaded]`.
  - `body`: the **ScanWorkbench** (camera or paste + product/container select + qty + "Record count") and
    below it a "Counted so far" list (product, counted, expected if not blind, variance pill).
- **States:** empty counted list: "No counts recorded yet. Scan or pick an item to start."

### B3. Container detail (drawer)
- Side drawer `DetailLayout` (drawer presentation): `title` label, `meta` code · location, `status`
  Active/Inactive, `tabs` **Contents** · **History** · **Details**.
  - Contents: Products (name · available) and Units (asset tag · status pill · inline "Show QR" ·
    `[...]` Warranty). Sub-containers as chips.
  - History: scan rows (time · context · "Reviewed handover" / "QR scan").
  - Details: settings rows Label, Location, Active toggle, Kit components (when kit feature on), Save.
- **States:** Contents empty: "This container is empty." · History empty: "No scans yet."

### B4. Device detail (drawer)
- Covered in A13.

### B5. Machine service console / printer service console (tab body)
- **Where:** inside the core machine-type page (`panels/machine/MachineTypePage.tsx`; the page frame is
  owned by `ux-yuyu-spec.md`). Components `MachineServiceConsole.tsx`, `PrinterServiceConsole.tsx`.
- **Yuyu:** org2 tabs + rows, mgr2 inline actions.
- **Slot fill:** the type page's `DetailLayout` gets a **"Queue"** tab (and "Manual usage" and, for
  printers, "Printer reports" tabs) instead of stacked `Subsection`s.
  - Queue tab: sub-tabs Pending · Accepted · Printing (in progress) · Ready (completed) · Failed, each with
    `[loaded]` counts. Rows: requester chip · job title · meta "Planned {q} {unit} · actual {q} {unit}" ·
    status pill · **one inline next action** (Pending → "Accept", Accepted → "Start", In progress →
    "Complete", Completed → "Hand over", Failed → "Reprint"). Reject and Fail live in the row `[...]` in
    red. The action form (minutes, machine, pool, reason) opens as a **dialog** titled by the verb
    ("Start job", "Complete job", "Mark failed") instead of an inline bordered box.
  - Manual usage tab: primary "Log usage" (dialog), list of entries (outcome pill · qty · minutes).
  - Info line under the tabs (muted): "This type is metered in {unit}." Pool guidance appears as helper
    text in the Start dialog.
- **States:** "No jobs waiting. New requests land here." / "No manual usage logged yet."

---

## 4. Batch C — Configuration (`SettingsLayout`)

### C1. API access — tab `api`
- **Route** `/admin/api-access` · `ApiClientsPanel.tsx`, `ApiClientCreateCard.tsx`,
  `ApiClientListCard.tsx`, `ApiClientScopePicker.tsx`, `ApiClientsAccessSummary.tsx`,
  `ApiClientsTelegramSettings.tsx`.
- **Job:** let your own tools read and write this space without sharing a login; or request access.
- **Yuyu:** **org6 directly.**
- **Layout:** `SettingsLayout` with an org6 body (cards, not label-left rows, because this is a create
  surface).
  - `title` "API access", `subtitle` "Let your own tools work with {space}, without sharing anyone's
    login."
  - Section "New API client" (card): Client label, Allowed browser origins (one per line), **"What can it
    do?"** scope **check-cards** (label + `scope:key` in small mono, as in org6), primary **"Create
    client"**. Non-managers get "Request API access" (Label, Reason, Origins, then "Send request").
  - One-time secret: yellow strip "**Copy the secret now.** It's shown once." + dark code block + Copy +
    "Done".
  - Section "Clients": rows (label · `client_id` mono · origins as meta · scope count pill). Inline "Edit
    scopes" (drawer with the scope cards and Save). `[...]` "Rotate secret…" and "Delete…" (red, confirm).
  - Section "Your requests" (non-managers): rows with a status pill.
  - Section "Developer reference": yellow strip "Keep keys in a secret manager…" + key-value card
    "Makerspace code · Allowed browser origins" (from `ApiClientsAccessSummary`).
- **Merge/split:** **move `ApiClientsTelegramSettings` (Telegram chat ID and bot token, superadmin) out
  of API access** into Makerspace settings › Notifications / Integrations (core settings sub-nav; tell
  the core-spec owner). It is not an API-client concern.
- **States:** clients empty (dashed card): "No clients yet. The secret appears once, right after you
  create one." · scopes load error inline in the scope grid.

### C2. Modules — tab `modules`
- **Route** `/admin/modules` · `ModulesPanel.tsx` (superadmin). `SpacePacksPanel` is mounted inside
  Makerspace settings today.
- **Job:** switch whole feature families on or off for a space.
- **Yuyu:** org5 (rows + helper text), org6 (accordion reference).
- **Layout:** `SettingsLayout`.
  - `title` "Modules", `subtitle` "Switch features on for {space}. Turning one off keeps its data;
    turning it back on restores everything."
  - `subnav`: the module **groups** (Lending, Machines, Events, Community, Money, Platform …) as the
    in-page sub-nav, with "{installed} of {total}" counts. This replaces the accordion.
  - `sections`: one `SettingsRow` per module. Left: module name, description, "Turns on: …", "Also
    installs: …", "Needed by: …". Right: a **switch** (Core → a locked "Always on" pill). Toggling
    applies immediately (the API is per-action today) with toast "Events installed." + **Undo** (=
    uninstall; safe because uninstall keeps data). Uninstall that is blocked by dependents shows a
    disabled switch with helper "Turn off {dependents} first."
  - `dangerZone`: none here. Deleting data is a CLI step; say so in the subtitle helper.
  - Bottom section "Deployment" (read-only, superadmin): shipped/removed app rows + the env line in a
    dark code block with Copy.
- **States:** load error: standard. Install error inline on the row.

### C3. Platform settings — tab `platform`
- **Route** `/admin/platform` · `PlatformEmailPanel.tsx`, `PlatformSocialAuthPanel.tsx`,
  `PlatformStripeConnectPanel.tsx` (stacked today).
- **Job:** set deployment-wide email, sign-in providers and Stripe Connect.
- **Yuyu:** org5.
- **Layout:** `SettingsLayout` with `subnav`: **Email** · **Sign-in providers** · **Stripe Connect**
  (the last only when `platform_hosting`). `?section=` query.
  - Email: rows SMTP host / port / username / password ("Saved — leave blank to keep"), From email,
    TLS/SSL toggles. Footer Discard / **Save**.
  - Sign-in providers: two groups "Google" and "Apple" as row groups. Footer Discard / **Save**.
  - Stripe Connect: rows Publishable key, Secret key, Webhook secret (each with a "Saved" pill when set),
    Connect client ID, Application fee (basis points, helper "100 = 1%"). Footer Discard / **Save**.
    `dangerZone`: "Clear publishable key", "Clear secret key", "Clear webhook secret". These are three red
    outline buttons with one confirm each, and they replace the three neutral buttons beside Save.
- **States:** each section loads independently with skeleton rows; a save error appears inline above
  the footer.

### C4. Backup & restore — tab `backups`
- **Route** `/admin/backup-restore` · `BackupRestorePanel.tsx` (+ `RestoreDecision`). Gate
  `manage_makerspace`; deployment part superadmin.
- **Job:** make and download backups; superadmins schedule full backups and restore.
- **Yuyu:** org5 (rows + danger zone), org2 (archive list).
- **Layout:** `SettingsLayout` with `subnav`: **This space** · **Deployment** (superadmin).
  - This space: yellow callout "**Backups contain live member data.** Store downloads somewhere
    private." · primary **"Create backup"** · archive list rows (scope · date · size · status pill ·
    inline "Download"). If the module is off: info callout "The backup module isn't installed for this
    space. Deployment backups still cover it."
  - Deployment: settings rows "Daily full backup" (switch, helper "Last success {date}"), "Keep archives
    for" (days), Save. Primary **"Create full backup"**. Archive list with inline Download. Restore moves
    into the **danger zone**: "Restore from a backup" → picks an archive and a kind (Roll back in place /
    Disaster recovery) in a confirm dialog that requires typing the space or deployment name.
  - Active restore: a red-outlined callout card at the top, "**Restore waiting for your decision —
    {seconds}s left**", with Proceed / Reset / Abort (`RestoreDecision`, restyled).
- **States:** empty archives: "No backups yet. Create one before you change anything big." · failure
  detail inline per row · the global error line ("A backup operation failed…") becomes per-control
  messages.

### C5. Organizations — tab `organizations` (global)
- **Route** `/admin/organizations` · `panels/OrganizationsPanel.tsx`, `OrganizationSetup.tsx`
  (`OrganizationCreate`, `OrganizationLinks`), `OrganizationProfileForm.tsx`,
  `OrganizationMemberships.tsx`, `OrganizationInvitations.tsx`.
- **Job:** run an organization: its public profile, people, invitations and (superadmin) linked spaces.
- **Yuyu:** **organiser workspace boards directly** — org1 (org cards), org3 (create with preview), org4
  (members + invite card), org5 (settings + danger zone).
- **Layout:** two levels.
  1. **Index** — `DashboardLayout`-style card grid (org1 "Your organisations"): one card per org
     (avatar tile, name, your role, "{n} spaces"), plus a dashed "+ New organisation" card (superadmin
     only). This replaces the `<select>` and Prev/Next pager. If there is exactly one org, skip the index
     and open it.
  2. **Organization** — `SettingsLayout` with `subnav` **Profile** · **People** · **Invitations** ·
     **Spaces** (superadmin), selected via `?org={id}&section=`.
     - Profile (org5): rows Name, Public slug (as "spaceworks…/o/{slug}" with Copy), Website,
       Description, "Listed publicly" switch. Discard / Save. Outline header action "View public page ↗".
     - People (org4): table Person (avatar, name, email) · Role pill · Joined. Empty dashed: "It's just
       you so far. Create an invitation to bring in your team."
     - Invitations (org4 invite card): "Invite someone" card (governance actions + granted actions as
       check-cards, "Expires in" days, primary **"Create invite link"**). The created link shows as a
       field with Copy and an "Unused" pill. Below, an invitations list with state pills and inline
       "Revoke".
     - Spaces: rows "{space} · {relationship}" with inline "Change" and `[...]` "Unlink…" (confirm, existing
       copy). Primary "Link a space" (dialog: Space, Relationship).
  - Create org (superadmin): **`FlowLayout` page** using org3's pattern (Name, Slug with an "Available"
    check if derivable, Description, then "Create organisation" + Cancel), with a **live public-page
    preview** in `aside`.
- **States:** no access: "You're not part of an organization yet. Ask an organization admin for an
  invite." · load error with "Try again".

### C6. Member account — `/member/account`, `/m/:slug/member/account`
- **Route** `features/members/MemberAccountPage.tsx`, `MemberAccountProfile.tsx`,
  `MemberAccountSessions.tsx`, `MemberAccountMembership.tsx`, `MemberAccountExports.tsx`.
- **Job:** manage my profile, sign-in security, membership (cancel renewal / leave) and data export.
- **Yuyu:** **auth6 + auth7 directly.**
- **Layout:** member `AppShell` + `SettingsLayout`.
  - `title` "Account", `subtitle` "Your personal profile and sign-in security." (replaces "Your account" +
    "Back to membership" button; the back link becomes the shell's nav).
  - Underline tabs (as section switcher): **Profile** · **Security** · **Membership** · **Your data**.
  - Profile: rows Display name, First / last name, Contact phone. Footer Save.
  - Security (auth7): callout "**Two-step sign-in is off.** Add an authenticator so a stolen password
    isn't enough." → **"Set up authenticator"** (links to `/mfa`). Section "Sessions and devices": rows
    (device/session · last used · "This device" pill) with inline "Sign out". `dangerZone`-style row
    "Sign out everywhere" (if the API offers it; otherwise per-row only).
  - Membership: key-value card (plan, status, renews / ends) and, in the `dangerZone`, "Cancel
    renewal…" and "Leave {space}…" (each with the existing required-reason dialog; the button is
    "Confirm cancellation" / "Leave {space}").
  - Your data: "Request a copy of your data" (primary in the section), then a jobs list with inline
    "Prepare download" → "Download ZIP" (+ "Link expires {time}").
- **Merge:** the member portal "Account" tab (`/member/account-portal`) and this page are two "account"
  surfaces today. Keep **both routes** and make them one area: `/member/account-portal` holds the
  space-specific identity (maker profile, card, directory, referrals, certifications, see H6), and this
  page holds personal account security. Cross-link them with a sub-tab row so the user never has to know
  there are two. Final naming ("Account" vs "Profile & card") is an owner decision.
- **States:** self-service disabled: info callout "Account self-service is turned off for this space.
  Ask staff to update your details." · claim session: "Sign in with a full account to manage your
  profile, sessions or data." + "Sign in" · left: success callout "You've left {space}. Your Space Works
  account is still here."

### C7. Staff/member MFA management — `/mfa`
- **Route** `features/auth/MfaAccountPage.tsx` (standalone route; reused by members via "Manage two-step
  sign-in").
- **Yuyu:** auth7 (security tab), auth2 (centred card).
- **Layout:** `CenteredCardLayout` (this route renders outside any shell, for staff and members alike).
  - Not signed in: icon tile (shield) · "Two-step sign-in" · "Sign in to manage your authenticator." ·
    two links "Staff sign-in" / "Member sign-in".
  - Signed in, off: title "Turn on two-step sign-in" · body "Confirm your password, then scan a QR code
    with your authenticator app." · Current password · primary **"Continue"** → `MfaFlow` enrol (C-F2).
  - Signed in, on: title "Two-step sign-in is on" + success pill · password field · primary **"New
    recovery codes"** · secondary red link "Turn off two-step sign-in" (hidden when required).
  - After a change: success callout "Done. You've been signed out everywhere — sign in again to
    continue."
- **Recovery codes display:** a 2-column mono grid in a bordered box + "Copy all" + "Download .txt", then
  primary "I've saved my codes".

---

## 5. Batch D — Read-only analytics (`DashboardLayout`)

### D1. Platform dashboard — tab `platform-dashboard` (global, superadmin)
- **Route** `/admin/platform-dashboard` · `PlatformDashboardPanel.tsx`.
- **Job:** "is the deployment healthy, and what needs me?"
- **Yuyu:** org1/org2 (greeting, stat cards, callouts, list + rail).
- **Layout:** `DashboardLayout`.
  - `greeting` "Checked {relative time}", `title` "Platform", `actions`: outline **"Run checks now"**
    (replaces "Refresh dashboard and checks"; there is no primary).
  - `callouts`: one per `error` problem (max 2, then "+{n} more in Problems"): "**{message}**" →
    "Inspect".
  - `stats`: one card per tenant state (Live / Hidden / Archived …) `[loaded]` · Failed emails
    `[loaded]` · Failed notifications `[loaded]`.
  - `main` sections: **Problems** (rows: status pill Error/Warning/OK + message + inline "Inspect") ·
    **Tenant usage** (rows per tenant; click opens a drawer with `UsageTable`) · **Scheduler freshness**
    (rows: job, last run, status pill).
  - `rail`: "Backups" at-a-glance card (Last result, Last success, Automatic on/off, Offsite destinations
    with state pills, link "Backup settings →") and "Delivery" card (link "Platform settings →").
- **States:** checks running: skeleton rows in Problems · all clear: success callout "All checks
  passed." · load error: standard.

### D2. Usage & limits — tab `usage`
- **Route** `/admin/usage` · `TenantUsagePanel.tsx` (`UsageTable` is shared with D1).
- **Job:** "how close is this space to its limits?"
- **Yuyu:** mgr2 progress stat card.
- **Layout:** `DashboardLayout`.
  - `title` "Usage & limits", `greeting` "Counters reset with each quota period.", `actions` outline
    "Refresh".
  - `callouts`: any resource over its limit: "**{resource} is over its limit.**" (danger tint). Self-hosted
    (unmanaged): info callout "This deployment has no managed limits. Storage isn't tracked in
    self-hosted mode."
  - `main`: a grid of **progress stat cards**, one per resource: label · "{used} of {limit}" · progress
    bar (warn ≥ 80%, danger > 100%) · "Unlimited" when no limit. The table is kept as an accessible
    alternative ("Show as table").
- **Merge option:** this could become a "Plan & usage" section of Makerspace settings. It stays a tab
  now, because the tab key and gate exist. Owner decision.
- **States:** standard skeleton cards; error with "Try again".

### D3. Organization analytics — tab `organization-analytics`
- **Route** `/admin/organization-analytics` · `panels/OrganizationAnalyticsPanel.tsx`.
- **Job:** compare an organization's spaces and see its combined total.
- **Yuyu:** org2 stats + list.
- **Layout:** `DashboardLayout`.
  - `title` "Organization analytics", `greeting` "Your organization's spaces, side by side."
  - `actions`: none. Controls row under the title: **Organization picker** (a select fed by the existing
    `useOrganizations` list. This replaces the raw numeric "Organization ID" input) and **Report**
    select.
  - `stats`: the organization-total metrics as stat cards (first 4).
  - `main`: "Breakdown by space" — one card per space with its table (stacked on mobile).
- **States:** nothing selected: "Pick an organization to see its numbers." · no spaces: "This
  organization doesn't own any spaces with reports yet." · error with "Try again".

### D4. Makerspace picker (superadmin, pre-workspace)
- **Route** any `/admin/*` when superadmin has no selection · `MakerspacePicker.tsx` (rendered by
  `StaffApp` gate).
- **Job:** choose which space to operate.
- **Yuyu:** **org1 Home** ("Your organisations" cards).
- **Layout:** `DashboardLayout`, ideally inside `AppShell` in a **no-workspace mode** (the sidebar shows
  only global items, Platform dashboard and Organizations, and the switcher card reads "Choose a space").
  See gap §11.4. Fallback if the shell cannot render without a workspace: the same body in
  `CenteredCardLayout` wide variant.
  - `greeting` "{weekday, date}", `title` "Good morning, {name}" (time-aware), `subtitle` "Choose a space
    to work in."
  - `toolbar`: search "Name, code or slug" (new, client-side; needed past ~10 spaces).
  - `main`: card grid. Card = space avatar tile · name · code as meta · "Superadmin access: off" warn pill
    when relevant · whole card clickable ("Open {name}").
- **States:** none exist: "No spaces yet. Create one from Users › Create makerspace, or from the control
  plane." (today: "Create one from the Django control plane").

---

## 6. Batch E — Flows (`FlowLayout`)

### E1. Bulk import — tab `bulk`
- **Route** `/admin/bulk-import` · `panels/BulkImport.tsx`, `BulkImportHelpers.ts`.
- **Job:** add or update many items from a spreadsheet, safely (preview first).
- **Yuyu:** org3 (focused form), mgr2 (progress).
- **Layout:** `FlowLayout` (page), steps:
  1. **Upload** — a big drop zone (org3 logo drop style): "Drop a CSV or Excel file here, or choose a
     file" + "or paste a table" (expands the textarea). Advanced JSON is behind "Use JSON instead"
     (disclosure).
  2. **Match columns** — the mapping grid (today's modal becomes the step body): each field ← column
     select ("Don't import"). Pre-filled by `suggestMapping`.
  3. **Review** — summary stat cards Create / Update / Warnings / Errors / Rows `[loaded from preview]`,
     then the row table with status pills; error rows first. The footer primary is disabled while errors
     exist ("Fix {n} errors to continue").
  4. **Import** — progress bar with "{processed} of {total} rows", then a result summary and "View
     inventory →".
  - `footer`: Back · primary **"Preview"** (step 2) / **"Import {n} rows"** (step 3). The file-job path
    ("Apply file job") is chosen automatically for large files, so the user never picks between "Apply
    rows" and "Apply file job".
- **States:** unreadable file: "We couldn't read that file. Save it as CSV or .xlsx and try again." · no
  rows: "That file has no rows." · job failed: "The import stopped. Nothing after row {n} was saved."
  (only if the API reports it; otherwise the job error text).

### E2. QR tools (print batch builder) — tab `qr`
- **Route** `/admin/qr-tools` · `panels/QrTools.tsx`, `QrImage.tsx`. Module `qr_print_batches`.
- **Job:** build a sheet of QR labels for items, units and boxes, then download them to print.
- **Yuyu:** mgr4 (date cards → batch cards), mgr3 (columns + dashed add).
- **Layout:** `ListLayout` (batches) → `DetailLayout` (a batch) as the working surface. It is not a strict
  wizard, because users add labels in any order.
  - Index: `title` "QR labels", `subtitle` "Print labels for items, units and boxes." · primary **"New
    batch"** · batch cards (title, "{n} labels", created date). Today's "Select a print batch" dropdown
    goes away.
  - Batch detail: `back` "← All batches", `title` batch title, `meta` "{n} labels".
    - `actions`: primary **"Download all (ZIP)"** (disabled at 0).
    - `body` left: **"Add labels"** card with a segmented control **Item** · **Units** · **Reprint a
      unit** (replaces three stacked forms), then fields + "Add to batch".
    - `body` right/below: label grid (QR image + label text), dashed "+ Add labels" tile when empty.
- **States:** no batches: "No label batches yet. Start one to print QR labels." · empty batch: "This batch
  is empty. Add an item, units or a box." · item with no units: "This item has no individual units yet."

### E3. Create makerspace — inside Users (core page), superadmin
- **Route** `/admin/users` (opened from the core Users page) · `usersModals/CreateMakerspaceModal.tsx`,
  `CreationWizardSteps.tsx`.
- **Yuyu:** org3 (form + live preview).
- **Layout:** `FlowLayout`, **page presentation** via `?create=makerspace` (no route change). Today it is a
  modal with "Step 1 of 5" text.
  - `stepper`: Identity · Profile & hours · Modules · First staff · Review.
  - `aside`: **live preview card** (org3) showing space avatar tile, name, `/m/{slug}`, public code, and
    "Your catalogue will appear here".
  - Identity: Name, Public code (4 chars, helper "Shown on labels and receipts"), Slug (prefix
    `…/m/`), Location.
  - Profile & hours: Timezone, Country, Currency, hours editor. Helper "Leave as is to use the pack or
    deployment defaults."
  - Modules: Space pack picker, or "Choose modules myself" (switch) → module check-cards.
  - First staff: Email (optional), Role.
  - Review: key-value summary with "Edit" links per step.
  - `footer`: Cancel (text) · Back · **Next** / **"Create makerspace"**.
- **States:** validation inline per field (not one sentence for all of step 1).

### E4. Tenant migration — tab `migration` (superadmin)
- **Route** `/admin/tenant-migration` · `TenantMigrationPanel.tsx`, `TenantMigrationDisclosure.tsx`,
  `TenantMigrationExports.tsx`, `TenantMigrationPairings.tsx`, `TenantMigrationImports.tsx`,
  `TenantMigrationIdentityDecisions.tsx`.
- **Job:** move one space from a managed deployment to a self-hosted one, irreversibly, in a safe order.
- **Yuyu:** mgr2's door-station card (strong, staged controls) + org5 danger zone.
- **Layout:** `FlowLayout` (page) with a **visible, persistent stepper**, because the order is the safety
  model. Steps (with the side each one runs on):
  1. **Review disclosure** (source) — closure summary, identity list, acknowledgement checkbox,
     "Approve disclosure" / revoke.
  2. **Pin deployments** (both) — the pairing JSON fields, "Use this deployment's identity", "Pin pairing".
  3. **Encrypt export** (source) — recipient key, "Create encrypted export", job rows with "Download
     one-use archive".
  4. **Import & resolve** (target) — archive + digest, "Start import", per-person identity decisions.
  5. **Verify & materialise** (target) — verification stat cards (imported / resolved / dropped),
     "Materialise".
  6. **Cut over** (both) — a **danger zone** card holding "Quiesce source", "Archive source", "Activate
    target", "Abort target", "Recover source". Each one confirms by typing the space name.
  - `aside`: a status card per step (Not started / Done ✓ / Blocked: "needs step 2").
  - Top callout (danger tint, replaces the red box): "**This is one-way.** Cut-over archives the source
    space; it isn't deleted, and archives sit outside the purge guarantee."
- **States:** pairings loading as skeleton; each step's error stays inside its step.

### E5. Password recovery — `/reset-password`
- **Route** `features/staff/ResetPasswordPage.tsx` → `auth/PasswordRecoveryFlow.tsx` (code flow),
  `auth/LegacyPasswordResetForm.tsx` (uid/token link), `auth/NewPasswordFields.tsx`.
- **Yuyu:** **auth2** (set new password), auth3 (confirm card).
- **Layout:** `CenteredCardLayout` per step (a 3-step flow rendered as a sequence of centred cards, not
  as `FlowLayout`):
  1. Request: icon tile (key) · "Reset your password" · "We'll email you a code." · Email · primary
     **"Send code"** · "Back to sign in".
  2. Confirm: icon tile (mail) · "Check your email" · "We sent a code to **{email}**." · Code · New
     password with **strength meter + rule checks** (auth2: "✓ At least 12 characters") · Confirm ·
     primary **"Save new password"** · secondary "Use a different email".
  3. Success: icon tile (check) · "Password updated" · "You've been signed out on other devices." ·
     primary **"Go to sign in"**.
  - Unavailable: icon tile (warn) · "Password reset isn't available" · body from the server · "Back to
    sign in".
  - Legacy link: same as step 2 without the code field.
- **Copy:** never confirm whether an email exists ("If that address has an account, a code is on its
  way.") — keep whatever the current flow guarantees.

---

## 7. Batch F — Gates and system cards (`CenteredCardLayout`)

All of these use the same card: logo top-left, icon tile, title, body, one primary, one secondary.

| # | Screen | Component · trigger | Icon · title · body | Primary / secondary |
|---|---|---|---|---|
| F1 | **Change-password gate** | `staff/ChangePasswordGate.tsx` · `must_change_password` | lock · "Set a new password" · "**{username}** is using a temporary password. Choose your own to continue." · fields Current / New (meter + rules) / Confirm | **Save new password** / "Sign out" (text) |
| F2 | **MFA challenge / enrol** | `auth/MfaFlow.tsx` · login returns a challenge | shield · Enrol: "Set up two-step sign-in" + QR (white tile) + "Can't scan? Enter this key" (mono, Copy) · Verify: "Enter your 6-digit code" + "Use a recovery code instead" link · Codes: grid + Copy all / Download | **Verify** / "Back to sign in"; codes: **I've saved my codes** · footnote "This sign-in expires in {n} minutes." |
| F3 | **Access denied (single-tenant)** | `staff/StaffAccessDenied.tsx` | lock · "You don't have access to {space}" · "This console is only for {space}'s team. Sign in with an account that's a member here." | **Sign out** / theme toggle moves to footer |
| F4 | **Recovery quarantine** (superadmin) | `staff/RecoveryQuarantinePanel.tsx` | danger tile · eyebrow "Recovery quarantine" · "Staff access is paused" · reason · residual risk in a bordered danger box · confirm checkbox | **Lift quarantine** (danger pill, disabled until ticked) |
| F5 | **Org invitation redeem** | `organizations/OrganizationInvitationRedeemPage.tsx` · `/organization-invitations/redeem/:token` | **auth4**: overlapping avatar tiles (org + you) · "You've been invited to join" · org name (if known) · scope pill · "This link works once." · Not signed in: Username or email + Password + **Sign in and continue** · Redeemed: success state "You're in" + **Open organizations** | footnote "Signed in as {user} · Switch account". **Owner decision:** today redemption fires automatically once signed in. Yuyu asks for an explicit **Accept invite** click. Recommended (frontend-only: call the mutation on click), but it is a behaviour change. |
| F6 | **404** | `AppRoutes.NotFoundPage` | compass · eyebrow "404" · "We couldn't find that page" · "The link may be old, or the page moved." | **Go to home** (`/` or tenant home) / "Staff sign-in" (only on `/admin*`-like paths) |
| F7 | **Session / route loading** | `StaffApp.StaffLoading`, `AppRoutes.RouteFallback` | logo + spinner · "Restoring your session…" / "Opening {space}…" | none. Keep these messages in a `role=status` region |
| F8 | **No makerspace assigned** | `StaffTabContent` `Panel title="No makerspace"` | empty tile · "No space assigned yet" · "Ask a space manager to add you to their team." | **Sign out** |
| F9 | **Panel crashed** | `StaffPanelErrorBoundary` | in-page (not full-screen) danger-tinted empty card inside the current layout's body · "This page couldn't load" · "Something went wrong on our side. Reloading usually fixes it." | **Reload** / "Report details" (copies the error id if one exists) |
| F10 | **Tenant home unavailable** | `AppRoutes.FamilyHome` error / no public programme | public variant inside `PublicLayout`: "We couldn't load this space" + Try again · "{Space} hasn't published anything yet. Check back soon." | — |

---

## 8. Batch G — Public pages (`PublicLayout` / `PublicDetailLayout`)

All public pages drop their hand-built headers for the shared `PublicShell` (PLAN §3.4): space brand
left; nav (Catalogue, Machines, Events, Bookings, Stats, as enabled); "Sign in" right; theme toggle and
the "space works" credit in the footer. The "Staff login" buttons in public headers go away (staff use
`/admin`; keep a footer link "Staff sign-in").

### G1. Landing directory (central mode) — `/`
- **Component** `features/LandingPage.tsx`. **Yuyu:** org1 (cards), att1 hero tone.
- **Layout:** `PublicLayout` (deployment-level `PublicShell`: Space Works logo, "About", "Sign in").
  - `hero`: eyebrow "Space Works" · **one Unbounded accent line** "Find a space. Borrow the tool." ·
    intro "Public catalogues from community workshops, labs and makerspaces." · big search field "Search
    by name, code or place" + result count.
  - `content`: space cards (cover image, colour not greyscale; avatar tile; name; location link; code;
    "Open catalogue →"; whole card clickable).
  - The left aside with "Public spaces / Live / Status access" tiles is removed (it duplicated the count
    and "Live" was not data).
- **States:** loading: skeleton cards · empty: "No public spaces yet. They appear here once a space turns
  on its catalogue." · no match: "No spaces match '{q}'." + "Clear search" · error: "Couldn't load spaces.
  Try again."

### G2. About — `/about`
- **Component** `features/AboutPage.tsx`. **Layout:** `PublicLayout`, narrow reading column.
  - `hero`: eyebrow "About" · title "Open-source makerspace management" · 2 short paragraphs (existing
    copy, tightened) · licence line.
  - `content`: two link cards "Browse spaces →" and "Staff sign-in →" (org1 card style).

### G3. Public machines — `/machines`, `/m/:slug/machines`
- **Component** `inventory/PublicMachinesPage.tsx` (+ `MachineIntakeForm`). **Yuyu:** org2 list → card
  grid, att1 tone.
- **Layout:** `PublicLayout`.
  - `hero`: eyebrow "Machines" · title "What you can use at {space}" · intro.
  - `toolbar`: kind chips (one per group, replacing collapsible sections) + "Training required" filter
    chip.
  - `content`: card grid. Card = image (or icon tile) · name · status pill (Available / In use / Down) ·
    meta "{h} h logged" · "Training required" pill · queue line "3 jobs queued · about 2 h". Primary on
    the card: **"Request a job"** when structured intake is on (opens `MachineIntakeForm` in a dialog, not
    inline in the card).
- **States:** "No machines listed yet." · not enabled: "Machines aren't public at {space}." · throttled:
  "You're going a bit fast. Wait a moment and try again." · not found: F6-style public card.

### G4. Public bookings — `/bookings`, `/m/:slug/bookings`
- **Component** `bookings/PublicBookingsPage.tsx`, `PublicBookingForm.tsx`, `SpaceDiscoveryCalendar.tsx`,
  `discovery/*`. **Yuyu:** att1 (detail + sticky action card).
- **Layout:** `PublicLayout` (list of spaces) → selecting a space opens **`PublicDetailLayout`** in place
  (`?space={token}`, no new route).
  - List: `hero` "Book a space at {space}" · `toolbar` = `DiscoveryControls` (search, kind chips,
    list/calendar toggle) · cards (image, name, location, kind pill, Capacity, "Instant" vs "Needs
    approval" pill, **"Choose a time"**).
  - Detail: `hero` image + name + kind + location · `main` description, availability calendar, rules ·
    `aside` sticky **booking card** (date/time pickers, `PublicBookingForm` fields, primary **"Request
    booking"** or **"Book now"** per approval mode, helper "Staff confirm requests within a day" /
    "Confirmed instantly if free").
  - Header nav "My bookings" → member Bookings tab (H2).
- **States:** "No bookable spaces yet." · "No spaces match these filters." · not enabled / throttled as G3.

### G5. Public events list — `/events`, `/m/:slug/events` (only if `ux-yuyu-spec.md` leaves it out)
- **Component** `inventory/PublicEventsPage.tsx`. **Yuyu:** org2 rows from the attendee side.
- **Layout:** `PublicLayout`: `hero` "What's on at {space}" · `toolbar` discovery controls (list /
  calendar) · **date-chip rows** (title, time · place, price, availability pill "6 spots left" /
  "Waitlist") → event page (core).
- **States:** "No upcoming events. Check back soon."

### G6. Print request — `/print`, `/m/:slug/print`
- **Component** `printing/PublicPrintRequestPage.tsx`, `PublicPrintRequestForm.tsx`,
  `PublicPrintRequestParts.tsx` (`StatusResult` stepper), `PublicPrintRequestPanels.tsx`.
- **Job:** send a 3D-print job with files, then track it.
- **Yuyu:** att1 (main + sticky card), att9 (confirmation).
- **Layout:** `PublicDetailLayout`.
  - `hero`: eyebrow "3D printing" · title "Send a print job to {space}".
  - `main`: the form in three titled groups. **Your print** (Title, Project brief) · **Material**
    (filament pool select grouped by material, or Material + Colour, Quantity, Estimated grams) ·
    **Files** (model files drop zone, print-time screenshots drop zone, Source link). Submit at the
    bottom: **"Send print request"**.
  - `aside` sticky: **"Track your job"** card. Before submit: "After you send it, you'll get a link to
    follow progress here." After submit / with `?token=`: the status stepper (Requested → Accepted →
    Printing → Ready to collect → Collected) with the current step highlighted, plus "Copy tracking link".
  - On success the page scrolls to the aside, and a success callout "**Request sent.** We'll update this
    page as it moves." replaces the form.
- **States:** loading service: skeleton · unavailable: "3D printing isn't open for requests right now." +
  the tracker if a token exists + "Back to catalogue" · load error: "Couldn't reach the print service. Try
  again in a moment." · upload progress: inline "Uploading 2 of 3 files…".

### G7. Public stats — `/stats`, `/m/:slug/stats`
- **Component** `stats/PublicStatsPage.tsx`, `StatsSections.tsx`, `StatsParts.tsx`. **Yuyu:** org2 stat
  cards.
- **Layout:** `PublicLayout` with a `DashboardLayout`-style body: `hero` eyebrow "Live stats" · title
  "{space} in numbers" · "Updated live from the public catalogue." · sections **Printing** (stat cards:
  busiest printer, queue; bar chart by brand; filament trend; per-printer table) · **Lending** (most
  popular, tools out, recently added as cards) · **Out right now** (current loans list, no personal data
  beyond what the API already returns).
- **States:** off/missing: "Stats aren't public for this space." · empty: "Nothing to show yet. Stats
  fill in as people borrow and print."

### G8. Public organization — `/o/:organizationSlug`
- **Component** `organizations/PublicOrganizationPage.tsx`. **Yuyu:** org3 preview card → full page;
  att1.
- **Layout:** `PublicLayout`: `hero` avatar tile · org name · description · "Visit website ↗" (outline) ·
  `content` "Upcoming events across spaces": **date-chip rows** (title, "{host space} · time · place",
  price, availability pill, inline **"Register at {host}"**). This replaces large image cards; images
  become a small thumbnail.
- **States:** "This organization doesn't have a public page." · "No upcoming events." · events error
  with Try again.

### G9. Event feedback — `/events/:token/feedback`
- **Component** `inventory/PublicEventFeedbackPage.tsx` (+ `forms/CustomFormFields`). **Yuyu:** auth3
  (centred, focused), att9.
- **Layout:** `PublicLayout`, narrow single column (form) → `CenteredCardLayout` for the end states.
  - `hero`: eyebrow = event title · title = survey title · helper: anonymous "We don't store who sent
    this." / certificate "Certificates go to people marked as attended."
  - Needs sign-in: info callout "**Sign in to get your certificate.**" → "Sign in".
  - Form card + primary **"Send feedback"**.
  - Thank you card: check tile · "Thank you" · server thank-you text · certificate download button if
    one is returned.
  - Unavailable card: "Feedback is closed for this event."

### G10. Self-checkout — `/checkout`, `/m/:slug/checkout`
- **Component** `inventory/PublicSelfCheckoutPage.tsx`, `PublicEvidenceUpload.tsx`,
  `PublicToolScanPanel.tsx`, `PublicToolResultCard.tsx`, `KitChecklist`.
- **Job:** on a phone at the shelf: borrow or return a QR-tagged tool with photo proof.
- **Yuyu:** att11 (scan + big result), auth3 (one thing per screen).
- **Layout:** `PublicLayout` (minimal `PublicShell`), with a **`FlowLayout` body** that is mobile-first.
  - Top: segmented control **Borrow** · **Return** (replaces "Use (check out)" / "Return" tabs).
  - Borrow steps: 1 **Photo** ("Take a photo of the tool" camera/upload tile, preview) → 2 **Scan**
    (camera frame, "Hold the tool's QR inside the frame") → 3 **Check the kit** (only if it has parts) → 4
    **Confirm** (result card: tool name, due date, "Borrow it").
  - Return steps: 1 Photo → 2 **Condition notes** (required) → 3 Scan → 4 Confirm ("Return it").
  - Done: big success panel (att11 green) "**You've got it.** Due back {date}." / "**Returned.** Thanks!"
    + "Borrow another".
  - **Hard rules unchanged:** a scan and uploaded evidence stay required. The step order only makes the
    requirement visible.
- **States:** not enabled: "Self-checkout isn't on at {space}." + "Back to catalogue" · scan/loan error:
  inline danger callout on the Confirm step with the server message.

### G11. Archived payments — `/member/archived`
- **Component** `members/ArchivedPayments.tsx`. **Yuyu:** auth6 calm list.
- **Layout:** `PublicLayout` (deployment-level shell) narrow column: `hero` eyebrow "Closed spaces" ·
  "Payments and receipts" · per-space sections (space name header, charge rows with amount + status pill
  + receipt download).
- **States:** "No archived payments. Nothing is owed to spaces that have closed." · not signed in / not
  found → F6.

---

## 9. Batch H — Member area tab bodies (member `AppShell`)

The member shell, its nav and the **Overview** tab are in `ux-yuyu-spec.md`. These are the bodies of the
other `memberTabs()` (gating unchanged). Each tab body uses `ListLayout` slots without the shell header
repeating the space name.

### H1. Loans — `/member/loans`
- **Component** `MemberActivity.tsx` (section `loans`), `MemberDashboardSections.tsx`
  (`MemberHistory`), `MemberLoanRenew.tsx`. **Yuyu:** org2 tabs + rows.
- `title` "Loans" · `tabs` **Out now** · **History** · rows: item, "Due Fri" / "Overdue" pill, inline
  **"Renew"** when allowed, history rows with returned date.
- Empty: "Nothing out right now. Browse the catalogue to borrow something." + "Browse catalogue".

### H2. Bookings — `/member/bookings`
- **Component** `bookings/MyBookings.tsx`, `BookingReschedule.tsx`. **Yuyu:** org2 date-chip rows.
- `title` "Bookings" · `actions` primary **"Book a space"** (→ public bookings) · `tabs` Upcoming · Past
  (replaces the two `aria-pressed` buttons) · **date-chip rows** (space, time range, status pill) · inline
  "Move" · `[...]` "Cancel booking…" (inline confirm stays, restyled).
- Empty: "No upcoming bookings. Book a bench or room when you need one."

### H3. Events — `/member/events` (+ partner events)
- **Component** `MemberActivity` (events), `MemberCalendarActions`, `MemberEventCancel`,
  `MemberEventFeedback`, `PartnerEvents.tsx`. **Yuyu:** att9 ticket, org2 rows.
- `title` "Events" · `tabs` **Going** · **Past** · **Partner events** (only when `PartnerEvents` has rows).
- Going rows: date chip · title · time · place · inline "Ticket" (opens an att9 ticket card dialog with
  QR, "Add to calendar", "Can't make it? Cancel").
- Past rows: inline "Give feedback" / "Certificate".
- Partner events: info line "Your space partners with these hosts, so you can register even when the
  event isn't public." · rows grouped by series · inline **"Register"** (expands the registration fields
  in a dialog rather than inline).
- Empty Going: "You're not registered for anything yet. See what's on." + "See events".

### H4. Payments — `/member/payments`
- **Component** `MemberPayments.tsx`, `MemberDashboardSections` (`MemberDues`), `payments/PaymentDocuments`
  (member audience). **Yuyu:** org2 stats + rows.
- `title` "Payments" · `stats`: Outstanding (per currency) `[loaded]` · Membership fee `[loaded]` ·
  rows: what, due, amount, status pill, inline **"Pay now"** (online rail) or muted "Pay at the desk" ·
  secondary outline header action "Receipts" (drawer with documents).
- Empty: "Nothing to pay. You're all settled."

### H5. Inbox — `/member/inbox`
- **Component** `notifications/MemberNotifications.tsx`, `AnnouncementFeed.tsx`, `PreferenceCentre.tsx`,
  member notices. **Yuyu:** activity rail.
- `title` "Inbox" · `tabs` **Notices** · **Announcements** · **Preferences** (Preferences uses
  `SettingsLayout` rows: channel switches, digest frequency, Save).
- Empty: "No notices need your attention." / "No announcements yet."

### H6. Account portal — `/member/account-portal`
- **Component** `MemberProfilePanel.tsx` (+ `memberProfile/*`), `MemberCardPanel.tsx` (+ `memberCard/*`),
  `MemberDirectory.tsx`, `MemberReferrals.tsx`, `MemberCertifications.tsx`, `MemberClaimCodes`. Today
  these stack in one tall column.
- **Layout:** `SettingsLayout` with sub-tabs **Profile** · **Card** · **Certifications** · **Community**
  · **Invite a friend**, plus a link chip "Account & security →" (C6). Tab contents depend on modules, as
  today.
  - Profile (auth6): rows Avatar (upload), Headline, Institution, Bio, Interests, Languages, GitHub;
    "Projects" list with dashed "+ Add project". Save.
  - Card (att9 ticket style): a card visual (space colour band, printed name, number, QR when active)
    · "Name printed on the card" row · photo upload with consent · actions "Save name", "Preview PDF",
    "Save for offline use" / "Forget offline card", "Keep my loans on this device". Revoked: danger
    callout "This card was revoked. Ask staff for a new one."
  - Certifications: rows (machine, level, granted date, expiry pill). Empty: "No training records yet.
    Ask staff about a machine induction."
  - Community (member directory): `ListLayout` body: search + member cards (avatar, name, headline,
    interests chips) → profile drawer (projects, links, recently attended). Empty: "No members have
    shared a profile yet."
  - Invite a friend (`MemberReferrals`): org4 "Invite someone" card (email + **"Send invite"**) +
    "Pending invitations" list + claim-code field. Empty: "No pending invitations."
- **Split note:** Community is a directory, not account content. It belongs in its own member nav item.
  That requires adding a value to `MEMBER_TABS`/`memberTabs` (a gating change, which PLAN §5 says to
  avoid), so it stays a sub-tab here and the decision goes to the owner.

---

## 10. Batch I — Stations (`KioskLayout`)

### I1. Event check-in station — `/event-check-in/:stationToken`, `/m/:slug/event-check-in/:stationToken`
- **Component** `events/EventCheckInStationPage.tsx` + `staff/OfflineCheckInOperator.tsx`
  (`eventCheckInOfflineStore`).
- **Yuyu:** **att10 (PIN pad) + att11 (door scanner) directly.**
- **Layout:** `KioskLayout`, two states:
  1. **Locked:** `stage` left = space avatar tile, "{event} · Door check-in", big title "Enter the station
     PIN", body "Ask an organiser for the 8-digit PIN. It unlocks check-in on this device only.", **8 PIN
     boxes**. `side` right = numeric keypad (1–9, Clear, 0, ⌫) + full-width **"Open check-in"** (disabled
     until 8 digits). A physical keyboard still works. Keep the `Station PIN` label as the input's
     accessible name. Error: "That PIN didn't work, or check-in isn't open right now."
  2. **Unlocked:** `station bar` = avatar, event name, "Door check-in · Station", counter "{n} / {total}
     checked in", **Online / Offline pill** (queued count when offline: "Offline · 3 waiting to sync"),
     outline **"Lock station"** (= today's "Wipe data and lock station"; confirm "Lock and wipe this
     device? Unsynced check-ins will be lost." only when the queue is non-empty). `stage` = camera frame
     "Hold the ticket QR inside the frame" + search "Name, email or ticket code" + **Find**. `side` =
     result panel (green "Checked in · {name} · just now" with **"Next guest"** + **"Undo"** if the
     operator supports undo; amber "Already checked in at {time}"; red "Not on the list"), then "Recent"
     list.
- **States:** roster downloading: "Getting the guest list ready…" with progress · roster unavailable
  (400/403/410 wipes): danger panel "This station was turned off. Ask an organiser for a new link."

### I2. Public desk kiosk — `/kiosk/:slug` (central)
- **Component** `kiosk/PublicDeskKioskPage.tsx` (wraps `PublicInventoryPage`).
- **Layout:** `KioskLayout` whose `stage` hosts the **public catalogue body** (core spec's catalogue,
  unchanged). `station bar` = space avatar · "Public desk" · outline "Open full catalogue". There are no
  sign-in or theme controls in the bar (the theme toggle moves to a small footer control). Larger touch
  targets (`min-h-12`), larger base type.
- **Note:** this is the only kiosk that embeds a core screen. Coordinate with the catalogue owner so the
  catalogue body renders without its own `PublicShell` header when hosted here.

### I3. Scanner page — `/scanner`
- **Component** `kiosk/ScannerPage.tsx`.
- **Job:** a staff device that only resolves QR codes.
- **Yuyu:** att11.
- **Layout:** `KioskLayout`: `station bar` "Scanner" + signed-in staff chip · `stage` = **ScanWorkbench**
  (§11.2: camera + paste field + Resolve) · `side` = **resolved-object card** (the same card as the staff
  Scanner tab: "Box B-04 · 12 items", "Asset · Multimeter #3 · Out", allowed actions as labelled
  buttons/pills) · Recent list.
- **Fix:** today the result is a raw `JSON.stringify` `<pre>`. Replace it with the shared result card.
  Add camera scanning (the staff `QrScanner` already exists).
- **States:** idle: "Scan a label or paste its code." · unknown QR: "That code isn't one of ours." ·
  revoked: "This label was revoked." (from the server message).

### I4. Member PWA offline page — `public/member-pwa/offline.html` (+ `offline.css`, `offline.js`)
- **Layout:** static HTML that mirrors `KioskLayout`'s look in plain CSS. It cannot use React
  primitives, so PLAN Phase 1 must update `offline.css` with the new tokens by hand.
  - Top bar: space name (from the saved card) · "Offline" pill.
  - Card visual (as H6 Card) with the saved QR, name, number, and "Saved {date} · last-known".
  - "My loans" list (saved) with due dates.
  - Footer: primary **"Try again online"**, red text button "Forget saved card and loans".
- **Copy:** "You're offline. This is your last-saved card. It may not show recent changes." · no card: "No
  card saved on this device. Next time you're online, save it from your account."

### Staff Scanner tab — tab `scanner` (listed here because it shares I3's parts)
- **Route** `/admin/scanner` · `panels/ScannerPanel.tsx`, `ScannerPanelForms.tsx`. Gate `manage_qr`;
  module `scanner`.
- **Layout:** `AppShell` + `ListLayout` frame (title "Scanner", subtitle "Scan or paste a label to see
  what it is and act on it.") whose `list` slot holds the **ScanWorkbench** + resolved-object card.
  Actions on the card: primary depends on target (Box → "View contents"); `[...]` "Rename & rebind…",
  "Move to another space…" (each opens a dialog instead of an inline form), red "Revoke label…" (confirm).
  The checkout/return hint becomes an info callout with a link: "To lend this, use Direct handout →".

---

## 11. Layout gaps and shared sections

No screen in this doc needs a new page layout. These are the places where the closed set needs a
**variant** or a **shared section**:

1. **`FlowLayout` needs a `dialog` presentation** besides `page`. It is used by New transfer (A3), Start
   count (A4), Add item (A5), Add device + enrollment (A13), Send announcement (A7). Proposal: the same
   stepper/footer contract rendered inside `Modal`. Single-step dialogs simply hide the stepper.
2. **`ScanWorkbench` shared section (not a layout).** Camera frame + paste/search field + Resolve/Find +
   result panel + recent list. It is used inside `ListLayout` (staff Scanner, Member cards › Scan),
   `DetailLayout` (Stocktake session), `FlowLayout` (Self-checkout scan step) and `KioskLayout` (Scanner
   page, Event check-in station). It wraps the existing `QrScanner`. Proposed home:
   `components/ui/ScanWorkbench.tsx`, ≤200 lines, with `ResultPanel` (success / warn / danger + "Next" +
   optional "Undo") split out.
3. **`DetailLayout` drawer presentation.** Container detail (B3), Device detail (A13), Warranty manage
   (A10), Procurement edit (A5) and Organized event (A11, already `EventDrawer`) open as side drawers. This
   assumes the restyled `DetailDrawer` can host `DetailLayout` slots (back → close, tabs, body). If the
   core spec defines drawers differently, follow it.
4. **`AppShell` no-workspace mode** for the superadmin makerspace picker (D4) and global routes
   (Organizations, Platform dashboard) before a space is chosen. The sidebar shows only global items and
   the switcher reads "Choose a space". This needs `StaffApp`'s gate order to render the picker inside the
   shell. That touches `shell-contracts.md` §1A (gate order), so raise it with the shell owner. Fallback:
   `CenteredCardLayout` wide variant.
5. **`CenteredCardLayout` wide variant** (max-width ~ 720 px) for card grids that sit outside any shell
   (D4 fallback, G11 archived payments if the deployment shell is not used).
6. **Static offline page** (I4) cannot consume layouts. It mirrors `KioskLayout` by hand in
   `offline.css`. This is a constraint for the token phase, not a layout gap.

---

## 12. Batch J — Overlays and global chrome (no page layout)

### J1. Command palette
- **Component** `staff/CommandPalette.tsx`. Keep: name "Search and commands", Ctrl/⌘K, combobox/listbox
  semantics, dialog-stack guard.
- **Change:** the trigger moves to the sidebar top as a search-looking field "Search or jump to…" with a
  `⌘K` hint (PLAN §3.4). Results are **grouped** with small headers: **Go to** (tabs), **Create**
  (quick-create commands), **Results** (entity hits, with entity-type icon and tab name as meta). Each
  item has a leading icon; the selected item uses the active-pill style. Footer hint: "↑↓ to move · Enter to
  open · Esc to close".
- **States:** searching: "Searching…" (live) · none: "No matches for '{q}'." · search error: "Search
  isn't available right now. You can still jump to pages."

### J2. Job tray
- **Component** `components/ui/JobTray.tsx` (`jobStore`). Today it is a `<details>` strip under the
  header.
- **Change:** a compact pill pinned at the **bottom of the sidebar** (above the user chip): "2 jobs
  running" with a spinner. Clicking opens a popover list. Each job has a label, a status pill (Queued /
  Building / Ready / Failed), "Open" (to its source panel), and "Dismiss". When a job finishes: toast "Your
  export is ready." with "Download"/"Open". Keep the `aria-live` summary.
- **States:** check error: row text "Couldn't check progress." + "Retry".

### J3. Setup checklist
- **Component** `staff/SetupChecklist.tsx` (`setupChecklistState.ts`). Shown on Dashboard to space
  managers.
- **Change (coordinate with the core Dashboard spec):** a **Yuyu callout card** at the top of Home:
  "**Finish setting up {space}** — 3 of 5 done" + progress bar + the next undone step as the action link
  ("Set opening hours →"). It expands to the full list (Done ✓ / To do rows linking to their tabs) and a
  "Hide" control that persists per browser (unchanged).

### J4. Shared dialogs restyled once
- Payment Settlement / Refund / Amend (A1), Category delete, Restrict requester (A9), Reissue/Revoke card
  (A12), Device revoke + enrollment (A13), Bulk-import mapping (now a step, E1), Create QR batch (E2),
  Org link change (C5), Reset email template (B1). All follow: title as a question or verb ("Revoke this
  card?"), one sentence of consequence, then Cancel (outline) + verb button (danger tint when
  destructive). Required-reason fields autofocus.

---

## 13. Cross-cutting merges and moves (summary)

| Move | From → to | Why | Needs |
|---|---|---|---|
| Telegram chat ID / bot token | API access → Makerspace settings › Notifications/Integrations | not an API-client concern | core settings owner |
| Broadcast composer | pinned above inbox → "Send announcement" dialog on Notifications | one primary; inbox is the job | — |
| Stocktake policy & schedules | top of Stocktake → More › "Count policy and schedule" drawer | config ≠ daily work | — |
| Suppressions | below delivery log → tab "Suppressed addresses" | one list per view | — |
| Space packs | Makerspace settings → stays (core); referenced from Create makerspace step 3 | — | core settings owner |
| Usage & limits | own tab → optionally Settings › Plan & usage | fewer admin tabs | owner decision |
| Member directory | Account tab → own member nav item | it's community, not account | `memberTabs` change, owner decision |
| Member account (2 pages) | `/member/account` + account-portal tab → one cross-linked area | user sees one "account" | — |
| Platform settings (3 stacked panels) | → sub-nav sections | — | — |
| Accountability (4 stacked panels) | → tabs | — | — |
| Member cards (4 stacked sections) | → tabs | — | — |
| QR tools (3 stacked forms) | → batch list + batch detail with segmented "Add labels" | — | — |
| Organizations select + pager | → org cards index + org settings sub-nav | Yuyu organiser workspace | — |
| Dead code | `panels/EmailLogPanel.tsx` (exported, not routed) | — | separate cleanup |

---

## 14. Coverage table

### 14.1 Staff tab keys (all 42 in `ALL_TABS`)

`ALL_TABS` has 42 keys; PLAN §2's "41 tabs" undercounts by one. Labels are from `TAB_LABELS`.

| Tab key | Label | Component | Spec | Section | Layout |
|---|---|---|---|---|---|
| `platform-dashboard` | Platform dashboard | `PlatformDashboardPanel` | longtail | D1 | DashboardLayout |
| `usage` | Usage & limits | `TenantUsagePanel` | longtail | D2 | DashboardLayout |
| `dashboard` | Dashboard | `panels/DashboardPanel` | ux-yuyu-spec | Staff Home | DashboardLayout |
| `notifications` | Notifications | `panels/NotificationInbox` | longtail | A7 | ListLayout |
| `requests` | Requests | `panels/RequestsPanel` | ux-yuyu-spec | Requests | ListLayout / DetailLayout |
| `direct` | Direct handout | `DirectLoans` | ux-yuyu-spec | Direct handout | (core) |
| `handover` | Job handover | `panels/machine/HandoverConsole` | longtail | A17 | ListLayout |
| `inventory` | Inventory | `panels/Inventory` | ux-yuyu-spec | Inventory | ListLayout / DetailLayout |
| `needsfix` | To-be-fixed | `panels/NeedsFixShelf` | longtail | A6 | ListLayout |
| `categories` | Categories | `panels/Categories` | longtail | A15 | ListLayout |
| `machines` | Machines | `panels/MachinesPanel` | ux-yuyu-spec (+ longtail B5 for service-console tab bodies) | Machines | (core) DetailLayout |
| `events` | Events | `EventsPanel` | ux-yuyu-spec (+ longtail §13 note: collaboration inbox → callout) | Events | (core) |
| `organized` | Organized events | `panels/OrganizedEventsPanel` | longtail | A11 | ListLayout |
| `bookings` | Bookings | `BookingsPanel` | ux-yuyu-spec | Bookings | (core) |
| `members` | Members | `MembersPanel` | ux-yuyu-spec | Members | (core) |
| `cards` | Member cards | `panels/MemberCardsPanel` | longtail | A12 | ListLayout |
| `tobuy` | To Buy | `panels/ProcurementPanel` | longtail | A5 | ListLayout |
| `transfers` | Transfers | `panels/StockTransferPanel` | longtail | A3 | ListLayout + FlowLayout(dialog) |
| `stocktake` | Stocktake | `panels/StocktakeSessionPanel` | longtail | A4, B2 | ListLayout / DetailLayout |
| `containers` | Containers | `panels/ContainersPanel` | longtail | A16, B3 | ListLayout / DetailLayout(drawer) |
| `ledger` | Ledger | `panels/Ledger` | longtail | A2 | ListLayout |
| `reports` | Reports | `panels/OperationsReports` | ux-yuyu-spec | Reports | (core) |
| `accountability` | Accountability | `panels/AccountabilityPanel` | longtail | A9 | ListLayout |
| `warranty` | Warranties | `panels/WarrantyPanel` | longtail | A10 | ListLayout |
| `bulk` | Bulk import | `panels/BulkImport` | longtail | E1 | FlowLayout |
| `qr` | QR Tools | `panels/QrTools` | longtail | E2 | ListLayout / DetailLayout |
| `scanner` | Scanner | `panels/ScannerPanel` | longtail | §10 "Staff Scanner tab" | ListLayout + ScanWorkbench |
| `api` | API access | `ApiClientsPanel` | longtail | C1 | SettingsLayout |
| `settings` | Settings | `MakerspaceSettingsPanel` | ux-yuyu-spec | Makerspace settings | (core) SettingsLayout |
| `emailtemplates` | Email templates | `panels/EmailTemplatesPanel` | longtail | A18, B1 | ListLayout / DetailLayout |
| `users` | Users | `panels/Users` | ux-yuyu-spec (+ longtail E3 for Create makerspace) | Staff & roles | (core) |
| `platform` | Platform settings | `PlatformEmail/SocialAuth/StripeConnect` | longtail | C3 | SettingsLayout |
| `audit` | Audit log | `panels/AuditLog` | ux-yuyu-spec | Audit log | (core) |
| `devices` | Devices | `panels/DevicesPanel` | longtail | A13 | ListLayout |
| `email-logs` | Delivery logs | `panels/DeliveryLogPanel` | longtail | A8 | ListLayout |
| `payments` | Payments | `PaymentsPanel` | longtail | A1 | ListLayout |
| `organizations` | Organizations | `panels/OrganizationsPanel` | longtail | C5 | DashboardLayout(index) / SettingsLayout |
| `organization-analytics` | Organization analytics | `panels/OrganizationAnalyticsPanel` | longtail | D3 | DashboardLayout |
| `modules` | Modules | `ModulesPanel` | longtail | C2 | SettingsLayout |
| `exports` | Data export | `DataExportsPanel` | longtail | A14 | ListLayout |
| `backups` | Backup & restore | `BackupRestorePanel` | longtail | C4 | SettingsLayout |
| `migration` | Tenant migration | `TenantMigrationPanel` | longtail | E4 | FlowLayout |

Totals: 12 tabs in `ux-yuyu-spec.md`, 30 in this doc, 42 in all.

### 14.2 Routes (`AppRoutes.tsx`, both modes)

| Route (single · central) | Component | Spec | Section | Layout |
|---|---|---|---|---|
| `/` · `/m/:slug` → `FamilyHome` → inventory/events/bookings/machines/membership | per `publicHome()` | ux-yuyu-spec (catalogue, event, member home), longtail (machines G3, bookings G4) | — | PublicLayout |
| `FamilyHome` error / "No public programme" | `AppRoutes.FamilyHome` | longtail | F10 | PublicLayout |
| `/` (central) | `LandingPage` | longtail | G1 | PublicLayout |
| `/about` | `AboutPage` | longtail | G2 | PublicLayout |
| `/o/:organizationSlug` | `PublicOrganizationPage` | longtail | G8 | PublicLayout |
| `/items/:itemId` · `/m/:slug/items/:itemId` | `PublicItemPage` | ux-yuyu-spec | Public item | PublicDetailLayout |
| `/checkout` · `/m/:slug/checkout` | `PublicSelfCheckoutPage` | longtail | G10 | PublicLayout + FlowLayout body |
| `/events` · `/m/:slug/events` | `PublicEventsPage` | ux-yuyu-spec if covered, else longtail | G5 | PublicLayout |
| `/events/:publicToken` · `/m/:slug/events/:publicToken` | `PublicEventDetailPage` | ux-yuyu-spec | Public event page | PublicDetailLayout |
| `/events/:publicToken/feedback` · `/m/:slug/…/feedback` | `PublicEventFeedbackPage` | longtail | G9 | PublicLayout / CenteredCardLayout |
| `/event-check-in/:stationToken` · `/m/:slug/event-check-in/:stationToken` | `EventCheckInStationPage` | longtail | I1 | KioskLayout |
| `/machines` · `/m/:slug/machines` | `PublicMachinesPage` | longtail | G3 | PublicLayout |
| `/bookings` · `/m/:slug/bookings` | `PublicBookingsPage` | longtail | G4 | PublicLayout / PublicDetailLayout |
| `/print` · `/m/:slug/print` | `PublicPrintRequestPage` | longtail | G6 | PublicDetailLayout |
| `/member` · `/m/:slug/member` (overview, sign-in) | `MemberArea` | ux-yuyu-spec | Member home / Member sign-in | AppShell / AuthLayout |
| `/member/:memberTab` · `/m/:slug/member/:memberTab` — `loans` | `MemberArea` | longtail | H1 | AppShell + ListLayout |
| — `bookings` | `MemberArea` → `MyBookings` | longtail | H2 | AppShell + ListLayout |
| — `events` | `MemberArea` → activity + `PartnerEvents` | longtail | H3 | AppShell + ListLayout |
| — `payments` | `MemberArea` → `MemberPayments` | longtail | H4 | AppShell + ListLayout |
| — `inbox` | `MemberArea` → notifications | longtail | H5 | AppShell + ListLayout / SettingsLayout |
| — `account-portal` | `MemberArea` → profile, card, directory, referrals | longtail | H6 | AppShell + SettingsLayout |
| — `overview` | `MemberArea` | ux-yuyu-spec | Member home | AppShell + DashboardLayout |
| `/member/account` · `/m/:slug/member/account` | `MemberAccountPage` | longtail | C6 | AppShell + SettingsLayout |
| `/member/archived` | `ArchivedPayments` | longtail | G11 | PublicLayout |
| `/stats` · `/m/:slug/stats` | `PublicStatsPage` | longtail | G7 | PublicLayout |
| `/reset-password` | `ResetPasswordPage` | longtail | E5 | CenteredCardLayout |
| `/mfa` | `MfaAccountPage` | longtail | C7 | CenteredCardLayout |
| `/staff-invitations/accept` | `StaffInvitationAcceptPage` | ux-yuyu-spec | Invitation accept | CenteredCardLayout |
| `/organization-invitations/redeem/:token` | `OrganizationInvitationRedeemPage` | longtail | F5 | CenteredCardLayout |
| `/admin/*` · `/m/:slug/admin/*` (sign-in) | `StaffApp` → `LoginPanel` | ux-yuyu-spec | Staff sign-in | AuthLayout |
| `/admin/*` gates: MFA, change password, quarantine, access denied, picker, loading | `StaffApp` | longtail | F1–F4, F7, D4 | CenteredCardLayout / DashboardLayout |
| `/admin/{tab}` | `StaffWorkspace` → tab | per 14.1 | — | AppShell + per 14.1 |
| `/guest-admin/*` | `StaffApp guestOnly` | same as `/admin/*` (narrow tab set, same layouts) | — | — |
| `/scanner` | `ScannerPage` | longtail | I3 | KioskLayout |
| `/kiosk/:stationToken` · `/m/:slug/kiosk/:stationToken` | `KioskStationPage` | ux-yuyu-spec | Kiosk station | KioskLayout |
| `/kiosk/:slug` (central) | `PublicDeskKioskPage` | longtail | I2 | KioskLayout |
| `/superadmin` (central) | `SuperadminPage` → `StaffApp` | same as `/admin/*` (D4 picker) | D4 | — |
| `*` | `NotFoundPage` | longtail | F6 | CenteredCardLayout |
| (static) `/member-pwa/offline.html` | PWA offline | longtail | I4 | KioskLayout (static mirror) |

### 14.3 Non-route surfaces

| Surface | Component | Spec | Section |
|---|---|---|---|
| Command palette | `CommandPalette` | longtail | J1 |
| Job tray | `components/ui/JobTray` | longtail | J2 |
| Setup checklist | `SetupChecklist` | longtail (coordinate with core Dashboard) | J3 |
| Create makerspace wizard | `usersModals/CreateMakerspaceModal` | longtail | E3 |
| MFA challenge (inside staff sign-in) | `auth/MfaFlow` | longtail | F2 |
| Panel error boundary | `StaffPanelErrorBoundary` | longtail | F9 |
| Payment dialogs | `SettlementDialog`, `PaymentRefundDialog`, `RefundReceiptAmendDialog` | longtail | A1, J4 |
| Payment reconcile actions (embedded in bookings/events/admissions) | `PaymentReconcileActions` | host screen's spec (core); restyle per A1 dialogs | A1 |
| Event collaboration inboxes (inside Events) | `CollaborationInbox`, `EventSeriesCollaborationInbox` | ux-yuyu-spec Events page; recommended as a yellow callout "{n} spaces invited you to co-host" → review list | §13 |
| Integration health (inside Settings) | `IntegrationHealthPanel` | ux-yuyu-spec (Settings) | — |
| Machine service / printer consoles (inside machine type) | `MachineServiceConsole`, `PrinterServiceConsole` | longtail | B5 |

---

## 15. Appendix: wireframes and mobile notes per screen

The wireframes are desktop (≥1024 px, inside `AppShell` unless the layout says otherwise). The sidebar is
omitted. `[Primary]` is the pill button, `(Outline)` an outline pill, `[More v]` the overflow,
`[...]` a row overflow. **Mobile defaults** (<768 px) apply to every screen unless an exception is listed:
stat cards go 2-up; tabs scroll horizontally with the active one kept in view; toolbar filters fold
into a "Filters" sheet button beside search; card rows stack (title, meta, then status and inline action on
their own line, inline action full-width); the header primary becomes a full-width button under the title;
`rail` drops below `main`; drawers become full-screen sheets; dialogs become bottom sheets.

### Batch A

**A1 Payments, A2 Ledger:** see §2.

**A3 Transfers**
```
Transfers                                                    [New transfer]
Stock moved between boxes and spaces.
┌ (→) 4 × Jumper kit             Box A-02 → Box C-11 · restock      3 Oct  (SK) ┐
┌ (→) 1 × Oscilloscope           Fab Lab → Uni Lab · loan pool      1 Oct  (RM) ┐
                    dialog: New transfer — Step 1 of 2 · From and to
                    [Source v] [Destination v]      (Back) [Next]
```
Mobile: the dialog is a full-height sheet; line editor rows stack product over qty.

**A4 Stocktake**
```
Stocktake                                         [Start count]  [More v]
Count what's on the shelves and fix the numbers.
┌ ! Monthly cycle count is due today.                         Start it → ┐
┌In progress┐┌Needs approval┐┌Applied this month┐
 Active 1 | Needs approval 2 | Ready to apply | Done
┌ (#14) Count of Box B (all)   Counting · 23 lines · started 2 Oct   Continue ┐
```

**A5 To buy**
```
To buy                                            [Add item]  [More v]
┌ ! 3 items are running low.                          Review suggestions → ┐
┌Estimated total┐┌Open budget┐┌Spent┐
 Requested 4 | Approved 2 | Ordered 3 | Received 1 | Cancelled | All
 ── Laser cutter ───────────────────────────────────────────────
┌ Honeycomb bed ×1   Vendor X · est ₹4,200 · Asha     [Requested]  Approve [...] ┐
```
Mobile: removes today's 1180 px horizontal-scroll table entirely.

**A6 To be fixed**
```
To be fixed
Units returned broken. Repair them back into stock, or scrap them.
┌Units to fix┐┌Products┐
┌ Multimeter   (3 to fix)  5 available · 9 total   [– 3 +]  Repaired [...] ┐
```

**A7 Notifications**
```
Notifications · 4 unread               (Send announcement)  [Mark all read]
 Unread 4 | All
 (Hardware)(Printing)(Events)(Bookings)(Members)(Payments)…
 Today
┃(▣) Request accepted · Arduino kit — Asha's request was…      2 min ago   Open
 (◷) Booking cancelled · Bench 2 — …                           1 h ago
```

**A8 Delivery logs**
```
Delivery logs                                                   [Send test]
┌ ! 2 deliveries failed.                                      Show failed → ┐
 Deliveries | Suppressed addresses
 (All)(Sent)(Failed)(Pending)(Skipped)  [Channel v] [Destination v] [More filters]
┌ (✉) Requests · accepted   asha@… · 3 attempts · 10:02     [Failed]  Retry ┐
     SMTP 550 mailbox unavailable
```

**A9 Accountability**
```
Accountability
┌Overdue 4┐┌Open problems 1┐┌Repeat offenders 2┐┌Restricted 1┐
 Overdue | Problems | Repeat offenders | Restricted
┌ (RM) Soldering station · Ravi M.                 [Overdue 6 d]  Open loan ┐
```

**A10 Warranties**
```
Warranties                         Coverage for machines and assets in Fab Lab.
 All | Active | Expiring soon | Expired | Not covered     [Expires before ▢] (Missing docs)
┌ (LC) Laser cutter · Trotec   bought 2024 → expires Mar 2027   [Active] 2 docs  Manage ┐
```

**A11 Organized events**
```
Organized events
 Upcoming | Past
┌[OCT|14] Robotics meetup     Fab Lab · Bengaluru            12 / 40 going ▬▬──  [Published] ┐
```

**A12 Member cards**
```
Member cards                                  (Scan a card)  [Print all active]
┌Active cards 120┐┌Without a card 8┐
 Cards | Issue | Scan | Card layout
 (Active)(Revoked)
┌[ ] MC-0012  Asha K.   [Active]  printed 2×  photo ✓        Print [...] ┐
```

**A13 Devices**
```
Devices                                                       [Add device]
┌Online 2┐┌Offline 1┐┌Revoked 0┐
┌ (printer) Bambu X1 · Printer     Last seen 4 min ago            [Online]  ┐
┌ (label) Label printer · Label    Offline since 09:12            [Offline] ┐
```

**A14 Data export**
```
Data export                                                 [Request export]
A readable copy of your space's records. Not a backup.
┌ ! Exports include member names, emails and phone numbers.   Read what's included ┐
┌ (⇩) Export · 3 Oct 10:02     4,812 rows                 [Ready]   Download ┐
```

**A15 Categories**
```
Categories                                                  [Add category]
┌ Name          Products   Order   Icon                          ┐
│ Electronics      42        1      cpu            Edit  [...]   │
```

**A16 Containers**
```
Containers                                           [Create in QR tools]
 [Search……]  (Active)(Inactive)
┌[B-04] Electronics bin · Shelf 2                         12 items ┐
```

**A17 Job handover**
```
Ready to collect
Finished jobs waiting for their owners.
┌Waiting 5┐┌Unpaid 2┐
 [Search requester……]
┌ (AK) Bracket v2 · Bambu X1 · finished 20 min ago   [Unpaid ₹120]  Hand over ┐
```

**A18 Email templates (index)**
```
Email templates
 Hardware | Printing | Events | Bookings
 To members
┌ Request accepted        Sent when a request is accepted          [Edited] ┐
 To staff
┌ New request             Sent when someone submits a request               ┐
```

### Batch B

**B1 Email template editor**
```
← All templates
Request accepted  [Edited]                         (Preview)  [Save]  [More v]
Hardware · to members
[ Space default | Laser cutter | 3D printer ]
 Edit | Preview | Default
┌ Subject  [………………………………]            ┐  ┌ Merge fields      ┐
│ Plain text                          │  │ {{member_name}}   │
│ [……………………………………………………]          │  │ {{item_name}} …   │
└─────────────────────────────────────┘  └───────────────────┘
```
Mobile: the Merge fields rail becomes an "Insert field" button above the text area.

**B2 Stocktake session**
```
← All counts
[#14] Count of Box B  [Counting]                         [Complete count]
Started 2 Oct · Blind count
┌Lines counted 23┐┌Variances 2┐
┌ camera / paste ┐ [Product v] [Qty] [Record count]
 Counted so far
┌ Multimeter    counted 9        [–1]                           ┐
```

**B3 Container drawer**
```
│ Electronics bin   [Active]        × │
│ B-04 · Shelf 2                       │
│ Contents | History | Details         │
│ Products: Arduino Uno · 6 avail      │
│ Units: MM-03 [Out]   Show QR  [...]  │
```

**B5 Service queue tab (inside machine type)**
```
 Overview | Queue | Manual usage | Printer reports | …
 Pending 3 | Accepted 1 | Printing 2 | Ready 1 | Failed
┌ (AK) Bracket v2   planned 40 g · actual —        [Pending]  Accept [...] ┐
```

### Batch C

**C1 API access:** the org6 layout, as is:
```
API access
┌ New API client ──────────────────────────────────────────────┐
│ [Client label] [Allowed origins]                               │
│ What can it do?  ┌☑ Inventory   ┐┌☐ Requests  ┐┌☐ Events    ┐ │
│                  └inventory:read ┘└requests:…  ┘└events:read ┘ │
│ [Create client]                                                │
└────────────────────────────────────────────────────────────────┘
 Clients
┌┄ No clients yet. The secret appears once, right after you create one. ┄┐
 Developer reference
┌ ! Keep keys in a secret manager. Never put them in browser code or URLs. ┐
```

**C2 Modules**
```
Modules                          Switch features on for Fab Lab…
 Lending 3/4 │ Loans · Borrowing with evidence…           [● on ]
 Machines 2/3│ ─────────────────────────────────────────────
 Events 1/2  │ Events · Public events, registration…      [○ off]
 Money 1/3   │ Payments · Online card payments…  Needed by: Memberships [● locked]
 Platform    │
```
Mobile: the sub-nav becomes a horizontal chip row above the rows.

**C3 Platform settings, C4 Backup & restore** (the org5 template):
```
Platform settings
 Email  │ SMTP host           [………………]
 Sign-in│ ─────────────────────────────
 Stripe │ SMTP password       [••••••] (Saved)
        │                         (Discard) [Save]
        │ ┌ Danger zone ───────────────────────────────────────┐
        │ │ Clear secret key   Removes the saved key.  (Clear…) │
```

**C5 Organizations**
```
Organizations
┌[MC] Maker Collective    ┐ ┌┄ + New organisation ┄┐
│ Owner · 3 spaces        │ │ A home for a group…  │
└─────────────────────────┘ └┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
→ Maker Collective          (View public page ↗)
 Profile │ Name        [Maker Collective]
 People  │ Public slug  …/o/maker-collective   Copy
 Invites │ …                              (Discard) [Save]
 Spaces  │
```

**C6 Member account:** the auth6/auth7 layout, as is, with tabs Profile · Security · Membership · Your data.

**C7 /mfa:** centred card (see Batch F).

### Batch D

**D1 Platform dashboard**
```
Checked 2 min ago
Platform                                                    (Run checks now)
┌ ! Offsite backup "b2" failed verification.                    Inspect → ┐
┌Live 12┐┌Hidden 1┐┌Failed emails 3┐┌Failed alerts 0┐
 Problems                                      │ Backups
┌[Error] Scheduler: reports didn't run   Inspect│ Last success 02:00
┌[Warn ] Fab Lab near storage limit      Inspect│ Offsite b2 [Needs attention]
 Tenant usage · Scheduler freshness            │ Delivery …
```

**D2 Usage & limits**
```
Usage & limits                                                  (Refresh)
┌Members         ┐┌Storage          ┐┌API calls today ┐
│ 340 of 500     ││ 4.1 of 5 GB     ││ 1,204          │
│ ▬▬▬▬▬▬▬───     ││ ▬▬▬▬▬▬▬▬▬─ (82%)││ Unlimited      │
```

**D3 Organization analytics**
```
Organization analytics
[Organization: Maker Collective v]  [Report: Loans v]
┌Total loans 812┐┌Overdue 9┐┌…┐
 Breakdown by space
┌ Fab Lab ─ table ┐ ┌ Uni Lab ─ table ┐
```

**D4 Makerspace picker**
```
Wednesday, 15 October
Good morning, Shaan                       [Search spaces……]
Choose a space to work in.
┌[FL] Fab Lab        ┐┌[UL] Uni Lab        ┐┌[TS] Tinker Space         ┐
│ FLAB · /m/fab-lab  ││ ULAB               ││ [Superadmin access: off] │
```

### Batch E

**E1 Bulk import**
```
Bulk import                         Step 2 of 4 · Match columns
 ● Upload ─ ● Match columns ─ ○ Review ─ ○ Import
┌ Name       ← [Item name v]    Quantity ← [Qty v]                 ┐
│ Category   ← [Don't import v] Location ← [Shelf v]               │
                                                   (Back) [Preview]
```

**E2 QR labels**
```
← All batches
October labels · 24 labels                         [Download all (ZIP)]
┌ Add labels  [ Item | Units | Reprint a unit ] ┐  ┌QR┐┌QR┐┌QR┐┌┄+┄┐
│ [Item v]                     [Add to batch]   │  │A1││A2││B4││add│
```

**E3 Create makerspace**
```
New makerspace                    Step 1 of 5 · Identity
 ● Identity ─ ○ Profile & hours ─ ○ Modules ─ ○ First staff ─ ○ Review
[Name……………]                                     PUBLIC PAGE PREVIEW
[Public code ▢▢▢▢]  Shown on labels and receipts  ┌[TS] Tinker Space ┐
[Slug …/m/ tinker-space]                          │ /m/tinker-space  │
[Location……]                                      │┄ Catalogue here ┄│
Cancel                                        (Back) [Next]
```

**E4 Tenant migration**
```
Tenant migration
┌ ! This is one-way. Cut-over archives the source space…            ┐
 ✓ Review disclosure ─ ✓ Pin deployments ─ ● Encrypt export ─ ○ … ─ ○ Cut over
┌ Step 3 · Encrypt export (source)        ┐ ┌ Status         ┐
│ [Recipient key……]  [Create export]      │ │ 1 Done ✓       │
│ export 3 Oct  [Ready] Download one-use  │ │ 4 Needs step 3 │
```
Mobile: the stepper collapses to "Step 3 of 6 · Encrypt export" with a "Steps" sheet.

**E5 Password recovery:** the auth2 card (see Batch F).

### Batch F (one template)
```
 space works
                 ┌──────────────────────────────┐
                 │          ( icon )            │
                 │   Set a new password         │
                 │   asha is using a temporary… │
                 │   [Current password]         │
                 │   [New password] ▬▬▬─  ✓ 12+ │
                 │   [Confirm]                  │
                 │   [   Save new password    ] │
                 │        Sign out              │
                 └──────────────────────────────┘
```
Mobile: the card goes full-width with a 16 px gutter; the logo stays top-left.

### Batch G

**G1 Landing**
```
space works                                         About   Sign in
Space Works
Find a space. Borrow the tool.            (Unbounded accent, once)
[Search by name, code or place………………………]   12 spaces
┌ cover ┐┌ cover ┐┌ cover ┐
│[FL] Fab Lab · Bengaluru   FLAB   Open catalogue → │
```

**G3 Public machines**
```
{Fab Lab}  Catalogue  Machines  Events  Bookings         Sign in
What you can use at Fab Lab
(All)(3D printers)(Laser)(CNC)  (Training required)
┌ img ┐┌ img ┐┌ img ┐
│ Bambu X1 [Available] 312 h · 3 jobs queued · ~2 h   [Request a job] │
```

**G4 Public bookings (detail state)**
```
← All spaces
┌ hero image ───────────────────────────────┐
Bench 2 · Workshop · Ground floor            ┌ Book this space ──────────┐
Description…                                 │ [Date] [From][To]         │
Availability calendar                        │ [Your details…]           │
                                             │ [Request booking]         │
                                             │ Staff confirm within a day│
```

**G6 Print request**
```
3D printing
Send a print job to Fab Lab
 Your print   [Title] [Project brief]          ┌ Track your job ─────┐
 Material     [Filament v] [Qty] [Grams]       │ After you send it…  │
 Files        ┌┄ Drop model files ┄┐           │ ○ Requested         │
              ┌┄ Drop screenshots ┄┐           │ ○ Accepted …        │
 [Send print request]                          └─────────────────────┘
```
Mobile: the tracker card moves above the form once a token exists, otherwise below it.

**G7 Public stats**
```
Live stats
Fab Lab in numbers
 Printing  ┌Busiest printer┐┌Queue 4┐  [bar: by brand] [trend]
 Lending   ┌Most popular┐┌Tools out 37┐┌Recently added┐
 Out right now  rows…
```

**G8 Public organization**
```
[MC] Maker Collective                                   (Visit website ↗)
Description…
Upcoming events across spaces
┌[OCT|14] Robotics meetup   Fab Lab · 6 pm · Free   [6 spots left]  Register at Fab Lab ┐
```

**G9 Event feedback:** a narrow form, with the Batch F card for the end states.

**G10 Self-checkout** (mobile-first; desktop centres a 480 px column)
```
[ Borrow | Return ]
Step 2 of 4 · Scan
┌───────────────┐
│ ┌─┐       ┌─┐ │
│               │   Hold the tool's QR inside the frame
│ └─┘       └─┘ │
└───────────────┘
(Back)                       [Next]
```

**G11 Archived payments:** a narrow list of space sections with charge rows.

### Batch H (inside the member shell)
```
Bookings                                                   [Book a space]
 Upcoming | Past
┌[OCT|16] Bench 2 · 10:00–12:00                    [Confirmed]  Move [...] ┐
```
H1, H3, H4 and H5 follow the same row template. H6 uses the auth6 settings template with sub-tabs.

### Batch I
**I1 locked:** the att10 layout, as is. Left: avatar, "{event} · Door check-in", "Enter the station
PIN", 8 boxes. Right: keypad + "Open check-in". **I1 unlocked:** the att11 layout, as is. Station bar
with counter, Online pill and "Lock station"; scanner left; result panel right with "Next guest" /
"Undo"; recent list; search + Find. Mobile/tablet portrait: the stage sits above the side panel; keypad
keys stay at least 64 px.

**I2 Public desk kiosk:** station bar + catalogue body. **I3 Scanner page:** the att11 layout with the
resolved-object card in the side panel. **I4 Offline page:** a single-column card + loans + two buttons.
