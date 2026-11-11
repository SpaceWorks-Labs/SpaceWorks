# Space Works brand v1

The [brand guidelines v1.0](space-works-brand-guidelines-v1.pdf) are the source of truth.
This reference summarises the PDF; the product font implementation follows the approved brand kit
described under Typography below.

The design system lives in its own repository,
[SpaceWorks-Design](https://github.com/SpaceWorks-Labs/SpaceWorks-Design) (published at
[spaceworks-labs.github.io/SpaceWorks-Design](https://spaceworks-labs.github.io/SpaceWorks-Design/)):
the PDF and its 17 pages as SVG/PNG, the logo masters, icons, fonts, `tokens/tokens.css` and
`tokens.json`, the Patch mascot and the UI/UX specs (`docs/ui-brand-spec.md`, `docs/ux-spec.md`,
`docs/ux-screens-longtail.md`). The files in this folder, `frontend/public/brand/`,
`frontend/public/fonts/` and `frontend/src/index.css` are byte-for-byte copies or exact
transcriptions of that kit. When the kit changes, copy the new files across; never redraw them here.

Space Works helps teams keep shared parts, tools and materials organised. The identity is clear,
capable, curious and playful. The open box is an invitation: four flaps welcome the next project,
a clear structure gives every part a place, teal grounds it and orange brings energy.

## Where the brand lives in the product

| What | File | Kit source |
| --- | --- | --- |
| Colour tokens, light and dark | `frontend/src/index.css` (`:root` / `:root.dark` / `.sw-island-dark`), mapped one-to-one in `frontend/tailwind.config.ts` | `tokens/tokens.css` (dark surfaces deepened, decision 225) |
| Brand colour fields (teal, citron, ink, tenant) | `frontend/src/styles/fields.css` | brand p.7, p.13 |
| Radius, motion, chart marks | `frontend/src/styles/chrome.css`, `tailwind.config.ts` | `ui-brand-spec.md` §E |
| Buttons, inputs, pills, nav, tabs | `frontend/src/styles/buttons.css`, `components.css` | `ui-brand-spec.md` §B–C |
| Fonts and `@font-face` | `frontend/public/fonts/`, `frontend/src/index.css` | `fonts/` |
| Logo | `frontend/src/components/SpaceWorksLogo.tsx` + `spaceWorksLogoPaths.ts` | `logo/*.svg` |
| Favicon, app icons, social card | `frontend/public/brand/` | `icons/` |
| Patch | `frontend/public/brand/patch/`, `components/delight/NotFoundPatch.tsx` | `mascot/walk*`, `mascot/dark/walk*` |
| Tenant colour derivation | `frontend/src/lib/brandColours.ts` and `backend/apps/makerspaces/theme_contrast.py` | `ui-brand-spec.md` §H.5 |

### Token summary

Every token is a space-separated sRGB triplet used as `rgb(var(--color-x))`. Neutrals are mixes of
Deep Ink with Warm Cream or white; fills are the seven brand hexes plus the one sampled danger red.
No alpha tints: soft fills are opaque.

| Role | Light | Dark |
| --- | --- | --- |
| `bg` / `surface` / `panel` / `hover` | Cream `#FFF4E8` / `#F6ECE0` / white / `#EFE6DB` | Black `#000000` / `#0A1513` / `#12201E` / `#1C312D` |
| `ink` / `muted` | Deep Ink / `#5B6863` | Cream / `#B3B4AA` |
| `line` (hairline) / `outline` (control boundary) | `#D5D0C6` / `#828A83` | `#2E4B45` / `#809B92` |
| `accent` (staff action) · label | Maker Teal · Cream | Maker Teal · Cream |
| `accent-ink` (links, focus in light; = `brand-ink`) | Maker Teal | `#80B1A6` |
| `focus` ring | Maker Teal | Citron |
| `brand` (stranger-facing action; **tenant-overridable**) | = accent | = accent |
| `emphasis` (one bold moment, never tenant-overridable) | Workshop Orange · Ink label | same |
| `success` / `warn` / `info` fills · Ink label | Citron / Warm Yellow / Sky Blue | same |
| `success-ink` / `warn-ink` / `info-ink` (coloured text) | `#536D49` / `#696834` / `#51697B` | `#E9FCAA` / `#FFDE77` / `#CBD9F8` |
| `danger` | `#B91C1C` · Cream label | `#FCA5A5` · Ink label |
| `sidebar` / hover / active item | Citron / `#F2FFD2` / Maker Teal | Deep Ink `#142C2A` / `#20403C` / Maker Teal |
| soft fills (`accent`, `emphasis`, `success`, `warn`, `info`) | `#E0EEEC` / `#FFEEE9` / `#FBFFF2` / `#FFFAE9` / `#F6F9FF` | `#0F2C29` / `#232621` / `#203026` / `#232D21` / `#1D2C2E` |
| `scrim` (dims the page behind dialogs and the camera) | Deep Ink | Black |

Text on a fill uses its `on-*` token; coloured text uses the `*-ink` token, never the fill
(`text-success-ink`, not `text-success`). There is no orange text token. Shape: controls 10 px,
cards 16 px (`rounded-xl` / `rounded-card`), pills fully round, no shadows except `shadow-overlay` on
popovers, menus, dialogs and toasts. Motion: colour 120 ms, no translate or scale on hover,
`prefers-reduced-motion` honoured.

**Dark set: true black, lit by the brand** (owner decision 225, 10 November 2026; brand lift 11 November
2026; calmed 11 November 2026, owner: "professional, clean, and a better dark theme palette"). The page is
pure black `#000` for OLED screens. Raised surfaces are three near-black layers with a faint Maker Teal and
Cream lift, so cards, dialogs and tables read as Space Works ink without turning green or glowing
(`surface` 10 % teal + 4 % cream, `panel` 14 % + 7 %, `hover` 20 % + 11 %; each layer steps 1.1:1 or more
above the one below). The `sidebar` is Deep Ink itself (brand p.16), with `sidebar-hover` Deep Ink
+ 12 % teal + 6 % cream. Softs are the panel plus 16 % teal or 7 % of their fill. The neutrals are brand
mixes over black too: `muted` is Cream 70 % + Teal 8 % (a warm sage, 5.4:1 at worst), links and
`brand-ink` are Teal + 50 % Cream (clearly teal, so a link never reads as muted text), the `line` hairline
is a quiet divider, Teal 28 % + Cream 18 % (2.2:1 on black, 1.8:1 on `panel`: decorative, never the only
thing that identifies a control), and the `outline` control boundary Teal 30 % + Cream 50 % (3:1 or more on
every ground, so inputs and buttons keep their 3:1 edge). Status inks (`success-ink`, `warn-ink`,
`info-ink`) are their brand colour + 30 % Cream so coloured text sits on black without buzzing; status
fills, accent and danger are unchanged. Text is Cream; the focus ring is Citron. Elevation reads from the
layer steps and the hairline, not from shadows,
which are invisible on black (`--shadow-color` is black in dark). The browser chrome colour
(`theme-color`) follows the theme: Cream in light, black in dark. `frontend/src/styles/darkTokens.test.ts`
pins the recipe and the contrast floors (text 4.5:1 on every ground including the sidebar and softs;
focus, control boundaries and chart marks 3:1; the hairline kept between 1.6:1 and 3:1), and the tenant brand derivation
in `frontend/src/lib/brandColours.ts` and `backend/apps/makerspaces/theme_contrast.py` validates against
the same surfaces.

The earlier Deep Ink dark set (`#142C2A` / `#193935` / `#1F433F`) survives as the `.sw-island-dark`
block: the light-mode sign-in brand panel (p.1 cover) uses it, and the dark illustrations in
`frontend/src/assets/illustrations/` and the dark print artwork are drawn in it. The kit's
`tokens/tokens.css` / `tokens.json` in SpaceWorks-Design still carry the Deep Ink dark surfaces and
need the true-black values above synced. The kit's `docs/ui-brand-spec.md` §A.3 dark proposal (accent
`#579C90` with an Ink label) is not used.

**Tenant branding.** A makerspace may set `primary_color` (the `brand` fill) and optionally
`accent_color` (the seed for `brand-ink`). They recolour only stranger-facing surfaces; staff screens,
`accent`, `focus`, `emphasis`, status tones, neutrals and the sidebar always keep the Space Works
palette, and the Space Works logo is never recoloured.

## Logo masters

These supplied outlined vectors are the approved logo masters. The lowercase wordmark is artwork,
not live type. Scale each complete master as one object; never rebuild the lockup with text or CSS.

| File | Use |
| --- | --- |
| [symbol.svg](symbol.svg) | Full-colour symbol on Warm Cream or white |
| [symbol-reversed.svg](symbol-reversed.svg) | Separately drawn cream symbol on Deep Ink or Maker Teal |
| [lockup-stacked.svg](lockup-stacked.svg) | Primary symbol and two-line wordmark on a light ground |
| [lockup-stacked-reversed.svg](lockup-stacked-reversed.svg) | Reversed primary lockup on a dark ground |
| [lockup-horizontal.svg](lockup-horizontal.svg) | Full-colour horizontal lockup for wide headers |
| [lockup-horizontal-reversed.svg](lockup-horizontal-reversed.svg) | Official reversed horizontal lockup on a dark ground |
| [lockup-horizontal-one-colour-ink.svg](lockup-horizontal-one-colour-ink.svg) | One-colour ink horizontal lockup on a light ground |
| [symbol-one-colour-ink.svg](symbol-one-colour-ink.svg) | One-colour ink symbol on a light ground |
| [lockup-stacked-one-colour-ink.svg](lockup-stacked-one-colour-ink.svg) | One-colour ink primary lockup on a light ground |
| [app-icon.svg](app-icon.svg) | Symbol on a Warm Cream tile, nominally 62% of tile height |

Horizontal layouts have their own supplied reversed and one-colour ink masters. Use the reversed
horizontal master on dark grounds, retaining its complete outlined wordmark and symbol; do not
substitute a stacked lockup solely because the ground is dark. The reversed and ink drawings have
their own notches and knocked-out interior: recolouring the full-colour symbol cannot reproduce them.

The vector brand [banner](../banner.svg) uses the stacked master on Warm Cream.
The README banners ([light](../readme/banner.svg), [dark](../readme/banner-dark.svg)) pair the
horizontal master and the app icon (on a white tile) on Warm Cream, and the reversed horizontal master
and the app icon on a Deep Ink card (the `.sw-island-dark` ground kept for dark artwork, decision
227(h)). Gilroy ExtraBold and Outfit text is converted to outlines, because GitHub renders SVG without
webfonts.
The [social card](../spaceworks-logo.png) is 1200 by 630 with a centred 600 px stacked lockup.
The [favicon](../../frontend/public/brand/favicon.svg) is the app-icon artwork. Prepared raster
exports in `frontend/public/brand/` serve 16/32 px favicons, apple-touch 180 and PWA 192/512 icons.
PWA tiles are safe for `any maskable` use.

## Colour

Use these seven exact sRGB colours. Neutral first, accent second; give each layout one bold moment.

| Colour | Hex | Role from the PDF |
| --- | --- | --- |
| Deep Ink | `#142C2A` | Text, structure, depth |
| Maker Teal | `#006E63` | Primary brand, actions |
| Workshop Orange | `#FF7447` | Energy, emphasis |
| Citron | `#DFFF8F` | Fresh fields, short tags |
| Sky Blue | `#B5CDFF` | Supporting information |
| Warm Yellow | `#FFD447` | Small highlights, ink text |
| Warm Cream | `#FFF4E8` | Canvas, breathing room |

Use Cream on Teal (5.68:1), Ink on Cream (13.60:1), Ink on Orange (5.51:1),
Ink on Yellow (10.37:1), Ink on Citron (13.23:1), or Ink on Sky (9.23:1).
Avoid orange text on cream (2.47:1). Status always includes a word or icon alongside colour.
Any product shades must be documented mixes of brand colours, never new logo fills.
The control-plane primary ramp is derived from Teal toward Cream for lighter steps and Ink for darker
steps; both 500 and 600 retain Maker Teal, per the design brief.

## Typography

The PDF assigns Gilroy the primary role and Unbounded short geometric accents. The product follows
the approved brand kit (SpaceWorks-Design, 15 October 2026) with one owner override (9 November 2026):
the repository is AGPL, so only **Gilroy's free weights** ship and Outfit (OFL) carries running text.

- **Gilroy ExtraBold 800** for headings, titles, display numbers and other brand moments (every
  `h1`–`h6` and `font-display` at 600+). **Gilroy Light 300** only for large light display text.
- **Outfit** (variable, 400–700) for all body and UI text: body 400, labels and meta 500, emphasis
  600–700. Machine strings use Outfit with tabular numerals and wider tracking. Preserve the original
  outlined wordmark in all logos; the logo masters here are the kit's Figma exports.
- **Unbounded** for one short accent phrase per layout. Never use it for long copy.

PDF type scale (size / line height): display 72/76, heading 48/52, subheading 32/38, body 16/24,
label 14/20, accent 48/56. Do not substitute other families or a monospace face: machine strings
(IDs, secrets, URLs, pickup codes) use the `.code-text` utility, never `font-mono`.

The faces are self-hosted from `frontend/public/fonts/` (`font-display: swap`, `font-synthesis:
none`); `index.html` preloads Outfit and Gilroy ExtraBold. Outfit and Unbounded are under the SIL OFL
(`frontend/public/fonts/LICENSES/OFL-*.txt`); Gilroy Light/ExtraBold are under the Radomir Tinkov Free
Font EULA (`LICENSES/Gilroy-Free-Font-EULA.txt`). The commercial Gilroy 400–700 files are **not** in the
repository. Print output (certificates, badges, cards) keeps the stored `"Gilroy"` design token but
renders it in Outfit — see `backend/apps/events/certificates/fonts/README.md`. What the Gilroy EULA does
and does not allow, and the redistribution risk, is recorded in `frontend/public/fonts/README.md`.

## Space, sizes and backgrounds

Measure visible artwork. With H equal to symbol height, leave **H/4 clear space on every side**.
Keep the supplied symbol-to-wordmark gap (H/6) and height relationship (1.25 times) intact;
the master already contains these proportions. Clear space lies outside each SVG viewBox.

- Screen minimum: **symbol height 48 px**, **primary lockup width 180 px**. Horizontal product
  lockups also keep symbol height at least 48 px (about 288 px wide).
- Sidebar: stacked 180 px wide with about 16 px clear space; mobile bar: symbol 48 with 12 px clear space.
- Auth panel: stacked 240-320 px wide. Use the reversed master on dark grounds.
- Print starting sizes: symbol 12 mm, primary lockup 40 mm. Proof at actual size.
- Below 48 px, test a dedicated small-size asset. The product uses the supplied app-icon raster
  exports for 16/32 px favicons; check legibility at the final size.

Do not stretch, rotate, recolour panels, lose dark panels, add effects or change the type.
Preserve every panel, internal gap and wordmark proportion. Do not use gradients, shadows or filters.
Keep the artwork clear of neighbouring text and controls.

## Icons and imagery

Icons use a **24 px grid, 2 px stroke, rounded ends and consistent weight**. Lucide React implements
that specification in the product, at a default rendered size of 20 px. Pair unfamiliar icons with
labels; name icon-only buttons and hide decorative SVGs from assistive technology. Use typographic
marks rather than emoji. Show real parts, hands and shared benches in soft daylight, with honest
materials and the work in focus. Avoid staged tech cliches and busy backdrops.

## Patch, the mascot

Patch is an African painted wolf carrying a wrench: the friendly face, never the logo. The kit's
`mascot/README.md` holds the full rules. In the product:

- Use Patch for empty states, onboarding, loading, success moments and 404/error pages; use the logo
  for headers, favicons, app icons and legal pages. Never put Patch inside or beside the box symbol.
- Patch counts as the layout's one bold moment: no Unbounded phrase or orange flap on the same screen.
- Use the files as supplied: no recolouring, filters, shadows, outlines, stretching or CSS mirroring
  (heading left uses the approved `walk-left` art). Do not scale bitmaps past their size.
- On dark surfaces use the `dark/` variants with the Warm Cream sticker border.
- Honour reduced motion with a still frame. Patch is decorative (`aria-hidden`) beside real copy.
- Today Patch appears only on the 404 page (`NotFoundPatch`, light and dark walk sheets in
  `frontend/public/brand/patch/`). Kiosk surfaces never show Patch: the kiosk worker neither precaches
  nor caches `/brand/patch/`. Empty states use the original programme illustrations in
  `frontend/src/assets/illustrations/`.

## Voice

Sound like a helpful maker: clear, warm and specific. Make the next step easy. Use sentence case.
The brand name in copy is **Space Works**; the outlined wordmark stays **space works**.

| Say | Skip |
| --- | --- |
| Find the right part. | Optimize your asset ecosystem. |
| No parts added yet. Add your first item. | Inventory database is empty. |
| Couldn't save. Try again. | Oops! Something went horribly wrong. |

Keep technical names accurate. On shelf labels, put the item name first and details second; test
size and contrast at the intended viewing distance.
