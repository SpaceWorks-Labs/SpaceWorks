# Original Space Works programme artwork

Source: `docs/brand/space-works-brand-guidelines-v1.pdf` v1.0, pp. 3–14,
`docs/brand/README.md` (approved 2026-10-15 font kit), and supplied symbol masters.
These are new vector constructions for the 2026-10 Events programme, not imports
from another product. Flaps, print layers, workbench objects and perforated tags
carry the brand's invitation to make. No third-party artwork, fonts, filters,
gradients, scripts, bitmap assets or external image references are included.

`manifest.ts` is the complete 29-entry / 58-file catalogue. It declares each pair,
viewBox dimensions, semantics, suggested alternative text, empty label and named
consumer. Resolved light/dark colours come from the **same CSS tokens** in
`src/index.css`; the inventory test checks every resolved value. SVG image
documents cannot inherit CSS variables through an `<img>`, so values are resolved
in the files, with a real separately reviewed dark composition. No inversion filter
or tenant colour override is used. Template artwork uses the identical palette in
`backend/apps/events/default_templates/manifest.py`.

```tsx
import { illustrationImageProps } from '../../assets/illustrations'

// Beside an equivalent empty-state heading: decorative, one selected image.
<img {...illustrationImageProps('empty/teams', theme)} />
// When the illustration itself adds meaning: accessible image and suggested alt.
<img {...illustrationImageProps('roles/mentor', theme, false)} />
```

Use the actual resolved light/dark theme. Do not mount both twins and hide one.
Prefer the empty label for the screen's heading; context may need different copy.
`getIllustration(id, theme)` also exposes the metadata for P's shared renderer.
Keep the aspect ratio. Frontend vectors contain no live text/fonts; all labels
and controls stay in the caller's Gilroy ExtraBold/Outfit/Unbounded/lucide component system.

All source SVG roots are inert (`aria-hidden`, `focusable=false`), including the
loader, robot and pass. Meaning belongs to the enclosing image/component. Loader
consumers provide a visible or screen-reader status label with `role=status`.
Animation belongs to P, stays still with reduced motion, and never changes the
accessible name. Decorative companions are click-through; interactions require
labelled keyboard buttons. No asset initiates network or workflow operations.

The tag's crossed ornamental square and the pass's plus-shaped resource marker
are **not QR encodings**. The landing scene has no QR. A real credential is E's
typed rendering resource, never composited into a packaged asset.

Suggested display sizes: mood glyph 48–96 px, loader 80–160 px, companion 80–160
px, area/role scenes 160–240 px wide, pass 280–360 px, workshop 480–640 px. Small
contact sheets additionally exercise half size. The small flap motifs are original
ornaments, not altered brand logos. Print seeds use the complete supplied symbol
through the typed logo slot, at least 12 mm high with H/4 clear space.

Consumer integration and signed acceptance status are recorded in
`docs/events-programme-artwork-inventory.md`. This asset package does not claim
that another lane's empty screen or motion behavior has been installed.
