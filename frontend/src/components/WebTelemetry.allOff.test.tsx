import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ bootstrap: vi.fn(), platform: vi.fn(), update: vi.fn(), scope: vi.fn() }));
vi.mock("../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "", bootstrap: null }) }));
vi.mock("../features/inventory/usePublicInventory", () => ({ useTenantBootstrap: mocks.bootstrap }));
vi.mock("../lib/api/requests", () => ({ publicAnonymousRequest: mocks.platform }));
vi.mock("../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => false }));
vi.mock("../lib/telemetry/sessionFence", () => ({ browserIdentity: () => "anonymous", subscribeBrowserIdentity: () => () => {}, resolveBrowserIdentity: vi.fn(), markAuthPresent: vi.fn() }));
vi.mock("../lib/telemetry/consentScope", () => ({ consentScope: mocks.scope }));
vi.mock("../lib/telemetry/runtime", () => ({ updateWebTelemetry: mocks.update, stopWebTelemetry: vi.fn() }));
vi.mock("./TelemetryConsent", () => ({ TelemetryConsent: () => <button>Privacy preferences</button> }));
import { WebTelemetry } from "./WebTelemetry";

const defaults = {
  pageview: { provider: "none", site_id: "", endpoint: "" },
  replay: { provider: "none", site_id: "", endpoint: "" },
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" },
};

function ConfigReady() {
  const query = useQuery({ queryKey: ["platform-telemetry-config"], queryFn: mocks.platform, enabled: false });
  return query.isSuccess ? <span>Configuration loaded</span> : null;
}
function setup(path: string, ready = false) {
  mocks.update.mockClear(); mocks.scope.mockReset(); mocks.scope.mockResolvedValue("scope");
  delete window.__WEB_ANALYTICS__;
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><WebTelemetry />{ready ? <ConfigReady /> : null}</MemoryRouter>
  </QueryClientProvider>);
}
afterEach(() => { cleanup(); vi.clearAllMocks(); delete window.__WEB_ANALYTICS__; });

it("does not show consent or admit a provider for anonymous all-off platform configuration", async () => {
  mocks.bootstrap.mockReturnValue({ data: undefined });
  mocks.platform.mockResolvedValue({ platform_telemetry: defaults, platform_telemetry_legacy_allowed: false });
  setup("/about", true);
  await screen.findByText("Configuration loaded");
  await act(async () => {});
  expect(screen.queryByRole("button", { name: "Privacy preferences" })).not.toBeInTheDocument();
  expect(mocks.scope).not.toHaveBeenCalled();
  expect(mocks.update).not.toHaveBeenCalled();
});

it("keeps anonymous tenant module-off defaults inert without falling back to platform providers", async () => {
  mocks.platform.mockClear();
  mocks.bootstrap.mockReturnValue({ data: { makerspace: { id: 7, slug: "lab" }, telemetry: defaults, telemetry_legacy_allowed: false } });
  setup("/m/lab");
  await act(async () => {});
  expect(mocks.bootstrap).toHaveBeenCalledWith("lab", true);
  expect(mocks.platform).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Privacy preferences" })).not.toBeInTheDocument();
  expect(mocks.scope).not.toHaveBeenCalled();
  expect(mocks.update).not.toHaveBeenCalled();
});
