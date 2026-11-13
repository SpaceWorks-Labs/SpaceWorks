import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenantProvider } from "../../lib/tenant";
import { expectNoA11yViolations } from "../../test/axe";
import { PublicMachineServiceStatusPage } from "./PublicMachineServiceStatusPage";
import type { MachineServiceStatus } from "./types";

const api = vi.hoisted(() => ({ fetchServiceStatus: vi.fn(), fetchOwnerControls: vi.fn(), cancelOwnServiceRequest: vi.fn() }));
vi.mock("./api", () => ({ ...api, serviceKeys: {
  status: (token: string) => ["public-machine-service-status", token], owner: (token: string) => ["machine-service-owner", token] } }));
const session = vi.hoisted(() => ({ token: "" }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<object>()), getAccessToken: () => session.token }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined, isLoading: false, isError: false }) }));

function job(overrides: Partial<MachineServiceStatus> = {}): MachineServiceStatus {
  return { public_token: "tok", status: "accepted", title: "Laser panel", machine_type_name: "Laser cutter",
    created_at: "2026-10-18T09:00:00Z", accepted_at: null, started_at: null, completed_at: null, cancelled_at: null,
    estimated_minutes: 15, queue_position: 3, queue_approved_ahead: 2, queue_awaiting_review_ahead: 0,
    eta: { calculated_at: "2026-10-18T10:00:00Z", estimated_start_at: "2026-10-18T10:50:00Z", estimated_finish_at: "2026-10-18T11:05:00Z",
      start_in_minutes: 50, finish_in_minutes: 65, confidence: "estimated", reasons: [], approved_ahead: 2,
      awaiting_review_ahead: 0, active_machine_count: 2, missing_estimate_count: 0 }, ...overrides };
}

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/machine-service/requests/tok"]}><TenantProvider>
      <Routes><Route path="/m/:slug/machine-service/requests/:publicToken" element={<PublicMachineServiceStatusPage />} /></Routes>
    </TenantProvider></MemoryRouter></QueryClientProvider>);
}

describe("PublicMachineServiceStatusPage", () => {
  beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()); session.token = ""; });

  it("renders the server ETA for any machine type and offers no write to anonymous visitors", async () => {
    api.fetchServiceStatus.mockResolvedValue(job());
    const { container } = show();
    expect((await screen.findAllByText("Laser panel")).length).toBeGreaterThan(0);
    expect(screen.getByText(/Starts in about 50 min/)).toBeInTheDocument();
    expect(api.fetchOwnerControls).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Cancel job" })).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("lets the signed-in owner cancel after confirming, then refetches", async () => {
    session.token = "member-jwt";
    api.fetchServiceStatus.mockResolvedValueOnce(job()).mockResolvedValue(job({ status: "cancelled", eta: null }));
    api.fetchOwnerControls.mockResolvedValueOnce({ request_id: 41, can_cancel: true }).mockResolvedValue({ request_id: 41, can_cancel: false });
    api.cancelOwnServiceRequest.mockResolvedValue(job({ status: "cancelled", eta: null }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Cancel job" }));
    fireEvent.click(await screen.findByRole("button", { name: "Yes, cancel job" }));
    await waitFor(() => expect(api.cancelOwnServiceRequest).toHaveBeenCalledWith(41));
    expect(await screen.findByText(/was cancelled. Nothing was charged/)).toBeInTheDocument();
    expect(api.fetchServiceStatus.mock.calls.length).toBeGreaterThan(1);
  });

  it("shows the finished state without an estimate for terminal jobs", async () => {
    api.fetchServiceStatus.mockResolvedValue(job({ status: "completed", eta: null }));
    show();
    expect(await screen.findByText("Your job finished and is ready to collect.")).toBeInTheDocument();
    expect(screen.queryByText(/Starts in/)).toBeNull();
  });

  it.each([
    ["rejected", /wasn't approved, so it won't be run/],
    ["failed", /couldn't be completed/],
  ])("gives a %s job its own accurate copy, never 'finished'", async (status, copy) => {
    api.fetchServiceStatus.mockResolvedValue(job({ status, eta: null }));
    show();
    expect(await screen.findByText(copy)).toBeInTheDocument();
    expect(screen.queryByText(/finished/)).toBeNull();
  });
});
