import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopReceipt } from "./ShopReceipt";

const mocks = vi.hoisted(() => ({ staff: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest: mocks.staff }));

const receipt = { order_id: 77, space_name: "Lab", supplier_gstin: "29ABCDE1234F1Z5", document_number: "INV-0007", document_title: "Tax invoice",
  issued_at: "2026-11-04T10:00:00Z", buyer_name: "Asha", pickup_code: "K7Q2", channel: "pos", currency: "inr",
  lines: [{ label: "Pen", sku: "PEN-1", quantity: 2, unit_amount: "50.00", discount_amount: "0", line_total: "100.00", hsn_code: "9608",
    tax_rate_bps: 1800, tax_amount: "15.25" }],
  subtotal: "100.00", discount_total: "0", tax_total: "15.25", total: "100.00", status: "collected", paid: true, method: "cash", notes: [] };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ShopReceipt orderId={77} onBack={vi.fn()} /></QueryClientProvider>);
}
const pageRule = () => document.querySelector("style[data-receipt-page]")?.textContent ?? "";

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  mocks.staff.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "POST" ? undefined : receipt));
});

describe("shop receipt", () => {
  it("prints on an 80 mm roll by default and switches to an A4 sheet", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    show();
    expect(await screen.findByRole("article", { name: "Tax invoice" })).toHaveAttribute("data-format", "80mm");
    expect(pageRule()).toContain("size: 80mm auto");
    expect(screen.queryByRole("columnheader", { name: "HSN" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Print 80 mm receipt" }));
    expect(print).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("radio", { name: "A4 sheet" }));
    expect(screen.getByRole("article", { name: "Tax invoice" })).toHaveAttribute("data-format", "a4");
    expect(pageRule()).toContain("size: A4");
    expect(screen.getByRole("columnheader", { name: "HSN" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Print A4" }));
    expect(print).toHaveBeenCalledTimes(2);
    expect(window.localStorage.getItem("spaceworks.shop.receiptFormat")).toBe("a4");
  });

  it("emails the receipt", async () => {
    show();
    fireEvent.change(await screen.findByLabelText("Email"), { target: { value: "asha@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send receipt" }));
    await waitFor(() => expect(screen.getByText("Receipt sent.")).toBeVisible());
    expect(mocks.staff).toHaveBeenCalledWith("/admin/shop/orders/77/receipt/", expect.objectContaining({ method: "POST",
      body: JSON.stringify({ email: "asha@example.com" }) }));
  });
});
