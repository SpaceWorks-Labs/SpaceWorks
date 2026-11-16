import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createEvent, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MachineType } from "../../machinesApi";
import { dropPosition } from "./boardOrder";
import { JobBoard } from "./JobBoard";
import type { JobBoard as Board, StaffJob } from "./machineJobsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const type = { id: 7, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false, managing_action: "manage_machines", makerspace: 1,
  capability_config: { metering_unit: "minutes", requires_booking: false } } as MachineType;
const file = (id: number, name: string) => ({ id, kind: "model", original_filename: name, content_type: "", size_bytes: 2048,
  created_at: "2026-11-01T10:00:00Z", attached_at: "2026-11-01T10:00:00Z" });
const job = (id: number, title: string, extra: object = {}) => ({ queue_id: 1, requester: { id: 50, username: "ana", display: "Ana" },
  requester_name: "Ana", estimated_minutes: 30, eta: null, payment: null, status: "accepted", urgent: false, files: [],
  created_at: `2026-11-01T1${id}:00:00Z`, queued_at: `2026-11-01T1${id}:00:00Z`, id, title, ...extra });
const board = {
  machine_type_id: 7, lanes: [], review: [], waiting_on_member: [], ready: [], overdue_pickup_ids: [], no_show_member_ids: [],
  queue: [job(1, "Coasters", { at_risk_reasons: ["eta_after_needed_by"], needed_by: "2026-11-02" }), job(2, "Box lid"),
    job(3, "Sign", { files: [file(9, "part.stl"), file(10, "notes.pdf")] })],
};

function renderBoard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><JobBoard makerspaceId={1} machineType={type} batchEnabled={false} pools={[]}
    machines={[]} /></QueryClientProvider>);
}

function dataTransfer() {
  const store: Record<string, string> = {};
  return { effectAllowed: "", dropEffect: "", setData: (k: string, v: string) => { store[k] = v; }, getData: (k: string) => store[k] };
}

const card = (title: string) => screen.getByRole("heading", { name: title }).closest("li")!;

describe("JobBoard (GAP2 M3-M5)", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequest.mockImplementation(async (path: string) => path.includes("/board?") ? board : {});
  });

  it("flags a job that may miss its needed-by date", async () => {
    renderBoard();
    expect(await screen.findByText("At risk: finishes after its needed-by date")).toBeVisible();
    expect(within(card("Box lid")).queryByText(/At risk/)).toBeNull();
  });

  it("drags a job onto another to reorder it through the same endpoint, and announces it", async () => {
    renderBoard();
    await screen.findByRole("heading", { name: "Sign" });
    expect(screen.getByText("Drag a job to reorder the queue, or use its move buttons.")).toBeVisible();
    const transfer = dataTransfer();
    fireEvent.dragStart(card("Sign"), { dataTransfer: transfer });
    const over = createEvent.dragOver(card("Coasters"), { dataTransfer: transfer });
    fireEvent(card("Coasters"), over);
    expect(over.defaultPrevented).toBe(true);
    fireEvent.drop(card("Coasters"), { dataTransfer: transfer });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/3/reorder",
      { method: "POST", body: JSON.stringify({ position: 1 }) }));
    expect(screen.getByText("Moved Sign to place 1 in the queue.")).toBeInTheDocument();
  });

  it("keeps the move buttons as the keyboard way to reorder", async () => {
    renderBoard();
    fireEvent.click(await screen.findByRole("button", { name: "Move Box lid down" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/2/reorder",
      { method: "POST", body: JSON.stringify({ position: 3 }) }));
  });

  it("opens a job's files with a preview only for the safe formats", async () => {
    renderBoard();
    await screen.findByRole("heading", { name: "Sign" });
    fireEvent.click(within(card("Sign")).getByRole("button", { name: "More actions" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Files (2)" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("part.stl")).toBeVisible();
    expect(within(dialog).getAllByRole("button", { name: "Download" })).toHaveLength(2);
    expect(within(dialog).getAllByRole("button", { name: "Load preview" })).toHaveLength(1);
    expect(within(dialog).getByText("3D model")).toBeVisible();
  });
});

describe("dropPosition", () => {
  const rows = [job(1, "A"), job(2, "B"), job(3, "C"), job(4, "Urgent", { urgent: true })] as unknown as StaffJob[];
  const data = { ...board, queue: rows, lanes: [] } as unknown as Board;
  it("lands before a target above and after a target below", () => {
    expect(dropPosition(rows[2], rows[0], rows, data)).toBe(1);
    expect(dropPosition(rows[0], rows[2], rows, data)).toBe(3);
    expect(dropPosition(rows[0], rows[1], rows, data)).toBe(2);
  });
  it("refuses itself and a job of another urgency", () => {
    expect(dropPosition(rows[0], rows[0], rows, data)).toBeNull();
    expect(dropPosition(rows[0], rows[3], rows, data)).toBeNull();
  });
});
