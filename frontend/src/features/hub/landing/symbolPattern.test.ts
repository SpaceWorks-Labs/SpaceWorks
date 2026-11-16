/// <reference types="node" />
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { contrast, type RGB } from "../../../lib/brandColours";

// Decision 300 addendum 2: the symbol pattern behind the hero and the overview. It must stay a quiet,
// token-coloured mask that never moves and never takes muted text below AA where it is densest.
const pattern = readFileSync("src/features/hub/landing/symbol-pattern.css", "utf8");
// Normalise CRLF: a Windows checkout may convert line endings, and the selectors below span a newline.
const tokens = readFileSync("src/index.css", "utf8").replace(/\r\n/g, "\n");
const block = (source: string, selector: string) => source.split(`${selector} {`)[1].split("}")[0];
const token = (source: string, name: string) => source.match(new RegExp(`--color-${name}: ([0-9 ]+);`))![1].split(" ").map(Number) as RGB;
const light = block(tokens, "@layer base {\n  :root"), dark = block(tokens, ":root.dark");
const alphas = [...pattern.matchAll(/--sw-pattern-alpha: ([0-9.]+)/g)].map(match => Number(match[1]));
const over = (ground: RGB, ink: RGB, alpha: number) => ground.map((value, i) => value * (1 - alpha) + ink[i] * alpha) as RGB;

describe("symbol pattern", () => {
  it("masks our own one-colour symbol and fades it out towards the centre", () => {
    const symbol = readFileSync("src/features/hub/landing/symbol-mask.svg", "utf8");
    expect(symbol).toBe(readFileSync("../docs/brand/symbol-one-colour-ink.svg", "utf8"));
    expect(pattern).toMatch(/mask-image: url\("\.\/symbol-mask\.svg"\), linear-gradient\(90deg, #000, transparent 30%, transparent 70%, #000\)/);
    expect(pattern).toMatch(/mask-composite: intersect/);
  });

  it("takes its colour from tokens: Deep Ink in light, the neutral muted grey in dark, smaller and fainter on phones", () => {
    expect(pattern).toMatch(/\.sw-hub \{ --sw-pattern-ink: var\(--color-ink\); --sw-pattern-alpha: 0\.045; --sw-pattern-tile: 172px 160px; \}/);
    expect(pattern).toMatch(/:root\.dark \.sw-hub \{ --sw-pattern-ink: var\(--color-muted\);/);
    expect(pattern).toMatch(/max-width: 767px[\s\S]*--sw-pattern-tile: 120px 112px/);
    expect(Math.max(...alphas)).toBeLessThanOrEqual(0.08);
  });

  it("never sits on a layer that moves in the pinned sequence", () => {
    expect(pattern).toMatch(/\.sw-hub-seq\[data-animated\] :is\(\.sw-hub-seq-copy, \.sw-hub-seq-reveal\)::before \{ content: none; \}/);
    expect(pattern.replace(/\/\*[\s\S]*?\*\//g, "")).not.toMatch(/transform|animation|transition/); // rules only, not comments
  });

  it("keeps muted and link text at AA over the densest tiles, on the page and on the overview band", () => {
    const [lightAlpha, darkAlpha] = [alphas[0], alphas[1]];
    for (const ground of ["bg", "surface"]) {
      const lit = over(token(light, ground), token(light, "ink"), lightAlpha);
      expect([ground, contrast(token(light, "muted"), lit) >= 4.5]).toEqual([ground, true]);
      expect([ground, contrast(token(light, "accent-ink"), lit) >= 4.5]).toEqual([ground, true]);
      const night = over(token(dark, ground), token(dark, "muted"), darkAlpha);
      expect([ground, contrast(token(dark, "muted"), night) >= 4.5]).toEqual([ground, true]);
      expect([ground, contrast(token(dark, "accent-ink"), night) >= 4.5]).toEqual([ground, true]);
    }
  });
});
