import { afterEach, describe, expect, it, vi } from "vitest";
import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";
import { installTelemetryBoundary } from "./boundary";
import { consentScope } from "./consentScope";
import { telemetryScope } from "./scope";

/** Decision 263 addendum: a space's telemetry stays with that space, the platform's with platform pages. */
const config = (siteId: string): WebTelemetryConfig => ({
  pageview: { provider: "ga4", site_id: siteId, endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" },
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" },
});
const consent = { analytics: true, replay: false, diagnostics: false };
const slugOf = (url: URL) => url.pathname.match(/^\/m\/([^/]+)/)?.[1] ?? "root";

afterEach(() => { vi.doUnmock("./sessionFence"); vi.doUnmock("./providers"); vi.resetModules(); });

describe("scope selection", () => {
  it("gives each space and the platform its own scope", () => {
    expect(telemetryScope(new URL("/m/alpha/events", location.origin), false)).toEqual({ kind: "tenant", slug: "alpha" });
    expect(telemetryScope(new URL("/m/beta/events", location.origin), false)).toEqual({ kind: "tenant", slug: "beta" });
    expect(telemetryScope(new URL("/about", location.origin), false)).toEqual({ kind: "platform" });
    expect(telemetryScope(new URL("/about", location.origin), true, "alpha")).toEqual({ kind: "tenant", slug: "alpha" });
  });
  it("never shares a consent binding between spaces or with the platform, even with identical settings", async () => {
    const policy = [config("G-SAME"), null];
    const keys = await Promise.all([consentScope(1, policy), consentScope(2, policy), consentScope(0, policy)]);
    expect(new Set(keys).size).toBe(3);
  });
});

describe("switching scope in one session", () => {
  async function runtimeWith(loaded: string[], stopped: string[]) {
    vi.resetModules();
    vi.doMock("./sessionFence", () => ({ browserIdentity: () => "anonymous" }));
    vi.doMock("./providers", () => ({ providerFactories: (value: WebTelemetryConfig) => [{ purpose: "analytics", load: async () => {
      loaded.push(value.pageview.site_id);
      return { purpose: "analytics" as const, start: async () => undefined, stop: () => { stopped.push(value.pageview.site_id); }, pageView: vi.fn() };
    } }] }));
    return import("./runtime");
  }

  it("tears down space A's provider and never starts space B's in the same document", async () => {
    const loaded: string[] = [], stopped: string[] = [];
    const { updateWebTelemetry } = await runtimeWith(loaded, stopped);
    history.replaceState(null, "", "/m/alpha/events");
    await updateWebTelemetry("1:alpha", config("G-ALPHA"), consent, new URL(location.href), true);
    expect(loaded).toEqual(["G-ALPHA"]);
    history.replaceState(null, "", "/m/beta/events");
    await updateWebTelemetry("2:beta", config("G-BETA"), consent, new URL(location.href), true);
    // A full document reload is required before B may load: A's SDK is gone, B's never ran here.
    expect(stopped).toContain("G-ALPHA");
    expect(loaded).toEqual(["G-ALPHA"]);
  });

  it("does not carry a space's provider onto platform pages", async () => {
    const loaded: string[] = [], stopped: string[] = [];
    const { updateWebTelemetry } = await runtimeWith(loaded, stopped);
    history.replaceState(null, "", "/m/alpha/events");
    await updateWebTelemetry("1:alpha", config("G-ALPHA"), consent, new URL(location.href), true);
    history.replaceState(null, "", "/about");
    await updateWebTelemetry("0:platform", config("G-PLATFORM"), consent, new URL(location.href), true);
    expect(stopped).toContain("G-ALPHA");
    expect(loaded).not.toContain("G-PLATFORM");
  });

  it("loads only the current space when nothing was loaded before the switch", async () => {
    const loaded: string[] = [], stopped: string[] = [];
    const { updateWebTelemetry } = await runtimeWith(loaded, stopped);
    history.replaceState(null, "", "/m/beta/events");
    await updateWebTelemetry("2:beta", config("G-BETA"), consent, new URL(location.href), true);
    expect(loaded).toEqual(["G-BETA"]);
  });

  it("starts nothing while the browser is not verified anonymous", async () => {
    const loaded: string[] = [], stopped: string[] = [];
    const { updateWebTelemetry } = await runtimeWith(loaded, stopped);
    history.replaceState(null, "", "/m/alpha/events");
    await updateWebTelemetry("1:alpha", config("G-ALPHA"), consent, new URL(location.href), false);
    expect(loaded).toEqual([]);
  });
});

describe("navigation boundary", () => {
  it("leaves the SPA when a loaded page moves to another space or to the platform", () => {
    for (const target of ["/m/beta/events", "/about"]) {
      history.replaceState(null, "", "/m/alpha/events");
      const stop = vi.fn();
      const dispose = installTelemetryBoundary(() => true, stop, slugOf);
      try {
        history.pushState(null, "", target);
        expect(stop).toHaveBeenCalledOnce();
        expect(location.pathname).toBe("/m/alpha/events");
      } finally { dispose(); }
    }
  });
  it("stays in the SPA before any provider loaded", () => {
    history.replaceState(null, "", "/m/alpha/events");
    const stop = vi.fn();
    const dispose = installTelemetryBoundary(() => false, stop, slugOf);
    try { history.pushState(null, "", "/m/beta/events"); expect(stop).not.toHaveBeenCalled(); expect(location.pathname).toBe("/m/beta/events"); }
    finally { dispose(); }
  });
});

describe("session fence", () => {
  it("fences telemetry on a sign-in in this tab and on a session pulse from another tab", async () => {
    vi.resetModules();
    const { installSessionTelemetryFence, beforeSessionTransition, browserIdentity } = await import("./sessionFence");
    const fence = vi.fn(() => false);
    const dispose = installSessionTelemetryFence(fence);
    try {
      beforeSessionTransition();
      expect(fence).toHaveBeenCalledTimes(1);
      expect(browserIdentity()).toBe("auth_present");
      window.dispatchEvent(new StorageEvent("storage", { key: "spaceworks-session-pulse", newValue: "x" }));
      expect(fence).toHaveBeenCalledTimes(2);
      expect(browserIdentity()).toBe("unknown");
    } finally { dispose(); }
  });
});
