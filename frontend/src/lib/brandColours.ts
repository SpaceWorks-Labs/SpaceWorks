import type { CSSProperties } from "react";

export type RGB = [number, number, number];
export type BrandTokens = { fillText: RGB; surfaces: RGB[]; defaultFill: RGB };
export type ContrastPair = { mode: string; pair: string; ratio: number; minimum: number };
export const BRAND_SURFACES: Record<"light" | "dark", RGB[]> = {
  light: [[255, 244, 232], [246, 236, 224], [255, 255, 255], [239, 230, 219]],
  dark: [[20, 44, 42], [27, 50, 48], [34, 56, 53], [46, 66, 63]],
};
export const PRODUCT_FILL: Record<"light" | "dark", RGB> = {
  light: [0, 110, 99],
  dark: [87, 156, 144],
};
export const BODY_TEXT: Record<"light" | "dark", RGB[]> = {
  light: [[20, 44, 42], [91, 104, 99]],
  dark: [[255, 244, 232], [192, 190, 181]],
};
export const FIXED_INKS: Record<"light" | "dark", RGB[]> = {
  light: [[0, 110, 99], [83, 109, 73], [105, 104, 52], [81, 105, 123], [185, 28, 28]],
  dark: [[163, 196, 184], [223, 255, 143], [255, 212, 71], [181, 205, 255], [252, 165, 165]],
};
export const FIXED_SOFTS: Record<"light" | "dark", RGB[]> = {
  light: [[224, 238, 236], [255, 238, 233], [251, 255, 242], [255, 250, 233], [246, 249, 255]],
  dark: [[40, 68, 64], [61, 63, 55], [57, 80, 64], [61, 75, 55], [52, 74, 77]],
};
const INK: RGB = [20, 44, 42], CREAM: RGB = [255, 244, 232];
const BLACK: RGB = [0, 0, 0], WHITE: RGB = [255, 255, 255];

