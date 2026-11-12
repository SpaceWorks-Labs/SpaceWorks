# Decisions: UX and design

Part of the [decisions index](../decisions.md). Newest first. Each entry keeps its reason.

### D-381 — Logo animation correctness
- **Area:** ux-design
- **Date:** 13 November
- **Decision:** The box animation is fixed at the generator so a shut box has one solid orange lid face and an open box two orange flaps, with no blank holes in dark; explicit state tests and a headless frame check guard it.
- **Why:** Blank holes and double faces were seen in dark and light.
- **Status:** current

### D-380 — One bright chart palette in both themes
- **Area:** ux-design
- **Date:** 13 November
- **Decision:** Chart series are teal, orange, citron, sky and yellow with the same hex in light and dark; graphic contrast of 3:1 comes from a per-theme `--chart-edge` outline and a casing under lines rather than dulled colours. Red is reserved for errors and dash patterns stay.
- **Why:** Keep one recognisable palette while meeting contrast.
- **Status:** current

### D-376 — Reusable motion templates
- **Area:** ux-design
- **Date:** 13 November
- **Decision:** The light/dark switch animation (720 ms circular View-Transition reveal, cross-fade fallback, instant under reduced motion) and every other animation family (route transition, page enter, overlays, toast, sidebar, skeleton, hover/press, search) ship as token-based reusable templates in the design system. All search inputs use one shared SearchField with a focus ring, loading spinner swap and reduced-motion colour-only behaviour.
- **Why:** Other products should reuse the same motion.
- **Status:** current

### D-367 — Logo hover is a fold-then-open cycle
- **Area:** ux-design
- **Date:** 13 November
- **Decision:** From the at-rest open logo the hover folds it shut then opens it (generator-driven, no hold), leaving mid-way lets the cycle finish, and the brand spec names it as the single hover-motion exception.
- **Why:** Soften the hover so it never snaps.
- **Status:** current

### D-362 — Logo hover opens the box once
- **Area:** ux-design
- **Date:** 13 November
- **Decision:** The Space Works mark plays the one-shot box opening on hover and keyboard focus wherever it appears, through one shared component; reduced motion and touch show the static mark, and tenant logos never animate. From the open rest state it folds shut then opens, with no snap.
- **Why:** One consistent brand motion; the rule and motion catalogue are recorded in the design system.
- **Status:** current

### D-323 — Motion pass and tokens
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** Route changes use the View Transitions API (content cross-fades while the shell stays still, CSS fade fallback), and drawers, dialogs, menus and toasts share one set of motion tokens (120/180/240 ms) in `index.css`. Animation uses transforms and opacity only with no new dependency; `prefers-reduced-motion` disables it and kiosk/TV get fades only.
- **Why:** Consistent, fast, accessible motion across the app.
- **Status:** current

### D-322 — Box-opening loader everywhere
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** Every loading state in the web app uses the Space Works box-opening animation (full size for pages and panels, compact inline for buttons and rows); the ring spinner and loading skeletons are replaced, reduced motion shows the still logo, and each state keeps a polite status label.
- **Why:** Reason not recorded.
- **Status:** current

