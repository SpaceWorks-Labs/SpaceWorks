import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { ShopBuyerOrderView } from "./ShopBuyerOrderView";
import { eventPickupRefreshInterval, fetchMemberShopOrder, shopKeys, type ShopBuyerOrder } from "./shopApi";
import { MemberShopOrderDetail } from "../members/shopOrders/MemberShopOrderDetail";

import { ShopOrderDetail } from "../staff/shop/ShopOrderDetail";
import { shopAccess } from "../staff/shop/shopAccess";
import { staffShopKeys } from "../staff/shop/staffShopApi";
import { fetchOrder, movePickupToSpace, type ShopStaffOrder } from "../staff/shop/staffShopOrdersApi";

vi.mock("../staff/shop/staffShopOrdersApi", async original => ({
  ...await original<typeof import("../staff/shop/staffShopOrdersApi")>(), fetchOrder: vi.fn(), movePickupToSpace: vi.fn(),
}));
vi.mock("./shopApi", async original => ({ ...await original<typeof import("./shopApi")>(), fetchMemberShopOrder: vi.fn() }));

const at = (hour: number) => `2026-11-07T${String(hour).padStart(2, "0")}:00:00Z`;
const order: ShopBuyerOrder = {
  id: 19, status: "awaiting_payment", channel: "online", pickup_code: "TEST42", pickup_at: "space",
  pickup_event_title: "", pickup_requires_staff_confirmation: false, space_name: "Demo space", currency: "inr", subtotal: "80.00", discount_total: "0.00",
  total: "80.00", tax_total: "0.00", amount_due: "80.00", created_at: at(1), expires_at: null,
  paid_at: null, ready_at: null, collected_at: null, closed_at: null, returns: [],
  lines: [{ id: 7, variant_id: 4, label: "Demo shirt", quantity: 2, unit_amount: "40.00", discount_amount: "0.00",
    line_total: "80.00", hsn_code: "", tax_rate_bps: null, tax_amount: "0.00" }],
};

it("shows only recorded fulfilment stages, never guesses payment or pickup from the current status", () => {
  render(<ShopBuyerOrderView order={order} />);
  const history = screen.getByRole("region", { name: "Order history" });
  expect(within(history).getByText("Order placed")).toBeVisible();
  expect(within(history).queryByText("Payment received")).not.toBeInTheDocument();
  expect(within(history).queryByText("Ready to collect")).not.toBeInTheDocument();
  expect(within(history).queryByText("Collected")).not.toBeInTheDocument();
  expect(screen.getByText("TEST42")).toBeVisible();
  expect(screen.getByText("To pay at the desk")).toBeVisible();
});

it.each(["paid", "ready"] as const)("retains pickup and payment history without asking a %s buyer to pay again", status => {
  render(<ShopBuyerOrderView order={{ ...order, status, paid_at: at(2), ready_at: status === "ready" ? at(3) : null }} />);
  const history = screen.getByRole("region", { name: "Order history" });
  expect(within(history).getByText("Payment received").parentElement?.querySelector("time"))
    .toHaveAttribute("datetime", at(2));
  if (status === "ready") {
    expect(within(history).getByText("Ready to collect").parentElement?.querySelector("time"))
      .toHaveAttribute("datetime", at(3));
  }
  expect(screen.getByText("TEST42")).toBeVisible();
  expect(screen.getByText(/Pick up at Demo space/)).toBeVisible();
  expect(screen.queryByText("To pay at the desk")).toBeNull();
});

it("does not present a held online checkout as desk payment", () => {
  render(<ShopBuyerOrderView order={{ ...order, status: "held" }} />);
  expect(screen.getByText("TEST42")).toBeVisible();
  expect(screen.queryByText("To pay at the desk")).toBeNull();
});

it("keeps the paid, ready and collected timeline and its real machine-readable timestamps", () => {
  render(<ShopBuyerOrderView order={{ ...order, status: "collected", paid_at: at(2), ready_at: at(3), collected_at: at(4) }} />);
  const history = screen.getByRole("region", { name: "Order history" });
  expect(within(history).getAllByRole("listitem").map(row => row.querySelector("time")?.dateTime)).toEqual([at(1), at(2), at(3), at(4)]);
  expect(screen.queryByText("Show this code at the desk")).not.toBeInTheDocument();
});

