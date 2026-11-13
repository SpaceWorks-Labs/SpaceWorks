import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { FinanceOverview } from "./FinanceOverview";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OfflinePayment } from "../members/MemberPaymentOffline";
import { FinancePanel } from "./FinancePanel";
import { TaxSettings } from "./TaxSettings";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, staffRequest };
});
vi.mock("zxing-wasm/writer", () => ({ setZXingModuleOverrides: vi.fn(), writeBarcode: vi.fn(() => Promise.resolve({})) }));

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  // FinancePanel keeps its section in the URL path (0.12.0 row 15), so it needs a router.
  return render(<MemoryRouter><QueryClientProvider client={client}>{node}</QueryClientProvider></MemoryRouter>);
}

const tax = { enabled: true, mode: "gst_india", tax_name: "", rate_bps: 1800, prices_include_tax: true, gstin: "27AAPFU0939F1ZV",
  state_code: "27", scheme: "regular", exempt: false, sac_code: "999599", foreign_currency: "no_gst", lut_number: "",
  invoice_prefix: "INV", credit_note_prefix: "CN" };
const preview = { title: "Tax invoice", currency: "inr", taxable: "847.46", tax: "152.54", gross: "1000.00", supply_type: "intra",
  components: [{ code: "cgst", label: "CGST", rate_bps: 900, amount: "76.27" }, { code: "sgst", label: "SGST", rate_bps: 900, amount: "76.27" }],
  notes: ["Tax payable on reverse charge: No."], sample_number: "INV26-27/0001" };

beforeEach(() => { staffRequest.mockReset(); });

describe("TaxSettings", () => {
  it("explains how to turn tax on while the capability is off", async () => {
    staffRequest.mockResolvedValue({ ...tax, enabled: false });
    wrap(<TaxSettings makerspaceId={3} />);
    expect(await screen.findByText(/Turn on “Tax on charges”/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save tax settings" })).not.toBeInTheDocument();
  });

  it("shows a live CGST/SGST sample and saves the policy", async () => {
    staffRequest.mockImplementation((path: string, options?: { method?: string }) =>
      Promise.resolve(path.endsWith("/preview") ? preview : options?.method === "PUT" ? tax : tax));
    wrap(<TaxSettings makerspaceId={3} />);
    expect(await screen.findByText(/Sample: Tax invoice INV26-27\/0001/)).toBeInTheDocument();
    expect(screen.getByText(/CGST @ 9%/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save tax settings" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/billing/tax", expect.objectContaining({ method: "PUT" })));
  });
});

describe("OfflinePayment", () => {
  const offline = { upi: { vpa: "space@okbank", payee_name: "Lab", amount: "250.00", currency: "inr", reference: "SW-9",
    uri: "upi://pay?pa=space@okbank&am=250.00" }, instructions: "Pay at the desk too.", claim: null, claimable: true };

  it("shows the exact amount, the UPI ID and sends a claim", () => {
    const onClaim = vi.fn();
    wrap(<OfflinePayment offline={offline} onClaim={onClaim} pending={false} error={null} />);
    expect(screen.getByText("₹250.00")).toBeInTheDocument();
    expect(screen.getByText("space@okbank")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: /Transaction reference/ }), { target: { value: "UTR12345678" } });
    fireEvent.click(screen.getByRole("button", { name: "I've paid" }));
    expect(onClaim).toHaveBeenCalledWith(expect.objectContaining({ reference: "UTR12345678" }));
  });

  it("shows the claim status instead of the form once claimed", () => {
    wrap(<OfflinePayment offline={{ ...offline, claimable: false, claim: { id: 1, reference: "UTR1", paid_on: "2026-10-30",
      status: "submitted", decision_note: "" } }} onClaim={vi.fn()} pending={false} error={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(/confirm once it reaches/);
    expect(screen.queryByRole("button", { name: "I've paid" })).not.toBeInTheDocument();
  });
});

describe("FinancePanel", () => {
  it("offers no sections when every switch is off", () => {
    wrap(<FinancePanel makerspace={{ id: 1, enabled_modules: [], enabled_features: [] }} canViewFinance canRecordPayment />);
    expect(screen.getByText(/No finance screens are switched on/)).toBeInTheDocument();
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("shows income and spending for the caller's areas", async () => {
    staffRequest.mockImplementation((path: string) => Promise.resolve(path.includes("/finance/access")
      ? { everything: false, domains: ["inventory", "loans"], machine_type_ids: null, record_domains: ["inventory", "loans"], record_everything: false }
      : { start: "2026-01-01", end: "2026-10-31", rows: [{ month: "2026-10", domain: "loans", machine_type: "", currency: "inr",
        income: "500.00", other_income: "0.00", refunds: "0.00", expenses: "120.00", payouts: "0.00", money_in: "500.00",
        money_out: "120.00", net: "380.00" }] }));
    wrap(<FinancePanel makerspace={{ id: 1, enabled_modules: [], enabled_features: ["finance.ledger"] }} canViewFinance={false} canRecordPayment={false} />);
    expect(await screen.findByText("Inventory loans")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Disputes" })).not.toBeInTheDocument();
  });
});

describe("LedgerEntriesSection receipts", () => {
  it("shows a PDF receipt as a link button, never an image", async () => {
    const { LedgerEntriesSection } = await import("./LedgerEntriesSection");
    staffRequest.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 4, kind: "expense", domain: "general",
      machine_type_id: null, machine_type_label: "", event_id: null, category: "rent", method: "bank_transfer", account: "bank",
      amount: "900.00", currency: "usd", entry_date: "2026-10-01", description: "Workshop rent", counterparty: "", reference: "",
      source_kind: "manual", source_id: "", has_receipt: true, receipt_kind: "pdf", created_at: "2026-10-01T00:00:00Z",
      voided_at: null, void_reason: "" }] });
    const view = wrap(<LedgerEntriesSection makerspaceId={1} access={{ everything: true, domains: [], machine_type_ids: null,
      record_domains: [], record_everything: true }} />);
    expect(await screen.findByRole("button", { name: "Receipt (PDF)" })).toBeInTheDocument();
    expect(view.container.querySelector("img")).toBeNull();
  });
});

describe("FinanceOverview keyboard access", () => {
  it("makes the wide captioned money table focusable without changing its data", async () => {
    staffRequest.mockResolvedValue({ start: "2026-01-01", end: "2026-10-31", rows: [{
      month: "2026-10", domain: "loans", machine_type: "", currency: "inr", income: "500.00",
      other_income: "0.00", refunds: "0.00", expenses: "120.00", payouts: "0.00", net: "380.00" }] });
    wrap(<FinanceOverview makerspaceId={1} />);
    const region = await screen.findByRole("region", { name: "Income and spending by month and area" });
    const table = within(region).getByRole("table", { name: "Income and spending by month and area" });
    expect(within(table).getAllByRole("columnheader")).toHaveLength(8);
    expect(within(table).getByText("Inventory loans")).toBeInTheDocument();
    for (const amount of ["₹500.00", "₹120.00", "₹380.00"]) expect(within(table).getByText(amount)).toBeInTheDocument();
    expect(region.tabIndex).toBe(0);
    region.focus(); expect(region).toHaveFocus();
    expect(region).toHaveClass("focus-visible:outline-2", "focus-visible:outline-offset-2", "focus-visible:outline-focus");
  });
});
