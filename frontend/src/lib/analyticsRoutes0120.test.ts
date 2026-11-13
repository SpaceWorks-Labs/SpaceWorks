import { describe, expect, it } from "vitest";
import { analyticsTemplate, isBearerUrl } from "./webAnalytics";
import { analyticsExcludedScreens, analyticsPublicRoutes0120 } from "./analyticsRoutes0120";

const at = (path: string) => new URL(path, window.location.origin);

describe("0.12.0 public pages in the analytics allow-list (decision 326)", () => {
  it.each([
    ["/features", "/features"], ["/features/guest-handover", "/features/:module"], ["/spaces", "/spaces"], ["/docs", "/docs"], ["/docs/api-guide", "/docs/*"],
    ["/help/loans/how-to-borrow", "/help/:sectionId/:articleSlug"], ["/m/tinkerspace/now", "/m/:slug/now"],
  ])("%s counts as the template %s", (path, template) => {
    expect(analyticsTemplate(at(path))).toBe(template);
    expect(isBearerUrl(at(path))).toBe(false);
  });

  it("keeps TV and display screens out", () => {
    for (const path of ["/display", "/stats/tv", "/m/tinkerspace/stats/tv"]) expect(analyticsTemplate(at(path))).toBeNull();
    for (const screen of analyticsExcludedScreens) expect(analyticsPublicRoutes0120).not.toContain(screen);
  });

  it("does not open personal profiles or unknown one-segment paths", () => {
    expect(analyticsTemplate(at("/shaan"))).toBeNull();
    expect(analyticsTemplate(at("/profiles/by-account/12"))).toBeNull();
  });

  it("still refuses query-bearing URLs on the new pages", () => {
    expect(analyticsTemplate(at("/features?ref=x"))).toBeNull();
  });
});
