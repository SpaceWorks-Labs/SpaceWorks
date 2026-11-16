import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../../areaOverview/allowedTabsContext";
import { IssueQueue } from "../../repairs/IssueQueue";
import { IssueRecord } from "../../repairs/IssueRecord";
import type { IssueDetail } from "../../repairs/repairsApi";
import { sessionFilterQuery } from "./sessions/SessionFilters";
import { SessionsScreen } from "./sessions/SessionsScreen";
import { WorkOrdersScreen } from "./workOrders/WorkOrdersScreen";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const empty = { count: 0, next: null, previous: null, results: [] };
const machines = [{ id: 4, name: "Laser A", machine_type: { id: 7, name: "Laser cutters" }, is_active: true }] as never[];
const calls = () => staffRequest.mock.calls.map(([path]) => String(path));
function show(node: React.ReactNode, entry: string, tabs: string[] = []) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[entry]}><AllowedTabsContext.Provider value={tabs}>{node}</AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string) => String(path).includes("work-orders") ? [] : empty);
});

describe("sessions filters (A16) and saved views (A17)", () => {
  it("sends machine type, source and dates from the URL and loads saved views", async () => {
    show(<SessionsScreen makerspaceId={1} machines={machines} onBack={vi.fn()} />,
      "/admin/machines?view=sessions&s_machine_type=7&s_source=device&s_since=2026-11-01");
    await waitFor(() => expect(calls().some(path => path.startsWith("/admin/makerspaces/1/machine-sessions?")
      && path.includes("machine_type=7") && path.includes("source=device") && path.includes("since=2026-11-01"))).toBe(true));
    expect(calls()).toContain("/admin/makerspaces/1/saved-views?entity=machine_sessions&page=1");
    expect(await screen.findByText("No sessions match these filters. Clear filters to see them all.")).toBeVisible();
  });

  it("never sends presentation keys to the API", () => {
    expect(sessionFilterQuery({ machine: "4", columns: "a", density: "compact", member: "" })).toBe("machine=4");
  });
});

describe("work orders machine filter (A16)", () => {
  it("narrows the list on the server and offers saved views", async () => {
    show(<WorkOrdersScreen makerspaceId={1} machines={machines} onBack={vi.fn()} />, "/admin/machines?view=work-orders&wo_machine=4");
    await waitFor(() => expect(calls()).toContain("/admin/makerspaces/1/work-orders?status=open,in_progress,on_hold&machine=4"));
    expect(calls()).toContain("/admin/makerspaces/1/saved-views?entity=work_orders&page=1");
  });

  it("ignores a machine id that is not a number", async () => {
    show(<WorkOrdersScreen makerspaceId={1} machines={machines} onBack={vi.fn()} />, "/admin/machines?view=work-orders&wo_machine=x");
    await waitFor(() => expect(calls()).toContain("/admin/makerspaces/1/work-orders?status=open,in_progress,on_hold"));
  });
});

describe("repairs queue state in the URL (A17)", () => {
  it("restores the tab from rp_state and loads repairs saved views", async () => {
    show(<IssueQueue makerspace={{ id: 3 } as never} mine={false} canOpen={false} onOpen={vi.fn()} />, "/admin/repairs?rp_state=done");
    await waitFor(() => expect(calls()).toContain("/admin/makerspaces/3/issues?state=fixed,closed,rejected&page=1"));
    expect(calls()).toContain("/admin/makerspaces/3/saved-views?entity=repairs&page=1");
  });

  it("shows no saved views on My jobs", async () => {
    show(<IssueQueue makerspace={{ id: 3 } as never} mine canOpen={false} onOpen={vi.fn()} />, "/admin/repairs");
    await waitFor(() => expect(calls()).toContain("/admin/makerspaces/3/my-jobs?page=1"));
    expect(calls().some(path => path.includes("saved-views"))).toBe(false);
  });
});

const issue = { id: 9, area: "machines", subject_type: "machine", subject_id: 2, subject_label: "Laser A", source: "staff", title: "Lens",
  state: "assigned", priority: "normal", quote_state: "none", reporter_name: "", assignees: [], work_order_id: 3,
  created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z", fixed_at: null, closed_at: null, description: "", resolution: "",
  reporter_email: "", quote_amount: null, quote_currency: "", quote_note: "", quote_contact_id: null, payout_entry_id: null,
  reporter_notified_at: null, events: [], photos: [], dispatches: [], parts: [], viewer_role: "manager", default_contact_ids: [] } as IssueDetail;

describe("issue cross-links (A18)", () => {
  it("links the work order and the machine into Machines", () => {
    show(<IssueRecord issue={issue} />, "/m/lab/admin/repairs?issue=9", ["machines"]);
    expect(screen.getByRole("link", { name: "Open work order 3" }))
      .toHaveAttribute("href", "/m/lab/admin/machines?view=work-orders&work_order=3");
    expect(screen.getByRole("link", { name: "Laser A" })).toHaveAttribute("href", "/m/lab/admin/machines?machine=2");
  });

  it("keeps plain text for someone who cannot open Machines", () => {
    show(<IssueRecord issue={issue} />, "/m/lab/admin/repairs?issue=9", []);
    expect(screen.getByText("Work order 3")).toBeVisible();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