export function rgb(value: unknown): RGB | null {
  if (typeof value !== "string" || value.trim() !== value || !/^#(?:[\da-f]{3}|[\da-f]{6})$/i.test(value)) return null;
  const hex = value.slice(1);
  const expanded = hex.length === 3 ? [...hex].map((c) => c + c).join("") : hex;
  return [0, 2, 4].map((i) => parseInt(expanded.slice(i, i + 2), 16)) as RGB;
}

function luminance(color: RGB) {
  const linear = color.map((c) => {
    const v = c / 255;
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

export function contrast(a: RGB, b: RGB) {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

function blend(a: RGB, b: RGB, amount: number, rounded = true): RGB {
  return a.map((v, i) => {
    const channel = v * (1 - amount) + b[i] * amount;
    return rounded ? Math.round(channel) : channel;
  }) as RGB;
}

// Keep this derivation in sync with apps/makerspaces/theme_contrast.py.
export function deriveBrandPalette(theme: Record<string, string>, mode: "light" | "dark", surfaces = BRAND_SURFACES[mode]) {
  const custom = Boolean(theme.primary_color || theme.accent_color);
  const fill = rgb(theme.primary_color) ?? PRODUCT_FILL[mode];
  const foreground = [INK, CREAM, WHITE, BLACK].find((color) => contrast(color, fill) >= 4.5)!;
  let away = luminance(foreground) > .5 ? INK : CREAM;
  const toward = away === INK ? CREAM : INK;
  if (contrast(blend(fill, away, .10), fill) < 1.06 && contrast(foreground, blend(fill, toward, .20)) >= 4.5) away = toward;
  let hover = blend(fill, away, .10), active = blend(fill, away, .20);
  // A derived interaction may degrade to the previous algorithm, never reject.
  const fallback = luminance(foreground) < .5 ? WHITE : BLACK;
  if (contrast(foreground, hover) < 4.5) hover = blend(fill, fallback, .08);
  if (contrast(foreground, active) < 4.5) active = blend(fill, fallback, .16);
  const texts = [...BODY_TEXT[mode], ...FIXED_INKS[mode]];
  let soft = surfaces[2];
  for (let step = 0; step <= 100; step++) {
    const candidate = blend(surfaces[2], fill, .12 * (1 - step / 100));
    if (texts.every((text) => contrast(text, candidate) >= 4.55)) { soft = candidate; break; }
  }
  const names = ["bg", "surface", "panel", "hover"];
  const backgrounds = [...surfaces.map((color, i) => ({ name: names[i], color })), { name: "brand-soft", color: soft },
    ...FIXED_SOFTS[mode].map((color, i) => ({ name: `${["accent", "emphasis", "success", "warn", "info"][i]}-soft`, color }))];
  let ink = FIXED_INKS[mode][0];
  if (custom) {
    const seed = rgb(theme.accent_color) ?? fill, endpoint = mode === "light" ? INK : CREAM;
    for (let step = 0; step <= 100; step++) {
      const candidate = blend(seed, endpoint, step / 100);
      if (backgrounds.every(({ color }) => contrast(candidate, color) >= 4.5)) { ink = candidate; break; }
    }
  }
  const pairs: ContrastPair[] = [];
  const add = (pair: string, a: RGB, b: RGB, minimum = 4.5) => pairs.push({ mode, pair, ratio: contrast(a, b), minimum });
  for (const [name, background] of [["brand", fill], ["brand-hover", hover], ["brand-active", active]] as const) add(`on-brand on ${name}`, foreground, background);
  backgrounds.forEach(({ name, color }) => add(`brand-ink on ${name}`, ink, color));
  texts.forEach((text, i) => add(`${["ink", "muted", "accent-ink", "success-ink", "warn-ink", "info-ink", "danger"][i]} on brand-soft`, text, soft));
  surfaces.slice(0, 3).forEach((color, i) => add(`brand boundary on ${names[i]}`, ink, color, 3));
  return { fill, foreground, hover, active, ink, soft, pairs };
}

export function brandContrastReport(value: unknown) {
  const theme = value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  if (!theme) return { errors: ["Theme configuration must be an object."], pairs: [], failures: [], valid: false };
  const errors = ["primary_color", "accent_color"].filter((key) => key in theme && (typeof theme[key] !== "string" || (theme[key] !== "" && !rgb(theme[key]))))
    .map((key) => `${key} must be a #RGB or #RRGGBB colour, or blank.`);
  const pairs = (["light", "dark"] as const).flatMap((mode) => deriveBrandPalette(theme as Record<string, string>, mode).pairs);
  const failures = pairs.filter(({ ratio, minimum }) => ratio < minimum);
  return { errors, pairs, failures, valid: errors.length === 0 };
}

export function tenantColourStyle(value: unknown, tokens: BrandTokens, mode?: "light" | "dark"): CSSProperties {
  if (!brandContrastReport(value).valid) return {};
  const theme = value as Record<string, string>;
  if (!theme.primary_color && !theme.accent_color) return {};
  const resolvedMode = mode ?? (luminance(tokens.surfaces[0]) < .5 ? "dark" : "light");
  return brandPaletteStyle(deriveBrandPalette(theme, resolvedMode, tokens.surfaces));
}

export function brandPaletteStyle(palette: ReturnType<typeof deriveBrandPalette>): CSSProperties {
  return {
    "--color-brand": palette.fill.join(" "),
    "--color-on-brand": palette.foreground.join(" "),
    "--color-brand-ink": palette.ink.join(" "),
    "--color-brand-hover": palette.hover.join(" "),
    "--color-brand-active": palette.active.join(" "),
    "--color-brand-soft": palette.soft.join(" "),
    "--color-brand-boundary": palette.ink.join(" "),
  } as CSSProperties;
}

export function readBrandTokens(): BrandTokens | null {
  const css = getComputedStyle(document.documentElement);
  function token(name: string): RGB | null {
    const channels = css.getPropertyValue(`--color-${name}`).trim().split(/\s+/).map(Number);
    return channels.length === 3 && channels.every((value) => Number.isFinite(value) && value >= 0 && value <= 255) ? channels as RGB : null;
  }
  const fillText = token("on-brand"), defaultFill = token("brand");
  const surfaces = [token("bg"), token("surface"), token("panel"), token("hover")];
  if (!fillText || !defaultFill || surfaces.some((value) => value === null)) return null;
  return { fillText, defaultFill, surfaces: surfaces as RGB[] };
}
