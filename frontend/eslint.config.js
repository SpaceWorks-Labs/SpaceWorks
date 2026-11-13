// Frontend lint (#108, P41): the CI `frontend` job runs `npm run lint` beside `tsc -b`.
// TypeScript already enforces types and unused names (tsconfig `strict`, `noUnused*`), so this
// config adds what the compiler cannot see: the recommended JavaScript and typescript-eslint
// rules, and React's rules of hooks. Each rule changed from its preset says why.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  // Generated code, build output and third-party bundles are not ours to lint. The test suites are
  // local and gitignored (#108), so lint covers the published tree only and a local run with them
  // present gives the same answer as CI.
  { ignores: ["dist/**", "dev-dist/**", "node_modules/**", "src/generated/**", "public/**", "coverage/**",
    "playwright-report/**", "test-results/**", ".npm-cache/**", ".pwa-browser/**",
    "e2e/**", "src/test/**", "src/**/*.test.{ts,tsx}", "*.vitest.config.mjs", "scripts/**/*.test.mjs"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      // The codebase marks a deliberate discard with a leading underscore, most often to drop
      // keys from an object with a rest spread (`const { id: _id, ...rest } = row`).
      "@typescript-eslint/no-unused-vars": ["error", {
        argsIgnorePattern: "^_", varsIgnorePattern: "^_", destructuredArrayIgnorePattern: "^_",
        caughtErrorsIgnorePattern: "^_", ignoreRestSiblings: true,
      }],
      // Sanitisers strip or refuse control characters on purpose (`/[\x00-\x1f]/`), which is
      // exactly what this rule forbids.
      "no-control-regex": "off",
      // tsconfig `lib` is ES2020, which does not type `new Error(message, { cause })`.
      "preserve-caught-error": "off",
    },
  },
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      // The classic hook rules only. The plugin's newer React Compiler rules (purity, refs,
      // set-state-in-effect, ...) assume code written for the compiler, which this app does not use.
      "react-hooks/rules-of-hooks": "error",
      // A missing dependency is reviewed case by case (many effects intentionally run once), so it
      // warns rather than fails the build.
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    files: ["*.{js,mjs,cjs,ts}", "scripts/**/*.{js,mjs,cjs}", "docker/**/*.{js,mjs}"],
    languageOptions: { globals: globals.node },
  },
  {
    // Playwright `page.evaluate` callbacks run in the browser, not in Node.
    files: ["scripts/verify-pwa-browser.mjs"],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
);
