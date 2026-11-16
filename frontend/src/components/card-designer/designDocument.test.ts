import { describe, expect, it } from "vitest";

import type { CardDocument, Side } from "./cardTypes";
import { layerContrast } from "./contrast";
import { addLayer, applyStock, duplicateLayer, moveLayer, newLayer, patchLayer, removeLayer } from "./designDocument";
import { snapToGuides } from "./cardGeometry";

const side = (): Side => ({ page_width_mm: 85.6, page_height_mm: 53.98, background: { kind: "colour", colour: "#FFFFFF" }, layers: [] });
const doc = (): CardDocument => ({ version: 2, stock: "cr80-landscape", back_enabled: false, mono: false,
  watermark: { kind: "none", text: "", asset_id: null, opacity_pct: 10, angle_deg: -30, colour: "#006E63" }, front: side(), back: side() });

describe("design document edits", () => {
  it("adds, patches, reorders, duplicates and removes layers without mutating the original", () => {
    const start = doc();
    const text = newLayer("text", start.front, start.stock);
    const band = newLayer("band", start.front, start.stock);
    let next = addLayer(addLayer(start, "front", band), "front", text);
    expect(start.front.layers).toHaveLength(0);
    next = patchLayer(next, "front", text.id, { colour: "#FF0000" });
    expect(next.front.layers[1].colour).toBe("#FF0000");
    next = moveLayer(next, "front", text.id, "down");
    expect(next.front.layers[0].id).toBe(text.id);
    const copy = duplicateLayer(next, "front", text.id);
    expect(copy.document.front.layers).toHaveLength(3);
    expect(copy.id).not.toBe(text.id);
    next = removeLayer(copy.document, "front", text.id);
    expect(next.front.layers.map((layer) => layer.id)).not.toContain(text.id);
  });

  it("caps a side at 60 layers (decision 314)", () => {
    let next = doc();
    for (let i = 0; i < 65; i += 1) next = addLayer(next, "front", newLayer("shape", next.front, next.stock));
    expect(next.front.layers).toHaveLength(60);
  });

  it("new QR layers meet the stock's minimum and keep it when the stock changes", () => {
    const start = doc();
    const qr = newLayer("verify_qr", start.front, start.stock);
    expect(qr.w_mm).toBe(18);
    const a6 = applyStock(addLayer(start, "front", qr), "a6-portrait");
    expect(a6.front.page_width_mm).toBe(105);
    expect(a6.front.layers[0].w_mm).toBeGreaterThanOrEqual(20);
    expect(a6.front.layers[0].w_mm).toBe(a6.front.layers[0].h_mm);
    expect("page_width_mm" in a6).toBe(false);
    const custom = applyStock(start, "custom", 90, 60);
    expect(custom.page_width_mm).toBe(90);
  });

  it("measures text contrast against the band beneath it", () => {
    const start = doc();
    const band = newLayer("band", start.front, start.stock, { h_mm: 53.98 });
    const text = newLayer("text", start.front, start.stock, { colour: "#FFFFFF" });
    const next = addLayer(addLayer(start, "front", band), "front", text);
    expect(layerContrast(next.front, 1)).toBeGreaterThan(4.5);
    const plain = addLayer(start, "front", text);
    expect(layerContrast(plain.front, 0)).toBeLessThan(1.1);
  });

  it("snaps a moving layer's centre to the card centre", () => {
    const start = side();
    const layer = { ...newLayer("shape", start, "cr80-landscape"), w_mm: 10, h_mm: 10 };
    const snapped = snapToGuides(start, layer, 37.5, 5);
    expect(snapped.x).toBe(37.8);
    expect(snapped.guides.some((guide) => guide.axis === "x")).toBe(true);
  });
});
