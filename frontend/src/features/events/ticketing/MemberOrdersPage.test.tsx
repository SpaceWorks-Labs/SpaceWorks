import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { TenantProvider } from "../../../lib/tenant";
import { MemberOrdersPage } from "./MemberOrdersPage";
import type { TicketOrder } from "./ticketingApi";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"),
  memberRequest: mocks.request }));
vi.mock("../../inventory/usePublicInventory", () => ({
  useTenantBootstrap: () => ({ data: { makerspace: { id: 7 } }, isLoading: false }) }));
vi.mock("../../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in to see your orders</p> }));

const order: TicketOrder = {
  id: 44, kind: "tickets", status: "paid", event: 5, series: null, event_title: "Robot night", currency: "inr",
  subtotal: "20.00", discount_total: "0", fee_total: "1.00", total: "21.00", created_at: "2026-11-01T10:00:00Z",
  paid_at: "2026-11-01T10:05:00Z", checkout_url: "", payment_status: "paid", payment_disputed: false, hold_expires_at: null,
  lines: [{ id: 1, kind: "ticket", label: "Early bird", quantity: 2, unit_amount: "10.00", line_total: "20.00" }],
  seats: [
    { id: 11, event_id: 5, ticket_type_id: 1, status: "claimed", attendee_email: "asha@example.com", registration_id: 31,
      invited_at: null, claimed_at: "2026-11-01T10:06:00Z" },
    { id: 12, event_id: 5, ticket_type_id: 1, status: "unclaimed", attendee_email: "", registration_id: null,
      invited_at: null, claimed_at: null },
  ],
};

function show(path = "/m/lab/member/orders") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><TenantProvider><Routes>
    <Route path="/m/:slug/member/orders" element={<MemberOrdersPage />} />
    <Route path="/m/:slug/member/orders/:orderId" element={<MemberOrdersPage />} />
  </Routes></TenantProvider></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { vi.clearAllMocks(); });

describe("my orders", () => {
  it("lists each order with its total and how many places are claimed", async () => {
    mocks.request.mockResolvedValue({ results: [order] });
    show();
    const link = await screen.findByRole("link", { name: /Robot night/ });
    expect(link).toHaveAttribute("href", "/m/lab/member/orders/44");
    expect(within(link).getByText(/1 of 2 places claimed/)).toBeVisible();
    expect(within(link).getByText("Paid")).toBeVisible();
    expect(mocks.request).toHaveBeenCalledWith("/member/makerspaces/7/orders/");
  });

  it("shows the empty state", async () => {
    mocks.request.mockResolvedValue({ results: [] });
    show();
    expect(await screen.findByText("You have no ticket orders yet.")).toBeVisible();
  });

  it("asks a visitor to sign in", async () => {
    mocks.request.mockRejectedValue(new StructuredApiError(401, { detail: "Sign in." }));
    show();
    expect(await screen.findByText("Sign in to see your orders")).toBeVisible();
  });

  it("names an attendee for an unclaimed place and chases the rest", async () => {
    mocks.request.mockImplementation((path: string) => Promise.resolve(path.endsWith("/orders/") ? { results: [order] } : order));
    show("/m/lab/member/orders/44");
    expect(await screen.findByText("What you bought")).toBeVisible();
    expect(screen.getByText("Booking fee")).toBeVisible();
    expect(screen.getByText("asha@example.com")).toBeVisible();
    fireEvent.change(screen.getByLabelText("Attendee email"), { target: { value: "ravi@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("/member/makerspaces/7/orders/44/attendees/",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ assignments: { "12": "ravi@example.com" } }) })));
    fireEvent.click(screen.getByRole("button", { name: "Remind people to claim" }));
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("/member/makerspaces/7/orders/44/chase/",
      expect.objectContaining({ method: "POST" })));
  });

  it("flags a disputed payment and offers payment on a pending order", async () => {
    mocks.request.mockResolvedValue({ ...order, status: "pending", payment_disputed: true, checkout_url: "https://pay.example/x" });
    show("/m/lab/member/orders/44");
    expect(await screen.findByText("This payment is disputed with the card provider.")).toBeVisible();
    expect(screen.getByRole("link", { name: /Pay now/ })).toHaveAttribute("href", "https://pay.example/x");
    expect(screen.queryByRole("button", { name: "This one is mine" })).toBeNull();
  });
});
