// Puts the active Lingui instance in context and refreshes server-rendered text when the
// effective locale changes (phase 8 i18n): active queries reset, inactive ones invalidate,
// so no cached response or error keeps the old language.
import { I18nProvider } from "@lingui/react";
import type { QueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { activeLocale, i18n, onLocaleChange } from "./i18n";

export function I18nRoot({ queryClient, children }: { queryClient: QueryClient; children: ReactNode }) {
  const [locale, setLocale] = useState(activeLocale());
  useEffect(() => onLocaleChange(() => {
    const next = activeLocale();
    setLocale((previous) => {
      if (previous !== next) {
        void queryClient.invalidateQueries({ type: "inactive" });
        void queryClient.resetQueries({ type: "active" });
      }
      return next;
    });
  }), [queryClient]);
  return <I18nProvider i18n={i18n} key={locale}>{children}</I18nProvider>;
}
