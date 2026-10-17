import { useSyncExternalStore } from "react";
import { brandPaletteStyle, deriveBrandPalette } from "../../lib/brandColours";
import { currentTheme, subscribeTheme } from "../../lib/theme";
import { paletteSeeds } from "./PagePresentationForm";
import type { AccentChoice } from "./pageTypes";

/** Only brand tokens change. Focus, status and console tokens keep their Space Works values. */
export function usePageBranding(theme?: Record<string, string>, choice?: AccentChoice | null) {
  const mode = useSyncExternalStore(subscribeTheme, currentTheme);
  const seed = choice && choice !== "inherit" ? paletteSeeds[choice] : undefined;
  if (!theme && !seed) return {};
  return brandPaletteStyle(deriveBrandPalette(seed ? { ...theme, primary_color: seed, accent_color: seed } : theme ?? {}, mode));
}
