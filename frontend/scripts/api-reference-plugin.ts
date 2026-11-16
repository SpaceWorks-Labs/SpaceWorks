// Serves the in-app API reference (/docs/api/reference) as small virtual modules derived from
// openapi-schema.json at build, dev and vitest time. The 15 MB schema never reaches the browser:
//   virtual:spaceworks-api-index      every operation (for search) + the tag list
//   virtual:spaceworks-api-tags       the tag list + one lazy loader per tag
//   virtual:spaceworks-api-tag/<slug> one tag's operations, the schemas they reach and their auth schemes
// Each tag module is reached only through a dynamic import, so Rollup emits it as its own chunk.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import { buildApiReference, type ApiReference } from "../src/features/docs/apiReference/apiReferenceModel";

const INDEX = "virtual:spaceworks-api-index";
const TAGS = "virtual:spaceworks-api-tags";
const TAG = "virtual:spaceworks-api-tag/";
const PREFIX = "\0spaceworks-api:";

export function apiReference(options: { schemaPath?: string } = {}): Plugin {
  let schemaPath = "";
  let cached: ApiReference | null = null;
  const reference = () => {
    cached ??= buildApiReference(JSON.parse(readFileSync(schemaPath, "utf8")));
    return cached;
  };
  return {
    name: "spaceworks-api-reference",
    configResolved(config) { schemaPath = resolve(config.root, options.schemaPath ?? "openapi-schema.json"); },
    resolveId(id) {
      if (id === INDEX || id === TAGS || id.startsWith(TAG)) return PREFIX + id;
      return null;
    },
    load(id) {
      if (!id.startsWith(PREFIX)) return null;
      this.addWatchFile(schemaPath);
      const ref = reference();
      const virtualId = id.slice(PREFIX.length);
      if (virtualId === INDEX) {
        return `export default ${JSON.stringify(ref.index)};\nexport const tags = ${JSON.stringify(ref.tags)};\nexport const version = ${JSON.stringify(ref.version)};`;
      }
      if (virtualId === TAGS) {
        const loaders = ref.tags.map(tag => `${JSON.stringify(tag.slug)}: () => import(${JSON.stringify(TAG + tag.slug)})`);
        return `export const tags = ${JSON.stringify(ref.tags)};\nexport const version = ${JSON.stringify(ref.version)};\nexport const loaders = {\n${loaders.join(",\n")}\n};`;
      }
      const payload = ref.payloads[virtualId.slice(TAG.length)];
      if (!payload) this.error(`Unknown API reference tag: ${virtualId}`);
      return `export default ${JSON.stringify(payload)};`;
    },
    watchChange(id) { if (resolve(id) === schemaPath) cached = null; },
    handleHotUpdate({ file, server }) {
      if (resolve(file) !== schemaPath) return;
      cached = null;
      for (const module of [...server.moduleGraph.idToModuleMap.values()]) {
        if (module.id?.startsWith(PREFIX)) server.moduleGraph.invalidateModule(module);
      }
      server.ws.send({ type: "full-reload" });
      return [];
    },
  };
}
