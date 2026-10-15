# Welcome surfaces and dark theme: brand spec

Status: Phase 1 spec, written 2026-10-15 against `lane/dr-resp-shell` @ `1e8b38be`. No app code was changed.
The owner asked for the welcome page and sign-in screens to follow the brand guidelines but look bolder,
and for dark mode to be good. This spec covers both.

**Source rule.** Every decision comes from two sources only:

- **Brand kit**: guideline pages p.1–p.17 (`SpaceWorks-Design/brand/guidelines/png/NN.png`),
  `tokens/tokens.css`, the logo masters, and `docs/ui-brand-spec.md` (its brand-mix derivation rules).
- **Yuyu boards**: `references/yuyu/*.png`, measured in `docs/design-revamp/research/ux-yuyu-spec.md`.

Every colour below is one of these: a brand hex, a **brand-mix** (a per-channel sRGB mix of brand
colours, rounded, using the same `blend()` as `lib/brandColours.ts`), or the existing Yuyu danger
values. Fonts are Gilroy 400–700, plus Unbounded 500–600 for one accent phrase per layout. Icons are
`lucide-react`. There are no emoji, no stock images, no shadows on cards, and no invented hues. All
contrast ratios are WCAG 2.x, computed with the luminance function in `lib/brandColours.ts`. That
function reproduces the PDF's own tested pairs: cream on teal 5.68, ink on citron 13.23, ink on
orange 5.51.

---

## 0. Decisions at a glance

