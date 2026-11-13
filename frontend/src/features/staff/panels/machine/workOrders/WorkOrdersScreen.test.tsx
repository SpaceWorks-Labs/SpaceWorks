import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MachineWorkOrders } from "./MachineWorkOrders";
import { WorkOrdersScreen } from "./WorkOrdersScreen";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", () => ({ staffRequest }));

const order = { id: 11, subject_type: "machine", subject_id: 4, subject_label: "Laser A", title: "Replace belt", description: "Slipping on X.",
  priority: "high", status: "in_progress", takes_machine_down: true, due_on: "2026-11-10", assignee_id: null, resolution: "",
  schedule_id: null, log_id: null, created_at: "2026-11-01T09:00:00Z", updated_at: "2026-11-01T09:00:00Z", started_at: "2026-11-01T10:00:00Z", closed_at: null };
const machine = { id: 4, name: "Laser A", machine_type: { id: 7, name: "Laser cutters" }, makerspace: 1 };
const show = (node: React.ReactNode, entry = "/") => render(<MemoryRouter initialEntries={[entry]}>
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider></MemoryRouter>);

describe("work orders", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequest.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.includes("operator-candidates")) return [{ user_id: 20, username: "sam", display_name: "Sam Lee" }];
      if (init?.method === "POST") return { ...order, id: 12 };
      return [order];
    });
  });

  it("lists open work orders and creates one for a chosen machine", async () => {
    show(<WorkOrdersScreen makerspaceId={1} machines={[machine as never]} onBack={vi.fn()} />);
    expect(await screen.findByText("Replace belt")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/1/work-orders?status=open,in_progress,on_hold");
    fireEvent.click(screen.getAllByRole("button", { name: "New work order" })[0]);
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Machine"), { target: { value: "4" } });
    fireEvent.change(within(dialog).getByLabelText("What needs doing"), { target: { value: "Align mirrors" } });
    fireEvent.change(within(dialog).getByLabelText("Priority"), { target: { value: "urgent" } });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: /Takes the machine down/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Create work order" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/1/work-orders", { method: "POST", body: JSON.stringify({
      subject_type: "machine", subject_id: 4, title: "Align mirrors", description: "", priority: "urgent", due_on: null, takes_machine_down: true }) }));
  });

  it("closes an in-progress order with a resolution, cost and parts note, and assigns staff", async () => {
    show(<WorkOrdersScreen makerspaceId={1} machines={[]} onBack={vi.fn()} />, "/?view=work-orders&work_order=11");
    expect(await screen.findByRole("heading", { name: "Replace belt" })).toBeVisible();
    fireEvent.change(await screen.findByLabelText("Assigned to"), { target: { value: "20" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/work-orders/11/assign", { method: "POST", body: JSON.stringify({ assignee_id: 20 }) }));
    fireEvent.click(screen.getAllByRole("button", { name: "Close work order" })[0]);
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("What was done"), { target: { value: "New belt fitted" } });
    fireEvent.change(within(dialog).getByLabelText(/Cost/), { target: { value: "12.50" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Close work order" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/work-orders/11/status", { method: "POST", body: JSON.stringify({
      status: "done", resolution: "New belt fitted", cost: "12.50", parts_note: "" }) }));
  });

  it("shows a machine's open work orders in its drawer", async () => {
    show(<MachineWorkOrders makerspaceId={1} machineId={4} canCreate />);
    expect(await screen.findByText("Replace belt")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/1/work-orders?status=open,in_progress,on_hold&machine=4");
  });
});
