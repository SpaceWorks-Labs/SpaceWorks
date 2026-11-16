import { afterEach, describe, expect, it, vi } from "vitest";
import { analyticsTemplate, isBearerUrl, pageView, removeAnalytics } from "./webAnalytics";

afterEach(() => {
  removeAnalytics();
  delete window.__WEB_ANALYTICS__;
  vi.unstubAllGlobals();
});
const url = (path: string) => new URL(path, "https://space.example");

describe("booking public analytics adapter", () => {
  it.each([
    ["/bookings", "/bookings"],
    ["/m/real-tenant/bookings", "/m/:slug/bookings"],
    ["/bookings/public-resource-id", "/bookings/:resourceToken"],
    ["/m/real-tenant/bookings/public-resource-id", "/m/:slug/bookings/:resourceToken"],
  ])("projects %s to a route template", (path, template) => {
    expect(analyticsTemplate(url(path))).toBe(template);
  });

  it.each([
    "/member/bookings/private-confirmation", "/m/private/member/bookings/private-confirmation",
    "/admin/spaces/42/check-in", "/staff/booking-invite#private-invite",
    "/m/private/admin/spaces/42/website", "/admin/spaces/42/website",
    "/bookings/resource?confirmation=private-booking",
    "/m/private/bookings/resource?confirmation=private-booking",
    "/scanner", "/staff/booking-invite",
    "/bookings/resource?token=private-qr", "/bookings/resource#private-token",
    "/api/v1/public/booking-feeds/private-feed", "/embed/tenant/bookings/private-embed",
    "/api/v1/public/tenant/bookings/calendar/private-feed.ics",
    "/m/tenant/member/bookings/private-confirmation",
  ])("excludes private navigation %s", path => {
    const collect = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", collect);
    window.__WEB_ANALYTICS__ = { scriptUrl: "https://stats.example/js/script.manual.js",
      collectUrl: "https://stats.example/api/event", domain: "space.example" };
    pageView(url(path));
    expect(analyticsTemplate(url(path))).toBeNull();
    expect(collect).not.toHaveBeenCalled();
    expect(document.getElementById("web-analytics")).toBeNull();
  });

  it("omits real identities and referrer, and cancels collection before private navigation", () => {
    const collect = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", collect);
    window.__WEB_ANALYTICS__ = { scriptUrl: "https://stats.example/js/script.manual.js",
      collectUrl: "https://stats.example/api/event", domain: "space.example" };
    pageView(url("/m/tenant-secret/bookings/resource-secret"));
    expect(collect).toHaveBeenCalledOnce();
    const options = collect.mock.calls[0][1];
    expect(JSON.parse(options.body)).toEqual({ n: "pageview",
      u: "https://space.example/m/:slug/bookings/:resourceToken", d: "space.example", r: "", p: { client: "web" } });
    expect(options.referrerPolicy).toBe("no-referrer");
    expect(options.credentials).toBe("omit");
    expect(document.getElementById("web-analytics")?.dataset.manual).toBe("true");
    pageView(url("/member/bookings/private-confirmation"));
    expect(document.getElementById("web-analytics")).toBeNull();
    expect(options.signal.aborted).toBe(true);
  });

  it("recognizes credential boundaries for the shared full-document navigation guard", () => {
    expect(isBearerUrl(url("/staff/booking-invite#private-invite"))).toBe(true);
    expect(isBearerUrl(url("/bookings/resource?token=private-qr"))).toBe(true);
    expect(isBearerUrl(url("/bookings/public-resource"))).toBe(false);
  });
});
