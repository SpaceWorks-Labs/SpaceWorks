import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { PrintStatusPanel } from "./PublicPrintRequestPanels";
import type { PrintStatus } from "./publicApi";

const session = vi.hoisted(() => ({ token: "", memberRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<object>()),
  getAccessToken: () => session.token, memberRequest: session.memberRequest }));

const eta = { calculated_at: "2026-10-18T10:00:00Z", estimated_start_at: "2026-10-18T10:50:00Z",
  estimated_finish_at: "2026-10-18T11:05:00Z", start_in_minutes: 50, finish_in_minutes: 65, confidence: "estimated" as const,
  reasons: [], approved_ahead: 0, awaiting_review_ahead: 0, active_machine_count: 2, missing_estimate_count: 0 };
function status(overrides: Partial<PrintStatus> = {}): PrintStatus {
  return { public_token: "tok", status: "accepted", title: "Bracket", created_at: "2026-10-18T09:00:00Z", accepted_at: null,
    started_at: null, completed_at: null, estimated_minutes: 15, queue_position: 1, queue_approved_ahead: 0,
    queue_awaiting_review_ahead: 0, eta, cancelled_at: null, ...overrides } as PrintStatus;
}
function panel(tokenStatus: PrintStatus, publicToken?: string) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PrintStatusPanel submitted={false} tokenStatus={tokenStatus} tokenStatusPending={false} tokenStatusError={null}
      publicToken={publicToken} makerspaceSlug="lab" />
  </QueryClientProvider>);
}

beforeEach(() => { session.token = ""; session.memberRequest.mockReset(); });

it("uses the server ETA (no browser countdown) and normalizes the printing transport status", async () => {
  const { container } = panel(status({ status: "printing", started_at: "2026-10-18T09:50:00Z" }));
  expect(screen.getByText(/Done around/)).toBeInTheDocument();
  expect(screen.queryByText(/left$/)).toBeNull();
  expect(screen.getByText("printing", { exact: false })).toBeInTheDocument();
  expect(container.querySelector("[aria-current='step']")?.textContent).toContain("Printing");
  await expectNoA11yViolations(container);
});

it("only an approved first job is next; a pending one is awaiting review", () => {
  const { unmount } = panel(status());
  expect(screen.getByText("You're next among approved jobs")).toBeInTheDocument();
  unmount();
  panel(status({ status: "pending", eta: { ...eta, confidence: "rough", reasons: ["awaiting_approval"] } }));
  expect(screen.getAllByText("Awaiting review").length).toBeGreaterThan(0);
  expect(screen.queryByText("You're next among approved jobs")).toBeNull();
});

it("shows a cancelled job as terminal and lets only the signed-in owner cancel a live one", async () => {
  const { unmount } = panel(status({ status: "cancelled", eta: null }));
  expect(screen.getByText(/was cancelled. Nothing was charged/)).toBeInTheDocument();
  unmount();
  const anonymous = panel(status(), "tok");
  expect(screen.queryByRole("button", { name: "Cancel job" })).toBeNull();
  anonymous.unmount();
  session.token = "member-jwt";
  session.memberRequest.mockImplementation(async (path: string) => path.endsWith("/owner") ? { request_id: 5, can_cancel: true } : { status: "cancelled" });
  panel(status(), "tok");
  fireEvent.click(await screen.findByRole("button", { name: "Cancel job" }));
  fireEvent.click(await screen.findByRole("button", { name: "Yes, cancel job" }));
  await waitFor(() => expect(session.memberRequest).toHaveBeenCalledWith("/member/machine-service/requests/5/cancel", expect.objectContaining({ method: "POST" })));
});
