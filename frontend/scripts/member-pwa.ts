import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin, ResolvedConfig } from "vite";

export function memberPwa(): Plugin {
  let config: ResolvedConfig;
  return {
    name: "spaceworks-member-icons", apply: "build",
    configResolved(value) { config = value; },
    async generateBundle() {
      for (const size of [192, 512]) this.emitFile({
        type: "asset", fileName: `member-pwa/icon-${size}.png`,
        source: await readFile(resolve(config.root, "public", "brand", `icon-${size}.png`)),
      });
    },
    async closeBundle() {
      const output = resolve(config.root, config.build.outDir);
      const worker = await readFile(resolve(output, "member-sw.js"), "utf8");
      const revision = createHash("sha256").update(worker);
      for (const file of ["offline.html", "offline.js", "offline.css", "icon-192.png", "icon-512.png"]) {
        revision.update(await readFile(resolve(output, "member-pwa", file)));
      }
      await writeFile(resolve(output, "member-sw.js"), worker.replace("__MEMBER_REVISION__", revision.digest("hex")));
    },
  };
}
