// Frontend unmarked-literal guard (phase 8 i18n): `npm run i18n:check`.
//
// Scans frontend/src (tests and generated files excluded) for user-facing copy that is not
// marked with Lingui (positions: scripts/i18n-literal-positions.mjs). The generated files
// are covered through their GENERATORS: each listed generator renders to a temporary path
// and that output is scanned with the generated-file exclusion off, so a generator template
// cannot emit raw copy into an excluded file. Modules bundled into a worker are skipped
// (scripts/i18n-worker-closure.mjs). Exit status 1 lists `path:line: category`.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { findUnmarked } from "./i18n-literal-positions.mjs";
import { workerClosure } from "./i18n-worker-closure.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const GENERATED_SOURCE_FILES = [
  { script: "scripts/generate-api-client.mjs", env: "API_CLIENT_OUTPUT", name: "api.ts" },
  { script: "scripts/generate-locales.mjs", env: "LOCALES_OUTPUT", name: "locales.ts" },
];

export function isExcluded(relative) {
  const posix = relative.split(path.sep).join("/");
  return /(^|\/)(generated|test|__tests__|locales)\//.test(posix) || /\.(test|spec)\.[tj]sx?$/.test(posix)
    || /\.d\.ts$/.test(posix) || /\.dev\.tsx?$/.test(posix);
}

export function scanFile(file, display = file) {
  const text = fs.readFileSync(file, "utf8");
  const kind = file.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, kind);
  return findUnmarked(sourceFile).map(({ line, category }) => `${display}:${line}: ${category}`);
}

function walk(directory, out = []) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

export function scanGenerators(generators = GENERATED_SOURCE_FILES, root = ROOT) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "i18n-generated-"));
  const findings = [];
  try {
    for (const { script, env, name } of generators) {
      const output = path.join(directory, name);
      execFileSync(process.execPath, [path.join(root, script)], { cwd: root, env: { ...process.env, [env]: output }, stdio: "ignore" });
      findings.push(...scanFile(output, `${script} -> ${name}`));
    }
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
  return findings;
}

export function run() {
  const src = path.join(ROOT, "src");
  const workers = workerClosure(ROOT);
  const findings = walk(src)
    .filter((file) => !isExcluded(path.relative(src, file)) && !workers.has(path.resolve(file)))
    .flatMap((file) => scanFile(file, path.relative(ROOT, file).split(path.sep).join("/")));
  findings.push(...scanGenerators());
  return findings;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const findings = run();
  findings.forEach((line) => console.log(line));
  console.error(`${findings.length} unmarked user-facing literal(s)`);
  process.exit(findings.length ? 1 : 0);
}
