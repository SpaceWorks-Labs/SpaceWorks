import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyticsTemplate, installAnalyticsNavigationGuard, isBearerUrl, pageView, removeAnalytics } from "./webAnalytics";

const url = (path: string) => new URL(path, "https://space.example.org");
const GOOD = { scriptUrl: "https://stats.example.org/js/script.manual.js", collectUrl: "https://stats.example.org/api/event", domain: "space.example.org" };

afterEach(() => { removeAnalytics(); delete window.__WEB_ANALYTICS__; vi.restoreAllMocks(); });

describe("analyticsTemplate", () => {
  it.each([["/", "/"], ["/about", "/about"], ["/events/12", "/events/:id"], ["/m/forge/events/3", "/m/:slug/events/:id"], ["/m/forge/inventory", "/m/:slug/inventory"]])(
    "%s reports the template %s, never the real path", (path, template) => expect(analyticsTemplate(url(path))).toBe(template));
  it("refuses anything with a query or fragment, and any unknown path", () => {
    expect(analyticsTemplate(url("/events/12?x=1"))).toBeNull();
    expect(analyticsTemplate(url("/events/12#top"))).toBeNull();
    expect(analyticsTemplate(url("/some/private/page"))).toBeNull();
    expect(analyticsTemplate(url("/anna-handle"))).toBeNull();
  });
});

describe("isBearerUrl", () => {
  it.each(["/ticket/abc", "/tickets/abc", "/claim/x", "/reset-password/x", "/station/1", "/event-check-in/x", "/kiosk", "/invite/x", "/space-invite/x",
    "/org-invitations/x", "/embed/x", "/reauth", "/app/auth", "/app/auth/callback"])("treats %s as a credential screen", (path) => expect(isBearerUrl(url(path))).toBe(true));
  it("treats any fragment as a credential", () => expect(isBearerUrl(url("/about#x"))).toBe(true));
  it.each(["token", "secret", "code", "nonce", "claim", "invite", "state", "access_token"])("treats the query key %s as a credential, even on a console page", (key) => {
    expect(isBearerUrl(url(`/about?${key}=1`))).toBe(true);
    expect(isBearerUrl(url(`/admin?${key}=1`))).toBe(true);
  });
  it("leaves ordinary console navigation alone, even with a harmless query", () => {
    expect(isBearerUrl(url("/admin"))).toBe(false);
    expect(isBearerUrl(url("/m/forge/admin/x?tab=2"))).toBe(false);
    expect(isBearerUrl(url("/member/profile"))).toBe(false);
    expect(isBearerUrl(url("/guest-admin"))).toBe(false);
  });
  it("fails closed for an unrecognised public route and for a public page with a query", () => {
    expect(isBearerUrl(url("/brand-new-page"))).toBe(true);
    expect(isBearerUrl(url("/about?utm=1"))).toBe(true);
  });
  it("lets a known public route through", () => expect(isBearerUrl(url("/about"))).toBe(false));
});

