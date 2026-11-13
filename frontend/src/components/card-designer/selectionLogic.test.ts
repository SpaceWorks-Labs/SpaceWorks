import { describe, expect, it } from "vitest";

import { alignLayers, distributeLayers } from "./alignment";
import { copyLayers, duplicateLayers, pasteLayers } from "./clipboard";
import { MAX_LAYERS } from "./designDocument";
import { doc, layer, side } from "./designerFixtures.test";
import { boundsOf, clickSelection, groupLabels, groupLayers, pruneSelection, removeLayers, selectAll, ungroupLayers } from "./selection";

describe("selection and groups", () => {
  const a = layer({ id: "a", group: "g1" }), b = layer({ id: "b", group: "g1" }), c = layer({ id: "c" });
  const layers = [a, b, c];

  it("a plain click selects the whole group, Alt-click one member", () => {
    expect(clickSelection(layers, [], "a").sort()).toEqual(["a", "b"]);
    expect(clickSelection(layers, [], "a", { single: true })).toEqual(["a"]);
    expect(clickSelection(layers, [], "c")).toEqual(["c"]);
  });

  it("the clicked layer is last (the primary)", () => {
    expect(clickSelection(layers, [], "b")).toEqual(["a", "b"]);
  });

  it("a plain click inside the selection keeps it, so it can be dragged", () => {
    const current = ["a", "b", "c"];
    expect(clickSelection(layers, current, "c")).toBe(current);
  });

  it("Shift/Ctrl adds and removes, a group at a time", () => {
    expect(clickSelection(layers, ["c"], "a", { additive: true }).sort()).toEqual(["a", "b", "c"]);
    expect(clickSelection(layers, ["a", "b", "c"], "b", { additive: true })).toEqual(["c"]);
    expect(clickSelection(layers, ["c"], "c", { additive: true })).toEqual([]);
  });

  it("select all takes visible layers only and pruning drops gone ids", () => {
    const s = side([a, layer({ id: "h", hidden: true }), c]);
    expect(selectAll(s)).toEqual(["a", "c"]);
    expect(pruneSelection(s, ["a", "zz"])).toEqual(["a"]);
    const kept = ["a"];
    expect(pruneSelection(s, kept)).toBe(kept);
  });

  it("groups get a fresh id, ungroup clears it, labels follow stacking order", () => {
    const document = doc([layer({ id: "x" }), layer({ id: "y" }), layer({ id: "z" })]);
    const grouped = groupLayers(document, "front", ["x", "z"], "new-group");
    expect(grouped.front.layers.map((item) => item.group ?? null)).toEqual(["new-group", null, "new-group"]);
    expect(groupLayers(document, "front", ["x"])).toBe(document);
    expect(ungroupLayers(grouped, "front", ["x", "z"]).front.layers.every((item) => !item.group)).toBe(true);
    expect(groupLabels([layer({ group: "q" }), layer({ group: "p" }), layer({ group: "q" })])).toEqual({ q: "A", p: "B" });
  });

  it("delete keeps locked layers", () => {
    const document = doc([layer({ id: "x" }), layer({ id: "y", locked: true })]);
    expect(removeLayers(document, "front", ["x", "y"]).front.layers.map((item) => item.id)).toEqual(["y"]);
  });

  it("bounds cover every layer", () => {
    expect(boundsOf([layer({ x_mm: 5, y_mm: 6, w_mm: 10, h_mm: 4 }), layer({ x_mm: 20, y_mm: 2, w_mm: 5, h_mm: 5 })]))
      .toEqual({ x: 5, y: 2, w: 20, h: 8 });
  });
});

describe("align and distribute", () => {
  it("one layer aligns to the card, or to the safe area", () => {
    const s = side([layer({ id: "a", x_mm: 30, y_mm: 20, w_mm: 10, h_mm: 10 })]);
    expect(alignLayers(s, ["a"], "left")).toEqual({ a: { x_mm: 0, y_mm: 20 } });
    expect(alignLayers(s, ["a"], "right", true)).toEqual({ a: { x_mm: 72.6, y_mm: 20 } });
    expect(alignLayers(s, ["a"], "middle")).toEqual({ a: { x_mm: 30, y_mm: 22 } });
  });

  it("several align to their bounds; locked layers and their groups never move", () => {
    const s = side([layer({ id: "a", x_mm: 10 }), layer({ id: "b", x_mm: 30 }), layer({ id: "l", x_mm: 50, locked: true })]);
    const patches = alignLayers(s, ["a", "b", "l"], "right");
    expect(patches).toEqual({ a: { x_mm: 50, y_mm: 10 }, b: { x_mm: 50, y_mm: 10 } });
    expect(patches.l).toBeUndefined();
  });

  it("a group aligns as one unit", () => {
    const s = side([layer({ id: "a", x_mm: 20, group: "g" }), layer({ id: "b", x_mm: 40, group: "g" })]);
    expect(alignLayers(s, ["a", "b"], "left")).toEqual({ a: { x_mm: 0, y_mm: 10 }, b: { x_mm: 20, y_mm: 10 } });
  });

  it("distributes equal gaps between the outer two", () => {
    const s = side([layer({ id: "a", x_mm: 0, w_mm: 10 }), layer({ id: "b", x_mm: 12, w_mm: 10 }), layer({ id: "c", x_mm: 50, w_mm: 10 })]);
    expect(distributeLayers(s, ["a", "b", "c"], "horizontal")).toEqual({ b: { x_mm: 25, y_mm: 10 } });
    expect(distributeLayers(s, ["a", "b"], "horizontal")).toEqual({});
  });
});

describe("copy, paste and duplicate", () => {
  let n = 0;
  const makeId = () => `new-${++n}`;

  it("pastes with new ids, new group ids and a 2 mm offset", () => {
    const front = [layer({ id: "a", group: "g", x_mm: 5 }), layer({ id: "b", group: "g", x_mm: 15 }), layer({ id: "c", group: "solo" })];
    const clip = copyLayers(front, ["a", "b", "c"]);
    const result = pasteLayers(doc(front), "back", clip, { makeId });
    const pasted = result.document.back.layers;
    expect(pasted).toHaveLength(3);
    expect(new Set(pasted.map((item) => item.id)).size).toBe(3);
    expect(pasted.every((item) => !["a", "b", "c"].includes(item.id))).toBe(true);
    expect(pasted[0].group).toBe(pasted[1].group);
    expect(pasted[0].group).not.toBe("g");
    expect(pasted[2].group).toBeNull();
    expect(pasted[0].x_mm).toBe(7);
    expect(result.ids).toEqual(pasted.map((item) => item.id));
  });

  it("keeps pasted layers on the card", () => {
    const front = [layer({ id: "edge", x_mm: 80, w_mm: 5.6 })];
    expect(pasteLayers(doc(front), "front", front, { makeId }).document.front.layers[1].x_mm).toBe(80);
  });

  it("stops at the layer cap", () => {
    const full = Array.from({ length: MAX_LAYERS }, () => layer());
    const document = doc(full);
    expect(pasteLayers(document, "front", [layer()], { makeId })).toEqual({ document, ids: [] });
  });

  it("duplicate renames named layers", () => {
    const document = doc([layer({ id: "a", name: "Logo" })]);
    const result = duplicateLayers(document, "front", ["a"]);
    expect(result.document.front.layers[1].name).toBe("Logo copy");
  });
});
