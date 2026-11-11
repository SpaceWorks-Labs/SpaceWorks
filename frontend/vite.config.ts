import { lingui } from "@lingui/vite-plugin";
import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";
import { kioskPwa } from "./scripts/kiosk-pwa";
import { memberPwa } from "./scripts/member-pwa";
import { docsContent } from "./scripts/docs-plugin";
import { apiReference } from "./scripts/api-reference-plugin";
import { existsSync, readFileSync } from "node:fs";

/**
 * The product version, read once at build time from the repository's VERSION file. The Docker build
 * context is frontend/ alone, so there it falls back to the OpenAPI snapshot's info.version, which
 * scripts/bump-version.sh writes from VERSION and scripts/ci/check_version_bump.py holds equal to it.
 */
function productVersion() {
  const file = new URL("../VERSION", import.meta.url);
  if (existsSync(file)) return readFileSync(file, "utf8").trim();
  const schema = JSON.parse(readFileSync(new URL("./openapi-schema.json", import.meta.url), "utf8")) as { info: { version: string } };
  return schema.info.version;
}

export default defineConfig({
  define: { __SPACEWORKS_VERSION__: JSON.stringify(productVersion()) },
  // Lingui compiles imported .po catalogues and transforms its macros natively (phase 8 i18n).
  // "message" keeps each source message beside its id, so English needs no catalogue chunk.
  plugins: [react(), lingui({ macroTransform: { macro: { descriptorFields: "message" } } }), memberPwa(), kioskPwa(), docsContent(), apiReference()],
  server: {
    port: 5000,
    // Inside the dev container the backend is another service on the compose
    // network, not localhost — docker-compose.dev.yml sets this to http://backend:8000.
    proxy: {
      // Shared website HTML belongs to Django, including its exact framing policy.
      ...Object.fromEntries(["/embed/", "/share/", "/sitemap.xml", "/robots.txt"].map(path => [path, {
        target: process.env.VITE_DEV_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: false,
      }])),
      "/api": {
        target: process.env.VITE_DEV_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Two stable vendor chunks so an app deploy does not invalidate the framework bytes
        // every browser already has cached. Page code splits per route in AppRoutes.tsx.
        manualChunks(id: string) {
          if (/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler)\//.test(id)) return "react";
          if (id.includes("node_modules/@tanstack/")) return "tanstack";
          return undefined;
        },
        // /docs code, page bodies, the API reference and Mermaid live under assets/docs/, which the
        // kiosk worker leaves out of its install-time precache (scripts/kiosk-pwa.ts DOCS_ASSET).
        chunkFileNames(chunk) {
          const docs = chunk.moduleIds.some(id => /^\0virtual:spaceworks-(doc|api)|[\\/]src[\\/]features[\\/]docs[\\/]|node_modules[\\/](mermaid|@mermaid-js)[\\/]/.test(id));
          return docs ? "assets/docs/[name]-[hash].js" : "assets/[name]-[hash].js";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // scripts/*.test.mjs are node:test suites (`node --test`), not vitest files.
    // legacy-worktree-imports/ holds skipped tests kept for reference (see the header of each file).
    exclude: [...configDefaults.exclude, "scripts/**/*.test.mjs", "e2e/**", "legacy-worktree-imports/**"],
  },
});
