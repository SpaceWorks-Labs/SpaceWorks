# Space Works brand → SpaceWorks UI: design-system spec

Design-system specification. The brand export and typography sections were refreshed from Figma on 15 October 2026. App-specific implementation notes below describe the prior integration, not verification of another repository.

**Binding source rule (owner).** Every visual decision comes from exactly two sources: the brand PDF
(`brand/space-works-brand-guidelines-v1.pdf`) for visual identity, and the Yuyu boards
(`scratchpad/crops/*.png`, summarised in `ux-yuyu-spec.md`) for layout and UX. All existing app
functionality is kept and re-themed. Every token below names its source:

- **brand**: a verbatim brand hex, or white (p.4 and p.16 draw white cards).
- **brand-mix**: a per-channel sRGB mix of brand colours (Deep Ink, Warm Cream, white, or a brand
  accent with one of those). The mix is stated.
- **Yuyu**: a pixel-sampled Yuyu colour. **Yuyu-mix**: a sampled Yuyu colour mixed with a brand neutral.

Nothing else (no OKLCH shifts, no black, no invented hues).

**Reproducibility.** Every number in this document comes from stdlib Python scripts, now copied to
`docs/design-revamp/research/tools/`:

| Script | Job |
|---|---|
| `pdfx2.py` | inflate the PDF objects and page streams |
| `pdf2svg.py`, `logo_list.py`, `logo_build.py` | vector extraction to SVG |
| `brand_tokens_v2.py` | the token derivation and every contrast ratio |
| `brand_contract_v2.py` | the tenant contract plus a 4,096-colour sweep |
| `png.py`, `sample_yuyu.py` | Yuyu pixel sampling |
| `otfinfo.py` | font metrics |

The maths is WCAG 2.x relative luminance. It reproduces the PDF's own tested pairs exactly:

| Pair | Ratio |
|---|---|
| cream on teal | 5.68 |
| ink on cream | 13.60 |
| ink on orange | 5.51 |
| ink on yellow | 10.37 |
| ink on citron | 13.23 |
| ink on sky | 9.23 |
| orange on cream | 2.47 |

**Derivation rules for brand-mix tokens:**

- **Text inks.** Mix the brand colour toward Deep Ink in light mode, or toward Warm Cream in dark mode,
  at the smallest step that reaches **≥4.6:1** on every background in the universal set. The universal
  set is `bg`, `surface`, `panel`, `hover` and the five `*-soft` fills.
- **Soft fills.** `panel` plus 12 % of the tone, stored as an opaque triplet. No alpha anywhere.
- **Hover and active.** Mix the fill 10 % / 20 % away from its label colour (toward Deep Ink when the label
  is cream, toward Cream when the label is ink), so label contrast only rises. One exception: when that step
  is imperceptible (<1.06:1) and stepping toward the label still keeps ≥4.5, it steps toward the label.
  That only happens on the near-white pastels.

---

## 0. Key decisions

