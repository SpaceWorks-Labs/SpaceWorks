# Decisions: Product and scope

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-344 — Card Studio 2: photo path and editor features
- **Area:** product
- **Date:** 12 November
- **Decision:** Single and bulk photo upload feed the background-eraser adapter, and the cut-out shows over any card background with per-card mask, crop and position, falling back to the original photo with no provider. The editor gains the Canva-level features (layers, multi-select, alignment, guides, undo/redo, shapes, text styles, brand kit, assets library, templates, front/back, print-ready PDF with bleed and crop marks, bulk merge, versioning). Certificates use the same editor.
- **Why:** Reach parity with common design tools for ID cards.
- **Status:** current
- **Implemented in:** `backend/apps/card_designs/`

### D-325 — Display settings, public stats page and Anthias
- **Area:** product
- **Date:** 11 November
- **Decision:** Space Managers choose which sections each display screen and the public space page show, their order, layout, theme and privacy level. A public stats display respects `public_stats_capabilities`. Display URLs are signed, read-only, cookie-free and excluded from analytics, and a first-class Anthias integration keeps per-space players (encrypted credentials), syncs web assets through the Anthias REST API with an asset-id mapping, is SSRF-safe and audited.
- **Why:** Digital signage should be configurable without code and work on common signage players.
- **Status:** current

### D-314 — Card Studio and background-eraser adapter
- **Area:** product
- **Date:** 11 November
- **Decision:** The ID card builder becomes a full designer with a quick mode and an advanced free canvas (uploaded backgrounds and images, layers, snapping, rich text, photo effects, templates and import/export). The server renders every layer property identically to the designer preview, enforced with golden fixtures and TypeScript twin tests. Background removal is a uniform image-adapter contract (HMAC-signed HTTPS, async job, off by default, per-space provider, derived private cut-out linked to the original); no eraser service is shipped in this repo. Card photos can be bulk-uploaded and matched to holders by file name.
- **Why:** Printed cards must match what staff design, and the maintainer runs the eraser as a separate service.
- **Status:** current
- **Implemented in:** `backend/apps/card_designs/`, `backend/apps/id_programmes/`

### D-307 — Public space page: Here now, machines, calendar and display screen
- **Area:** product
- **Date:** 11 November
- **Decision:** Each space's public page gains, behind existing module switches, "Here now" (checked-in people), "Machines now" (never who is using one unless they opted in) and an events calendar of public, listed events. Logged-out visitors see names only for people whose profile is open to the web and who did not hide presence; everyone else is a count. A paired full-screen display route rotates these panels, is claimed by staff with a short code and defaults off, with a limit key for displays that defaults to none.
- **Why:** Gives a space a public, privacy-respecting live view; existing presence and kiosk infrastructure is extended rather than duplicated.
- **Status:** current

### D-306 — Public features page and sign-in ID-card showcase
- **Area:** product
- **Date:** 11 November
- **Decision:** A public `/features` page lists every module and its features, built from the frontend capability catalogue (`lib/features.ts`, `featureHelp.ts`) plus a short curated summary, with a test asserting every frontend-exposed module key appears. The ID-card showcase is a decorative live sample card beside the sign-in forms rather than on the landing page, and the mascot Patch appears on landing pages under the brand rules.
- **Why:** A generated list cannot drift from the real module set.
- **Status:** current
- **Implemented in:** `frontend/src/lib/features.ts`, `frontend/src/lib/featureHelp.ts`

### D-303 — Profiles are visible by default
- **Area:** product
- **Date:** 11 November
- **Decision:** A member's profile is visible to any signed-in user in any space, addressed by handle, with every section on by default; the member can hide the whole profile or any section. The open web (logged-out visitors, search engines) is a separate opt-in switch. Never shown regardless of defaults: attendance at private, invite-only or unlisted events, unpublished or withdrawn results, and anything from a space where the member is restricted, suspended or revoked. Existing profiles with no recorded visibility change get the new default plus a one-time in-app notice; members who explicitly hid theirs keep it hidden. Directory rows show only display name, headline and avatar.
- **Why:** A profile should work like a username across the platform; this supersedes the opt-in default of D-302 and the earlier INVARIANTS rule.
- **Status:** current

### D-302 — Member profile: status, achievements, projects
- **Area:** product
- **Date:** 11 November
- **Decision:** The maker profile gains a "current status" (preset plus optional line of up to 120 characters), achievements that are either derived and verified from published SpaceWorks data (hackathon placements, prizes, roles, events attended) or self-reported and labelled as such, and importing one's own hackathon submission as a project. Every section has its own show toggle; private data comes only from the profile's own space.
- **Why:** Members want a résumé-style profile that reflects their activity.
- **Status:** partly superseded by D-303 (default visibility) and D-304 (profile is account-level)

