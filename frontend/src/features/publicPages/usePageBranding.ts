import { useSyncExternalStore } from "react";
import { brandPaletteStyle, deriveBrandPalette } from "../../lib/brandColours";
import { currentTheme, subscribeTheme } from "../../lib/theme";
import { useTenantDefaultTheme } from "../../lib/useTenantBranding";
import { paletteSeeds } from "./PagePresentationForm";
import type { AccentChoice } from "./pageTypes";
import type { ResolvedTheme, ThemeConfig } from "../../generated/api";

/** Only brand tokens change. Focus, status and console tokens keep their Space Works values. */
export function usePageBranding(theme?: ResolvedTheme | ThemeConfig, choice?: AccentChoice | null) {
  const config = theme && "theme_config" in theme ? theme.theme_config : theme;
  useTenantDefaultTheme(config);
  const mode = useSyncExternalStore(subscribeTheme, currentTheme);
  const seed = choice && choice !== "inherit" ? paletteSeeds[choice] : undefined;
  if (!theme && !seed) return {};
  return brandPaletteStyle(deriveBrandPalette(seed ? { ...config, primary_color: seed, accent_color: seed } : config ?? {}, mode));
}
