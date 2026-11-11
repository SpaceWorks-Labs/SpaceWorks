import { describe, expect, it } from "vitest";
import { applyFilterOps, cssFilter, DEFAULT_COVER_EDITS, dragPan, filterOps, guidesFor, placement } from "./coverMath";

describe("cover geometry", () => {
  it("always covers the frame, even rotated and straightened", () => {
    const place = placement({ ...DEFAULT_COVER_EDITS, straighten: 12 }, 4000, 3000);
    const cos = Math.abs(Math.cos(place.angle)), sin = Math.abs(Math.sin(place.angle));
    expect(4000 * place.scale).toBeGreaterThanOrEqual(cos * place.W + sin * place.H - 1e-6);
    expect(3000 * place.scale).toBeGreaterThanOrEqual(sin * place.W + cos * place.H - 1e-6);
  });
  it("keeps a drag inside the room the zoom leaves", () => {
    expect(dragPan({ ...DEFAULT_COVER_EDITS, zoom: 2 }, 4000, 3000, 100000, 0).panX).toBe(1);
    expect(dragPan(DEFAULT_COVER_EDITS, 1680, 735, 500, 0).panX).toBe(0);
  });
  it("draws guides only for crops that differ from the frame", () => {
    expect(guidesFor("banner").map(guide => guide.id)).toEqual(["cards", "social"]);
    expect(guidesFor("square")).toHaveLength(3);
  });
});

describe("cover colour", () => {
  it("applies the look first, then the sliders, as a CSS filter", () => {
    expect(cssFilter(filterOps({ look: "mono", brightness: 0, contrast: 20, saturation: 0 }))).toBe("grayscale(1) contrast(1.1) contrast(1.2)");
    expect(cssFilter(filterOps(DEFAULT_COVER_EDITS))).toBe("none");
  });
  it("matches the canvas filter in the pixel fallback", () => {
    const pixel = new Uint8ClampedArray([200, 100, 50, 255]);
    applyFilterOps(pixel, [{ fn: "grayscale", amount: 1 }]);
    expect(pixel[0]).toBe(pixel[1]);
    expect(pixel[1]).toBe(pixel[2]);
  });
});