### D-300 — Landing scroll story, landing switch and installer question
- **Area:** product
- **Date:** 11 November
- **Decision:** The landing uses a restrained scroll-driven story (pinned hero scene, sticky product stage, reveal-on-scroll, full static fallback for reduced motion, short viewports and phones) with no new animation dependency, plus a subtle tiled brand-symbol background. The deployment setting `HUB_LANDING_ENABLED` (default on, asked by the installer, changeable via `scripts/apply-settings.sh`) controls it; when off, `/` shows the single listed space's home or the `/spaces` directory, and `/docs`, `/spaces` and other routes keep working. The landing links the three public repos and the dark palette is reviewed as one system with AA contrast.
- **Why:** A space may want its own home at `/` instead of the product page.
- **Status:** partly superseded by D-316 (dark palette values)
- **Implemented in:** `backend/config/settings_credentials.py`, `scripts/apply-settings.sh`

### D-278 — Docs ship in-app at /docs (no wiki)
- **Area:** product
- **Date:** 11 November
- **Decision:** Documentation lives in the repo and renders at `/docs`, not in a GitHub wiki. Folders with front matter (title, group, order, summary) include `docs/guide`, `docs/architecture`, `docs/modules`, `docs/hosting`, `docs/project`, tutorials, user guides, how-to, API and reference. The docs UX has sidebar, on-this-page scroll-spy, search, copy buttons, callouts, an endpoint reference generated from the OpenAPI schema, and code-split chunks.
- **Why:** The same content ships with the release and stays versioned with the code.
- **Status:** current
- **Implemented in:** `docs/guide`, `docs/architecture`, `docs/modules`, `docs/hosting`, `docs/project`, `docs/tutorials`, `docs/user-guides`

### D-277 — Hub landing page and in-app docs
- **Area:** product
- **Date:** 11 November
- **Decision:** The hub's `/` is an original landing page in the app's own design language (what it is, areas, how it works, install CTA, Spaces section, Docs section), with the directory at `/spaces`; nothing is copied from the separate website repo, and every claim must be true of this codebase. User docs render in-app at `/docs` from the repo's markdown. The landing states that native Android and iOS apps are in development, with no store badges or dates.
- **Why:** The product needs its own front page without redirecting to a standalone site.
- **Status:** current
- **Implemented in:** `frontend/src`, `docs/`

### D-226 — Final audit answers
- **Area:** product
- **Date:** 10 Nov 2026
- **Decision:** `require_waiver` applies only while `membership.guest_passes` is on. An event creator and every co-organizer holding `manage_event` must hold the required certification, with a non-member organizer refused `certification_required` unless staff override with a reason. On a booking move, included hours are released and re-taken for the new time. A loan return grace is one hour or until that session closes, whichever is first. Sponsored-guest damage while `safety.incidents` is off still writes the incident record and notifies the sponsor (a narrow exception to D-218). Payout money stays session-only for receipts-payments totals and native device grants, and webhook names stay per area family.
- **Why:** Audit follow-ups (FINAL-AUDIT-0.12.0).
- **Status:** current

### D-223 — Guest passes and event venue flow
- **Area:** product
- **Date:** 10 Nov 2026
- **Decision:** Guest passes are a capability `membership.guest_passes` under Membership (with an events adapter; core never imports events): a dated permit on an existing account, never a membership and with no member card. Issue paths are event-linked, member-sponsored and a paid day pass (a charge subject under `charges.membership`, no automatic credit toward joining). The Space Manager chooses per space guest borrowing (none, on-site only, or full with deposit), guest machine use (none, supervised, or after induction certification), sponsor-or-guest liability, door registration (guest pass or full membership) and whether a waiver is required. Publishing an event whose linked booking is pending warns, and a rejected/cancelled/missing one blocks unless the organizer chooses an audited "publish without room"; a pending linked booking holds its slot as tentative and event cancel/move offers but never auto-changes the booking. Staff-only "house" bookings have no booker, charge or plan hours. Wallet pass credentials are per makerspace, falling back to platform credentials. No door/keyfob access control is built; on-site check-in is location presence or staff desk check-in.
- **Why:** The maintainer judged door access control unnecessary and only location check-in needed.
- **Status:** current

