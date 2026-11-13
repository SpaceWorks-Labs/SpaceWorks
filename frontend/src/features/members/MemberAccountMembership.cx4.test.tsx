import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { MemberAccountMembership } from "./MemberAccountMembership";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest: request }));

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const onLeft = vi.fn();
  render(<QueryClientProvider client={client}><MemberAccountMembership makerspaceId={7} onLeft={onLeft} /></QueryClientProvider>);
  return onLeft;
}

beforeEach(() => { request.mockReset(); });

describe("membership renewal cancellation boundaries", () => {
  it("module-off exposes neither cancellation nor leave controls", async () => {
    request.mockRejectedValue(new StructuredApiError(404, { code: "module_disabled", detail: "Membership is off." }));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Membership is off.");
    expect(screen.queryByRole("button", { name: /^Cancel renewal/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Leave makerspace/ })).not.toBeInTheDocument();
  });

  it("a pending cancellation disables repeat confirmation and keeps membership until the response", async () => {
    request.mockImplementation((_path: string, init?: RequestInit) => init?.method === "POST"
      ? new Promise(() => {}) : Promise.resolve({ status: "active", renewal_cancelled_at: null }));
    const onLeft = show();
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel renewal/ }));
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Moving" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Confirm cancellation" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Keep membership" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm cancellation" }));
    expect(request.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
    expect(onLeft).not.toHaveBeenCalled();
  });

  it("a failed cancellation keeps the reason and supports another attempt", async () => {
    let attempts = 0;
    request.mockImplementation((_path: string, init?: RequestInit) => {
      if (init?.method !== "POST") return Promise.resolve({ status: "active", renewal_cancelled_at: null });
      attempts += 1;
      return Promise.reject(new StructuredApiError(503, { code: "temporarily_unavailable", detail: "Please retry." }));
    });
    const onLeft = show();
    fireEvent.click(await screen.findByRole("button", { name: /^Cancel renewal/ }));
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Moving" } });
    fireEvent.submit(screen.getByRole("button", { name: "Confirm cancellation" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Please retry.");
    expect(screen.getByLabelText("Reason")).toHaveValue("Moving");
    fireEvent.submit(screen.getByRole("button", { name: "Confirm cancellation" }).closest("form")!);
    await waitFor(() => expect(attempts).toBe(2));
    expect(onLeft).not.toHaveBeenCalled();
  });
});
