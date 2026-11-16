// CARD-STUDIO-2 (decision 344(b)) editor operations: stacking, lock/hide, zoom steps, keyboard commands, snapping to the
// document guides, aligning to the document's safe zone, ruler guide lines, the photo variant pick, brand swatches,
// polygon geometry and the icon library copy.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { alignLayers } from "./alignment";
import { kitSwatches } from "./brandKit";
import { moveSelection, stepZoom } from "./canvasMath";
import { addRulerLine } from "./designDocument";
import { doc, layer, side } from "./designerFixtures.test";
import { exportBleed } from "./DesignToolbar";
import { holderPhotoState, pickPhoto, SAMPLE_PHOTO } from "./photoVariant";
import { designerCommand, shortcutGroups } from "./shortcuts";
import { restack, restackLayers } from "./stacking";
import { polygonPoints } from "./studioMath";

const ids = (layers: { id: string }[]) => layers.map((item) => item.id);
const key = (k: string, extra: Partial<KeyboardEvent> = {}) =>
  designerCommand({ key: k, ctrlKey: true, metaKey: false, shiftKey: false, altKey: false, target: null, ...extra });

describe("stacking order", () => {
  const stack = [layer({ id: "a" }), layer({ id: "b" }), layer({ id: "c" }), layer({ id: "d" })];
  it("brings a selection forward one step as a block", () => {
    expect(ids(restackLayers(stack, ["b", "c"], "forward"))).toEqual(["a", "d", "b", "c"]);
    expect(ids(restackLayers(stack, ["d"], "forward"))).toEqual(["a", "b", "c", "d"]);
  });
  it("sends backward, to the front and to the back keeping relative order", () => {
    expect(ids(restackLayers(stack, ["c"], "backward"))).toEqual(["a", "c", "b", "d"]);
    expect(ids(restackLayers(stack, ["a", "c"], "front"))).toEqual(["b", "d", "a", "c"]);
    expect(ids(restackLayers(stack, ["b", "d"], "back"))).toEqual(["b", "d", "a", "c"]);
  });
  it("returns the same document when nothing selected is on the side", () => {
    const document = doc(stack);
    expect(restack(document, "front", ["zz"], "front")).toBe(document);
  });
});

describe("keyboard commands", () => {
  it("maps arrange, lock, hide and zoom shortcuts", () => {
    expect(key("]")).toEqual({ type: "stack", op: "forward" });
    expect(key("[")).toEqual({ type: "stack", op: "backward" });
    expect(key("}", { shiftKey: true })).toEqual({ type: "stack", op: "front" });
    expect(key("{", { shiftKey: true })).toEqual({ type: "stack", op: "back" });
    expect(key("L", { shiftKey: true })).toEqual({ type: "toggle", flag: "locked" });
    expect(key("H", { shiftKey: true })).toEqual({ type: "toggle", flag: "hidden" });
    expect(key("=")).toEqual({ type: "zoom", to: "in" });
    expect(key("-")).toEqual({ type: "zoom", to: "out" });
    expect(key("0")).toEqual({ type: "zoom", to: "fit" });
    expect(key("l")).toBeNull();
  });
  it("lists every shortcut group with translated rows", () => {
    const groups = shortcutGroups();
    expect(groups.map((group) => group.title)).toEqual(["Select", "View", "Arrange", "Move and size", "Edit"]);
    expect(groups.flatMap((group) => group.rows).every((row) => row.action.length > 0 && row.keys.length > 0)).toBe(true);
  });
});

describe("zoom steps", () => {
  it("steps 25 % within 50-400 % and counts fit as 100 %", () => {
    expect(stepZoom("fit", "in")).toBe(1.25);
    expect(stepZoom(1, "out")).toBe(0.8);
    expect(stepZoom(4, "in")).toBe(4);
    expect(stepZoom(0.5, "out")).toBe(0.5);
    expect(stepZoom(2, "fit")).toBe("fit");
  });
});

