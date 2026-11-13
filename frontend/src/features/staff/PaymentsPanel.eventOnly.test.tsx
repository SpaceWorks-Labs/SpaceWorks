import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PaymentsPanel } from "./PaymentsPanel";
import type { PaymentRow } from "./paymentsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

const payment: PaymentRow = {
  id: 52, subject_type: "event_registration", subject_id: 9, subject_label: "Soldering workshop",
  status: "pending", amount: "8.00", currency: "usd", refunded_amount: "0.00", refunds: [],
  created_at: "2026-07-20T10:00:00Z", updated_at: "2026-07-20T10:00:00Z",
};

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (_path: string, options?: RequestInit) =>
    options?.method === "POST" ? payment : { count: 1, next: null, previous: null, results: [payment] });
});

function renderPanel(actorActions: string[], initialEntry = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter initialEntries={[initialEntry]}><QueryClientProvider client={queryClient}>
    <PaymentsPanel makerspaceId={7} makerspaceName="Lab" actorActions={actorActions} />
  </QueryClientProvider></MemoryRouter>);
}

const listPaths = () => staffRequest.mock.calls.map(([path]) => String(path)).filter(path => path.startsWith("/admin/makerspace/7/payments"));

describe("PaymentsPanel for an Event Manager without finance actions", () => {
  // Decision 242(a) / audit M1: the Event Manager reads the own-area queue, which covers every event
  // charge type (ticket orders, venue fees, entry fees, teams, deposits), not only registrations.
  it("reads the own-area queue across every event charge type and drops finance-only surfaces", async () => {
    renderPanel(["manage_events"], "/?subject_type=booking");
    await screen.findByText("Soldering workshop");
    const paths = listPaths().filter(path => !path.includes("/summary"));
    expect(paths.length).toBeGreaterThan(0);
    for (const path of paths) {
      expect(path).toContain("/payments/area-queue");
      expect(path).not.toContain("for_recording");
      expect(path).not.toContain("subject_type=");
    }
    // Saved views are finance-gated server-side, so their request must never be made.
    expect(staffRequest.mock.calls.some(([path]) => String(path).includes("saved-views"))).toBe(false);
    expect(screen.queryByRole("combobox", { name: "Subject" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Billing documents" })).not.toBeInTheDocument();
    expect(screen.getByText(/Charges for the areas you run, owed to Lab/)).toBeInTheDocument();
  });

  it("still offers the receipt and waive actions on an event charge", async () => {
    renderPanel(["manage_events"]);
    await screen.findByText("Soldering workshop");
    expect(screen.getAllByRole("button", { name: "Mark paid" }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("checkbox", { name: "Select row 52" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Mark paid in person" })).toBeInTheDocument());
    expect(screen.getAllByRole("button", { name: "Waive" }).length).toBeGreaterThan(0);
  });

  it("keeps finance staff on the unfiltered ledger", async () => {
    renderPanel(["view_finance", "manage_events"]);
    await screen.findByText("Soldering workshop");
    expect(listPaths().every(path => !path.includes("subject_type="))).toBe(true);
  });
});
