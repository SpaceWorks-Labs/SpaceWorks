import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MachineType } from "../../machinesApi";
import { JobBoard } from "./JobBoard";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const type = { id: 7, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false, managing_action: "manage_machines", makerspace: 1,
  capability_config: { metering_unit: "minutes", requires_booking: false } } as MachineType;
const base = { queue_id: 1, requester: { id: 50, username: "ana", display: "Ana" }, requester_name: "Ana", estimated_minutes: 30, eta: null, payment: null };
const job = (id: number, title: string, status: string, extra: object = {}) => ({ ...base, id, title, status, created_at: `2026-11-01T1${id}:00:00Z`, queued_at: `2026-11-01T1${id}:00:00Z`, ...extra });
const board = {
  machine_type_id: 7,
  lanes: [{ machine_id: 3, machine_name: "Laser A", status: "idle", locked_out: true, running: [], assigned: [] }],
  queue: [job(1, "Coasters", "accepted"), job(2, "Box lid", "accepted")],
  review: [job(3, "Sign", "pending")],
  waiting_on_member: [job(4, "Lamp", "changes_requested", { changes_code: "wrong_format" })],
  ready: [job(5, "Keyrings", "completed")],
  overdue_pickup_ids: [5], no_show_member_ids: [50],
};
const coded = (message: string, code: string) => Object.assign(new Error(message), { code, status: 409 });

function renderBoard(batchEnabled = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><JobBoard makerspaceId={1} machineType={type} batchEnabled={batchEnabled} pools={[]}
    machines={[{ id: 3, name: "Laser A", makerspace: 1, machine_type: type, status: "idle", is_active: true } as never]} /></QueryClientProvider>);
}

describe("JobBoard", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequest.mockImplementation(async (path: string) => path.includes("/board?") ? board : {});
  });

  it("lays out lanes, queue, review, waiting and ready with their flags", async () => {
    renderBoard();
    expect(await screen.findByRole("heading", { name: "Laser A" })).toBeVisible();
    expect(screen.getByText("Locked out: maintenance overdue")).toBeVisible();
    expect(screen.getByRole("heading", { name: /To review/ })).toBeVisible();
    expect(screen.getByText("Needs changes")).toBeVisible();
    expect(screen.getByText("Wrong file format")).toBeVisible();
    expect(screen.getByText("Waiting over 14 days")).toBeVisible();
    expect(screen.getAllByText("Member has missed pickups before").length).toBeGreaterThan(0);
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/1/machine-service/board?machine_type_id=7");
  });

  it("reorders with accessible move buttons", async () => {
    renderBoard();
    fireEvent.click(await screen.findByRole("button", { name: "Move Box lid up" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/2/reorder", { method: "POST", body: JSON.stringify({ position: 1 }) }));
    expect(screen.getByRole("button", { name: "Move Coasters up" })).toBeDisabled();
  });

  it("turns Accept into Send quote when the type needs a quote", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path.includes("/board?")) return board;
      if (path.endsWith("/accept")) throw coded("Send a quote instead.", "quote_required");
      return {};
    });
    renderBoard();
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Accept job" }));
    expect(await screen.findByRole("heading", { name: /Send quote: Sign/ })).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(/needs a quote/);
    fireEvent.click(screen.getByRole("button", { name: "Send quote" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/3/quote", expect.objectContaining({ method: "POST" })));
  });

  it("explains a payment-due refusal at pickup", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path.includes("/board?")) return board;
      if (path.endsWith("/collect")) throw coded("Charge must be settled.", "payment_due");
      return {};
    });
    renderBoard();
    fireEvent.click(await screen.findByRole("button", { name: "Collect" }));
    fireEvent.change(screen.getByLabelText(/Pickup code/), { target: { value: "AB12" } });
    fireEvent.click(screen.getByRole("button", { name: "Mark collected" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/must be paid before pickup/);
    expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/5/collect", { method: "POST", body: JSON.stringify({ pickup_code: "AB12", collector_name: "" }) });
  });

  it("starts a batch from two selected queued jobs", async () => {
    renderBoard(true);
    fireEvent.click(await screen.findByRole("checkbox", { name: "Select Coasters for a batch" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Box lid for a batch" }));
    fireEvent.click(screen.getByRole("button", { name: "Start as batch" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getAllByText(/50% of the run/)).toHaveLength(2);
    fireEvent.change(within(dialog).getByLabelText("Machine"), { target: { value: "3" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Start batch" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/1/machine-service/batches", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(staffRequest.mock.calls.find(([path]) => String(path).endsWith("/batches"))![1].body);
    expect(body).toMatchObject({ job_ids: [1, 2], machine_id: 3, plans: { 1: { estimated_minutes: 30 }, 2: { estimated_minutes: 30 } } });
  });
});
