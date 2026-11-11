import { describe, expect, it, vi } from "vitest";
import { providerFactories, safeOrigin } from "./providers";

const posthogSpy = vi.hoisted(() => vi.fn(() => ({ purpose: "analytics" })));
vi.mock("./adapters/posthog", () => ({ posthog: posthogSpy }));
import { TelemetryController } from "./controller";
import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";

const config: WebTelemetryConfig = {
  pageview: { provider: "posthog", site_id: "project", endpoint: "https://analytics.example" },
  replay: { provider: "posthog", site_id: "project", endpoint: "https://analytics.example" },
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" },
};
describe("provider selection", () => {
  it("coalesces PostHog analytics and replay to a single loader", () => {
    expect(providerFactories(config, { analytics: true, replay: true, diagnostics: false }, "/about")).toHaveLength(1);
  });
  it("keeps loader untouched when consent is denied", async () => {
    history.replaceState(null, "", "/about");
    const load = vi.fn();
    await new TelemetryController().start(new URL(location.href), { analytics: false, replay: false, diagnostics: false }, [{ purpose: "replay", load }], () => true);
    expect(load).not.toHaveBeenCalled();
  });
});

it("only selects legacy fallback with explicit backend permission and no primary", async () => {
  const { legacySelected } = await import("./legacy");
  const none = { ...config, pageview: { provider: "none" as const, site_id: "", endpoint: "" } };
  expect(legacySelected(none, true, true)).toBe(true);
  expect(legacySelected(none, false, true)).toBe(false);
  expect(legacySelected(config, true, true)).toBe(false);
});

describe("endpoint guard and PostHog project isolation", () => {
  it("accepts only a bare https origin", () => {
    expect(safeOrigin("https://analytics.example/")).toBe("https://analytics.example");
    for (const bad of ["http://analytics.example", "https://user:pw@analytics.example", "https://analytics.example/x.js", "https://analytics.example?q=1", "https://analytics.example#f", "javascript:alert(1)", "https://a.example\@evil.example", "not a url"]) expect(safeOrigin(bad)).toBeUndefined();
  });
  it("skips a provider whose endpoint is not a safe origin", () => {
    const umami = { ...config, pageview: { provider: "umami" as const, site_id: "id", endpoint: "http://analytics.example" }, replay: { provider: "none" as const, site_id: "", endpoint: "" } };
    expect(providerFactories(umami, { analytics: true, replay: false, diagnostics: false }, "/")).toHaveLength(0);
  });
  it("never sends replay to the analytics project when the PostHog projects differ", async () => {
    posthogSpy.mockClear();
    const split = { ...config, replay: { provider: "posthog" as const, site_id: "other", endpoint: "https://analytics.example" } };
    const [factory] = providerFactories(split, { analytics: true, replay: true, diagnostics: false }, "/about");
    await factory.load();
    expect(posthogSpy).toHaveBeenCalledWith("project", "https://analytics.example", true, false, "/about");
    posthogSpy.mockClear();
    const [same] = providerFactories(config, { analytics: true, replay: true, diagnostics: false }, "/about");
    await same.load();
    expect(posthogSpy).toHaveBeenCalledWith("project", "https://analytics.example", true, true, "/about");
  });
});
