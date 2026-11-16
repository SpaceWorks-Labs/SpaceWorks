/// <reference types="node" />
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { contrast, type RGB } from "../lib/brandColours";

// Decision 316 (supersedes the teal lift of 275): dark is ONE solid black family. The page is #000 and every
// layer is a neutral grey (no green or teal tint in any surface), control boundaries ride on outline at 3:1,
// muted is a neutral grey, and brand colour lives only in accents (teal fill, Citron focus, links, status inks).
// Soft fills are the panel plus a hint of their accent hue. The Deep Ink island keeps its set (light-mode panel).
const INK: RGB = [20, 44, 42], TEAL: RGB = [0, 110, 99], CREAM: RGB = [255, 244, 232], BLACK: RGB = [0, 0, 0];
const ORANGE: RGB = [255, 116, 71], CITRON: RGB = [223, 255, 143], YELLOW: RGB = [255, 212, 71], SKY: RGB = [181, 205, 255];

const css = readFileSync("src/index.css", "utf8");
const chrome = readFileSync("src/styles/chrome.css", "utf8");
function block(source: string, selector: string) {
  const parts = source.split(`${selector} {`);
  if (parts.length < 2) throw new Error(`${selector} block missing`);
  // A selector can open several blocks (motion tokens first, colour tokens later): take the one holding colour tokens.
  const bodies = parts.slice(1).map((part) => part.split("}")[0]);
  return bodies.find((body) => body.includes("--color-")) ?? bodies[0];
}
const dark = block(css, ":root.dark"), island = block(css, ".sw-island-dark");
function read(source: string, name: string): RGB {
  const match = source.match(new RegExp(`--color-${name}: ([0-9 ]+);`));
  if (!match) throw new Error(`--color-${name} missing`);
  return match[1].split(" ").map(Number) as RGB;
}
const token = (name: string) => read(dark, name);
const names = (source: string) => [...source.matchAll(/--color-([\w-]+):/g)].map((m) => m[1]);
const grey = (n: number): RGB => [n, n, n];
const mix = (a: RGB, b: RGB, t: number) => a.map((v, i) => Math.round(v * (1 - t) + b[i] * t)) as RGB;
const lit = (base: RGB, t: number, u: number) => base.map((v, i) => Math.round(v * (1 - t - u) + TEAL[i] * t + CREAM[i] * u)) as RGB;
const NEUTRAL_LAYERS: Record<string, RGB> = { surface: grey(11), panel: grey(20), hover: grey(28), line: grey(44), outline: grey(120), muted: grey(172), sidebar: grey(11), "sidebar-hover": grey(28) };
const ISLAND_LIFTS: Record<string, [number, number]> = {
  sidebar: [.14, 0], surface: [.10, .03], panel: [.16, .06], hover: [.22, .09], "sidebar-hover": [.22, .09],
};
// Links and status inks are documented accent mixes over their brand colour.
const DARK_MIXES: Record<string, RGB> = {
  ...NEUTRAL_LAYERS,
  "success-ink": mix(CITRON, CREAM, .3), "warn-ink": mix(YELLOW, CREAM, .3), "info-ink": mix(SKY, CREAM, .3),
  "accent-ink": mix(TEAL, CREAM, .5), "brand-ink": mix(TEAL, CREAM, .5), "brand-boundary": mix(TEAL, CREAM, .5),
};
const SOFTS: Record<string, [RGB, number]> = {
  "accent-soft": [TEAL, .10], "brand-soft": [TEAL, .10], "emphasis-soft": [ORANGE, .06],
  "success-soft": [CITRON, .06], "warn-soft": [YELLOW, .06], "info-soft": [SKY, .06],
};
const GROUNDS = ["bg", "surface", "panel", "hover", "sidebar", "sidebar-hover", "accent-soft", "emphasis-soft", "success-soft", "warn-soft", "info-soft"];
const TEXTS = ["ink", "muted", "accent-ink", "brand-ink", "success-ink", "warn-ink", "info-ink", "danger"];

function worst(texts: RGB[], grounds: RGB[]) {
  let low = Infinity;
  for (const text of texts) for (const ground of grounds) low = Math.min(low, contrast(text, ground));
  return low;
}