### D-219 — Release 0.12.0 choices: fonts, due dates, privacy, audit, upgrades
- **Area:** product
- **Date:** 9 Nov 2026
- **Decision:** Brand display text uses only the free Gilroy weights (Light, ExtraBold), with Outfit for body and Unbounded as accent. Loan returns falling due while the space is closed roll to the next opening plus a one-hour grace; pickup deadlines roll to the close of the next open session. Room outages on public pages show only a neutral "Unavailable" when the room shows public availability, and an event page shows only "Venue update pending". Payee money (reimbursements, payouts) is session-only, never read by personal tokens or OAuth clients. Area roles read audit rows and audit-backed reports only for their own area, the Space Manager and superadmin keep the whole space. Upgrades are forward-only (rollback means restoring the pre-upgrade backup; the updater refuses a downgrade). Card designs and ID programmes are archived when removed (hard delete only if never used).
- **Why:** Reason not recorded
- **Status:** partly superseded by D-225

### D-209 — Own-history completeness and Shop pickup tracking
- **Area:** product
- **Date:** 7 Nov 2026
- **Decision:** Members and account-only borrowers can reach their own history of purchases, payments, event participation, loans/returns and bookings from the account area; account-only borrowers reach their loans and core money without the membership dashboard or the online rail. Shop pickup fulfilment has status and timestamps plus receipts, returns and refunds under the pickup-only decision (no carrier shipping). Cross-owner and cross-tenant access is denied.
- **Why:** Reason not recorded
- **Status:** current

### D-170 — Public stats page
- **Area:** product
- **Date:** 2 November
- **Decision:** The public stats page has switchable sections: events, machines and printing, lending and inventory, community. The Space Manager fixes the period (month, year, all time or financial year), headline numbers and order in Settings, and there is a full-screen auto-refreshing kiosk mode. It never shows names, contacts, hidden items, private events or community counts below 3, everything goes through the public projection, and a section is hidden when its module is off (data kept). D-205 later lets area managers configure their own area's stats.
- **Why:** Privacy: counts must not identify individuals.
- **Status:** current
- **Implemented in:** `backend/apps/makerspaces/public_stats_settings.py`, `backend/apps/makerspaces/public_stats_catalogue.py`

### D-154 — Membership import, erasure and contact access
- **Area:** product
- **Date:** 31 October
- **Decision:** Record-only membership import rows are allowed in every space as a per-row staff choice with no invitation or account. An approved erasure ends the membership as a voluntary leave (a paid term opens a refund due under the refund policy) and blanks the record, titles, maker profile, application answers and imported details while keeping money rows, the audit log and the account. Member contact details stay behind `manage_members`. Membership waivers are not built.
- **Why:** Reason not recorded
- **Status:** current

### D-145 — Chat alerts and invites
- **Area:** product
- **Date:** 30 October
- **Decision:** WhatsApp alerts go to each on-shift mentor's own consented number only, never shared team numbers. Organization invites accept an optional invitee email so they can be sent like event and booking staff invites. The chat copy of a staff invite carries the single-use invite link in the encrypted envelope body.
- **Why:** Reason not recorded
- **Status:** current

### D-138 — KiCad files stay download-only
- **Area:** product
- **Date:** 29 October
- **Decision:** There is no in-browser KiCad viewer; KiCad files stay download-only. Pairwise judging counts as judging work for contribution certificates.
- **Why:** Reason not recorded
- **Status:** current

### D-136 — Card-design approval at four levels
- **Area:** product
- **Date:** 29 October
- **Decision:** The card-design approval switch is configurable per space (default on for non-Space-Manager edits), per organization, per ID programme and per event, with the most specific level winning. For event cards the default stays "no approval".
- **Why:** Reason not recorded
- **Status:** current
- **Implemented in:** `backend/apps/card_designs/approval.py`

### D-135e — ID card answers (Q-I1 to Q-I12)
- **Area:** product
- **Date:** 29 October
- **Decision:** Bulk card files are kept 7 days (private), then deleted. The card font library is the full Google Fonts catalogue, served from the app itself with no runtime calls to Google from the browser. Photo clean-up runs on the server and never through a hosted API; the original is deleted once accepted. A "photo needs update" card stays valid and the holder gets one reminder. Blood group and emergency contact are seen only by the holder and on the printed card (organizers only behind a per-event switch). Event cards expire at event end plus one day and are issued automatically to every confirmed registrant. Programme holders need no host-space membership. An organizer is anyone with the event's edit permission. A card scan only identifies and never signs anyone in. Wallet credentials are platform-level. Programme designs use the same approval switch as other designs.
- **Why:** Privacy and CSP for self-hosted fonts and server-side photo processing; other reasons not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/card_designs/`, `backend/apps/events/id_cards.py`

### D-132 — ID card features
- **Area:** product
- **Date:** 28 October
- **Decision:** ID cards include a verify QR with a public validity page, wallet passes with live updates, expiry tied to membership or event with staff revoke (reason, audited), scan to check in, bulk generation with print sheets, photo capture with crop, two-sided designs with opt-in encrypted sensitive fields, and delivery plus a "my cards" page. The designer is a free canvas with a background and draggable layers, and heavy work (bulk, PDFs, wallet passes, emails) runs as chunked, retried, cancellable background tasks, never inside a request.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/id_programmes`, `backend/apps/card_designs`, `docs/wallet-passes.md`

