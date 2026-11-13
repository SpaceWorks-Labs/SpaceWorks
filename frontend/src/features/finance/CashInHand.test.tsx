import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { reportItem } from "../../test/analyticsFixtures";
import { CashInHand } from "./CashInHand";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const catalog = { results: [reportItem("cash-in-hand", { title: "Cash in hand per collector", chart_spec: null, grains: ["day"] })] };
const asha = { collector_id: 4, collector: "asha", currency: "inr", received_cash: "1500.00", refunded_cash: "0.00",
  handed_over: "500.00", cash_in_hand: "1000.00" };

function respond(rows: Record<string, unknown>[]) {
  staffRequest.mockImplementation((path: string, init?: { method?: string }) => {
    if (path.endsWith("/reports/catalog")) return Promise.resolve(catalog);
    if (path.includes("/analytics/cash-in-hand")) return Promise.resolve({ typed_rows: rows, rows: [] });
    if (init?.method === "POST") return Promise.resolve({ entry_id: 1, collector_id: 4, amount: "1000.00", currency: "inr" });
    return Promise.reject(new Error(`unexpected ${path}`));
  });
}

beforeEach(() => { staffRequest.mockReset(); });

describe("CashInHand", () => {
  it("shows an empty state when nobody has recorded cash", async () => {
    respond([]);
    wrap(<CashInHand makerspaceId={3} canHandover />);
    expect(await screen.findByText(/Nobody has recorded a cash payment/)).toBeInTheDocument();
  });

  it("lists each collector and records a hand-over from their row", async () => {
    respond([asha]);
    wrap(<CashInHand makerspaceId={3} canHandover />);
    const table = await screen.findByRole("table", { name: "Cash in hand per collector" });
    expect(within(table).getByText("asha")).toBeInTheDocument();
    expect(within(table).getByText("₹1,000.00")).toBeInTheDocument();
    fireEvent.click(within(table).getByRole("button", { name: "Record hand-over" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/Amount/)).toHaveValue("1000.00");
    fireEvent.change(within(dialog).getByLabelText(/Note/), { target: { value: "To treasurer" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Record hand-over" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/billing/cash-handovers",
      expect.objectContaining({ method: "POST" })));
    const post = staffRequest.mock.calls.find(([path]) => String(path).endsWith("/cash-handovers"))!;
    expect(JSON.parse(post[1].body as string)).toMatchObject({ collector_id: 4, amount: "1000.00", currency: "inr", note: "To treasurer" });
    expect(await screen.findByText("Hand-over from asha recorded.")).toBeInTheDocument();
  });

  it("offers no hand-over without the switch or record-payment access", async () => {
    respond([asha]);
    wrap(<CashInHand makerspaceId={3} canHandover={false} />);
    await screen.findByRole("table", { name: "Cash in hand per collector" });
    expect(screen.queryByRole("button", { name: "Record hand-over" })).not.toBeInTheDocument();
  });
});
