import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MachineType } from "../machinesApi";
import { MachinesPanel } from "./MachinesPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));
vi.mock("./MachineTypesPanel", () => ({ MachineTypesPanel: ({ visible }: { visible: boolean }) => visible ? <p>Type configuration</p> : null }));
vi.mock("./machine/MachineDrawer", () => ({ MachineDrawer: () => null }));

const laser: MachineType = {
  id: 1, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false,
  managing_action: "manage_machines", makerspace: 1, can_create_machine: true,
  capability_config: { metering_unit: "length", requires_booking: false },
};
const lathe: MachineType = { ...laser, id: 2, slug: "lathe", name: "Lathes" };

function Probe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }

function mount(route: string, types: MachineType[] = [laser, lathe]) {
  staffRequest.mockImplementation(async (path: string) => {
    if (path.endsWith("/machine-types")) return types;
    if (path.endsWith("/machines")) return { count: 0, next: null, results: [] };
    return [];
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={[route]}><QueryClientProvider client={client}>
    <MachinesPanel makerspaceId={1} canManage canConfigureMachineTypes maintenanceEnabled={false} machineServiceEnabled={false}
      printingEnabled={false} delegatedRecipientRulesEnabled={false} />
    <Probe />
  </QueryClientProvider></MemoryRouter>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("machine-type views are routed subpaths (0.12.0 row 14)", () => {
  it("links each type tab to its own path and opens Settings by URL", async () => {
    mount("/admin/machines/1-laser");
    const settings = await screen.findByRole("link", { name: "Settings" });
    expect(settings).toHaveAttribute("href", "/admin/machines/1-laser/settings");
    expect(screen.getByRole("link", { name: /^Machines/ })).toHaveAttribute("href", "/admin/machines/1-laser");
    fireEvent.click(settings);
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/admin/machines/1-laser/settings"));
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  });

  it("deep-links straight into a type's Settings view", async () => {
    mount("/admin/machines/1-laser/settings");
    expect(await screen.findByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
  });

  it("redirects an old ?view=settings link to the routed path, keeping other parameters", async () => {
    mount("/admin/machines/1-laser?view=settings&machine=4");
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/admin/machines/1-laser/settings?machine=4"));
  });

  it("routes a sole type shown inline at the index without a type segment", async () => {
    mount("/admin/machines?view=settings", [laser]);
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent(/^\/admin\/machines\/settings$/));
    expect(await screen.findByText("Type configuration")).toBeInTheDocument();
  });

  it("falls back to the machines view for an unknown view segment", async () => {
    mount("/admin/machines/1-laser/whatever");
    expect(await screen.findByRole("link", { name: /^Machines/ })).toHaveAttribute("aria-current", "page");
  });
});
