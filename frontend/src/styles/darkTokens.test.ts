/// <reference types="node" />
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { contrast, type RGB } from "../lib/brandColours";

// Decision 225: dark is true black. 0.12.0 lights it with the brand, calmly (owner 2026-11-11: "professional,
// clean"): three near-black layers with a faint Maker Teal + Cream lift, a quiet hairline between them, and
// control boundaries carried by outline at 3:1. The sidebar is Deep Ink itself, and muted, links, status
// inks, hairlines and boundaries are documented teal/cream mixes. The Deep Ink island keeps its set.
const INK: RGB = [20, 44, 42], TEAL: RGB = [0, 110, 99], CREAM: RGB = [255, 244, 232], BLACK: RGB = [0, 0, 0];
const ORANGE: RGB = [255, 116, 71], CITRON: RGB = [223, 255, 143], YELLOW: RGB = [255, 212, 71], SKY: RGB = [181, 205, 255];

const css = readFileSync("src/index.css", "utf8");
const chrome = readFileSync("src/styles/chrome.css", "utf8");
function block(source: string, selector: string) {
  const parts = source.split(`${selector} {`);
  if (parts.length < 2) throw new Error(`${selector} block missing`);
  return parts[1].split("}")[0];
}
const dark = block(css, ":root.dark"), island = block(css, ".sw-island-dark");
function read(source: string, name: string): RGB {
  const match = source.match(new RegExp(`--color-${name}: ([0-9 ]+);`));
  if (!match) throw new Error(`--color-${name} missing`);
  return match[1].split(" ").map(Number) as RGB;
}
const token = (name: string) => read(dark, name);
const names = (source: string) => [...source.matchAll(/--color-([\w-]+):/g)].map((m) => m[1]);
const lit = (base: RGB, t: number, u: number) => base.map((v, i) => Math.round(v * (1 - t - u) + TEAL[i] * t + CREAM[i] * u)) as RGB;
const mix = (a: RGB, b: RGB, t: number) => a.map((v, i) => Math.round(v * (1 - t) + b[i] * t)) as RGB;
const SURFACE_LIFTS: Record<string, [number, number]> = { surface: [.10, .04], panel: [.14, .07], hover: [.20, .11] };
const ISLAND_LIFTS: Record<string, [number, number]> = {
  sidebar: [.14, 0], surface: [.10, .03], panel: [.16, .06], hover: [.22, .09], "sidebar-hover": [.22, .09],
};
// Text and boundary tokens that the true-black set derives itself (over black), instead of copying the island.
const DARK_MIXES: Record<string, RGB> = {
  muted: lit(BLACK, .08, .70), line: lit(BLACK, .28, .18), outline: lit(BLACK, .30, .50),
  "success-ink": mix(CITRON, CREAM, .3), "warn-ink": mix(YELLOW, CREAM, .3), "info-ink": mix(SKY, CREAM, .3),
  "accent-ink": mix(TEAL, CREAM, .5), "brand-ink": mix(TEAL, CREAM, .5), "brand-boundary": mix(TEAL, CREAM, .5),
  sidebar: INK, "sidebar-hover": lit(INK, .12, .06),
};
const SOFTS: Record<string, [RGB, number]> = {
  "accent-soft": [TEAL, .16], "brand-soft": [TEAL, .16], "emphasis-soft": [ORANGE, .07],
  "success-soft": [CITRON, .07], "warn-soft": [YELLOW, .07], "info-soft": [SKY, .07],
};
const GROUNDS = ["bg", "surface", "panel", "hover", "sidebar", "sidebar-hover", "accent-soft", "emphasis-soft", "success-soft", "warn-soft", "info-soft"];
const TEXTS = ["ink", "muted", "accent-ink", "brand-ink", "success-ink", "warn-ink", "info-ink", "danger"];

function worst(texts: RGB[], grounds: RGB[]) {
  let low = Infinity;
  for (const text of texts) for (const ground of grounds) low = Math.min(low, contrast(text, ground));
  return low;
}

