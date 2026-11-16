import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { chooseTheme, claimTenantDefaultTheme, currentTheme, initializeTheme, themePreference } from "./theme";
import { tenantDefaultMode } from "./useTenantBranding";

let stop: () => void;
beforeEach(() => { localStorage.clear(); document.documentElement.classList.remove("dark"); stop = initializeTheme(); });
afterEach(() => stop());

describe("the space's default look", () => {
  it("reads only valid modes from a theme blob", () => {
    expect(tenantDefaultMode({ mode: "dark" })).toBe("dark");
    expect(tenantDefaultMode({ mode: "system" })).toBe("system");
    expect(tenantDefaultMode({ mode: "purple" })).toBeUndefined();
    expect(tenantDefaultMode(null)).toBeUndefined();
  });
  it("paints solid black until the page is left", () => {
    const release = claimTenantDefaultTheme("dark");
    expect(currentTheme()).toBe("dark");
    expect(themePreference()).toBe("dark");
    release();
    expect(currentTheme()).toBe("light");
  });
  it("lets the visitor's own choice win, before or after the claim", () => {
    chooseTheme("light");
    const release = claimTenantDefaultTheme("dark");
    expect(currentTheme()).toBe("light");
    release();
    localStorage.clear();
    const again = claimTenantDefaultTheme("dark");
    chooseTheme("light");
    expect(currentTheme()).toBe("light");
    again();
  });
  it("ignores an unknown mode and keeps light as the default", () => {
    const release = claimTenantDefaultTheme("neon");
    expect(themePreference()).toBe("light");
    release();
  });
});
