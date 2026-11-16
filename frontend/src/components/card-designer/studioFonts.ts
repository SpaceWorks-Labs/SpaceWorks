// The Card Studio's font allow-list: the faces vendored under public/fonts (free Gilroy Light/ExtraBold and
// OFL faces only), mirroring apps/card_designs/fonts.py STUDIO_FONTS. They are served from this app, never a CDN.
import { t } from "@lingui/core/macro";

export type StudioFont = { family: string; label: string; category: "sans" | "display" | "serif" | "handwriting";
  weights: number[]; file: string; range?: [number, number] };

export const STUDIO_FONTS: StudioFont[] = [
  { family: "Gilroy Light", label: t`Gilroy Light`, category: "sans", weights: [300], file: "Gilroy-Light.woff2" },
  { family: "Gilroy ExtraBold", label: t`Gilroy ExtraBold`, category: "sans", weights: [800], file: "Gilroy-ExtraBold.woff2" },
  { family: "Outfit", label: t`Outfit`, category: "sans", weights: [300, 400, 500, 600, 700, 800],
    file: "Outfit-Variable.woff2", range: [100, 900] },
  { family: "Unbounded", label: t`Unbounded`, category: "display", weights: [400, 500, 600, 700, 800],
    file: "Unbounded-Variable.woff2", range: [200, 900] },
  { family: "Bebas Neue", label: t`Bebas Neue (condensed)`, category: "display", weights: [400], file: "BebasNeue-400.woff2" },
  { family: "Pacifico", label: t`Pacifico (script)`, category: "handwriting", weights: [400], file: "Pacifico-400.woff2" },
  { family: "DM Serif Display", label: t`DM Serif Display`, category: "serif", weights: [400], file: "DMSerifDisplay-400.woff2" },
];

export const studioFont = (family: string) => STUDIO_FONTS.find((font) => font.family === family);

/** The shipped weight nearest to `weight` for `family` (the server rejects a weight a family does not ship). */
export function nearestWeight(family: string, weight: number) {
  const font = studioFont(family);
  if (!font) return weight;
  return [...font.weights].sort((a, b) => Math.abs(a - weight) - Math.abs(b - weight))[0];
}

const loaded = new Map<string, Promise<boolean>>();

/** Register a studio face with the FontFace API under the name the canvas uses ("SW Card <family>"). */
export function loadStudioFont(family: string): Promise<boolean> {
  const font = studioFont(family);
  if (!font || typeof FontFace === "undefined" || typeof document === "undefined") return Promise.resolve(false);
  if (!loaded.has(family)) {
    const weight = font.range ? `${font.range[0]} ${font.range[1]}` : String(font.weights[0]);
    loaded.set(family, (async () => {
      try {
        const face = new FontFace(`SW Card ${family}`, `url(/fonts/${font.file}) format("woff2")`, { weight });
        await face.load();
        document.fonts.add(face);
        return true;
      } catch {
        loaded.delete(family);
        return false;
      }
    })());
  }
  return loaded.get(family)!;
}