describe("dark tokens (true black)", () => {
  it("puts the page on #000 and layers three near-black surfaces with a faint teal and cream lift", () => {
    expect(token("bg")).toEqual(BLACK);
    for (const [name, [t, u]] of Object.entries(SURFACE_LIFTS)) expect([name, token(name)]).toEqual([name, lit(BLACK, t, u)]);
    for (const [name, [t, u]] of Object.entries(ISLAND_LIFTS)) {
      expect([name, read(island, name)]).toEqual([name, lit(INK, t, u)]); // the island keeps the kit's lifts
      // Near-black, not green: teal never outweighs cream three to one in a layer's lift.
      if (name in SURFACE_LIFTS) expect(SURFACE_LIFTS[name][0] / SURFACE_LIFTS[name][1]).toBeLessThan(3);
    }
    for (const [name, [fill, t]] of Object.entries(SOFTS)) expect([name, token(name)]).toEqual([name, mix(token("panel"), fill, t)]);
    expect(token("bg")).not.toEqual(token("surface"));
    expect(contrast(token("hover"), BLACK)).toBeGreaterThan(contrast(token("panel"), BLACK));
    expect(contrast(token("panel"), BLACK)).toBeGreaterThan(contrast(token("surface"), BLACK));
  });

  it("derives muted, links, hairlines, boundaries and the Deep Ink sidebar as brand mixes; the rest match the island", () => {
    const own = new Set(["bg", ...Object.keys(SURFACE_LIFTS), ...Object.keys(SOFTS), ...Object.keys(DARK_MIXES)]);
    expect(names(dark).filter((n) => n !== "scrim").sort()).toEqual(names(island).sort());
    for (const [name, value] of Object.entries(DARK_MIXES)) expect([name, token(name)]).toEqual([name, value]);
    for (const name of names(island).filter((n) => !own.has(n))) expect([name, token(name)]).toEqual([name, read(island, name)]);
    expect(token("accent")).toEqual(TEAL);
    expect(token("focus")).toEqual(CITRON);
    expect(token("ink")).toEqual(CREAM);
    // Links read teal and muted reads neutral, so the two never look alike.
    const tealness = ([r, g]: RGB) => g - r;
    expect(tealness(token("accent-ink"))).toBeGreaterThan(40);
    expect(Math.abs(tealness(token("muted")))).toBeLessThan(10);
  });

  it("dims behind dialogs and the camera with black, never a Cream wash", () => {
    expect(token("scrim")).toEqual(BLACK);
    expect(read(block(css, ":root"), "scrim")).toEqual(read(block(css, ":root"), "ink")); // light: unchanged Deep Ink
  });

  it("keeps the light-mode sign-in island on Deep Ink", () => {
    expect(read(island, "bg")).toEqual(INK);
    expect(css).toMatch(/\n {2}\.sw-island-dark \{/);
  });

  it("keeps text, muted, link, status and danger inks at AA (4.5:1) on every ground", () => {
    expect(worst(TEXTS.map(token), GROUNDS.map(token))).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps disabled controls (muted on surface) and placeholders (muted on panel) legible", () => {
    expect(contrast(token("muted"), token("surface"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("muted"), token("panel"))).toBeGreaterThanOrEqual(4.5);
  });

  it("keeps labels on solid fills (buttons, badges, the active nav item) at AA", () => {
    const pairs: [string, string][] = [["on-accent", "accent"], ["on-accent", "accent-hover"], ["on-accent", "sidebar-active"],
      ["on-brand", "brand"], ["on-emphasis", "emphasis"], ["on-success", "success"], ["on-warn", "warn"], ["on-info", "info"], ["on-danger", "danger"]];
    for (const [label, fill] of pairs) expect([label, fill, contrast(token(label), token(fill)) >= 4.5]).toEqual([label, fill, true]);
  });

  it("keeps control boundaries, the Citron focus ring and the teal fill's boundary at 3:1 or more", () => {
    for (const ground of ["bg", "surface", "panel", "hover", "sidebar", "sidebar-hover"]) expect(contrast(token("outline"), token(ground))).toBeGreaterThanOrEqual(3);
    for (const ground of ["bg", "surface", "panel", "hover", "sidebar"]) expect(contrast(token("focus"), token(ground))).toBeGreaterThanOrEqual(3);
    expect(contrast(token("focus"), TEAL)).toBeGreaterThanOrEqual(3); // ring on a teal button or field
    for (const ground of ["bg", "panel", "sidebar"]) expect(contrast(token("accent-ink"), token(ground))).toBeGreaterThanOrEqual(3); // primary button border
    expect(contrast(token("accent"), token("bg"))).toBeGreaterThanOrEqual(3);
  });

  it("separates layers with a quiet hairline that never glows; boundaries that identify a control stay on outline", () => {
    // Decorative: line divides layers (about 2:1 on black), so it sits clearly below the 3:1 control boundary.
    for (const ground of ["bg", "surface", "panel"]) {
      const ratio = contrast(token("line"), token(ground));
      expect([ground, ratio >= 1.6 && ratio < 3]).toEqual([ground, true]);
    }
    expect(contrast(token("line"), token("hover"))).toBeGreaterThanOrEqual(1.3);
    expect(contrast(token("outline"), token("line"))).toBeGreaterThan(2); // a control never looks like a divider
    // Each layer steps up from the one below, so cards read without a border at all.
    expect(contrast(token("surface"), token("bg"))).toBeGreaterThanOrEqual(1.1);
    expect(contrast(token("panel"), token("surface"))).toBeGreaterThanOrEqual(1.1);
    expect(contrast(token("danger-line"), token("panel"))).toBeGreaterThanOrEqual(2);
    expect(dark).toMatch(/--shadow-color: 0 0 0;/);
  });

  it("keeps every dark chart mark at 3:1 or more on the page and on cards", () => {
    const charts = block(chrome, ":root.dark");
    const resolve = (name: string) => {
      const ref = (charts.match(new RegExp(`--chart-${name}: var\\(--color-([\\w-]+)\\)`)) ?? block(chrome, ":root").match(new RegExp(`--chart-${name}: var\\(--color-([\\w-]+)\\)`)))!;
      return token(ref[1]);
    };
    for (const name of ["accent", "info", "success", "warn", "danger"]) {
      for (const ground of ["bg", "surface", "panel"]) expect([name, ground, contrast(resolve(name), token(ground)) >= 3]).toEqual([name, ground, true]);
    }
  });

  it("keeps solid status marks perceivable on the dark panel", () => {
    for (const fill of [CITRON, SKY, YELLOW, ORANGE]) {
      expect(contrast(fill, token("panel"))).toBeGreaterThanOrEqual(3);
      expect(contrast(INK, fill)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
