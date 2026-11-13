import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../../../test/axe";
import type { MachineType } from "../../machinesApi";
import { MachineServiceConsole } from "./MachineServiceConsole";
import { PrinterServiceConsole } from "./PrinterServiceConsole";
import { blankServiceDraft, type ServiceDraft } from "./serviceDrafts";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const eta = { calculated_at: "2026-10-18T10:00:00Z", estimated_start_at: "2026-10-18T10:50:00Z",
  estimated_finish_at: "2026-10-18T11:05:00Z", start_in_minutes: 50, finish_in_minutes: 65, confidence: "estimated",
  reasons: [], approved_ahead: 2, awaiting_review_ahead: 0, active_machine_count: 2, missing_estimate_count: 0 };
let rows: Record<string, unknown>[] = [];

beforeEach(() => {
  staffRequest.mockReset();
  rows = [{ id: 4, title: "Laser job", requester_name: "Ada", status: "accepted", planned_quantity: "20",
    planned_grams: "20", actual_consumed_quantity: "0", eta }];
  staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (options?.method === "POST" && path.endsWith("/cancel")) {
      rows = [{ ...rows[0], status: "cancelled", eta: null }];
      return rows[0];
    }
    if (path.includes("machine-service/requests")) return rows;
    if (path.includes("machine-service-report")) return { printer_metrics: [] };
    return [];
  });
});

const laser: MachineType = { id: 7, slug: "laser", name: "Laser cutters", icon: "", is_builtin: false,
  managing_action: "manage_machines", makerspace: 1, capability_config: { metering_unit: "length", requires_booking: false } };
const printer = { id: 1, slug: "3d_printer", name: "3D Printer", icon: "", is_builtin: true, managing_action: "", makerspace: null,
  capability_config: { metering_unit: "weight" as const, requires_booking: false } };

function Stateful({ kind }: { kind: "generic" | "printer" }) {
  const [draft, setDraftState] = useState<ServiceDraft>(blankServiceDraft());
  const setDraft = (update: (draft: ServiceDraft) => ServiceDraft) => setDraftState(update);
  return kind === "generic"
    ? <MachineServiceConsole makerspaceId={1} canManage machineType={laser} machines={[]} pools={[]} draft={draft} setDraft={setDraft} />
    : <PrinterServiceConsole makerspaceId={1} canManage printingEnabled machineType={printer} machines={[]} pools={[]} draft={draft} setDraft={setDraft} />;
}

describe.each(["generic", "printer"] as const)("%s staff console", (kind) => {
  it("shows the server ETA in the row and cancels through a confirmation, then refetches", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(<QueryClientProvider client={client}><Stateful kind={kind} /></QueryClientProvider>);
    expect(await screen.findByText("Laser job")).toBeVisible();
    expect(screen.getByText(/Starts in about 50 min/)).toBeInTheDocument();
    await expectNoA11yViolations(container);
    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Cancel job" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/returns any reserved material to its pool, charges nothing/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Keep job" })).toBeVisible();
    expect(within(dialog).queryByRole("button", { name: "Confirm" })).toBeNull();
    const confirm = within(dialog).getByRole("button", { name: "Cancel job" });
    expect(confirm).toHaveClass("desk-button-danger");
    fireEvent.click(confirm);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/4/cancel",
      expect.objectContaining({ method: "POST", body: "{}" })));
    await waitFor(() => expect(screen.queryByText(/Starts in about 50 min/)).toBeNull());
  });
});

describe.each(["generic", "printer"] as const)("%s staff console running cancel (decision 61a)", (kind) => {
  it("pre-fills the material used so far and sends the confirmed amount", async () => {
    const started = new Date(Date.now() - 30 * 60000).toISOString();
    rows = [{ id: 4, title: "Laser job", requester_name: "Ada", status: "in_progress", started_at: started,
      estimated_minutes: 60, planned_quantity: "20", planned_grams: "20", reserved_quantity: "20", reserved_grams: "20",
      actual_consumed_quantity: null, eta: null }];
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><Stateful kind={kind} /></QueryClientProvider>);
    expect(await screen.findByText("Laser job")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "More actions" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "Cancel job" }));
    const dialog = await screen.findByRole("dialog");
    const field = within(dialog).getByLabelText(/Material used so far .*0 to 20/) as HTMLInputElement;
    expect(Number(field.value)).toBeGreaterThan(9.5);
    expect(Number(field.value)).toBeLessThanOrEqual(10.5);
    fireEvent.change(field, { target: { value: "7.5" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel job" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-service/requests/4/cancel",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ consumed_quantity: "7.5" }) })));
  });
});
