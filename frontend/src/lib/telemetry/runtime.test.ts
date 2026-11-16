import { expect, it, vi } from "vitest";
import type { WebTelemetryConfig } from "../../features/staff/analytics/telemetryApi";

it("emits a second templated view for a different item without reinitializing", async () => {
  vi.resetModules(); const pageView = vi.fn(), start = vi.fn(async () => {}), load = vi.fn(async () => ({ purpose: "analytics" as const, start, stop: vi.fn(), pageView }));
  vi.doMock("./sessionFence", () => ({ browserIdentity: () => "anonymous" }));
  vi.doMock("./providers", () => ({ providerFactories: () => [{ purpose: "analytics", load }] }));
  const { updateWebTelemetry } = await import("./runtime");
  const consent = { analytics: true, replay: false, diagnostics: false };
  const config: WebTelemetryConfig = { pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" } };
  history.replaceState(null, "", "/items/1"); await updateWebTelemetry("scope", config, consent, new URL(location.href), true);
  history.pushState(null, "", "/items/2"); await updateWebTelemetry("scope", config, consent, new URL(location.href), true);
  expect(load).toHaveBeenCalledTimes(1); expect(pageView).toHaveBeenCalledWith("/items/:itemId");
  vi.doUnmock("./sessionFence"); vi.doUnmock("./providers");
});

it("queues the latest safe navigation while a provider import is pending", async () => {
  vi.resetModules(); let resolve!: (value: { purpose: "analytics"; start: () => Promise<void>; stop: () => void; pageView: (path: string) => void }) => void;
  const pageView = vi.fn(), load = vi.fn(() => new Promise<{ purpose: "analytics"; start: () => Promise<void>; stop: () => void; pageView: (path: string) => void }>(done => { resolve = done; }));
  vi.doMock("./sessionFence", () => ({ browserIdentity: () => "anonymous" }));
  vi.doMock("./providers", () => ({ providerFactories: () => [{ purpose: "analytics", load }] }));
  const { updateWebTelemetry } = await import("./runtime"); const config: WebTelemetryConfig = { pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" } };
  const consent = { analytics: true, replay: false, diagnostics: false };
  history.replaceState(null, "", "/items/1"); const first = updateWebTelemetry("scope", config, consent, new URL(location.href), true);
  history.pushState(null, "", "/items/2"); const next = updateWebTelemetry("scope", config, consent, new URL(location.href), true);
  resolve({ purpose: "analytics", start: async () => undefined, stop: vi.fn(), pageView }); await Promise.all([first, next]);
  expect(load).toHaveBeenCalledTimes(1); expect(pageView).toHaveBeenCalledWith("/items/:itemId");
  vi.doUnmock("./sessionFence"); vi.doUnmock("./providers");
});
