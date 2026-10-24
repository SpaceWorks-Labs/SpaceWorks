import { useSyncExternalStore } from "react";
import { currentTheme, subscribeTheme } from "../lib/theme";
import { useDelight, useReducedMotion } from "./delight/DelightProvider";
import { revealTheme } from "./delight/themeReveal";
import "./delight/delight.css";
import { MoonIcon, SunIcon } from "./icons";
import { IconButton } from "./ui/IconButton";

export function ThemeToggle({ variant = "text" }: { variant?: "text" | "icon" }) {
  const theme = useSyncExternalStore(subscribeTheme, currentTheme);
  const { enabled } = useDelight();
  const reduced = useReducedMotion();
  const toggle = (element: HTMLElement) => revealTheme(theme === "dark" ? "light" : "dark", element, enabled, reduced);

  if (variant === "icon") {
    return (
      <IconButton
        label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        onClick={event => toggle(event.currentTarget)}
      >
        {theme === "dark" ? <SunIcon /> : <MoonIcon />}
      </IconButton>
    );
  }

  return (
    <button
      className="desk-button"
      type="button"
      onClick={event => toggle(event.currentTarget)}
    >
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
