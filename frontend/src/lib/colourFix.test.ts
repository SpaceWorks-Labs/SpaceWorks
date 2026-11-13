import { describe, expect, it } from "vitest";
import cases from "./fixtures/themeContrastCases.json";
import { brandContrastReport, deriveBrandPalette } from "./brandColours";
import { advisoryPairs, issuesOf, suggestFix, toHex } from "./colourFix";
import { colourPresets } from "./colourPresets";

type Case = { theme: Record<string, string> } & Record<"light" | "dark", { fill: number[]; foreground: number[]; hover: number[]; active: number[]; soft: number[]; ink: number[]; pairs: [string, number, number][] }>;

// Fixture generated from backend/apps/makerspaces/theme_contrast.py; the backend pytest reads the same file.
describe("TS contrast mirror matches theme_contrast.py", () => {
  it.each((cases as Case[]).map((c) => [JSON.stringify(c.theme), c] as const))("theme %s", (_name, expected) => {
    for (const mode of ["light", "dark"] as const) {
      const got = deriveBrandPalette(expected.theme, mode), want = expected[mode];
      expect(got.fill).toEqual(want.fill);
      expect(got.foreground).toEqual(want.foreground);
      expect(got.hover).toEqual(want.hover);
      expect(got.active).toEqual(want.active);
      expect(got.soft).toEqual(want.soft);
      expect(got.ink).toEqual(want.ink);
      expect(got.pairs.map((p) => p.pair)).toEqual(want.pairs.map((p) => p[0]));
      got.pairs.forEach((p, i) => { expect(p.ratio).toBeCloseTo(want.pairs[i][1], 5); expect(p.minimum).toBe(want.pairs[i][2]); });
    }
  });
});

describe("presets", () => {
  it.each(colourPresets().map((p) => [p.name, p] as const))("%s passes every required check and the fill advice", (_name, preset) => {
    const theme = { primary_color: preset.primary, accent_color: preset.accent };
    expect(brandContrastReport(theme).failures).toEqual([]);
    expect(issuesOf(theme).advice).toEqual([]);
  });
  it("starts with the blank Space Works default", () => {
    expect(colourPresets()[0]).toMatchObject({ primary: "", accent: "" });
  });
});

describe("fix suggestion", () => {
  it("has nothing to fix for the default or a passing colour", () => {
    expect(suggestFix({})).toBeNull();
    expect(suggestFix({ primary_color: "#1d5fa8" })).toBeNull();
  });
  it("nudges a fill that vanishes on solid black to the nearest passing lightness", () => {
    const theme = { primary_color: "#142c2a", accent_color: "" };
    expect(issuesOf(theme).advice.map((p) => p.mode)).toEqual(["dark"]);
    const fix = suggestFix(theme)!;
    expect(fix.key).toBe("primary_color");
    const next = { ...theme, primary_color: fix.value };
    expect(issuesOf(next)).toEqual({ blocking: [], advice: [] });
    // one lightness step less would still fail
    expect(advisoryPairs(next).every((p) => p.ratio >= p.minimum)).toBe(true);
  });
  it("reports 3:1 for the advice pair and rounds hex output", () => {
    expect(advisoryPairs({ primary_color: "#000" }).find((p) => p.mode === "dark")!.ratio).toBe(1);
    expect(toHex([0, 110, 99])).toBe("#006e63");
  });
  it("gives no suggestion for malformed input", () => {
    expect(suggestFix({ primary_color: "red" })).toBeNull();
  });
});