| # | Decision | Source |
|---|---|---|
| W1 | The landing page opens with **one full Maker Teal colour field** (rounded r28). It holds the Unbounded phrase "Less searching. More making." in cream, the Citron search bar, and a **cropped open-box facet pair** (an Orange top and a Warm Yellow face) in the bottom-right corner. The field is identical in light and dark. | p.13 (teal field + Unbounded "Make room." + orange/yellow facets cropped at the edge), p.1, p.16 (Citron search bar), Yuyu Y11 brand panel r28 |
| W2 | **Facets, never the logo.** Graphic accents reuse at most **two** facet paths taken verbatim from the symbol master (`logoMasters.symbol.paths[2]` top diamond, `[1]` right face), recoloured with brand fills. The assembled logo is never recoloured, rotated, stretched or animated. | p.13 "Use flap shapes as quiet accents. Keep the logo itself intact." p.8 (all six don'ts) |
| W3 | **Colour fields are scoped token islands.** Each field is a class that redefines the tokens of its subtree, so existing buttons, links, inputs and focus rings recolour themselves without new variants. The four fields are `.sw-field-teal`, `.sw-field-citron`, `.sw-island-dark` and `.sw-field-brand`. | p.7 (the four documented logo grounds: cream, white, Deep Ink, Teal) |
| W4 | The sign-in brand panel is a **Deep Ink island** in light mode (the p.1 cover) and a **Maker Teal field** in dark mode (p.7 #04 "Reversed / teal"). Either way it carries the Unbounded phrase, the existing product showcase cards, and the facet pair. Only one logo appears per screen. | p.1, p.7, Yuyu Y11/P22 |
| W5 | The **About** page opens with a **Citron field** (p.2 composition): ink type, teal caps eyebrow, teal primary. It is identical in both modes. | p.2, p.5, p.11, p.15 (Citron pages) |
| W6 | **Dark surfaces are rebuilt as "teal-lit ink".** Each surface is Deep Ink plus Maker Teal plus a little Cream, replacing Deep Ink plus Cream. Today's mixes are grey-beige, which reads as a muddy inversion. The new ones stay in the brand's green-teal hue family, with crisper borders. Every text pair is ≥4.73:1, up from the owner pass's 4.60. | p.1, p.16 (Deep Ink grounds); `ui-brand-spec.md` brand-mix rule "a brand accent with Deep Ink / Cream" |
| W7 | In dark mode the **focus ring becomes Citron**: 13.23 on bg, 9.75 on panel, 5.52 on the teal field. | p.9 Citron "fresh fields"; SC 2.4.11/1.4.11 |
| W8 | **Small status marks are solid brand fills with ink labels in both modes.** That covers pills, avatars, date chips and identity tiles, and matches p.16, which draws "12 available" in Citron, "2 left" in Orange and "24 available" in Sky on the dark page. Large tinted areas (callouts, result cards) keep the dark `*-soft` + `*-ink` pairing. | p.10 tested pairs, p.16 |
| W9 | The **hero Citron search bar stays Citron in dark mode**, with ink text at 13.23. The console `FilterBar` in dark gets a Citron 1 px boundary and a Citron icon on a surface fill. Today it becomes an anonymous grey box, which is where the brand disappears. | p.16 (Citron search on the dark page) |
| W10 | **Motion is entrance-only, page-level and done once.** Facets slide in along their own isometric axis, and showcase cards rise into place. There is no hover translate or scale, which keeps the existing system rule. With `prefers-reduced-motion: reduce`, everything renders in its final state with no animation. | `ui-brand-spec.md` §E motion; Yuyu P22 floating cards |

---

## 1. What each source contributes

### 1.1 Brand guideline pages

| Page | Device taken | Where it is used |
|---|---|---|
| p.1 Cover | A Deep Ink field with the reversed stacked lockup and a big cream Unbounded "Less searching. More making."; cream app-icon tile | Light-mode sign-in brand panel (Deep Ink island); hero type scale up to 76/80 |
| p.2 Brand | Citron field, ink Gilroy statement type, small caps teal labels ("OUR PURPOSE") | About-page Citron field and its eyebrow |
| p.3 Open invitation | The open box as "Open · Organized · Energetic": "Teal grounds it. Orange gets it moving." | Teal fields as ground, Orange facets as the only "moving" element |
| p.4 Flexible family | Horizontal lockup for **narrow headers**, symbol for **recognition at a glance**, reversed on dark | Header logo rules (§2.4) |
| p.5 Room to breathe | Clear space H÷4 (already implemented by `SpaceWorksLogo` padding) | No logo inside a field closer than H÷4 to an edge or text |
| p.6 Keep it legible | Symbol ≥48 px, lockup ≥180 px | Phone header uses the 48 px symbol; ≥640 uses the 298 px horizontal lockup (its 48 px-symbol floor) |
| p.7 Right background | Four grounds: full colour on cream, ink one-colour on white, reversed on Deep Ink, reversed on Teal | `SpaceWorksLogo ground="dark"` inside the ink and teal fields |
| p.8 System intact | Don't stretch, rotate, recolour panels, lose dark panels, add effects, or change the type | Facets are separate shapes (W2); the logo is never animated; full-colour artwork is never placed on Deep Ink |
| p.9 Seven colours | Exact sRGB values | Every fill in this spec |
| p.10 Readable by design | Tested pairs; "Add a word or icon to every status"; avoid orange text on cream (2.47) | W8 solid pills; no orange text anywhere |
| p.11 Two fonts | Gilroy leads; Unbounded Medium/Semibold, **one accent per layout** | One `font-accent` element per screen (§2.3) |
| p.12 Lean type scale | Display 72/76, Heading 48/52, Subheading 32/38, Body 16/24, Label 14/20, Accent 48/56 | §2.3 type steps |
| p.13 Built from the box | Teal field + Unbounded "Make room." + **orange diamond and yellow face cropped at the field's corner**; "Use one bold moment. Align to a simple grid. Let empty space do its job."; colour balance: neutral first, accent second | W1, W2, the facet component, and the rule of one field per page |
| p.14 Useful details | 24 px grid, 2 px stroke, rounded icons; imagery should show the real space (no clichés) | lucide icons at 24/2; tenant cover photos shown as-is; no stock art |
| p.15 Voice | "Find the right part." / "No parts added yet. Add your first item." / "Couldn't save. Try again." Brand name "Space Works", wordmark "space works" | Empty-state and loading copy (§3.6) |
| p.16 Calm where it counts | Deep Ink page, Citron sidebar, Citron search bar, solid Citron/Orange/Sky status tags, teal "+ Add item" | W8, W9, dark console sidebar active state |
| p.17 A place for every part | White card with Gilroy ID text and a Citron shelf tag | Space cards: name first, code second |

### 1.2 Yuyu boards (measurements from `ux-yuyu-spec.md`)

| Board / screen | Pattern taken | Where |
|---|---|---|
| *Sign in, invites & account* — Y11 | Split screen: form column 400 wide, centred; brand panel inset 16, **radius 28**, holding a 40 bold headline and 2–3 real product cards rotated −3°/+2° with soft shadows; fixed order: mode switch → social → divider → fields → primary → legal | AuthLayout (§4.1); the r28 radius reused for the landing teal field |
| *Sign in…* — Y12–Y15 | Centred task card 440/480, r20, 32 padding, logo top-left | CenteredCardLayout and the RouteFallback "Opening Space Works…" card (§4.4) |
| *Attending an event* — Y18/Y19 | Public chrome: brand left, nav, "Sign in" outline pill right; a ~70 px public title; Y19 tenant theming recolours only the title, chip tint and primary; footer "Powered by …" | Landing/public header (§3.1), public catalogue top (§5) |
| *Organiser workspace* — Y1, Y4 | Org cards on the home screen; **dashed empty state with one sentence, no illustration** (P17) | Space cards (§3.4); empty states unchanged in form (§3.6) |
| *Organiser workspace* — Y1–Y10 sidebar | Sidebar a step darker than the canvas, right hairline, 40–44 px items | Dark sidebar token (§6) |

---

## 2. Shared building blocks (build these first)

### 2.1 Colour fields: scoped token islands (new, `frontend/src/styles/fields.css`)

Each field redefines only the tokens its children read, so `desk-button*`, `ActionControl`, `FilterBar`,
links and focus outlines need no new variants. Fields are flat, with no shadow (p.16 "Quiet surfaces").

```css
/* Teal field — p.13, p.7 #04. Identical in both modes. */
.sw-field-teal, :root.dark .sw-auth-brand:not(.sw-field-brand) {
  background: rgb(0 110 99); color: rgb(255 244 232);
  --color-panel: 0 110 99;  --color-surface: 0 110 99;  --color-hover: 2 103 93;
  --color-ink: 255 244 232; --color-muted: 255 244 232;          /* cream on teal 5.68 */
  --color-line: 102 164 152;                                      /* Teal + 40% Cream, decorative 2.15 */
  --color-outline: 255 244 232;                                   /* control boundary 5.68 */
  --color-focus: 223 255 143;                                     /* Citron ring on teal 5.52 */
  --color-accent-ink: 255 244 232; --color-accent-soft: 2 103 93; /* ghost buttons */
}
/* Citron field — p.2/p.5/p.11/p.15. Identical in both modes (light-token island). */
.sw-field-citron {
  background: rgb(223 255 143); color: rgb(20 44 42);
  --color-panel: 223 255 143; --color-surface: 223 255 143; --color-hover: 203 234 133;
  --color-ink: 20 44 42; --color-muted: 91 104 99;               /* 13.23 / 5.23 */
  --color-line: 182 213 123; --color-outline: 20 44 42;
  --color-focus: 0 110 99;                                        /* teal on citron 5.52 */
  --color-accent-ink: 0 110 99; --color-accent-soft: 203 234 133;
  --color-on-accent: 255 244 232;
}
/* Tenant field — member sign-in: the tenant's derived brand fill, always ≥4.5 for on-brand. */
.sw-field-brand {
  background: rgb(var(--color-brand)); color: rgb(var(--color-on-brand));
  --color-ink: var(--color-on-brand); --color-muted: var(--color-on-brand);
  --color-line: var(--color-on-brand); --color-outline: var(--color-on-brand); --color-focus: var(--color-on-brand);
}
```

**Deep Ink island.** Change the dark token selector in `index.css` from `:root.dark {` to
`:root.dark,\n  .sw-island-dark {`. A subtree with `class="sw-island-dark"` then gets the full dark
token set (including `color-scheme: dark`). Tailwind `dark:` variants do not fire inside it, so the
island must only contain components whose light classes read tokens. AuthShowcase, ListRow and
StatusPill all qualify, because W8 removes their `dark:` overrides. Set `background: rgb(var(--color-bg))`
on the island.

Logo inside any field: pass `ground="dark"` (reversed artwork) inside teal, ink and brand fields, and
`ground="light"` inside citron. `SpaceWorksLogo` otherwise follows the global theme and would draw the
wrong master inside a field.

### 2.2 `BrandFacets` (new, `frontend/src/components/BrandFacets.tsx`, ~45 lines)

A decorative SVG built from the symbol master's facet paths.

```tsx
<BrandFacets size="sm" | "md" | "lg" | "xl" tone="orange-yellow" | "teal" | "orange" className=… />
```

- `aria-hidden="true"`, `focusable="false"`, `pointer-events-none`, `absolute` positioned by the caller.
  The caller's field has `relative overflow-hidden` so the field's rounded corner crops the facets (p.13).
- Paths: `d` strings imported from `logoMasters.symbol.paths[2].d` (top diamond) and `[1].d` (right
  face), in the master viewBox `0 0 136 126`. Use `viewBox="22 16 92 110"` so that only those two facets
  frame. The master's 1.2-unit gap between facets is kept exactly; that gap is the brand's "hairline"
  detail.
- Tones:
  - `orange-yellow`: diamond `rgb(var(--color-emphasis))` (#FF7447), face `rgb(var(--color-warn))`
    (#FFD447). This is the p.13 pairing.
  - `teal`: diamond only, #006E63, for space-card covers.
  - `orange`: diamond only, #FF7447, for the teal cover tile.
- Sizes (rendered diamond width): sm 128 px · md 216 px · lg 360 px · xl 440 px.
- Hard limits:
  - Never more than two facets.
  - Never the full seven-path set.
  - Never rotated, skewed or scaled non-uniformly.
  - Never placed under text. Callers reserve padding so facets sit in empty corner space ("Let empty
    space do its job", p.13).
- Motion: see §2.5.

### 2.3 Type steps (all from p.12; add to `chrome.css` `@layer components`)

| Class | Phone <640 | Tablet 640–1279 | Desktop 1280–1679 | Monitor ≥1680 | Face |
|---|---|---|---|---|---|
| `.sw-hero-title` | 32/40 | 48/56 (p.12 Accent) | 64/72 | 76/80 (p.1 cover size) | Unbounded 600, tracking −0.02em, `text-wrap: balance`, max 12ch |
| `.sw-hero-lede` | 16/24 | 20/28 | 20/28 | 24/32 | Gilroy 500 |
| `.sw-field-heading` (About) | 32/38 | 48/52 (p.12 Heading) | 48/52 | 56/60 | Gilroy 600, tracking −0.015em |
| `.sw-field-eyebrow` | 12/16 caps +0.08em | same | same | same | Gilroy 600, `text-accent-ink` (teal on citron 5.52) |
| Section `h2` | `title-panel` 20/28 | 20/28 | 20/28 | 24/32 | Gilroy 600 |

**One Unbounded element per screen.** That element is `.sw-hero-title` on the landing page and the brand
panel phrase on sign-in. Remove the `[&_h1]:font-accent` wrapper from `LandingPage.tsx`, because the hero
sets the face itself. The `.font-accent` 32/40 override for phones in `chrome.css` stays.

### 2.4 Header logo rule (PublicLayout, central identity only)

| Width | Today | Proposed |
|---|---|---|
| <640 | Stacked lockup 180 on its own row, buttons wrap to two more rows (~340 px of chrome, measured at 375) | **Symbol 48** (p.4 "recognition at a glance", p.6 floor) + "About" + theme icon + "Sign in": **one 72 px row** |
| ≥640 | Horizontal 288 (clamped to its 298 floor) | Horizontal lockup at its floor, **298** (p.4 "narrow headers") |

Pass `liveStatus={<ThemeToggle variant="icon" />}` on the landing and About pages. The text toggle
wraps on phones. The icon variant exists already and has an `aria-label`.

### 2.5 Motion (add to `layouts.css`; all inside `@media (prefers-reduced-motion: no-preference)`)

```css
@keyframes sw-facet-in { from { opacity: 0; translate: 8px 6px; } to { opacity: 1; translate: 0 0; } }
@keyframes sw-rise     { from { opacity: 0; translate: 0 12px; } to { opacity: 1; translate: 0 0; } }
@media (prefers-reduced-motion: no-preference) {
  .sw-facets path { transform-box: fill-box; animation: sw-facet-in 640ms cubic-bezier(.32,.72,0,1) both; }
  .sw-facets path:nth-of-type(1) { animation-delay: 120ms; }   /* diamond */
  .sw-facets path:nth-of-type(2) { animation-delay: 200ms; }   /* face   */
  .sw-auth-showcase > * { animation: sw-rise 480ms cubic-bezier(.32,.72,0,1) both; }
  .sw-auth-showcase > :nth-child(2) { animation-delay: 120ms; }
  .sw-auth-showcase > :nth-child(3) { animation-delay: 240ms; }
}
```

- The facet shift (8, 6) is in SVG user units along the facet's own edge slope, 6/8 ≈ the master's 32/43.
  The flap "opens" outward instead of sliding sideways.
- Use the individual `translate` property, not `transform`. `.sw-auth-showcase` children already carry
  `rotate` (Tailwind) and `transform: rotate()` (layouts.css), and animating `transform` would discard
  their tilt.
- Never animate the headline. It is the LCP element, and p.16 asks for calm.
- Under reduce, the `no-preference` guard means there is no animation at all. The global
  `chrome.css` reduce rule stays as a backstop.
- No hover translate or scale anywhere (`ui-brand-spec.md` §E). Hover remains a colour change: 120 ms,
  border → `outline`, fill → `hover`.

---

## 3. Landing / welcome page (`features/LandingPage.tsx`)

### 3.1 Structure

```
┌ header — canvas (bg-bg), no bar, no bottom border on landing/About ──────────────────────────────┐
│ [space works ▸ horizontal 298 | symbol 48 on phone]          About   [◐]   ( Sign in )          │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ HERO .sw-field-teal  r28 (r20 <768)  relative overflow-hidden ───────────────────────────────────┐
│  Less searching.                     ← h1 .sw-hero-title, cream (5.68)                          │
│  More making.                                                                                    │
│  Find shared tools and your next community workshop.   ← .sw-hero-lede, cream                  │
│                                                                                                  │
│  [⌕  Search by name, code or place              ]  (Clear search)   3 / 3 spaces               │
│   ↑ Citron fill, ink text 13.23, boundary vs teal 5.52        ↑ cream, aria-live                │
│                                                                              ◆ orange diamond    │
│                                                                           ▱ yellow face ← crop │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
  All spaces                                                    ← h2, Gilroy 600 20/28
┌ card ┐ ┌ card ┐ ┌ card ┐ (┌ card ┐ ≥1680)
footer (unchanged links)
```

### 3.2 Breakpoints

| | Phone 390 | Tablet 768 | Desktop 1440 | Monitor 1920 |
|---|---|---|---|---|
| Container | 16 gutters | 24 gutters, max 1168 | max 1192 (existing `sw-layout`) | **max 1440** (landing-only `.sw-landing` override at ≥1680) |
| Hero radius / padding | r20 · 28/20/**128 bottom** | r28 · 48/40/48 | r28 · 64/56 · min-height 440 | r28 · 80/72 · min-height 520 |
| Hero grid | single column | single column, text max 560 | `grid-cols-[minmax(0,7fr)_minmax(0,5fr)]`; text + search in col 1, col 2 empty (facets live there) | same |
| Title | 32/40 | 48/56 | 64/72 | 76/80 |
| Search | full width, h-12 | max-w 560, h-12 | max-w 600, h-14 (56 px; p.16 search is 49 tall at 1312, scaled) | same |
| Facets | `sm`, right −24 bottom −40 | `md`, right −32 bottom −56 | `lg`, right −48 bottom −72 | `xl`, right −56 bottom −88 |
| Cards | 1 col, gap 16 | 2 col, gap 24 | 3 col, gap 24 | 4 col, gap 24 |
| Gap hero → h2 | 32 | 40 | 48 | 56 |

At every size, the 128 px bottom padding on phones and the empty grid column at ≥1280 keep the facets clear
of text and the search bar. That reserved space is the p.13 "empty space".

### 3.3 Hero contents (functions unchanged)

- `h1` "Less searching. More making." This is the **only** h1 and the only Unbounded element on the page.
- Lede "Find shared tools and your next community workshop."
- `<form role="search">` with the same `FilterBar` (`searchLabel="Search makerspaces"`, placeholder "Search
  by name, code or place"), passed a new `variant="hero"` prop. That variant forces the Citron fill in
  **both** modes: classes `bg-success text-on-success placeholder:text-on-success border-transparent`,
  the icon `text-on-success`, and no `dark:` overrides. Ink on citron is 13.23. Inside the teal field
  `--color-focus` is Citron, and with an outline offset of 2 the ring draws on the teal field, so it
  measures Citron-on-teal 5.52.
- "Clear search" (`desk-button`, shown only when the input has text). Inside the field it renders as a cream
  outline on teal automatically.
- `aria-live="polite"` count "`{filtered} / {n} spaces`", cream, `tabular-nums`.
- **Loading and error states:** the hero is static and renders immediately. Only the card grid goes
  through `QueryContent`. This changes `PublicLayout` (§3.7).

### 3.4 Space cards (`LandingSpaces`)

Everything that exists today stays: the cover image or placeholder, the "Public catalogue" pill,
`MakerspaceBrand md`, `MakerspaceMapLink`, `public_code`, and the stretched link "Open catalogue →" with
`aria-label="Open {name} catalog"`.

- Card: `rounded-2xl border border-line bg-panel`, hover `border-outline` (colour only, 120 ms).
  `focus-within` uses the outline-focus ring on the stretched link (existing).
- **Cover placeholder when there is no image.** Replace `bg-brand-soft` plus a large letter with a solid
  brand tile chosen by `identityTone(space.slug)` (the deterministic hash already in `tones.ts`):

| Tone | Tile fill | Initial (Gilroy 700, 64/64; 48/48 <640) | Facet (top-right, `sm`, cropped) |
|---|---|---|---|
| success | Citron #DFFF8F | Deep Ink, 13.23 | teal diamond |
| info | Sky #B5CDFF | Deep Ink, 9.23 | teal diamond |
| warn | Warm Yellow #FFD447 | Deep Ink, 10.37 | teal diamond |
| accent | Maker Teal #006E63 | Warm Cream, 5.68 | orange diamond |

  The tiles are the same in dark mode. Against the dark panel the fills are Citron 9.75, Sky 6.80,
  Yellow 7.64 and Teal 1.76; the teal tile is bounded by the card border `line`. The letter stays
  `aria-hidden`.
- Cover photo when present: show it as-is, `object-cover`, with no filter or overlay (p.8 "no effects",
  p.14 "show the real space").
- "Public catalogue" pill moves to `tone="neutral"` (`bg-surface text-ink`, readable on every tile). A
  success pill on a Citron tile would vanish. The word stays.
- Body: padding 24 (20 on phones). `public_code` in `code-text text-sm text-muted`.

### 3.5 Light vs dark

| Element | Light | Dark |
|---|---|---|
| Canvas | Cream `bg` 255 244 232 | Deep Ink 20 44 42 |
| Header | canvas, full-colour lockup | canvas, reversed lockup (automatic) |
| Hero field | Maker Teal; edge vs cream 5.68 | Maker Teal; edge vs Deep Ink 2.40 (large-area boundary) |
| Search | Citron, ink | Citron, ink (unchanged, W9) |
| Facets | Orange + Yellow | same |
| Cards | white `panel`, `line` border | teal-lit panel 31 67 63, `line` 77 109 103 (1.91 vs panel) |
| Cover tiles | solid brand | solid brand |

### 3.6 Empty, loading and error states (copy follows p.15)

- No matches: the dashed card (Yuyu P17) with "No spaces match '{q}'. Try another name or place." and a
  "Clear search" action. Unchanged.
- None published: "No public spaces yet. They appear here once a space turns on its catalogue."
  Unchanged.
- Loading: three skeleton cards matching the card shape (cover block plus 2 lines), **not** two
  full-width slabs. Use `Skeleton` with the new fill (§7.2).
- Error: "Couldn't load spaces. Try again." with Retry. Unchanged.
- `total === 1` redirects to `/m/{slug}`. Unchanged.

### 3.7 `PublicLayout` change

Add a third member to the `PublicBody` union:
`{ hero: ReactNode; header?: never; children: ReactNode; aside?: never }`. When `hero` is set, render it
in place of `<PageHeader>`, **outside** `QueryContent` (so it never shows a loading state), followed by
`QueryContent` around `content`. The hero must contain the page's one `h1` (tests enforce this).

Also add `chrome?: "bar" | "canvas"` (default `"bar"`). With `"canvas"`, the header is `bg-bg` with no
`border-b`. Landing and About use `"canvas"`; every tenant page keeps `"bar"`.

### 3.8 About page (`features/AboutPage.tsx`)

`PublicLayout width="narrow" chrome="canvas" hero={…}`, with a **Citron field** hero (r28, padding 40/32
on tablet+, 28/20 on phones):

- Eyebrow "About" (`.sw-field-eyebrow`, teal caps)
- `h1` "Open-source makerspace management" (`.sw-field-heading`, ink)
- Lede "Tools to run a community workshop, with care for every handover." (20/28, ink)
- Primary "Browse spaces" (`desk-button-primary`, teal on citron, boundary 5.52)

There is no Unbounded element on this page: the title is long, and p.12 says Unbounded is for short
phrases only. There are no facets either, because citron is already the page's one bold moment. The body
paragraphs, the licence link and the two `ListRow`s stay verbatim. The field is identical in dark mode
(a citron island on Deep Ink, as on p.4).

---

## 4. Sign-in and welcome surfaces

### 4.1 `AuthLayout` (`components/layouts/AuthLayout.tsx`)

```
≥1280  ┌ form column (50%) ───────────────┬ brand panel (50%) inset 16, r28 ────────────────┐
       │ [space works horizontal 298]     │  Less searching.          ← Unbounded 600        │
       │                                   │  More making.              48/56 (≥1680: 64/72) │
       │   Staff console          eyebrow │                                                  │
       │   Welcome back.          h1      │     ╭ Multimeter · Due back Fri ╮   (−3°)        │
       │   (social) ── or … ──            │        ╭ Request #1042 · Ready… ╮  (+2°)        │
       │   Username / Password / Forgot?  │     (✓ Return photo attached)       (−2°)        │
       │   [■■■■■■ Sign in ■■■■■■]         │                                     ◆ facets    │
       └───────────────────────────────────┴──────────────────────────────────────────────────┘
768–1279  120 px brand band above the form: phrase 24/32 left, `md` facets cropped right; no showcase
<768      brand panel hidden (unchanged); stacked lockup 180 above the form
```

- **One logo.** Today the form column shows a stacked 180 lockup and the panel shows a stacked 240 at xl.
  Keep only the form-column logo: horizontal 298 at ≥640 (p.4) and stacked 180 below 640. Remove the
  panel's `SpaceWorksLogo`.
- Panel field:
  - Light: `sw-auth-brand sw-island-dark` (Deep Ink, cream phrase 13.60). The showcase cards render as
    dark-token cards inside the island.
  - Dark: the same markup. `:root.dark .sw-auth-brand` resolves to the teal-field tokens (§2.1), giving
    cream on teal at 5.68. Showcase cards there read `--color-panel` = teal. To keep them as cards,
    scope `.sw-auth-showcase { --color-panel: 31 67 63; --color-line: 77 109 103; }` under
    `:root.dark`. That is the new dark panel, which separates from teal by its `line` border.
- Facets: `BrandFacets tone="orange-yellow"`. Size `lg` at ≥1280 (`xl` at ≥1680), absolute
  right −48 bottom −72. Size `md` in the 120 px band, right −24 bottom −88 (mostly cropped; only the
  diamond tip shows).
- Showcase: the existing `AuthShowcase` content, `aria-hidden` and `inert` (unchanged), with the
  `sw-rise` stagger. The `shadow-overlay` on floating cards stays: Yuyu P22 allows soft shadows on
  floating objects only.
- Form column: unchanged slot order (Yuyu P22) and the existing 400 px max width. Title "Welcome back."
  uses `title-page`, 32/38 at ≥640.

### 4.2 `LoginPanel` (staff)

No logic changes. It keeps:

- eyebrow "Staff console" or "Front desk"
- title "Welcome back."
- divider "or with your username"
- labels "Username" and "Password"
- "Forgot password?" on the label row when email is enabled
- the IdP-only message when password login is off
- the error under the fields with `role=alert`
- "Signing in…" while pending
- the MFA hand-off

It inherits the new panel automatically. `brand.headline` stays at its default, "Less searching. More
making.".

### 4.3 `MemberAuthPanel` (member sign-in and sign-up)

- Pass `brand={{ tenant: tenantBrand, showcase: <AuthShowcase /> }}` (unchanged). In `AuthLayout`, a
  `brand.tenant` switches the panel to `sw-auth-brand sw-field-brand`:
  - The tenant's derived `--color-brand` fill with `on-brand` text. `deriveBrandPalette` guarantees
    ≥4.5. With no tenant override it is Maker Teal plus cream (5.68).
  - The tenant logo (when present) on a 64 px cream tile `rounded-xl bg-[rgb(255_244_232)] p-2`, so any
    uploaded logo reads.
  - The tenant name in Gilroy 600 32/38.
  - Then the Unbounded phrase.
- **No Space Works facets on tenant panels.** The facets are Space Works' own mark and would clash with
  a tenant colour.
- Keep everything else verbatim:
  - the mode switch (only when self-serve)
  - the "This space doesn't run self sign-up…" line
  - the `desk-button-brand` primary
  - Verify email (`CenteredCardLayout`)
  - the `SupportContact` footer rendered by `MemberArea`
- The e2e heading "Member sign in" stays.

### 4.4 Centred cards and the first-run welcome

`CenteredCardLayout` covers RouteFallback "Opening Space Works…", reset password, verify email, MFA,
invites, the change-password gate and access denied. It already follows Yuyu Y12–Y15. Changes:

- Logo: horizontal 298 at ≥640, stacked 180 below.
- The loading body uses the fixed `Skeleton` fill (§7.2). Today two beige or grey slabs fill the card.
- The `media.banner` tone tile uses `toneSurfaceClasses` (soft in dark), because it is a large area.

No other first-run or setup "welcome" surface exists in `features/`. `SetupChecklist` is FROZEN to the
shell lane. The staff home greeting picks up the dark tokens only.

---

## 5. Public makerspace home top (`PublicLayout` bar + `PublicInventoryPage`)

These pages are tenant-branded (Yuyu Y19), so Space Works fields and facets do **not** appear here.

- Header bar: keeps `chrome="bar"`. Fix the phone layout as in §2.4: tenant brand plus "Sign in" on row
  one, and the nav row scrolls horizontally on row two (as today).
- Title "Borrow tools from {name}": `text-brand-ink` (Y19 recolours the title). `deriveBrandPalette`
  guarantees ≥4.5 against bg, surface, panel, hover and every soft.
- Search card: keep the `Card`, the "Search inventory" label, the submit button "Search"
  (`desk-button-brand`) and "Clear". Give the input the p.16 treatment: `bg-success text-on-success
  border-transparent placeholder:text-on-success` in **both** modes (W9). The submit model is unchanged.
- Category chips, the sticky request card and the product cards pick up the token and pill changes only.

---

## 6. Dark theme: tokens

### 6.1 Diagnosis (measured in the running app, 1440 and 375, both themes)

1. Surfaces are **Deep Ink + Cream** mixes (3/6/12/17%). Cream pulls the green out, so the panel,
   hover and header read as grey-beige slabs. Examples: the landing cards, the public header bar, and
   the skeletons, which are `bg-line` 86 100 95, the heaviest surface on the page.
2. The **brand disappears in dark mode**:
   - The Citron search turns into a grey box.
   - Status pills turn into 6% tints.
   - The sidebar (27 50 48) is 1.09:1 from the canvas, so the shell reads as a single grey plane.
3. Borders are weak: `line` vs `panel` is 1.67:1, so card edges blur into the canvas.
4. Charts: `--chart-accent` is Maker Teal on a dark panel at 1.68:1, under the 3:1 needed for
   non-text marks.
5. The Spinner arc is `border-t-accent` (teal) on `border-line`: 1.01:1.

### 6.2 Token table (`index.css` `:root.dark` + `.sw-island-dark`). Light tokens are unchanged.

"Teal-lit ink" mixes are `Ink·(1−t−u) + Teal·t + Cream·u`, rounded per channel. "Soft" mixes are
`panel·(1−t) + tone·t`.

| Token | Current | Proposed | Source | Key contrast (proposed) |
|---|---|---|---|---|
| `bg` | 20 44 42 | **20 44 42** (unchanged) #142C2A | brand Deep Ink | cream 13.60 |
| `sidebar` | 27 50 48 | **17 53 50** #113532 | Ink + 14% Teal | cream 12.26 · muted 7.62 · accent-ink 7.42 |
| `surface` | 34 56 53 | **25 57 53** #193935 | Ink + 10% Teal + 3% Cream | cream 11.54 · vs bg 1.18 |
| `panel` | 48 68 65 | **31 67 63** #1F433F | Ink + 16% Teal + 6% Cream | cream 10.01 · vs surface 1.15 |
| `hover` | 60 78 74 | **37 77 72** #254D48 | Ink + 22% Teal + 9% Cream | cream 8.67 · danger 4.95 |
| `line` | 86 100 95 | **77 109 103** #4D6D67 | Ink + 20% Teal + 26% Cream | vs bg 2.60 · vs panel **1.91** (was 1.67) |
| `outline` | 149 154 147 | **147 161 152** #93A198 | Ink + 10% Teal + 55% Cream | vs bg 5.47 / surface 4.64 / panel 4.03 / hover 3.49 (≥3) |
| `ink` | 255 244 232 | unchanged | brand Warm Cream | 13.60 → 8.27 worst (success-soft) |
| `muted` | 189 188 179 | **199 196 186** #C7C4BA | Cream + 24% Ink | worst 5.14 (success-soft), was 4.60 |
| `focus` | 163 196 184 | **223 255 143** #DFFF8F | brand Citron | bg 13.23 · panel 9.75 · hover 8.43 · teal field 5.52 |
| `accent` / `-hover` / `-active` | 0 110 99 / 2 103 93 / 4 97 88 | unchanged | brand Teal (owner pass) | cream label 5.68 / 6.24 / 6.78 |
| `on-accent` | 255 244 232 | unchanged | brand | — |
| `accent-soft` | 45 71 67 | **26 74 69** #1A4A45 | panel + 16% Teal | cream 9.18 · accent-ink 5.56 |
| `accent-ink` | 163 196 184 | **171 200 188** #ABC8BC | Teal + 67% Cream | worst 5.01 · vs panel 6.06 · vs sidebar 7.42 |
| `brand`, `-hover`, `-active`, `on-brand` | = accent set | = accent set | tenant-overridable | — |
| `brand-soft` | 45 71 67 | **26 74 69** | = accent-soft | — |
| `brand-ink`, `brand-boundary` | 163 196 184 | **171 200 188** | = accent-ink | — |
| `emphasis` / `-hover` / `-active` / `on-emphasis` | 255 116 71 / 255 129 87 / 255 142 103 / 20 44 42 | unchanged | brand | ink on orange 5.51 |
| `emphasis-soft` | 60 71 65 | **47 70 64** #2F4640 | panel + 7% Orange | cream 9.35 · danger 5.34 |
| `success` set / `on-success` | 223 255 143 … / 20 44 42 | unchanged | brand | 13.23 |
| `success-soft` | 59 79 70 | **44 80 69** #2C5045 | panel + 7% Citron | **danger 4.73 = worst cell in the matrix** |
| `success-ink` | 223 255 143 | unchanged | brand | worst 8.05 |
| `warn` set / `on-warn` | 255 212 71 … | unchanged | brand | 10.37 |
| `warn-soft` | 60 77 65 | **47 77 64** #2F4D40 | panel + 7% Yellow | muted 5.33 |
| `warn-ink` | 255 212 71 | unchanged | brand | worst 6.31 |
| `info` set / `on-info` | 181 205 255 … | unchanged | brand | 9.23 |
| `info-soft` | 56 76 76 | **42 77 76** #2A4D4C | panel + 7% Sky | muted 5.31 |
| `info-ink` | 181 205 255 | unchanged | brand | worst 5.61 |
| `danger` / `-hover` / `-active` / `on-danger` | 252 165 165 / 253 185 182 / 253 201 195 / 20 44 42 | unchanged | Yuyu (D4) | worst 4.73 |
| `danger-line` | 124 98 97 | unchanged | Yuyu-mix: Ink + 45% #FCA5A5 | 1.95 vs panel (decorative) |
| `sidebar-hover` | 60 78 74 | **37 77 72** | = hover | cream 8.67 |
| `sidebar-active` | 0 110 99 | unchanged | = accent; boundary is `border-accent-ink` at 7.42 vs sidebar | — |
| `--shadow-color` | 20 44 42 | unchanged | brand | overlays only |
| `--chart-accent` (chrome.css) | var(accent) | **dark: var(--color-accent-ink)** | = accent-ink | vs panel 6.06 (was 1.68) |

### 6.3 Full text matrix (proposed dark)

Universal set = bg, surface, panel, hover, sidebar and the five softs. The rule is ≥4.6 everywhere.

| Text \ ground | bg | surface | panel | hover | sidebar | acc-soft | emp-soft | suc-soft | warn-soft | info-soft |
|---|---|---|---|---|---|---|---|---|---|---|
| ink (cream) | 13.60 | 11.54 | 10.01 | 8.67 | 12.26 | 9.18 | 9.35 | 8.27 | 8.58 | 8.55 |
| muted | 8.45 | 7.17 | 6.23 | 5.39 | 7.62 | 5.70 | 5.81 | 5.14 | 5.33 | 5.31 |
| accent-ink | 8.23 | 6.98 | 6.06 | 5.25 | 7.42 | 5.56 | 5.66 | 5.01 | 5.19 | 5.18 |
| success-ink | 13.23 | 11.23 | 9.75 | 8.43 | 11.93 | 8.93 | 9.10 | 8.05 | 8.35 | 8.32 |
| warn-ink | 10.37 | 8.80 | 7.64 | 6.61 | 9.35 | 7.00 | 7.13 | 6.31 | 6.54 | 6.52 |
| info-ink | 9.23 | 7.83 | 6.80 | 5.88 | 8.32 | 6.23 | 6.35 | 5.61 | 5.82 | 5.80 |
| danger | 7.77 | 6.59 | 5.72 | 4.95 | 7.01 | 5.25 | 5.34 | **4.73** | 4.90 | 4.89 |

Fills with labels (unchanged, brand-tested): cream on teal 5.68, hover 6.24, active 6.78; ink on orange
5.51, on citron 13.23, on yellow 10.37, on sky 9.23. Solid pills against the dark panel: Citron 9.75,
Sky 6.80, Yellow 7.64, Orange 4.06. All exceed 3:1, so every pill shape is perceivable as well as
labelled. Field pairs: Citron search on teal 5.52, focus on teal 5.52, focus on the Deep Ink island
13.23, teal field vs cream canvas 5.68, Deep Ink island vs cream 13.60.

Elevation steps (luminance ratio to the layer below): bg → sidebar 1.11, bg → surface 1.18,
surface → panel 1.15, panel → hover 1.16. These match the owner pass. Separation now comes from **hue**
(the layers sit visibly in teal) and from the **stronger `line`** (1.91 vs panel), not from extra
lightness. Lightness is capped because `danger` (fixed Yuyu #FCA5A5) must stay ≥4.6 on `hover`.

### 6.4 Tenant-colour constants that must move in lockstep

`BRAND_SURFACES.dark`, `BODY_TEXT.dark[1]` (muted), `FIXED_INKS.dark[0]` (accent-ink) and
`FIXED_SOFTS.dark` must change in **both** of these files, in the same commit:

- `frontend/src/lib/brandColours.ts`
- `backend/apps/makerspaces/theme_contrast.py` (comment: "Keep this derivation in sync")

The goldens in `lib/brandColours.test.ts` (dark `soft` for `#fff`; dark `ink` for `#004400` and
`#f3c3dd`) and in `backend/tests/makerspaces/test_theme_contrast.py` will shift. Regenerate them from
the new constants. Do not hand-edit. Re-run the 64-colour grid test; it must still accept every colour.

---

## 7. Component-level dark fixes

### 7.1 Status marks: solid in both modes (W8)

- `components/ui/tones.ts`: rename today's map to `toneSurfaceClasses` (kept for **large areas**:
  `Callout`, the `CenteredCardLayout` banner). Add `toneMarkClasses` = the same strings **without** the
  `dark:bg-*-soft dark:text-*-ink` parts.
- Switch these to `toneMarkClasses`: `StatusPill.tsx`, `Avatar.tsx`, `DateChip.tsx`, `IdentityChip.tsx`.
  Keep the `toneClasses` export as an alias of `toneMarkClasses` so other importers resolve unchanged.
- `styles/components.css`: drop the `dark:` overrides from `.chip-available, .status-box-done`,
  `.status-box-active` and `.status-box-pending`.
- Unchanged: `BorrowRequestCard.tsx`, `PublicToolResultCard.tsx` and `PublicToolScanPanel.tsx` keep
  `dark:bg-success-soft dark:text-success-ink`. They are large result blocks, where a solid Citron slab
  in dark would be the glare p.16 warns against.

### 7.2 Other fixes

| File | Fix |
|---|---|
| `components/ui/Skeleton.tsx` | `bg-line` → `bg-line dark:bg-hover`. Dark skeleton goes from the 2.38:1 slab to hover (1.57 vs bg). |
| `components/ui/Spinner.tsx` | `border-t-accent` → `border-t-focus`: teal in light, Citron in dark (9.75 vs panel). |
| `components/ui/FilterBar.tsx` | Add `variant?: "hero" \| "console"` (default console). `hero` is solid Citron in both modes (§3.3). `console` in dark becomes `dark:bg-surface dark:border-success dark:text-ink dark:placeholder:text-muted`, with the icon `dark:text-success`. The Citron boundary is 13.23 vs bg and 11.23 vs surface. |
| `components/shell/Sidebar.tsx` | Search button `dark:bg-surface` → `dark:bg-panel` (the new sidebar is close to surface). Add `border-r border-line` to the `aside` in dark only (`dark:border-r`), matching the Yuyu sidebar hairline. |
| `components/shell/SidebarItem.tsx` | No change. The active item is teal fill + `border-accent-ink` (7.42 vs sidebar) + cream label (5.68), as on p.16. |
| `styles/chrome.css` | `:root.dark { --chart-accent: var(--color-accent-ink); }`. Add the `.sw-hero-*`, `.sw-field-*` type classes (§2.3). |
| `components/layouts/layouts.css` | Motion keyframes (§2.5); `.sw-landing` 1440 max at ≥1680; hero padding and grid classes. |
| `components/SpaceWorksLogo.tsx` | No change. Callers inside fields pass `ground` (§2.1). |
| `index.css` | Dark token values (§6.2); the selector becomes `:root.dark,\n  .sw-island-dark`; `@import "./styles/fields.css";`. |
| `components/ui/DataTable.tsx` | No change (`dark:bg-hover` thead is fine with the new hover). |
| `.desk-input` (components.css) | No change. `dark:bg-surface` gives an inset input on the panel (1.15) with the `outline` boundary at 4.64. |
| Scrollbar (index.css) | No change. The thumb uses `line` (now 2.60 vs bg). |
| Images / placeholders | `ImageThumbnail` falls back to `Avatar tone="accent"` (accent-soft + accent-ink 5.56). No change. Photos get no dimming or filter in dark (p.8, p.14). |

---

## 8. Implementation plan

Ordered so each step is independently testable. Shared files (`index.css`, `styles/*`,
`components/ui/*`, `components/layouts/*`, `lib/brandColours.ts`) are coordinator-owned. Land steps
1–4 before any lane rebases.

1. **Tokens and provenance** (one commit, both stacks):
   - `index.css`: dark values per §6.2; the selector change to `:root.dark,\n  .sw-island-dark`.
   - `lib/brandColours.ts` and `backend/apps/makerspaces/theme_contrast.py`: the §6.4 constants.
   - `lib/brandColours.test.ts`: update the CSS parser (`split(":root.dark,")`), regenerate the dark
     goldens.
   - `backend/tests/makerspaces/test_theme_contrast.py`: regenerate the goldens.
   - `features/members/MemberAreaBranding.test.tsx`: update the dark fixture tokens on line 33.
   - **New** `frontend/src/styles/darkTokens.test.ts`, which parses the `:root.dark` block and asserts:
     - Every text token is ≥4.6 on the §6.3 universal set.
     - `outline` is ≥3 on bg, surface, panel and hover.
     - `focus` is ≥3 on bg, surface, panel, hover and sidebar.
     - **Provenance**: every surface and soft equals its stated brand-mix recomputed from the seven
       brand hexes, so no hand-tuned value can slip in.
2. **Fields and facets:**
   - New `styles/fields.css` (§2.1).
   - New `components/BrandFacets.tsx` + `BrandFacets.test.tsx`. Test that it is `aria-hidden`, renders
     exactly 1–2 `path`s whose `d` strings equal `logoMasters.symbol.paths[2|1].d`, uses no `rotate`
     or `transform` attribute, and ships no assembled seven-path artwork.
   - `layouts.css` motion (§2.5).
   - `chrome.css` type classes and the dark `--chart-accent`.
3. **Primitives:**
   - `tones.ts` split, plus the `StatusPill`/`Avatar`/`DateChip`/`IdentityChip` switch.
   - `components.css` pill classes.
   - `Skeleton`, `Spinner`, the `FilterBar` variant, and the `Sidebar` tweaks.
   - Update the existing tests: `tones` consumers' snapshots (`StatusPill`, `Avatar`, `DateChip`,
     `IdentityChip` tests asserting class strings), `FilterBar.test.tsx` (hero variant classes),
     `Sidebar.test.tsx`.
   - New `tones.test.ts`: `toneMarkClasses` contains no `dark:`; `toneSurfaceClasses` keeps the soft
     overrides.
4. **Layouts:**
   - `PublicLayout.tsx`: the `hero` body variant, `chrome="canvas"`, the phone logo rule (§2.4).
   - `AuthLayout.tsx`: one logo, the panel field classes, tenant panel, facets.
   - `CenteredCardLayout.tsx`: logo rule, banner → `toneSurfaceClasses`.
   - Tests:
     - `PublicLayout.test.tsx`: hero renders outside `QueryContent` (visible while `state.loading`);
       exactly one h1; `chrome="canvas"` has no `border-b`; at <640 the header renders the symbol
       (`data-logo="symbol"`, or `symbol-reversed` in dark).
     - `AuthLayout.test.tsx`: exactly one `[data-logo]`; the panel has `sw-island-dark` (light) or
       `sw-field-brand` when `brand.tenant`; exactly one `.font-accent` element; facets absent on tenant
       panels.
     - `LayoutGallery`/`LayoutResponsive` tests: update expectations if they assert logo variants.
5. **Screens** (public lane):
   - `LandingPage.tsx`: extract `LandingHero` and `SpaceCard` into
     `features/landing/LandingHero.tsx` + `features/landing/SpaceCard.tsx` to stay under ~200 lines.
   - `AboutPage.tsx`, `features/auth/AuthShowcase.tsx` (no content change), `MemberAuthPanel.tsx`
     (none beyond props), `PublicInventoryPage.tsx` (title `text-brand-ink`, Citron input).
   - **New** `features/LandingPage.test.tsx`:
     - one h1 "Less searching. More making." with class `sw-hero-title`
     - the searchbox "Search makerspaces" filters and the live count updates
     - "Clear search" appears or disappears
     - links "About", "Sign in" (`/member`), "License", "Staff sign-in" (`/admin`) all present
     - each card's link `Open {name} catalog` → `/m/{slug}`
     - placeholder tile tone is deterministic per slug
     - `total === 1` navigates
     - loading shows the hero plus skeleton cards, and the error shows Retry
     - axe clean in light and with `document.documentElement.classList.add("dark")`
   - **New** `features/AboutPage.test.tsx`: Citron field present; all existing links kept (licence,
     Browse spaces ×2, Staff sign-in).
6. **e2e:**
   - `e2e/a11y.spec.ts`: add `"/"` and `"/about"` to both colour schemes. The existing staff login and
     member sign-in runs cover the auth panel in both themes, and axe colour-contrast now checks the
     field islands in a real browser.
7. **Docs** (same commit as step 1 or 4):
   - Append the §6.2 table as the new dark column in `docs/design-revamp/research/ui-brand-spec.md` A.1.
   - Add a superseding note at the top of `dark-contrast-owner-pass.md`.
   - Write a `dark-tokens-v3.json` beside the owner-pass JSON (values plus sources), matching its
     format.
   - Sync to the SpaceWorks-Design repo (`tokens/tokens.css` dark block) per the design-repo rule.
8. **Verification:**
   - `./scripts/dev.sh test` (zero reds) and `npx vitest run`.
   - In the browser: 390 / 768 / 1440 / 1920 × light / dark for `/`, `/about`, `/m/alpha-lab`,
     `/m/alpha-lab/admin` (signed out), `/m/alpha-lab/member` (signed out), and one console screen
     (Inventory) to check pills, sidebar, table, skeleton and focus rings.
   - Emulate `prefers-reduced-motion: reduce` once and confirm no animation runs.

## 9. Risks and owner checkpoints

- **W6 changes the dark palette the owner signed off on.** The changes are the surface hue, softs,
  muted, accent-ink and focus. Accent stays the saturated teal the owner asked for. The provenance test
  makes it trivial to revert to the owner-pass constants if they prefer the old hue. Show them the
  Inventory and landing screens side by side before merging step 1.
- **W8 reverses `ui-brand-spec.md` D6** (dark pills were soft + tone-ink). This spec cites p.16 for the
  change. If the owner prefers soft pills, skip step 3's `toneMarkClasses` switch; nothing else depends
  on it.
- **Citron focus ring (W7)** is very visible by design. It sits on an offset, so it never touches a
  Citron fill.
- **Tenant goldens shift** (step 1). The FE and BE constants must land in one commit or the theme
  validator disagrees with the preview.
- **File ownership.** `LandingPage`/`AboutPage`/auth screens belong to `dr-screens-public`. The layouts,
  ui, styles and lib files are coordinator files. Another agent is editing these now, so rebase onto
  their work before step 4.

## Owner decisions (2026-10-15)

- Dark palette: **apply the new Deep Ink + Maker Teal dark surfaces** in this spec.
- Status pills: **solid brand fills in both light and dark** (large callouts keep soft fills).

## Implementation notes (2026-10-16, built on `feature/design-revamp`)

Where the build differs from the text above, the build wins:

- **Hero grid** is `2fr / 1fr` at ≥1280 (not 7/5): Unbounded 600 sets "Less searching." at 9.4em, so the
  phrase needs ~600 px at 64 px to stay on one line. The title is two explicit block lines.
- **Phone header** keeps the responsive lane's menu: symbol 48 + Menu + Sign in on one row; "About" and the
  theme toggle live in the menu below 1024 px.
- **Tenant sign-in panel** shows the phrase and showcase on the tenant brand fill, but not the tenant
  logo/name: the form column already carries `MakerspaceBrand`, so repeating it would be a second identity
  on one screen. Showcase cards are always a Deep Ink island (`.sw-island-dark`) so they read as product
  objects on any field.
- **Public catalogue title** keeps `text-ink` (PageHeader has no title-colour slot); only the search input
  took the Citron treatment.
- **Drift guards**: `backend/tests/test_frontend_theme_contrast.py` now reads `dark-tokens-v3.json` and accepts
  Deep Ink + Teal + Cream mixes for dark neutrals; `frontend/src/styles/darkTokens.test.ts` recomputes every
  dark surface and soft from the brand hexes.
