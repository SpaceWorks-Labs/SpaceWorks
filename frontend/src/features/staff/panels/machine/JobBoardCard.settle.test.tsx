import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StaffListContext } from "../../StaffListContext";
import { JobBoardCard } from "./JobBoardCard";
import type { StaffJob } from "./machineJobsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../../lib/api")), staffRequest }));

const job = (status: string) => ({ id: 3, title: "Bracket", status: "completed", requester_name: "Ada",
  payment: { id: 77, subject_type: "machine_service_request", subject_label: "Bracket", status, amount: "9.00", currency: "usd",
    checkout_url: "", online_payment_available: false, settlement: null, created_at: "2026-11-01T00:00:00Z" } }) as unknown as StaffJob;
const handlers = { onDialog: vi.fn(), onDirect: vi.fn(), onUncollected: vi.fn(), onFiles: vi.fn() };

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue({ id: 77, status: "paid_offline" }); });

function mount(card: StaffJob, actions: string[]) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(<QueryClientProvider client={client}>
    <StaffListContext.Provider value={{ ownerName: "x", canShare: false, actions, makerspace: { id: 2 } }}>
      <ul><JobBoardCard job={card} {...handlers} /></ul>
    </StaffListContext.Provider></QueryClientProvider>);
}

describe("JobBoardCard settle (decision 242 a, audit M3)", () => {
  it("lets the Machine Manager record the job's cash and waive it on the card", async () => {
    mount(job("pending"), ["manage_machines"]);
    expect(screen.getByRole("button", { name: "Payment actions" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Mark offline" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/payments/77/mark-offline", expect.objectContaining({ method: "POST" })));
  });

  it("shows no settle control on a paid job or to a role without authority", () => {
    mount(job("paid_online"), ["manage_machines"]);
    expect(screen.queryByRole("button", { name: "Mark offline" })).toBeNull();
  });

  it("hides it from a Technician", () => {
    mount(job("pending"), ["work_repairs"]);
    expect(screen.queryByRole("button", { name: "Mark offline" })).toBeNull();
  });
});
