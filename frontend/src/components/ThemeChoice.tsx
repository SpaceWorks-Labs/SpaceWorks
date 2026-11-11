import { t } from "@lingui/core/macro";
import { useSyncExternalStore } from "react";
import { subscribeThemePreference, themePreference, type ThemePreference } from "../lib/theme";
import { useReducedMotion } from "./delight/DelightProvider";
import { revealTheme } from "./delight/themeReveal";
import { SegmentedControl } from "./ui";

/**
 * Light, Dark or System (parity A3). System follows the device's `prefers-color-scheme`
 * and keeps following it while the page is open; the header toggle still flips between
 * light and dark, which turns a System choice back into a fixed one.
 */
export function ThemeChoice() {
  const preference = useSyncExternalStore(subscribeThemePreference, themePreference, () => "light" as const);
  const reduced = useReducedMotion();
  const options = [
    { value: "light", label: t`Light` },
    { value: "dark", label: t`Dark` },
    { value: "system", label: t`System` },
  ];
  return <div className="grid gap-2">
    <SegmentedControl label={t`Appearance`} value={preference} options={options}
      onChange={value => revealTheme(value as ThemePreference, document.activeElement instanceof HTMLElement ? document.activeElement : document.body, true, reduced)} />
    <p className="text-sm text-muted">{preference === "system"
      ? t`Matches your device's light or dark setting, and changes when it does.`
      : t`Saved on this device and browser.`}</p>
  </div>;
}