it("shows cancellation time and no pending pickup code after an unpaid order is cancelled", () => {
  render(<ShopBuyerOrderView order={{ ...order, status: "cancelled", closed_at: at(2) }} />);
  const history = screen.getByRole("region", { name: "Order history" });
  expect(within(history).getByText("Cancelled").parentElement?.querySelector("time")).toHaveAttribute("datetime", at(2));
  expect(screen.queryByText("TEST42")).not.toBeInTheDocument();
});

it("does not claim money was received for a free order confirmed without a charge", () => {
  render(<ShopBuyerOrderView order={{ ...order, status: "collected", total: "0.00", amount_due: "0.00", paid_at: at(2) }} />);
  expect(screen.getByText("No payment due")).toBeVisible();
  expect(screen.queryByText("Payment received")).not.toBeInTheDocument();
});

it("labels returned goods without promising that the refund case has paid money", () => {
  render(<ShopBuyerOrderView order={{ ...order, status: "refunded", paid_at: at(2), collected_at: at(3), closed_at: at(4),
    returns: [{ line_id: 7, quantity: 2, amount: "80.00", created_at: at(4) }] }} />);
  expect(screen.getByText("Returned")).toBeVisible();
  expect(screen.getByText(/Demo shirt · 2 returned/)).toBeVisible();
  expect(screen.getByText(/Return values do not confirm a refund/)).toBeVisible();
  expect(screen.queryByText("Refunded")).not.toBeInTheDocument();
  expect(screen.queryByText("Show this code at the desk")).not.toBeInTheDocument();
});

it.each([["/m/demo/member/shop-orders", "/m/demo/member/payments"], ["/member/shop-orders", "/member/payments"]])(
  "links an account buyer from %s to the existing own payment/refund/document surface", async (backHref, expected) => {
    vi.mocked(fetchMemberShopOrder).mockResolvedValue({ ...order, status: "collected" });
    render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemberShopOrderDetail orderId={19} backHref={backHref} />
    </QueryClientProvider></MemoryRouter>);
    expect(await screen.findByRole("link", { name: "Payments, refunds and receipts" })).toHaveAttribute("href", expected);
    expect(fetchMemberShopOrder).toHaveBeenCalledWith(19);
  },
);

it.each([false, true])("stops pickup directions for an interrupted event (staff=%s)", staff => {
  render(<ShopBuyerOrderView staff={staff} order={{ ...order, pickup_at: "event",
    pickup_event_title: "Cancelled workshop", pickup_requires_staff_confirmation: true, expires_at: at(5) }} />);
  expect(screen.getByText(staff ? /Confirm an in-person pickup arrangement/ : /Contact the makerspace/)).toBeVisible();
  expect(screen.getByText(/Held until/)).toBeVisible();
  expect(screen.getByText("Amount due")).toBeVisible();
  expect(screen.queryByText("TEST42")).toBeNull();
  expect(screen.queryByText(/Pick up at|Cancelled workshop|To pay at the desk/)).toBeNull();
});

it("keeps pickup instructions for an available event", () => {
  render(<ShopBuyerOrderView order={{ ...order, pickup_at: "event", pickup_event_title: "Open workshop" }} />);
  expect(screen.getByText(/Pick up at Open workshop/)).toBeVisible();
  expect(screen.getByText("TEST42")).toBeVisible();
});

