import type { Booking } from "../bookingsApi";

/**
 * #159: the price frozen when a booking awaiting approval was requested. Approval charges
 * exactly this, never a re-quote; a booking without one is charged at the approval-day price.
 */
export function RequestedPrice({ booking }: { booking: Booking }) {
  const price = booking.requested_price;
  if (booking.status !== "pending" || !price || price.total == null) return null;
  const amount = `${(price.currency ?? "").toUpperCase()} ${price.total}`.trim();
  const saved = price.discount_total && Number(price.discount_total) > 0
    ? ` (member discount ${(price.currency ?? "").toUpperCase()} ${price.discount_total})` : "";
  return (
    <span className="mt-1 block text-sm text-muted">
      Requested price: <span className="font-medium text-ink">{Number(price.total) > 0 ? amount : "Free"}</span>{saved}
      {" "}&middot; approving charges this price
    </span>
  );
}
