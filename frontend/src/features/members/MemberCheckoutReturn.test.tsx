import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CHECKOUT_POLL_MS, CHECKOUT_POLLS, MemberCheckoutReturn } from "./MemberCheckoutReturn";

function Where() {
  const location = useLocation();
  return <div data-testid="where">{location.pathname + location.search}</div>;
}

function mount(path: string, onPaymentsTab: boolean, client = new QueryClient()) {
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path="*" element={<><MemberCheckoutReturn onPaymentsTab={onPaymentsTab} /><Where /></>} /></Routes>
  </MemoryRouter></QueryClientProvider>);
  return client;
}

afterEach(() => { vi.useRealTimers(); });

describe("MemberCheckoutReturn", () => {
  it("moves a payer returning from checkout to the Payments tab", () => {
    mount("/m/lab/member?checkout=success", false);
    expect(screen.getByTestId("where")).toHaveTextContent("/m/lab/member/payments?checkout=success");
  });

  it("says a successful checkout is being confirmed and re-reads charges and receipts until the webhook lands", () => {
    vi.useFakeTimers();
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    mount("/m/lab/member/payments?checkout=success", true, client);
    expect(screen.getByRole("status")).toHaveTextContent("being confirmed");
    expect(screen.getByRole("status")).toHaveTextContent("don't pay again");
    act(() => { vi.advanceTimersByTime(CHECKOUT_POLL_MS); });
    expect(invalidate).toHaveBeenCalledWith(expect.objectContaining({ predicate: expect.any(Function) }));
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["payment-documents"] });
    const predicate = (invalidate.mock.calls[0][0] as unknown as { predicate: (query: { queryKey: unknown[] }) => boolean }).predicate;
    expect(predicate({ queryKey: ["member", "lab", "payments"] })).toBe(true);
    expect(predicate({ queryKey: ["member", "archived-payments", 4, "payments"] })).toBe(true);
    expect(predicate({ queryKey: ["member", "lab", "activity"] })).toBe(false);
    // Bounded: it stops after CHECKOUT_POLLS rounds.
    for (let round = 0; round < CHECKOUT_POLLS + 3; round += 1) act(() => { vi.advanceTimersByTime(CHECKOUT_POLL_MS); });
    expect(invalidate.mock.calls.filter(([filters]) => filters && "predicate" in filters)).toHaveLength(CHECKOUT_POLLS);
  });

  it("tells a payer who cancelled that nothing was charged, and can be dismissed", () => {
    mount("/member/payments?checkout=cancelled", true);
    expect(screen.getByRole("status")).toHaveTextContent("nothing was charged");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByTestId("where")).toHaveTextContent(/^\/member\/payments$/);
  });

  it("ignores an unknown outcome", () => {
    mount("/member/payments?checkout=whatever", true);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
