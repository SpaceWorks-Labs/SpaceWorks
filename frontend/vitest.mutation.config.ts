// Vitest config used only by Stryker (stryker.config.json): the base config, narrowed to the test files that import
// the mutated gate/permission modules, so a mutant is judged by the tests that can see it (decision 457).
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { defineConfig, mergeConfig } from "vitest/config";
import base from "./vite.config";

// MUT_REGEX narrows the test selection to one target (npx stryker run --mutate <file>); the default covers all of them.
const MUTATED = new RegExp(process.env.MUT_REGEX ?? "featureGates|lib/features|/features\"|staffAccess|consoleAccess|staffBottomNav|paymentAccess");

// MUT_PATHS (optional) additionally restricts the selection by test file path, which keeps static mutants affordable.
const NAMED = new RegExp(process.env.MUT_PATHS ?? ".");

function testFiles(dir: string, out: string[] = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) testFiles(path, out);
    else if (/\.test\.tsx?$/.test(entry.name) && NAMED.test(path) && MUTATED.test(readFileSync(path, "utf8"))) out.push(path.split("\\").join("/"));
  }
  return out;
}

export default mergeConfig(base, defineConfig({ server: { fs: { strict: false } }, test: { include: testFiles("src"), exclude: ["src/features/hub/FeaturesPage.test.tsx"] } }));
