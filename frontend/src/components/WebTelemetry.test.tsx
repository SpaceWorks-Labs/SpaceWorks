import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ bootstrap: vi.fn(), platform: vi.fn(), update: vi.fn() }));
vi.mock("../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "", bootstrap: null }) }));
vi.mock("../features/inventory/usePublicInventory", () => ({ useTenantBootstrap: mocks.bootstrap }));
vi.mock("../lib/api/requests", () => ({ publicAnonymousRequest: mocks.platform }));
vi.mock("../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => false }));
vi.mock("../lib/telemetry/sessionFence", () => ({ browserIdentity: () => "anonymous", subscribeBrowserIdentity: () => () => {}, resolveBrowserIdentity: vi.fn(), markAuthPresent: vi.fn() }));
vi.mock("../lib/telemetry/consentScope", () => ({ consentScope: async () => "scope" }));
vi.mock("../lib/telemetry/runtime", () => ({ updateWebTelemetry: mocks.update, stopWebTelemetry: vi.fn() }));
vi.mock("./TelemetryConsent", () => ({ TelemetryConsent: ({ onChange }: { onChange: (x: object) => void }) => <button onClick={() => onChange({ analytics: true, replay: false, diagnostics: false })}>Consent</button> }));
import { WebTelemetry } from "./WebTelemetry";
const config = { pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" } };
function renderAt(path: string) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><WebTelemetry /></MemoryRouter></QueryClientProvider>); }
it("does not request platform telemetry for an unresolved tenant", () => {
  mocks.platform.mockClear(); mocks.bootstrap.mockReturnValue({ data: undefined }); renderAt("/m/lab");
  expect(mocks.platform).not.toHaveBeenCalled();
});
it("uses the central legacy permission supplied by platform config", async () => {
  mocks.platform.mockResolvedValue({ platform_telemetry: config, platform_telemetry_legacy_allowed: true });
  mocks.bootstrap.mockReturnValue({ data: undefined }); window.__WEB_ANALYTICS__ = { scriptUrl: "https://metrics.test/manual.js", collectUrl: "https://metrics.test/custom/api", domain: "space.test" };
  renderAt("/about"); await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(expect.any(String), config, expect.any(Object), expect.any(URL), true, true));
  delete window.__WEB_ANALYTICS__;
});
it("uses only the resolved tenant legacy permission on a tenant route", async () => {
  mocks.update.mockClear(); mocks.platform.mockClear();
  mocks.bootstrap.mockReturnValue({ data: { makerspace: { id: 7, slug: "lab" }, telemetry: config, telemetry_legacy_allowed: true } });
  window.__WEB_ANALYTICS__ = { scriptUrl: "https://metrics.test/manual.js", collectUrl: "https://metrics.test/custom/api", domain: "space.test" };
  renderAt("/m/lab"); await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(expect.any(String), config, expect.any(Object), expect.any(URL), true, true));
  expect(mocks.platform).not.toHaveBeenCalled(); delete window.__WEB_ANALYTICS__;
});
