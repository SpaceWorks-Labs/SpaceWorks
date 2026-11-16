import { defineConfig } from 'vitest/config'

// Local-only harness: the requested root junction config is absent in this worktree.
export default defineConfig({
  root: process.cwd(),
  server: { fs: { strict: false } },
  resolve: { dedupe: ['react', 'react-dom'] },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'] },
})
