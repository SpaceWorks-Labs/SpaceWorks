import { realpathSync } from "node:fs";
import { resolve } from "node:path";

// Run from frontend/. The supplied node_modules is a junction into another worktree.
export default {
  resolve: { preserveSymlinks: true },
  server: { fs: { allow: [resolve(".."), realpathSync("node_modules")] } },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"],
    include: ["src/features/deployment/*.test.tsx"], pool: "forks", maxWorkers: 1 },
};
