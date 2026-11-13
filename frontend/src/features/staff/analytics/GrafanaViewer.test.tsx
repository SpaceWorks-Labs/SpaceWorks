import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GrafanaViewer } from "./GrafanaViewer";
import { AnalyticsPanel } from "./AnalyticsPanel";

const { staffRequest, staffRequestBlob } = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest, staffRequestBlob };
});

const summary = {
  provider: "grafana", configured: true, can_manage: false, views_version: 3,
  dashboards: [{ uid: "inv", title: "Inventory", mode: "public" }, { uid: "mach", title: "Machines", mode: "render" }],
};
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe("GrafanaViewer", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequestBlob.mockReset();
    URL.createObjectURL = vi.fn(() => "blob:render-1");
    URL.revokeObjectURL = vi.fn();
  });

  it("frames a public dashboard and draws a rendered one as an image", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/7/grafana") return summary;
      if (path === "/admin/makerspaces/7/grafana/dashboards/inv/embed") {
        return { mode: "public", url: "https://grafana.example.org/public-dashboards/abc" };
      }
      throw new Error(path);
    });
    staffRequestBlob.mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    const view = render(<QueryClientProvider client={client()}><GrafanaViewer scope={{ kind: "space", makerspaceId: 7 }} /></QueryClientProvider>);
    const frame = await screen.findByTitle("Inventory");
    expect(frame.getAttribute("src")).toBe("https://grafana.example.org/public-dashboards/abc");
    expect(frame.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(frame.getAttribute("sandbox")).toContain("allow-scripts");
    fireEvent.click(screen.getByRole("tab", { name: "Machines" }));
    const image = await screen.findByRole("img", { name: "Machines" });
    expect(image.getAttribute("src")).toBe("blob:render-1");
    expect(staffRequestBlob).toHaveBeenCalledWith("/admin/makerspaces/7/grafana/dashboards/mach/render?width=1600&height=900&theme=light");
    fireEvent.click(screen.getByRole("button", { name: "Refresh image" }));
    await waitFor(() => expect(staffRequestBlob).toHaveBeenCalledTimes(2));
    view.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:render-1");
  });

  it("uses the platform routes for the platform scope", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/platform/grafana") return { ...summary, dashboards: [summary.dashboards[0]] };
      if (path === "/admin/platform/grafana/dashboards/inv/embed") return { mode: "public", url: "https://g.example.org/public-dashboards/p" };
      throw new Error(path);
    });
    render(<QueryClientProvider client={client()}><GrafanaViewer scope={{ kind: "platform" }} /></QueryClientProvider>);
    expect((await screen.findByTitle("Inventory")).getAttribute("src")).toBe("https://g.example.org/public-dashboards/p");
  });

  it("shows the typed refusal when a dashboard cannot open", async () => {
    const { StructuredApiError } = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/7/grafana") return { ...summary, dashboards: [summary.dashboards[0]] };
      throw new StructuredApiError(409, { code: "grafana_not_configured", detail: "Grafana is not connected yet." });
    });
    render(<QueryClientProvider client={client()}><GrafanaViewer scope={{ kind: "space", makerspaceId: 7 }} /></QueryClientProvider>);
    expect(await screen.findByText(/This dashboard could not open/)).toBeTruthy();
    expect(screen.getByText(/Grafana is not connected yet/)).toBeTruthy();
  });

  it("is shown beside Metabase only when the chosen tool includes Grafana", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path === "/admin/makerspaces/7/metabase") {
        return { available: true, reason: "", views_version: 3, configured: false, can_manage: false, dashboards: [], provider: "metabase" };
      }
      throw new Error(path);
    });
    render(<QueryClientProvider client={client()}><AnalyticsPanel scope={{ kind: "space", makerspaceId: 7 }} /></QueryClientProvider>);
    expect(await screen.findByText(/Ask your Space Manager to connect Metabase/)).toBeTruthy();
    expect(staffRequest.mock.calls.some(([path]) => String(path).includes("/grafana"))).toBe(false);
  });
});
