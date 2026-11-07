// Lingui catalogue configuration (phase 8 i18n). English is the source locale and today the
// only catalogue; the locale list comes from the generated registry (scripts/generate-locales.mjs).
import { defineConfig } from "@lingui/conf";
import { formatter } from "@lingui/format-po";
import { SUPPORTED_LOCALES } from "./src/generated/locales";

export default defineConfig({
  sourceLocale: "en",
  locales: SUPPORTED_LOCALES.map((locale) => locale.code),
  catalogs: [
    {
      path: "<rootDir>/src/locales/{locale}/messages",
      include: ["<rootDir>/src"],
      exclude: ["**/*.test.*", "**/src/test/**", "**/src/generated/**", "**/node_modules/**"],
    },
  ],
  // No origins: the catalogue changes only when wording does, so the drift diff stays quiet.
  format: formatter({ origins: false, lineNumbers: false }),
});
