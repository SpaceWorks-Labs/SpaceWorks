# Functionality parity audit — public, member, auth and kiosk routes

Status: read-only research. No app code was changed. Written 2026-10-15.

- **Old** = commit `d3e5ed29` (`dev`, pre-revamp), read with `git show d3e5ed29:<path>`.
- **New** = the `feature/design-revamp` **working tree** (including uncommitted edits).
- Scope: every non-staff route in `frontend/src/AppRoutes.tsx` plus the sign-in / reset / MFA /
  invitation pages the staff routes fall back to. The route table itself is unchanged: both versions
  register the same paths (`git diff d3e5ed29 -- frontend/src/AppRoutes.tsx` only restyles
  `NotFoundPage`, `FamilyHome`'s empty and error states and `RouteFallback`).
- No public or member source file was **deleted** in the revamp; the only deletions under
  `frontend/src` are staff dock files. So every "MISSING" below is a capability that was dropped
  from a file that still exists, or a component that still exists but is no longer rendered.
  I grepped the new tree for each one before calling it missing.

Status key:

| Status | Meaning |
|---|---|
| PRESENT | Same capability, same endpoint, reachable on the same page without extra clicks. |
| BURIED | Still works, but now behind a tab, `?section=`, drawer, modal, overflow menu, user menu or the mobile action sheet. |
| CHANGED | Still exists, but behaviour, copy, data shown or the control changed in a way a user would notice. New defects are listed here as well. |
| MISSING | No longer rendered anywhere on the page (or anywhere in the app). |

Shared chrome used by most new public pages (referenced below as **chrome**):
`components/layouts/PublicLayout.tsx` (header: makerspace brand → link home, "Sign in" →
`member`, nav, `liveStatus`; footer: Space Works symbol + credit + links) fed by
`features/inventory/PublicPageChrome.tsx` (`publicPageChrome`: nav Catalogue / Events / Machines /
Book a space / Request a 3D print / Stats gated on the same modules and `public_stats_enabled`;
`liveStatus` = `MakerspaceMapLink` + icon `ThemeToggle`; footer About / License / Staff sign-in /
support email / support URL).

---

## 1. Landing / makerspace directory — `/` (central)

Old `features/LandingPage.tsx` · New `features/LandingPage.tsx` (PublicLayout, central identity).

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Auto-redirect to the only makerspace when exactly one exists | LandingPage.tsx:51 | PRESENT | LandingPage.tsx:28 |
| Space Works home link + wordmark "Space Works · Shared equipment portal" | :57-63 | CHANGED | Header now shows the full horizontal/stacked logo (PublicLayout.tsx:33-34); the "Shared equipment portal" tagline is gone. |
| Theme toggle in header | :65 | PRESENT | `liveStatus={<ThemeToggle />}` |
| "Staff login" button in header | :66 | BURIED | Footer link "Staff sign-in" only; header button is now "Sign in" → `/member`. |
| Sidebar eyebrow "Inventory Directory" + h1 "Makerspaces" + intro copy | :74-78 | CHANGED | h1 is now "Less searching. More making." with a new subtitle. |
| "Public spaces" count tile | :80-84 | CHANGED | Count moved into the search toolbar text `filtered / N spaces` (LandingPage.tsx:33). |
| "Live · Status access" tile | :85-88 | MISSING | Not rendered anywhere (decorative; low value). |
| "Standard public portal" badge | :98-101 | MISSING | Not rendered (decorative). |
| Search by name/code/slug/location (token AND match) | :103-111, :31-47 | PRESENT | `FilterBar` in header meta (LandingPage.tsx:30-32). |
| Clear search button | :113 | PRESENT | "Clear search" (LandingPage.tsx:32) and in empty state. |
| Live "x/y shown" counter (aria-live) | :114-116 | PRESENT | LandingPage.tsx:33 (`aria-live`). |
| Loading spinner | :120 | PRESENT | PublicLayout `state: loading` skeleton. |
| "Makerspaces are unavailable" error card | :121-126 | CHANGED | Generic error block with a new **Retry** button (improvement). |
| "No public makerspaces yet" empty card | :127-132 | PRESENT | Empty message (LandingPage.tsx:38). |
| "No matching makerspaces" empty card | :133-138 | PRESENT | Empty message + Clear search action. |
| Space card: cover image (grayscale → colour on hover) | :145-147 | CHANGED | Cover shown in colour; no-cover fallback is now an initial letter instead of the blueprint pattern. |
| Space card: "Public" chip | :148 | PRESENT | `StatusPill "Public catalogue"` (LandingPage.tsx:47). |
| Space card: MakerspaceBrand (logo + name) | :151 | PRESENT | LandingPage.tsx:50. |
| Space card: map/location link | :152 | PRESENT | LandingPage.tsx:51. |
| Space card: public code | :154 | PRESENT | LandingPage.tsx:53. |
| Space card: "Open catalog →" full-card link | :155-161 | PRESENT | "Open catalogue →" (LandingPage.tsx:54). |
| New: nav "About", footer About / Staff sign-in | — | (new) | — |
| Footer copyright "© year Space Works — Open Source Makerspace Manager" + License link (SiteFooter) | :170 | CHANGED | Footer credit is "Space Works · Made for shared workshops"; **License link is gone from this footer** (still on tenant pages via `publicPageChrome`). |

## 2. About — `/about`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Space Works logo + wordmark home link | AboutPage.tsx:12-18 | CHANGED | Full logo via PublicLayout central identity. |
| Theme toggle | :20 | PRESENT | `liveStatus` |
| "Staff login" header button | :21-23 | BURIED | Footer "Staff sign-in" + ListRow at AboutPage.tsx:17. |
| h1 + three explanatory paragraphs | :30-56 | PRESENT | Copy shortened (AboutPage.tsx:11-14). |
| AGPL licence link | :47-54 | PRESENT | AboutPage.tsx:14. |
| "Browse makerspaces →" card | :59-62 | PRESENT | ListRow "Browse spaces" + header primary + nav. |
| "Staff login →" card | :63-66 | PRESENT | ListRow "Staff sign-in". |
| SiteFooter (copyright + About + License) | :70 | CHANGED | Footer has only "Staff sign-in"; License link gone from footer (still in body). |

## 3. FamilyHome / empty tenant / 404 (`/`, `/m/:slug`, `*`)

| Capability | Old file:line | Status | New location |
|---|---|---|---|
| Choose home by `publicHome(bootstrap)` (events / bookings / machines / membership / inventory) | AppRoutes.tsx:50-56 | PRESENT | AppRoutes.tsx:57-62 |
| "Unable to load this makerspace" | :48 | CHANGED | PublicLayout error with Retry and a "Space Works" placeholder brand. |
| "No public programme is available" | :57 | CHANGED | Empty state "X hasn't published anything yet" inside chrome with Sign in. |
| 404 "Page not found" | :37 | CHANGED | CenteredCardLayout with "Go to home" and (under `/admin`) "Staff sign-in" (improvement). |
| Single-tenant "Loading site…" / "Site unavailable" (App.tsx) | App.tsx:27-50 | CHANGED | CenteredCardLayout; "Site unavailable" gains a Retry button. |

## 4. Public catalogue — `/m/:slug` · `/` (single)

Old `features/inventory/PublicInventoryPage.tsx` + `publicInventory/PublicInventoryHeader.tsx` +
`PublicInventoryParts.tsx`. New `PublicInventoryPage.tsx` inside PublicLayout (`width="wide"`, aside
= PublicActionCard). **`PublicInventoryHeader.tsx` still exists but is no longer imported anywhere
(dead code).**

### 4a. Header and page

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| PageMetadata (title, description, OG image) | PublicInventoryPage.tsx:80 | PRESENT | :96 (skipped when `embedded`). |
| Skip link | :81 | PRESENT | PublicLayout/LayoutFrame skip link. |
| Eyebrow "Public Inventory" + h1 = MakerspaceBrand (xl) | PublicInventoryHeader.tsx:29-40 | CHANGED | Brand moved to the header bar (normal size); h1 is "Borrow tools from {name}". |
| Tagline "Shared tools and equipment published by this makerspace." | Header:41-43 | CHANGED | Subtitle is now "{n} tools and kits". |
| Map / location link | Header:44-47 | PRESENT | chrome `liveStatus`. |
| Stats icon link (gated `public_stats_enabled`) | Header:51-55 | PRESENT | chrome nav "Stats" (same gate). |
| Theme toggle (icon) | Header:56 | PRESENT | chrome `liveStatus`. |
| Staff login icon link | Header:57-59 | BURIED | Footer "Staff sign-in" only. |
| SpaceWorksBadge | Header:62 | CHANGED | Space Works symbol now only in footer. |
| "{n} listed items" counter | Header:63-65 | CHANGED | Folded into subtitle "{n} tools and kits". |
| "Request a 3D print" link (module `printing`) | Header:66-70 | PRESENT | chrome nav. |
| "Events" link (module `events`) | Header:71-75 | PRESENT | chrome nav. |
| "Machines" link (module `machines`) | Header:76-80 | PRESENT | chrome nav. |
| "Book a space" link (module `bookings`) | Header:81-85 | PRESENT | chrome nav. |
| New: "Member area" header primary, "Sign in" header action | — | (new) | PublicInventoryPage.tsx:99 |
| SiteFooter with `SupportContact` (support email / URL) and License | :198 | PRESENT | chrome footer links (email + support URL + License). |

### 4b. Browse, search, list

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Browse "All items" | PublicInventoryParts.tsx:76-83 | PRESENT | Chip row (PublicInventoryParts.tsx:44-54). |
| Browse "Popular" (`sort=popular`) | :84-96 | PRESENT | Chip row. |
| Browse "Most used" (`sort=most_used`) | :97-110 | PRESENT | Chip row. |
| Categories list with product counts | :112-141 | CHANGED | Same data, but merged into one horizontally scrolling chip row with no "Browse"/"Categories" headings; the sticky left sidebar is gone (many categories now scroll off-screen horizontally). |
| Search box + Search button | PublicInventoryPage.tsx:98-110 | PRESENT | :81-83 |
| Clear search | :111-123 | PRESENT | :84 and empty-state action. |
| Loading state | :127 | PRESENT | QueryContent skeleton. |
| Error card "…may not exist or its public inventory is disabled" | :129-131 / Parts:41-48 | CHANGED | Generic "Couldn't load inventory. Try again." + Retry. |
| Empty "No matching items" / "No public items yet" | :133-135 | PRESENT | :86 |
| Pagination "Page x of y" + Previous / Next (+ "loading…") | :152-177 | CHANGED | Shared `Pagination` component (:90). |

### 4c. Product card (`ProductCard.tsx`) and quick view

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Image (or initials) opens quick view | ProductCard.tsx:56-75 | PRESENT | unchanged structure. |
| Availability chip (Available (n) / Limited (n) / Unavailable) | :17-40 | CHANGED | `AvailabilityBadge` pill ("n available"/"n limited"); Unavailable is now neutral grey, was neutral chip on card but **red** on the quick view/item page. |
| Name links to item detail page | :83 | PRESENT | unchanged. |
| ID label, description (clamped), category chip | :91-98 | PRESENT | unchanged. |
| Quantity stepper − / count / + (add/remove to request) | :102-122 | PRESENT | unchanged. |
| "Quick view" / "Details" button | :126-131 | PRESENT | unchanged. |
| Quick view: modal with image, ID, name, availability, tracking chip, category chip, description, Close | ProductQuickViewModal.tsx:23-93 | CHANGED | Now a right-hand `DetailLayout` drawer (720px); tracking mode moved into the meta line; same fields. |

### 4d. Request panel (`PublicRequestPanel.tsx`, `BorrowRequestCard.tsx`)

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| "Requests unavailable" card when `request_workflow` off | PublicRequestPanel.tsx:163-171 | PRESENT | unchanged. |
| "Borrow something" / "Member borrowing" explainer card | :174-194 | PRESENT | unchanged. |
| Tab switch "Borrow request" / "Scan a tool" | :196-218 | CHANGED | `SegmentedControl` (same two modes). |
| Panel placement: sticky right column on desktop | PublicInventoryPage.tsx:182-190 | CHANGED | PublicActionCard "Your request": inline aside from 768px; **on phones it collapses to a bottom bar "N items · Review request" that opens a modal** — the "Scan a tool" mode is reachable only by first opening "Review request". (BURIED on mobile.) |
| Selected items list with quantities + count badge | BorrowRequestCard.tsx:57-89 | PRESENT | unchanged. |
| Clear selection | :90-92 | PRESENT | unchanged. |
| Account-less contact fields (name, email, phone optional) gated on `request_access=anyone` + session probe | :97-135 | PRESENT | unchanged. |
| Honeypot `website` | :137-148 | PRESENT | unchanged. |
| "Requested for" textarea | :150-160 | PRESENT | unchanged. |
| Submit request (idempotency key, `submitPublicRequest`) | :161-168, Panel:79-123 | PRESENT | unchanged. |
| Success banner + account-less public token | :170-195 | PRESENT | unchanged. |

### 4e. Scan a tool (`PublicToolScanPanel.tsx`) and evidence upload

| Capability | Old file:line | Status | New location |
|---|---|---|---|
| "Scan QR with camera" (QrScanner) | PublicToolScanPanel.tsx:95-101, :197 | PRESENT | unchanged (but see 4d mobile note). |
| "Scanned OK" + clear | :103-111 | PRESENT | unchanged. |
| Check out: issue photo (`PublicEvidenceUpload` file + camera) + Check out (`publicToolCheckout`) | :115-133 | PRESENT | unchanged. |
| Return: return photo + condition notes + "Report a problem" checkbox + problem note + Return (`publicToolReturn`) | :135-183 | PRESENT | unchanged. |
| Loan result card (status, items, public token) | :15-33, :193 | PRESENT | unchanged. |
| Evidence upload: file input, "Take photo" camera button, presign + upload | PublicEvidenceUpload.tsx:57-83 | PRESENT | unchanged (restyled file button). |

## 5. Public item page — `/m/:slug/items/:itemId`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| PageMetadata (title, description, image) | PublicItemPage.tsx:45 | PRESENT | :50 |
| "Back to {name}" button | :48 | CHANGED | Breadcrumb "Catalogue / item" + header brand link. |
| Theme toggle | :48 | PRESENT | chrome. |
| Loading skeleton | :51 | PRESENT | QueryContent. |
| "Item not found" / "Inventory is not enabled" | :52 | CHANGED | Now a full-page CenteredCardLayout with "Back to the catalogue" (no catalogue chrome). |
| Generic error + Retry | :52 | PRESENT | PublicLayout error + Retry. |
| Image | :54 | PRESENT | Cover image (PublicDetailLayout). |
| Name + availability badge | :55 | PRESENT | Title + action-card summary. |
| Borrowing terms | :56 | PRESENT | "Borrowing terms" section. |
| Notify-when-back (feature `inventory.notify_when_back`) | :57 | PRESENT | Inside action card form. |
| Category | :58 | PRESENT | Chip. |
| Description | :59 | PRESENT | "Description" section. |
| "Request from the catalogue" (module `request_workflow`) | :60 | PRESENT | Action-card primary. |
| New: mobile bottom bar "Borrow this item" | — | (new) | — |

## 6. Self-checkout — `/m/:slug/checkout`

Old `PublicSelfCheckoutPage.tsx` (header + card). New: `FlowLayout` (`compact`) + SiteFooter.

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Header eyebrow "Public Tool Checkout", MakerspaceBrand h1, explainer | :106-123 | CHANGED | h1 "Borrow or return a tool", subject = name; MakerspaceBrand moved inside the work card (:124). |
| "Back to inventory" header link | :126-128 | CHANGED | Only the flow's "Cancel" button navigates back (:116). |
| Loading / error / "Self-checkout is not enabled" + back link (feature `inventory.self_checkout`) | :135-158 | PRESENT | FlowLayout state + empty with "Back to catalogue" (:106-110). |
| Mode switch "Use (check out)" / "Return" | :162-190 | PRESENT | SegmentedControl "Borrow"/"Return" (:125). |
| Issue photo upload | :193-200 | PRESENT | :127 |
| Return photo + "Return condition notes" (required) | :201-221 | PRESENT | :128-129 |
| "Scan QR" (disabled until photo/notes) | :225-232 | PRESENT | Footer next "Scan QR" with disabled reason (:117-120). |
| Kit checklist capture + "Confirm checkout/return" | :234-238 | PRESENT | `KitChecklistCapture` + footer label switches to Confirm. |
| Error message | :239-243 | PRESENT | Flow error callout. |
| Result card (repeat use without leaving the form) | :245-249 | CHANGED | Result panel replaces the form; user must press "Borrow another"/"Return another" to reset (extra click per tool). |
| New: step list (Photo → Scan → Check the kit) | — | (new) | — |

## 7. Public events list — `/m/:slug/events`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| PageMetadata + canonical path when events is home | PublicEventsPage.tsx:44, :102 | PRESENT | :40, :93 |
| Header: eyebrow, MakerspaceBrand, SpaceWorksBadge, "Inventory" link, theme toggle | :104-111 | CHANGED | chrome (brand in bar, nav, symbol in footer). |
| h1 "Upcoming events" + intro | :113 | PRESENT | header; new primary "My events" → `member/events`. |
| Discovery: search, month, List/Month calendar, Free events / Registration open, Clear filters | :114 | PRESENT | :97 (List/Calendar now a SegmentedControl). |
| Category filter | :115 | PRESENT | :98 |
| Tag filter | :115 | PRESENT | :99 |
| "{n} matching event(s)" status | :116 | PRESENT | :100 |
| Month calendar view with anchor links | :117 | PRESENT | :101 |
| Loading skeletons | :118 | PRESENT | chrome loading state. |
| Distinct error titles (Please slow down 429 / Events are not enabled 400 / Makerspace not found 404 / unavailable) and Retry only when retryable | :119-122 | CHANGED | One generic "Couldn't load events. Try again." with Retry always offered (also for 400/404 where retry cannot help). |
| Empty states (no events / no matching) | :123-124 | PRESENT | :102 |
| Grouping by recurring series with "Recurring series" eyebrow | :125-126 | CHANGED | Series title kept; eyebrow dropped. |
| Event cover image on each card | :135 | MISSING | ListRow uses a date chip; `item.image_url` is not rendered on the list. (Still on the detail page.) |
| Title linking to detail page | :137 | PRESENT | ListRow `href`. |
| Start–end time + location | :137 | PRESENT | ListRow meta. |
| Event `status` badge (`StatusBadge item.status`) | :137 | CHANGED | Replaced by a pill from `availability`/`registration_open`; the event's own status (e.g. cancelled/postponed) is no longer shown. |
| Description on the card | :138 | MISSING | Not rendered on the list (detail page only). |
| Price (EventPrice incl. "From", Free, "No tickets available") | :139 | PRESENT | inline EventPrice. |
| Capacity ("Unlimited" / n) | :139 | MISSING | Not shown on the list **or** on the detail page. |
| Availability label | :139 | PRESENT | Pill (Full → warn). |
| "Registration closed · {cutoff time}" | :140 | BURIED | List shows only "Registration closed"; cutoff time only on the detail page note. |
| Register / Apply / Join waitlist button that **expands the registration form inline** | :141, :144 | CHANGED | Button is now a link to the detail page; registration happens there (one extra page load). |
| "Add to calendar" (.ics download) with "Preparing…" | :142 | PRESENT | :110 (no "Preparing…" label; button still disables). |
| Calendar download error | :143 | PRESENT | :111 |

## 8. Public event detail — `/m/:slug/events/:publicToken`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| "All events" back button | PublicEventDetailPage.tsx:34 | CHANGED | Breadcrumb "All events". |
| Loading / 400 / generic error | :35-36 | PRESENT | PublicLayout state + Retry. |
| 404 "Event not found." | :36 | CHANGED | Full-page CenteredCardLayout with "All events" (:35). |
| PageMetadata | :38 | PRESENT | :37 |
| Cover image | :39 | PRESENT | `cover` |
| Title | :40 | PRESENT | |
| Start time · location | :41 | PRESENT | Facts row (start, "Until" end, location). |
| Category, tags | :42-43 | PRESENT | Chips. |
| Description | :44 | PRESENT | "About" section. |
| Price | :45 | PRESENT | Action-card summary. |
| Add to calendar | :46-47 | PRESENT | Action-card secondary. |
| Share event (Web Share / clipboard) | :48-49 | PRESENT | Action-card secondary. |
| Registration form (when open) / "Registration is closed." | :50 | CHANGED | Action card titled Join/Apply/Join waitlist. **When the event has a custom form, tickets, promo codes or invite audience the form is now behind a "Register" button that opens a modal** (EventRegistrationEntry.tsx:13-17); simple events render inline. Closed note now includes cutoff time. |
| Header chrome (brand, nav) | — | CHANGED (defect) | New page has chrome, but in **central mode** it passes no bootstrap (PublicEventDetailPage.tsx:32,38): the brand shows the **raw slug** with no logo and the nav shows only "Catalogue". Needs `useTenantBootstrap` like the other pages. |
| Capacity / availability text | — | MISSING | See §7; never shown on detail. |

### 8a. Registration form (`EventRegistrationForm.tsx`) — unchanged fields

| Capability | Old file:line | Status | Notes |
|---|---|---|---|
| Honeypot, contact fallback (phone/email when account lacks them) | EventRegistrationForm.tsx:~99-101 | PRESENT | |
| Ticket picker (`EventTicketPicker`) + "Choose a ticket type" validation | ~102 | PRESENT | |
| Invitation code (audience `invite`) | ~103 | PRESENT | |
| Promo code (when `promo_codes_enabled`) | ~104 | PRESENT | |
| Custom form fields + server errors | ~106 | PRESENT | |
| Submit Register / Apply / Join waitlist | ~110 | PRESENT | |
| "No tickets available for this account" | ~84 | PRESENT | |
| Success panel (pending / waitlisted / registered) | :72-77 | CHANGED | Now a `TicketCard` with a check icon; `organisation` is hard-coded to "Space Works" instead of the makerspace name. |

## 9. Event feedback — `/m/:slug/events/:publicToken/feedback`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Loading skeleton | PublicEventFeedbackPage.tsx:58 | PRESENT | PublicLayout loading. |
| "Feedback unavailable" + reasons ("closed, event not ended, or link invalid") + Back to events | :59 | CHANGED | CenteredCard; explanation shortened to "Feedback is closed for this event." (loses the "not ended / invalid link" hint). |
| Thank-you text + certificate note + "Open member area" | :60 | PRESENT | CenteredCard success. |
| Event title eyebrow, survey title, anonymous/certificate note | :63-64 | PRESENT | header eyebrow/title/subtitle (copy shortened). |
| "Sign in … before submitting certificate feedback" + Member sign in | :65 | PRESENT | Card + link. |
| Survey questions (CustomFormFields, yes/no as checkbox) + validation + API errors | :66-67 | PRESENT | |
| Registration email (when `requires_auth`) | :68 | PRESENT | |
| Submit feedback (disabled until restored session) | :69 | PRESENT | |
| SiteFooter | :73 | CHANGED | chrome footer. |

## 10. Public machines — `/m/:slug/machines`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Header (eyebrow "Our Machines", MakerspaceBrand, badge, Inventory link, theme) | PublicMachinesPage.tsx:93-100 | CHANGED | chrome; new primary "Member area". |
| h1 "Machines" + intro | :102 | PRESENT | header. |
| Loading / distinct error titles (429/400/404) + conditional Retry | :103-107 | CHANGED | Generic error, Retry always. |
| Empty "No machines listed" | :108 | PRESENT | :90 |
| Collapsible group per machine type with **type icon** and count | :109-112 | CHANGED | Plain toggle button "Type · n" (:98); `machine_type.icon` no longer rendered. |
| Machine image | :117 | CHANGED | Small ListRow thumbnail instead of a 9rem card image. |
| Name | :119 | PRESENT | |
| Status badge (idle/running/reserved/maintenance/offline) | :121 | CHANGED | Mapped to Available / In use / Reserved / **Down** — maintenance and offline are no longer distinguishable. |
| Usage hours logged | :122 | PRESENT | |
| Status since (absolute time) | :124 | CHANGED | Relative time. |
| Training required / not required (detail feature) | :125 | PRESENT | |
| Queue length + ETA (detail feature) | :126 | PRESENT | |
| Structured intake form inline (feature `machines.structured_intake`): job title, schema fields, material/colour, Request work | :127, MachineIntakeForm.tsx | BURIED | Behind a "Request a job" button that opens a modal (`dialog` prop). |
| Pagination (24) | :134-135 | PRESENT | :108 |
| New: kind filter chips + "Training required" filter | — | (new) | :91-96 |

## 11. Public bookings — `/m/:slug/bookings`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| PageMetadata + canonical | PublicBookingsPage.tsx:42, :61 | PRESENT | :31, :59 |
| Header: brand, badge, Inventory, Events (module), "My bookings", theme | :63-77 | CHANGED | chrome nav; "My bookings" is now header primary → `member/bookings` (old went to `member`). |
| h1 + intro | :80-81 | PRESENT | |
| Discovery: search + kind facets + month + List/Calendar + Clear | :83 | PRESENT | :63 |
| "{n} matching space(s)" | :84 | PRESENT | :64 |
| Distinct errors (429/400/404) + conditional Retry | :86-92 | CHANGED | Generic + Retry. |
| Empty / no-match states | :93-94 | PRESENT | :65 |
| Space card image | :101 | CHANGED | Thumbnail in ListRow; full cover only on the space detail view. |
| Name, location, kind badge | :105-108 | PRESENT | |
| Description | :110 | PRESENT | ListRow meta / detail "About this space". |
| Capacity + confirmation mode + explanatory sentence | :111-115 | PRESENT | Pill + meta; sentence moved into the detail action card note. |
| Per-space month calendar (calendar view) | :116 | PRESENT | :73 |
| "Choose a time" expands booking form inline | :117-118 | CHANGED | Opens a per-space detail view via `?space=` (PublicDetailLayout) with "Availability" section + booking form in the sticky action card; "Close booking form" returns. Deep-linkable (improvement). |
| Booking form: published availability (Previous/Next 14 days, booker names), starts/ends, honeypot, submit, pending vs booked confirmation | PublicBookingForm.tsx, AvailabilityCalendar.tsx | PRESENT | Availability shown as a detail section (`showCalendar={false}` on the form). |

## 12. Print request — `/m/:slug/print`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Header: eyebrow "Public 3D Print Request", brand h1, intro, badge, "Back to inventory" | PublicPrintRequestPage.tsx:60 | CHANGED | chrome; h1 "Send a print job to {name}", chip "3D printing". |
| Loading / error panels | :60 | PRESENT | Layout state + Retry (new). |
| Printing unavailable panel + back link | :60 / Panels:10 | CHANGED | EmptyState "3D printing isn't open…" + "Back to catalogue"; the token-status block still shows via the action card. |
| Form: Title, Project brief, Slicer settings | PublicPrintRequestForm.tsx:105-118 | PRESENT | Grouped under "Your print" fieldset. |
| Material + Colour selects (catalogue) | :121-122 | PRESENT | "Material" fieldset. |
| Filament pool select (grouped by material) + loading/error | :134-165 | PRESENT | |
| Quantity, Estimated filament (g), Source link | :168-200 | PRESENT | |
| Model files picker + screenshot picker with per-file Remove | :203-215, Parts:87-130 | PRESENT | ListRow per file; empty state "No files added yet". |
| Honeypot | :93-102 | PRESENT | |
| Upload progress + submit error + "Submit print request" | :218-233 | PRESENT | Button renamed "Send print request". |
| Status tracker: submitted note, title, created time, 5 steps, queue position, live time-left countdown, current status | Panels:7, Parts:164-266 | CHANGED | Action card "Track your job"; steps as pills + progress bar; created time relative; **status error now generic** ("Couldn't load your print status") instead of the server message. |
| Status link from `?token=` | Page (statusLinkHandledRef) | PRESENT | |
| New: "Copy tracking link", auto-scroll to tracker, "Send another request" | — | (new) | |

## 13. Public stats — `/m/:slug/stats`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Header: eyebrow, brand, intro, badge, "Catalog", theme, **"Staff login"** | PublicStatsPage.tsx:42-72 | CHANGED | chrome; "Browse catalogue" primary; Staff login only in footer (BURIED). |
| Loading / "Stats not available" / "No public activity yet" | :75-79, :95-126 | CHANGED | Generic error copy (loses "turned off / may not exist" explanation) + Retry. |
| Printing tiles: hours all time, this month, filament g, completed jobs | StatsSections.tsx:24-41 | PRESENT | StatCards. |
| Busiest printer (image, name, model, hours, completed) | :44-71 | PRESENT | ListRow. |
| Queue: pending / accepted / printing / active | :73-87 | PRESENT | Pills. |
| Filament by brand | :89-98 | PRESENT | |
| Filament trend chart | :101-110 | CHANGED | Bars now rendered as progress bars. |
| Per-printer table (image, model, jobs, hours, grams) | :112-161 | PRESENT | DataTable. |
| Hardware tiles: library size, available now, currently out | :169-181 | PRESENT | Section renamed "Lending". |
| Most popular / Tools out / Recently added | :183-214 | PRESENT | Recently added date → relative time. |
| Currently out cards: item, holder, due, since | :225-252 | PRESENT | ListRow + due pill ("Since" → "Borrowed {relative}"). |

## 14. Public organization page — `/o/:organizationSlug` (central)

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Org brand (logo+name) or Space Works badge fallback | PublicOrganizationPage.tsx:35-37 | PRESENT | PublicLayout brand (org logo/name; Space Works logo while loading). |
| "Directory" link + theme toggle | :39-40 | PRESENT | nav "Directory" + `liveStatus`. |
| Loading / 404 "not found" / error message | :46-52 | CHANGED | Generic error copy (server message dropped) + Retry (new). |
| Eyebrow, h1 name, description (pre-wrap), "Visit website" | :55-63 | PRESENT | Header (description as subtitle). |
| Events: loading, error + Retry, empty | :71-81 | PRESENT | |
| Event card image | :86 | MISSING | ListRow has a date chip only. |
| Hosted by, date range, location, description (3 lines), price, availability | :88-95 | PRESENT | ListRow meta/right (description clamp 2 lines). |
| "Register at {host}" link | :96-98 | PRESENT | |
| Previous / Next + "Page n · count events" | :105-111 | CHANGED | `Pagination` assuming 24 per page (fine only while the API page size stays 24). |

## 15. Organization invitation redeem — `/organization-invitations/redeem/:token`

| Capability | Old file:line | Status | New location |
|---|---|---|---|
| Badge, eyebrow, h1 | OrganizationInvitationRedeemPage.tsx:67-69 | PRESENT | CenteredCardLayout (title becomes "You're in" on success). |
| Restoring skeleton | :70 | PRESENT | Card loading state. |
| Sign-in form (username/email, password, "Sign in and continue", error) | :71-79 | PRESENT | Card content + primary. |
| "Redeeming invitation…" | :80 | CHANGED | Card loading state (no text). |
| Success + "Open organizations" | :81-87 | PRESENT | |
| Error + "Return to directory" | :88 | PRESENT | |

## 16. Member area — `/m/:slug/member`, `/member`, `/member/:memberTab`

Old `features/members/MemberArea.tsx` (one column, tab strip, every panel of a tab stacked). New:
`MemberArea.tsx` → `MemberPortalTabs` (sidebar `AppShell`, mobile bottom tabs) → `MemberSectionNavigation`
→ `MemberScreenLayout` (Dashboard / List / Settings / Public layout per tab) with sub-sections in
`?section=`. All queries, mutations and gates are carried over verbatim.

### 16a. Shell, session, sign-in

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Session restore ("Restoring session…") | MemberArea.tsx:56-58, :128 | PRESENT | CenteredCard loading (:142). |
| Staff claim-session hand-off (`MemberClaimSession`) | :129 | PRESENT | :143 (now DashboardLayout; "Browse tools" header primary). |
| Member sign-in panel (`MemberAuthPanel`) + SupportContact | :130 | PRESENT | :144 (+ tenant brand). See §20. |
| Header eyebrow "Member area" + h1 "Your makerspace access" | :132 | CHANGED | Per-tab page headers (`MemberScreenLayout` titles). |
| Theme toggle in page header | :132 | BURIED | Inside the user menu (UserMenu.tsx:12). |
| Tab strip Overview/Loans/Bookings/Events/Payments/Inbox/Account (module-gated, arrow-key nav) | MemberPortalTabs.tsx:26-53 | CHANGED | Sidebar nav (desktop) + bottom tabs with "More" (mobile); same gating (`memberTabs`). "Overview" renamed "Home". |
| SupportContact at page bottom | :197 | PRESENT | :218 (inside every tab body). |
| "Sign in to your account" button when unauthenticated | :189 | PRESENT | :211 |
| "Sign in" link to `/admin` when memberships query fails (non-401) | :187 | PRESENT | :209 |
| Error line (bootstrap/memberships/request/accept/presence/activity/checkout) | :186 | PRESENT | :208 |
| New: sidebar workspace card (makerspace name, status), user menu (Account & two-step sign-in, theme, **Sign out**), "View public page ↗" | — | (new) | MemberArea.tsx:147-151. Note: user menu shows "Your account" + "Sign out" even when signed out. |

### 16b. Overview (Home) tab

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| PWA install card (`MemberInstall`, module `membership`) | :134 | PRESENT | :156 (rendered at the top of every tab body). |
| Archived-payments card / "Closed makerspace?" card → `/member/archived` | :137-138 | PRESENT | :158-159 |
| Loading / error for joining options | :139-140 | PRESENT | :160-161 |
| "Checking your sign-in status…" | :141 | PRESENT | :162 |
| Admission join (`AdmissionJoin`: application form, Sign in to join) / `JoinMembershipCta` | :142 | PRESENT | :163 |
| Ask for an invitation (`InvitationRequestForm`) | :143 | PRESENT | :164 |
| Own application status (`MemberAdmission`: answers, Cancel application, Download application data) / "Membership request sent" | :144-145 | PRESENT | :165-166 |
| Staff-issued claim code redemption (`MemberClaimRedemption`) | :146 | PRESENT | :167 |
| Membership status card (space · status · role) | :147 | PRESENT | :168 (status as pill). |
| Current waiver text + "Accept waiver" / acceptance on file | :149 | PRESENT | :170 (+ new overview banner "Accept the updated waiver" linking to it). |
| Verifier panel (`can_verify`) | :150 | PRESENT | :171 |
| Vouch for an applicant (join mode `vouch`) | :151 | PRESENT | :172 |
| Presence: status + **Start 2-hour presence / End presence** button (module `presence`, geofence) | :152 | CHANGED | Status card stays (:173); the button moved to the page-header primary action (MemberArea.tsx:155). It is only visible on Home/Account/Inbox-preferences headers (list tabs override `primary`). |
| "Needs your attention" notices | :154 | PRESENT | :175 (now ListRows with level pill). |
| Activity overview: checked-in state, waiver warning, 3D print requests, machine-service requests, recent presence | :157 → MemberActivity.tsx:149-154 | PRESENT | :178 |
| Membership term | :158 | PRESENT | :179 |
| New: stat cards (On loan, Overdue, Bookings), overdue banner, compact member card with "View your member card" | — | (new) | MemberScreenLayout.tsx:27-30, MemberArea.tsx:180 |
| Non-member overview | :132-197 | CHANGED | Rendered as a nested PublicLayout (makerspace header + "Browse catalogue" + Space Works footer) inside the member shell — two headers and two footers on one screen. |

### 16c. Loans tab

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Offline loans control (`OfflineLoansControl`) | MemberActivity.tsx:148 | PRESENT | "Out now" section. |
| Active hardware loans: label, due, overdue, Renew (`MemberLoanRenew`) | MemberActivity.tsx:150 | PRESENT | "Out now" (`?section=current`), ListRows with due date chip. |
| Your history: requests (status, date, items, returned, damaged/missing) + returned items (late flag) | MemberArea.tsx:160 → MemberDashboardSections.tsx:86-133 | BURIED | Second tab "History" (`?section=history`); request date now only in the date chip. |
| "Active membership required" / "Loading your activity…" | :190, :192 | PRESENT | :212, :214 |
| New: "Browse catalogue" header action | — | (new) | |

### 16d. Bookings tab

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Activity "Bookings" section: Upcoming + Past from `/activity` (space, start, status) | MemberArea.tsx:157 → MemberActivity.tsx:152 | MISSING | New MemberArea.tsx:178 renders `MemberActivityPanel` only for overview/events/loans, so the `section="bookings"` block is never shown. Largely duplicated by MyBookings below (same data from another endpoint), so low impact — decide to drop on purpose or restore. |
| My bookings (`MyBookings`): private calendar feed (create / rotate / revoke link) | :188 → MyBookings.tsx:56 | PRESENT | |
| Upcoming / Past toggle | MyBookings.tsx:57-59 | PRESENT | `Tabs` |
| Booking rows: space, start–end + timezone, status, cancel cutoff | :64-70 | PRESENT | ListRow |
| Reschedule booking (inline form → `BookingReschedule`) | :71, :76 | CHANGED | Opens in a modal. |
| Cancel booking + confirm/keep | :72, :77-80 | BURIED | "Cancel booking" moved into an overflow (⋯) menu; confirmation panel unchanged. |
| Loading / error + Retry / empty / pagination | :61-63, :81-85 | PRESENT | |
| New: "Book a space" header action | — | (new) | |

### 16e. Events tab

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Event registrations: calendar subscription link (`MemberCalendarActions`: create/rotate/revoke/copy) | MemberActivity.tsx:153 | PRESENT | Rendered in each of Going/Past. |
| Registration rows: title, status label, "No payment until confirmed", waitlist position | :153 | PRESENT | ListRows with date chip and status pill. |
| Cancel registration (`MemberEventCancel`, cutoff) | :153 | PRESENT | |
| Show / hide check-in QR (authenticated blob) | MemberActivity.tsx:78-119 | CHANGED | Opens a modal "Your event ticket" (TicketCard). Defects: loading text "Loading your ticket?" (literal "?"), `organisation` hard-coded "Space Works". |
| Feedback / certificate (`MemberEventFeedback`) | :153 | PRESENT | |
| All registrations in one list | :153 | BURIED | Split into "Going" / "Past" tabs (`?section=going|past`, by start time). |
| Partner (collaborative) events (`PartnerEvents`) | MemberArea.tsx:161 | BURIED | Third tab "Partner events" (`?section=partners`), shown only once the query returns rows. |
| Partner event: host, date+time, price, Register / Apply…, ticket picker, invite code, promo code, host waiver acceptance, custom form, contact fallback | PartnerEvents.tsx:146-219 | CHANGED | Expanded form now a modal with the register button in its footer; row shows date chip (time of day dropped from the row). |
| New: "See events" header action | — | (new) | |

### 16f. Payments tab

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Membership fee + outstanding per currency / "unavailable" / "Nothing outstanding" | MemberArea.tsx:159 → MemberDashboardSections.tsx:52-77 | PRESENT | StatCards. |
| Payments list: due filter, subject, status, due badge, amount, Pay now (`checkout_url`), Generate payment link (checkout mutation), refunds | :166 → MemberPayments.tsx | PRESENT | ListRow per payment; amount as display number. |
| Receipts and credit notes (`PaymentDocuments`: show/hide, Download PDF, paging) | MemberPayments.tsx → PaymentDocuments.tsx:37-55 | PRESENT | |
| Loading / empty "No payments to show" / error | :193-195 | PRESENT | :215-217 (empty copy "Nothing to pay. You are all settled."). |

### 16g. Inbox tab

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Activity-derived notices + "No notices need your attention" | MemberArea.tsx:154, :191 | PRESENT | "Notices" section (default). |
| Announcements feed (feature `membership.broadcasts`) with paging | MemberNotifications.tsx:10 | BURIED | "Announcements" tab (`?section=announcements`). |
| Personal inbox: unread count, Unread-only, family filter, Mark all read, rows (family, time, title, summary), Open link, Mark read, paging | PersonalInbox.tsx:39-70 | CHANGED | ListLayout: Unread/All tabs, family filter, Mark all read in header, date grouping, "Read message" expander, `Pagination` (assumes 24/page). Same endpoints. |
| Preference centre (feature `notifications.member_preferences`): per family×channel toggle, mandatory events, digest | MemberNotifications.tsx:12 | BURIED | "Preferences" tab (`?section=preferences`). Defect: the new `SettingsRow` label uses a literal "?" separator ("bookings ? Inbox", PreferenceCentre.tsx:29) and repeats the label already printed next to the checkbox. |
| "Active membership required" / loading | :190, :192 | PRESENT | |

### 16h. Account (Profile & card) tab — `/member/account-portal`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| "Manage two-step sign-in" → `/mfa` | MemberArea.tsx:136 | PRESENT | :157 plus header secondary. |
| "Manage your account" → `/member/account` (gated member_accounts + self_service/self_export) | :148 | PRESENT | :169 plus header secondary "Account & security →". |
| Member profile (`MemberProfilePanel`): directory visibility, show attended events, avatar, headline/bio/institution, interests, languages, GitHub, projects, Save profile | :162 → MemberProfilePanel.tsx | BURIED | `?section=profile` (default). Save/Discard bar appears only when dirty. |
| Member card (`MemberCardPanel`): number, active/revoked, print count, printed-name edit + Save name, Preview card (PDF), photo upload/consent, offline save | :162 → MemberCardPanel.tsx:56-113 | BURIED | `?section=card` (TicketCard with QR + issued date added); compact copy on Home. |
| Certifications (`MemberCertifications`, module `machines`) | :155 | BURIED | `?section=certifications`. Defect: meta shows "{type} ? Granted …" — literal "?" instead of "·" (MemberCertifications.tsx:18). |
| Member directory (`MemberDirectory`): list, click to expand profile, hidden count | :162 → MemberDirectory.tsx:60-104 | BURIED | `?section=community` (labelled "Community"); profile opens in a drawer; new name search. |
| Referrals + claimable invitations (`MemberReferrals`: send referral, verify-email hint, claim with application answers) | :167-184 | BURIED | `?section=invitations` ("Invite a friend"/"Invitations"). |

## 17. Member account page — `/m/:slug/member/account`, `/member/account`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| "Back to membership" button | MemberAccountPage.tsx:41 | CHANGED | Header secondary "Profile & card →", user-menu "Member area", sidebar. |
| Session restore / sign-in fallback (`MemberAuthPanel`) | :40 | PRESENT | |
| Loading / bootstrap error | :42-43 | CHANGED | Generic error + Retry. |
| "You have left this makerspace" | :44 | PRESENT | |
| Claim-session notice | :45 | PRESENT | |
| "Account self-service is disabled" | :47 | PRESENT | |
| Profile: display name, first, last, contact phone, Save profile | :48 → MemberAccountProfile.tsx | BURIED | `?section=profile`; Save/Discard appears only when dirty. |
| Sessions and devices: list, current marker, legacy note, Revoke, paging | :48 → MemberAccountSessions.tsx | BURIED | `?section=security` (+ new "Manage two-step sign-in" link). |
| Membership: status, Cancel renewal, Leave makerspace, reason + confirm | :48 → MemberAccountMembership.tsx | BURIED | `?section=membership`; actions are DangerZones. |
| Data export: request, list, download | :49 → MemberAccountExports.tsx | BURIED | `?section=data` ("Your data"). |
| New: member shell (sidebar, Sign out) | — | (new) | |

## 18. Archived payments — `/member/archived`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| 404 → "Page not found" + back | ArchivedPayments.tsx:91-105 | PRESENT | CenteredCard. |
| Unauthenticated → `MemberAuthPanel` | :107-116 | PRESENT | |
| Header eyebrow/h1/explanation | :120-129 | PRESENT | PublicLayout header (Space Works chrome). |
| Loading / error (server message) | :131-142 | CHANGED | Generic error + Retry. |
| Empty "No archived payments" | :143-150 | PRESENT | EmptyState. |
| Per closed makerspace: pending/total chip, payment rows, settle (checkout), receipts | :151-153, :30-80 | PRESENT | |
| "Back to Space Works" | :155-157 | PRESENT | Header primary. |

## 19. Staff sign-in — `/admin`, `/m/:slug/admin`, `/guest-admin` (signed out)

`StaffApp.tsx` is unchanged; it renders `LoginPanel`, `MfaFlow`, `ChangePasswordGate`.

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Badge, eyebrow "Guest admin desk"/"Space Manager desk", h1 "Sign in" | LoginPanel.tsx:60-64 | CHANGED | AuthLayout split screen; eyebrow "Front desk"/"Staff console", h1 "Welcome back." |
| Copy depends on password login switch | :65-69 | PRESENT | |
| Username + password (when password login on) | :70-96 | PRESENT | PasswordInput (show/hide added). |
| Error | :97 | PRESENT | |
| Sign in (pending spinner) | :98-109 | PRESENT | |
| Forgot password? (only when email enabled AND password login) | :110-117 | PRESENT | Beside the password label. |
| Social sign-in (Google / Apple / OIDC) | :119-121 | PRESENT | `social` slot above the form. MFA challenge from social now handled by LoginPanel (`onMfaChallenge`). |
| MFA challenge (`MfaFlow`): enroll QR + manual key, code, recovery codes after enroll, expiry note, Back to sign-in | MfaFlow.tsx (old) | PRESENT | CenteredCard; adds "Use a recovery code instead", copy/download codes, copy key. |
| Change-password gate: current, new, confirm, mismatch, Update, Sign out | ChangePasswordGate.tsx:31-95 | PRESENT | CenteredCard + strength meter. |

## 20. Member sign-in (`MemberAuthPanel`, used by member area, account page, archived payments)

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Public config probe (self-registration, password login switches) | MemberAuthPanel.tsx:38-59 | PRESENT | |
| Sign in / Create account toggle (only when self-serve) | :218-221 | PRESENT | SegmentedControl "Sign in / Create account". |
| "This space does not run self sign-up" | :222-226 | PRESENT | `legal` slot. |
| Sign-up fields: name, phone (optional), email, password | :188-204 | PRESENT | + password strength meter. |
| Email-only mode when password login off | :205-210 | PRESENT | |
| Submit (sign-up → verify notice; login → verification-only or done) | :61-98, :213-217 | PRESENT | |
| Email verification: code, Verify, Resend code | :131-169 | PRESENT | CenteredCard. |
| MFA challenge | :129-130 | PRESENT | |
| Social sign-in (member surface, makerspace slug) | :228-237 | PRESENT | |
| Forgot password | — | (absent in both) | Old member sign-in never had one either; worth adding (see Restore list). |

## 21. Reset password — `/reset-password`

| Capability | Old file:line | Status | New location |
|---|---|---|---|
| OTP flow: request (email) → confirm (6-digit code, new + confirm password) → success; "unavailable" state | PasswordRecoveryFlow.tsx:74-166 | PRESENT | CenteredCard per step. |
| Acknowledgement text + "delivery may take a few minutes" | :118-121 | PRESENT | |
| Request another code with cooldown | :147-154 | PRESENT | Card escape action. |
| Back to sign in / Go to sign in | :86, :111, :162 | PRESENT | |
| Legacy `uid`+`token` link form | LegacyPasswordResetForm.tsx:30-59 | PRESENT | CenteredCard. |

## 22. MFA account page — `/mfa`

| Capability | Old file:line | Status | New location |
|---|---|---|---|
| Restore session; "Sign in to manage…" notice | MfaAccountPage.tsx:15, :28 | PRESENT | |
| Status (enrolled / required) | :29 | PRESENT | + status pill. |
| Confirm current password | :30-31 | PRESENT | |
| Enroll authenticator → MfaFlow | :35, :24 | PRESENT | |
| Regenerate recovery codes | :33 | PRESENT | |
| Disable MFA (not when required) | :34 | CHANGED | DangerZone + confirm dialog (safer). |
| Show new recovery codes | :37 | PRESENT | + Copy all / Download .txt. |
| Staff sign-in / Member sign-in links | :39 | PRESENT | |

## 23. Staff invitation accept — `/staff-invitations/accept`

| Capability | Old file:line | Status | New location |
|---|---|---|---|
| h1, explanation | StaffInvitationAcceptPage.tsx:15-17 | PRESENT | CenteredCard (explanation moved to footer). |
| Password | :18-19 | PRESENT | PasswordInput. |
| MFA code (optional) | :20-21 | BURIED | Inside a "My account uses two-step sign-in" disclosure. |
| Accept invitation (disabled without token), error | :22-23 | PRESENT | |
| Success detail + "Sign in with your email" | :16 | PRESENT | |

## 24. Kiosk station — `/m/:slug/kiosk/:stationToken`, `/kiosk/:uuid`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Station PIN entry (8 digits, numeric) + Unlock + invalid-PIN error | KioskStationPage.tsx:73-76 | CHANGED | `KioskPin` digit boxes + on-screen keypad (Clear/Delete); same validation. |
| "Reconnect to unlock and load this handover" when offline and locked | :73 | PRESENT | Callout in work mode. |
| Station name, makerspace · kind subtitle | :72, :78 | PRESENT | KioskLayout context. |
| Start operator shift (lease) + error | :79, :62-66 | PRESENT | "ready" mode primary; error shown as retryable state. |
| Replay correction when `?recovery=` (`KioskReplayCorrection`) | :79 | PRESENT | work panel. |
| Offline/queue mode (`KioskOfflineHandover`) | :79-82 | PRESENT | work panel. |
| Online QR lookup (`KioskOnlineScanner`) | :83 | CHANGED | `ScanWorkbench` (typed lookup **plus** camera scan, result panel with "Next"). |
| Online handover (`KioskOnlineHandover`): request number load, details, assign box, issue/return with photo, box scan, remark, kit checklist | :84-85 | CHANGED | Assign box and issue/return are kiosk `FlowLayout`s with Cancel; success is a ResultPanel; double-submit guarded (improvement). |
| "Continue with encrypted queue" | :87 | PRESENT | |
| Full screen | :90 | PRESENT | header action. |
| Lock station (with pending-work confirmation) | :91-94, :99-103 | PRESENT | header action + ConfirmDialog "Discard handovers and lock?". |
| Idle reset (lease/session expiry) | :48-53 | CHANGED | Adds a 10-second countdown callout with "Keep working" (improvement). |
| Storage error notice | :98 | PRESENT | |
| New: connection pill (Online/Offline · n queued) | — | (new) | |

### 24a. Offline handover, queue status, replay recovery

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Loaded handover select, operation select (permitted ops), box/return QR, asset QRs, evidence photo file + camera, remark, kit checklist, Queue handover | KioskOfflineHandover.tsx:62-82 | PRESENT | Inside kiosk FlowLayout; warning callout with "Retry now" (new). |
| Queue status: pending/failed counts, per-command sequence/kind/status/failure, guidance, "Review failed handover online", Retry queued work, Acknowledge completion | KioskQueueStatus.tsx:8-26 | PRESENT | DataTable. |
| Replay correction: capture fresh correction, check corrective replay, resolve, acknowledge no change | KioskReplayCorrection.tsx | PRESENT | |
| Staff replay recovery panel: status filter, list, details (failure, guidance, station, operator, retention, evidence preview), acknowledge, correct online (station URL), paging | KioskReplayRecoveryPanel.tsx:15-44, KioskReplayDetail.tsx, KioskReplayResolution.tsx | CHANGED | Collapsible section (collapsed when empty), rows with Resolved/Unresolved pill and "Review" button; same actions. |

## 25. Public desk kiosk — `/kiosk/:slug` (central)

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Header: badge, eyebrow "Kiosk", h1 "Public desk", theme toggle, "Catalog" link | PublicDeskKioskPage.tsx:13-27 | CHANGED | KioskLayout header ("Public desk"), "Open full catalogue" action; theme toggle moved into the side panel. |
| Full public catalogue incl. its own header (makerspace brand/logo, map, stats link, listed count, module nav, staff login) and footer (support contact) | :28 → PublicInventoryPage | MISSING (header/footer) | `PublicInventoryPage embedded` renders only body + request panel: **no makerspace name or logo appears anywhere on the desk**, no map link, no Events/Machines/Bookings/Print links, no support contact. |
| Catalogue body (browse, search, cards, quick view, request panel incl. Scan a tool) | via PublicInventoryPage | CHANGED | Squeezed into the left "capture" column of the two-column kiosk stage, with the request panel stacked **under** the product grid; the right column is a static "Find your next tool" card. |
| New: connection pill | — | (new) | |

## 26. Scanner — `/scanner` (signed-in staff)

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Badge, eyebrow, h1 "QR resolution", theme toggle | ScannerPage.tsx:28-36 | CHANGED | KioskLayout "Scanner"; theme toggle in side panel. |
| QR payload input + Resolve (`/admin/qr/resolve`) | :37-52 | PRESENT | ScanWorkbench (adds camera scan). |
| Error message | :53-55 | PRESENT | Result panel "Couldn't resolve this label" + Try again. |
| Raw target JSON | :58-60 | CHANGED | Key/value card (all fields except `type`), status as pill. |
| Allowed actions chips | :61-67 | PRESENT | Pills + "No actions available" note. |

## 27. Event check-in station — `/m/:slug/event-check-in/:stationToken`

| Capability | Old file:line | Status | New location / what's needed |
|---|---|---|---|
| Badge, h1 "Event check-in station" | EventCheckInStationPage.tsx:37-39 | CHANGED | KioskLayout. |
| 8-digit PIN + Unlock + error | :40-45 | CHANGED | KioskPin keypad; now disabled while offline with a reason. |
| Offline check-in operator (auto roster download, search, check in, sync) | :46 | PRESENT | work capture column. |
| "Wipe data and lock station" | :47 | CHANGED | "Lock station" header action; asks for confirmation when unsynced check-ins exist (improvement); wipe failure now reported. |
| New: connection pill, side "Welcome them in" guidance | — | (new) | |

---

## 28. Logo presence per page

"SW logo" = `SpaceWorksLogo` / `SpaceWorksBadge` (old badge = 22px mark + "Space Works" wordmark;
new badge = 48px symbol). "Tenant brand" = `MakerspaceBrand` (tenant logo, else name; new adds an
avatar initial when no logo). Note the old `SiteFooter` had **no** logo; the new `SiteFooter` and the
PublicLayout footer both carry the 48px symbol.

| Page | Old: SW logo? | Old: tenant brand? | New: SW logo? | New: tenant brand? |
|---|---|---|---|---|
| Landing `/` | Yes — 36px mark + wordmark, header | Yes — per space card | Yes — horizontal 288 / stacked 180 header, symbol footer | Yes — per card |
| About | Yes — 36px mark + wordmark | No | Yes — horizontal/stacked header + footer symbol | No |
| 404 / route fallback | No | No | Yes — stacked 180 (CenteredCard) | No |
| App "Loading site" / "Site unavailable" | Yes — badge | No | Yes — stacked 180 | No |
| Public catalogue | Yes — badge in header | Yes — xl, as h1 | Footer symbol only | Yes — header bar (normal size) |
| Item page | No (footer had none) | No | Footer symbol | Yes — header bar |
| Self-checkout | Yes — badge | Yes — lg, h1 | SiteFooter symbol only | Yes — inside the work card |
| Events list | Yes — badge | Yes — lg | Footer symbol | Yes |
| Event detail | No (no header/footer at all) | No | Footer symbol; stacked on 404 card | Yes in single mode; **central mode shows the raw slug, no logo** |
| Event feedback | No | No | Footer symbol; stacked on unavailable/thanks cards | Yes |
| Machines | Yes — badge | Yes — lg | Footer symbol | Yes |
| Bookings | Yes — badge | Yes — lg | Footer symbol | Yes |
| Print request | Yes — badge | Yes — lg, h1 | Footer symbol | Yes |
| Stats | Yes — badge | Yes — lg, h1 | Footer symbol | Yes |
| Organization page | Yes — badge only when org not loaded | Yes — org logo/name | Full logo while loading; footer symbol | Yes — org |
| Org invitation redeem | Yes — badge | No | Yes — stacked 180 | No |
| Member area (all tabs) | No | No | Yes — sidebar stacked 180 + mobile top-bar symbol | No — workspace card shows name + initial avatar, not the tenant logo |
| Member area, non-member overview | No | No | Sidebar logo **and** nested PublicLayout footer symbol | Yes (nested header) |
| Member sign-in (`MemberAuthPanel`) | Yes — badge | No | Yes — stacked 180 + 240 in brand aside | Yes when `tenantBrand` passed (member area, account page; not archived payments) |
| Member email verification | Yes — badge | No | Yes — stacked 180 | No |
| Claim session | No | No | No | No |
| Member account page | No | No | Yes — sidebar | No |
| Archived payments | No | No | Yes — horizontal header + footer symbol | No |
| Staff sign-in (LoginPanel) | Yes — badge | No | Yes — stacked 180 + 240 aside | No |
| Staff restoring / access denied / picker (StaffApp) | Yes — badge | No | Yes — badge (StaffApp unchanged; picker keeps badge) | No |
| Change-password gate | Yes — badge | No | Yes — stacked 180 | No |
| MFA challenge (MfaFlow) | No | No | Yes — stacked 180 | No |
| MFA account page | No | No | Yes — stacked 180 | No |
| Reset password (OTP + legacy) | Yes — badge | No | Yes — stacked 180 | No |
| Staff invitation accept | No | No | Yes — stacked 180 | No |
| Kiosk station | Yes — badge | No | Yes — symbol 48 | No (makerspace name only as text subtitle) |
| Public desk kiosk | Yes — badge, plus the catalogue's badge and tenant brand | Yes — via embedded catalogue header | Yes — symbol 48 | **No — tenant brand lost** |
| Scanner | Yes — badge | No | Yes — symbol 48 | No |
| Event check-in station | Yes — badge | No | Yes — symbol 48 | No |

---

## 29. Counts

| Status | Rows |
|---|---|
| PRESENT | 258 |
| BURIED | 22 |
| CHANGED | 84 (some carry new defects; all defects are listed in §30 S3) |
| MISSING | 9 |

Counted mechanically from the per-page tables in §1–§27 (status-key rows excluded). Rows marked
"(new)" and "(absent in both)" are not counted.

The 9 MISSING rows: Landing "Live" tile; Landing "Standard public portal" badge; Events-list cover
image; Events-list description; Events-list capacity; Event-detail capacity/availability (same gap
as the list one, seen from the detail page); Org-page event image; Member Bookings-tab activity
section; Public desk tenant header/footer. Of these, only the last four carry real user value; the
two landing tiles were decorative.

---

## 30. Restore list (severity-ordered)

Severity: **S1** = user-visible loss of identity or of a task path; **S2** = information a user relied
on is gone or harder to reach; **S3** = defect / polish. Yuyu refs are from
`research/ux-yuyu-spec.md`.

### S1

1. **Public desk kiosk has no makerspace identity or programme links.**
   Old: `PublicDeskKioskPage.tsx:13-28` rendered the whole `PublicInventoryPage`, whose header
   (`publicInventory/PublicInventoryHeader.tsx:27-90`) carried MakerspaceBrand, map, stats, module
   links and staff login, and whose `SiteFooter` carried SupportContact.
   New: `PublicInventoryPage embedded` (PublicInventoryPage.tsx:97) drops all of it.
   Fix: pass `context.identity` (tenant logo) and `title = display name` into `KioskLayout`
   (KioskLayout.tsx:10, 28) by reading `useTenantBootstrap(slug)`; render the request panel in the
   kiosk `panel` column instead of under the grid, and the catalogue body alone in `capture`
   (Yuyu Y28 two-column kiosk: big work area left, result/action card right). Put the module links
   as large kiosk `headerActions`.

2. **Event detail page in central mode shows the raw slug as the brand and an empty nav.**
   `PublicEventDetailPage.tsx:32,38` passes `undefined` bootstrap to `publicPageChrome` outside
   single mode. Fix: `const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central")`
   (as in PublicEventsPage.tsx:41-42) and pass `bootstrap` + `display_name`; also apply
   `useTenantBranding`. Yuyu Y18/Y19 (public event page keeps tenant header and accent colour).

3. **Public catalogue on phones: "Scan a tool" and the request form are only reachable through the
   "Review request" bottom bar.** `PublicActionCard.tsx:27-40` + PublicInventoryPage.tsx:100.
   The old page stacked the panel below the list, always visible. Fix: give the mobile bar a second
   action "Scan a tool" that opens the sheet with `activeTab="scan"` (lift `activeTab` into
   PublicInventoryPage), and label the bar "Request · N items" even when N = 0. Yuyu Y18 sticky
   action card → mobile sheet pattern, with the primary verb visible.

### S2

4. **Events list lost cover image, description and capacity; inline registration became a page hop.**
   Old `PublicEventsPage.tsx:132-145`. New :105-111 (ListRow).
   Fix: switch the list to event cards (cover thumbnail via ListRow `identity: { kind: "image" }`
   when `image_url`, else the date chip), add a 2-line description clamp to `meta`, and show
   "Capacity n / Unlimited" next to price. Add capacity + availability to the detail action-card
   `summary` (PublicEventDetailPage.tsx:48). Keep the link-to-detail registration (it matches
   Yuyu Y18/Y23), but show the cutoff time on the list's closed pill
   (old :140 `effective_registration_cutoff_at`).

5. **Event `status` badge dropped from the events list** (old `PublicEventsPage.tsx:137`
   `<StatusBadge status={item.status} />`). A cancelled/postponed event now reads as "Available".
   Fix: when `item.status !== "published"` render `StatusPill` with the status in `right`, ahead of
   the availability pill.

6. **Member Bookings tab no longer renders the activity "Bookings" section**
   (old MemberArea.tsx:157 → MemberActivity.tsx:152). New MemberArea.tsx:178 excludes `bookings`.
   Decide: either add `|| activeTab === "bookings"` to that condition, or delete the bookings block
   from `MemberActivityPanel` and keep `MyBookings` as the single source. Recommended: drop the
   duplicate on purpose and record it, because `MyBookings` already has Upcoming/Past, reschedule
   and cancel (Yuyu Y2 single list with tabs).

7. **Presence start/end button moved into the page header and disappears on list tabs.**
   Old MemberArea.tsx:152 (button inside the Presence card). New MemberArea.tsx:155 header primary,
   overridden by `browse` in MemberScreenLayout.tsx:45. Fix: keep the header primary on Home, and
   also put an inline "Start 2-hour presence / End presence" button back into the Presence card
   (MemberArea.tsx:173) so it survives on every layout. Yuyu Y8 (check-in action lives with its
   status).

8. **Errors lost their specific reasons** on events (old PublicEventsPage.tsx:119-121), machines
   (PublicMachinesPage.tsx:104-106), bookings (PublicBookingsPage.tsx:86-91), stats
   (PublicStatsPage.tsx:103-112), feedback (PublicEventFeedbackPage.tsx:59), print status
   (PublicPrintRequestParts.tsx StatusResult), org page (:48-51), archived payments (:131-142).
   Retry is now offered for 400/404 where it cannot work. Fix: one helper
   `publicErrorState(error, noun)` that maps 429 → "Please slow down", 400 → "{noun} isn't turned on
   here" (no retry), 404 → "We couldn't find this makerspace" (no retry), else generic + retry, used
   by every `state=` above.

9. **Machines: type icon and maintenance vs offline distinction lost.**
   Old PublicMachinesPage.tsx:110 (`icon={group.icon}`) and :121 (`StatusBadge` with 5 states).
   New :98, :104. Fix: render the group toggle with the type icon, and map `maintenance` →
   "Maintenance", `offline` → "Offline" (both warn tone) instead of "Down".

10. **Organization page lost event images** (old PublicOrganizationPage.tsx:86). Fix: ListRow
    `identity: { kind: "image", src: event.image_url }` when present (new
    PublicOrganizationPage.tsx:33).

11. **Landing header lost "Staff login"; About/landing footers lost the License link.**
    Old LandingPage.tsx:66, AboutPage.tsx:21-23, SiteFooter License. New footers
    (LandingPage.tsx:37, AboutPage.tsx:9) list only About / Staff sign-in. Fix: add
    `{ label: "License", href: ".../LICENSE", external: true }` to both footers (as
    PublicPageChrome.tsx:27 already does). Keeping "Staff sign-in" in the footer is fine (Yuyu Y11
    keeps staff entry secondary).

12. **Member area theme toggle buried in the user menu** (old MemberArea.tsx:132). Acceptable for the
    shell pattern; optionally surface it in the mobile top bar. Low.

### S3 — defects and polish introduced by the revamp

13. `MemberCertifications.tsx:18` — `{row.machine_type_name} ? Granted …` renders a literal "?".
    Replace with ` · `.
14. `PreferenceCentre.tsx:29` — `SettingsRow` label `${feature} ? ${channel}` renders a literal "?",
    and duplicates the text already beside the checkbox. Use ` · ` or drop the outer label.
15. `MemberActivity.tsx:118` — "Loading your ticket?" should be "Loading your ticket…"; the
    `TicketCard organisation` there and in `EventRegistrationForm.tsx:77` is hard-coded
    "Space Works" — pass the makerspace name.
16. Self-checkout result replaces the form (PublicSelfCheckoutPage.tsx:122-123); old let the user
    scan the next tool immediately (:245-249). Consider auto-reset after a few seconds or keep the
    work panel under the result (Yuyu Y28 "big result card + keep scanning").
17. Non-member overview renders a full PublicLayout (second header + footer) inside the member shell
    (MemberScreenLayout.tsx:21-25). Use `DashboardLayout`/`CenteredCardLayout` content instead, or
    render the public join page outside `AppShell` for signed-out visitors.
18. Member shell user menu shows "Your account" and "Sign out" to signed-out visitors
    (MemberArea.tsx:150-151). Show "Sign in" instead when `unauthenticated`.
19. Workspace card in the member shell shows an initial avatar, not the tenant logo
    (MemberArea.tsx:149). Pass `{ kind: "image", src: bootstrap.makerspace.logo_url }` when set.
20. `publicInventory/PublicInventoryHeader.tsx` is dead code (no importers) — delete or reuse.
21. Catalogue categories are now one horizontal chip row (PublicInventoryParts.tsx:44-54); with
    many categories most are off-screen and the counts are hard to scan. Consider Yuyu Y20 filter
    pills with a "More" overflow, or restore a left column at `xl`.
22. Event detail registration for events with tickets/custom forms is behind a modal
    (EventRegistrationEntry.tsx:13-17); Yuyu Y23 shows the register form inline inside the sticky
    card. Consider rendering the form inline in the action card and reserving the modal for phones.
23. Org page and member inbox `Pagination` assume 24 per page (PublicOrganizationPage.tsx:39,
    PersonalInbox.tsx `pageSize: 24`); old used `next`/`previous`. Safe while the DRF page size stays
    24 (project convention), but drive `totalPages` from the API if it ever changes.
24. Feedback "unavailable" copy dropped the reasons ("survey closed, event not ended, or link
    invalid"; old PublicEventFeedbackPage.tsx:59). Restore the sentence in the card body.
