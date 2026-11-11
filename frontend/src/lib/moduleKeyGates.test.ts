import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

// A module gate must name a real module key (backend module registry -> generated ModulesEnum).
// Guards the #205 regression where consoles read the non-module "public_site" from enabled_modules.
const SRC = join(process.cwd(), "src");
const GATE = /(?:modules|enabled_modules|enabledModules|moduleKeys)\b[^;\n]{0,24}?\.(?:includes|has)\(\s*"([a-z_]+)"\s*\)/g;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === "generated" ? [] : sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

it("every literal module gate in the frontend names a registered module key", () => {
  const api = readFileSync(join(SRC, "generated", "api.ts"), "utf8");
  const declared = /export type ModulesEnum = ([^;]+);/.exec(api)?.[1] ?? "";
  const keys = new Set([...declared.matchAll(/"([a-z_]+)"/g)].map((match) => match[1]));
  expect(keys.size).toBeGreaterThanOrEqual(30);
  expect(keys.has("public_site")).toBe(false);
  const unknown: string[] = [];
  let gates = 0;
  for (const file of sources(SRC)) {
    for (const match of readFileSync(file, "utf8").matchAll(GATE)) {
      gates += 1;
      if (!keys.has(match[1])) unknown.push(`${file.slice(SRC.length)}: ${match[1]}`);
    }
  }
  expect(gates).toBeGreaterThan(50);
  expect(unknown).toEqual([]);
});
