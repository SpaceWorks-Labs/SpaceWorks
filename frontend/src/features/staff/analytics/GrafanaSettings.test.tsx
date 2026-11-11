import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnalyticsPanel } from "./AnalyticsPanel";

const { staffRequest, staffRequestBlob } = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest, staffRequestBlob };
});

type Scope = Parameters<typeof AnalyticsPanel>[0]["scope"];
const database = { host: "db", port: 5432, database: "m", schema: "spaceworks_analytics" };
const metabaseSummary = (provider: string, can_manage = true) => ({
  available: true, reason: "", views_version: 3, configured: false, can_manage, dashboards: [], provider,
});
const metabaseConnection = (provider: string) => ({
  ...metabaseSummary(provider), metabase_url: "", embed_secret_set: false, show_member_details: false,
  login: { role: "", exists: false, created_at: null, rotated_at: null }, database,
});
const grafanaConnection = {
  provider: "grafana", grafana_url: "https://grafana.example.org", token_set: true, token_updated_at: "2026-11-11T00:00:00Z",
  org_id: 2, dashboards: [{ uid: "inv", title: "Inventory", mode: "public", public_token: "a".repeat(32) }],
  login_role: "sw_an_x_s7_abcdef", database, private_hosts_allowed: false,
};
const grafanaSummary = { provider: "grafana", configured: false, dashboards: [], can_manage: true, views_version: 3 };

function mockApi(base: string, provider = "grafana") {
  staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    const method = options?.method ?? "GET";
    if (path === base.replace("grafana", "metabase")) return metabaseSummary(provider);
    if (path === `${base.replace("grafana", "metabase")}/connection`) return metabaseConnection(provider);
    if (path.endsWith("/telemetry")) throw new Error("telemetry not under test");
    if (path === "/admin/platform/firebase-web-settings") return { configured: false, config: null };
    if (path === base) return grafanaSummary;
    if (path === `${base}/connection`) return method === "PATCH" ? { ...grafanaConnection, ...JSON.parse(String(options?.body)) } : grafanaConnection;
    if (path === `${base}/token`) return method === "DELETE" ? undefined : grafanaConnection;
    if (path === `${base}/test`) {
      return { ok: false, version: "11.3.0", dashboards_found: null, checks: [
        { name: "health", ok: true, detail: "" }, { name: "search", ok: false, detail: "The token was refused." }] };
    }
    throw new Error(`${method} ${path}`);
  });
}

function renderPanel(scope: Scope) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AnalyticsPanel scope={scope} /></QueryClientProvider>);
}

async function openSettings(scope: Scope) {
  renderPanel(scope);
  fireEvent.click(await screen.findByRole("button", { name: "Connection settings" }));
  return screen.findByRole("form", { name: "Grafana connection" });
}

describe("GrafanaSettings", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequestBlob.mockReset();
    URL.createObjectURL = vi.fn(() => "blob:bundle");
    URL.revokeObjectURL = vi.fn();
  });

  it("saves the dashboard tool choice through the Grafana connection", async () => {
    mockApi("/admin/makerspaces/7/grafana");
    await openSettings({ kind: "space", makerspaceId: 7 });
    expect(screen.queryByRole("form", { name: "Metabase connection" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: /Both/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/grafana/connection",
      { method: "PATCH", body: JSON.stringify({ provider: "both" }) }));
  });

  it("never prefills the token, replaces it write-only and confirms removal", async () => {
    mockApi("/admin/makerspaces/7/grafana");
    await openSettings({ kind: "space", makerspaceId: 7 });
    const tokenForm = screen.getByRole("form", { name: "Grafana service-account token" });
    const input = within(tokenForm).getByLabelText(/Service-account token/) as HTMLInputElement;
    expect(input.value).toBe("");
    expect(input.type).toBe("password");
    fireEvent.change(input, { target: { value: "glsa_new" } });
    fireEvent.click(within(tokenForm).getByRole("button", { name: "Replace token" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/grafana/token",
      { method: "POST", body: JSON.stringify({ token: "glsa_new" }) }));
    await waitFor(() => expect(input.value).toBe(""));
    fireEvent.click(within(tokenForm).getByRole("button", { name: "Remove token" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/grafana/token", { method: "DELETE" }));
  });

  it("saves the URL, organization and dashboards", async () => {
    mockApi("/admin/makerspaces/7/grafana");
    const form = await openSettings({ kind: "space", makerspaceId: 7 });
    expect((within(form).getByLabelText(/Grafana dashboard 1 public access token/) as HTMLInputElement).value).toBe("a".repeat(32));
    fireEvent.change(within(form).getByLabelText(/Grafana dashboard 1 display/), { target: { value: "render" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save Grafana connection" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/grafana/connection", {
      method: "PATCH", body: JSON.stringify({ grafana_url: "https://grafana.example.org", org_id: 2,
        dashboards: [{ uid: "inv", title: "Inventory", mode: "render", public_token: "" }] }),
    }));
  });

  it("shows each connection check and downloads the bundle as a zip", async () => {
    mockApi("/admin/makerspaces/7/grafana");
    staffRequestBlob.mockResolvedValue(new Blob(["zip"]));
    await openSettings({ kind: "space", makerspaceId: 7 });
    fireEvent.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText(/Grafana is not working yet/)).toBeTruthy();
    expect(screen.getByText(/The token was refused/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Download provisioning bundle" }));
    await waitFor(() => expect(staffRequestBlob).toHaveBeenCalledWith("/admin/makerspaces/7/grafana/bundle?archive=zip"));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:bundle");
  });

  it("uses the platform routes for the platform scope", async () => {
    mockApi("/admin/platform/grafana");
    await openSettings({ kind: "platform" });
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/grafana/connection");
    expect(staffRequest.mock.calls.some(([path]) => String(path).includes("/makerspaces/"))).toBe(false);
  });

  it("gives a viewer no settings", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/7/metabase") return metabaseSummary("grafana", false);
      if (path === "/admin/makerspaces/7/grafana") return { ...grafanaSummary, can_manage: false };
      throw new Error(path);
    });
    renderPanel({ kind: "space", makerspaceId: 7 });
    expect(await screen.findByText(/Ask your Space Manager to connect Grafana/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Connection settings" })).toBeNull();
    expect(staffRequest.mock.calls.some(([path]) => String(path).endsWith("/connection"))).toBe(false);
  });
});
