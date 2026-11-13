/// <reference types="node" />
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { colourSurfaces, previewBaseVars } from "./colourSurfaces";

describe("surface grouping", () => {
  it("groups by who sees each surface, with staff untouched by space colours", () => {
    const surfaces = colourSurfaces();
    expect(surfaces.map((s) => s.id)).toEqual(["staff", "member", "public", "printed", "screens"]);
    expect(surfaces.find((s) => s.id === "staff")!.uses).toBe("none");
    expect(surfaces.find((s) => s.id === "printed")!.uses).toBe("accent");
    expect(surfaces.find((s) => s.id === "staff")!.roles).toEqual(expect.arrayContaining(["Space Manager", "Inventory Manager", "Machine Manager"]));
    expect(surfaces.every((s) => s.roles.length > 0 && s.note && s.examples)).toBe(true);
  });
});

describe("preview base variables mirror index.css", () => {
  const css = readFileSync("src/index.css", "utf8");
  const block = (selector: string) => css.slice(css.indexOf(selector)).split("}")[0];
  it.each([["light", "color-scheme: light"], ["dark", ":root.dark {"]] as const)("%s tokens", (mode, selector) => {
    const vars = previewBaseVars(mode) as Record<string, string>;
    const source = block(selector);
    for (const name of ["bg", "surface", "panel", "hover", "line", "outline", "ink", "muted", "focus", "accent", "accent-hover", "accent-active", "on-accent", "accent-soft", "accent-ink"]) {
      const match = new RegExp(`--color-${name}:\\s*([\\d ]+);`).exec(source);
      expect(match, `--color-${name} in ${mode}`).not.toBeNull();
      expect(vars[`--color-${name}`], `--color-${name} in ${mode}`).toBe(match![1].trim());
    }
  });
});
