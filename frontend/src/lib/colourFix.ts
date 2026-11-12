import { brandContrastReport, contrast, deriveBrandPalette, rgb, BRAND_SURFACES, type ContrastPair, type RGB } from "./brandColours";

export type Theme = Record<string, string>;
export type ColourKey = "primary_color" | "accent_color";

export function toHex(color: RGB) {
  return `#${color.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

function toHsl([r, g, b]: RGB): [number, number, number] {
  const [x, y, z] = [r / 255, g / 255, b / 255];
  const max = Math.max(x, y, z), min = Math.min(x, y, z), l = (max + min) / 2, d = max - min;
  if (d === 0) return [0, 0, l];
  const s = d / (1 - Math.abs(2 * l - 1));
  const h = max === x ? ((y - z) / d + 6) % 6 : max === y ? (z - x) / d + 2 : (x - y) / d + 4;
  return [h * 60, s, l];
}

function fromHsl(h: number, s: number, l: number): RGB {
  const channel = (n: number) => {
    const a = (n + h / 30) % 12;
    return Math.round(255 * (l - s * Math.min(l, 1 - l) * Math.max(-1, Math.min(a - 3, Math.min(9 - a, 1)))));
  };
  return [channel(0), channel(8), channel(4)];
}

/** What the backend does not block but a space still wants to know: the brand fill has to read against the page. */
export function advisoryPairs(theme: Theme): ContrastPair[] {
  return (["light", "dark"] as const).map((mode) => {
    const { fill } = deriveBrandPalette(theme, mode);
    return { mode, pair: "brand fill on bg", ratio: contrast(fill, BRAND_SURFACES[mode][0]), minimum: 3 };
  });
}

export function issuesOf(theme: Theme) {
  const blocking = brandContrastReport(theme).failures;
  const advice = advisoryPairs(theme).filter((pair) => pair.ratio < pair.minimum);
  return { blocking, advice };
}

const count = (theme: Theme) => { const i = issuesOf(theme); return i.blocking.length + i.advice.length; };

/** Nearest lightness (by HSL L, 1% steps) of an entered colour at which no pair fails; null when nothing to fix. */
export function suggestFix(theme: Theme): { key: ColourKey; value: string } | null {
  if (!brandContrastReport(theme).valid || count(theme) === 0) return null;
  let best: { key: ColourKey; value: string; delta: number } | null = null;
  for (const key of ["primary_color", "accent_color"] as const) {
    const base = rgb(theme[key]);
    if (!base) continue;
    const [h, s, l] = toHsl(base);
    for (let step = 1; step <= 100; step++) {
      for (const sign of [-1, 1]) {
        const next = l + sign * step / 100;
        if (next < 0 || next > 1) continue;
        const value = toHex(fromHsl(h, s, next));
        if (count({ ...theme, [key]: value }) === 0) {
          if (!best || step < best.delta) best = { key, value, delta: step };
          step = 101;
          break;
        }
      }
    }
  }
  return best ? { key: best.key, value: best.value } : null;
}
