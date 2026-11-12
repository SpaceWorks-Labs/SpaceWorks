import { useEffect, useSyncExternalStore } from "react";
import type { TenantBootstrap } from "./api";
import { readBrandTokens, tenantColourStyle } from "./branding";
import { claimTenantDefaultTheme, currentTheme, subscribeTheme, type ThemePreference } from "./theme";

// Scope custom colours to this public/member page, including central /m/:slug
// navigation. Putting these on :root would also recolour the staff console.
/** The space's default look for a bootstrap or theme blob, for displays that decide their own theme from it. */
export function tenantDefaultMode(theme: unknown): ThemePreference | undefined {
  const mode = theme && typeof theme === "object" ? (theme as { mode?: unknown }).mode : undefined;
  return mode === "light" || mode === "dark" || mode === "system" ? mode : undefined;
}

/** Make the space's default look (Light / Solid black / System) the starting theme while this page is mounted. A visitor's own toggle still wins. */
export function useTenantDefaultTheme(theme: unknown, enabled = true) {
  const mode = enabled ? tenantDefaultMode(theme) : undefined;
  useEffect(() => claimTenantDefaultTheme(mode), [mode]);
}

export function useTenantBranding(bootstrap: TenantBootstrap | null | undefined) {
  useTenantDefaultTheme(bootstrap?.theme);
  const mode = useSyncExternalStore(subscribeTheme, currentTheme);
  const tokens = readBrandTokens();
  return bootstrap && tokens ? tenantColourStyle(bootstrap.theme, tokens, mode) : {};
}
