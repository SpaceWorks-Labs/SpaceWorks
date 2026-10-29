# KiCanvas (vendored renderer for KiCad previews)

Status: **not yet vendored.** `kicanvas-entry.ts` is the seam the app imports; until the source
below is added it throws `KicanvasUnavailable`, and every KiCad preview shows the honest
"download to open in KiCad" card.

## What goes here

- Upstream: <https://github.com/theacodes/kicanvas>, MIT. Pin one commit SHA here when vendoring.
- Copy the TypeScript **source** (`src/`), not the minified bundle, so it can be reviewed and patched,
  together with `LICENSE.md` and the bundled-asset licences: earcut (ISC) and the Newstroke font
  data. Material Symbols (Apache-2.0) are not needed because the app draws its own toolbar.
- Add one line to the repository `NOTICE`:
  "KiCanvas (MIT, github.com/theacodes/kicanvas) renders KiCad schematic and board previews;
  vendored at <sha> with local patches listed in frontend/src/vendor/kicanvas/VENDORED.md."

## Local patches (keep each small and list it here)

1. Remove the Google Fonts `<link>` injection (privacy, brand-font rule, CSP).
2. Run with `controls="none"`; the app draws its own toolbar, so Material Symbols are dropped.
   Newstroke stays: it draws KiCad text as vectors.
3. Disable the GitHub/Codeberg URL sources (unused code that could fetch).

## Wiring after vendoring

Implement `mountKicad` in `kicanvas-entry.ts` by registering the custom elements and creating
`<kicanvas-embed controls="none">` with a `<kicanvas-source name="submission.kicad_pcb">` (or
`.kicad_sch`) whose `textContent` is the checked text. Map `fit`, `zoom` and `setLayerVisible` to
the viewer. The build check in `scripts/verify-pwa-build.mjs` refuses the chunk if it contains
`fonts.googleapis.com` or a remote `fetch(`.
