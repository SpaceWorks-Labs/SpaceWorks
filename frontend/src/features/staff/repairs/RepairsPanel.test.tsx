import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../../test/axe";
import { RepairsPanel } from "./RepairsPanel";
import type { IssueDetail } from "./repairsApi";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest: api.staffRequest }));

const space = { id: 4, name: "Lab", slug: "lab", enabled_modules: ["machines", "bookings"],
  enabled_features: ["machines.repairs", "machines.maintenance", "machines.issue_reporting"] } as never;
const issue = (overrides: Partial<IssueDetail> = {}): IssueDetail => ({
  id: 9, area: "machines", subject_type: "machine", subject_id: 2, subject_label: "Laser A", source: "machine_job",
  title: "Lens cracked", state: "assigned", priority: "high", quote_state: "none", reporter_name: "Asha", assignees: [],
  work_order_id: 3, created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z", fixed_at: null, closed_at: null,
  description: "Cracked after a job.", resolution: "", reporter_email: "", quote_amount: null, quote_currency: "",
  quote_note: "", quote_contact_id: null, payout_entry_id: null, reporter_notified_at: null, events: [], photos: [],
  dispatches: [], parts: [], viewer_role: "technician", default_contact_ids: [], ...overrides,
});

function show(actions: string[], path = "/") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><RepairsPanel makerspace={space} actions={actions} /></MemoryRouter></QueryClientProvider>);
}

describe("RepairsPanel", () => {
  beforeEach(() => { api.staffRequest.mockReset(); });

  it("gives a Technician My jobs and the maintenance due, never the queue or the directory", async () => {
    api.staffRequest.mockImplementation((path: string) => Promise.resolve(String(path).includes("my-maintenance")
      ? { machine_schedules: [], schedules: [] } : { count: 1, next: null, previous: null, results: [issue()] }));
    const { container } = show(["work_repairs", "run_maintenance", "set_service_state"]);
    expect(await screen.findByText("Lens cracked")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "My jobs" })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "Queue" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Technicians" })).toBeNull();
    expect(screen.getByRole("radio", { name: "Maintenance" })).toBeInTheDocument();
    expect(api.staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4/my-jobs?page=1");
    await expectNoA11yViolations(container);
  });

  it("gives a manager the queue with a new-job action", async () => {
    api.staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    show(["manage_machines"]);
    expect(await screen.findByRole("heading", { name: "Repairs" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New repair job" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Technicians" })).toBeInTheDocument();
  });

  it("shows a Technician the reporter's first name and the steps they may take", async () => {
    api.staffRequest.mockResolvedValue(issue());
    show(["work_repairs"], "/?issue=9");
    expect(await screen.findByText(/Reported by Asha/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start work" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start work" }));
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalledWith("/admin/issues/9/start", expect.objectContaining({ method: "POST" })));
  });
});
