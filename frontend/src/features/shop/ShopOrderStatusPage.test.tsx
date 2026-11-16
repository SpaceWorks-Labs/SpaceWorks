import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api/errors";
import { ShopOrderStatusPage } from "./ShopOrderStatusPage";

// MOD-3 flow audit (shop: a guest's private order link): loading, ready, and the one non-leaking error state.
const mocks = vi.hoisted(() => ({ status: vi.fn() }));
vi.mock("./shopApi", async (original) => ({ ...(await original<typeof import("./shopApi")>()), fetchOrderStatus: mocks.status }));
vi.mock("./useShopSpace", () => ({
  useShopSpace: () => ({ slug: "lab", name: "Lab", bootstrap: undefined, brandStyle: {}, path: (part = "") => `/m/lab${part ? `/${part}` : ""}`,
    chrome: { makerspace: { slug: "lab", name: "Lab" }, nav: [], footer: { links: [] } } }),
}));

const order = { id: 19, status: "awaiting_payment", channel: "online", pickup_code: "TEST42", pickup_at: "space", pickup_event_title: "",
  pickup_requires_staff_confirmation: false, space_name: "Demo space", currency: "inr", subtotal: "80.00", discount_total: "0.00",
  total: "80.00", tax_total: "0.00", amount_due: "80.00", created_at: "2026-11-07T01:00:00Z", expires_at: null, paid_at: null,
  ready_at: null, collected_at: null, closed_at: null, returns: [],
  lines: [{ id: 7, variant_id: 4, label: "Demo shirt", quantity: 2, unit_amount: "40.00", discount_amount: "0.00", line_total: "80.00",
    hsn_code: "", tax_rate_bps: null, tax_amount: "0.00" }] };

function show(token = "tok-1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/m/lab/shop/order/${token}`]}>
    <Routes><Route path="/m/:slug/shop/order/:token" element={<ShopOrderStatusPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { mocks.status.mockReset(); });

describe("ShopOrderStatusPage", () => {
  it("reads the order by the link's token and shows who it is from", async () => {
    mocks.status.mockResolvedValue(order);
    show("tok-1");
    expect(await screen.findByText("From Demo space")).toBeInTheDocument();
    expect(screen.getByText("Demo shirt")).toBeInTheDocument();
    expect(mocks.status).toHaveBeenCalledWith("lab", "tok-1");
  });

  it("answers a wrong or expired link with one generic message that never says whether an order exists", async () => {
    mocks.status.mockImplementation(() => Promise.reject(new StructuredApiError(404, { detail: "Not found." })));
    show("wrong");
    expect(await screen.findByText("This order link is not valid. Check the link in your email.")).toBeInTheDocument();
    expect(screen.queryByText("Demo shirt")).not.toBeInTheDocument();
  });

  it("shows the same generic message for a server refusal other than 404", async () => {
    mocks.status.mockImplementation(() => Promise.reject(new StructuredApiError(403, { detail: "Order 19 belongs to someone else." })));
    show("other");
    expect(await screen.findByText("This order link is not valid. Check the link in your email.")).toBeInTheDocument();
    expect(screen.queryByText(/belongs to someone else/)).not.toBeInTheDocument();
  });
});
