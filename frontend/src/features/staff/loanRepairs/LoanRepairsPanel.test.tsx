import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LoanRepairsPanel } from "./LoanRepairsPanel";
import type { LoanRepairLine, LoanRepairs } from "./loanRepairsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const line: LoanRepairLine = { accountability_id: 31, product_name: "Soldering iron", quantity: 1, asset_tag: "",
  remark: "Cracked tip", evidence_id: 4, issue: null };
const repaired: LoanRepairLine = { ...line, issue: { id: 12, state: "triaged", title: "Damaged on return", quote_state: "pending",
  quote_amount: "18.50", quote_currency: "usd", payout_amount: null, payout_currency: "", work_order: { id: 3, status: "open" },
  parts: [{ id: 1, kind: "needed", name: "Heating element", quantity: 2, to_buy_item_id: 8 }],
  to_buy_items: [{ id: 8, name: "Heating element", quantity: 2, status: "needed", estimated_unit_cost: "6.00",
    actual_unit_cost: null, receipts: [] }] } };

describe("LoanRepairsPanel", () => {
  it("sends a damaged line to repairs, then shows its work order, parts and cost", async () => {
    let data: LoanRepairs = { request_id: 9, lines: [line] };
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => {
      if (init?.method === "POST") { data = { request_id: 9, lines: [repaired] }; return Promise.resolve({ created: true, issue_id: 12, line: repaired }); }
      return Promise.resolve(data);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><LoanRepairsPanel loan={{ id: 9, status: "closed_with_issue", makerspace_id: 7 }} /></QueryClientProvider>);
    fireEvent.click(await screen.findByRole("button", { name: "Send Soldering iron · 1 damaged to repairs" }));
    await waitFor(() => expect(screen.getByText(/Work order #3/)).toBeInTheDocument());
    const post = staffRequest.mock.calls.find(([, init]) => init?.method === "POST");
    expect(post?.[0]).toBe("/admin/makerspaces/7/requests/9/repairs");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ accountability_id: 31 });
    expect(screen.getByText("Needs 2 x Heating element")).toBeInTheDocument();
    expect(screen.getByText(/To buy: 2 x Heating element/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /to repairs/ })).not.toBeInTheDocument();
  });

  it("sends an optional note with the handoff", async () => {
    staffRequest.mockReset();
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => init?.method === "POST"
      ? Promise.resolve({ created: true, issue_id: 12, line: repaired }) : Promise.resolve({ request_id: 9, lines: [line] }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><LoanRepairsPanel loan={{ id: 9, status: "closed_with_issue", makerspace_id: 7 }} /></QueryClientProvider>);
    fireEvent.change(await screen.findByLabelText("Note for repairs (optional)"), { target: { value: "  Tip snapped at the collar  " } });
    fireEvent.click(screen.getByRole("button", { name: "Send Soldering iron · 1 damaged to repairs" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true));
    const post = staffRequest.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ accountability_id: 31, note: "Tip snapped at the collar" });
  });
});
