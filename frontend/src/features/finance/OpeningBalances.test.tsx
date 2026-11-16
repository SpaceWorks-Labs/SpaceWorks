import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GstinCheck } from "./GstinCheck";
import { OpeningBalances } from "./OpeningBalances";
import type { FinanceAccess } from "./financeApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<object>("../../lib/api")), staffRequest }));

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}
const access = (record: boolean): FinanceAccess => ({ everything: true, domains: [], machine_type_ids: null, record_domains: [], record_everything: record });
const row = { fy_start: "2026-04-01", currency: "inr", cash_amount: "500.00", bank_amount: "12000.00", set_at: "2026-04-02T10:00:00Z" };

beforeEach(() => { staffRequest.mockReset(); });

describe("OpeningBalances", () => {
  it("lists the year's balances and saves a new revision for finance recorders", async () => {
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "PUT" ? row : [row]));
    wrap(<OpeningBalances makerspaceId={3} access={access(true)} />);
    expect(await screen.findByText("inr")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/finance/opening-balances");
    fireEvent.change(screen.getByLabelText("Currency"), { target: { value: "INR" } });
    fireEvent.change(screen.getByLabelText("Cash"), { target: { value: "750.50" } });
    fireEvent.click(screen.getByRole("button", { name: "Save opening balance" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/finance/opening-balances",
      expect.objectContaining({ method: "PUT" })));
    const body = JSON.parse(staffRequest.mock.calls.find(call => call[1]?.method === "PUT")![1].body);
    expect(body).toMatchObject({ currency: "inr", cash_amount: "750.50", bank_amount: "0" });
  });

  it("is read-only without record authority and filters by year", async () => {
    staffRequest.mockResolvedValue([]);
    wrap(<OpeningBalances makerspaceId={3} access={access(false)} />);
    expect(await screen.findByText("No opening balances are set for this year.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save opening balance" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Financial year containing"), { target: { value: "2025-06-01" } });
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/finance/opening-balances?fy=2025-06-01"));
  });
});

describe("GstinCheck", () => {
  it("checks a full GSTIN offline and names its state", async () => {
    staffRequest.mockResolvedValue({ valid: true, gstin: "27AAPFU0939F1ZV", state_code: "27", state_name: "Maharashtra" });
    wrap(<GstinCheck makerspaceId={3} gstin="27aapfu0939f1zv" />);
    fireEvent.click(screen.getByRole("button", { name: "Check GSTIN" }));
    expect(await screen.findByText("Valid GSTIN for Maharashtra (state 27).")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/billing/tax/validate-gstin",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ gstin: "27AAPFU0939F1ZV" }) }));
  });

  it("stays disabled until fifteen characters are entered", () => {
    wrap(<GstinCheck makerspaceId={3} gstin="27AAP" />);
    expect(screen.getByRole("button", { name: "Check GSTIN" })).toBeDisabled();
  });
});