### D-128e — ID card scope and fonts
- **Area:** product
- **Date:** 28 October
- **Decision:** ID cards are fully digital with no fee, and a font library (including Indic scripts) is allowed for cards only. Six templates ship (Classic, Bold, Minimal, Community, Student, Event pass), membership card designs by non-Space-Managers need per-space approval (default on), and member numbers use a fixed number with a custom pattern. Every organizer of an event can edit and publish that event's card design with no approval and every edit audited, but mentors and non-organizer staff cannot.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/card_designs`, `backend/apps/id_programmes`, `backend/apps/events/id_cards.py`

### D-96 — Research picks: donations and calendar sync
- **Area:** product
- **Date:** 24 October
- **Decision:** Donations and sponsors (one-off and recurring, perks, receipts) and iCal calendar sync for bookings, events and the rota are built, each with its own switch and ledger records. Incident registers, inductions, keyholder rota, lockers, keys, lost and found, voting, skills directory, waivers, grants, accounting export, fabrication service, suggestion box and POS were not built at that time. The shop was later chosen as the "something else" (D-128c).
- **Why:** Reason not recorded.
- **Status:** partly superseded by D-128c

### D-71 — Public card verify page and tax mode
- **Area:** product
- **Date:** 21 October
- **Decision:** A minimal public card verify page (separate opaque token; Valid, Expired or Revoked plus space and valid-until; name and photo only if the holder opts in; noindex, rate-limited) is built. Guest RSVP is not offered, so sign-in stays. A `billing.tax` capability is off by default with "India GST" and "single named tax" modes. Short links use `/e/<7-char base62>`.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/events/short_links.py`

### D-51a — Notification cutover and delight defaults
- **Area:** product
- **Date:** 20 October
- **Decision:** Fresh installs (no makerspace, at most the bootstrap account, no notification history) send notifications by default, while upgraded deployments stay held until the operator runs `notification_cutover activate`. Delight effects and easter eggs are on by default for new and existing spaces, each space can turn them off, reduced motion is always honoured and the dark-mode transition is always on. Hackathon storage cap is 25 GB decimal.
- **Why:** Upgrades must not start sending unexpectedly.
- **Status:** current

### D-33 — Reuse the member profile photo
- **Area:** product
- **Date:** 18 October
- **Decision:** The existing member profile photo is reused for badges, ID cards, team cards and mentor/judge cards. Staff accounts have no profile by design.
- **Why:** Reason not recorded.
- **Status:** current

### D-30 — Date of birth is saved, age is computed
- **Area:** product
- **Date:** 18 October
- **Decision:** Date of birth is a sensitive saved detail (encrypted, opt-in, editable, exported, deleted with the account). Age is never stored; it is computed whenever needed, and an "age" form question is answered as of the event start date. Organizers see the computed age unless the form explicitly asks for date of birth, which the member sees before submitting.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/saved_details`

### D-28 — Registration autofill and Saved details
- **Area:** product
- **Date:** 18 October
- **Decision:** Personal data a member enters in registration forms can be saved to their own account and prefill later forms, matched by a well-known field key. Each field has a "save to my profile" choice (on by default, off for sensitive fields such as dietary, accessibility and emergency contact), a Saved details page allows view, edit and delete, and organizers see only the answers actually submitted. Saved data is encrypted where the PII rules require, exported with the account and deleted with it.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/accounts/saved_details`

### D-23 — One shared handle namespace
- **Area:** product
- **Date:** 18 October
- **Decision:** Members, makerspaces and organizations share one handle namespace. Existing member handles win, and the default handle is the slug. A published page of a makerspace stays public and the team section links only to public member profiles; staff private data is never shown.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `backend/apps/makerspaces/handle_gate.py`, `backend/apps/makerspaces/public_page_handles.py`

### D-3 — No age limit or minors features
- **Area:** product
- **Date:** 18 October
- **Decision:** There is no minimum-age setting and no minors or guardian-consent gating in events or hackathons.
- **Why:** Reason not recorded.
- **Status:** current
