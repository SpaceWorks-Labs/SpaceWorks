// Preview parity: the TypeScript twin must reproduce the server's studio plan (decision 314), for every case in
// the golden fixtures the CARD-ENGINE lane writes (backend/apps/card_designs/fixtures/). Read-only here.
// Text widths depend on the real font files, which a unit test cannot measure, so the rich-plan cases use a
// measurer calibrated from the fixture's own expected widths (em-widths per word); line breaks, baselines, bars,
// rules and the shrink scale are then asserted exactly. Pixel-level parity is a browser check (screenshots).
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type { Layer } from "./cardTypes";
import { barcodeMinimum, barcodeRects, carriesDesk } from "./barcodes";
import { iconPaths } from "./IconLayerView";
import { pickPhoto } from "./photoVariant";
import { gradientLine, imageBox, polygonPoints, radialCircle, roundedRadius } from "./studioMath";
import { isRichText, planLayer, type MeasureText } from "./studioText";

const DIR = resolve(__dirname, "../../../../backend/apps/card_designs/fixtures");
const PLAN = resolve(DIR, "studio_plan_cases.json");
const COMPAT = resolve(DIR, "studio_compat_cases.json");
const present = existsSync(PLAN) && existsSync(COMPAT);
const load = <T>(path: string) => JSON.parse(readFileSync(path, "utf-8")) as { cases: T[] };

type Case = { id: string; kind: string; input: Record<string, any>; expected: Record<string, any> }; // eslint-disable-line @typescript-eslint/no-explicit-any
const close = (actual: number, expected: number, tolerance: number, label: string) =>
  expect(Math.abs(actual - expected), `${label}: ${actual} vs ${expected}`).toBeLessThanOrEqual(tolerance);

// em-widths (width / size) of the words in each rich_plan case, from the fixture's expected widths.
const EM: Record<string, Record<string, number>> = {
  "rich/two-weight-name": { FATHIMA: 72.67 / 18, SHENZA: 65.97 / 18 },
  "rich/highlight-centred": { MENTOR: (39.46 - 5) / 8 },
  "rich/underline-script": { Electronics: 50.7 / 11 },
  "rich/wrap-shrink": { Community: 59.04 / 11.5, hardware: 68.44 / 14.95, hackathon: 4.2, " ": 0.25, night: 112.14 / 14.95 - 4.45 },
};
const KNOWN = ["place", "gradient", "rich_plan", "polygon", "icon", "photo_pick", "mask_radius", "barcode"];
const measurerFor = (id: string): MeasureText => (text, _span, size) =>
  (EM[id][text] ?? [...text].length * 0.5) * size;

