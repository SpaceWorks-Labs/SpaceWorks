import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initializeTheme, THEME_KEY, themePreference } from "../lib/theme";
import { ThemeChoice } from "./ThemeChoice";
import { ThemeToggle } from "./ThemeToggle";

// Parity A3: Light / Dark / System, where System follows `prefers-color-scheme` live.
describe("system theme", () => {
  let dispose: (() => void) | undefined;
  let darkOS: boolean;
  let media: EventTarget;
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
    darkOS = true;
    media = new EventTarget();
    vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
      get matches() { return query.includes("prefers-color-scheme: dark") ? darkOS : true; },
      addEventListener: media.addEventListener.bind(media),
      removeEventListener: media.removeEventListener.bind(media),
    })));
  });
  afterEach(() => { dispose?.(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("follows prefers-color-scheme while System is chosen", () => {
    localStorage.setItem(THEME_KEY, "system");
    dispose = initializeTheme();
    expect(document.documentElement).toHaveClass("dark");
    darkOS = false;
    act(() => { media.dispatchEvent(new Event("change")); });
    expect(document.documentElement).not.toHaveClass("dark");
    darkOS = true;
    act(() => { media.dispatchEvent(new Event("change")); });
    expect(document.documentElement).toHaveClass("dark");
  });

  it("stays light by default on a dark device until System is picked", () => {
    dispose = initializeTheme();
    render(<ThemeChoice />);
    expect(document.documentElement).not.toHaveClass("dark");
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "System" }));
    expect(localStorage.getItem(THEME_KEY)).toBe("system");
    expect(themePreference()).toBe("system");
    expect(document.documentElement).toHaveClass("dark");
    expect(screen.getByRole("radio", { name: "System" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText(/Matches your device/)).toBeVisible();
  });

  it("the header toggle turns a System choice back into a fixed one", () => {
    localStorage.setItem(THEME_KEY, "system");
    dispose = initializeTheme();
    render(<><ThemeChoice /><ThemeToggle variant="icon" /></>);
    fireEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    expect(screen.getByRole("radio", { name: "Light" })).toHaveAttribute("aria-checked", "true");
    darkOS = true;
    act(() => { media.dispatchEvent(new Event("change")); });
    expect(document.documentElement).not.toHaveClass("dark");
  });

  it("accepts a System choice made in another tab", () => {
    dispose = initializeTheme();
    darkOS = false;
    localStorage.setItem(THEME_KEY, "system");
    act(() => { window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY, newValue: "system" })); });
    expect(themePreference()).toBe("system");
    expect(document.documentElement).not.toHaveClass("dark");
  });
});