describe("dark tokens (one solid black family)", () => {
  it("puts the page on #000 and layers neutral greys with no green or teal tint", () => {
    expect(token("bg")).toEqual(BLACK);
    for (const name of ["surface", "panel", "hover", "line", "outline", "muted", "sidebar", "sidebar-hover"]) {
      const [r, g, b] = token(name);
      expect([name, r === g && g === b]).toEqual([name, true]);
    }
    for (const [name, value] of Object.entries(NEUTRAL_LAYERS)) expect([name, token(name)]).toEqual([name, value]);
    for (const [name, [t, u]] of Object.entries(ISLAND_LIFTS)) expect([name, read(island, name)]).toEqual([name, lit(INK, t, u)]); // the island keeps the kit's lifts
    for (const [name, [fill, t]] of Object.entries(SOFTS)) expect([name, token(name)]).toEqual([name, mix(token("panel"), fill, t)]);
    expect(contrast(token("hover"), BLACK)).toBeGreaterThan(contrast(token("panel"), BLACK));
    expect(contrast(token("panel"), BLACK)).toBeGreaterThan(contrast(token("surface"), BLACK));
  });

  it("keeps soft fills near-black: a faint hint of the accent hue, never a coloured background", () => {
    for (const name of Object.keys(SOFTS)) {
      const c = token(name);
      expect([name, Math.max(...c) <= 40]).toEqual([name, true]);
      expect([name, Math.max(...c) - Math.min(...c) <= 12]).toEqual([name, true]);
    }
  });

  it("derives links and status inks as accent mixes; the rest match the island", () => {
    const own = new Set(["bg", ...Object.keys(SOFTS), ...Object.keys(DARK_MIXES)]);
    expect(names(dark).filter((n) => n !== "scrim").sort()).toEqual(names(island).sort());
    for (const [name, value] of Object.entries(DARK_MIXES)) expect([name, token(name)]).toEqual([name, value]);
    for (const name of names(island).filter((n) => !own.has(n))) expect([name, token(name)]).toEqual([name, read(island, name)]);
    expect(token("accent")).toEqual(TEAL);
    expect(token("focus")).toEqual(CITRON);
    expect(token("ink")).toEqual(CREAM);
    // Links read teal and muted reads neutral, so the two never look alike.
    const tealness = ([r, g]: RGB) => g - r;
    expect(tealness(token("accent-ink"))).toBeGreaterThan(40);
    expect(tealness(token("muted"))).toBe(0);
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
    // Decorative: line divides layers (about 1.5:1 on black), so it sits clearly below the 3:1 control boundary.
    for (const [ground, floor] of [["bg", 1.45], ["surface", 1.35], ["panel", 1.3]] as const) {
      const ratio = contrast(token("line"), token(ground));
      expect([ground, ratio >= floor && ratio < 3]).toEqual([ground, true]);
    }
    expect(contrast(token("line"), token("hover"))).toBeGreaterThanOrEqual(1.2);
    expect(contrast(token("outline"), token("line"))).toBeGreaterThan(2); // a control never looks like a divider
    // Each layer steps up from the one below, so cards read as a step even before the hairline.
    expect(contrast(token("surface"), token("bg"))).toBeGreaterThanOrEqual(1.06);
    expect(contrast(token("panel"), token("surface"))).toBeGreaterThanOrEqual(1.05);
    expect(contrast(token("danger-line"), token("panel"))).toBeGreaterThanOrEqual(2);
    expect(dark).toMatch(/--shadow-color: 0 0 0;/);
  });

  it("keeps every dark chart mark boundary at 3:1 or more on the page and on cards", () => {
    // Decision 380: series fills are the same bright brand colours as light; the hairline edge carries the boundary.
    const edge = block(chrome, ":root.dark").match(/--chart-edge: ([0-9 ]+);/)![1].split(" ").map(Number) as RGB;
    for (const ground of ["bg", "surface", "panel"]) expect([ground, contrast(edge, token(ground)) >= 3]).toEqual([ground, true]);
  });

  it("keeps solid status marks perceivable on the dark panel", () => {
    for (const fill of [CITRON, SKY, YELLOW, ORANGE]) {
      expect(contrast(fill, token("panel"))).toBeGreaterThanOrEqual(3);
      expect(contrast(INK, fill)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