describe.skipIf(!present)("studio_plan_cases.json", () => {
  const cases = present ? load<Case>(PLAN).cases : [];
  it("covers place, gradient and rich plans (and, once regenerated, the CARD-STUDIO-2 kinds)", () => {
    const kinds = new Set(cases.map((item) => item.kind));
    for (const kind of ["place", "gradient", "rich_plan"]) expect(kinds.has(kind)).toBe(true);
    for (const kind of kinds) expect(KNOWN).toContain(kind);
  });
  for (const item of cases) {
    it(item.id, () => {
      const { input, expected } = item;
      if (item.kind === "place") {
        const box = imageBox(input.box[0], input.box[1], input.image[0], input.image[1], input.fit, input.zoom, input.focal[0], input.focal[1]);
        close(box.x, expected.left, 0.3, "left"); close(box.y, expected.top, 0.3, "top");
        close(box.w, expected.width, 0.3, "width"); close(box.h, expected.height, 0.3, "height");
      } else if (item.kind === "gradient" && input.spec.type === "linear") {
        const line = gradientLine(input.spec.angle_deg, input.box[0], input.box[1]);
        for (const key of ["x0", "y0", "x1", "y1"] as const) close(line[key], expected[key], 0.3, key);
      } else if (item.kind === "polygon") {
        const points = polygonPoints(input.shape, input.box[0], input.box[1]);
        expect(points).toHaveLength(expected.points.length);
        points.forEach(([x, y], index) => { close(x, expected.points[index][0], 0.01, `x ${index}`); close(y, expected.points[index][1], 0.01, `y ${index}`); });
      } else if (item.kind === "icon") {
        // Same vendored paths; the SVG viewBox (meet, centred) is the server's contain-and-centre fit.
        expect(iconPaths(input.icon)).toEqual(expected.paths);
        const scale = Math.min(input.box[0], input.box[1]) / 24;
        close(scale, expected.scale, 0.0001, "scale");
        close((input.box[0] - 24 * scale) / 2, expected.dx, 0.0001, "dx"); close((input.box[1] - 24 * scale) / 2, expected.dy, 0.0001, "dy");
      } else if (item.kind === "photo_pick") {
        const state = { cutout: input.cutout ? "blob:cutout" : null, useCutout: input.use_cutout, sample: false };
        expect(pickPhoto(input.variant, state)).toBe(expected.pick);
      } else if (item.kind === "barcode") {
        // The server encodes; the browser must draw the same rectangles from that encoding, with the same minimums.
        const rects = barcodeRects(expected.encoding, input.box[0], input.box[1], input.text_mm);
        expect(rects).toHaveLength(expected.rects.length);
        rects.forEach((rect, index) => rect.forEach((value, k) => close(value, expected.rects[index][k], 0.0002, `rect ${index}.${k}`)));
        expect(barcodeMinimum(input.symbology, "number")).toEqual({ w: expected.minimum.number, h: expected.min_height });
        if (expected.minimum.desk !== null) expect(barcodeMinimum(input.symbology, "desk").w).toBe(expected.minimum.desk);
        expect(carriesDesk(input.symbology)).toBe(expected.minimum.desk !== null);
      } else if (item.kind === "mask_radius") {
        close(roundedRadius(input.box[0], input.box[1], input.radius_mm), expected.radius, 0.001, "radius");
      } else if (item.kind === "gradient") {
        const circle = radialCircle(input.spec.cx_pct, input.spec.cy_pct, input.spec.radius_pct, input.box[0], input.box[1]);
        for (const key of ["cx", "cy", "r"] as const) close(circle[key], expected[key], 0.3, key);
      } else {
        const { plan } = planLayer(input.layer as Layer, input.values, measurerFor(item.id));
        expect(plan.lines.map((line) => line.parts.map((part) => part.text).join("")), "line breaks").toEqual(expected.lines.map((line: { text: string }) => line.text));
        close(plan.scale, expected.scale, 0.001, "scale");
        plan.lines.forEach((line, index) => {
          const want = expected.lines[index];
          close(line.baseline, want.baseline, 0.3, `baseline ${index}`); close(line.size, want.size, 0.25, `size ${index}`);
          close(line.x, want.x, 0.5, `x ${index}`); close(line.width, want.width, Math.max(0.5, want.width * 0.02), `width ${index}`);
        });
        expect(plan.bars).toHaveLength(expected.bars.length);
        expected.bars.forEach((bar: Record<string, number>, index: number) => (["x", "y", "w", "h", "radius"] as const).forEach((key) =>
          close(plan.bars[index][key], bar[key], 0.6, `bar ${index}.${key}`)));
        expect(plan.rules).toHaveLength(expected.rules.length);
        expected.rules.forEach((rule: Record<string, number>, index: number) => (["x", "y", "w", "thickness"] as const).forEach((key) =>
          close(plan.rules[index][key], rule[key], 0.6, `rule ${index}.${key}`)));
      }
    });
  }
});

describe.skipIf(!present)("studio_compat_cases.json", () => {
  const cases = present ? load<{ id: string; input: Record<string, any>; expected: Record<string, any> }>(COMPAT).cases : []; // eslint-disable-line @typescript-eslint/no-explicit-any
  for (const item of cases) {
    it(`${item.id}: a v2 document keeps its layers and draws on the plain text path`, () => {
      expect(item.expected.version).toBe(3);
      for (const side of ["front", "back"] as const) {
        expect(item.expected[side].layers.map((layer: Layer) => layer.id)).toEqual(item.input[side].layers.map((layer: Layer) => layer.id));
        expect(item.expected[side].layers.filter((layer: Layer) => isRichText(layer))).toEqual([]);
      }
    });
  }
});

describe.skipIf(present)("studio fixtures not written yet", () => {
  it.skip("waits for studio_plan_cases.json and studio_compat_cases.json from CARD-ENGINE", () => undefined);
});
