import { t } from "@lingui/core/macro";
import { afterEach, describe, expect, it, vi } from "vitest";
import { formatDate, formatDateTime, formatLocale, formatNumber, formatPercent, formatTime, localDateIn } from "./format";
import { activeLocale, canonicalLocale, localeHeaders, localeSource, setExplicitLocale, setMakerspaceLocale, setUserLocale, withLocaleHeaders } from "./i18n";

afterEach(() => {
  vi.unstubAllGlobals();
  setExplicitLocale(null);
  setUserLocale(null);
  setMakerspaceLocale(null);
});

describe("i18n runtime", () => {
  it("activates English and renders macro messages", () => {
    expect(activeLocale()).toBe("en");
    const name = "Ada";
    expect(t`Hello ${name}`).toBe("Hello Ada");
  });

  it("canonicalises like the backend", () => {
    expect(canonicalLocale("EN-us")).toBe("en");
    expect(canonicalLocale("en_GB")).toBe("en");
    expect(canonicalLocale("fr")).toBeNull();
    expect(canonicalLocale("")).toBeNull();
  });

  it("keeps the source order explicit > user > makerspace > system", () => {
    expect(localeSource()).toBe("system");
    setMakerspaceLocale("en");
    expect(localeSource()).toBe("makerspace");
    setUserLocale("en");
    expect(localeSource()).toBe("user");
    setExplicitLocale("en");
    expect(localeSource()).toBe("explicit");
    setExplicitLocale(null);
    expect(localeSource()).toBe("user");
    setUserLocale("fr");
    expect(localeSource()).toBe("makerspace");
  });

  it("sends X-SpaceWorks-Locale only for an explicit choice", () => {
    setUserLocale("en");
    expect(localeHeaders()).toEqual({ "Accept-Language": "en" });
    setExplicitLocale("en");
    expect(localeHeaders()).toEqual({ "Accept-Language": "en", "X-SpaceWorks-Locale": "en" });
    setExplicitLocale(null);
    const merged = withLocaleHeaders({ "X-SpaceWorks-Locale": "fr", Authorization: "Bearer x" });
    expect(merged.get("X-SpaceWorks-Locale")).toBeNull();
    expect(merged.get("Authorization")).toBe("Bearer x");
  });

  it("ignores unsupported explicit choices", () => {
    setExplicitLocale("xx");
    expect(localeSource()).toBe("system");
  });
});

describe("format", () => {
  it("keeps the browser's regional variant of the active language", () => {
    vi.stubGlobal("navigator", { languages: ["en-GB", "en"], language: "en-GB" });
    expect(formatLocale()).toBe("en-GB");
    vi.stubGlobal("navigator", { languages: ["de-DE"], language: "de-DE" });
    expect(formatLocale()).toBe("en");
  });

  it("formats with the formatting locale, never undefined", () => {
    vi.stubGlobal("navigator", { languages: ["en-US"], language: "en-US" });
    const date = new Date(Date.UTC(2026, 0, 2, 15, 4));
    expect(formatDate(date, { timeZone: "UTC" })).toBe(date.toLocaleDateString("en-US", { timeZone: "UTC" }));
    expect(formatTime(date, { timeZone: "UTC", hour: "2-digit", minute: "2-digit" })).toContain("03:04");
    expect(formatDateTime(date.toISOString(), { timeZone: "UTC", year: "numeric" })).toBe("2026");
    expect(formatNumber(1234.5)).toBe("1,234.5");
    expect(formatPercent(0.25)).toBe("25%");
  });
});

describe("localDateIn", () => {
  it("uses the zone's calendar day, not UTC", () => {
    const instant = new Date("2026-11-09T22:30:00Z");
    expect(localDateIn("UTC", instant)).toBe("2026-11-09");
    expect(localDateIn("Asia/Kolkata", instant)).toBe("2026-11-10");
  });
});
