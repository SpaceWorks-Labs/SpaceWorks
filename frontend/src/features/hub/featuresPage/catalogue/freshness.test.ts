import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const frontend = resolve(__dirname, "../../../../..");
const script = resolve(frontend, "scripts/features-catalogue/generate.mjs");

// Re-derives registryData.ts, registryTitles.ts and limitData.ts from the backend sources (the same code as
// `npm run features:catalogue`) and fails when a committed file differs, or when report_coverage.py gained a statement
// the replay in coverage.mjs does not know. The cure is `npm run features:catalogue` (or teaching coverage.mjs).
describe.skipIf(!existsSync(resolve(frontend, "../backend/apps/operations/report_coverage.py")))("generated catalogue data is fresh", () => {
  it("matches what the backend registries say now, including every loop in report_coverage.py", () => {
    let output = "";
    try {
      execFileSync(process.execPath, [script, "--check"], { encoding: "utf8", stdio: "pipe" });
    } catch (error) {
      output = String((error as { stderr?: string }).stderr ?? error);
    }
    expect(output).toBe("");
  });
});
