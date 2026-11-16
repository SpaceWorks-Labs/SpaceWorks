import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { initializeTheme, THEME_KEY } from "../lib/theme";
import { ThemeToggle } from "./ThemeToggle";

describe("theme preference", () => {
  let dispose: (() => void) | undefined;
  let darkOS: boolean;
  let media: EventTarget;
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
    document.head.querySelector('meta[name="theme-color"]')?.remove();
    const chrome = document.createElement("meta");
    chrome.name = "theme-color";
    document.head.append(chrome);
    darkOS = true;
    media = new EventTarget();
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      get matches() { return darkOS; },
      addEventListener: media.addEventListener.bind(media),
      removeEventListener: media.removeEventListener.bind(media),
    })));
  });
  afterEach(() => { dispose?.(); document.head.querySelector('meta[name="theme-color"]')?.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("defaults to light even on a dark OS without creating a stored preference", async () => {
    dispose = initializeTheme();
    render(<ThemeToggle variant="icon" />);
    expect(document.documentElement).not.toHaveClass("dark");
    expect(document.head.querySelector('meta[name="theme-color"]')).toHaveAttribute("content", "#FFF4E8");
    expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeVisible();
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    darkOS = false;
    act(() => media.dispatchEvent(new Event("change")));
    await waitFor(() => expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeVisible());
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });
  it.each(["light", "dark"])("keeps an explicit %s choice over OS changes", (choice) => {
    localStorage.setItem(THEME_KEY, choice);
    dispose = initializeTheme();
    expect(document.documentElement.classList.contains("dark")).toBe(choice === "dark");
    expect(document.head.querySelector('meta[name="theme-color"]')).toHaveAttribute("content", choice === "dark" ? "#000000" : "#FFF4E8");
    darkOS = !darkOS;
    act(() => media.dispatchEvent(new Event("change")));
    expect(document.documentElement.classList.contains("dark")).toBe(choice === "dark");
  });
  it("saves a click and shares it between toggles", async () => {
    dispose = initializeTheme();
    render(<><ThemeToggle /><ThemeToggle variant="icon" /></>);
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Switch to light mode" })).toBeVisible());
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(document.head.querySelector('meta[name="theme-color"]')).toHaveAttribute("content", "#000000");
    act(() => media.dispatchEvent(new Event("change")));
    expect(document.documentElement).toHaveClass("dark");
  });
  it("defaults an invalid choice to light and accepts a cross-tab choice and reset", () => {
    localStorage.setItem(THEME_KEY, "invalid");
    dispose = initializeTheme();
    expect(document.documentElement).not.toHaveClass("dark");
    localStorage.setItem(THEME_KEY, "dark");
    act(() => window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY, newValue: "dark" })));
    expect(document.documentElement).toHaveClass("dark");
    localStorage.removeItem(THEME_KEY);
    act(() => window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY, newValue: null })));
    expect(document.documentElement).not.toHaveClass("dark");
  });
  it("handles invalid stored values and unavailable storage", async () => {
    localStorage.setItem(THEME_KEY, "broken");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    dispose = initializeTheme();
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Light" })).toBeVisible());
    act(() => media.dispatchEvent(new Event("change")));
    expect(document.documentElement).toHaveClass("dark");
  });
});
