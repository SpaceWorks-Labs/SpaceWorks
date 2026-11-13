import { describe, expect, it } from "vitest";

import { canvasWidth, equalSpacing, fitInside, minimumSize, moveSelection, pointerDeltaMm, pointerToMm, resizeLayer,
  rotationAt } from "./canvasMath";
import { layer, side } from "./designerFixtures.test";
import { fitText, wrap, type Measure } from "./textFit";

describe("zoom and pointer maths", () => {
  it("100 % fills the column, 150/200 % scale it, Fit also respects the height", () => {
    expect(canvasWidth(500, 1000, 85.6, 53.98, 1)).toBe(500);
    expect(canvasWidth(500, 1000, 85.6, 53.98, 2)).toBe(1000);
    expect(canvasWidth(500, 1000, 85.6, 53.98, 1.5)).toBe(750);
    expect(canvasWidth(500, 300, 53.98, 85.6, "fit")).toBeCloseTo(300 * 53.98 / 85.6);
    expect(fitInside(200, 100, 85.6, 53.98)).toBe(Math.min(200, 100 * 85.6 / 53.98));
  });

  it("a pointer movement is the same distance in mm at every zoom", () => {
    for (const zoom of [1, 1.5, 2] as const) {
      const px = canvasWidth(428, 1000, 85.6, 53.98, zoom) / 85.6;
      const { dx, dy } = pointerDeltaMm({ x: 100, y: 100 }, { x: 100 + 10 * px, y: 100 - 4 * px }, px);
      expect(dx).toBeCloseTo(10);
      expect(dy).toBeCloseTo(-4);
      expect(pointerToMm(50 + 20 * px, 70 + 5 * px, { left: 50, top: 70 }, px)).toEqual({ x: expect.closeTo(20), y: expect.closeTo(5) });
    }
  });
});

describe("moving a selection", () => {
  const other = layer({ id: "o", x_mm: 40, y_mm: 30, w_mm: 10, h_mm: 10 });

  it("snaps the moved bounds to other layers and reports the guide", () => {
    const moving = layer({ id: "m", x_mm: 10, y_mm: 10, w_mm: 10, h_mm: 5 });
    const result = moveSelection(side([moving, other]), [moving], 29.4, 0, { gridMm: 0.1 });
    expect(result.patches.m.x_mm).toBe(40);
    expect(result.guides).toContainEqual({ axis: "x", at: 40 });
  });

  it("Alt (free) skips the grid and guides", () => {
    const moving = layer({ id: "m", x_mm: 10, y_mm: 10, w_mm: 10, h_mm: 5 });
    const result = moveSelection(side([moving, other]), [moving], 29.43, 0, { gridMm: 1, free: true });
    expect(result.patches.m.x_mm).toBe(39.4);
    expect(result.guides).toEqual([]);
  });

  it("moves every selected layer by the same amount and keeps the selection on the card", () => {
    const a = layer({ id: "a", x_mm: 10, y_mm: 10 }), b = layer({ id: "b", x_mm: 30, y_mm: 20 });
    const result = moveSelection(side([a, b]), [a, b], 100, 0, { gridMm: 1 });
    expect(result.patches.b.x_mm).toBe(75.6);
    expect(result.patches.a.x_mm).toBe(55.6);
    expect(result.patches.a.y_mm).toBe(10);
  });

  it("finds equal spacing between two neighbours", () => {
    const left = layer({ id: "l", x_mm: 0, y_mm: 10, w_mm: 10 }), right = layer({ id: "r", x_mm: 50, y_mm: 10, w_mm: 10 });
    const box = { x: 24.5, y: 10, w: 10, h: 10 };
    const spaced = equalSpacing(side([left, right]), new Set(["m"]), box);
    expect(spaced.x).toBe(25);
    expect(spaced.hints[0].gaps).toEqual([[10, 25], [35, 50]]);
  });
});

describe("resizing", () => {
  const s = side([]);
  it("photos keep their shape unless Shift is held", () => {
    const photo = layer({ kind: "photo", w_mm: 20, h_mm: 25 });
    const kept = resizeLayer(s, photo, 4, 0, { gridMm: 1, stock: "cr80-landscape" });
    expect(kept.w_mm / kept.h_mm).toBeCloseTo(0.8, 1);
    const free = resizeLayer(s, photo, 4, 0, { gridMm: 1, stock: "cr80-landscape", shift: true });
    expect(free).toEqual({ w_mm: 24, h_mm: 25 });
  });

  it("other layers keep their shape only with Shift", () => {
    const shape = layer({ w_mm: 20, h_mm: 10 });
    expect(resizeLayer(s, shape, 4, 0, { gridMm: 1, stock: "cr80-landscape" })).toEqual({ w_mm: 24, h_mm: 10 });
    expect(resizeLayer(s, shape, 4, 0, { gridMm: 1, stock: "cr80-landscape", shift: true })).toEqual({ w_mm: 24, h_mm: 12 });
  });

  it("QR codes stay square and never drop under the stock minimum", () => {
    const qr = layer({ kind: "desk_qr", w_mm: 20, h_mm: 20 });
    const grown = resizeLayer(s, qr, 3, 0, { gridMm: 1, stock: "cr80-landscape" });
    expect(grown.w_mm).toBe(grown.h_mm);
    expect(resizeLayer(s, qr, -10, -10, { gridMm: 1, stock: "cr80-landscape" })).toEqual({ w_mm: 18, h_mm: 18 });
    expect(minimumSize(qr, "a6-portrait", s)).toEqual({ w: 20, h: 20 });
  });

  it("rotation snaps QR and barcodes to right angles, Shift to 15°", () => {
    const centre = { x: 0, y: 0 };
    expect(rotationAt(layer({ kind: "verify_qr" }), centre, { x: 10, y: 1 }, false)).toBe(90);
    expect(rotationAt(layer(), centre, { x: 10, y: -3 }, true)).toBe(75);
  });
});

describe("text fitting (mirrors the server)", () => {
  const measure: Measure = (text, size) => text.length * size * 0.5;
  const style = { family: "x", weight: 400, sizePt: 10, lineHeight: 1.2, trackingPt: 0, shrink: true };

  it("wraps on words", () => {
    expect(wrap("aa bb cc", 10, 20, measure)).toEqual(["aa", "bb", "cc"]);
    expect(wrap("aa bb cc", 10, 25, measure)).toEqual(["aa bb", "cc"]);
  });

  it("keeps a name on one line down to 60 % before wrapping", () => {
    expect(fitText("Priya Raman", style, 50, 12, measure)).toEqual({ sizePt: 9, oneLine: true });
  });

  it("wraps when one line would need less than 60 %", () => {
    const result = fitText("Alexandra Montgomery-Fitzgerald", style, 60, 40, measure);
    expect(result.oneLine).toBe(false);
  });

  it("leaves the size alone without shrink-to-fit", () => {
    expect(fitText("Priya Raman", { ...style, shrink: false }, 50, 12, measure).sizePt).toBe(10);
  });
});