| # | Decision | Source / why |
|---|---|---|
| D1 | The light canvas is Warm Cream with white cards. Dark mode is built **only from the brand's reversed pairings**: `bg` = Deep Ink, raised surfaces = Ink mixed with 3/6/11 % Cream, text = Warm Cream, accents = brand. **No black.** | brand p.7 (reversed on Ink / Teal); owner rule |
| D2 | `accent` = **Maker Teal** in light. In dark it is **Teal + 34 % Cream** (#579C90) with Deep Ink labels. | brand-mix. Brand teal on Deep Ink is 2.36:1, under the 3:1 a selected-state fill needs (SC 1.4.11). |
| D3 | `secondary` is renamed **`brand`** (the action colour of a stranger-facing surface; default = accent; tenant-overridable). **`emphasis` = Workshop Orange**: Space Works' own, never tenant-overridable, one bold moment per layout. | brand p.9 "teal = primary · actions; orange = energy · emphasis"; p.13 "use one bold moment" |
| D4 | **Danger comes from Yuyu**, because the brand has no red: `#B91C1C` text/fill, `#991B1B` hover, `#FCA5A5` card border (dark text). | Yuyu org5 danger zone (sampled, C.0) |
| D5 | Solid `*-soft` tokens replace every `bg-{tone}/NN`. **Translucent text is banned.** | Codex (1): `text-on-accent/75` on teal = 3.90:1 |
| D6 | Status = **word** (mandatory) on a soft pill. Light mode uses the brand-tested solid pastel + ink pairs; dark mode uses soft + tone-ink. Icons are optional. | brand p.10 "add a word or icon to every status"; Yuyu P10 tinted pills |
| D7 | **Typography updated by the owner, 15 October 2026:** Gilroy Regular 400 / Medium 500 / Semibold 600 / Bold 700 for all everyday text and headings. Unbounded 500–600 for one short accent phrase. This supersedes the previous Outfit body and free-weight-only restriction. | owner; current Figma p.11–12 |
| D8 | Shape follows the brand's own product mock (p.16, measured): controls r 10, window/cards r 16, tags fully round, **no shadows**, hairlines = Deep Ink @ 18 %. Yuyu asks for pill buttons; one token switches it. | brand p.16 vector; Yuyu P11 |
| D9 | Light-mode sidebar = **Citron field** with Deep Ink labels and a filled teal active item. Dark-mode sidebar = Deep Ink. **The nav is text-only.** Neither the brand mock (p.16) nor Yuyu (org5) puts icons in the sidebar. | brand p.16; Yuyu org5 |
| D10 | Attention counters and low-stock tags use `emphasis` (orange + ink; p.16 "2 left" is an orange tag). `danger` is reserved for destructive actions and errors. | brand p.16 |
| D11 | **No "System" theme option.** The existing Light/Dark toggle stays as it is. | owner |
| D12 | Logo masters are exported directly from the Figma component library into `logo/`. All three horizontal variants are supplied as masters, including reversed and one-colour ink. | current Figma component library |

---

## A. Tokens

### A.1 Full token table, with the source of every value

| Token | Light | Source (light) | Dark | Source (dark) |
|---|---|---|---|---|
| `bg` | `255 244 232` #FFF4E8 | brand | `20 44 42` #142C2A | brand (reversed ground) |
| `surface` | `246 236 224` #F6ECE0 | brand-mix: Cream + 4% Ink | `27 50 48` #1B3230 | brand-mix: Ink + 3% Cream |
| `panel` | `255 255 255` #FFFFFF | brand (white card, p.4/p.16) | `34 56 53` #223835 | brand-mix: Ink + 6% Cream |
| `hover` | `239 230 219` #EFE6DB | brand-mix: Cream + 7% Ink | `46 66 63` #2E423F | brand-mix: Ink + 11% Cream |
| `line` | `213 208 198` #D5D0C6 | brand-mix: Cream + 18% Ink (p.16 rules = Ink @ 18%) | `55 74 71` #374A47 | brand-mix: Ink + 15% Cream |
| `outline` | `130 138 131` #828A83 | brand-mix: Cream + 53% Ink | `119 128 122` #77807A | brand-mix: Ink + 42% Cream |
| `ink` | `20 44 42` #142C2A | brand | `255 244 232` #FFF4E8 | brand (reversed text) |
| `muted` | `91 104 99` #5B6863 | brand-mix: Ink + 30% Cream | `192 190 181` #C0BEB5 | brand-mix: Cream + 27% Ink |
| `focus` | `0 110 99` #006E63 | = accent-ink | `163 196 184` #A3C4B8 | = accent-ink |
| `accent` | `0 110 99` #006E63 | brand | `87 156 144` #579C90 | brand-mix: Teal + 34% Cream |
| `accent-hover` | `2 103 93` #02675D | brand-mix: accent + 10% Ink | `104 165 153` #68A599 | brand-mix: accent + 10% Cream |
| `accent-active` | `4 97 88` #046158 | brand-mix: accent + 20% Ink | `121 174 162` #79AEA2 | brand-mix: accent + 20% Cream |
| `on-accent` | `255 244 232` #FFF4E8 | brand (tested pair 5.68) | `20 44 42` #142C2A | brand |
| `accent-soft` | `224 238 236` #E0EEEC | brand-mix: panel + 12% accent | `40 68 64` #284440 | brand-mix: panel + 12% accent |
| `accent-ink` | `0 110 99` #006E63 | brand | `163 196 184` #A3C4B8 | brand-mix: dark accent + 45% Cream |
| `brand` | `0 110 99` #006E63 | = accent (tenant-overridable) | `87 156 144` #579C90 | = accent (tenant-overridable) |
| `brand-hover` | `2 103 93` #02675D | = accent-hover (tenant-overridable) | `104 165 153` #68A599 | = accent-hover (tenant-overridable) |
| `brand-active` | `4 97 88` #046158 | = accent-active (tenant-overridable) | `121 174 162` #79AEA2 | = accent-active (tenant-overridable) |
| `on-brand` | `255 244 232` #FFF4E8 | = on-accent | `20 44 42` #142C2A | = on-accent |
| `brand-soft` | `224 238 236` #E0EEEC | = accent-soft (tenant-overridable) | `40 68 64` #284440 | = accent-soft (tenant-overridable) |
| `brand-ink` | `0 110 99` #006E63 | = accent-ink (tenant-overridable) | `163 196 184` #A3C4B8 | = accent-ink (tenant-overridable) |
| `brand-boundary` | `0 110 99` #006E63 | = brand-ink | `163 196 184` #A3C4B8 | = brand-ink |
| `emphasis` | `255 116 71` #FF7447 | brand | `255 116 71` #FF7447 | brand |
| `emphasis-hover` | `255 129 87` #FF8157 | brand-mix: emphasis + 10% Cream | `255 129 87` #FF8157 | brand-mix: emphasis + 10% Cream |
| `emphasis-active` | `255 142 103` #FF8E67 | brand-mix: emphasis + 20% Cream | `255 142 103` #FF8E67 | brand-mix: emphasis + 20% Cream |
| `on-emphasis` | `20 44 42` #142C2A | brand (tested pair) | `20 44 42` #142C2A | brand (tested pair) |
| `emphasis-soft` | `255 238 233` #FFEEE9 | brand-mix: panel + 12% emphasis | `61 63 55` #3D3F37 | brand-mix: panel + 12% emphasis |
| `success` | `223 255 143` #DFFF8F | brand | `223 255 143` #DFFF8F | brand |
| `success-hover` | `203 234 133` #CBEA85 | brand-mix: success + 10% Ink | `203 234 133` #CBEA85 | brand-mix: success + 10% Ink |
| `success-active` | `182 213 123` #B6D57B | brand-mix: success + 20% Ink | `182 213 123` #B6D57B | brand-mix: success + 20% Ink |
| `on-success` | `20 44 42` #142C2A | brand (tested pair) | `20 44 42` #142C2A | brand (tested pair) |
| `success-soft` | `251 255 242` #FBFFF2 | brand-mix: panel + 12% success | `57 80 64` #395040 | brand-mix: panel + 12% success |
| `success-ink` | `83 109 73` #536D49 | brand-mix: Citron + 69% Ink | `223 255 143` #DFFF8F | brand |
| `warn` | `255 212 71` #FFD447 | brand | `255 212 71` #FFD447 | brand |
| `warn-hover` | `232 195 68` #E8C344 | brand-mix: warn + 10% Ink | `232 195 68` #E8C344 | brand-mix: warn + 10% Ink |
| `warn-active` | `208 178 65` #D0B241 | brand-mix: warn + 20% Ink | `208 178 65` #D0B241 | brand-mix: warn + 20% Ink |
| `on-warn` | `20 44 42` #142C2A | brand (tested pair) | `20 44 42` #142C2A | brand (tested pair) |
| `warn-soft` | `255 250 233` #FFFAE9 | brand-mix: panel + 12% warn | `61 75 55` #3D4B37 | brand-mix: panel + 12% warn |
| `warn-ink` | `105 104 52` #696834 | brand-mix: Yellow + 64% Ink | `255 212 71` #FFD447 | brand |
| `info` | `181 205 255` #B5CDFF | brand | `181 205 255` #B5CDFF | brand |
| `info-hover` | `165 189 234` #A5BDEA | brand-mix: info + 10% Ink | `165 189 234` #A5BDEA | brand-mix: info + 10% Ink |
| `info-active` | `149 173 212` #95ADD4 | brand-mix: info + 20% Ink | `149 173 212` #95ADD4 | brand-mix: info + 20% Ink |
| `on-info` | `20 44 42` #142C2A | brand (tested pair) | `20 44 42` #142C2A | brand (tested pair) |
| `info-soft` | `246 249 255` #F6F9FF | brand-mix: panel + 12% info | `52 74 77` #344A4D | brand-mix: panel + 12% info |
| `info-ink` | `81 105 123` #51697B | brand-mix: Sky + 62% Ink | `181 205 255` #B5CDFF | brand |
| `danger` | `185 28 28` #B91C1C | Yuyu (sampled #B91C1C) | `252 165 165` #FCA5A5 | Yuyu (sampled #FCA5A5) |
| `danger-hover` | `153 27 27` #991B1B | Yuyu (sampled #991B1B) | `253 185 182` #FDB9B6 | Yuyu-mix: #FCA5A5 + 25% Cream |
| `danger-active` | `133 30 29` #851E1D | Yuyu-mix: #991B1B + 15% Ink | `253 201 195` #FDC9C3 | Yuyu-mix: #FCA5A5 + 45% Cream |
| `on-danger` | `255 244 232` #FFF4E8 | brand | `20 44 42` #142C2A | brand |
| `danger-line` | `252 165 165` #FCA5A5 | Yuyu (sampled, danger-zone card border) | `124 98 97` #7C6261 | Yuyu-mix: Ink + 45% #FCA5A5 |
| `sidebar` | `223 255 143` #DFFF8F | brand (p.16 sidebar) | `20 44 42` #142C2A | brand (Deep Ink) |
| `sidebar-hover` | `242 255 210` #F2FFD2 | brand-mix: Citron + 60% white | `46 66 63` #2E423F | = hover |
| `sidebar-active` | `0 110 99` #006E63 | brand (p.16 active item) | `87 156 144` #579C90 | = accent |
| `--shadow-color` | `20 44 42` | brand (overlays only) | `20 44 42` | brand |

Removed: `--color-accent-bright` (a pastel; cream on it would be 1.97), `--color-secondary*`,
`--color-on-secondary`, `--brand-tint-10/15-alpha`, `--color-danger-ink` (0 call sites, not mapped in
Tailwind). There is **no orange text token**: orange appears only as a fill with an ink label, or as decoration.

### A.2 Computed contrast (text tokens must reach ≥4.5 on every surface they can sit on)

Universal background set: `bg`, `surface`, `panel`, `hover`, plus the five softs (accent, emphasis, success, warn, info).

| Text token | Light: bg / surface / panel / hover · worst soft | Dark: bg / surface / panel / hover · worst soft |
|---|---|---|
| `ink` | 13.60 / 12.64 / 14.75 / 11.95 · 12.37 | 13.60 / 12.52 / 11.49 / 9.84 · 8.08 |
| `muted` | 5.37 / 4.99 / 5.83 / 4.72 · 4.88 | 7.92 / 7.29 / 6.69 / 5.73 · 4.71 |
| `accent-ink` (= default `brand-ink`, `focus`) | 5.68 / 5.28 / 6.16 / 4.99 · 5.16 | 7.83 / 7.21 / 6.61 / 5.67 · 4.65 |
| `success-ink` | 5.30 / 4.93 / 5.75 / 4.66 · 4.82 | 13.23 / 12.19 / 11.18 / 9.58 · 7.86 |
| `warn-ink` | 5.33 / 4.96 / 5.78 / 4.69 · 4.85 | 10.37 / 9.55 / 8.76 / 7.50 · 6.16 |
| `info-ink` | 5.29 / 4.92 / 5.74 / 4.65 · 4.82 | 9.23 / 8.50 / 7.80 / 6.68 · 5.49 |
| `danger` (text and fill) | 5.96 / 5.54 / 6.47 / 5.24 · 5.43 | 7.77 / 7.16 / 6.57 / 5.62 · 4.62 |

The worst cell in the whole matrix is **4.65 in light** (`info-ink` on `hover`) and **4.62 in dark**
(`danger` on `success-soft`). On the light Citron sidebar: ink 13.23, muted 5.23, accent-ink 5.52. On
`sidebar-hover`: ink 14.06, muted 5.55. On the dark Deep Ink sidebar: ink 13.60, muted 7.92.

| Fill · label | Light rest / hover / active | Dark rest / hover / active |
|---|---|---|
| `accent` · `on-accent` | 5.68 / 6.24 / 6.78 | 4.61 / 5.22 / 5.89 |
| `emphasis` · ink | 5.51 / 5.99 / 6.55 | same |
| `success` · ink | 13.23 / 10.99 / 8.99 | same |
| `warn` · ink | 10.37 / 8.66 / 7.11 | same |
| `info` · ink | 9.23 / 7.77 / 6.47 | same |
| `danger` · `on-danger` | 5.96 / 7.66 / 8.80 | 7.77 / 8.99 / 10.06 |

| Non-text (≥3:1) | Light vs bg / surface / panel (/ sidebar) | Dark |
|---|---|---|
| `focus` | 5.68 / 5.28 / 6.16 / 5.52 | 7.83 / 7.21 / 6.61 / 7.83 |
| `outline` (form-control boundary) | 3.27 / 3.04 / 3.55 | 3.62 / 3.33 / 3.06 |
| `accent` as a selected fill (nav pill, tab underline) | 5.68 / 5.28 / 6.16 / 5.52 | 4.61 / 4.25 / 3.89 / 4.61 |
| `danger-line` (decorative card border, Yuyu) | 1.90 vs panel | 2.24 vs panel |
| `line` (decorative hairline) | 1.42 / 1.32 / 1.54 | ink on line 8.67 |

Banned translucent cases (measured): `on-accent/75` on teal is 3.90 and `/80` is 4.22. Cream at 80 % on
danger is 3.90. Orange text on cream is 2.47.

### A.3 Paste-ready `index.css` block

Keep `:root {` and `:root.dark {` byte-exact; the guard finds them as literal strings. Do not put
braces in comments inside these blocks.

```css
  :root {
    color-scheme: light;
    --color-bg: 255 244 232;
    --color-surface: 246 236 224;
    --color-panel: 255 255 255;
    --color-hover: 239 230 219;
    --color-line: 213 208 198;
    --color-outline: 130 138 131;
    --color-ink: 20 44 42;
    --color-muted: 91 104 99;
    --color-focus: 0 110 99;
    --color-accent: 0 110 99;
    --color-accent-hover: 2 103 93;
    --color-accent-active: 4 97 88;
    --color-on-accent: 255 244 232;
    --color-accent-soft: 224 238 236;
    --color-accent-ink: 0 110 99;
    --color-brand: 0 110 99;
    --color-brand-hover: 2 103 93;
    --color-brand-active: 4 97 88;
    --color-on-brand: 255 244 232;
    --color-brand-soft: 224 238 236;
    --color-brand-ink: 0 110 99;
    --color-brand-boundary: 0 110 99;
    --color-emphasis: 255 116 71;
    --color-emphasis-hover: 255 129 87;
    --color-emphasis-active: 255 142 103;
    --color-on-emphasis: 20 44 42;
    --color-emphasis-soft: 255 238 233;
    --color-success: 223 255 143;
    --color-success-hover: 203 234 133;
    --color-success-active: 182 213 123;
    --color-on-success: 20 44 42;
    --color-success-soft: 251 255 242;
    --color-success-ink: 83 109 73;
    --color-warn: 255 212 71;
    --color-warn-hover: 232 195 68;
    --color-warn-active: 208 178 65;
    --color-on-warn: 20 44 42;
    --color-warn-soft: 255 250 233;
    --color-warn-ink: 105 104 52;
    --color-info: 181 205 255;
    --color-info-hover: 165 189 234;
    --color-info-active: 149 173 212;
    --color-on-info: 20 44 42;
    --color-info-soft: 246 249 255;
    --color-info-ink: 81 105 123;
    --color-danger: 185 28 28;
    --color-danger-hover: 153 27 27;
    --color-danger-active: 133 30 29;
    --color-on-danger: 255 244 232;
    --color-danger-line: 252 165 165;
    --color-sidebar: 223 255 143;
    --color-sidebar-hover: 242 255 210;
    --color-sidebar-active: 0 110 99;
    --shadow-color: 20 44 42;
  }
  :root.dark {
    color-scheme: dark;
    --color-bg: 20 44 42;
    --color-surface: 27 50 48;
    --color-panel: 34 56 53;
    --color-hover: 46 66 63;
    --color-line: 55 74 71;
    --color-outline: 119 128 122;
    --color-ink: 255 244 232;
    --color-muted: 192 190 181;
    --color-focus: 163 196 184;
    --color-accent: 87 156 144;
    --color-accent-hover: 104 165 153;
    --color-accent-active: 121 174 162;
    --color-on-accent: 20 44 42;
    --color-accent-soft: 40 68 64;
    --color-accent-ink: 163 196 184;
    --color-brand: 87 156 144;
    --color-brand-hover: 104 165 153;
    --color-brand-active: 121 174 162;
    --color-on-brand: 20 44 42;
    --color-brand-soft: 40 68 64;
    --color-brand-ink: 163 196 184;
    --color-brand-boundary: 163 196 184;
    --color-emphasis: 255 116 71;
    --color-emphasis-hover: 255 129 87;
    --color-emphasis-active: 255 142 103;
    --color-on-emphasis: 20 44 42;
    --color-emphasis-soft: 61 63 55;
    --color-success: 223 255 143;
    --color-success-hover: 203 234 133;
    --color-success-active: 182 213 123;
    --color-on-success: 20 44 42;
    --color-success-soft: 57 80 64;
    --color-success-ink: 223 255 143;
    --color-warn: 255 212 71;
    --color-warn-hover: 232 195 68;
    --color-warn-active: 208 178 65;
    --color-on-warn: 20 44 42;
    --color-warn-soft: 61 75 55;
    --color-warn-ink: 255 212 71;
    --color-info: 181 205 255;
    --color-info-hover: 165 189 234;
    --color-info-active: 149 173 212;
    --color-on-info: 20 44 42;
    --color-info-soft: 52 74 77;
    --color-info-ink: 181 205 255;
    --color-danger: 252 165 165;
    --color-danger-hover: 253 185 182;
    --color-danger-active: 253 201 195;
    --color-on-danger: 20 44 42;
    --color-danger-line: 124 98 97;
    --color-sidebar: 20 44 42;
    --color-sidebar-hover: 46 66 63;
    --color-sidebar-active: 87 156 144;
    --shadow-color: 20 44 42;
  }
```

`tailwind.config.ts` `colors` maps every token one-to-one. The body blueprint grid, `.blueprint-bg`,
`brutal-*` and `.material-chrome` are deleted.

Palette copies that must move in the same batch:

| File | Change |
|---|---|
| `public/member-pwa/offline.css` | `#1e333f` → `#142C2A`, focus `#f9cd68` → `#A3C4B8` |
| `scripts/member-pwa.ts`, `scripts/kiosk-pwa.ts` | icon rasters come from `app-icon.svg` |
| `public/spaceworks-logo.svg` | replace with `symbol.svg` |
| `index.html` | `theme-color` `#FFF4E8` (light) / `#142C2A` (dark) |
| `backend/config/unfold.py` `COLORS.primary` | a brand-mix ramp: 50–400 = Teal + 90/75/55/35/15 % Cream, 500 = Teal, 600–950 = Teal + 15/30/45/60/75 % Ink |

---

## B. Interaction states

The button family stays closed (`desk-button*`). Every variant keeps `min-h-11` and
`focus-visible:outline-2 outline-offset-2 outline-focus`. The family drops `hover:-translate-y-0.5`,
`hover:shadow-*` and `disabled:opacity-50`. Disabled is explicit: `bg-surface text-muted border-line`
(light 4.99, dark 7.29).

| Variant | Rest | Hover | Active | Light r/h/a | Dark r/h/a |
|---|---|---|---|---|---|
| `desk-button-primary` (staff main) | `bg-accent text-on-accent` | `bg-accent-hover` | `bg-accent-active` | 5.68 / 6.24 / 6.78 | 4.61 / 5.22 / 5.89 |
| `desk-button-brand` (ex `-secondary`; public/member main) | `bg-brand text-on-brand border-brand-boundary` | `bg-brand-hover` | `bg-brand-active` | default = primary; tenants proven by H.5 | |
| `desk-button` (neutral; the Yuyu outline "secondary") | `bg-panel text-ink border-line` | `bg-hover` | `bg-line` | 14.75 / 11.95 / 9.60 | 11.49 / 9.84 / 8.67 |
| `desk-button-ghost` | `text-accent-ink`, no fill | `bg-accent-soft` | `bg-accent-soft text-ink` | 6.16 / 5.16 / 12.37 | 6.61 / 5.60 / 9.72 |
| `desk-button-emphasis` (new; the one bold public CTA, never in staff chrome) | `bg-emphasis text-on-emphasis` | `-hover` | `-active` | 5.51 / 5.99 / 6.55 | same |
| `desk-button-danger` (final confirm) | `bg-danger text-on-danger` | `bg-danger-hover` | `bg-danger-active` | 5.96 / 7.66 / 8.80 | 7.77 / 8.99 / 10.06 |
| `desk-button-danger-outline` (new; Yuyu "Delete organisation…") | `bg-panel text-danger border-danger` | `text-danger-hover border-danger-hover` | same + `bg-hover` | 6.47 / 8.31 / 6.73 | 6.57 / 7.79 / 6.68 |
| `desk-button-success` / `-warn` (kept in Phase 1, folded into primary/neutral in Phase 6) | `bg-success\|warn text-on-*` | `-hover` | `-active` | 13.23/10.99/8.99 · 10.37/8.66/7.11 | same |

| Element | Rest | Hover | Selected / current | Ratios (light · dark) |
|---|---|---|---|---|
| Sidebar item (text-only, D9) | `text-ink` on `sidebar` | `bg-sidebar-hover` | `bg-sidebar-active text-on-accent font-semibold`, `aria-current="page"` | 13.23 / 14.06 / 5.68 (pill vs field 5.52) · 13.60 / 9.84 / 4.61 (pill vs field 4.61) |
| Sidebar sub-item (Yuyu org5: indented, smaller) | `text-muted` 14/20 | `text-ink` | `text-ink font-semibold`, no fill | 5.23 · 7.92 |
| Underline tab | `text-muted` | `text-ink` | `text-ink font-semibold` + 2 px `accent` underline | underline 5.68 · 4.61 |
| Segmented control | track `bg-surface border-line` | `text-ink` | thumb `bg-panel border-outline text-ink` | thumb boundary 3.55 · 3.06 |
| Table / list row | `bg-panel` | `bg-hover` | `bg-accent-soft` + checked box | 14.75 / 11.95 / 12.37 · 11.49 / 9.84 / 9.72 |
| Input | `bg-panel border-outline text-ink`, placeholder `text-muted` | `border-ink` | focus: `border-accent` + ring | boundary 3.55 · 3.06 |
| Search field (p.16 citron field) | `bg-sidebar border-transparent`, `Search` icon | `bg-sidebar-hover` | ring | text 13.23, placeholder 5.23 · dark `bg-surface` |
| Invalid field | `border-danger` + message `text-danger` | | | 6.47 · 6.57 |
| Link | `text-accent-ink`, underline on hover | | | 5.68 · 7.83 |
| Theme toggle | **Light / Dark only** (D11) | | | |

Counters (unread, cart): `bg-emphasis text-on-emphasis` (5.51), at full opacity.

---

## C. Status pills

**C.0 Yuyu samples** (from `crops/org5-settings.png` using `png.py`; exact pixel values):

| Colour | Where | Matches |
|---|---|---|
| **#991B1B** (153,27,27) | "Delete organisation" heading | Tailwind red-800 |
| **#B91C1C** (185,28,28) | button text and 1 px border | red-700 |
| **#FCA5A5** (252,165,165) | 1 px card border | red-300 |
| **#15803D** (21,128,61) and **#DCFCE7** | the dominant greens in `full-att11.png` | green-700 / green-100 |

The greens are **not used**: Citron covers success (owner preference).

**Shape** (Yuyu P10 + brand p.16): fully round, 24 px tall (32 on public), 12/16 semibold, horizontal
padding 8–10. The **word is mandatory and the icon is optional.** Neither source shows icons in pills.

| Tone | Light | Dark |
|---|---|---|
| success | `bg-success text-on-success` (13.23) | `bg-success-soft text-success-ink` (7.86) |
| warn | `bg-warn text-on-warn` (10.37) | `bg-warn-soft text-warn-ink` (6.53) |
| info | `bg-info text-on-info` (9.23) | `bg-info-soft text-info-ink` (5.89) |
| emphasis | `bg-emphasis text-on-emphasis` (5.51) | same |
| accent | `bg-accent-soft text-accent-ink` (5.16) | same (5.60) |
| danger (Yuyu danger-zone vocabulary) | `bg-panel border border-danger-line text-danger` (6.47) | same (6.57) |
| neutral | `bg-surface border border-line text-ink` (12.64) | same (12.52) |

| Domain · status (backend value) → tone · word |
|---|
| **Request:** `draft` neutral "Draft" · `pending_approval` warn "Pending approval" · `accepted` info "Accepted" · `rejected` danger "Rejected" · `issued` **accent** "Issued" (today `danger`, must be fixed) · `partially_returned` warn "Partly returned" · `returned` success "Returned" · `closed_with_issue` danger "Closed with issue" |
| **Loan / self-checkout:** `checked_out` accent "Checked out" (today danger) · `returned` success. **Return condition:** `no_issue` success · `needs_fix` warn · `damaged` danger · `missing` danger |
| **Asset:** `available` success · `reserved` info · `issued` accent · `maintenance` warn · `damaged` danger · `lost` danger · `retired` neutral |
| **Public availability:** Available success "N available" · Limited **emphasis** "N left" (p.16) · Unavailable neutral |
| **Event:** `draft` neutral · `published` success · `cancelled` danger · `completed` info |
| **Registration:** `pending_approval` warn · `registered` success · `waitlisted` info · `rejected` danger · `cancelled` neutral · `attended` accent |
| **Booking:** `pending` warn · `confirmed` success · `rejected` danger · `cancelled` neutral · `completed` info · `no_show` danger "No-show" |
| **Payment:** `pending` warn "Unpaid" · `paid_online` success "Paid online" · `paid_offline` success "Paid offline" · `waived` info · `canceled` neutral "Cancelled" |
| **Refund:** `pending` warn · `succeeded` success · `failed` danger |
| **Machine:** `idle` success "Available" · `running` accent · `reserved` info · `maintenance` warn · `offline` neutral |
| **Service request:** `pending` warn · `accepted` info · `in_progress` accent · `completed` success · `collected` neutral · `rejected` danger · `failed` danger |
| **Certificate:** `pending` warn · `rendering` info · `active` success · `failed` danger · `revoked` neutral |

Copy changes ("Unpaid", "Partly returned", "N left") need owner sign-off. The other words keep the backend labels.
`StatusStepper`: completed = success, current = `accent-soft` + `aria-current="step"`, issue = the danger
pill, upcoming = neutral.

---

## D. Typography

### D.1 Faces and roles

| Role | Family | Weights | Files |
|---|---|---|---|
| Headings and titles | Gilroy | 600, 700 | `Gilroy-SemiBold.woff`, `Gilroy-Bold.woff` |
| Body, labels, controls and IDs | Gilroy | 400, 500, 600, 700 | `Gilroy-Regular.woff`, `Gilroy-Medium.woff`, plus the heading files |
| One short expressive accent | Unbounded | 500, 600 | `Unbounded-Variable.woff2` |

The four Gilroy files were converted from the owner's installed fonts without subsetting or changing outlines.
See `fonts/README.md` for provenance. Legacy Gilroy 300/800 and Outfit files remain for compatibility;
they are not the defaults for new surfaces. The logo wordmark is supplied as vector outlines.

### D.2 Self-hosted CSS

Import `tokens/tokens.css`. Use `var(--font-sans)` for body and `var(--font-display)` for headings.
Both resolve to Gilroy. `var(--font-accent)` resolves to Unbounded with Gilroy as fallback.
Use explicit line heights and `font-synthesis: none`. IDs and code use Gilroy with tabular figures,
not a separate monospace family. Keep `pre` text wrapping on narrow screens.

### D.3 Type scale tokens (family + weight)

| Token / class | Size / line | Family · weight | Tracking | Use |
|---|---|---|---|---|
| `text-display` | 72/76 (mobile 44/48) | Gilroy 600 | −0.02em | public landing hero |
| `text-display-sub` | 32/38 (mobile 24/30) | Gilroy 400 | 0 | optional sub-line under a display/heading on public and auth only |
| `text-heading` | 48/52 (mobile 34/40) | Gilroy 600 | −0.015em | public section heads, auth brand panel |
| `.title-page` (brand Subheading) | 32/38 (mobile 26/32) | Gilroy 600 | −0.01em | one h1 per page |
| `.title-panel` (between Body and Subheading) | 20/28 | Gilroy 600 | −0.005em | card and panel titles |
| `.title-section` | 16/24 | Gilroy 600 | 0 | section titles, list-row titles |
| Stat number / big display number | 32/38 (hero stats 48/52) | Gilroy 600 + `tabular-nums` | −0.01em | `StatCard`, report totals |
| Date-chip numeral | 20/24 | Gilroy 600 + `tabular-nums` | 0 | `DateChip` |
| `text-body` | 16/24 | Gilroy 400 | 0 | body, descriptions, inputs |
| `text-label` | 14/20 | Gilroy 500 | 0 | nav items, form labels, meta, dense table cells |
| Button label | 14/20 (large 16/24) | Gilroy 600 | 0 | `desk-button*` |
| `.col-header` | 14/20 | Gilroy 600, sentence case, `text-accent-ink` | 0 | table headers (p.16) |
| Inline strong / pill emphasis | inherit | Gilroy 700 | 0 | `<strong>`, pill counts |
| `text-caption` | 12/16 | Gilroy 500 | 0.01em | pills, timestamps, helper text |
| `.eyebrow` | 12/16 | Gilroy 600 uppercase | 0.08em | category kicker, `text-muted` (p.17) |
| IDs / shelf codes | inherit | Gilroy 500 + `tabular-nums` | 0 | `text-accent-ink` under a title (p.17), `text-ink` in cells |
| `text-accent` | 48/56 (mobile 32/40) | Unbounded 500 (600 allowed) | −0.01em | **one** phrase per layout: landing hero, auth brand panel, the empty-state hero; never in staff chrome |

### D.4 `font-mono` decision (Codex 4)

There are 235 occurrences on 227 lines in 126 files, plus `.eyebrow`, `.chip` and `.status-box` in CSS.
**Migrate, do not alias.** IDs and codes move to Gilroy with `tabular-nums` (brand p.17 wants clear IDs in the UI family, not a mono). Secrets, digests and JSON use Gilroy with the `.code-text` utility (`font-variant-numeric: tabular-nums slashed-zero; letter-spacing: 0.02em`) — **owner rule: no monospace family** (PLAN §0.4 supersedes this spec). The site lists are in H.6.

---

## E. Shape, borders, shadow, spacing, motion

Measured from the p.16 vector mock (the 1312 × 493 product frame):

| Element | Measurement |
|---|---|
| Window radius | 16 |
| Nav item | 205×49, r 10 |
| Primary button | 197×47, r 9 |
| Search field | 997×49, r 8, Citron |
| Status tags | 34 tall, fully round |
| Row rules | Deep Ink 1 px at opacity 0.18 |
| Shadows | none anywhere |
| Sidebar | 245 wide, 20 px inset, labels inset 19 |
| Nav | text-only |

Yuyu (org5) shows the same pattern: a text-only nav, an active item filled warm grey, sub-items indented, and danger as a white card with a red-300 border.

| Token | Value | Notes |
|---|---|---|
| `--radius-control` | **10px** (brand). Owner may switch it to `9999px` for Yuyu pill buttons. | buttons, nav items, inputs, segmented thumb |
| `borderRadius` sm / DEFAULT / md / lg / xl / 2xl / full | 6 / 8 / 10 / 12 / **16** / 20 / 9999 | `xl` = cards and panels (was 18). `md` (273 uses) 12→10. `lg` (93) 14→12. |
| Borders | 1px `line` on cards and dividers. 1px `outline` on form controls. 2px only for the tab underline and the focus ring. | |
| Shadow | cards none. `shadow-overlay` = `0 2px 6px rgb(var(--shadow-color)/.06), 0 12px 32px rgb(var(--shadow-color)/.10)` for popovers, menus, modals, drawers and toasts only. | `soft`, `soft-lg`, `brutal*` and `elev-*` deleted |
| Spacing | 4 px grid: 4/8/12/16/20/24/32/40/48/64. Page gutter 16 / 24 / 32. Sidebar 256 wide, 20 inset, items 44 tall with a 4 px gap. Card padding 20 (24 on settings). Rows 56 (list) / 48 (table). Every control is 44 tall. | |
| Motion | colour 120 ms. Expand 200 ms. Drawer/modal enter 240 ms `cubic-bezier(0.32,0.72,0,1)`, exit 160 ms. No translate or scale on hover. `prefers-reduced-motion` honoured. | |

---

## F. Logo: exact extraction and in-product use

### F.1 Current master exports

Use `logo/`: ten SVG masters and ten matching transparent 4× PNGs exported directly from Figma.
The app tile includes its cream field. Wordmarks are outlined, so logo rendering does not require font files.
Source component IDs and bounds are in `brand/figma-styles.json`.

| Variant | Full color | Deep Ink | Reversed cream |
|---|---|---|---|
| Primary / stacked wordmark | `lockup-stacked` | `lockup-stacked-one-colour-ink` | `lockup-stacked-reversed` |
| Horizontal | `lockup-horizontal` | `lockup-horizontal-one-colour-ink` | `lockup-horizontal-reversed` |
| Symbol | `symbol` | `symbol-one-colour-ink` | `symbol-reversed` |

Each basename has `.svg` and `.png`. The tenth variant is `app-icon`.

### F.2 Usage

Full-color artwork uses Deep Ink, Maker Teal and Workshop Orange. Reversed artwork is Warm Cream.
The monochrome marks have a hollow opening and transparent fold gaps so all four flaps remain visible.
Use the dedicated variants; recoloring the full-color symbol is not equivalent.
Keep the supplied proportions. Clear space is one quarter of the symbol height on every side.
PNG app icons and the social card are derived from these masters. The editable component source remains in Figma;
`brand/logo-masters.svg` and `.png` are portable reference sheets, not a native `.fig` backup.

### F.3 In-product sizes (rules: symbol ≥48 px; primary lockup ≥180 px wide; clear space H÷4)

| Placement | Artwork | Size | Clear space | Compliance |
|---|---|---|---|---|
| Staff/member **sidebar** (≥1024) | `lockup-stacked.svg` (dark: `lockup-stacked-reversed.svg`) | **180 px wide** → H 63.7 | 16 → logo block 96 px tall | meets both minimums. The horizontal lockup cannot fit: at H 48 it is 288 px, wider than the 256 sidebar. |
| Mobile top bar (<1024) | `symbol.svg` (dark: `symbol-reversed.svg`) | **48 px** | 12 → bar 72 px | the brand symbol variant "recognition at a glance" |
| Public header ≥ 768 | `lockup-horizontal.svg` (dark: `lockup-horizontal-reversed.svg`) | symbol 48 → **300 × 48** | 12 → header 72 | |
| Public header < 768 | `symbol.svg` | 48 | 12 | |
| Auth brand panel | `lockup-stacked.svg` on Cream | 240–320 px wide | ≥ H÷4 | |
| Favicon 16 / 32 | below 48 → **p.6 "test a dedicated small-size asset"**: owner to supply. Interim: `app-icon.svg` rasterised and proofed. | 16, 32 | | **open item** |
| `favicon.svg` | `app-icon.svg` | — | | |
| apple-touch-icon | `app-icon.svg` → PNG | 180 | | |
| PWA member + kiosk | `app-icon.svg` → PNG, `purpose: "any maskable"` | 192, 512 | | maskable-safe (F.2) |
| OG / Twitter | Cream 1200×630, `lockup-stacked.svg` 600 px wide centred | | H÷4 | |
| Django `/control/` (Unfold) | `SITE_LOGO` = `lockup-horizontal.svg` at symbol 48 (288 px, fits Unfold's 288 px sidebar) with the dark variant for dark mode; `SITE_ICON` = `symbol.svg`; `SITE_TITLE` "Space Works" | | | replaces the violet `COLORS` with the A.3 brand-mix ramp |
| Email header (if templates show one) | `lockup-stacked.svg` PNG @2x, 180 px wide | | | |

`SpaceWorksLogo` takes `variant: "symbol" | "stacked" | "horizontal"` and `ground: "light" | "dark"`, and maps
to the extracted files only. It has `role="img"` and `aria-label="Space Works"`, and its size props are
clamped to the minimums (TS types plus a runtime `Math.max`). It never takes `className` colour
overrides and never applies CSS `transform`.

---

## G. Icons

The brand spec (p.14) is a 24 px grid, 2 px stroke, rounded ends, consistent weight, and unfamiliar icons
always labelled. **`lucide-react` is acceptable only as the implementation of that spec**: it is drawn on
a 24 grid with 2 px stroke and round caps and joins. Pin the exact version. Render at 20/16 with default
(relative) stroke. Icon-only buttons need `aria-label` plus a tooltip, and the SVG gets `aria-hidden`.

**Source observations.** Neither the p.16 brand mock nor the Yuyu sidebar (org5, org1) uses nav icons; both
nav lists are **text-only**. Yuyu uses icons only for "View public page ↗", the switcher chevrons,
callouts and back arrows.

**Default: no icons in the sidebar or member tabs.** Icons appear only where a source shows them:

| Use | Icon |
|---|---|
| Search field (p.14 / p.16) | `Search` |
| p.14 brand set | Storage `Archive`, Parts `Cpu`, Location `MapPin` |
| Create actions ("+ Add item", p.16) | `Plus` |
| Back link "← All x" | `ArrowLeft` |
| "View public page ↗" | `ArrowUpRight` |
| Workspace switcher | `ChevronsUpDown` |
| Callouts | `Info` / `TriangleAlert` / `CircleCheck` |
| Overflow | `Ellipsis` |
| Theme toggle | `Sun` / `Moon` |
| Sign out | `LogOut` |

This replaces `components/icons.tsx` and `staffNavIcons.tsx`. The old nav-icon set is deleted.

---

## H. Migration lists

### H.1 Translucency bans (Codex 1)

| Site | Today → measured | Replacement |
|---|---|---|
| `features/staff/panels/DashboardPanel.tsx:77–80,83,91` | `text-on-accent/75` (3.90), `text-on-secondary/75`, `text-on-success/75`, `text-on-warn/75`, `text-bg/80` on danger (3.90), `text-bg` | `StatCard`: a neutral panel with Gilroy-600 number in `text-{tone}-ink` and a full-opacity label. The secondary tone becomes `emphasis`. |
| `features/inventory/PublicInventoryParts.tsx:67` | `text-on-secondary/80` counter (4.22) | `text-on-brand` |
| `components/ui/StatusStepper.tsx:55` | `opacity-70` on fills | full opacity, `text-caption` |
| `features/inventory/RequestSummary.tsx:23,30` | `opacity-80` | `text-muted` |
| `features/staff/panels/OperationsReportState.tsx:74`, `features/stats/StatsParts.tsx:33` | `eyebrow opacity-70` on fills | `StatCard` |
| `features/inventory/ProductCard.tsx:71`, `ProductQuickViewModal.tsx:52` | `text-ink/15` decorative initials | `text-line` + `aria-hidden` |
| `styles/chrome.css` `.material-chrome` | panel @0.8 + blur | delete |
| `components.css` ghost/nav `hover:bg-accent/15`; the `.desk-shell .bg-secondary/10\|15` color-mix block | alpha tints | `hover:bg-accent-soft`; `bg-brand-soft`; delete the color-mix block |
| **119 `bg-{tone}/NN` occurrences in 58 files** (12 of them `hover:`) | alpha tints | `/5`, `/10`, `/15` → `bg-{tone}-soft` (`secondary` → `brand-soft`). **`bg-danger/NN` → `bg-panel border border-danger-line`** (the Yuyu danger card; there is no danger-soft) |
| `border-{tone}/20–40` (≈40) | decorative | allowed; `border-danger/40` → `border-danger-line` |
| `disabled:opacity-50` (14) | WCAG-exempt | allowed outside the button family |

### H.2 Fill tokens used as text, and undefined tokens (Codex 2)

| File:line | Today | Replacement |
|---|---|---|
| `features/members/MemberAdmission.tsx:44`, `MemberArea.tsx:149`, `MemberReferrals.tsx:67,80`, `MemberVerifierPanel.tsx:20` | `text-success` | `text-success-ink` |
| `features/staff/MembershipAdmissionSettings.tsx:70`, `panels/MachineTypesPanel.tsx:100`, `SetupChecklist.tsx:22`, `StaffBookingForm.tsx:63` | `text-success` | `text-success-ink` |
| `features/members/MemberCertifications.tsx:18`, `MemberDashboardSections.tsx:122`, `features/staff/MembershipAdmissionSettings.tsx:56` | `text-warn` | `text-warn-ink` |
| `features/staff/handover/IssueDialog.tsx:59` | `border-warn/40 bg-warn/10 text-warn` | `border-warn bg-warn-soft text-warn-ink` (5.54 light / 6.53 dark) |
| `styles/components.css:191–192` | `hover:text-accent` | `hover:text-accent-ink` |
| `features/staff/PlatformDashboardPanel.tsx` (×5) | `text-brand` (**undefined today**) | `text-accent-ink`. After the rename, `text-brand` would otherwise become a fill used as text. |
| `features/staff/panels/QueuesReturnRequestModal.tsx`, `features/staff/EvidenceRetentionPanel.tsx` | `text-warning` (undefined) | `text-warn-ink` |
| `features/staff/OfflineCheckInOperator.tsx`, `features/staff/EventStationSettings.tsx:44` | `border-warning bg-warning-soft text-warning-ink` (undefined) | `border-warn bg-warn-soft text-warn-ink` |
| `text-danger` (475) | stays | `danger` is text-capable (A.2) |
| `text-info`, `text-secondary`, `text-accent-bright` | 0 sites | — |

### H.3 `text-bg` on a danger fill → `text-on-danger` (9 sites)

`components/ui/Badge.tsx:16`, `features/inventory/AvailabilityBadge.tsx:16`, `panels/machine/MachineTypeCards.tsx:24`,
`panels/machine/SharedConsumablesSection.tsx:31`, `components.css` `.status-box-danger` and
`.desk-button-danger`, and `DashboardPanel.tsx:91`.
The counters in `StaffDock.tsx:209` and `StaffDockPopover.tsx:105` become `bg-emphasis text-on-emphasis`; both files are removed in Phase 3.
Status uses of a danger fill become the danger pill (C).

### H.4 Rename `secondary` → `brand`

Do this as one mechanical commit before any new button variant lands.

| Old | New |
|---|---|
| `--color-secondary`, `-hover`, `-active`, `-boundary` | `--color-brand`, `-hover`, `-active`, `-boundary` |
| `--color-on-secondary` | `--color-on-brand` |
| `--color-secondary-ink` | `--color-brand-ink` |
| `--brand-tint-*-alpha` | removed (replaced by `--color-brand-soft`) |
| `bg-secondary` | `bg-brand` |
| `text-on-secondary` | `text-on-brand` |
| `text-secondary-ink` | `text-brand-ink` |
| `border-secondary` | `border-brand` |
| `bg-secondary/10\|15` | `bg-brand-soft` |
| `desk-button-secondary` (113 / 65 files) | `desk-button-brand` on stranger-facing surfaces; staff sites per the table below |
| Badge `"secondary"`, StatTone `"pink"` | `"emphasis"` |

| Staff/shared site using `secondary` today | Remap (staff never takes the tenant colour) |
|---|---|
| `DashboardPanel.tsx:78,88`, `OperationsReportState.tsx:68`, `stats/StatsParts.tsx:18,105`, `StatusStepper.tsx:6`, `Badge.tsx:18` | `emphasis` / `StatCard` / pill tones |
| `InventoryPanelParts.tsx:198`, `OperationsReportsFablab.tsx:69`, `forms/CustomAnswersView.tsx:5`, `forms/CustomFormBuilder.tsx:16` | `border-line bg-accent-soft` |
| `EventDrawer.tsx:61`, `MakerspaceLocationSettings.tsx:104`, `StaffDock.tsx:29,33` | `text-accent-ink` / `border-accent` |
| `components/MakerspaceMapLink.tsx:17` (shared) | prop-driven: `text-brand-ink` on public pages, `text-accent-ink` on staff pages |
| `desk-button-secondary` in `BillingDocumentsSettings:30`, `KioskStationSettings:82,83,90`, `AccountabilityPanel:191`, `DashboardMachineQueue:34`, `CapabilityPresetListEditor:46`, `MachineCreateForm:199`, `PoolColourSelector:192`, `SharedConsumablesSection:168`, `CardTemplateForm:153`, `DeliveryLogScreen:59,69`, `SuppressionAdmin:27` | `desk-button`, or `desk-button-primary` when it is the screen's main action |
| `LoginPanel.tsx:100` | `desk-button-primary` |
| `MakerspaceThemeSettings.tsx:64` | stays `desk-button-brand` (it previews the tenant colour) |
| Shared `ToastHost:28`, `AnnouncementFeed:18`, `PersonalInbox:62`, `PaymentDocuments:39–52` | `desk-button` (neutral) |

### H.5 Tenant-branding contract (Codex 3)

| Aspect | Contract |
|---|---|
| What a tenant sets | `primary_color` → the `brand` fill; optional `accent_color` → the seed for `brand-ink`. Nothing else. |
| Where it applies | stranger-facing surfaces only: the 10 `useTenantBranding` callers (public inventory, item, events, event feedback, machines, bookings, self-checkout, print request, stats, `MemberArea`) and the Phase-5 `PublicShell`. |
| What it never touches | `accent`, `focus`, `emphasis`, status tones, neutrals, `sidebar`. Staff screens contain zero `brand-*` classes (guard I). |
| Default | `brand` = `accent` per mode. |
| Label | **PLAN v2 §10.1 overrides (owner rule "keep all functionality")**: candidates Deep Ink, Warm Cream, white, then **black** (black is today's label, kept as a functional fallback for tenant-chosen colours only). |
| Hover / active / soft / link ink | the same rules as the product: shift away from the label; soft = strongest ≤12 % mix over `panel` that keeps every fixed text ≥4.55; link ink = `accent_color` (or the fill) mixed toward Ink (light) or Cream (dark) until ≥4.5 on 10 backgrounds. All of these are mixes with brand neutrals. |
| Pairs checked | `on-brand` on brand/hover/active; `brand-ink` on bg, surface, panel, hover, brand-soft and the 5 softs; ink, muted and 5 fixed inks on `brand-soft`; boundary ≥3. **The `on-secondary/80` pair is removed** together with its only call site. |
| Emitted vars (`brandPaletteStyle`) | `--color-brand`, `--color-on-brand`, `--color-brand-ink`, `--color-brand-hover`, `--color-brand-active`, `--color-brand-soft`, `--color-brand-boundary` (7 keys; 8 today) |
| Acceptance (PLAN §10.1) | **Never reject a well-formed colour that today's validator accepts.** Acceptance set ⊇ today's: if a derived pair fails, degrade the derived token (soft → `panel`, link ink → `accent-ink`, hover/active → today's algorithm) instead of rejecting. Rejection only for malformed values. Proven by a sweep test over all 4,096 `#RGB` (with and without `accent_color`) asserting `valid` in both modes, plus a parity test: every colour today's validator accepts is still accepted. |

Changes the contract implies:
- **`lib/brandColours.ts` and `theme_contrast.py`** move in lockstep:
  - `BRAND_SURFACES` is 4 per mode (A.1).
  - `PRODUCT_FILL` is per mode: `[0,110,99]` light, `[87,156,144]` dark.
  - `BODY_TEXT` is light `[20,44,42]`, `[91,104,99]` and dark `[255,244,232]`, `[192,190,181]`.
  - `FIXED_INKS` holds accent-ink, success-ink, warn-ink, info-ink and danger.
  - `FIXED_FILLS` becomes `FIXED_SOFTS` (5 per mode).
  - Label candidates are ink, cream, white, then black (PLAN §10.1).
  - `readBrandTokens` reads `brand`, `on-brand` and the 4 surfaces.
- **`MakerspaceThemeSettings`:**
  - Placeholder → `#006e63`.
  - Copy: "Leave blank to use Maker Teal. Staff screens always use the Space Works palette."
  - Preview grounds use mode ink (`#142C2A` / `#FFF4E8`) instead of hard-coded white/black.
  - Add hover/active swatches and a `brand-soft` card with muted text.

### H.6 `font-mono` migration (Codex 4)

**A. → `.code-text` on Gilroy** (57 sites; machine strings; owner rule — no `font-code`/monospace family).

| Kind | Sites |
|---|---|
| Inputs | `KioskOfflineHandover:70,72`, `KioskOnlineScanner:26`, `MemberCalendarActions:83`, `MemberClaimRedemption:22`, `BillingDocumentsSettings:37`, `DirectLoanIssueFields:214`, `DirectLoanReturnModal:221`, `BulkImport:126`, `EmailTemplateEditor:180,184`, `MaterialCataloguePanel:34`, `ScanCardBox:41`, `ScannerPanel:190`, `PlatformSocialAuthPanel:91`, `SpacePacksPanel:43`, `TenantMigrationExports:107,152`, `TenantMigrationImports:41,162`, `TenantMigrationPairings:64,73,74,75,78,79`, `tenantMigrationUi:63` |
| Display | `BorrowRequestCard:180`, `PublicToolScanPanel:21`, `ApiClientCreateCard:93`, `ApiClientListCard:144`, `ApiClientsAccessSummary:37`, `EventInvitesPanel:20`, `EventPromosPanel:24`, `KioskStationSettings:75`, `MakerspaceCustomDomainSettings:228,230,232`, `MemberClaimCodes:113`, `ModulesPanel:147`, `OrganizationInvitations:51`, `SuppressionAdmin:33`, `AuditLog:55`, `TenantMigrationDisclosure:69,76`, `TenantMigrationExports:128`, `TenantMigrationPairings:60,61,93`, `ResetPasswordModal:64`, `MemberCalendarActions:79`, `EmailTemplateEditor:237`, `OrganizationMemberships:28,29`, `KioskReplayDetail:18`, `EventOrganizers:34`, `OrganizedEventsPanel:85` |

**C. → delete `font-mono`** (30 sites; label voice).
`AppRoutes:37`, `AvailabilityCalendar:40`, `Badge:25`, `AvailabilityBadge:63`, `tenantMigrationUi:40`,
`ImageUploader:190,200,217,229`, `ProcurementReceipts:83`, `WarrantySection:191`,
`MakerspaceCustomDomainSettings:227,229,231` (→ `.eyebrow`), `EmailTemplatesPanel:104`, `MachineTypePage:70`
(→ `.col-header`), `MachinesPanel:164,178`, `MakerspaceLocationSettings:104`, `DirectLoanIssueFields:172`,
`QrTools:176`, `MakerspaceMapLink:17`, `ProductCard:126`, `LandingPage:156`, `PublicInventoryHeader:63`,
`BorrowRequestCard:66`, `ArchivedPayments:46`, and in CSS `.eyebrow`, `.chip`, `.status-box`.

**B. → `tabular-nums`** (the remaining ~143 lines; a codemod).
These are counts, prices, quantities, dates, page counters, `#id`, card and request numbers, box codes,
PINs (keep `tracking-widest`), versions and public codes. They include 8 inputs:
`EventCheckInStationPage:43`, `KioskStationPage:75`, `KioskOnlineHandover:67,74,84`,
`PublicPrintRequestForm:173,187` and `EventFormFields:60`.

### H.7 Other corrections

- `statusToneMap`: `issued` and `checked_out` change `danger` → `accent`. Add every status in C.
- The dashboard and stats tiles become `StatCard`: a neutral panel with the tone carried by the number (Yuyu P4).
- `OperationsReportCharts` marks need ≥3:1 on panel. Light: teal 6.16, info-ink 5.74, success-ink 5.75,
  warn-ink 5.78, danger 6.47. Dark: the brand fills. Orange and the pastels in light mode only appear with a 1 px ink stroke.
- The PLAN's "theme (Light/Dark/System)" in the user menu becomes **Light/Dark** (D11).

---

## I. Contrast-guard changes

**`backend/tests/test_frontend_theme_contrast.py`**

| Change | Detail |
|---|---|
| `TEXT_TOKENS` | `ink, muted, accent-ink, brand-ink, success-ink, warn-ink, info-ink, danger` |
| `BACKGROUNDS` | `bg, surface, panel, hover, accent-soft, brand-soft, emphasis-soft, success-soft, warn-soft, info-soft` (7 × 10 × 2 assertions) |
| new `test_fill_labels` | `on-X` on X / X-hover / X-active ≥4.5 for accent, brand, emphasis, success, warn, info, danger |
| new `test_sidebar` | ink, muted and accent-ink on `sidebar` and `sidebar-hover` ≥4.5; `sidebar-active` vs `sidebar` ≥3; `on-accent` on `sidebar-active` ≥4.5 |
| `test_focus…` | ≥3 on bg, surface, panel, hover and sidebar |
| new `test_control_boundary` | `outline` ≥3 on bg, surface and panel |
| new `test_token_provenance` | parse the A.1 values. Every neutral must equal an integer-percent mix of `20 44 42` with `255 244 232` or white (re-derive and compare). Every fill must be a brand hex or one of the 3 Yuyu reds. Fails on any off-source colour. |
| new source guards (scan `frontend/src`, excluding `*.test.*`) | `\btext-[\w-]+/\d+`; `\bbg-(accent\|brand\|emphasis\|success\|warn\|info\|danger)/\d+`; `\btext-(accent\|brand\|emphasis\|success\|warn\|info)(?![\w-])`; `\bfont-mono\b`; `warning\|accent-bright\|secondary` colour utilities; `brand-` utilities under `features/staff/` (except `MakerspaceThemeSettings.tsx`); `#[0-9a-fA-F]{6}` hex literals outside `lib/brandColours.ts`, `SpaceWorksLogo` and the filament swatches |
| Parser | unchanged (`:root {` / `:root.dark {`, comments stripped) |

**`backend/tests/makerspaces/test_theme_contrast.py`**

| Test | Change |
|---|---|
| imports | `SURFACES` (4 per mode), `PRODUCT_FILL` (per mode), `BODY_TEXT`, `FIXED_INKS` (5), `FIXED_SOFTS` |
| `test_custom_palette_passes…` (`#000 #fff #f3c3dd #004400 #abc` + `#5a1633`) | unchanged; all pass |
| `test_dark_derivation_matches_frontend_golden_values` | `#f3c3dd/#5a1633`: fill (243,195,221) in both modes; **fg (20,44,42)** (was 0,0,0); light ink (90,22,51); **dark ink (207,180,180)** (was 194,169,180). `#004400`: **hover (26,86,23), active (51,103,46), fg (255,244,232)** |
| `test_opaque_aa_is_not_enough_for_existing_translucent_counters` | **replace** (PLAN §10.1) with `test_mid_tone_is_accepted_with_black_label`: `#777` is **valid** in both modes, `on-brand` = black, every emitted pair ≥4.5 or degraded per §10.1 |
| `test_serializer…`, `test_theme_patch_contrast_400…` | `#777` now **saves** (200); exercise the 400 path with malformed values only (`"#77"`, `"red"`, `"#gggggg"`) |
| `test_validation_surfaces_match_rendered_css…` | 4 surfaces; `--color-brand` = `PRODUCT_FILL[mode]`; BODY_TEXT, FIXED_INKS and FIXED_SOFTS mirror index.css and brandColours.ts. **Replace the tint-alpha assertions** with: `--color-brand-soft/-hover/-active == derive_palette({}, mode)`. Light (224,238,236)/(2,103,93)/(4,97,88); dark (40,68,64)/(104,165,153)/(121,174,162). |
| `test_tint_strength_protects…` | becomes a soft golden: `#fff` dark soft = (60,79,77); `#000` light soft = (229,229,229) |
| bootstrap fallback tests | stored-colour fallback is exercised with a **malformed** stored value (`"red"`), not `#777` (which is now valid) |
| `test_links_and_semantic_inks…` | the mint card becomes `success-soft` dark (57,80,64) |
| `test_secondary_tints_have_an_opaque_base…` | replace with: no `color-mix(` tenant tint and no `--brand-tint-` in components.css; `MemberDirectory.tsx` contains `desk-panel mt-2 border-brand p-3` |
| new | `#e91e63` is **accepted** with a black label; sweep over all 4,096 `#RGB` (± `accent_color`) asserts `valid` in both modes; parity test: every colour the pre-revamp validator accepts is still accepted; `#004400` dark ink = (179,191,162) |

**`frontend/src/lib/brandColours.test.ts`**
- Fixtures: `fillText [255,244,232]`, `defaultFill [0,110,99]`, 4 surfaces.
- `#000` → `--color-on-brand` `"255 244 232"`. `#fff` → `"20 44 42"`.
- `#004400` hover `[26,86,23]`, active `[51,103,46]`. Night ink `[207,180,180]`.
- `#777` is valid with a black label (PLAN §10.1); add a 64-colour grid sweep asserting `valid` in both modes.
- The key list is the 7 `--color-brand*` keys.
- The soft golden replaces the tint-alpha test.

Backstops that stay: vitest axe, and Playwright `e2e/a11y.spec.ts`, which composites real colours. All of
these tests live only in the main checkout (they are gitignored), so the updated copies must be synced back.

---

## K. Brand fidelity checklist (rule → where → how enforced)

| # | Rule (PDF page) | Where it applies in the app | Enforcement |
|---|---|---|---|
| 1 | Use the supplied masters; one recognisable unit (p.4, p.8) | every logo render | `SpaceWorksLogo` imports only the `logo-extract` files; guard: no `<svg>` with the brand panel colours outside that component |
| 2 | Clear space **H÷4** on every side (p.5) | sidebar, top bar, headers, auth, OG | the component wraps the artwork in `padding: calc(var(--logo-h) / 4)`; the OG/PWA build script asserts the margin |
| 3 | Symbol↔wordmark gap **H÷6**; wordmark height = H÷1.25 (p.5) | lockups | baked into the extracted masters (measured 0.171 H / 0.81 H); never re-composed in CSS |
| 4 | Symbol ≥ **48 px** (p.6) | top bar, public header, Unfold, favicon | `height` prop typed `48 \| 52 \| 64 \| …`; runtime clamp; unit test renders every variant and asserts the symbol box ≥48 |
| 5 | Primary lockup ≥ **180 px** wide (p.6) | sidebar (180), auth (240–320), OG (600), email (180) | `variant="stacked"` clamps `width >= 180`; test |
| 6 | Below 48 px: a dedicated small-size asset (p.6) | favicon 16/32, PWA badge | **open owner item**; interim raster proofed; tracked in PLAN §8 |
| 7 | App icon: symbol at 62 % on a Warm Cream tile (p.6) | `favicon.svg`, apple-touch 180, PWA 192/512 (maskable), kiosk PWA | `app-icon.svg` extracted from p.6 (measured 61.1 %); PWA script rasterises only this file; `verify-pwa-build` checks sizes |
| 8 | Background pairings 01 full colour / Cream, 02 one-colour ink / white, 03 reverse / Ink, 04 reversed / Teal (p.7) | light ground → full colour; dark mode (Ink) → reversed; any teal surface → reversed | `ground` prop selects the file; guard forbids `filter`, `opacity` and `fill` overrides on the logo |
| 9 | Don't stretch / rotate / recolour panels / lose dark panels / add effects / change the type (p.8) | all logo uses | component props have no `className` or `style` passthrough; preserveAspectRatio default; lint bans `transform`, `filter` and `box-shadow` on `[data-logo]`; the wordmark is outlines, never live text |
| 10 | Wordmark lowercase "space works"; copy "Space Works" (p.4, p.15) | `aria-label`, `<title>`, meta, Unfold `SITE_TITLE`, emails, UI copy | i18n/copy grep: `/\bSpaceWorks\b/` banned in user-facing strings (the code identifiers `SpaceWorks*` are exempt) and `/space works/` banned in prose (wordmark artwork only) |
| 11 | Seven exact sRGB colours; neutral first, accent second (p.9, p.13) | all tokens | A.1 provenance; `test_token_provenance`; hex-literal guard |
| 12 | Tested text pairs; **orange text on cream banned** (p.10) | all text | no `emphasis-ink` token exists; guard bans `text-emphasis`; contrast guard ≥4.5 universal matrix |
| 13 | Every status = colour + word or icon (p.10) | `StatusPill`, stepper, availability, machine states | `StatusPill` requires a `label: string` prop (TS non-optional, non-empty); axe; test that every C status maps to a word |
| 14 | Gilroy leads; Unbounded **one accent per layout** (p.11–12) | Gilroy 600 on every heading and number; Gilroy for UI text; accent on landing, auth, empty hero | `font-accent` only through `<AccentHeadline>`; a test mounts each page and asserts ≤1 `[data-accent]`; guard bans raw `font-accent` outside that component |
| 15 | Type scale 72/76, 48/52, 32/38, 16/24, 14/20, accent 48/56 (p.12) | D.3 | Tailwind `fontSize` defines only these (+ derived 20/28, 12/16); guard bans arbitrary `text-[NNpx]` |
| 16 | Clear IDs and shelf codes (p.17) | tables, labels, item pages | `font-mono` removed (H.6); Gilroy 500 + `tabular-nums` (use Gilroy Medium for clear IDs) |
| 17 | Icons on a 24 grid, 2 px, rounded; label unfamiliar ones (p.14) | the G list only | lucide defaults; an `IconButton` with a required `label` prop; axe `button-name` |
| 18 | One bold moment; align to a simple grid; let empty space work (p.13) | page layouts | one `desk-button-emphasis` per page (test); 4 px spacing scale only; no shadows or decoration (E) |
| 19 | Voice: say "No parts added yet. Add your first item." / "Couldn't save. Try again." and skip "Oops! …", "Inventory database is empty" (p.15) | empty states, errors, toasts | `EmptyState` takes `nextStep` (required); a copy-lint list bans "Oops", "Something went wrong", "database is empty" and "asset ecosystem" |
| 20 | Calm in-product: quiet sidebar, one "+ Add item" primary, search + table (p.16) | staff shell, list pages | `PageHeader` accepts at most one `primary` action (TS tuple); text-only nav; Citron search field |
| 21 | Theme: existing Light/Dark only (owner) | `ThemeToggle` | no "System" option; test pins the two options |

**In-product logo sizes at a glance:**

| Placement | Spec |
|---|---|
| Sidebar | stacked 180 × 63.7, clear space 16 |
| Mobile bar | symbol 48 (bar 72) |
| Public header | horizontal 288 × 48 (≥768), else symbol 48 |
| Auth panel | stacked 240–320 |
| Favicon 16/32 | small-size master (open item) |
| PWA 192/512 and apple-touch 180 | `app-icon.svg` |
| OG 1200×630 | Cream, stacked 600 wide |
| Django `/control/` | horizontal at symbol 48 (288 px) + `SITE_ICON` symbol |

---

## J. Owner decisions still open

1. Control radius: 10 px (brand p.16) or pill (Yuyu).
2. Citron sidebar (brand p.16) or the Yuyu warm-neutral sidebar.
3. Reversed horizontal is now supplied directly from the Figma component library.
4. Tenant mid-tone primaries: accept the 15.8 % rejection (audit stored palettes first), or allow black as a functional-only label.
5. The original Gilroy free-font EULA covers the legacy Light/ExtraBold files. The current 400–700 faces were supplied by the owner; see `fonts/README.md` for provenance and licensing.
6. Copy changes: "Unpaid", "Partly returned", "N left", registration wording.
