import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { PaymentsPanel } from "./PaymentsPanel";
import type { Paginated } from "../../lib/usePaginatedQuery";
import type { PaymentRow } from "./paymentsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

const payment: PaymentRow = {
  id: 41,
  subject_type: "booking",
  subject_id: 9,
  subject_label: "Laser cutter booking",
  status: "pending",
  amount: "125.00",
  currency: "usd",
  refunded_amount: "0.00",
  refunds: [],
  created_at: "2026-07-20T10:00:00Z",
  updated_at: "2026-07-20T10:00:00Z",
};

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (_path: string, options?: RequestInit) =>
    options?.method === "POST" ? payment : { count: 1, next: null, previous: null, results: [payment] });
});

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return {
    queryClient,
    ...render(
      <MemoryRouter><QueryClientProvider client={queryClient}>
        <PaymentsPanel makerspaceId={7} actorActions={["view_finance", "record_payment", "manage_bookings", "manage_makerspace"]} />
      </QueryClientProvider></MemoryRouter>,
    ),
  };
}

async function waitForPayment() {
  await screen.findByText("Laser cutter booking");
}

describe("PaymentsPanel", () => {
  it("keeps the Due filter on the To collect toolbar and Type as its own column", async () => {
    renderPanel();
    await waitForPayment();
    expect(screen.getByRole("columnheader", { name: "Type" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Overdue" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("due_state=overdue"))).toBe(true));
  });
  it("renders all four subject filter choices", async () => {
    renderPanel();
    await waitForPayment();

    if (screen.queryByRole("button", { name: /^Filters/ })) fireEvent.click(screen.getByRole("button", { name: /^Filters/ }));
    const subjectFilter = screen.getByRole("combobox", { name: "Subject" });
    expect(subjectFilter).toHaveTextContent("Machine service");
    expect(subjectFilter).toHaveTextContent("Booking");
    expect(subjectFilter).toHaveTextContent("Event registration");
    expect(subjectFilter).toHaveTextContent("Membership dues");
  });

  it("runs a single action and invalidates every payment view after success", async () => {
    const { queryClient } = renderPanel();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await waitForPayment();

    // Marking paid offline is two steps now: the API requires a receipt saying how and
    // when the money arrived, so the button opens the form and the request only goes
    // once staff confirm it.
    fireEvent.click(screen.getByRole("button", { name: "Mark paid" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/makerspace/7/payments/41/mark-offline",
      expect.objectContaining({ method: "POST" }),
    ));
    // Pick the settlement call itself: a list refetch follows it with no body.
    const call = staffRequest.mock.calls.find(
      ([path]) => path === "/admin/makerspace/7/payments/41/mark-offline",
    )!;
    const settlement = JSON.parse((call[1] as { body: string }).body).settlement;
    expect(settlement.method).toBe("cash");
    expect(settlement.received_at).toEqual(expect.any(String));
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["payments", 7] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["operations-report", "payment-reconciliation"] });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["dashboard", 7] });
    });
  });

  it("runs a bulk action with the selected payment ids", async () => {
    renderPanel();
    await waitForPayment();

    fireEvent.click(screen.getByRole("checkbox", { name: "Select row 41" }));
    expect(screen.getByText("1 selected")).toBeVisible();
    fireEvent.click(screen.getAllByRole("button", { name: "Waive" })[0]);

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/makerspace/7/payments/bulk/waive",
      { method: "POST", body: JSON.stringify({ ids: [41] }) },
    ));
  });

  it("keeps the visible list, reports a 409 conflict, and refetches", async () => {
    let listRequests = 0;
    let finishRefetch: ((rows: Paginated<PaymentRow>) => void) | undefined;
    staffRequest.mockImplementation((_path: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        return Promise.reject(new StructuredApiError(409, { detail: "Payment status changed" }));
      }
      if (_path.includes("saved-views")) return Promise.resolve({ count: 0, next: null, previous: null, results: [] });
      // Decision 241/242: the by-area summary above the ledger is its own request, not a list read.
      if (_path.includes("area-queue/summary")) return Promise.resolve({ groups: [] });
      // Parity C20: the header reads the payment settings for the test-mode badge.
      if (_path.includes("payment-settings")) return Promise.resolve({ test_mode: false });
      listRequests += 1;
      if (listRequests === 1) return Promise.resolve({ count: 1, next: null, previous: null, results: [payment] });
      return new Promise<Paginated<PaymentRow>>((resolve) => { finishRefetch = resolve; });
    });
    renderPanel();
    await waitForPayment();

    fireEvent.click(screen.getByRole("button", { name: "Actions for Laser cutter booking" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Waive" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Payment status changed");
    await waitFor(() => expect(listRequests).toBe(2));
    expect(screen.getByText("Laser cutter booking")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith(
      "/admin/makerspace/7/payments/41/waive",
      { method: "POST" },
    );

    finishRefetch?.({ count: 1, next: null, previous: null, results: [payment] });
  });

  it("offers every payment subject the ledger records, renewal and loan charges included", async () => {
    renderPanel();
    await waitForPayment();

    if (screen.queryByRole("button", { name: /^Filters/ })) fireEvent.click(screen.getByRole("button", { name: /^Filters/ }));
    const subjectFilter = screen.getByRole("combobox", { name: "Subject" });
    expect(subjectFilter).toHaveTextContent("Membership renewal");
    expect(subjectFilter).toHaveTextContent("Loan deposit");
    expect(subjectFilter).toHaveTextContent("Late return fee");
  });

  it("shows a settled row's receipt and lets staff correct it instead of settling again", async () => {
    const settled: PaymentRow = {
      ...payment,
      status: "paid_offline",
      settlement: {
        id: 3, method: "upi", reference: "UPI-9", received_at: "2026-07-20T10:00:00Z",
        recorded_at: "2026-07-20T10:05:00Z", corrected: false,
      },
    };
    staffRequest.mockImplementation(async (_path: string, options?: RequestInit) =>
      options?.method === "POST" ? settled : { count: 1, next: null, previous: null, results: [settled] });
    renderPanel();
    await waitForPayment();

    expect(screen.getByText("UPI · UPI-9")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Waive" })).toBeNull();
    // Only the bulk toolbar could still offer it; the row itself never does.
    expect(screen.queryAllByRole("button", { name: "Mark paid" })).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Actions for Laser cutter booking" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Correct receipt" }));
    expect(screen.getAllByRole("heading", { level: 2, name: "Correct the receipt" })).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));

    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(
      "/admin/makerspace/7/payments/41/amend-settlement",
      expect.objectContaining({ method: "POST" }),
    ));
    const call = staffRequest.mock.calls.find(
      ([path]) => path === "/admin/makerspace/7/payments/41/amend-settlement",
    )!;
    expect(JSON.parse((call[1] as { body: string }).body).settlement.method).toBe("cash");
  });
  it("keeps status deep links and opens receipts only on demand", async () => {
    renderPanel();
    await waitForPayment();
    expect(screen.getByRole("heading", { level: 1, name: "Payments" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Paid in person" })).toHaveAttribute("href", "/?status=paid_offline");
    expect(screen.getByRole("link", { name: "All" })).toHaveAttribute("href", "/?status=");
    expect(staffRequest.mock.calls.some(([path]) => path.includes("payment-documents"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Billing documents" }));
    expect(await screen.findByRole("dialog")).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payment-documents?page=1"));
  });

  it("keeps receipt failures visible inside the payment dialog", async () => {
    staffRequest.mockImplementation(async (_path: string, options?: RequestInit) => {
      if (options?.method === "POST") throw new Error("Receipt could not be saved");
      return { count: 1, next: null, previous: null, results: [payment] };
    });
    renderPanel();
    await waitForPayment();
    fireEvent.click(screen.getByRole("button", { name: "Mark paid" }));
    fireEvent.click(screen.getByRole("button", { name: "Save receipt" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Receipt could not be saved");
    expect(screen.getByRole("dialog")).toContainElement(screen.getByRole("alert"));
  });

  it("closes receipts when finance authority is removed", async () => {
    const { rerender, queryClient } = renderPanel();
    await waitForPayment();
    fireEvent.click(screen.getByRole("button", { name: "Billing documents" }));
    expect(await screen.findByRole("dialog")).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payment-documents?page=1"));
    const documentCalls = staffRequest.mock.calls.filter(([path]) => path.includes("payment-documents")).length;
    rerender(<MemoryRouter><QueryClientProvider client={queryClient}>
      <PaymentsPanel makerspaceId={8} actorActions={["record_payment"]} />
    </QueryClientProvider></MemoryRouter>);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/8/payments?for_recording=true&status=pending&page=1&ordering=due_at"));
    expect(staffRequest.mock.calls.filter(([path]) => path.includes("payment-documents"))).toHaveLength(documentCalls);
    expect(screen.queryByRole("button", { name: "Billing documents" })).not.toBeInTheDocument();
  });
  it("changes status through the router and preserves the all-status query", async () => {
    renderPanel();
    await waitForPayment();
    if (screen.queryByRole("button", { name: /^Filters/ })) fireEvent.click(screen.getByRole("button", { name: /^Filters/ }));
    fireEvent.click(screen.getByRole("radio", { name: "Overdue" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments?status=pending&due_state=overdue&page=1&ordering=due_at"));
    if (screen.queryByRole("button", { name: "Show results" })) fireEvent.click(screen.getByRole("button", { name: "Show results" }));
    fireEvent.click(screen.getByRole("link", { name: "Paid in person" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments?status=paid_offline&page=1&ordering=due_at"));
    expect(screen.getByRole("link", { name: /Paid in person/ })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getByRole("link", { name: "All" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/payments?page=1&ordering=due_at"));
  });
});
