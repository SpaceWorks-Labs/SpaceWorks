# Final parity audit — public, auth and kiosk surfaces

Status: read-only research, written 2026-10-16 against HEAD `7e1e7b2d` (public files identical to `b348ee18`).
Old = `d3e5ed29` (`git show d3e5ed29:frontend/src/<path>`). New = working tree. Paths below are relative to
`frontend/src/` unless stated. No app code was changed. `npx vitest run` over inventory, kiosk, organizations,
auth, bookings, printing and stats: 42 files, 137 tests, all pass.

## Summary

**Capability rows: 138 PRESENT / 6 BURIED / 33 CHANGED / 3 MISSING** (180 rows; the 3 MISSING are the two decorative landing tiles
and the borrow-request status lookup, a feature that was already dead code in the old tree; no capability is unreachable).
**Earlier restore list (`parity-public-member.md` §30), public half: 13 verified fixed, 3 still open (all P2), 8 are
member-area items owned by the member audit.** Route table (`AppRoutes.tsx`) and every gate (`request_workflow`,
`inventory.self_checkout`, `inventory.notify_when_back`, `public_stats_enabled`, `events`/`machines`/`bookings`/
`printing` modules, `machines.public_detail`, `machines.structured_intake`, `machines.material_catalogue`, the auth
`/config` switches) are unchanged from old. No file in scope was deleted except the dead `PublicInventoryHeader.tsx`.

New findings: **0 P0, 2 P1, 8 P2.**

## Restore list (P0 to P2)

### P0

None. Every old capability in scope is still mounted and reachable at all widths; no destructive action lost a
confirmation; no gate is looser or stricter.

### P1

**P1-1. Phone request sheet discards the draft and the account-less reference token whenever it closes.**
- Old: `PublicInventoryPage.tsx:182-190` rendered `PublicRequestPanel` inline and permanently, so purpose text,
  contact fields and the "Save this reference" banner (`BorrowRequestCard.tsx:164-185`) survived scrolling.
- New: below 768px `PublicActionCard.tsx:92-103` renders the panel only inside `<Modal>`, and `Modal.tsx:91`
  (`if (!open) return null`) unmounts it. The state lives in the panel (`PublicRequestPanel.tsx:49-59`:
  `requestedFor`, `contactName/Email/Phone`, `submitted`, `publicToken`), so it is lost when the sheet closes. A
  backdrop tap closes it (`Modal.tsx:99-103`). Consequences: a requester who closes the sheet to add one more
  item loses what they typed; an account-less requester who closes the success sheet loses the public token, which
  the copy itself calls "their only route back" (there is no status-lookup page, see P2-8).
- Fix: lift those seven `useState`s (and `activeTab`, already lifted) from `PublicRequestPanel.tsx` into
  `PublicInventoryPage.tsx` and pass them as props; or keep the panel mounted and hide the sheet with `hidden`
  instead of unmounting. Smaller alternative: persist `publicToken` to `localStorage` the way the print page
  does (`PublicPrintRequestPage.tsx:49-51`). Same pattern, lower stakes: `PublicBookingForm` in the booking sheet
  (`PublicBookingsPage.tsx:55`) and `NotifyWhenBack` in the item sheet (`PublicItemPage.tsx:207`) lose their typed
  values and success message on close.

**P1-2. Scan lookups do not clear or re-focus, so keyboard-wedge scans stack up (kiosk station and `/scanner`).**
- Old: `kiosk/KioskOnlineScanner.tsx:20` cleared the field after a successful lookup (`setPayload("")`).
- New: `KioskOnlineScanner.tsx:26-30` delegates to `components/ui/ScanWorkbench.tsx`, whose input value
  (`:32`, submit `:47`) is never cleared, and whose input is `disabled={blocked}` while the lookup runs (`:49`),
  which drops focus and nothing restores it. A USB/Bluetooth scanner that types the code plus Enter appends the
  second code to the first, and the focus is gone after the first lookup. The "Next" button
  (`KioskOnlineScanner.tsx:30`) only resets the result. The same component serves `/scanner`
  (`ScannerPage.tsx:20`), where the old page never cleared either (so only the focus loss is new there).
- Why it matters: the kiosk is a scan-all-day operator flow ("Scan or type a QR code"); camera scanning is
  unaffected.
