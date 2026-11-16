import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberRefundControl } from "./MemberRefundRequest";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, memberRequest };
});

function renderControl(payment: Parameters<typeof MemberRefundControl>[0]["payment"]) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemberRefundControl makerspaceId={4} payment={payment} /></QueryClientProvider>);
}

const openCase = { id: 9, kind: "request" as const, status: "open" as const, decision_note: "", withdrawable: true,
  created_at: "2026-10-20T10:00:00Z", decided_at: null };

beforeEach(() => { memberRequest.mockReset(); memberRequest.mockResolvedValue(openCase); });

describe("MemberRefundControl", () => {
  it("asks for a refund with the member's reason", async () => {
    renderControl({ id: 31, refund_case: null, refund_requestable: true });
    fireEvent.click(screen.getByRole("button", { name: "Request refund" }));
    const send = screen.getByRole("button", { name: "Send request" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Why are you asking?"), { target: { value: "Could not attend" } });
    fireEvent.click(send);
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/4/payments/31/refund-request",
      { method: "POST", body: JSON.stringify({ reason: "Could not attend" }) }));
  });

  it("shows the decision and lets the member withdraw an open request", async () => {
    const { rerender } = renderControl({ id: 31, refund_case: openCase, refund_requestable: false });
    expect(screen.getByText("Refund under review")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Request refund" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Withdraw request" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/4/refund-requests/9/withdraw",
      { method: "POST", body: "{}" }));
    rerender(<QueryClientProvider client={new QueryClient()}><MemberRefundControl makerspaceId={4} payment={{ id: 31,
      refund_case: { ...openCase, status: "declined", withdrawable: false, decision_note: "Outside the window" },
      refund_requestable: true }} /></QueryClientProvider>);
    expect(screen.getByText("Refund declined")).toBeInTheDocument();
    expect(screen.getByText(/Outside the window/)).toBeInTheDocument();
  });

  it("renders nothing for a charge that cannot be refunded", () => {
    const { container } = renderControl({ id: 31, refund_case: null, refund_requestable: false });
    expect(container).toBeEmptyDOMElement();
  });
});
