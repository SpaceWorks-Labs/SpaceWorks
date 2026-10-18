import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Keep local test tooling inside RB3-E ownership, including the junction workaround.
export default defineConfig({
  root: fileURLToPath(new URL("../../../../", import.meta.url)),
  resolve: { preserveSymlinks: true },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"],
    include: ["src/features/finance/eventPayouts/**/*.test.{ts,tsx}"] },
});
