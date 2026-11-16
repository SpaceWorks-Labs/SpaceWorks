import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { expectNoA11yViolations } from "../../test/axe";
import { MachineJobPage } from "./MachineJobPage";
import type { MemberJob } from "./types";

const api = vi.hoisted(() => ({ fetchMyJob: vi.fn(), approveQuote: vi.fn(), declineQuote: vi.fn(), resubmitJob: vi.fn(), fetchJobTypes: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));
vi.mock("./MemberJobsShell", () => ({ MemberJobsShell: ({ children }: { children: (context: object) => ReactNode }) => <>{children({
  slug: "lab", makerspaceId: 1, ready: true, bootstrapError: false, path: (part = "") => `/m/lab/${part}` })}</> }));
vi.mock("../members/MemberPaymentOffline", () => ({ useUpiQr: (value: string | null) => value ? `blob:${value}` : null }));
vi.mock("../machine-service/api", () => ({ cancelOwnServiceRequest: vi.fn() }));

const local = (day: number, hour: number) => new Date(2026, 10, day, hour, 0).toISOString();
function job(overrides: Partial<MemberJob> = {}): MemberJob {
  return { id: 7, public_token: "tok", makerspace_id: 1, queue_id: 3, can_cancel: true, title: "Bracket", status: "accepted", label: "in_queue", machine_type_name: "3D printer",
    machine_name: "", position: 3, eta: null, timeline: [{ step: "submitted", at: local(1, 9) }, { step: "in_queue", at: local(1, 10) }],
    changes_message: "", quote: null, quote_expires_at: null, awaiting_payment: false, reason: "", fail_code: "", failure_outcome: "",
    pickup_code: "", pickup_location: "", copies: 2, needed_by: null, created_at: local(1, 9), ...overrides };
}
const quote = { total: "120.00", currency: "inr", lines: [{ label: "Machine time", net: "100.00" }, { label: "Filament", net: "20.00" }], digest: "d1" };

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/m/lab/member/machine-jobs/7"]}><Routes>
      <Route path="/m/:slug/member/machine-jobs/:jobId" element={<MachineJobPage />} />
    </Routes></MemoryRouter></QueryClientProvider>);
}

describe("MachineJobPage", () => {
  beforeEach(() => {
    Object.values(api).forEach(fn => fn.mockReset());
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 2, 9, 0));
  });
  afterEach(() => vi.useRealTimers());

  it("shows you're next, a day-and-time ETA beyond 24 h, and the timeline", async () => {
    api.fetchMyJob.mockResolvedValue(job({ position: 1, eta: { calculated_at: local(2, 9), estimated_start_at: local(5, 12),
      estimated_finish_at: local(5, 14), start_in_minutes: 4500, finish_in_minutes: 4620, confidence: "estimated", reasons: [],
      approved_ahead: 0, awaiting_review_ahead: 0, active_machine_count: 1, missing_estimate_count: 0 } }));
    const { container } = show();
    expect(await screen.findByText("You're next")).toBeInTheDocument();
    expect(screen.getByText(/ready Thu, about 14:00/)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Job timeline" })).toHaveTextContent("Joined the queue");
    expect(screen.getByRole("button", { name: "Cancel job" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("re-asks with the new quote when the price changed, then approves its digest", async () => {
    api.fetchMyJob.mockResolvedValue(job({ status: "quoted", label: "quote_sent", position: null, quote }));
    api.approveQuote.mockRejectedValueOnce(new StructuredApiError(409, { detail: "changed", code: "price_changed",
      quote: { ...quote, total: "150.00", digest: "d2", lines: [{ label: "Machine time", net: "150.00" }] } }))
      .mockResolvedValueOnce(job({ position: 4 }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Approve quote" }));
    expect(await screen.findByText("The price changed since you opened this page.")).toBeInTheDocument();
    expect(screen.getAllByText(/150\.00/).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Approve new price" }));
    await waitFor(() => expect(api.approveQuote).toHaveBeenLastCalledWith(7, "d2"));
    expect(await screen.findByText("#4")).toBeInTheDocument();
  });

  it("shows the pickup place and code as text and as a QR", async () => {
    api.fetchMyJob.mockResolvedValue(job({ status: "completed", label: "ready_to_collect", position: null, pickup_code: "K7Q2", pickup_location: "Shelf B", can_cancel: false }));
    const { container } = show();
    expect(await screen.findByText("K7Q2")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "QR code of pickup code K7Q2" })).toHaveAttribute("src", "blob:K7Q2");
    expect(screen.getAllByText("Shelf B").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Cancel job" })).toBeNull();
    await expectNoA11yViolations(container);
  });

  it("says what failed and that the job was re-queued for free", async () => {
    api.fetchMyJob.mockResolvedValue(job({ fail_code: "nozzle_jam", failure_outcome: "requeued", position: 1 }));
    show();
    expect(await screen.findByText("Failed: nozzle jam — re-queued at the front, no charge")).toBeInTheDocument();
  });

  it("shows the staff message and sends the member's reply", async () => {
    api.fetchMyJob.mockResolvedValue(job({ status: "changes_requested", label: "needs_changes", position: null, changes_message: "Wall too thin." }));
    api.fetchJobTypes.mockResolvedValue([]);
    api.resubmitJob.mockResolvedValue(job({ status: "pending", label: "submitted", position: null }));
    show();
    expect(await screen.findByText("Wall too thin.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Your reply"), { target: { value: "Thickened to 2 mm" } });
    fireEvent.click(screen.getByRole("button", { name: "Send changes" }));
    await waitFor(() => expect(api.resubmitJob).toHaveBeenCalledWith(7, "Thickened to 2 mm", []));
  });
});
