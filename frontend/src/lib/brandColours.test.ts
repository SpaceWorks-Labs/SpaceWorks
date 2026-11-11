/// <reference types="node" />
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { BRAND_SURFACES, BODY_TEXT, FIXED_INKS, FIXED_SOFTS, PRODUCT_FILL, brandContrastReport, contrast, deriveBrandPalette, rgb, tenantColourStyle, type BrandTokens } from "./brandColours";

const light: BrandTokens = { fillText: [255, 244, 232], defaultFill: [0, 110, 99], surfaces: BRAND_SURFACES.light };
const dark: BrandTokens = { ...light, surfaces: BRAND_SURFACES.dark };
const modes = ["light", "dark"] as const;

function expectAccessible(theme: Record<string, string>) {
  const report = brandContrastReport(theme);
  expect(report.valid).toBe(true);
  expect(report.failures).toEqual([]);
  expect(report.pairs.every(({ ratio, minimum }) => ratio >= minimum)).toBe(true);
}

describe("tenant colours", () => {
  it("uses WCAG sRGB transfer and strict shorthand parsing", () => {
    expect(contrast([0, 0, 0], [255, 255, 255])).toBe(21);
    expect(contrast([100, 100, 100], [100, 100, 100])).toBe(1);
    expect(contrast([117, 117, 117], [255, 255, 255])).toBeCloseTo(4.6075, 4);
    expect(rgb("#aBc")).toEqual([170, 187, 204]);
    expect(rgb("#ffffff\n")).toBeNull();
  });
  it.each(["#000", "#fff", "#f3c3dd", "#004400", "#abc"])("derives accessible colours for %s in both modes", (primary_color) => {
    expectAccessible({ primary_color, accent_color: "#5a1633" });
  });
  it("prefers the brand neutrals for labels", () => {
    expect(tenantColourStyle({ primary_color: "#000" }, light)["--color-on-brand" as keyof React.CSSProperties]).toBe("255 244 232");
    expect(tenantColourStyle({ primary_color: "#fff" }, dark)["--color-on-brand" as keyof React.CSSProperties]).toBe("20 44 42");
  });
  it("shares interaction and link goldens with the backend", () => {
    const palette = deriveBrandPalette({ primary_color: "#004400" }, "light");
    expect(palette.fill).toEqual([0, 68, 0]);
    expect(palette.hover).toEqual([26, 86, 23]);
    expect(palette.active).toEqual([51, 103, 46]);
    expect(palette.foreground).toEqual([255, 244, 232]);
    expect(deriveBrandPalette({ primary_color: "#004400" }, "dark").ink).toEqual([128, 156, 116]);
    const theme = { primary_color: "#f3c3dd", accent_color: "#5a1633" };
    expect(deriveBrandPalette(theme, "light").ink).toEqual([90, 22, 51]);
    expect(deriveBrandPalette(theme, "dark").ink).toEqual([182, 146, 152]);
  });
  it.each(["#777", "#e91e63"])("accepts %s with a black label", (primary_color) => {
    expectAccessible({ primary_color });
    modes.forEach((mode) => expect(deriveBrandPalette({ primary_color }, mode).foreground).toEqual([0, 0, 0]));
  });
  it("accepts the 64-colour grid with and without a link seed", () => {
    for (const r of [0, 85, 170, 255]) for (const g of [0, 85, 170, 255]) for (const b of [0, 85, 170, 255]) {
      const primary_color = `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
      expectAccessible({ primary_color });
      expectAccessible({ primary_color, accent_color: "#5a1633" });
    }
  });
  it("emits only the seven scoped brand tokens", () => {
    expect(Object.keys(tenantColourStyle({ primary_color: "#fff" }, light))).toEqual([
      "--color-brand", "--color-on-brand", "--color-brand-ink", "--color-brand-hover", "--color-brand-active", "--color-brand-soft", "--color-brand-boundary",
    ]);
  });
  it("derives opaque soft fills that protect every fixed ink", () => {
    expect(deriveBrandPalette({ primary_color: "#fff" }, "dark").soft).toEqual([46, 59, 57]);
    expect(deriveBrandPalette({ primary_color: "#000" }, "light").soft).toEqual([229, 229, 229]);
    modes.forEach((mode) => {
      const palette = deriveBrandPalette({ primary_color: "#fff" }, mode);
      [...BODY_TEXT[mode], ...FIXED_INKS[mode]].forEach((text) => expect(contrast(text, palette.soft)).toBeGreaterThanOrEqual(4.55));
      FIXED_SOFTS[mode].forEach((soft) => expect(contrast(palette.ink, soft)).toBeGreaterThanOrEqual(4.5));
    });
  });
  it.each([null, [], "#fff", { primary_color: "#77" }, { primary_color: "red" }, { primary_color: "#gggggg" }, { primary_color: 0 }, { accent_color: false }])("rejects malformed colour values: %j", (theme) => {
    expect(brandContrastReport(theme).valid).toBe(false);
    expect(tenantColourStyle(theme, light)).toEqual({});
    expect(tenantColourStyle(theme, dark)).toEqual({});
  });
  it("keeps defaults identical to the rendered CSS, including all contrast constants", () => {
    const css = readFileSync("src/index.css", "utf8");
    modes.forEach((mode) => {
      const block = css.split(mode === "light" ? ":root {" : ":root.dark {")[1].split("}")[0];
      const token = (name: string) => block.match(new RegExp(`--color-${name}: ([0-9 ]+);`))![1].split(" ").map(Number);
      const palette = deriveBrandPalette({}, mode);
      expect(palette.fill).toEqual(PRODUCT_FILL[mode]);
      BRAND_SURFACES[mode].forEach((surface, i) => expect(surface).toEqual(token(["bg", "surface", "panel", "hover"][i])));
      BODY_TEXT[mode].forEach((text, i) => expect(text).toEqual(token(["ink", "muted"][i])));
      FIXED_INKS[mode].forEach((text, i) => expect(text).toEqual(token(["accent-ink", "success-ink", "warn-ink", "info-ink", "danger"][i])));
      FIXED_SOFTS[mode].forEach((soft, i) => expect(soft).toEqual(token(`${["accent", "emphasis", "success", "warn", "info"][i]}-soft`)));
      for (const key of ["fill", "foreground", "hover", "active", "soft", "ink"] as const) {
        expect(palette[key]).toEqual(token({ fill: "brand", foreground: "on-brand", hover: "brand-hover", active: "brand-active", soft: "brand-soft", ink: "brand-ink" }[key]));
      }
      expectAccessible({});
    });
  });
});
