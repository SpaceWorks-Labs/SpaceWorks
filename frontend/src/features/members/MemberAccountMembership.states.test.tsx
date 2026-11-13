import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { MemberAccountMembership } from "./MemberAccountMembership";

// MOD-3B frontend states for the member's own renewal / leave controls: loading, error, permission denied,
// already-cancelled, confirm flow with keyboard-reachable controls.
const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), memberRequest }));

const active = { status: "active", renewal_cancelled_at: null };
function show(onLeft = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemberAccountMembership makerspaceId={7} onLeft={onLeft} /></QueryClientProvider>);
  return onLeft;
}
const posts = () => memberRequest.mock.calls.filter(([, init]) => init?.method === "POST");

beforeEach(() => { memberRequest.mockReset(); });

describe("MemberAccountMembership states", () => {
  it("loading: shows the loading label and no destructive controls yet", () => {
    memberRequest.mockReturnValue(new Promise(() => {}));
    show();
    expect(screen.getByText("Loading membership…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Cancel renewal/ })).not.toBeInTheDocument();
  });

  it("permission denied / error: the refusal is announced and no cancel or leave control is offered", async () => {
    memberRequest.mockRejectedValue(new StructuredApiError(403, { detail: "Membership is not available to you.", code: "forbidden" }));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Membership is not available to you.");
    expect(screen.queryByRole("button", { name: /^Leave makerspace/ })).not.toBeInTheDocument();
  });

  it("already cancelled: says so and the cancel-renewal button is disabled with its reason", async () => {
    memberRequest.mockResolvedValue({ status: "active", renewal_cancelled_at: "2026-11-01T00:00:00Z" });
    show();
    expect(await screen.findByText(/Renewal is cancelled\./)).toBeVisible();
    const buttons = screen.getAllByRole("button", { name: /^Cancel renewal/ });
    expect(buttons.every(button => button.hasAttribute("disabled") || button.getAttribute("aria-disabled") === "true")).toBe(true);
  });

  it("cancel renewal needs a reason before it can be confirmed, then posts it once", async () => {
    memberRequest.mockImplementation((_path: string, init?: { method?: string }) => Promise.resolve(init?.method === "POST"
      ? { ...active, renewal_cancelled_at: "2026-11-02T00:00:00Z" } : active));
    const onLeft = show();
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel renewal/ }));
    const confirm = screen.getByRole("button", { name: "Confirm cancellation" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Moving away" } });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0][0]).toMatch(/\/cancel$/);
    expect(JSON.parse(posts()[0][1].body)).toEqual({ reason: "Moving away" });
    expect(onLeft).not.toHaveBeenCalled();
  });

  it("leave: confirming calls onLeft; Keep membership closes the form without any request", async () => {
    memberRequest.mockImplementation((_path: string, init?: { method?: string }) => Promise.resolve(init?.method === "POST"
      ? { status: "revoked", renewal_cancelled_at: null } : active));
    const onLeft = show();
    fireEvent.click(await screen.findByRole("button", { name: /^Leave makerspace/ }));
    fireEvent.click(screen.getByRole("button", { name: "Keep membership" }));
    expect(screen.queryByLabelText("Reason")).not.toBeInTheDocument();
    expect(posts()).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: /^Leave makerspace/ }));
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Done" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm leave" }));
    await waitFor(() => expect(onLeft).toHaveBeenCalledTimes(1));
    expect(posts()[0][0]).toMatch(/\/leave$/);
  });

  it("a failed leave keeps the form and announces the server's refusal", async () => {
    memberRequest.mockImplementation((_path: string, init?: { method?: string }) => init?.method === "POST"
      ? Promise.reject(new StructuredApiError(409, { detail: "Return your open loans first.", code: "open_loans" }))
      : Promise.resolve(active));
    const onLeft = show();
    fireEvent.click(await screen.findByRole("button", { name: /^Leave makerspace/ }));
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Done" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm leave" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Return your open loans first.");
    expect(onLeft).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Reason")).toBeInTheDocument();
  });
});
