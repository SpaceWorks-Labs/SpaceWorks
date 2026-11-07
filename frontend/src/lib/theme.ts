import { readStorage, writeStorage } from "./safeStorage";

export type Theme = "light" | "dark";
export const THEME_KEY = "makerspace.theme";
let sessionChoice: Theme | undefined;

export function preferredTheme(): Theme {
  if (sessionChoice) return sessionChoice;
  const stored = readStorage(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return "light";
}

function applyTheme(theme = preferredTheme()) {
  document.documentElement.classList.toggle("dark", theme === "dark");
  const chrome = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (chrome) chrome.content = theme === "dark" ? "#142C2A" : "#FFF4E8";
}

// Called before React mounts, including pages without a toggle.
export function initializeTheme() {
  sessionChoice = undefined;
  applyTheme();
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY || event.key === null) {
      sessionChoice = undefined;
      applyTheme();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener("storage", onStorage);
  };
}

export function chooseTheme(theme: Theme) {
  sessionChoice = theme;
  writeStorage(THEME_KEY, theme);
  // Still works when localStorage is unavailable.
  applyTheme(theme);
}

export function subscribeTheme(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

export function currentTheme(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}
