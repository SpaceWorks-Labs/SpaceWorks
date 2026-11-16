// Copies the repository's docs/ Markdown into frontend/docs-snapshot/ (git-ignored) so a Docker build
// whose context is ./frontend can still publish /docs. Run from anywhere: `node frontend/scripts/docs-snapshot.mjs`.
// The docs plugin (scripts/docs-plugin.ts) prefers ../docs when it exists, so local builds never read this copy.
import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(frontend, "../docs");
const target = resolve(frontend, "docs-snapshot");
if (!existsSync(source)) {
  console.error(`docs-snapshot: ${source} not found`);
  process.exit(1);
}
rmSync(target, { recursive: true, force: true });
cpSync(source, target, { recursive: true, filter: path => !/\.(pdf|png|jpe?g|svg|json)$/i.test(path) });
console.log(`docs-snapshot: copied ${source} -> ${target}`);
