// Modules bundled into a worker (phase 8 i18n). The service worker and the preview workers
// are built without the Lingui plugin and never activate a catalogue, so a Lingui macro in
// any module they import would break the worker bundle. The literal guard skips this
// closure; its few strings are technical worker errors, not rendered copy.
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

export const WORKER_ENTRIES = [
  "src/sw.ts",
  "src/features/events/hackathonSubmissions/preview.worker.ts",
  "src/features/staff/panels/machine/filePreview/jobPreview.worker.ts",
];

function resolveImport(from, specifier) {
  if (!specifier.startsWith(".")) return null;
  const base = path.resolve(path.dirname(from), specifier);
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, path.join(base, "index.ts"), path.join(base, "index.tsx")]) {
    if (/\.tsx?$/.test(candidate) && fs.existsSync(candidate)) return candidate;
  }
  return null;
}

/** Absolute paths of every module reachable from the worker entries. */
export function workerClosure(root) {
  const seen = new Set();
  const queue = WORKER_ENTRIES.map((entry) => path.resolve(root, entry)).filter((file) => fs.existsSync(file));
  while (queue.length) {
    const file = queue.pop();
    if (seen.has(file)) continue;
    seen.add(file);
    const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
    source.forEachChild((node) => {
      if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
        const target = resolveImport(file, node.moduleSpecifier.text);
        if (target && !(ts.isImportDeclaration(node) && node.importClause?.isTypeOnly)) queue.push(target);
      }
    });
  }
  return seen;
}
