import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name) && !/\.stories\./.test(name)) out.push(path);
  }
  return out;
}

it("no raw type=\"search\" input exists outside SearchField", () => {
  const offenders = walk(join(process.cwd(), "src"))
    .filter(path => !path.endsWith("SearchField.tsx"))
    .filter(path => /type=["']search["']/.test(readFileSync(path, "utf8")));
  expect(offenders).toEqual([]);
}, 30_000);
