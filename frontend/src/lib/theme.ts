import { readStorage, writeStorage } from "./safeStorage";

/** The theme actually painted. */
export type Theme = "light" | "dark";
/** What the person chose: a fixed theme, or "system" to follow the device (parity A3). */
export type ThemePreference = Theme | "system";
export const THEME_KEY = "makerspace.theme";
const PREFERENCES: readonly ThemePreference[] = ["light", "dark", "system"];
const DARK_QUERY = "(prefers-color-scheme: dark)";
let sessionChoice: ThemePreference | undefined;

/** The stored choice. Light stays the default: nothing follows the device until someone picks "system". */
export function themePreference(): ThemePreference {
  if (sessionChoice) return sessionChoice;
  const stored = readStorage(THEME_KEY);
  return PREFERENCES.includes(stored as ThemePreference) ? stored as ThemePreference : "light";
}

function systemTheme(): Theme {
  try { return window.matchMedia?.(DARK_QUERY)?.matches ? "dark" : "light"; } catch { return "light"; }
}

export function preferredTheme(): Theme {
  const preference = themePreference();
  return preference === "system" ? systemTheme() : preference;
}

function applyTheme(theme = preferredTheme()) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  const chrome = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (chrome) chrome.content = theme === "dark" ? "#000000" : "#FFF4E8";
}

const preferenceListeners = new Set<() => void>();
const announce = () => preferenceListeners.forEach(listener => listener());

// Called before React mounts, including pages without a toggle.
export function initializeTheme() {
  sessionChoice = undefined;
  applyTheme();
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY || event.key === null) {
      sessionChoice = undefined;
      applyTheme();
      announce();
    }
  };
  // Only a "system" choice follows the device; a fixed choice ignores OS changes.
  const onSystemChange = () => { if (themePreference() === "system") applyTheme(); };
  let media: MediaQueryList | undefined;
  try { media = window.matchMedia?.(DARK_QUERY); } catch { media = undefined; }
  window.addEventListener("storage", onStorage);
  media?.addEventListener?.("change", onSystemChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    media?.removeEventListener?.("change", onSystemChange);
  };
}

export function chooseTheme(preference: ThemePreference) {
  sessionChoice = preference;
  writeStorage(THEME_KEY, preference);
  // Still works when localStorage is unavailable.
  applyTheme(preference === "system" ? systemTheme() : preference);
  announce();
}

/** The theme a choice would paint right now; lets a transition animate towards it. */
export function resolveTheme(preference: ThemePreference): Theme {
  return preference === "system" ? systemTheme() : preference;
}

export function subscribeTheme(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

/** For `useSyncExternalStore` readers of the choice itself (the Light / Dark / System picker). */
export function subscribeThemePreference(onChange: () => void) {
  preferenceListeners.add(onChange);
  return () => { preferenceListeners.delete(onChange); };
}

export function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}
