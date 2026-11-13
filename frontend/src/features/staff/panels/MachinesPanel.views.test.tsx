import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MachineType } from "../machinesApi";
import { MachinesPanel } from "./MachinesPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));
vi.mock("./MachineTypesPanel", () => ({ MachineTypesPanel: () => null }));
vi.mock("./machine/MachineDrawer", () => ({ MachineDrawer: () => null }));

const laser: MachineType = {
  id: 1, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false,
  managing_action: "manage_machines", makerspace: 1, can_create_machine: true,
  capability_config: { metering_unit: "length", requires_booking: false },
};
const lathe: MachineType = { ...laser, id: 2, slug: "lathe", name: "Lathes" };

function Probe() { const location = useLocation(); return <output data-testid="location">{location.pathname}{location.search}</output>; }

function mount(route: string, { service = true, sessions = true } = {}) {
  staffRequest.mockImplementation(async (raw?: string) => { const path = String(raw);
    if (path.endsWith("/machine-types")) return [laser, lathe];
    if (path.endsWith("/machines") || path.includes("saved-views") || path.includes("machine-sessions")) return { count: 0, next: null, previous: null, results: [] };
    return [];
  });
  return render(<MemoryRouter initialEntries={[route]}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MachinesPanel makerspaceId={1} canManage canConfigureMachineTypes maintenanceEnabled={false} machineServiceEnabled={service}
      printingEnabled={false} delegatedRecipientRulesEnabled={false} enabledFeatures={sessions ? ["machines.sessions"] : []} />
    <Probe />
  </QueryClientProvider></MemoryRouter>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("Machines index views (A15/A16)", () => {
  it("opens All jobs from ?view=jobs when the service queue is on", async () => {
    mount("/admin/machines?view=jobs");
    expect(await screen.findByRole("heading", { name: "All jobs" })).toBeVisible();
  });

  it("does not offer All jobs while the service queue is off", async () => {
    mount("/admin/machines?view=jobs", { service: false });
    expect(await screen.findByRole("heading", { name: "Machines" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "All jobs" })).toBeNull();
  });

  it("opens Sessions narrowed to the type from the type page", async () => {
    mount("/admin/machines/1-laser");
    fireEvent.click(await screen.findByRole("button", { name: /more/i }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Sessions" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("view=sessions&s_machine_type=1"));
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("machine-sessions?") && String(path).includes("machine_type=1"))).toBe(true));
  });
});
