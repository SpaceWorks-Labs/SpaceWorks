// Compile parity: the TypeScript twin must produce exactly the server's settings and its layers within
// 0.01 mm, for every case in the E-B1 golden fixtures (written by the backend; read-only here).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { compileBadge } from "./badgeCompile";
import { isDefaultLayout, layoutFlags, normalizeSettings } from "./badgeNormalize";
import { layoutForPaper } from "./badgeGeometry";

const FIXTURES = resolve(__dirname, "../../../../../backend/apps/card_designs/fixtures");
const load = (name: string) => JSON.parse(readFileSync(resolve(FIXTURES, name), "utf-8"));
const compileCases = load("badge_compile_cases.json") as { event_title: string; organisation_name: string;
  cases: { id: string; input: unknown; settings: Record<string, unknown>; compiled: Record<string, unknown> & { layers: Record<string, unknown>[] } }[] };
const normalizeCases = load("badge_normalize_cases.json") as { id: string; input: unknown; settings: Record<string, unknown> }[];
const { event_title: title, organisation_name: organisation } = compileCases;

function expectClose(actual: unknown, expected: unknown, path: string) {
  if (typeof expected === "number") {
    expect(typeof actual, path).toBe("number");
    expect(Math.abs((actual as number) - expected), `${path}: ${actual} vs ${expected}`).toBeLessThanOrEqual(0.0100001);
    return;
  }
  if (expected && typeof expected === "object") {
    expect(Object.keys(actual as object).sort(), path).toEqual(Object.keys(expected).sort());
    for (const [key, value] of Object.entries(expected)) expectClose((actual as Record<string, unknown>)[key], value, `${path}.${key}`);
    return;
  }
  expect(actual, path).toEqual(expected);
}

describe("badge_normalize_cases.json", () => {
  it.each(normalizeCases.map((item) => [item.id, item] as const))("%s normalises exactly like the server", (_id, item) => {
    expect(normalizeSettings(item.input, title, organisation)).toEqual(item.settings);
  });
});

describe("badge_compile_cases.json", () => {
  it(`covers every case (${compileCases.cases.length})`, () => expect(compileCases.cases.length).toBeGreaterThan(90));

  it.each(compileCases.cases.map((item) => [item.id, item] as const))("%s", (_id, item) => {
    const settings = normalizeSettings(item.input, title, organisation);
    expect(settings).toEqual(item.settings);
    const { layers, palette: _palette, ...page } = compileBadge(settings);
    const { layers: expectedLayers, ...expectedPage } = item.compiled;
    expectClose(page, expectedPage, "page");
    expect(layers.map((layer) => layer.name)).toEqual(expectedLayers.map((layer) => layer.name));
    layers.forEach((layer, index) => {
      const { id: _id2, element: _element, ...mine } = layer;
      const { id: _serverId, ...theirs } = expectedLayers[index];
      expectClose(mine, theirs, `layer ${index} (${layer.name})`);
    });
  });
});

describe("stock turn and reflow", () => {
  it("turning the paper reflows an untouched layout to the new size", () => {
    const portrait = normalizeSettings({ widthMm: 105, heightMm: 148, colorMode: "colour" }, title, organisation);
    expect(isDefaultLayout(portrait)).toBe(true);
    const turned = { ...portrait, widthMm: 148, heightMm: 105, ...layoutForPaper(portrait.template, 148, 105, layoutFlags(portrait)) };
    expect(isDefaultLayout(turned)).toBe(true);
    expect(turned.elementSizes.name).not.toBe(portrait.elementSizes.name);
  });

  it("a hand-moved item marks the layout as adjusted, so toggles keep positions", () => {
    const settings = normalizeSettings({ colorMode: "colour" }, title, organisation);
    const moved = { ...settings, elementPositions: { ...settings.elementPositions, name: { xMm: 20, yMm: 50 } } };
    expect(isDefaultLayout(moved)).toBe(false);
  });
});
