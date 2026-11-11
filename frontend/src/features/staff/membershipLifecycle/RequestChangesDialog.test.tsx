import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError, staffRequest } from "../../../lib/api";
import { MembershipAdmissionReview, type ReviewMembershipRequest } from "../MembershipAdmissionReview";

vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const row = (extra: Partial<ReviewMembershipRequest> = {}) => ({
  id: 31, kind: "request", state: "requested", user: { id: 4, username: "asha" }, invite_email: "", assigned_role: null,
  decision_note: "", created_at: "2026-11-01T10:00:00Z", decided_at: null, changes_rounds: 0, changes_note: "", ...extra,
}) as unknown as ReviewMembershipRequest;

function show(request: ReviewMembershipRequest, askChanges = true, onChanged = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MembershipAdmissionReview row={request} makerspaceId={9} manageable canViewFinance={false}
    canRecordPayment={false} canWaive={false} approvePending={false} declinePending={false} selectedRole={1}
    onApprove={vi.fn()} onDecline={vi.fn()} askChanges={askChanges} onChanged={onChanged} /></QueryClientProvider>);
  return onChanged;
}

beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

describe("ask an applicant for changes (parity O-B2)", () => {
  it("sends the note to the request-changes route and refreshes the queue", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ id: 31, state: "changes_requested" });
    const onChanged = show(row());
    fireEvent.click(screen.getByRole("button", { name: "Ask for changes" }));
    const send = screen.getByRole("button", { name: "Send back for changes" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/What should they change/), { target: { value: "Add your workshop experience." } });
    fireEvent.click(send);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/9/join-requests/31/request-changes",
      { method: "POST", body: JSON.stringify({ reason: "Add your workshop experience." }) }));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("explains a typed refusal in words", async () => {
    vi.mocked(staffRequest).mockRejectedValue(new StructuredApiError(400, { code: "membership_changes_already_asked", detail: "x" }));
    show(row());
    fireEvent.click(screen.getByRole("button", { name: "Ask for changes" }));
    fireEvent.change(screen.getByLabelText(/What should they change/), { target: { value: "Again" } });
    fireEvent.click(screen.getByRole("button", { name: "Send back for changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already sent back once");
  });

  it("is absent when the switch is off, after one round, and for invitations", () => {
    show(row(), false);
    expect(screen.queryByRole("button", { name: "Ask for changes" })).toBeNull();
  });

  it("shows the waiting state and the note once sent back", () => {
    show(row({ state: "changes_requested", changes_rounds: 1, changes_note: "Add a photo." } as Partial<ReviewMembershipRequest>));
    expect(screen.queryByRole("button", { name: "Ask for changes" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByText(/Waiting for the applicant to edit and resubmit/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Decline" })).toBeEnabled();
  });
});
