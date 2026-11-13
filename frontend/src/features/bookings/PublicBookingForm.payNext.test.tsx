import { render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PublicBookingForm } from "./PublicBookingForm";
import type { PublicBookableSpace } from "./publicBookingsApi";

const { state } = vi.hoisted(() => ({ state: { data: undefined as unknown, owes: false } }));
vi.mock("./publicBookingsApi", () => ({
  useSubmitPublicBooking: () => ({ error: null, data: state.data, isPending: false, mutate: vi.fn() }),
}));
// The real preview only quotes while booking charges are on; here it reports what the quote owed.
vi.mock("../payments/PricePreview", () => ({
  PricePreview: ({ onOwes }: { onOwes?: (owes: boolean) => void }) => {
    useEffect(() => { onOwes?.(state.owes); }, [onOwes]);
    return null;
  },
}));

const space = { public_token: "room", name: "Laser bay", approval_mode: "instant", custom_form: null } as unknown as PublicBookableSpace;

function book(owes: boolean, status: "confirmed" | "pending", server: Record<string, unknown> = {}) {
  state.owes = owes;
  state.data = undefined;
  const view = render(<PublicBookingForm makerspaceSlug="lab" space={space} showCalendar={false} />);
  state.data = { status, ...server };
  view.rerender(<PublicBookingForm makerspaceSlug="lab" space={space} showCalendar={false} />);
}

afterEach(() => { state.data = undefined; });

describe("booking success says how to pay", () => {
  it("points a confirmed paid booking at Payments with both roads", () => {
    book(true, "confirmed");
    expect(screen.getByRole("link", { name: "Payments" })).toHaveAttribute("href", "/m/lab/member/payments");
    expect(screen.getByText(/Pay online there when it is offered, or pay at the space\./)).toBeVisible();
  });

  it("tells a pending paid request nothing is owed until approval", () => {
    book(true, "pending");
    expect(screen.getByText("You will only be charged if staff approve it.")).toBeVisible();
    expect(screen.queryByRole("link", { name: "Payments" })).toBeNull();
  });

  it("says nothing about payment for a free booking", () => {
    book(false, "confirmed");
    expect(screen.getByText("Space booked")).toBeVisible();
    expect(screen.queryByText(/Pay online there/)).toBeNull();
    expect(screen.queryByText(/only be charged/)).toBeNull();
  });
});

describe("the server's recorded amount wins over the client quote", () => {
  it("shows the pay step from amount_due even when the live quote said free", () => {
    book(false, "confirmed", { amount_due: "12.50", currency: "usd", pay_online: true });
    expect(screen.getByRole("link", { name: "Payments" })).toBeVisible();
  });

  it("hides it when the server recorded nothing owed", () => {
    book(true, "confirmed", { amount_due: null, currency: null, pay_online: false });
    expect(screen.queryByRole("link", { name: "Payments" })).toBeNull();
  });
});
