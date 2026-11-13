import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Machine, MachineType } from "../machinesApi";
import { MachinesPanel } from "./MachinesPanel";

// Machines audit 0.12.0: the console shows a role ONLY what the server scoped to it, per
// machine type. The server is the authority (types and machines arrive already narrowed);
// these tests pin that the console never widens it: no other type's card, no creation or
// certification controls without TYPE authority, and no per-type settings requests for a
// manager who is not the Space Manager.
const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));
vi.mock("./MachineTypesPanel", () => ({ MachineTypesPanel: () => null }));
vi.mock("./machine/MachineDrawer", () => ({ MachineDrawer: () => null }));

const laser: MachineType = {
  id: 1, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false,
  managing_action: "manage_machines", makerspace: 1, can_create_machine: true,
  capability_config: { metering_unit: "length", requires_booking: false },
};
const cnc: MachineType = { ...laser, id: 3, slug: "cnc", name: "CNC routers" };

function machine(id: number, name: string, type: MachineType): Machine {
  return {
    id, makerspace: 1, machine_type: type, name, location: "Lab", notes: "", status: "idle",
    firmware_version: "", camera_feed_url: "", image_url: null, warranty_status: "unknown",
    is_public: true, is_active: true, usage_hours: "0", can_operate: true, can_edit: true,
    can_delegate: false, can_retire: false, can_unretire: false, can_manage: true,
    created_at: "", updated_at: "",
  };
}

function mount(types: MachineType[], machines: Machine[], props: Partial<React.ComponentProps<typeof MachinesPanel>> = {}, route = "/admin/machines") {
  staffRequest.mockImplementation(async (path: string) => {
    if (!path) return [];
    if (path.endsWith("notification-recipient-rules")) return { scope_options: { machine_types: [], machines: [], categories: [] }, features: [] };
    if (path.endsWith("/machine-types")) return types;
    if (path.includes("/machines?page=")) return { count: machines.length, next: null, results: [] };
    if (path.endsWith("/machines")) return { count: machines.length, next: null, results: machines };
    if (path.endsWith("/job-settings")) return { accepts_job_requests: true, max_open_jobs: null, max_job_minutes: null, runs_unattended: false, file_groups: [], quote_mode: "never", quote_above_amount: null, payment_timing: "after", member_fault_charge: "none" };
    if (path.endsWith("/session-settings")) return { session_max_minutes: 240 };
    return [];
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={[route]}><QueryClientProvider client={client}>
    <MachinesPanel makerspaceId={1} canManage canConfigureMachineTypes={false} maintenanceEnabled={false}
      machineServiceEnabled printingEnabled delegatedRecipientRulesEnabled={false}
      enabledFeatures={["machines.sessions"]} {...props} />
  </QueryClientProvider></MemoryRouter>);
}

const requested = (fragment: string) => staffRequest.mock.calls.some(([path]) => String(path).includes(fragment));

beforeEach(() => { staffRequest.mockReset(); });

describe("Machines console per machine-type scope", () => {
  it("shows a laser-only manager only the laser type the server returned", async () => {
    mount([laser], [machine(1, "Laser One", laser)]);
    expect(await screen.findByText("Laser One", { selector: "strong" })).toBeVisible();
    expect(screen.queryByText("CNC routers")).not.toBeInTheDocument();
    expect(screen.queryByText(/3D printers/)).not.toBeInTheDocument();
  });

  it("a deep link to a type outside the scope falls back to the reachable index", async () => {
    mount([laser, cnc], [machine(1, "Laser One", laser), machine(2, "Router One", cnc)], {}, "/admin/machines/2-3d_printer");
    expect(await screen.findByRole("link", { name: /Laser cutters/ })).toBeVisible();
    expect(screen.getByRole("link", { name: /CNC routers/ })).toBeVisible();
    expect(screen.queryByText(/3D printers/)).not.toBeInTheDocument();
  });

  it("an operator-reachable type gives no creation or certification controls", async () => {
    const operated = { ...cnc, can_create_machine: false };
    mount([operated], [machine(2, "Router One", operated)]);
    expect(await screen.findByText("Router One", { selector: "strong" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Add machine" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Certifications" })).not.toBeInTheDocument();
  });

  it("a type-scoped manager never requests the per-type job or session settings", async () => {
    mount([laser], [machine(1, "Laser One", laser)]);
    fireEvent.click((await screen.findAllByRole("link", { name: /^Settings/ })).at(-1)!);
    await waitFor(() => expect(requested("/machine-types")).toBe(true));
    expect(requested("/job-settings")).toBe(false);
    expect(requested("/session-settings")).toBe(false);
  });

  it("the Space Manager (machine-type configuration) reads that type's job and session settings", async () => {
    mount([laser, cnc], [machine(1, "Laser One", laser)], { canConfigureMachineTypes: true }, "/admin/machines/1-laser/settings");
    await waitFor(() => expect(requested("/machine-types/1/job-settings")).toBe(true));
    expect(requested("/machine-types/1/session-settings")).toBe(true);
    expect(requested("/machine-types/3/job-settings")).toBe(false);
  });
});
