import { describe, expect, it } from "vitest";

import type { Layer } from "./cardTypes";
import { newLayer } from "./designDocument";
import { applyToRange, mergeSpans, planLayer, retypeSpans, spansText, type MeasureText } from "./studioText";

// Deterministic metrics: every character is 0.5 em wide.
const measure: MeasureText = (text, _span, size) => [...text].length * 0.5 * size;
const side = { page_width_mm: 54, page_height_mm: 86, background: { kind: "colour", colour: "#FFFFFF" } as const, layers: [] };
const text = (extra: Partial<Layer>) => newLayer("text", side, "cr80-portrait", { w_mm: 40, h_mm: 20, ...extra });
const PT = 1 / 0.3528;

describe("span editing", () => {
  it("styles only the selected word and keeps the text", () => {
    const spans = applyToRange([{ text: "SHENZA Ahmed" }], 0, 6, { font_weight: 800 });
    expect(spans.map((span) => span.text)).toEqual(["SHENZA", " Ahmed"]);
    expect(spans[0].font_weight).toBe(800);
    expect(spansText(spans)).toBe("SHENZA Ahmed");
  });
  it("splits a span in three when the middle is styled, and merges equal neighbours back", () => {
    const three = applyToRange([{ text: "abcdef" }], 2, 4, { colour: "#FF0000" });
    expect(three.map((span) => span.text)).toEqual(["ab", "cd", "ef"]);
    expect(mergeSpans(applyToRange(three, 2, 4, { colour: undefined })).length).toBe(1);
  });
  it("keeps styling aligned when text is typed in the middle", () => {
    const styled = applyToRange([{ text: "Hello World" }], 6, 11, { font_weight: 800 });
    const next = retypeSpans(styled, "Hello big World");
    expect(spansText(next)).toBe("Hello big World");
    expect(next[next.length - 1].font_weight).toBe(800);
    expect(next[0].font_weight).toBeUndefined();
  });
});

describe("rich plan (points, layer-local, like the server)", () => {
  it("wraps greedily; the first baseline is 0.9 x the size and leading is size x line height", () => {
    const { plan } = planLayer(text({ text: "aaa bbb ccc", font_size_pt: 10, shrink_to_fit: false, w_mm: 13 }), {}, measure);
    expect(plan.lines.map((line) => line.parts.map((part) => part.text).join(""))).toEqual(["aaa bbb", "ccc"]);
    expect(plan.lines[0].baseline).toBeCloseTo(9);
    expect(plan.lines[1].baseline - plan.lines[0].baseline).toBeCloseTo(12);
  });
  it("sizes a line by its biggest span and places parts one after another", () => {
    const layer = text({ spans: [{ text: "SHEN", font_weight: 300 }, { text: "ZA", font_weight: 800, size_scale: 2 }], text: "SHENZA", font_size_pt: 10 });
    const { plan } = planLayer(layer, {}, measure);
    expect(plan.lines).toHaveLength(1);
    expect(plan.lines[0].size).toBe(20);
    expect(plan.lines[0].parts[1].x).toBeCloseTo(plan.lines[0].parts[0].width);
  });
  it("draws one highlight bar and one underline per line, as wide as the text plus padding", () => {
    const layer = text({ text: "aaa bbb", font_size_pt: 10, shrink_to_fit: false, w_mm: 8,
      highlight: { colour: "#DFFF8F", pad_x_mm: 1, pad_y_mm: 0.5, radius_mm: 0.5 }, underline: { colour: "#000000", thickness_pt: 1, offset_pt: 2 } });
    const { plan } = planLayer(layer, {}, measure);
    expect(plan.bars).toHaveLength(2);
    expect(plan.bars[0].w).toBeCloseTo(plan.lines[0].width + 2 * PT);
    expect(plan.rules[0].y).toBeCloseTo(plan.lines[0].baseline + 2);
  });
  it("centres each line and moves its bar with it", () => {
    const layer = text({ text: "ab", align: "center", w_mm: 30, highlight: { colour: "#000000", pad_x_mm: 0, pad_y_mm: 0, radius_mm: 0 } });
    const { plan } = planLayer(layer, {}, measure);
    expect(plan.lines[0].x).toBeCloseTo((30 * PT - plan.lines[0].width) / 2);
    expect(plan.bars[0].x).toBeCloseTo(plan.lines[0].x);
  });
  it("shrinks every span uniformly, never below 60 percent, and keeps size ratios", () => {
    const layer = text({ spans: [{ text: "Big", size_scale: 2 }, { text: " small" }], text: "Big small", font_size_pt: 20, w_mm: 12, h_mm: 8 });
    const { plan } = planLayer(layer, {}, measure);
    expect(plan.scale).toBeLessThan(1);
    expect(plan.scale).toBeGreaterThanOrEqual(0.6 - 1e-6);
  });
  it("merges tags (including the split name) and applies uppercase per span", () => {
    const layer = text({ spans: [{ text: "{{first_name}}", uppercase: true }, { text: " {{last_name}}" }], text: "x" });
    const { spans } = planLayer(layer, { name: "Fathima Shenza" }, measure);
    expect(spans.map((span) => span.text)).toEqual(["FATHIMA", " Shenza"]);
  });
  it("uses a translation when the locale has one", () => {
    const layer = text({ text: "Hello", translations: { ml: "നമസ്കാരം" } });
    expect(planLayer(layer, {}, measure, "ml").spans[0].text).toBe("നമസ്കാരം");
    expect(planLayer(layer, {}, measure, "fr").spans[0].text).toBe("Hello");
  });
});
