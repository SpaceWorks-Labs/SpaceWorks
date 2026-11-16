import { describe, expect, it } from "vitest";
import type { Layer, LayerDocument } from "../layout";
import { pagePreset, resizePage } from "../layout";
import { alignToPage, contrast, hasNameTag, measurablePaper, resizeFromCorner, rotationFrom, snapMove } from "./geometry";
import { certificateSampleValues } from "./samples";

const page = { width: 297, height: 210 };
const layer = (patch: Partial<Layer> = {}): Layer => ({ id: "a", order: 0, type: "text", x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 20, rotation: 0, text: "{{name}}", ...patch });

describe("snapping", () => {
  it("snaps a box's centre to the page centre on both axes and reports guides", () => {
    const result = snapMove({ x_mm: 127.5, y_mm: 94, width_mm: 40, height_mm: 20 }, [], page, 2);
    expect(result.box.x_mm).toBe(128.5);
    expect(result.box.y_mm).toBe(95);
    expect(result.guides.map((g) => g.axis).sort()).toEqual(["x", "y"]);
  });
  it("snaps to another layer's edge and stays on the page", () => {
    const result = snapMove({ x_mm: 51, y_mm: 300, width_mm: 40, height_mm: 20 }, [{ x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 20 }], page, 2);
    expect(result.box.x_mm).toBe(50);
    expect(result.box.y_mm).toBe(190);
  });
});

describe("resizing and rotating", () => {
  it("keeps a picture's aspect unless stretched, and a QR square at 20 mm or more", () => {
    const start = { x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 20 };
    const locked = resizeFromCorner(start, "se", 20, 0, layer({ type: "logo" }), page, false);
    expect(locked.width_mm / locked.height_mm).toBeCloseTo(2);
    const free = resizeFromCorner(start, "se", 20, 0, layer({ type: "logo" }), page, true);
    expect([free.width_mm, free.height_mm]).toEqual([60, 20]);
    const qr = resizeFromCorner({ x_mm: 10, y_mm: 10, width_mm: 25, height_mm: 25 }, "nw", 20, 20, layer({ type: "certificate_qr" }), page, true);
    expect(qr.width_mm).toBe(qr.height_mm);
    expect(qr.width_mm).toBeGreaterThanOrEqual(20);
  });
  it("rotates in 15 degree steps with Shift and right angles for QR codes", () => {
    expect(rotationFrom({ x: 0, y: 0 }, { x: 10, y: -10 }, layer(), true)).toBe(45);
    expect(rotationFrom({ x: 0, y: 0 }, { x: 10, y: -2 }, layer({ type: "certificate_qr" }), false)).toBe(90);
  });
  it("aligns to page edges and centres", () => {
    const box = { x_mm: 10, y_mm: 10, width_mm: 40, height_mm: 20 };
    expect(alignToPage(box, page, "center")).toEqual({ x_mm: 128.5 });
    expect(alignToPage(box, page, "bottom")).toEqual({ y_mm: 190 });
  });
});

describe("checks and presets", () => {
  const doc = (layers: Layer[]): LayerDocument => ({ version: 2, page_width_mm: 297, page_height_mm: 210, layers });
  it("measures WCAG contrast and knows when the paper is covered", () => {
    expect(contrast("#000000", "#FFFFFF")).toBe(21);
    expect(contrast("#DFFF8F", "#FFFFFF")).toBeLessThan(4.5);
    expect(measurablePaper(doc([layer({ type: "image", width_mm: 297, height_mm: 210, x_mm: 0, y_mm: 0 })]))).toBe(false);
  });
  it("warns when no visible layer prints the name", () => {
    expect(hasNameTag(doc([layer()]))).toBe(true);
    expect(hasNameTag(doc([layer({ hidden: true })]))).toBe(false);
  });
  it("recognises and applies page presets, keeping QR codes scannable", () => {
    expect(pagePreset(297, 210)).toBe("a4-landscape");
    expect(pagePreset(215.9, 279.4)).toBe("letter-portrait");
    const portrait = resizePage(doc([layer({ type: "certificate_qr", width_mm: 25, height_mm: 25, x_mm: 260, y_mm: 170 })]), 210, 297);
    expect(portrait.layers[0].width_mm).toBeGreaterThanOrEqual(20);
    expect(portrait.layers[0].x_mm + portrait.layers[0].width_mm).toBeLessThanOrEqual(210);
  });
  it("fills sample merge values per kind", () => {
    expect(certificateSampleValues("Priya", "winner")).toMatchObject({ kind: "Winner", place: "1st place", name: "Priya" });
  });
});
