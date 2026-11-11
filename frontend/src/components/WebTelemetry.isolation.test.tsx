import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ bootstrap: vi.fn(), platform: vi.fn(), update: vi.fn(), stop: vi.fn() }));
vi.mock("../lib/tenant", () => ({ useTenant: () => ({ mode: "central", slug: "", bootstrap: null }) }));
vi.mock("../features/inventory/usePublicInventory", () => ({ useTenantBootstrap: mocks.bootstrap }));
vi.mock("../lib/api/requests", () => ({ publicAnonymousRequest: mocks.platform }));
vi.mock("../lib/api/sessionTokens", () => ({ hasSessionIdentity: () => false }));
vi.mock("../lib/telemetry/sessionFence", () => ({ browserIdentity: () => "anonymous", subscribeBrowserIdentity: () => () => {}, resolveBrowserIdentity: vi.fn(), markAuthPresent: vi.fn() }));
vi.mock("../lib/telemetry/runtime", () => ({ updateWebTelemetry: mocks.update, stopWebTelemetry: mocks.stop }));
vi.mock("./TelemetryConsent", () => ({ TelemetryConsent: ({ onChange }: { onChange: (x: object) => void }) => <button onClick={() => onChange({ analytics: true, replay: false, diagnostics: false })}>Consent</button> }));
import { WebTelemetry } from "./WebTelemetry";

/** Decision 263 addendum: a space page uses that space's provider only; platform pages the platform's. */
const config = (siteId: string) => ({ pageview: { provider: "ga4", site_id: siteId, endpoint: "" }, replay: { provider: "none", site_id: "", endpoint: "" }, diagnostics: { sentry: { enabled: false, dsn: "", sample_rate: 1 }, firebase_performance: { enabled: false, sample_rate: 0.1 } }, firebase: { api_key: "", auth_domain: "", project_id: "", app_id: "", messaging_sender_id: "", measurement_id: "", vapid_public_key: "" } });
const alpha = { makerspace: { id: 1, slug: "alpha" }, telemetry: config("G-ALPHA"), telemetry_legacy_allowed: false };
function renderAt(path: string) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[path]}><WebTelemetry /></MemoryRouter></QueryClientProvider>); }
const sentSiteIds = () => mocks.update.mock.calls.map(call => (call[1] as ReturnType<typeof config>).pageview.site_id);

beforeEach(() => { mocks.update.mockReset(); mocks.platform.mockReset(); mocks.bootstrap.mockReset(); mocks.platform.mockResolvedValue({ platform_telemetry: config("G-PLATFORM"), platform_telemetry_legacy_allowed: false }); });

it("uses the space's own provider on its page and never fetches the platform's", async () => {
  mocks.bootstrap.mockReturnValue({ data: alpha });
  renderAt("/m/alpha/events");
  await waitFor(() => expect(mocks.update).toHaveBeenCalled());
  expect(new Set(sentSiteIds())).toEqual(new Set(["G-ALPHA"]));
  expect(mocks.platform).not.toHaveBeenCalled();
});

it("never applies a stale bootstrap of another space while the new space resolves", async () => {
  mocks.bootstrap.mockReturnValue({ data: alpha });
  renderAt("/m/beta/events");
  await new Promise(resolve => setTimeout(resolve, 20));
  expect(mocks.update).not.toHaveBeenCalled();
  expect(mocks.platform).not.toHaveBeenCalled();
});

it("uses only the platform provider on platform pages", async () => {
  mocks.bootstrap.mockReturnValue({ data: undefined });
  renderAt("/about");
  await waitFor(() => expect(mocks.update).toHaveBeenCalled());
  expect(new Set(sentSiteIds())).toEqual(new Set(["G-PLATFORM"]));
});