- Fix: in `ScanWorkbench.tsx:47` call `setValue("")` after `onFind(...)` (the caller already shows the result),
  hold an input ref and re-focus it when `findPending` returns to false and when `result` is dismissed.

### P2

**P2-1. Theme toggle, map link and the whole nav sit behind the Menu button below 1024px.**
`PublicHeader.tsx:103,111,139-148`. Old pages showed the theme toggle and module links in the header at every
width (`PublicInventoryHeader.tsx:49-86`). Still reachable (two taps), and the pattern is deliberate, but the
theme toggle is a frequently used control on phones. Fix if wanted: render `liveStatus` inline next to the account
action below 1024px and keep only the nav links in the menu.

**P2-2. Public event detail on phones: bar label does not match the action, and complex events need three taps.**
`PublicEventDetailPage.tsx:67` fixes the bar label to "Register" even for "Apply to join" / "Join waitlist"
(card title `:56`); calendar and share are only inside the sheet; and for events with a custom form, tickets, promo
codes or an invite audience `EventRegistrationEntry.tsx:181-185` adds a second "Register" button that opens a
second modal on top of the sheet. Fix: pass the same label the card uses (`EventRegistrationEntry.tsx:176`) to
`mobileBar.label`, and render the form inline in the sheet on phones (modal only at tablet+).

**P2-3. Staff invitation: the MFA code field is hidden inside a disclosure** (`auth/StaffInvitationAcceptPage.tsx:28-32`,
old `:20-21` always visible). A user whose account has MFA sees only the server error. Fix: `open={Boolean(accept.error)}`
on the `<details>` (or open it when the error mentions the code).

