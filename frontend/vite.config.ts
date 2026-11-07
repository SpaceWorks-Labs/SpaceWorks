import { lingui } from "@lingui/vite-plugin";
import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";
import { kioskPwa } from "./scripts/kiosk-pwa";
import { memberPwa } from "./scripts/member-pwa";

export default defineConfig({
  // Lingui compiles imported .po catalogues and transforms its macros natively (phase 8 i18n).
  // "message" keeps each source message beside its id, so English needs no catalogue chunk.
  plugins: [react(), lingui({ macroTransform: { macro: { descriptorFields: "message" } } }), memberPwa(), kioskPwa()],
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
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // scripts/*.test.mjs are node:test suites (`node --test`), not vitest files.
    exclude: [...configDefaults.exclude, "scripts/**/*.test.mjs"],
  },
});
