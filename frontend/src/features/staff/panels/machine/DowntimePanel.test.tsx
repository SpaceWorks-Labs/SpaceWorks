import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DowntimePanel, LockoutBadge, LockoutNotice } from "./DowntimePanel";
import { MaintenanceSchedules } from "./MaintenanceSchedules";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ staffRequest }));

const downtime = { summary: { days: 30, uptime_percent: 96.25, periods: 2, mean_hours_to_repair: 4.5 }, periods: [
  { id: 2, kind: "offline", reason: "Laser tube", expected_back_at: null, started_at: "2026-11-01T09:00:00Z", ended_at: null },
  { id: 1, kind: "maintenance", reason: "Belt", expected_back_at: null, started_at: "2026-10-01T09:00:00Z", ended_at: "2026-10-01T13:00:00Z" },
] };
const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

describe("machine downtime and lockout", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("shows uptime, repair time and periods, and edits the open period", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "PATCH" ? downtime : downtime);
    wrap(<DowntimePanel machineId={4} canEdit />);
    expect(await screen.findByText("96.3%")).toBeVisible();
    expect(screen.getByText("4.5 h")).toBeVisible();
    expect(screen.getByText("Offline now")).toBeVisible();
    expect(screen.getByText("Belt")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Waiting for a new tube" } });
    fireEvent.click(screen.getByRole("button", { name: "Save downtime" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machines/4/downtime",
      { method: "PATCH", body: JSON.stringify({ reason: "Waiting for a new tube", expected_back_at: null }) }));
  });

  it("names the overdue schedules that lock a machine out", async () => {
    staffRequest.mockResolvedValue({ locked: true, schedules: [{ id: 9, description: "Clean the optics", next_due: "2026-10-20" }] });
    wrap(<><LockoutBadge machineId={4} /><LockoutNotice machineId={4} /></>);
    expect(await screen.findByText(/Clean the optics/)).toBeVisible();
    expect(screen.getAllByText("Locked out")).toHaveLength(2);
  });

  it("lets a schedule lock the machine out when overdue", async () => {
    staffRequest.mockResolvedValue({});
    wrap(<MaintenanceSchedules makerspaceId={1} machineId={4} schedules={[]} canEdit retired={false} onComplete={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("New schedule description"), { target: { value: "Clean the optics" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Lock the machine out when overdue" }));
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(JSON.parse(staffRequest.mock.calls[0][1].body)).toMatchObject({ description: "Clean the optics", blocks_use: true });
  });
});
