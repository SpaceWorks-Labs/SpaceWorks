import { describe, expect, it } from "vitest";
import type { Layer, Side } from "./cardTypes";
import { layerContrast, luminance, MINIMUM_RATIO, ratio, rgb, unreadable } from "./contrast";

const side = (background: Side["background"], layers: Partial<Layer>[]): Side => ({ page_width_mm: 100, page_height_mm: 60, background, layers: layers as Layer[] } as Side);
const text = (over: Partial<Layer> = {}): Partial<Layer> => ({ kind: "text", x_mm: 0, y_mm: 0, w_mm: 100, h_mm: 60, colour: "#000000", ...over });
const white = { kind: "colour", colour: "#ffffff" } as const;

describe("colour maths", () => {
  it("parses hex into channels", () => expect(rgb("#ff8000")).toEqual([255, 128, 0]));
  it("computes the WCAG luminance extremes", () => {
    expect(luminance([0, 0, 0])).toBe(0);
    expect(luminance([255, 255, 255])).toBeCloseTo(1, 6);
  });
  it("gives 21:1 for black on white regardless of argument order, and 1:1 for equal colours", () => {
    expect(ratio([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 5);
    expect(ratio([255, 255, 255], [0, 0, 0])).toBeCloseTo(21, 5);
    expect(ratio([9, 9, 9], [9, 9, 9])).toBe(1);
  });
  it("uses the linear branch for very dark channels", () => expect(luminance([5, 5, 5])).toBeCloseTo(5 / 255 / 12.92, 6));
});

describe("layerContrast", () => {
  it("is null for a missing layer, a non-text layer, and a text layer without a colour", () => {
    expect(layerContrast(side(white, []), 0)).toBeNull();
    expect(layerContrast(side(white, [{ kind: "image" }]), 0)).toBeNull();
    expect(layerContrast(side(white, [text({ colour: undefined })]), 0)).toBeNull();
  });
  it("measures a data field like a text layer", () => expect(layerContrast(side(white, [text({ kind: "data_field" })]), 0)).toBeCloseTo(21, 5));
  it("measures black text on a white colour background as 21:1", () => expect(layerContrast(side(white, [text()]), 0)).toBeCloseTo(21, 5));
  it("blends partly transparent text with the background", () => {
    const full = layerContrast(side(white, [text()]), 0)!;
    expect(layerContrast(side(white, [text({ opacity: 50 })]), 0)!).toBeLessThan(full);
  });
  it("dims an image background by its dim percentage and uses the asset colour, defaulting to mid grey", () => {
    const image = { kind: "image", asset_id: "a1", fit: "cover", dim_pct: 100 } as const;
    // A full dim turns any image black, so white text reads 21:1 on it.
    expect(layerContrast(side(image, [text({ colour: "#ffffff" })]), 0)).toBeCloseTo(21, 5);
    const bright = { ...image, dim_pct: 0 } as const;
    expect(layerContrast(side(bright, [text({ colour: "#ffffff" })]), 0, { a1: "#ffffff" })).toBeCloseTo(1, 5);
    expect(layerContrast(side(bright, [text({ colour: "#000000" })]), 0, { a1: "#ffffff" })).toBeCloseTo(21, 5);
    expect(layerContrast(side(bright, [text({ colour: "#000000" })]), 0)!).toBeCloseTo(ratio([0, 0, 0], [128, 128, 128]), 5);
  });
  it("samples a linear gradient at the text centre", () => {
    const gradient = { kind: "gradient", type: "linear", angle_deg: 90, stops: [{ colour: "#000000", at: 0 }, { colour: "#ffffff", at: 100 }] } as const;
    const left = layerContrast(side(gradient, [text({ colour: "#ffffff", x_mm: 0, w_mm: 2 })]), 0)!;
    const right = layerContrast(side(gradient, [text({ colour: "#ffffff", x_mm: 98, w_mm: 2 })]), 0)!;
    expect(left).toBeGreaterThan(MINIMUM_RATIO);
    expect(right).toBeLessThan(1.2);
  });
  it("samples a radial gradient from the centre outwards", () => {
    const radial = { kind: "gradient", type: "radial", angle_deg: 0, stops: [{ colour: "#ffffff", at: 0 }, { colour: "#000000", at: 100 }] } as const;
    const centre = layerContrast(side(radial, [text({ colour: "#000000", x_mm: 49, y_mm: 29, w_mm: 2, h_mm: 2 })]), 0)!;
    const corner = layerContrast(side(radial, [text({ colour: "#000000", x_mm: 98, y_mm: 58, w_mm: 2, h_mm: 2 })]), 0)!;
    expect(centre).toBeCloseTo(21, 0);
    expect(corner).toBeLessThan(1.5);
  });
  it("handles a gradient whose stops are out of order and a flat stop pair", () => {
    const g = { kind: "gradient", type: "linear", angle_deg: 0, stops: [{ colour: "#ffffff", at: 50 }, { colour: "#ffffff", at: 50 }, { colour: "#000000", at: 0 }] } as const;
    // Angle 0 runs bottom (t=0, black) to top (t=100): text at the top sits past the last stop, on white.
    expect(layerContrast(side(g, [text({ colour: "#000000", y_mm: 0, h_mm: 2 })]), 0)).toBeCloseTo(21, 0);
    // ...and text at the bottom sits on near-black, where black text is unreadable.
    expect(layerContrast(side(g, [text({ colour: "#000000", y_mm: 58, h_mm: 2 })]), 0)!).toBeLessThan(1.2);
  });
  it("includes a filled shape beneath the text, with its opacity", () => {
    const dark = { kind: "shape", shape: "rect", fill: "#000000", x_mm: 0, y_mm: 0, w_mm: 100, h_mm: 60 };
    expect(layerContrast(side(white, [dark, text({ colour: "#ffffff" })]), 1)).toBeCloseTo(21, 5);
    expect(layerContrast(side(white, [{ ...dark, opacity: 0 }, text({ colour: "#000000" })]), 1)).toBeCloseTo(21, 5);
  });
  it.each([
    ["hidden", { hidden: true }], ["without fill", { fill: undefined }], ["a line", { shape: "line" }],
    ["outside the text", { x_mm: 200 }], ["not a shape or band", { kind: "image" }],
  ])("ignores a layer beneath that is %s", (_name, over) => {
    const below = { kind: "shape", shape: "rect", fill: "#000000", x_mm: 0, y_mm: 0, w_mm: 100, h_mm: 60, ...over } as Partial<Layer>;
    expect(layerContrast(side(white, [below, text({ colour: "#000000" })]), 1)).toBeCloseTo(21, 5);
  });
  it("counts a band like a shape", () => expect(layerContrast(side(white, [{ kind: "band", fill: "#000000", x_mm: 0, y_mm: 0, w_mm: 100, h_mm: 60 },
    text({ colour: "#ffffff" })]), 1)).toBeCloseTo(21, 5));
  it("ignores layers above the text", () => expect(layerContrast(side(white, [text({ colour: "#000000" }),
    { kind: "shape", shape: "rect", fill: "#000000", x_mm: 0, y_mm: 0, w_mm: 100, h_mm: 60 }]), 0)).toBeCloseTo(21, 5));
});

describe("unreadable", () => {
  it("lists the visible text layers under 4.5:1, never hidden ones or non-text layers", () => {
    const s = side(white, [text({ colour: "#eeeeee" }), text({ colour: "#eeeeee", hidden: true }), text({ colour: "#000000" }), { kind: "image" }]);
    expect(unreadable(s)).toEqual([s.layers[0]]);
  });
});