### D-316 — Solid-black dark theme
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** The dark theme is a solid black family on every surface (background #000000, neutral greys, no green tint); teal, citron and orange appear only as accents, status and focus, and text is cream on black with AA contrast. The shipped dark `line` token is #2C2C2C, and teal is 2.99:1 on the dark panel so charts keep the accent-ink colour on dark.
- **Why:** Mixing pure black with green-tinted surfaces did not work visually.
- **Status:** current

### D-313 — Cold-start splash and Spaces header
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** The box symbol unfolds and flies into the navbar logo on first load (pre-React inline splash, once per page load, transforms/opacity only, still under reduced motion). `/spaces` uses the same header as the landing page.
- **Why:** First load must never be blank, and the Spaces page header was inconsistent.
- **Status:** current

### D-299 — Font policy: free Gilroy weights plus open fonts
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** Only Gilroy's free weights (Light 300, ExtraBold 800) are used, for display headings and light display text; every other weight, and anywhere the free files cannot be used (for example PDF engines), uses the open fonts Outfit and Unbounded (both OFL). Paid Gilroy weights are never shipped.
- **Why:** Avoids shipping unlicensed font weights in a public repository.
- **Status:** current

### D-275 — Public home and space directory
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** The `/spaces` directory lists only real public spaces (published, active, not archived or hidden) as cards led by the space's own cover image and logo, with place, offers chips and next public event, plus loading, empty, no-results and error-with-retry states. The directory has real brand character, with hover lift that respects reduced motion. Dark mode keeps a true-black page with brand accents.
- **Why:** The page lists makerspaces, so it should look like a makerspace directory rather than a tool-borrowing page.
- **Status:** partly superseded by D-316 (dark-theme surfaces)

### D-273 — Settings information architecture
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** Space settings live at `/admin/settings/<section>` in seven groups with search and one-line help from one translated catalogue (coverage enforced by a test). Area pages and Settings cross-link both ways; "Email & integrations" splits into Email sending and Webhooks; "Modules" reads "Areas & add-ons" in user-facing copy only; the Admin tools page is retired. Every offsite backup destination write, including name/retention edits and the connection probe, requires a recent re-sign-in. Paged lists use one shared pager (page size 24). Dark `--color-line` is 94 130 124.
- **Why:** Implements the D-255 grouping; one name per place.
- **Status:** partly superseded by D-316 (dark-theme values)
- **Implemented in:** `frontend/src/lib/featureHelp.ts`

### D-271 — Console-gaps batch 2 outcomes
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** The All-jobs view filters in the browser; platform module defaults are read-only for superadmin because the setup-areas choice owns them; planned-consumable shortage rows show the room, never the booker; the member 360 opens from any staff tab for staff holding an area action but never for handover-only desks; a venue fee for an already-booked room and window is refused with 409 `venue_room_already_booked`.
- **Why:** Reason not recorded
- **Status:** current

### D-269 — i18n and copy rules
- **Area:** ux-design
- **Date:** 11 November
- **Decision:** Counted messages are whole Lingui `plural()` messages; on-screen enum codes always go through translated label functions; `StatusBadge` requires a `label`; display-text maps are functions so they follow a language switch (`i18n:check` refuses plain `Record<string, string>` maps and raw DataTable `header:` strings); dates and numbers use the app locale. Copy says "loan history", "Inventory" and "spaces", and module names on screen come from one translated map typed by the generated ModulesEnum.
- **Why:** Keeps translations correct and prevents hard-coded text.
- **Status:** current

### D-258 — Mermaid diagrams where flows are hard to read
- **Area:** ux-design
- **Date:** 10 November
- **Decision:** Mermaid diagrams are used for flows that are hard to read in prose (architecture, request state machine, hosting shapes, installer and update flow, backup paths, money flow, role-to-area scoping, notification pipeline). The ASCII state machine stays in the contributor docs, and diagrams use plain wording.
- **Why:** Reason not recorded
- **Status:** current

### D-255 — Settings grouped by the maintainer's mental model (UX pass)
- **Area:** ux-design
- **Date:** 10 November
- **Decision:** Space settings are grouped as Space, People, Areas (Inventory, Machines, Events, Bookings, Shop), Money, Communication, Integrations and Administration, searchable, with one-line help and safe defaults. A research-backed UX review covers navigation, naming, layouts, consistent list/drawer/dialog/empty/error patterns, accessibility and mobile for every role.
- **Why:** Settings had no consistent grouping; the review makes the console predictable.
- **Status:** current

### D-247 — Tagline and "Lending" renamed to "Inventory"
- **Area:** ux-design
- **Date:** 10 Nov 2026
- **Decision:** The product tagline is "Run the space, not spreadsheets." in the official brand colours, used in the README banner and tagline. User-facing "Lending" (area and module names, navigation, settings, help, docs, notification copy) becomes "Inventory"; action words (borrow, loan, return, due back, renewals) stay, and internal identifiers, module keys (`loans.*`), routes and env keys are unchanged.
- **Why:** Reason not recorded
- **Status:** current

### D-235 — Ease of use and limits visibility
- **Area:** ux-design
- **Date:** 10 Nov 2026
- **Decision:** Ship an ease-of-use pass: minimal installer questions, a first-run guided setup, a "next steps" checklist, optional features hidden until switched on, plain-language labels without internal jargon, and a 5-minute quickstart in the docs. Every per-space limit is managed by the superadmin in the platform console with usage shown beside it and an audited change; each role sees its remaining allowance with warnings at 80% and at the limit; request rate-limit scopes are editable in the console within safe bounds (DB-stored, env values are defaults, audited).
- **Why:** The maintainer wanted the product easier for users.
- **Status:** current

### D-225 — Dark mode becomes true black
- **Area:** ux-design
- **Date:** 10 Nov 2026
- **Decision:** Dark surfaces use a #000 page background with near-black raised surfaces, keeping the current dark look, Maker Teal accent and Citron focus at WCAG AA (smallest token change). Dark illustrations and print artwork keep Deep Ink and the PWA manifest stays Cream.
- **Why:** The maintainer wanted the existing dark theme deepened toward black, not redesigned.
- **Status:** current

### D-210 — Uploaded makerspace logo in the shared public header
- **Area:** ux-design
- **Date:** 7 Nov 2026
- **Decision:** The public tenant header shows the uploaded makerspace logo instead of the SpaceWorks symbol plus name, with an accessible home name and correct single/central links; without an upload it shows the SpaceWorks symbol and the space name. Directory cards keep names.
- **Why:** Reason not recorded
- **Status:** current

### D-208 — Item images across public catalogue areas
- **Area:** ux-design
- **Date:** 7 Nov 2026
- **Decision:** Shop, booking resources, events, inventory and machines manage and display item images through the existing validated public image pipelines and permissions. Private evidence and card photos stay separate.
- **Why:** Reason not recorded
- **Status:** current

### D-206 — Makerspace home reuses the listing banner
- **Area:** ux-design
- **Date:** 7 Nov 2026
- **Decision:** The existing listing cover image is shown at the top of the makerspace home; there is no second banner field or upload path, and listing and home use the same configured image with an unset fallback.
- **Why:** Avoid duplicate image controls.
- **Status:** current

### D-204 — Light mode is the default theme
- **Area:** ux-design
- **Date:** 7 Nov 2026
- **Decision:** Space Works defaults to light mode. Saved light/dark preferences are respected (including cross-tab updates and unavailable storage), and a visitor whose OS is dark but has no saved choice starts light.
- **Why:** Reason not recorded
- **Status:** current

### D-203 — Makerspace home has no inventory list; Inventory is its own page
- **Area:** ux-design
- **Date:** 7 Nov 2026
- **Decision:** A makerspace home shows its overview, events and other enabled areas with no inventory list. Inventory is its own tab and page named "Inventory" (not "Catalogue") at `/m/<slug>/inventory`, or `/inventory` in single-tenant mode; item, detail and checkout flows stay reachable and published custom-page content is preserved.
- **Why:** Reason not recorded
- **Status:** current

### D-169 — README tagline, banner and calendar invites
- **Area:** ux-design
- **Date:** 2 November
- **Decision:** The README leads with a brand-palette banner with rounded corners and the mascot (official design-system art), a short tagline, and says any machine type can be added and lists the integrations. Calendar support is "Add to Google Calendar" links, .ics downloads and subscribable iCal feeds; event registration and booking confirmation emails also attach an .ics invite with UID and sequence numbers plus cancellations. The banner generator is not kept in the repo.
- **Why:** Reason not recorded
- **Status:** partly superseded by D-247 (tagline wording)

### D-57 — Delights and easter eggs
- **Area:** ux-design
- **Date:** 20 October
- **Decision:** Behind per-space delight flags and honouring reduced motion, the app has a logo unfold on hover/click with seven clicks opening Maker mode, one-time on-time-return confetti in brand shapes, a search-box phrase easter egg with a friendly after-midnight staff line, and a first-load card stagger. Kiosk, scanner, checkout and payment screens are excluded.
- **Why:** Reason not recorded.
- **Status:** current

### D-56 — Mascot rules
- **Area:** ux-design
- **Date:** 20 October
- **Decision:** The mascot appears only on the 404 page, with a thin warm-cream die-cut sticker border as the official dark-background variant (replacing the earlier cream card). Elsewhere the app uses design-system SVG illustrations.
- **Why:** The sticker border keeps contrast on dark backgrounds without a card.
- **Status:** current

### D-32 — Original artwork only
- **Area:** ux-design
- **Date:** 18 October
- **Decision:** Every illustration and glyph is original Space Works artwork in SVG with light and dark variants, built from the brand symbol and tokens: mood glyphs, loader, 404 art, empty states, landing illustrations, role illustrations, default certificate templates and default badge/ID-card templates. Decorative art is `aria-hidden` and meaningful art has alt text.
- **Why:** Reason not recorded.
- **Status:** current
- **Implemented in:** `frontend/src/assets/illustrations`

### D-31 — Everything is built in the Space Works theme
- **Area:** ux-design
- **Date:** 18 October
- **Decision:** All new UI uses only the Space Works brand: CSS-variable tokens for light and dark, Gilroy with one Unbounded accent per layout, lucide-react icons, the AppShell layouts, existing primitives, the accessibility floor and colour vocabulary. No third-party product look, fonts, palettes or copy.
- **Why:** Reason not recorded.
- **Status:** current
