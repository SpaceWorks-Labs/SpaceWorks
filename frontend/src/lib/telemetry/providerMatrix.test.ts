import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TelemetryController, type TelemetryAdapter } from "./controller";
import { providerFactories } from "./providers";
import type { Purpose } from "./policy";
import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";

// Every adapter module is replaced by a recorder: this file proves ADMISSION (when a loader runs, with which
// configured id, and that withdrawal stops it) for all providers using fake ids, with no account and no network.
const calls = vi.hoisted(() => ({ loads: [] as { provider: string; args: unknown[] }[], stops: [] as string[] }));
const fake = (provider: string, purpose: Purpose) => (...args: unknown[]): TelemetryAdapter => {
  calls.loads.push({ provider, args });
  return { purpose, async start() { /* a real adapter would inject its script here */ }, stop() { calls.stops.push(provider); } };
};
vi.mock("./adapters/plausible", () => ({ plausible: fake("plausible", "analytics") }));
vi.mock("./adapters/umami", () => ({ umami: fake("umami", "analytics") }));
vi.mock("./adapters/ga4", () => ({ ga4: fake("ga4", "analytics") }));
vi.mock("./adapters/firebaseAnalytics", () => ({ firebaseAnalytics: fake("firebase", "analytics") }));
vi.mock("./adapters/posthog", () => ({ posthog: fake("posthog", "analytics") }));
vi.mock("./adapters/clarity", () => ({ clarity: fake("clarity", "replay") }));
vi.mock("./adapters/sentry", () => ({ sentry: fake("sentry", "diagnostics") }));
vi.mock("./adapters/firebasePerformance", () => ({ firebasePerformance: fake("firebase_performance", "diagnostics") }));

const none = { provider: "none" as const, site_id: "", endpoint: "" };
const base: WebTelemetryConfig = {
  pageview: none, replay: none,
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "fake-key", auth_domain: "fake.firebaseapp.com", project_id: "fake-proj", app_id: "1:1:web:fake", messaging_sender_id: "1", measurement_id: "G-FAKEFB", vapid_public_key: "" },
};
const off = { analytics: false, replay: false, diagnostics: false };
const CASES: { name: string; provider: string; purpose: Purpose; config: WebTelemetryConfig; id: unknown }[] = [
  { name: "Plausible", provider: "plausible", purpose: "analytics", id: "fake.example", config: { ...base, pageview: { provider: "plausible", site_id: "fake.example", endpoint: "" } } },
  { name: "Umami", provider: "umami", purpose: "analytics", id: "00000000-fake", config: { ...base, pageview: { provider: "umami", site_id: "00000000-fake", endpoint: "https://umami.fake.example" } } },
  { name: "GA4", provider: "ga4", purpose: "analytics", id: "G-FAKE123", config: { ...base, pageview: { provider: "ga4", site_id: "G-FAKE123", endpoint: "" } } },
  { name: "Firebase Analytics", provider: "firebase", purpose: "analytics", id: expect.objectContaining({ measurementId: "G-FAKEFB" }), config: { ...base, pageview: { provider: "firebase", site_id: "", endpoint: "" } } },
  { name: "PostHog", provider: "posthog", purpose: "analytics", id: "phc_fake", config: { ...base, pageview: { provider: "posthog", site_id: "phc_fake", endpoint: "" } } },
  { name: "Clarity", provider: "clarity", purpose: "replay", id: "fakeproj", config: { ...base, replay: { provider: "clarity", site_id: "fakeproj", endpoint: "" } } },
  { name: "Sentry", provider: "sentry", purpose: "diagnostics", id: "https://fakekey@o0.ingest.sentry.io/0", config: { ...base, diagnostics: { ...base.diagnostics, sentry: { enabled: true, dsn: "https://fakekey@o0.ingest.sentry.io/0", sample_rate: 0.5 } } } },
  { name: "Firebase Performance", provider: "firebase_performance", purpose: "diagnostics", id: expect.objectContaining({ projectId: "fake-proj" }), config: { ...base, diagnostics: { ...base.diagnostics, firebase_performance: { enabled: true, sample_rate: 0.1 } } } },
];
const grant = (purpose: Purpose) => ({ ...off, [purpose]: true });
const start = (controller: TelemetryController, config: WebTelemetryConfig, consent: typeof off, path = "/about") => {
  history.replaceState(null, "", path);
  return controller.start(new URL(location.href), consent, providerFactories(config, consent, path), () => true);
};

beforeEach(() => { calls.loads.length = 0; calls.stops.length = 0; });
afterEach(() => vi.restoreAllMocks());

describe.each(CASES)("$name", ({ provider, purpose, config, id }) => {
  it("loads nothing and touches no script, network or cookie before consent", async () => {
    const fetcher = vi.spyOn(window, "fetch"), scripts = document.scripts.length, cookie = document.cookie;
    await start(new TelemetryController(), config, off);
    expect(calls.loads).toEqual([]);
    expect(fetcher).not.toHaveBeenCalled();
    expect(document.scripts.length).toBe(scripts);
    expect(document.cookie).toBe(cookie);
  });
  it("loads with the configured id once its own purpose is granted, and not for another purpose", async () => {
    const other = (["analytics", "replay", "diagnostics"] as Purpose[]).find(item => item !== purpose)!;
    await start(new TelemetryController(), config, grant(other));
    expect(calls.loads).toEqual([]);
    await start(new TelemetryController(), config, grant(purpose));
    expect(calls.loads.map(item => item.provider)).toEqual([provider]);
    expect(calls.loads[0].args[0]).toEqual(id);
  });
  it("stops the adapter when the visitor withdraws", async () => {
    const controller = new TelemetryController();
    await start(controller, config, grant(purpose));
    expect(calls.stops).toEqual([]);
    controller.stop();
    expect(calls.stops).toEqual([provider]);
  });
});

describe("replay routes", () => {
  const clarity = CASES.find(item => item.provider === "clarity")!.config;
  const posthogReplay: WebTelemetryConfig = { ...base, replay: { provider: "posthog", site_id: "phc_fake", endpoint: "" } };
  it("runs Clarity and PostHog replay only on anonymous public routes", async () => {
    for (const config of [clarity, posthogReplay]) {
      calls.loads.length = 0;
      await start(new TelemetryController(), config, grant("replay"), "/about");
      expect(calls.loads).toHaveLength(1);
    }
  });
  it("never starts replay on staff, finance or sign-in routes", async () => {
    for (const path of ["/admin", "/admin/finance", "/login", "/account"]) for (const config of [clarity, posthogReplay]) {
      expect(providerFactories(config, grant("replay"), path)).toHaveLength(0);
    }
  });
});
