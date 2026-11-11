import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import type { MemberSession, SessionPreview } from "./api";
import { SessionTimerCard } from "./SessionTimerCard";
import { UseMachinePage } from "./UseMachinePage";

const api = vi.hoisted(() => ({ fetchSessionPreview: vi.fn(), startSession: vi.fn(), stopSession: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));
vi.mock("../machine-jobs/MemberJobsShell", () => ({ MemberJobsShell: ({ children }: { children: (context: object) => ReactNode }) => <>{children({
  slug: "lab", makerspaceId: 1, ready: true, bootstrapError: false, path: (part = "") => `/m/lab/${part}` })}</> }));

const rate = { unit_amount: "120.00", currency: "inr", increment: 15, minimum: 30, discount_name: "" };
const live: MemberSession = { id: 5, makerspace_id: 1, machine_id: 3, machine_name: "Laser A", machine_type_name: "Laser cutter",
  source: "member_qr", status: "live", started_at: "2026-11-02T09:00:00Z", ended_at: null, minutes: 0, stop_reason: "", flagged: false,
  charge_state: "running", rate, amount: "60.00", payment: null };
function preview(overrides: Partial<SessionPreview> = {}): SessionPreview {
  return { machine_id: 3, machine_name: "Laser A", machine_type_name: "Laser cutter", machine_status: "idle", billing: true, rate,
    digest: "abc", max_minutes: 240, closes_at: null, can_start: true, refusal: null, live_session: null, ...overrides };
}

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/machines/3/use"]}><Routes>
      <Route path="/m/:slug/machines/:machineId/use" element={<UseMachinePage />} />
    </Routes></MemoryRouter></QueryClientProvider>);
}

describe("Use this machine", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); });
  afterEach(() => vi.useRealTimers());

  it("shows the frozen rate and rules, then starts with the digest it showed", async () => {
    api.fetchSessionPreview.mockResolvedValue(preview());
    api.startSession.mockResolvedValue(live);
    const { container } = show();
    expect(await screen.findByText(/₹120.00 an hour · billed per 15 min · 30 min minimum|INR 120.00 an hour/)).toBeVisible();
    expect(screen.getByText("4 h")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Start session" }));
    await waitFor(() => expect(api.startSession).toHaveBeenCalledWith(3, "abc"));
    await expectNoA11yViolations(container);
  });

  it("explains a refusal in words and keeps Start disabled", async () => {
    api.fetchSessionPreview.mockResolvedValue(preview({ can_start: false,
      refusal: { code: "certification_required", detail: "x", certifications: ["Laser safety"] } }));
    show();
    expect(await screen.findByText(/You need the certification for this machine first. \(Laser safety\)/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Start session" })).toBeDisabled();
  });

  it("shows the live session with Stop instead of Start", async () => {
    api.fetchSessionPreview.mockResolvedValue(preview({ can_start: false, refusal: { code: "session_already_live", detail: "" }, live_session: live }));
    api.stopSession.mockResolvedValue({ ...live, status: "closed", minutes: 20, charge_state: "raised" });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Stop session" }));
    await waitFor(() => expect(api.stopSession).toHaveBeenCalledWith(5));
    expect(screen.queryByRole("button", { name: "Start session" })).toBeNull();
  });
});

describe("SessionTimerCard", () => {
  it("ticks once a second and keeps the clock out of the accessibility tree", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-02T09:01:05Z"));
    const onStop = vi.fn();
    render(<SessionTimerCard session={live} maxMinutes={240} onStop={onStop} stopping={false} />);
    expect(screen.getByText("0:01:05")).toHaveAttribute("aria-hidden", "true");
    act(() => { vi.advanceTimersByTime(2000); });
    expect(screen.getByText("0:01:07")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop session" }));
    expect(onStop).toHaveBeenCalled();
  });
});
