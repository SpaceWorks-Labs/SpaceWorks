import type { ThemePreference } from "../../lib/theme";
import { chooseTheme } from "../../lib/theme";
import { transitionTheme } from "../../lib/themeTransition";

// Kept for existing callers. The theme transition is a core interaction, not an opt-in delight,
// so the delight flag no longer turns it off; reduced motion still switches instantly.
export function revealTheme(theme: ThemePreference, element: HTMLElement, _enabled: boolean, reduced: boolean) {
  if (reduced) { chooseTheme(theme); return; }
  transitionTheme(theme, element);
}
