import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../../areaOverview/allowedTabsContext";
import type { Machine } from "../../machinesApi";
import { StaffListContext } from "../../StaffListContext";
import { MachineRelatedTab } from "./MachineRelatedTab";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const machine = { id: 12, name: "Laser A", machine_type: { id: 3, slug: "laser", name: "Laser" } } as unknown as Machine;
const job = (id: number, machineId: number, status = "in_progress") => ({ id, title: `Job ${id}`, status, requester_name: "Asha",
  created_at: "2026-11-01T10:00:00Z", machine: { id: machineId, name: "M", status: "idle" }, assigned_machine: null });

function show(tabs: string[], modules = ["machine_service"], canManage = true, onJump = vi.fn(), features: string[] = []) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/admin/machines"]}>
      <StaffListContext.Provider value={{ ownerName: "sm", canShare: false, makerspace: { id: 4, enabled_modules: modules, enabled_features: features } }}>
        <AllowedTabsContext.Provider value={tabs}>
          <MachineRelatedTab machine={machine} makerspaceId={4} canManageMachines={canManage} onJump={onJump}
            jumps={[{ key: "Maintenance", label: "Maintenance" }, { key: "Warranty", label: "Warranty" }]} />
        </AllowedTabsContext.Provider>
      </StaffListContext.Provider>
    </MemoryRouter>
  </QueryClientProvider>);
  return onJump;
}

describe("MachineRelatedTab (MC11)", () => {
  beforeEach(() => {
    api.staffRequest.mockReset();
    api.staffRequest.mockImplementation((path: string) => Promise.resolve(path.includes("machine-service")
      ? [job(1, 12), job(2, 99), job(3, 12, "collected")]
      : { count: 1, next: null, previous: null, results: [{ id: 8, machine: 12, title: "Guard left open", status: "reported", occurred_at: "2026-11-02T10:00:00Z" }] }));
  });

  it("lists this machine's jobs and incidents and links into each area the viewer can open", async () => {
    show(["machines", "incidents", "repairs", "tobuy"]);
    expect(await screen.findByText("Job 1")).toBeInTheDocument();
    expect(screen.queryByText("Job 2")).toBeNull();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/machine-service/requests?machine=12", expect.anything());
    const related = screen.getByRole("region", { name: "Related" });
    expect(within(related).getByRole("link", { name: /Service queue/ })).toHaveAttribute("href", "/m/lab/admin/machines/3-laser/queue");
    expect(within(related).getByRole("link", { name: /Machine access/ })).toHaveAttribute("href", "/m/lab/admin/machines/3-laser/access");
    expect(await within(related).findByRole("link", { name: /Incidents/ })).toHaveAttribute("href", "/m/lab/admin/incidents?machine=12");
    expect(within(related).getByRole("link", { name: /To-Buy/ })).toBeInTheDocument();
    expect(within(related).queryByRole("link", { name: /Bookings/ })).toBeNull();
    expect(await screen.findByRole("link", { name: /Guard left open/ })).toHaveAttribute("href", "/m/lab/admin/incidents?incident=8");
  });

  it("never offers an area the viewer cannot open, and skips jobs without the service module", async () => {
    show(["machines"], [], false);
    expect(await screen.findByText("Nothing else is linked to this machine that you can open.")).toBeInTheDocument();
    expect(api.staffRequest).not.toHaveBeenCalledWith(expect.stringContaining("machine-service"), expect.anything());
  });

  it("lists this machine's time bookings read-only for a Machine Manager (MC11)", async () => {
    api.staffRequest.mockImplementation((path: string) => Promise.resolve(path.includes("machine-bookings")
      ? { count: 2, results: [{ id: 70, machine_id: 12, machine_name: "Laser A", member_name: "Ravi", starts_at: "2026-11-12T10:00:00Z", ends_at: "2026-11-12T11:00:00Z", status: "confirmed" },
        { id: 71, machine_id: 99, machine_name: "Other", member_name: "Not here", starts_at: "2026-11-12T10:00:00Z", ends_at: "2026-11-12T11:00:00Z", status: "confirmed" }] }
      : path.includes("machine-service") ? [] : { count: 0, next: null, previous: null, results: [] }));
    show(["machines"], [], true, vi.fn(), ["machines.time_booking"]);
    expect(await screen.findByText("Ravi")).toBeInTheDocument();
    expect(screen.queryByText("Not here")).toBeNull();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/machine-bookings?machine=12", expect.anything());
    expect(screen.queryByRole("button", { name: /cancel|approve/i })).toBeNull();
  });

  it("jumps to the drawer's own tabs", () => {
    const onJump = show([]);
    fireEvent.click(screen.getByRole("button", { name: "Warranty" }));
    expect(onJump).toHaveBeenCalledWith("Warranty");
  });
});
