import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AllowedTabsContext } from "../../areaOverview/allowedTabsContext";
import { AllJobsScreen, groupJobs } from "./AllJobsScreen";
import { LinkedJob } from "./LinkedJob";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const laser = { id: 7, slug: "laser", name: "Laser cutters" };
const printer = { id: 8, slug: "printer", name: "3D printers" };
const machines = [
  { id: 1, name: "Laser A", machine_type: laser, is_active: true },
  { id: 2, name: "Laser B", machine_type: laser, is_active: true },
  { id: 3, name: "Prusa", machine_type: printer, is_active: true },
] as never[];
const job = (id: number, title: string, type: string, machine: { id: number; name: string } | null, member = { id: 40, display: "Asha" }, status = "pending") => ({
  id, title, status, machine_type: type, machine: null, assigned_machine: machine ? { ...machine, status: "idle" } : null,
  requester: { ...member, username: member.display.toLowerCase() }, requester_name: member.display, created_at: "2026-11-01T09:00:00Z",
});
const jobs = [
  job(1, "Sign", "laser", { id: 1, name: "Laser A" }),
  job(2, "Coaster", "laser", { id: 2, name: "Laser B" }, { id: 41, display: "Ravi" }),
  job(3, "Bracket", "printer", null),
  job(4, "Old box", "laser", { id: 1, name: "Laser A" }, undefined, "collected"),
];

function Where() { const location = useLocation(); return <p data-testid="where">{location.search}</p>; }
function show(node: React.ReactNode, entry = "/admin/machines?view=jobs", tabs: string[] = ["machines"]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[entry]}><AllowedTabsContext.Provider value={tabs}>{node}<Where /></AllowedTabsContext.Provider></MemoryRouter>
  </QueryClientProvider>);
}

describe("All jobs across machine types (A15)", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequest.mockImplementation(async (path: string) => String(path).includes("saved-views")
      ? { count: 0, next: null, previous: null, results: [] } : jobs);
  });

  it("groups by type then machine with unassigned jobs last", () => {
    const groups = groupJobs(jobs as never[], machines);
    expect(groups.map(group => [group.label, group.count])).toEqual([["3D printers", 1], ["Laser cutters", 3]]);
    expect(groups[1].machines.map(row => row.label)).toEqual(["Laser A", "Laser B"]);
    expect(groups[0].machines[0].label).toBe("No machine yet");
  });

  it("reads every type from one request, hides finished jobs by default and keeps saved views", async () => {
    show(<AllJobsScreen makerspaceId={5} machines={machines} onBack={vi.fn()} />);
    expect(await screen.findByText("Sign")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/5/machine-service/requests");
    expect(screen.queryByText("Old box")).toBeNull();
    const laserGroup = screen.getByText("Laser cutters").closest("details")!;
    expect(within(laserGroup).getByRole("region", { name: "Laser B" })).toHaveTextContent("Coaster");
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/5/saved-views?entity=machine_jobs&page=1"));
  });

  it("filters by machine and member from the URL", async () => {
    show(<AllJobsScreen makerspaceId={5} machines={machines} onBack={vi.fn()} />, "/admin/machines?view=jobs&jobs_machine=1&jobs_member=40");
    expect(await screen.findByText("Sign")).toBeVisible();
    expect(screen.queryByText("Coaster")).toBeNull();
    expect(screen.queryByText("Bracket")).toBeNull();
  });

  it("opens a job with ?job= so the detail drawer shows it", async () => {
    show(<AllJobsScreen makerspaceId={5} machines={machines} onBack={vi.fn()} />);
    (await screen.findByText("Sign")).click();
    await waitFor(() => expect(screen.getByTestId("where").textContent).toContain("job=1"));
  });

  it("shows a filtered empty state with a way back", async () => {
    show(<AllJobsScreen makerspaceId={5} machines={machines} onBack={vi.fn()} />, "/admin/machines?view=jobs&jobs_q=nothing");
    expect(await screen.findByText("No jobs match these filters.")).toBeVisible();
  });
});

describe("job detail drawer (A18)", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("shows the job's facts with the machine as a deep link", async () => {
    staffRequest.mockResolvedValue({ ...jobs[0], description: "Engrave the sign.", estimated_minutes: 30 });
    show(<LinkedJob jobId={1} />, "/m/lab/admin/machines?job=1");
    expect(await screen.findByText("Engrave the sign.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Laser A" })).toHaveAttribute("href", "/m/lab/admin/machines?machine=1");
    expect(screen.getByText("Asha")).toBeVisible();
  });

  it("keeps the machine as plain text when Machines is not open to this person", async () => {
    staffRequest.mockResolvedValue(jobs[0]);
    show(<LinkedJob jobId={1} />, "/m/lab/admin/machines?job=1", []);
    expect(await screen.findByText("Laser A")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Laser A" })).toBeNull();
  });
});
