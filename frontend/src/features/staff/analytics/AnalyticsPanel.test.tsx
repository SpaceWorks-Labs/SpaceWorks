import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getStaffAccess } from "../staffAccess";
import { filterTabsByEnabledModules } from "../staffTabs";
import { AnalyticsPanel } from "./AnalyticsPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const summary = (overrides = {}) => ({
  available: true, reason: "", views_version: 1, configured: true, can_manage: false,
  dashboards: [{ id: 4, title: "Loans" }, { id: 5, title: "Machines" }], ...overrides,
});
const connection = {
  ...summary(), metabase_url: "https://mb.example.org", embed_secret_set: true, show_member_details: false,
  login: { role: "", exists: false, created_at: null, rotated_at: null },
  database: { host: "db", port: 5432, database: "makerspace_manager", schema: "spaceworks_analytics" },
};

function renderPanel(scope: Parameters<typeof AnalyticsPanel>[0]["scope"] = { kind: "space", makerspaceId: 7 }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AnalyticsPanel scope={scope} /></QueryClientProvider>);
}

describe("AnalyticsPanel", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("embeds the signed URL of the first listed dashboard and switches dashboards", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/7/metabase") return summary();
      if (path.endsWith("/dashboards/4/embed")) return { url: "https://mb.example.org/embed/dashboard/a.b.c#x", expires_at: "2026-11-05T00:10:00Z" };
      if (path.endsWith("/dashboards/5/embed")) return { url: "https://mb.example.org/embed/dashboard/d.e.f#x", expires_at: "2026-11-05T00:10:00Z" };
      throw new Error(path);
    });
    renderPanel();
    const frame = await screen.findByTitle("Loans");
    expect(frame.getAttribute("src")).toContain("/embed/dashboard/a.b.c");
    fireEvent.click(screen.getByRole("tab", { name: "Machines" }));
    await waitFor(() => expect(screen.getByTitle("Machines").getAttribute("src")).toContain("d.e.f"));
    expect(screen.queryByRole("button", { name: "Connection settings" })).toBeNull();
  });

  it("tells a viewer to ask the Space Manager when nothing is connected", async () => {
    staffRequest.mockResolvedValue(summary({ configured: false, dashboards: [] }));
    renderPanel();
    expect(await screen.findByText(/Ask your Space Manager to connect Metabase/)).toBeTruthy();
  });

  it("shows the password once after creating the login, and never the embed secret", async () => {
    staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/admin/makerspaces/7/metabase") return summary({ can_manage: true, configured: false, dashboards: [] });
      if (path.endsWith("/connection")) return connection;
      if (path.endsWith("/login") && options?.method === "POST") {
        return { role: "sw_an_abcd1234_s7_a1b2c3", password: "once-only-password", host: "db", port: 5432, database: "m", schema: "spaceworks_analytics" };
      }
      throw new Error(path);
    });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Connection settings" }));
    fireEvent.click(await screen.findByRole("button", { name: "Create login" }));
    expect(await screen.findByText(/once-only-password/)).toBeTruthy();
    expect(screen.queryByDisplayValue(/s{20,}/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(screen.queryByText(/once-only-password/)).toBeNull();
  });

  it("explains a hosting that cannot create logins", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/7/metabase") return summary({ can_manage: true });
      if (path.endsWith("/connection")) return { ...connection, available: false, reason: "not_available_on_hosting" };
      if (path.includes("/embed")) return { url: "https://mb.example.org/embed/dashboard/a.b.c", expires_at: "2026-11-05T00:10:00Z" };
      throw new Error(path);
    });
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Connection settings" }));
    expect(await screen.findByText(/Not available on this hosting/)).toBeTruthy();
  });

  it("uses the platform routes for the platform scope", async () => {
    staffRequest.mockResolvedValue(summary({ configured: false, dashboards: [] }));
    renderPanel({ kind: "platform" });
    await screen.findByText("Platform analytics");
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/metabase");
  });
});

describe("analytics tab gating", () => {
  const space = { enabled_modules: ["analytics"], enabled_features: [], unavailable_apps: [] };

  it("needs view_analytics (or manage_makerspace) and the analytics module", () => {
    expect(getStaffAccess(["view_analytics"], false, false).allowedTabs).toContain("analytics");
    expect(getStaffAccess(["view_inventory"], false, false).allowedTabs).not.toContain("analytics");
    const allowed = getStaffAccess(["manage_makerspace"], false, false).allowedTabs;
    expect(filterTabsByEnabledModules(allowed, space as never)).toContain("analytics");
    expect(filterTabsByEnabledModules(allowed, { ...space, enabled_modules: [] } as never)).not.toContain("analytics");
  });

  it("keeps the platform analytics tab for the superadmin on the central console", () => {
    expect(getStaffAccess([], true, false).allowedTabs).toContain("platform-analytics");
    expect(getStaffAccess([], true, true).allowedTabs).not.toContain("platform-analytics");
    expect(getStaffAccess(["manage_makerspace"], false, false).allowedTabs).not.toContain("platform-analytics");
  });
});