**P2-4. Self-checkout result replaces the work panel** (earlier #16, still open): `PublicSelfCheckoutPage.tsx:122-123`;
old `:245-249` let the borrower scan the next tool at once. Now one extra tap ("Borrow another"/"Return another").

**P2-5. Complex event registration is a modal on desktop** (earlier #22, still open): `EventRegistrationEntry.tsx:181-185`.
Yuyu Y23 puts the form inline in the sticky card.

**P2-6. Org page assumes 24 rows per page** (earlier #23, still open): `organizations/PublicOrganizationPage.tsx:42`
(`pageSize={24}`, `Math.ceil(count / 24)`); old followed the API's `next`/`previous`. Safe while DRF stays at 24.

**P2-7. "Unavailable" is grey on the card and the quick view** (`AvailabilityBadge.tsx:7-9`: success / warn / neutral).
Old quick view and item page used a red chip; the card was neutral. Consider `danger` for "Unavailable" so the
disabled "+" has a visible reason.

**P2-8. No borrow-request status lookup exists, in old or new (not a regression).** `inventory/api.ts:100
fetchRequestStatus` and `inventory/RequestSummary.tsx` are exported but imported by nothing in either tree, and
`BorrowRequestCard.tsx:181` still tells signed-in requesters "Check this page with your email to follow the
request". An account-less requester has only their token and nowhere to enter it. Decide whether to build a
`/m/:slug/requests?token=` page or drop the copy.
Also not regressions, noted for completeness: the member sign-in has no "Forgot password?" link (`members/MemberAuthPanel.tsx`
both versions), and `/reset-password` "Back to sign in" points to `/admin` (staff) even for members;
`staff/HandoverDialogs.tsx` and `staff/BookableSpaceMachineType.tsx` are unimported in both trees (dead).

### Earlier restore-list verification (`parity-public-member.md` §30, public half)

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Public desk has no tenant identity / programme links | FIXED | `kiosk/PublicDeskKioskPage.tsx:29-44` (logo, name, programme nav, full-catalogue link, request panel in right column, support + map + theme + staff link) |
| 2 | Central event detail shows raw slug | FIXED | `inventory/PublicEventDetailPage.tsx:28-30,48` loads bootstrap |
| 3 | Phone: Scan a tool only via Review request | FIXED | `PublicInventoryPage.tsx:107-108` + `PublicActionCard.tsx:76,96` (second "Scan a tool" verb; bar shows "Request · N items") |
| 4 | Events list lost cover, description, capacity, cutoff | FIXED | `inventory/PublicEventCard.tsx:140,154,157,129-131` |
| 5 | Event `status` badge dropped | FIXED | `PublicEventCard.tsx:149` (`StatusBadge status domain="event"`) |
| 8 | Errors lost their reasons (public pages) | FIXED | `inventory/publicErrorState.ts:196-202` used by events, event detail, machines, bookings, stats; org page `:29-30`; print `PublicPrintRequestParts.tsx:126`; feedback `PublicEventFeedbackPage.tsx:59` |
| 9 | Machines: type icon, maintenance vs offline | FIXED | `PublicMachinesPage.tsx:38,101,108` |
| 10 | Org page lost event images | FIXED | `PublicOrganizationPage.tsx:37` |
| 11 | Landing/About footers lost License | FIXED | `LandingPage.tsx:36`, `AboutPage.tsx:20` (Staff sign-in stays footer-only by design) |
| 15 | Hard-coded "Space Works" on event ticket (public half) | FIXED | `EventRegistrationEntry.tsx:180` passes `organisation` |
| 20 | `PublicInventoryHeader` dead code | FIXED | file deleted |
| 21 | Categories one scrolling chip row | FIXED | `PublicInventoryParts.tsx:55-59` (chips wrap, headings back) |
| 24 | Feedback "unavailable" lost its reasons | FIXED | `PublicEventFeedbackPage.tsx:59` |
| 16 | Self-checkout result replaces form | OPEN (P2-4) | |
| 22 | Event registration modal | OPEN (P2-5) | |
| 23 | Org page assumes 24 per page | OPEN (P2-6) | |
| 6, 7, 12-14, 15 (member part), 17-19 | Member-area items | not audited here | member audit |

## Capability table

Status key: PRESENT same capability and reachable where expected; BURIED needs extra taps for a used control;
CHANGED behaviour or copy differs; MISSING gone. "x:N" = line N of file x (old column is `d3e5ed29`).

### Landing `/` (central) and About `/about`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Redirect to the only makerspace when exactly one exists | LandingPage.tsx:49-51 | LandingPage.tsx:26 | PRESENT | `Navigate replace` kept |
| Search by name / code / slug / location, token AND match | :14-47,103-111 | LandingPage.tsx:12-24, LandingHero.tsx:20 | PRESENT | same normaliser and index |
| Clear search | :113 | LandingHero.tsx:23, LandingPage.tsx:35,40 | PRESENT | button and empty-state action |
| Live "x / n spaces" counter (aria-live) | :114-116 | LandingHero.tsx:22 | PRESENT | |
| Loading state | :120 | LandingPage.tsx:38 (`SpaceCardSkeletons`) | PRESENT | |
| Directory load error | :121-126 | LandingPage.tsx:33 | CHANGED | adds Retry |
| Empty "no public spaces" / "no match" | :127-138 | LandingPage.tsx:29,35,40 | PRESENT | |
| Space card: cover, Public chip, brand, map link, public code, "Open catalogue" full-card link | :143-164 | landing/SpaceCard.tsx:56-72 | PRESENT | no-cover fallback is a brand tile with initial |
| Header "Staff login" button | :66 | LandingPage.tsx:36 (footer "Staff sign-in") | CHANGED | footer link only; header now "Sign in" to `/member` |
| Theme toggle | :65 | LandingPage.tsx:32 | PRESENT | icon; inside Menu below 1024px (P2-1) |
| About nav / footer About + License | SiteFooter.tsx:17-27 | LandingPage.tsx:32,36 | PRESENT | License restored |
| "Live" and "Standard public portal" tiles | :85-88,99-101 | none | MISSING | decorative, replaced by the hero |
| "Shared equipment portal" tagline | :61 | none | CHANGED | hero copy replaces it |
| About: three paragraphs, AGPL link | AboutPage.tsx:30-56 | AboutPage.tsx:21-25 | PRESENT | copy shortened |
| About: Browse spaces, Staff login | :59-66 | AboutPage.tsx:12,18,27-28 | PRESENT | |
| About footer License | SiteFooter | AboutPage.tsx:20 | PRESENT | |
| Single-tenant `/` home choice by `publicHome` | AppRoutes.tsx:50-56 | AppRoutes.tsx:57-62 | PRESENT | |
| Unknown tenant / empty tenant / 404 / site unavailable | AppRoutes.tsx:37-57, App.tsx:27-50 | AppRoutes.tsx:33-39,50-56, App.tsx:26-33 | CHANGED | Retry added, copy reworded |

### Public chrome (header, footer, nav, theme)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Brand links home | PublicInventoryHeader.tsx:34-40 | PublicHeader.tsx:129-134 | PRESENT | |
| Nav: Request a 3D print (printing), Events, Machines, Book a space | Header:66-85 | PublicPageChrome.tsx:124-128 | PRESENT | same module gates; nav now on every public page; in Menu below 1024px (P2-1) |
| Stats link (`public_stats_enabled`) | Header:51-55 | PublicPageChrome.tsx:129 | PRESENT | |
| Map / location link | Header:44-47 | PublicPageChrome.tsx:140 | PRESENT | in Menu below 1024px |
| Theme toggle | Header:56 | PublicPageChrome.tsx:140 | BURIED | Menu below 1024px (P2-1) |
| Staff login | Header:57-59 | PublicPageChrome.tsx:144 (footer) | CHANGED | footer only, visible at every width |
| Sign in / member entry | none | PublicHeader.tsx:144, PublicPageChrome.tsx:139 | PRESENT | new |
| Support email and URL | SiteFooter.tsx + SupportContact.tsx | PublicPageChrome.tsx:130-136 | PRESENT | same validation regexes |
| About / License in footer | SiteFooter.tsx:17-27 | PublicPageChrome.tsx:142-143 | PRESENT | |
| Space Works badge | Header:62 | PublicLayout.tsx:48-50 (footer) | CHANGED | footer symbol |

### Catalogue `/m/:slug` (and `/`)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Page metadata | PublicInventoryPage.tsx:80 | PublicInventoryPage.tsx:103 | PRESENT | skipped when embedded (desk) |
| Listed-item count | Header:63-65 | PublicInventoryPage.tsx:106 | PRESENT | subtitle |
| Browse: All items, Popular, Most used | PublicInventoryParts.tsx:76-110 | PublicInventoryParts.tsx:47-49,57 | PRESENT | |
| Categories with counts | :112-141 | PublicInventoryParts.tsx:51,58 | PRESENT | wrapping chips |
| Search, Search button, Clear | :98-124 | PublicInventoryPage.tsx:85-89 | PRESENT | |
| Loading / error / empty | :127-135 | PublicInventoryPage.tsx:81-82,90 | CHANGED | generic error copy + Retry; empty gains Clear search |
| Pagination with count | :152-177 | PublicInventoryPage.tsx:96 | CHANGED | shared `Pagination`, hidden when one page |
| Product card: image, availability, name link, ID, description, category | ProductCard.tsx | ProductCard.tsx:30-73 | PRESENT | |
| Quantity stepper (`-`, count, `+`, disabled when Unavailable) | ProductCard.tsx:102-122 | ProductCard.tsx:76-98 | PRESENT | |
| Availability labels (Available n / Limited n / Unavailable) | ProductCard.tsx:17-40 | AvailabilityBadge.tsx:5-9 | CHANGED | "n available"; Unavailable now neutral (P2-7) |
| Quick view (image, ID, name, availability, tracking, category, description, Close) | ProductQuickViewModal.tsx | ProductQuickViewModal.tsx:20-37 | PRESENT | drawer |
| Request panel: unavailable card when `request_workflow` off | PublicRequestPanel.tsx:163-171 | PublicRequestPanel.tsx:151-160 | PRESENT | |
| Request panel: Borrow request / Scan a tool switch | :196-218 | PublicRequestPanel.tsx:185 | PRESENT | |
| Request panel placement | PublicInventoryPage.tsx:182-190 | PublicActionCard.tsx:88-105 | CHANGED | inline from 768px (sticky from xl); sheet below 768px (P1-1) |
| Selected items, count badge, Clear selection | BorrowRequestCard.tsx:57-92 | BorrowRequestCard.tsx:56-88 | PRESENT | |
| Account-less contact fields (`request_access=anyone` + session probe) | :97-135, Panel:65-79 | BorrowRequestCard.tsx:91-130, PublicRequestPanel.tsx:65-79 | PRESENT | |
| Honeypot `website` | :137-148 | BorrowRequestCard.tsx:131-143 | PRESENT | |
| Request purpose, Submit, idempotency key | :150-168, Panel:79-123 | BorrowRequestCard.tsx:144-162, PublicRequestPanel.tsx:85-129 | PRESENT | |
| Submit success banner and account-less reference token | :170-195 | BorrowRequestCard.tsx:164-185 | CHANGED | on phones the sheet closing discards it (P1-1) |
| Phone: reach Borrow and Scan | n/a | PublicInventoryPage.tsx:107-108, PublicActionCard.tsx:93-99 | PRESENT | bar "Request · N items" + "Scan a tool" |
| Request status lookup by token | none | none | MISSING | dead `fetchRequestStatus`/`RequestSummary` in both trees (P2-8); not a regression |

### Scan a tool panel and evidence upload (catalogue)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Check out / Return switch | PublicToolScanPanel.tsx | PublicToolScanPanel.tsx:121 | PRESENT | |
| Scan QR with camera, Scanned OK, Clear scan | :95-111 | :134-150 | PRESENT | |
| Issue photo upload (file + camera) | PublicEvidenceUpload.tsx:57-83 | PublicEvidenceUpload.tsx:36-79 | PRESENT | |
| Check out (`publicToolCheckout`) | :45-56 | :64-75 | PRESENT | |
| Return: photo, condition notes, Report a problem + note, Return | :57-183 | :76-118,185-205 | PRESENT | |
| Disabled-reason line ("Add a photo…") | n/a | :95-99,189 | PRESENT | new |
| Loan result with public token | :15-33 | :32-46 | PRESENT | |

### Item page `/m/:slug/items/:itemId`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Metadata, image, name, availability, category, description | PublicItemPage.tsx:45-59 | PublicItemPage.tsx:199-206 | PRESENT | |
| Borrowing terms | :56 | PublicItemPage.tsx:205 | PRESENT | |
| Notify when back (`inventory.notify_when_back`) | :57 | PublicItemPage.tsx:207 | PRESENT | |
| Request from the catalogue (`request_workflow`) | :60 | PublicItemPage.tsx:208 | PRESENT | |
| Back to catalogue | :48 | PublicItemPage.tsx:201 (breadcrumb) | CHANGED | breadcrumb + header brand |
| Not found / not enabled / error | :52 | PublicItemPage.tsx:195-197,192-194 | CHANGED | full-page card with Back, Retry for transient |
| Phone: notify and request actions | n/a | PublicItemPage.tsx:209 | BURIED | inside the "Borrow this item" sheet |

### Self-checkout `/m/:slug/checkout`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Gate `inventory.self_checkout` + disabled message + back link | PublicSelfCheckoutPage.tsx:146-158 | :55,110 | PRESENT | |
| Loading / error | :135-145 | :106-107 | PRESENT | |
| Use / Return switch (clears scanned payload) | :162-190 | :125 | PRESENT | |
| Issue photo; return photo + required condition notes | :193-221 | :127-129 | PRESENT | |
| Scan QR disabled until photo / notes | :225-232 | :117-120 | PRESENT | with reason |
| Kit checklist capture + Confirm checkout/return | :234-238 | :130,117 | PRESENT | |
| Error message | :239-243 | :121 | PRESENT | |
| Result card | :245-249 | :122-123 | CHANGED | replaces form; "Borrow another" (P2-4) |
| Back to inventory | :126-128 | :116 (Cancel) | CHANGED | Cancel navigates back |
| Support contact footer | :257 | :133 | PRESENT | `SiteFooter` |

### Public events (list, detail, registration, feedback, calendar)

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Search, month, free / open filter, List / Month calendar, Clear | PublicEventsPage.tsx:114 | PublicEventsPage.tsx:98 | PRESENT | |
| Category and tag filters | :115 | :99-100 | PRESENT | |
| "n matching event(s)" | :116 | :101 | PRESENT | |
| Month calendar with anchor links | :117 | :102 | PRESENT | |
| Loading skeleton | :118 | :97 | PRESENT | |
| Distinct errors (429 / 400 / 404) + conditional Retry | :119-122 | :97, publicErrorState.ts:196-202 | PRESENT | |
| Empty states | :123-124 | :103 | PRESENT | |
| Recurring-series grouping and title | :125-126 | :104-105 | CHANGED | "Recurring series" eyebrow now plain text |
| Cover image, status badge, description, location, time | :135-138 | PublicEventCard.tsx:140-154 | PRESENT | |
| Price, capacity, availability | :139 | :155-159 | PRESENT | |
| "Registration closed · cutoff" | :140 | :129-131,150 | PRESENT | |
| Register / Apply / Join waitlist | :141,144 | :124-126,161 | CHANGED | link to detail page instead of inline form |
| Add to calendar (.ics) | :142-143 | :162-164 | PRESENT | |
| Detail: image, title, time, location, category, tags, description | PublicEventDetailPage.tsx:39-44 | PublicEventDetailPage.tsx:50-55 | PRESENT | |
| Detail: price, capacity, availability | :45 | :58-62 | PRESENT | |
| Detail: Add to calendar, Share event | :46-49 | :64-66 | PRESENT | |
| Detail: registration form or "closed" with cutoff | :50 | :56-63, EventRegistrationEntry.tsx:174-185 | CHANGED | modal for complex events (P2-5) |
| Detail: central chrome and brand | none | :28-30,48 | PRESENT | |
| Detail: 404 / 400 / error | :36 | :43-45 | CHANGED | full-page card for 404 |
| Detail on phones | n/a | :67 | BURIED | sheet; label "Register" regardless (P2-2) |
| Registration form: honeypot, contact fallback, ticket picker, invite code, promo code, custom form, waitlist/approval | EventRegistrationForm.tsx | EventRegistrationForm.tsx | PRESENT | only restyled |
| Registration success panel | EventRegistrationForm.tsx:72-77 | EventRegistrationForm.tsx (TicketCard) | CHANGED | ticket card, now with the makerspace name |
| Feedback: survey, anonymous note, certificate sign-in, email field, submit, thank-you | PublicEventFeedbackPage.tsx:58-73 | PublicEventFeedbackPage.tsx:59-76 | PRESENT | |
| Feedback unavailable with reasons + Back to events | :59 | :59 | PRESENT | |

### Public machines `/m/:slug/machines`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Groups per type, type icon, count, collapse | PublicMachinesPage.tsx:109-112 | :101-102 | PRESENT | |
| Machine image, name, usage hours | :117-122 | :104-105 | PRESENT | |
| Status (idle / running / reserved / maintenance / offline) | :121 | :38,108 | PRESENT | five labels |
| Status since | :124 | :105 | CHANGED | relative time |
| Training required / queue + ETA (`machines.public_detail`) | :125-126 | :106-107 | PRESENT | |
| Structured intake request (`machines.structured_intake`) | :127, MachineIntakeForm.tsx | :109, MachineIntakeForm.tsx:36-44 | CHANGED | behind "Request a job" modal; same fields and endpoint |
| Pagination 24 | :134-135 | :112 | PRESENT | |
| Distinct errors / empty | :103-108 | :93-94 | PRESENT | |
| Kind and training filters | none | :95-100 | PRESENT | new |

### Bookings `/m/:slug/bookings`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Search, kind filter, month, List / Calendar, Clear | PublicBookingsPage.tsx:83 | :64 | PRESENT | |
| "n matching space(s)", errors, empty | :84-94 | :63,65-66 | PRESENT | |
| Space image, name, location, kind, description | :101-110 | :70-71 | PRESENT | |
| Capacity, confirmation mode, explanation | :111-115 | :71-72, :56 | PRESENT | explanation in detail card |
| Per-space month calendar in calendar view | :116 | :74 | PRESENT | |
| "Choose a time" opens booking form | :117-118 | :70,73,47-58 | CHANGED | `?space=` detail view, deep-linkable |
| 14-day published availability + booking form (starts / ends / honeypot / submit / pending vs booked) | PublicBookingForm.tsx, AvailabilityCalendar.tsx | :54-55 | PRESENT | availability as a section |
| "My bookings" | :73 | :62 | CHANGED | header primary, now `member/bookings` |
| Detail on phones | n/a | :57 | BURIED | form in the "Choose a time" sheet; draft lost on close (P1-1 pattern) |

### Print request `/m/:slug/print` and status

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Module gate + printer queue availability | PublicPrintRequestPage.tsx:38-43 | :38-44 | PRESENT | |
| Title, brief, slicer settings | PublicPrintRequestForm.tsx:105-118 | :104-119 | PRESENT | |
| Material + colour catalogue (`machines.material_catalogue`) | :121-122 | :122-125 | PRESENT | |
| Filament pool select, loading / error / none available | :134-165 | :126-169 | PRESENT | |
| Quantity, estimated grams, source link | :168-200 | :170-202 | PRESENT | |
| Model files and screenshot pickers with Remove | :203-215, Parts:87-130 | :205-219, Parts.tsx:41-62 | PRESENT | |
| Honeypot, upload progress, submit error, submit | :93-233 | :93-102,222-237 | PRESENT | |
| Status tracker: 5 steps, queue position, live time-left, current status | Panels / Parts:164-266 | PublicPrintRequestParts.tsx:70-120 | PRESENT | |
| Status from `?token=` and localStorage | Page:49-51 | :49-51 | PRESENT | |
| Status shown when printing is unavailable | Panels:10 | :74-76 (action card) | PRESENT | |
| Status error shows server message | Parts:250-253 | Parts.tsx:126 | PRESENT | |
| Copy tracking link, send another request | none | Panels.tsx:17, Page:68 | PRESENT | new |
| Tracker on phones | n/a | :76 | BURIED | "Track your job" sheet; state is page-level so nothing is lost |

### Stats `/m/:slug/stats`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Printing tiles, busiest printer, queue, by brand | StatsSections.tsx | StatsSections.tsx:9-26 | PRESENT | |
| Filament trend | :101-110 | :27 | CHANGED | bars as progress bars |
| Per-printer table | :112-161 | :28-35 | PRESENT | `DataTable` cards on phones |
| Hardware tiles, most popular, tools out, recently added | :168-214 | :39-48 | PRESENT | |
| Currently out (item, holder, due, since) | :225-252 | :51-55 | PRESENT | |
| Loading / "turned off" error / empty | PublicStatsPage.tsx:75-126 | :32-33 | PRESENT | explanation text kept |
| Catalogue and Staff links | :62-68 | PublicPageChrome.tsx | CHANGED | nav + footer |

### Organization pages

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Org brand, directory link, theme | PublicOrganizationPage.tsx:35-40 | :24-25 | PRESENT | |
| Name, description, Visit website | :55-63 | :26-27 | PRESENT | |
| Loading / 404 / error with reason | :46-52 | :29-30 | PRESENT | |
| Events list: image, host, dates, location, description, price, availability | :82-95 | :37-40 | PRESENT | |
| "Register at {host}" | :96-98 | :41 | PRESENT | |
| Pagination | :105-111 | :42 | CHANGED | assumes 24 per page (P2-6) |
| Invitation redeem: sign-in, auto-redeem, success link, error + back | OrganizationInvitationRedeemPage.tsx:44-90 | :52-78 | PRESENT | |

### Desk kiosk `/kiosk/:slug`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Full catalogue (browse, search, cards, quick view, request, scan) | PublicDeskKioskPage.tsx:28 | PublicDeskKioskPage.tsx:29-33 | PRESENT | body left, request panel right |
| Tenant brand, programme links, map, support contact | via catalogue header/footer | :30-32,36-38 | PRESENT | |
| Theme toggle, catalogue link, staff sign-in | :18-25 | :40-41, :32 | PRESENT | |

### Station kiosk `/m/:slug/kiosk/:stationToken`, `/kiosk/:uuid`

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| 8-digit PIN, unlock, invalid error | KioskStationPage.tsx:73-76 | KioskStationPage.tsx:56-60,86-87, KioskPin.tsx | CHANGED | digit boxes + keypad; hardware keyboard still types |
| Offline-locked notice | :73 | :92 | PRESENT | |
| Station name, makerspace and kind | :72,78 | :80-81 | PRESENT | |
| Start operator shift + error | :79,62-66 | :62-68,88-89 | PRESENT | |
| Recovery replay correction (`?recovery=`) | :79 | :70 | PRESENT | |
| Offline queue handover (capture, queue, status, retry, acknowledge) | KioskOfflineHandover.tsx, KioskQueueStatus.tsx | same, DataTable | PRESENT | |
| Online QR lookup | KioskOnlineScanner.tsx | KioskOnlineScanner.tsx:26-30 | CHANGED | camera added; field not cleared or re-focused (P1-2) |
| Online handover: load request, assign box, issue, return, photo, remark, kit | KioskOnlineHandover.tsx | KioskOnlineHandover.tsx (FlowLayout kiosk) | PRESENT | same commands; double-submit guarded |
| Continue with encrypted queue | :87 | :78 | PRESENT | |
| Full screen, Lock station + discard confirmation | :90-103 | :90-91,95-97 | PRESENT | |
| Idle reset | :48-53 | :49-54,83 | CHANGED | 10-second warning with Keep working |
| Storage error notice | :98 | :94 | PRESENT | |

### Event check-in station and scanner

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| 8-digit PIN unlock + error | EventCheckInStationPage.tsx:40-45 | :24-28,48-50 | CHANGED | keypad; disabled while offline with reason |
| Offline roster operator (auto download, search, check in, sync) | :46 | :54 | PRESENT | |
| "Wipe data and lock station" | :47 | :30-44,51-53 | CHANGED | confirmation when unsynced check-ins exist; wipe unchanged |
| `/scanner`: payload + resolve (`/admin/qr/resolve`) | ScannerPage.tsx:37-52 | ScannerPage.tsx:13-26 | CHANGED | adds camera; field not re-focused (P1-2) |
| Scanner: error, target, allowed actions | :53-67 | :22-33 | PRESENT | key/value card instead of raw JSON |

### Auth surfaces

| Capability | Old | New | Status | Note |
|---|---|---|---|---|
| Staff sign-in: username, password, error, pending | LoginPanel.tsx:70-109 | LoginPanel.tsx:57-80 | PRESENT | show/hide password added |
| Password-login switch copy and gating | :65-69,98 | :61-63,64,77 | PRESENT | |
| Forgot password (email enabled and password login on) | :110-117 | :69-72 | PRESENT | |
| Social sign-in (Google, Apple, OIDC) on staff surface, incl. MFA from social | :119-121 | :52-56, SocialSignInButtons.tsx:98-100 | PRESENT | |
| Staff MFA challenge, enroll QR + key, recovery codes, expiry, back | MfaFlow.tsx | MfaFlow.tsx:30-69 | PRESENT | recovery-code toggle, copy, download added |
| Change-password gate (current, new, confirm, mismatch, sign out) | ChangePasswordGate.tsx:31-95 | ChangePasswordGate.tsx:30-85 | PRESENT | |
| Member sign-in / create account, name, phone, email, password | MemberAuthPanel.tsx:171-240 | MemberAuthPanel.tsx:143-179 | PRESENT | |
| Self-registration and password-login switches | :38-59 | :41-61 | PRESENT | |
| "No self sign-up" notice | :222-226 | :153 | PRESENT | |
| Email verification: code, verify, resend | :131-169 | :129-142 | PRESENT | |
| Member MFA challenge | :129-130 | :127-128 | PRESENT | |
| Member social / OIDC (+ callback completion) | :228-237 | :149-152, SocialSignInButtons.tsx:60-70 | PRESENT | |
| Reset password: request, confirm, success, unavailable, resend cooldown | PasswordRecoveryFlow.tsx:74-166 | PasswordRecoveryFlow.tsx:30-100 | PRESENT | |
| Legacy `uid` + `token` reset | LegacyPasswordResetForm.tsx:30-59 | LegacyPasswordResetForm.tsx:27-40 | PRESENT | |
| MFA account page: status, password confirm, enroll, regenerate, disable, codes, links | MfaAccountPage.tsx:26-40 | MfaAccountPage.tsx:32-51 | PRESENT | disable now behind a confirm dialog |
| Staff invitation accept: password, optional MFA code, success link | StaffInvitationAcceptPage.tsx:14-25 | StaffInvitationAcceptPage.tsx:15-35 | BURIED | MFA field inside a disclosure (P2-3) |
| Archived-payments sign-in / member account sign-in fallback | MemberAuthPanel | same component | PRESENT | |
| Member "Forgot password" | none | none | MISSING | absent in both (P2-8 note); not a regression |
