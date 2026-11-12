// Post-build guard: fails on any JS chunk over 500 kB that is not on the allow-list of known lazy heavy chunks.
// vite.config.ts raises build.chunkSizeWarningLimit only so these known chunks do not print a warning on every
// build; this script is what stops a NEW oversized chunk (or the entry chunk) from slipping in unnoticed.
import { readdir, stat } from "node:fs/promises";
import { join, resolve } from "node:path";

const LIMIT = 500 * 1000; // bytes, the unit Vite reports kB in
// Chunk base names (hash stripped) that are lazy and cannot be split further. Each is a third-party engine or viewer.
const ALLOWED = new Set(["elk", "chunk-NGNAAXSQ", "three.module", "EventDrawer", "preview.worker", "_spaceworks-api_virtual_spaceworks-api-index"]);

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(path);
    else yield path;
  }
}

const offenders = [];
for await (const file of walk(resolve("dist/assets"))) {
  if (!file.endsWith(".js")) continue;
  const { size } = await stat(file);
  const base = file.split(/[\\/]/).pop().replace(/-[A-Za-z0-9_]{8}\.js$/, "").replace(/\.js$/, "");
  if (size > LIMIT && ![...ALLOWED].some((name) => base === name || base.startsWith(`${name}-`))) offenders.push(`${base} (${(size / 1000).toFixed(1)} kB)`);
}
if (offenders.length) {
  console.error(`Chunks over 500 kB that are not on the allow-list in scripts/check-chunk-sizes.mjs:\n  ${offenders.join("\n  ")}`);
  process.exit(1);
}
console.log("Chunk sizes verified: only the allow-listed lazy chunks exceed 500 kB.");
