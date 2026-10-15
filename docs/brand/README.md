# Space Works brand v1

The [brand guidelines v1.0](space-works-brand-guidelines-v1.pdf) are the source of truth.
This reference summarises the PDF; the product font implementation follows the binding
[design revamp plan, section 0.4](../design-revamp/PLAN.md).

Space Works helps teams keep shared parts, tools and materials organised. The identity is clear,
capable, curious and playful. The open box is an invitation: four flaps welcome the next project,
a clear structure gives every part a place, teal grounds it and orange brings energy.

## Logo masters

These are verbatim outlined vectors extracted from the PDF. The lowercase wordmark is artwork,
not live type. Scale each complete master as one object; never rebuild the lockup with text or CSS.

| File | Use |
| --- | --- |
| [symbol.svg](symbol.svg) | Full-colour symbol on Warm Cream or white |
| [symbol-reversed.svg](symbol-reversed.svg) | Separately drawn cream symbol on Deep Ink or Maker Teal |
| [lockup-stacked.svg](lockup-stacked.svg) | Primary symbol and two-line wordmark on a light ground |
| [lockup-stacked-reversed.svg](lockup-stacked-reversed.svg) | Reversed primary lockup on a dark ground |
| [lockup-horizontal.svg](lockup-horizontal.svg) | Full-colour horizontal lockup for wide headers |
| [symbol-one-colour-ink.svg](symbol-one-colour-ink.svg) | One-colour ink symbol on a light ground |
| [lockup-stacked-one-colour-ink.svg](lockup-stacked-one-colour-ink.svg) | One-colour ink primary lockup on a light ground |
| [app-icon.svg](app-icon.svg) | Symbol on a Warm Cream tile, nominally 62% of tile height |

There is no reversed horizontal master. Dark horizontal requests use the reversed stacked lockup;
the dark public header uses the reversed symbol. One-colour horizontal requests use the ink stacked
master. The reversed and ink drawings have their own notches and knocked-out interior: recolouring
the full-colour symbol cannot reproduce them.

The repository [banner](../banner.svg) uses the stacked master on Warm Cream.
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
steps; both 500 and 600 retain Maker Teal, per the lane brief.

## Typography

The PDF assigns Gilroy the primary role and Unbounded short geometric accents. The product follows
the owner's permanent implementation decision in PLAN section 0.4:

- Official free **Gilroy ExtraBold 800** for headings and display numbers; **Gilroy Light 300** is the
  other licensed brand weight. Preserve the original outlined wordmark in all logos.
- **Outfit** for body and UI text, labels, controls, tables and IDs in place of unlicensed Gilroy
  weights. Outfit is the only non-brand family. Machine strings use Outfit with tabular numerals,
  slashed zero and wider tracking.
- **Unbounded** for one short accent phrase per layout. Never use it for long copy.

PDF type scale (size / line height): display 72/76, heading 48/52, subheading 32/38, body 16/24,
label 14/20, accent 48/56. Do not substitute other families or a monospace face.

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

## Icons, imagery and voice

Icons use a **24 px grid, 2 px stroke, rounded ends and consistent weight**. Lucide React implements
that specification in the product, at a default rendered size of 20 px. Pair unfamiliar icons with
labels; name icon-only buttons and hide decorative SVGs from assistive technology. Use typographic
marks rather than emoji. Show real parts, hands and shared benches in soft daylight, with honest
materials and the work in focus. Avoid staged tech cliches and busy backdrops.

Sound like a helpful maker: clear, warm and specific. Make the next step easy. Use sentence case.
The brand name in copy is **Space Works**; the outlined wordmark stays **space works**.

| Say | Skip |
| --- | --- |
| Find the right part. | Optimize your asset ecosystem. |
| No parts added yet. Add your first item. | Inventory database is empty. |
| Couldn't save. Try again. | Oops! Something went horribly wrong. |

Keep technical names accurate. On shelf labels, put the item name first and details second; test
size and contrast at the intended viewing distance.
