import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { deniedConsent, readConsent } from "../lib/telemetry/policy";

const mocks = vi.hoisted(() => ({ bootstrap: vi.fn(), platform: vi.fn(), update: vi.fn(), stop: vi.fn(), scope: vi.fn(), identity: "anonymous" }));
vi.mock("../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "", bootstrap: null }) }));
vi.mock("../features/inventory/usePublicInventory", () => ({ useTenantBootstrap: mocks.bootstrap }));
vi.mock("../lib/api/requests", () => ({ publicAnonymousRequest: mocks.platform }));
vi.mock("../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => false }));
vi.mock("../lib/telemetry/sessionFence", () => ({ browserIdentity: () => mocks.identity, subscribeBrowserIdentity: () => () => {}, resolveBrowserIdentity: vi.fn(), markAuthPresent: vi.fn() }));
vi.mock("../lib/telemetry/consentScope", () => ({ consentScope: mocks.scope }));
vi.mock("../lib/telemetry/runtime", () => ({ updateWebTelemetry: mocks.update, stopWebTelemetry: mocks.stop }));
import { WebTelemetry } from "./WebTelemetry";

const config = {
  pageview: { provider: "none", site_id: "", endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" },
  diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } },
  firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" },
};
const selected = { token: "cx15-public-token", apiHost: "https://api-eu.mixpanel.com", sdkHost: "https://sdk.example.test" };
const boot = (modules: string[] = ["analytics"]) => ({ makerspace: { id: 7, slug: "lab" }, modules, telemetry: config, telemetry_legacy_allowed: false });
beforeEach(() => {
  vi.clearAllMocks(); localStorage.clear(); mocks.identity = "anonymous";
  window.__MIXPANEL__ = selected;
  mocks.scope.mockImplementation(async (_id, policy) => JSON.stringify(policy));
  mocks.bootstrap.mockReturnValue({ data: undefined });
  mocks.platform.mockResolvedValue({ platform_telemetry: config, platform_telemetry_legacy_allowed: false });
});
afterEach(() => { cleanup(); delete window.__MIXPANEL__; });
function setup(path: string) {
  history.replaceState(null, "", path);
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><WebTelemetry /></MemoryRouter>
  </QueryClientProvider>);
}

it.each(["/", "/about"])("landing page %s uses the real consent banner and persists grant then withdrawal", async path => {
  setup(path);
  const checkbox = await screen.findByRole("checkbox", { name: "Usage analytics" });
  expect(checkbox).not.toBeChecked();
  await waitFor(() => expect(mocks.update).toHaveBeenCalled());
  expect(mocks.update.mock.lastCall![2]).toEqual(deniedConsent());
  expect(mocks.update.mock.lastCall![6]).toEqual(selected);
  fireEvent.click(checkbox);
  expect(mocks.update.mock.lastCall![2]).toEqual({ ...deniedConsent(), analytics: true });
  const scope = await mocks.scope.mock.results[0].value;
  expect(readConsent(scope)).toEqual({ ...deniedConsent(), analytics: true });
  fireEvent.click(checkbox);
  expect(mocks.update.mock.lastCall![2]).toEqual(deniedConsent());
  expect(readConsent(scope)).toEqual(deniedConsent());
});

it("tenant analytics off hides Mixpanel; restoring the module restores consent with rows untouched", async () => {
  const row = boot([]); mocks.bootstrap.mockReturnValue({ data: row });
  const view = setup("/m/lab"); await act(async () => {});
  expect(screen.queryByRole("checkbox", { name: "Usage analytics" })).not.toBeInTheDocument();
  expect(mocks.update).not.toHaveBeenCalled(); expect(mocks.platform).not.toHaveBeenCalled();
  const enabled = { ...row, modules: ["analytics"] }; mocks.bootstrap.mockReturnValue({ data: enabled });
  view.rerender(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/m/lab"]}><WebTelemetry /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("checkbox", { name: "Usage analytics" })).not.toBeChecked();
  expect(enabled.telemetry).toBe(row.telemetry);
  expect(mocks.update.mock.lastCall![6]).toEqual(selected);
});

it("unknown tenant does not inherit the deployment provider or fetch platform config", async () => {
  setup("/m/unknown"); await act(async () => {});
  expect(mocks.platform).not.toHaveBeenCalled(); expect(mocks.update).not.toHaveBeenCalled();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it.each(["unknown", "authenticated"])("identity %s keeps collection stopped", async identity => {
  mocks.identity = identity; mocks.bootstrap.mockReturnValue({ data: boot() }); setup("/m/lab");
  await act(async () => {});
  expect(mocks.update).not.toHaveBeenCalled(); expect(mocks.stop).toHaveBeenCalled();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});

it("token or host changes bind a fresh denied consent policy", async () => {
  mocks.bootstrap.mockReturnValue({ data: boot() });
  const view = setup("/m/lab");
  fireEvent.click(await screen.findByRole("checkbox", { name: "Usage analytics" }));
  expect(mocks.update.mock.lastCall![2].analytics).toBe(true);
  window.__MIXPANEL__ = { ...selected, token: "other-public-project", apiHost: "https://collector.example.test" };
  view.rerender(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/m/lab"]}><WebTelemetry /></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(screen.getByRole("checkbox", { name: "Usage analytics" })).not.toBeChecked());
  expect(mocks.update.mock.lastCall![2]).toEqual(deniedConsent());
  expect(mocks.update.mock.lastCall![6]).toEqual(window.__MIXPANEL__);
});

it("a disabled deployment has no consent surface even on an analytics-enabled tenant", async () => {
  delete window.__MIXPANEL__; mocks.bootstrap.mockReturnValue({ data: boot() });
  setup("/m/lab"); await act(async () => {});
  expect(mocks.update).not.toHaveBeenCalled(); expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});
