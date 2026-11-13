import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Booking } from "../bookingsApi";
import { RequestedPrice } from "./RequestedPrice";

const base = { id: 1, status: "pending", requested_price: { total: "9.00", currency: "usd", discount_total: "0" } } as unknown as Booking;

describe("RequestedPrice", () => {
  it("shows the frozen price on a pending booking", () => {
    render(<RequestedPrice booking={base} />);
    expect(screen.getByText("$9.00")).toBeInTheDocument();
    expect(screen.getByText("Approval uses this price if booking charges apply.")).toBeInTheDocument();
  });
  it("labels a zero frozen price as free without promising a charge", () => {
    render(<RequestedPrice booking={{ ...base, requested_price: { total: "0.00", currency: "usd" } }} />);
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
  });
  it("renders nothing without a frozen price or once decided", () => {
    const { container, rerender } = render(<RequestedPrice booking={{ ...base, requested_price: null }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<RequestedPrice booking={{ ...base, status: "confirmed" } as Booking} />);
    expect(container).toBeEmptyDOMElement();
  });
});
