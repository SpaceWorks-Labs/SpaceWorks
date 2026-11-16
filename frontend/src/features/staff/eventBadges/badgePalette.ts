// Badge colours: TypeScript twin of backend apps/card_designs/badge_palette.py (the SpaceWorks-Events palette
// rules). Every text colour keeps 4.5:1 against what it sits on, Workshop Orange is only ever a fill, and
// "event" is the event's accent (Maker Teal in this release, which has no custom accent colour).
import { ratio, rgb } from "../../../components/card-designer/contrast";
import type { BadgeSettings } from "./badgeNormalize";

export const BRAND = { ink: "#142C2A", teal: "#006E63", orange: "#FF7447", citron: "#DFFF8F", sky: "#B5CDFF",
  yellow: "#FFD447", cream: "#FFF4E8", white: "#FFFFFF" } as const;
const MONO_INK = "#000000";
const MINIMUM_CONTRAST = 4.5;

export type BadgePalette = { background: string; text: string; heading: string; accent: string; on_accent: string;
  rule: string; tile: string; symbol: "ink" | "full"; textAdjusted: boolean };

/** Python's round(): halves go to the even neighbour (used only where the server calls round). */
function pyRound(value: number) {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

const toHex = (colour: number[]) =>
  `#${colour.map((c) => Math.max(0, Math.min(255, pyRound(c))).toString(16).toUpperCase().padStart(2, "0")).join("")}`;
const contrast = (first: string, second: string) => ratio(rgb(first), rgb(second));
export const colourOf = (key: string, eventAccent: string = BRAND.teal) =>
  (key === "event" ? eventAccent : BRAND[key as keyof typeof BRAND]);

function mix(first: string, second: string, weight: number) {
  const a = rgb(first), b = rgb(second);
  return toHex(a.map((x, index) => x * weight + b[index] * (1 - weight)));
}

function readableOn(surface: string, candidates: string[]) {
  const passing = candidates.find((candidate) => contrast(candidate, surface) >= MINIMUM_CONTRAST);
  if (passing) return passing;
  return candidates.reduce((best, candidate) => (contrast(candidate, surface) > contrast(best, surface) ? candidate : best));
}

const isReadable = (colour: string, surface: string) =>
  colour.toUpperCase() !== BRAND.orange && contrast(colour, surface) >= MINIMUM_CONTRAST;

function bandSafe(accent: string) {
  if ([BRAND.cream, BRAND.ink].some((text) => contrast(text, accent) >= MINIMUM_CONTRAST)) return accent;
  for (let step = 1; step <= 20; step += 1) {
    const deeper = mix(BRAND.ink, accent, step * 0.05);
    if (contrast(BRAND.cream, deeper) >= MINIMUM_CONTRAST) return deeper;
  }
  return BRAND.ink;
}

export function resolvePalette(settings: BadgeSettings, eventAccent?: string | null): BadgePalette {
  if (settings.colorMode === "mono") {
    return { background: BRAND.white, text: MONO_INK, heading: MONO_INK, accent: MONO_INK, on_accent: BRAND.white,
      rule: MONO_INK, tile: BRAND.white, symbol: "ink", textAdjusted: false };
  }
  const accentHex = (eventAccent || BRAND.teal).toUpperCase();
  const background = bandSafe(colourOf(settings.backgroundColor, accentHex));
  const accent = bandSafe(colourOf(settings.accentColor, accentHex));
  const automatic = readableOn(background, [BRAND.ink, BRAND.cream, BRAND.white]);
  const chosen = settings.textColor === "auto" ? automatic : colourOf(settings.textColor, accentHex);
  const keep = settings.textColor === "auto" || isReadable(chosen, background);
  const text = keep ? chosen : automatic;
  return { background, text, heading: isReadable(accent, background) ? accent : text, accent,
    on_accent: readableOn(accent, [BRAND.cream, BRAND.ink, BRAND.white]),
    rule: contrast(accent, background) >= 1.5 ? accent : text, tile: BRAND.white,
    symbol: background === BRAND.white ? "ink" : "full", textAdjusted: !keep };
}
