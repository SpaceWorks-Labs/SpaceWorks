import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopCartDrawer } from "./ShopCartDrawer";
import type { ShopSummary } from "./shopApi";
import type { CartLine } from "./useShopCart";

// MOD-3B frontend states for the basket sheet: closed, empty, editing lines, keyboard close, checkout hand-off.
const checkout = vi.hoisted(() => vi.fn());
vi.mock("./ShopCheckout", () => ({
  ShopCheckout: (props: { lines: CartLine[]; session: string; onPlaced: () => void }) => {
    checkout(props);
    return <button type="button" onClick={props.onPlaced}>place-order ({props.lines.length} lines, {props.session})</button>;
  },
}));
vi.mock("./useShopSpace", () => ({ useMemberSession: () => ["anonymous", vi.fn()] }));

const shop = { name: "Lab", currency: "inr" } as unknown as ShopSummary;
const pen: CartLine = { variantId: 11, quantity: 2, label: "Pen", price: "50.00", productSlug: "pen", max: 3 };
const cart = (lines: CartLine[] = [pen]) => ({
  lines, count: lines.length, add: vi.fn(), setQuantity: vi.fn(), remove: vi.fn(), clear: vi.fn(),
});

function show(open: boolean, theCart = cart(), onClose = vi.fn()) {
  render(<ShopCartDrawer open={open} onClose={onClose} slug="lab" shop={shop} cart={theCart} path={(part = "") => `/m/lab/${part}`} />);
  return { theCart, onClose };
}

beforeEach(() => { checkout.mockClear(); });

describe("ShopCartDrawer", () => {
  it("closed: renders nothing and does not mount checkout", () => {
    show(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(checkout).not.toHaveBeenCalled();
  });

  it("empty basket: says so while checkout still receives zero lines", () => {
    show(true, cart([]));
    expect(screen.getByRole("dialog", { name: "Your basket" })).toBeInTheDocument();
    expect(screen.getByText("Your basket is empty.")).toBeInTheDocument();
    expect(checkout).toHaveBeenLastCalledWith(expect.objectContaining({ lines: [], session: "anonymous" }));
  });

  it("lists lines with the unit price and edits them through the cart: fewer, more, remove", () => {
    const { theCart } = show(true);
    expect(screen.getByText("Pen")).toBeInTheDocument();
    expect(screen.getByText("₹50.00 each")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "One fewer Pen" }));
    expect(theCart.setQuantity).toHaveBeenCalledWith(11, 1);
    fireEvent.click(screen.getByRole("button", { name: "One more Pen" }));
    expect(theCart.setQuantity).toHaveBeenCalledWith(11, 3);
    fireEvent.click(screen.getByRole("button", { name: "Remove Pen" }));
    expect(theCart.remove).toHaveBeenCalledWith(11);
  });

  it("a line at its per-order maximum cannot be raised, and says why", () => {
    show(true, cart([{ ...pen, quantity: 3 }]));
    const more = screen.getByRole("button", { name: "One more Pen" });
    expect(more).toBeDisabled();
    expect(more).toHaveAttribute("title", "At most 3 per order");
  });

  it("keyboard: Escape and the close button both call onClose", () => {
    const { onClose } = show(true);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("an order placed in checkout clears the basket", () => {
    const { theCart } = show(true);
    fireEvent.click(screen.getByRole("button", { name: /place-order/ }));
    expect(theCart.clear).toHaveBeenCalledTimes(1);
  });
});
