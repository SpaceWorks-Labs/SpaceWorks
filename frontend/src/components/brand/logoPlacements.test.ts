import { readdirSync, readFileSync } from "node:fs";
import { join, resolve, sep } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(__dirname, "../..");
const walk = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
  const full = join(dir, entry.name);
  return entry.isDirectory() ? walk(full) : /\.(tsx|ts)$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [full] : [];
});
const rel = (file: string) => file.slice(SRC.length + 1).split(sep).join("/");

describe("Space Works mark placements", () => {
  it("every logo is drawn through AnimatedLogoMark (hover/focus opening), never SpaceWorksLogo directly", () => {
    const allowed = new Set(["components/SpaceWorksLogo.tsx", "components/brand/AnimatedLogoMark.tsx"]);
    const offenders = walk(SRC).filter(file => !allowed.has(rel(file)))
      .filter(file => /<SpaceWorksLogo\b/.test(readFileSync(file, "utf8"))).map(rel);
    expect(offenders).toEqual([]);
  }, 30_000);
  it("only the brand artwork modules read the logo masters", () => {
    const allowed = new Set(["components/SpaceWorksLogo.tsx", "components/spaceWorksLogoPaths.ts", "components/BrandFacets.tsx", "components/boxOpen/markup.ts"]);
    const offenders = walk(SRC).filter(file => !allowed.has(rel(file)))
      .filter(file => /logoMasters/.test(readFileSync(file, "utf8"))).map(rel);
    expect(offenders).toEqual([]);
  }, 30_000);
});
