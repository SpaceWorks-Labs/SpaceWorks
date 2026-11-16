import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { shopAccess } from "./shopAccess";
import { ShopPos } from "./ShopPos";

const mocks = vi.hoisted(() => ({ staff: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest: mocks.staff }));

const variant = (id: number, name: string, sku: string) => ({ id, name, options: {}, sku, price: "40.00", on_hand: 9, held: 0, reorder_point: 0,
  linked_product_id: null, is_active: true, sort_order: 0, archived_at: null, available: 9 });
const products = { count: 2, next: null, previous: null, results: [
  { id: 1, name: "Pen", kind: "merch", image_url: "", archived_at: null, created_at: "", updated_at: "", components: [], is_active: true,
    variants: [variant(11, "Standard", "PEN-1")] },
  { id: 2, name: "Shirt", kind: "merch", image_url: "", archived_at: null, created_at: "", updated_at: "", components: [], is_active: true,
    variants: [variant(21, "S", "SHIRT-S"), variant(22, "M", "SHIRT-M")] },
] };
const quote = { currency: "inr", lines: [{ variant_id: 11, label: "Pen", quantity: "1", unit_amount: "40.00", discount: "0", net: "40.00",
  tax_rate_bps: null, tax: null }], subtotal: "40.00", discount_total: "0", total: "40.00", tax_total: "0", amount_due: "40.00",
  tax_inclusive: true, discount_name: "", digest: "pos-digest" };
const call = (suffix: string) => mocks.staff.mock.calls.filter(([path]) => String(path).includes(suffix));

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const access = shopAccess(["sell_shop"], false, { enabled_modules: ["shop"], enabled_features: [] });
  render(<QueryClientProvider client={client}><ShopPos makerspaceId={4} access={access} /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.staff.mockImplementation((path: string) => Promise.resolve(path.includes("/products/") ? products
    : path.endsWith("/pos/quote/") ? quote : { id: 77, status: "collected", lines: [], returns: [] }));
});

const scan = async (text: string) => {
  const input = await screen.findByLabelText("Scan or type an item");
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: "Enter" });
};

describe("shop till", () => {
  it("adds a line when a scanned SKU and Enter arrive, and offers choices for an ambiguous name", async () => {
    show();
    await scan("pen-1");
    expect(within(screen.getByRole("list", { name: "Basket" })).getByText("Pen")).toBeVisible();
    await scan("shirt");
    expect(screen.getByText("2 items match. Choose one below.")).toBeVisible();
    fireEvent.click(within(screen.getByRole("list", { name: "Matching items" })).getByRole("button", { name: /Shirt · M/ }));
    expect(within(screen.getByRole("list", { name: "Basket" })).getByText("Shirt · M")).toBeVisible();
  });

  it("prices on the server and posts the sale with the quote digest and the method", async () => {
    show();
    await scan("PEN-1");
    await waitFor(() => expect(call("/pos/quote/")).not.toHaveLength(0));
    expect(JSON.parse(call("/pos/quote/")[call("/pos/quote/").length - 1][1].body)).toEqual({ lines: [{ variant_id: 11, quantity: 1 }], member_id: null });
    const sell = screen.getByRole("button", { name: "Sell" });
    await waitFor(() => expect(sell).toBeEnabled());
    fireEvent.click(screen.getByRole("radio", { name: "UPI" }));
    expect(sell).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Transaction reference"), { target: { value: "UPI-123" } });
    fireEvent.click(sell);
    expect(await screen.findByText("Sale recorded: order #77.")).toBeVisible();
    expect(JSON.parse(call("/pos/sale/")[0][1].body)).toMatchObject({ lines: [{ variant_id: 11, quantity: 1 }], method: "upi",
      reference: "UPI-123", quote_digest: "pos-digest", member_id: null });
  });

  it("explains a closed cash drawer", async () => {
    mocks.staff.mockImplementation((path: string) => path.endsWith("/pos/sale/")
      ? Promise.reject(new StructuredApiError(409, { detail: "x", code: "cash_session_closed" }))
      : Promise.resolve(path.includes("/products/") ? products : quote));
    show();
    await scan("PEN-1");
    const sell = screen.getByRole("button", { name: "Sell" });
    await waitFor(() => expect(sell).toBeEnabled());
    fireEvent.click(sell);
    expect(await screen.findByText("Open the cash drawer in Cash-up before taking cash.")).toBeVisible();
  });
});