describe("pageView", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => { fetchMock = vi.fn().mockResolvedValue(new Response("")); vi.stubGlobal("fetch", fetchMock); });
  afterEach(() => vi.unstubAllGlobals());

  it("does nothing, and removes any script, when analytics is not configured", () => {
    document.head.insertAdjacentHTML("beforeend", '<script id="web-analytics"></script>');
    pageView(url("/about"));
    expect(document.getElementById("web-analytics")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([
    ["a missing collect url", { ...GOOD, collectUrl: "" }], ["a missing script url", { ...GOOD, scriptUrl: "" }],
    ["an http script", { ...GOOD, scriptUrl: "http://stats.example.org/script.manual.js" }],
    ["credentials in a url", { ...GOOD, collectUrl: "https://u:p@stats.example.org/e" }],
    ["a query on the script", { ...GOOD, scriptUrl: "https://stats.example.org/script.manual.js?x=1" }],
    ["a fragment on the collector", { ...GOOD, collectUrl: "https://stats.example.org/e#x" }],
    ["a script that is not the manual build", { ...GOOD, scriptUrl: "https://stats.example.org/js/script.js" }],
    ["a malformed domain", { ...GOOD, domain: "bad domain!" }], ["an unparseable url", { ...GOOD, scriptUrl: "not a url" }],
  ])("refuses %s", (_n, config) => {
    window.__WEB_ANALYTICS__ = config;
    pageView(url("/about"));
    expect(document.getElementById("web-analytics")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("loads the provider script once with privacy attributes and sends only the route template", () => {
    window.__WEB_ANALYTICS__ = GOOD;
    pageView(url("/events/12"));
    pageView(url("/events/13"));
    const scripts = document.querySelectorAll("#web-analytics");
    expect(scripts).toHaveLength(1);
    const script = scripts[0] as HTMLScriptElement;
    expect(script.src).toBe(GOOD.scriptUrl);
    expect(script.defer).toBe(true);
    expect(script.referrerPolicy).toBe("no-referrer");
    expect(script.dataset).toMatchObject({ manual: "true", autoPageviews: "false", domain: "space.example.org", api: GOOD.collectUrl });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [target, init] = fetchMock.mock.calls[0];
    expect(target).toBe(GOOD.collectUrl);
    expect(init).toMatchObject({ method: "POST", mode: "cors", credentials: "omit", referrerPolicy: "no-referrer" });
    expect(JSON.parse(init.body)).toEqual({ n: "pageview", u: "https://space.example.org/events/:id", d: "space.example.org", r: "", p: { client: "web" } });
  });
  it("sends nothing and removes the script on a page that must not be tracked", () => {
    window.__WEB_ANALYTICS__ = GOOD;
    pageView(url("/about"));
    fetchMock.mockClear();
    pageView(url("/ticket/secret"));
    expect(document.getElementById("web-analytics")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it("survives a collector that is unreachable", async () => {
    window.__WEB_ANALYTICS__ = GOOD;
    fetchMock.mockRejectedValue(new Error("offline"));
    expect(() => pageView(url("/about"))).not.toThrow();
    await Promise.resolve();
  });
});

describe("removeAnalytics", () => {
  it("removes the script element and the provider global", () => {
    document.head.insertAdjacentHTML("beforeend", '<script id="web-analytics"></script>');
    window.plausible = () => undefined;
    removeAnalytics();
    expect(document.getElementById("web-analytics")).toBeNull();
    expect(window.plausible).toBeUndefined();
  });
});

describe("installAnalyticsNavigationGuard", () => {
  it("installs nothing without a valid config", () => expect(installAnalyticsNavigationGuard()).toBeUndefined());
  it("lets an ordinary public navigation through and restores history methods on cleanup", () => {
    window.__WEB_ANALYTICS__ = GOOD;
    const pushState = window.history.pushState;
    const cleanup = installAnalyticsNavigationGuard()!;
    expect(window.history.pushState).not.toBe(pushState);
    window.history.pushState({}, "", "/about");
    expect(window.location.pathname).toBe("/about");
    cleanup();
    expect(window.history.pushState).toBe(pushState);
    window.history.replaceState({}, "", "/");
  });
  it("hard-navigates instead of pushing into a credential URL, removing the script first", () => {
    window.__WEB_ANALYTICS__ = GOOD;
    const assign = vi.fn();
    const original = window.location;
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, href: original.href, assign } });
    document.head.insertAdjacentHTML("beforeend", '<script id="web-analytics"></script>');
    const cleanup = installAnalyticsNavigationGuard()!;
    window.history.pushState({}, "", "/ticket/abc");
    expect(assign).toHaveBeenCalledWith(expect.stringContaining("/ticket/abc"));
    expect(document.getElementById("web-analytics")).toBeNull();
    cleanup();
    Object.defineProperty(window, "location", { configurable: true, value: original });
  });
});