it.each(["member", "staff"] as const)("updates an open %s order when event pickup is interrupted", async surface => {
  vi.useFakeTimers();
  const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity, retry: false } } });
  const original = { ...order, pickup_at: "event", pickup_event_title: "Open workshop", expires_at: at(5) };
  const interrupted = { ...original, pickup_requires_staff_confirmation: true };
  const staffOrder: ShopStaffOrder = { ...original, pickup_at: "event", status: "awaiting_payment", channel: "online",
    makerspace: 3, buyer_name: "Buyer", buyer_email: "", payment_status: "pending", returns: [] };
  vi.mocked(fetchMemberShopOrder).mockClear().mockResolvedValue(interrupted);
  vi.mocked(fetchOrder).mockClear().mockResolvedValue({ ...staffOrder, pickup_requires_staff_confirmation: true });
  queryClient.setQueryData(shopKeys.memberOrder(order.id), original);
  queryClient.setQueryData(staffShopKeys.order(3, order.id), staffOrder);
  const request = surface === "member" ? fetchMemberShopOrder : fetchOrder;
  const mounted = render(<MemoryRouter><QueryClientProvider client={queryClient}>
    {surface === "member" ? <MemberShopOrderDetail orderId={order.id} backHref="/member/shop-orders" />
      : <ShopOrderDetail makerspaceId={3} orderId={order.id} access={shopAccess(["view_shop"], false, {})} onBack={vi.fn()} />}
  </QueryClientProvider></MemoryRouter>);
  try {
    expect(screen.getByText(/Pick up at Open workshop/)).toBeVisible();
    await act(() => vi.advanceTimersByTimeAsync(60_001));
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByText(surface === "member" ? /Contact the makerspace/ : /Confirm an in-person pickup arrangement/)).toBeVisible();
    expect(screen.queryByText(/Open workshop|TEST42|To pay at the desk/)).toBeNull();
    expect(screen.getByText("Amount due")).toBeVisible();
    expect(screen.getByText(/Held until/)).toBeVisible();
    const moved = { pickup_at: "space" as const, pickup_event_title: "", pickup_requires_staff_confirmation: false };
    vi.mocked(fetchMemberShopOrder).mockResolvedValue({ ...original, ...moved });
    vi.mocked(fetchOrder).mockResolvedValue({ ...staffOrder, ...moved });
    await act(() => vi.advanceTimersByTimeAsync(60_001));
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.getByText("TEST42")).toBeVisible();
    expect(screen.getByText("To pay at the desk")).toBeVisible();
    expect(screen.queryByText(/Contact the makerspace|Confirm an in-person pickup arrangement|Open workshop/)).toBeNull();
    await act(() => vi.advanceTimersByTimeAsync(120_000));
    expect(request).toHaveBeenCalledTimes(2);
  } finally {
    mounted.unmount();
    queryClient.clear();
    vi.useRealTimers();
  }
});

it("polls active event pickups until they move to the space or become terminal", () => {
  expect(eventPickupRefreshInterval(order)).toBe(false);
  expect(eventPickupRefreshInterval({ ...order, pickup_at: "event", status: "collected" })).toBe(false);
  expect(eventPickupRefreshInterval({ ...order, pickup_at: "event" })).toBe(60_000);
});

it.each([[["sell_shop"], true], [["view_shop"], false]] as const)(
  "offers the confirmed move to makerspace pickup only to desk staff (%s)", async (actions, offered) => {
    const interrupted: ShopStaffOrder = { ...order, pickup_at: "event", pickup_event_title: "Cancelled workshop",
      pickup_requires_staff_confirmation: true, status: "awaiting_payment", channel: "online", makerspace: 3,
      buyer_name: "Buyer", buyer_email: "", payment_status: "pending", returns: [] };
    vi.mocked(fetchOrder).mockReset().mockResolvedValue(interrupted);
    vi.mocked(movePickupToSpace).mockReset().mockResolvedValue({ ...interrupted, pickup_at: "space",
      pickup_requires_staff_confirmation: false });
    render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ShopOrderDetail makerspaceId={3} orderId={order.id} access={shopAccess(actions, false, {})} onBack={vi.fn()} />
    </QueryClientProvider></MemoryRouter>);
    expect(await screen.findByText(/Confirm an in-person pickup arrangement/)).toBeVisible();
    for (const menu of screen.queryAllByRole("button", { name: "More actions" })) fireEvent.click(menu);
    const item = screen.queryAllByRole("menuitem", { name: "Move pickup to the makerspace" });
    if (!offered) {
      expect(item).toHaveLength(0);
      return;
    }
    fireEvent.click(item[0]);
    expect(movePickupToSpace).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Move pickup" }));
    await waitFor(() => expect(movePickupToSpace).toHaveBeenCalledWith(order.id));
  },
);
