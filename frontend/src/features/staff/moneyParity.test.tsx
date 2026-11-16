import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { staffRequest, staffRequestBlob } = vi.hoisted(() => ({ staffRequest: vi.fn(), staffRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<object>(), staffRequest, staffRequestBlob }));

import { SeriesMoneyCard } from "./SeriesMoneyCard";
import { EventOrdersList } from "./eventTicketing/EventOrdersList";
import { TestModeNotice } from "./paymentTestMode";

const wrap = (ui: import("react").ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>;
const orders = { count: 1, next: null, previous: null, results: [{ id: 5, buyer: 1, buyer_name: "Ravi", total: "20.00", currency: "usd", status: "paid",
  seats: [{ id: 1, status: "claimed", attendee_email: "r@x.org" }], payment_disputed: false }] };

beforeEach(() => { staffRequest.mockReset(); staffRequestBlob.mockReset(); });

describe("event money parity (C20, C24)", () => {
  it("series money card shows each currency and nothing when hidden", () => {
    const { container, rerender } = render(<SeriesMoneyCard money={null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<SeriesMoneyCard money={{ occurrences: 3, currencies: [{ currency: "usd", income: "300.00", refunds: "20.00", other_income: "0.00", expenses: "50.00", payouts: "0.00", net: "230.00" }] }} />);
    expect(screen.getByRole("heading", { name: "Money across the series" })).toBeVisible();
    expect(screen.getByText("3 occurrences")).toBeVisible();
    expect(screen.getByText("$230.00")).toBeVisible();
  });

  it("flags test-mode keys, and says nothing for live keys or staff who cannot read payment settings", async () => {
    staffRequest.mockResolvedValue({ test_mode: true });
    const view = render(wrap(<TestModeNotice makerspaceId={4} />));
    expect(await screen.findByText("Test mode")).toBeVisible();
    view.unmount();
    staffRequest.mockRejectedValue(new Error("forbidden"));
    const { container } = render(wrap(<TestModeNotice makerspaceId={5} />));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/5/payment-settings"));
    expect(container).toBeEmptyDOMElement();
  });

  it("downloads the orders CSV through the event-orders report", async () => {
    staffRequest.mockImplementation(async (path: string) => path.includes("payment-settings") ? { test_mode: false } : orders);
    staffRequestBlob.mockResolvedValue(new Blob(["order_id\n5"], { type: "text/csv" }));
    Object.assign(URL, { createObjectURL: vi.fn(() => "blob:csv"), revokeObjectURL: vi.fn() });
    render(wrap(<EventOrdersList eventId={9} makerspaceId={4} exportsOn />));
    await screen.findByText(/Ravi/);
    fireEvent.click(screen.getByRole("button", { name: "Download orders CSV" }));
    await waitFor(() => expect(staffRequestBlob).toHaveBeenCalledWith("/admin/makerspace/4/reports/event-orders/export?subject_kind=event&subject_id=9&format=csv"));
  });

  it("offers no CSV without the exports switch", async () => {
    staffRequest.mockResolvedValue(orders);
    render(wrap(<EventOrdersList eventId={9} makerspaceId={4} />));
    expect(await screen.findByText(/Ravi/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Download orders CSV" })).toBeNull();
  });
});
