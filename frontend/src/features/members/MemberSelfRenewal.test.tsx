import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { TenantProvider } from "../../lib/tenant";
import { StructuredApiError } from "../../lib/api/errors";
import { BorrowingHistoryList } from "./BorrowingHistoryList";
import { MemberActivityPanel, type MemberActivity } from "./MemberActivity";
import type { OwnBorrowing } from "./borrowingHistoryApi";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), memberRequest: request, staffRequestBlob: vi.fn() }));
vi.mock("./MemberEventFeedback", () => ({ MemberEventFeedback: () => null }));
vi.mock("./MemberEventCancel", () => ({ MemberEventCancel: () => null }));

const loan: OwnBorrowing = {
  id: 12, status: "issued", created_at: "2026-10-01T00:00:00Z", issued_at: "2026-10-02T00:00:00Z", return_due_at: "2026-10-12T00:00:00Z",
  closed_at: null, source: "reviewed_request", checked_out_at: null, returned_at: null, items: [], returns: [],
};
let client: QueryClient;
function wrap(node: ReactNode) {
  client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><TenantProvider>{node}</TenantProvider></MemoryRouter></QueryClientProvider>);
}
const space = { makerspaceId: 7, makerspaceSlug: "lab" };

beforeEach(() => { request.mockReset(); });

it("lets an account-only borrower renew from the borrowing page when the server allows it", async () => {
  request.mockResolvedValue({ return_due_at: "2026-10-20T00:00:00Z", renewal_count: 1 });
  wrap(<BorrowingHistoryList rows={[{ ...loan, can_renew: true, renewal_refusal: null }]} space={space} />);
  const invalidate = vi.spyOn(client, "invalidateQueries");
  fireEvent.click(screen.getByRole("button", { name: "Renew loan" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/member/makerspaces/7/loans/12/renew", { method: "POST", body: "{}" }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["member", "borrowing-history"] }));
});

it("tells the borrower to ask staff when self-renewal is off, and offers no button", () => {
  wrap(<BorrowingHistoryList rows={[{ ...loan, can_renew: false, renewal_refusal: "self_renewal_off" }]} space={space} />);
  expect(screen.getByText("Ask staff to renew")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Renew loan" })).toBeNull();
});

it("shows the same hint on the member dashboard loan row", () => {
  const activity: MemberActivity = {
    active_hardware_loans: [{ request_id: 12, can_renew: false, renewal_refusal: "self_renewal_off", label: "Drill",
      checked_out_at: "2026-10-01T00:00:00Z", due_at: "2026-10-12T00:00:00Z", overdue: false }],
    recent_presence_sessions: [], currently_checked_in: false,
    accountability: { membership_active: true, waiver_acceptance_required: false, restriction_code: null },
  };
  wrap(<MemberActivityPanel modules={["membership", "request_workflow"]} activity={activity} makerspaceId={7} makerspaceSlug="lab" makerspaceName="Lab" />);
  expect(screen.getByText("Ask staff to renew")).toBeInTheDocument();
});

it("explains a renewal refusal in plain words", async () => {
  request.mockRejectedValue(new StructuredApiError(400, { code: "renewal_limit", detail: "x" }));
  wrap(<BorrowingHistoryList rows={[{ ...loan, can_renew: true }]} space={space} />);
  fireEvent.click(screen.getByRole("button", { name: "Renew loan" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("reached its renewal limit");
});
