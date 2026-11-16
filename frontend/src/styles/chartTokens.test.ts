/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { contrast, type RGB } from "../lib/brandColours";

// Decision 380: one bright series palette in both themes; contrast is carried by --chart-edge, not by dulling fills.
const css = readFileSync("src/index.css", "utf8");
const chrome = readFileSync("src/styles/chrome.css", "utf8");
const body = (source: string, selector: string) => {
  const bodies = source.split(`${selector} {`).slice(1).map((part) => part.split("}")[0]);
  const found = bodies.find((text) => text.includes("--chart-") || text.includes("--color-"));
  if (!found) throw new Error(`${selector} missing`);
  return found;
};
const triplet = (source: string, name: string): RGB => {
  const match = source.match(new RegExp(`--${name}: ([0-9 ]+);`));
  if (!match) throw new Error(`--${name} missing`);
  return match[1].trim().split(" ").map(Number) as RGB;
};
const light = body(css, ":root"), dark = body(css, ":root.dark");
const chartLight = body(chrome, ":root"), chartDark = body(chrome, ":root.dark");
const SERIES = [1, 2, 3, 4, 5].map((n) => `chart-${n}`);
const themes = { light: { colours: light, chart: chartLight }, dark: { colours: dark, chart: chartDark } };
// A theme's chart tokens: dark inherits whatever it does not override, which is exactly what the cascade does.
const chartToken = (theme: keyof typeof themes, name: string) => {
  const { chart } = themes[theme];
  return triplet(chart.includes(`--${name}:`) ? chart : chartLight, name);
};

describe("chart tokens (decision 380)", () => {
  it("uses the five bright brand colours in brand order, the same in light and dark", () => {
    const expected: RGB[] = [[0, 110, 99], [255, 116, 71], [223, 255, 143], [181, 205, 255], [255, 212, 71]];
    SERIES.forEach((name, index) => {
      expect(chartToken("light", name)).toEqual(expected[index]);
      expect(chartToken("dark", name)).toEqual(chartToken("light", name));
    });
    expect(chartDark).not.toMatch(/--chart-[1-5]:/);
  });

  it("keeps danger out of the series palette", () => {
    expect(chartLight).toMatch(/--chart-danger: var\(--color-danger\)/);
    expect(SERIES).not.toContain("chart-danger");
  });

  it("gives every mark boundary at least 3:1 on every chart background in both themes", () => {
    const table: string[] = [];
    for (const theme of ["light", "dark"] as const) {
      const edge = chartToken(theme, "chart-edge");
      for (const ground of ["bg", "surface", "panel"]) {
        const background = triplet(themes[theme].colours, `color-${ground}`);
        expect(contrast(edge, background), `${theme} edge on ${ground}`).toBeGreaterThanOrEqual(3);
        for (const name of SERIES) table.push(`${theme} ${name} on ${ground}: fill ${contrast(chartToken(theme, name), background).toFixed(2)}, edge ${contrast(edge, background).toFixed(2)}`);
      }
    }
    expect(table).toHaveLength(30);
  });

  it("explains why the edge is needed: bright fills alone miss 3:1 somewhere", () => {
    const bare = SERIES.filter((name) => (["light", "dark"] as const).some((theme) => ["bg", "surface", "panel"].some((ground) => contrast(chartToken(theme, name), triplet(themes[theme].colours, `color-${ground}`)) < 3)));
    expect(bare.length).toBeGreaterThan(0);
  });
});

describe("charts read colours only from the chart tokens", () => {
  const files = (dir: string): string[] => readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory() ? files(path) : /\.tsx?$/.test(entry) && !/\.test\./.test(entry) ? [path] : [];
  });
  const sources = [...files("src/features/staff/panels/charts"), "src/features/staff/panels/OperationsReportCharts.tsx"];

  it("never names a brand colour, hex or legacy chart alias in a chart component", () => {
    for (const path of sources) {
      const text = readFileSync(path, "utf8");
      expect([path, /#[0-9a-fA-F]{3,8}\b/.test(text)]).toEqual([path, false]);
      expect([path, /--chart-(accent|info|success|warn)\b/.test(text)]).toEqual([path, false]);
      expect([path, /--color-(accent|info|success|warn|emphasis)/.test(text)]).toEqual([path, false]);
    }
  });
});