describe("snapping and aligning to the document guides", () => {
  const moving = layer({ id: "m", x_mm: 20, y_mm: 20, w_mm: 10, h_mm: 10 });
  it("snaps an edge to a custom ruler line and to the document's safe zone", () => {
    const s = side([moving]);
    const ruler = moveSelection(s, [moving], 20.6, 0, { gridMm: 0.1, guides: { rulers: [{ axis: "x", at_mm: 41 }] } });
    expect(ruler.patches.m.x_mm).toBe(41);
    expect(ruler.guides).toContainEqual({ axis: "x", at: 41 });
    const safe = moveSelection(s, [moving], -10.4, 0, { gridMm: 0.1, guides: { safe_mm: 10 } });
    expect(safe.patches.m.x_mm).toBe(10);
  });
  it("aligns to the safe zone the document sets (a certificate's 10 mm)", () => {
    expect(alignLayers(side([moving]), ["m"], "left", true, 10)).toEqual({ m: { x_mm: 10, y_mm: 20 } });
  });
  it("adds ruler lines from a ruler click, never twice and at most 20", () => {
    const once = addRulerLine(doc([]), "x", 12.5);
    expect(once.guides?.rulers).toEqual([{ axis: "x", at_mm: 12.5 }]);
    expect(addRulerLine(once, "x", 12.5)).toBe(once);
    const full = { ...once, guides: { ...once.guides!, rulers: Array.from({ length: 20 }, (_v, i) => ({ axis: "y" as const, at_mm: i })) } };
    expect(addRulerLine(full, "x", 1)).toBe(full);
  });
  it("exports with the design's bleed, or 3 mm when none is set", () => {
    expect(exportBleed(doc([]))).toBe(3);
    expect(exportBleed({ ...doc([]), guides: { bleed_mm: 2, safe_mm: 3, margin_mm: 0, punch_slot: null, rulers: [] } })).toBe(2);
  });
});

describe("photo variant (twin of rendering_photo.photo_source)", () => {
  const holder = (cutout: string | null, useCutout: boolean) => ({ cutout, useCutout, sample: false });
  it("prints a ready cut-out for `cutout`, and for `auto` only when the holder chose it", () => {
    expect(pickPhoto("cutout", holder("blob:c", false))).toBe("cutout");
    expect(pickPhoto("auto", holder("blob:c", false))).toBe("original");
    expect(pickPhoto("auto", holder("blob:c", true))).toBe("cutout");
    expect(pickPhoto("original", holder("blob:c", true))).toBe("original");
  });
  it("falls back to the original when no cut-out is ready; samples show the silhouette", () => {
    expect(pickPhoto("cutout", holder(null, true))).toBe("original");
    expect(pickPhoto("cutout", SAMPLE_PHOTO)).toBe("silhouette");
    expect(pickPhoto("auto", SAMPLE_PHOTO)).toBe("silhouette");
  });
  it("ignores a cut-out link the holder row says is not available", () => {
    expect(holderPhotoState("blob:c", { available: false, use_cutout: true }).cutout).toBeNull();
    expect(holderPhotoState("blob:c", { available: true, use_cutout: false })).toEqual({ cutout: "blob:c", useCutout: false, sample: false });
  });
});

describe("brand kit swatches", () => {
  it("puts the space colours first, drops bad values and duplicates", () => {
    const swatches = kitSwatches({ colours: [{ label: "Space colour", hex: "#006e63" }, { label: "Bad", hex: "url(x)" }],
      logos: [], fonts: [] });
    expect(swatches[0]).toEqual({ label: "Space colour", hex: "#006E63" });
    expect(swatches.filter((swatch) => swatch.hex === "#006E63")).toHaveLength(1);
    expect(swatches.every((swatch) => /^#[0-9A-F]{6}$/.test(swatch.hex))).toBe(true);
  });
});

describe("polygon shapes and the icon library", () => {
  it("places polygon vertices inside the box", () => {
    expect(polygonPoints("triangle", 20, 10)).toEqual([[10, 0], [20, 10], [0, 10]]);
    expect(polygonPoints("diamond", 8, 4)).toEqual([[4, 0], [8, 2], [4, 4], [0, 2]]);
    const star = polygonPoints("star", 10, 10);
    expect(star).toHaveLength(10);
    expect(star[0]).toEqual([5, 0]);
    expect(polygonPoints("rect", 10, 10)).toEqual([]);
  });
  const backend = resolve(__dirname, "../../../../backend/apps/card_designs/studio_icons.json");
  it.skipIf(!existsSync(backend))("ships the same icon file as the server renderer", () => {
    expect(readFileSync(resolve(__dirname, "studioIcons.json"), "utf-8")).toBe(readFileSync(backend, "utf-8"));
  });
});
