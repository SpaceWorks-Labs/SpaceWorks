import { describe, expect, it } from "vitest";
import { formatMoney } from "../../lib/money";
import { drillHref, formatBytes, formatValue, offText } from "./overviewFormat";
import { overviewParams, overviewReady, readyOverview } from "./platformOverviewApi";

describe("platform overview formatting (#183A)", () => {
  it("formats each unit and leaves unmeasurable values as a dash", () => {
    expect(formatValue("percent", null)).toBe("—");
    expect(formatValue("hours", 2.5)).toMatch(/2[.,]5 h/);
    expect(formatBytes(2048)).toMatch(/2 KB/);
  });
  it("keeps money in its own currency", () => {
    expect(formatMoney("10.00", "inr")).toMatch(/10/);
    expect(formatMoney("3.00", "zzz-bad")).toBe("3.00 ZZZ-BAD");
  });
  it("links live spaces by id and never archived ones", () => {
    const live = { id: 7, name: "Lab", slug: "lab", excluded_reason: null, directory_hidden: false };
    expect(drillHref(live, "members")).toContain("for_space=7");
    expect(drillHref({ ...live, excluded_reason: "archived" }, "members")).toBeNull();
  });
  it("says how many spaces have a block off", () => {
    expect(offText(0)).toBe("On in every space");
    expect(offText(1)).toBe("Off in 1 space");
    expect(offText(3)).toBe("Off in 3 spaces");
  });
});

describe("platform overview query", () => {
  it("sends custom dates only for the custom period, once both are valid", () => {
    expect(overviewParams({ preset: "this_year", start: "2026-01-01", end: "", includeExcluded: true }).toString())
      .toBe("period=this_year&include_excluded=true");
    expect(overviewReady({ preset: "custom", start: "2026-02-01", end: "", includeExcluded: false })).toBe(false);
    expect(overviewReady({ preset: "custom", start: "2026-02-10", end: "2026-02-01", includeExcluded: false })).toBe(false);
    expect(overviewParams({ preset: "custom", start: "2026-02-01", end: "2026-02-10", includeExcluded: false }).toString())
      .toBe("period=custom&start=2026-02-01&end=2026-02-10");
  });
  it("treats a computing answer as not ready", () => {
    expect(readyOverview({ status: "computing", retry_after_seconds: 5 })).toBeUndefined();
  });
});
