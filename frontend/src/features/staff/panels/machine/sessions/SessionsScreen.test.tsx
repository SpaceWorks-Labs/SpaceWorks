import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../../../../test/axe";
import type { StaffSession } from "../../../../machine-sessions/api";
import { SessionsScreen } from "./SessionsScreen";
import { SessionSettingsEditor } from "./SessionSettingsEditor";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const flagged: StaffSession = { id: 9, makerspace_id: 1, machine_id: 3, machine_name: "Laser A", machine_type_name: "Laser cutter",
  source: "member_qr", status: "review", started_at: "2026-11-01T09:00:00Z", ended_at: "2026-11-01T13:00:00Z", minutes: 240,
  stop_reason: "max_length", flagged: true, charge_state: "held", rate: { unit_amount: "120.00", currency: "inr", increment: 15, minimum: 30, discount_name: "" },
  amount: "480.00", payment: null, member_id: 4, member_name: "Asha", needs_review: true, service_request_id: null, duration_minutes: 240,
  amendments: [] };
const page = (rows: StaffSession[]) => ({ count: rows.length, next: null, previous: null, results: rows });

function show(url = "/staff/machines?view=sessions&session_status=review") {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[url]}><SessionsScreen makerspaceId={1} machines={[]} onBack={vi.fn()} /></MemoryRouter>
  </QueryClientProvider>);
}

describe("staff machine sessions", () => {
  beforeEach(() => { staffRequest.mockReset(); });

  it("lists sessions to check and corrects the time with a reason", async () => {
    staffRequest.mockImplementation(async (path?: string) => String(path).includes("/amend") ? { ...flagged, minutes: 50 } : page([flagged]));
    const { container } = show();
    expect(await screen.findByText(/Asha · Laser A/)).toBeVisible();
    expect(screen.getByText("Check the time")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Correct time" }));
    fireEvent.change(screen.getByLabelText("Minutes"), { target: { value: "50" } });
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Left early" } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-sessions/9/amend",
      { method: "POST", body: JSON.stringify({ minutes: 50, reason: "Left early" }) }));
    await expectNoA11yViolations(container);
  });

  it("confirms a session under review", async () => {
    staffRequest.mockImplementation(async (path?: string) => String(path).includes("/confirm") ? { ...flagged, needs_review: false } : page([flagged]));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-sessions/9/confirm", { method: "POST", body: undefined }));
  });

  it("offers Assign for an unattributed device session and Stop for a live one", async () => {
    staffRequest.mockResolvedValue(page([{ ...flagged, member_id: null, member_name: "", source: "device", stop_reason: "device" },
      { ...flagged, id: 10, status: "live", needs_review: false, ended_at: null, charge_state: "running" }]));
    show();
    expect(await screen.findByRole("button", { name: "Assign member" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Confirm" })).toBeNull();
    expect(screen.getByRole("button", { name: "Stop session" })).toBeVisible();
    expect(screen.getByText("Unattributed")).toBeVisible();
  });

  it("saves the per-type maximum length", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "PUT"
      ? { session_max_minutes: 90 } : { session_max_minutes: 240 });
    render(<QueryClientProvider client={new QueryClient()}><SessionSettingsEditor makerspaceId={1} machineTypeId={2} /></QueryClientProvider>);
    const input = await screen.findByLabelText("Longest session (minutes)");
    expect(input).toHaveValue(240);
    fireEvent.change(input, { target: { value: "90" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/1/machine-types/2/session-settings",
      { method: "PUT", body: JSON.stringify({ session_max_minutes: 90 }) }));
    expect(await screen.findByText("Session setting saved.")).toBeVisible();
  });
});
