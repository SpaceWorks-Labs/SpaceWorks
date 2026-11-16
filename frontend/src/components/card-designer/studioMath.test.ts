import { describe, expect, it } from "vitest";

import { gradientCss, imageBox, maskCss, outlinePx, paintedBox, roundedRadius, sampleStops } from "./studioMath";
import { marqueeHits } from "./marquee";
import type { Layer } from "./cardTypes";

describe("image framing (spec section 2 position rule)", () => {
  it("covers the box and centres by default", () => {
    const box = imageBox(50, 80, 200, 100, "cover");
    expect(box.h).toBeCloseTo(80);
    expect(box.w).toBeCloseTo(160);
    expect(box.x).toBeCloseTo(-55);
  });
  it("moves with the focal point and scales with zoom", () => {
    const left = imageBox(50, 80, 200, 100, "cover", 1, 0, 50);
    expect(left.x).toBeCloseTo(0);
    const zoomed = imageBox(50, 80, 200, 100, "cover", 2, 100, 100);
    expect(zoomed.w).toBeCloseTo(320);
    expect(zoomed.x).toBeCloseTo(50 - 320);
  });
  it("contain leaves free space the focal point distributes", () => {
    const box = imageBox(100, 100, 50, 25, "contain", 1, 50, 100);
    expect([box.w, box.h]).toEqual([100, 50]);
    expect(box.y).toBe(50);
  });
});

describe("masks and outlines", () => {
  it("rounded uses 14 percent of the shorter side when no radius is given", () => {
    expect(roundedRadius(20, 30, null)).toBeCloseTo(2.8);
    expect(roundedRadius(20, 30, 4)).toBe(4);
  });
  it("circle on a non-square box is the inscribed circle", () => {
    expect(maskCss("circle", 20, 30, 10).clipPath).toBe("circle(100px at 50% 50%)");
    expect(maskCss("circle", 20, 20, 10).borderRadius).toBe("50%");
  });
  it("an arch has a semicircular top; too short falls back to rounded", () => {
    expect(maskCss("arch", 20, 40, 10).borderRadius).toBe("100px 100px 0 0");
    expect(maskCss("arch", 20, 5, 10).borderRadius).toBe(`${roundedRadius(20, 5, null) * 10}px`);
  });
  it("sticker outline dilates by width x 11.81 px and counts as part of the layer box", () => {
    expect(outlinePx({ width_mm: 1, colour: "#FFFFFF" })).toBe(12);
    expect(paintedBox({ x: 10, y: 10, w: 20, h: 30 }, { width_mm: 1, colour: "#FFFFFF" })).toEqual({ x: 9, y: 9, w: 22, h: 32 });
  });
});

describe("gradients", () => {
  it("radial radius is a share of half the diagonal", () => {
    const css = gradientCss({ type: "radial", angle_deg: 0, cx_pct: 30, cy_pct: 70, radius_pct: 50,
      stops: [{ colour: "#000000", at: 0 }, { colour: "#FFFFFF", at: 100 }] }, 30, 40);
    expect(css).toContain("circle 12.5mm at 30% 70%");
  });
  it("interpolates alpha straight, not premultiplied", () => {
    const samples = sampleStops([{ colour: "#000000", at: 0, alpha_pct: 0 }, { colour: "#FFFFFF", at: 100, alpha_pct: 100 }], 3);
    expect(samples[1].colour).toBe("#808080");
    expect(samples[1].alpha_pct).toBeCloseTo(50);
  });
});

describe("marquee selection", () => {
  const layer = (id: string, x: number, group?: string): Layer => ({ id, kind: "text", name: "", x_mm: x, y_mm: 0, w_mm: 10, h_mm: 10,
    rotation: 0, opacity: 100, locked: false, hidden: false, group });
  it("selects touched layers and whole groups, skipping locked and tiny drags", () => {
    const layers = [layer("a", 0, "g"), layer("b", 50, "g"), layer("c", 100)];
    expect(marqueeHits(layers, { x0: -1, y0: -1, x1: 12, y1: 12, additive: false })).toEqual(["a", "b"]);
    expect(marqueeHits(layers, { x0: 0, y0: 0, x1: 0.5, y1: 0.5, additive: false })).toEqual([]);
    expect(marqueeHits([{ ...layers[2], locked: true }], { x0: 90, y0: 0, x1: 120, y1: 20, additive: false })).toEqual([]);
  });
});
