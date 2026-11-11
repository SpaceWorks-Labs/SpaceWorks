import { t } from "@lingui/core/macro";

import { StructuredApiError } from "../../lib/api";
import { formatMoney } from "./paymentsApi";
import type { StaffBookingQuote } from "./staffBookingApi";
import { IncludedHoursLine } from "../payments/IncludedHoursLine";

/** The fresh confirmation a 409 `price_changed` from a staff create carries, if any. */
export function changedConfirmation(error: unknown): StaffBookingQuote | null {
  if (!(error instanceof StructuredApiError) || error.code !== "price_changed") return null;
  const next = (error.body as { confirmation?: StaffBookingQuote }).confirmation;
  return next && typeof next.price_confirmation === "string" ? next : null;
}

/**
 * Decision 216: the room (or machine time) price staff confirm before booking for a member.
 * The server re-verifies it under the booking lock, so this shows exactly what will be
 * charged. Copy and money formatting match `pricing/RequestedPrice` for bookings that wait
 * for approval.
 */
export function StaffPriceConfirmation({ confirmation, approval, machine = false }:
  { confirmation: StaffBookingQuote; approval: boolean; machine?: boolean }) {
  const price = confirmation.quote;
  let label: string;
  if (confirmation.charges === "off" || !price) label = t`Booking charges are off in this space, so this booking is free.`;
  else if (Number(price.total) > 0) {
    const amount = formatMoney(price.total, price.currency);
    label = machine ? t`Machine time price: ${amount}` : t`Room price: ${amount}`;
  }
  else label = machine ? t`Machine time price: Free` : t`Room price: Free`;
  const discount = price && Number(price.discount_total) > 0 ? formatMoney(price.discount_total, price.currency) : "";
  return (
    <div className="grid gap-1 rounded-md border border-line p-2 text-sm" role="status">
      <span className="font-medium text-ink">{label}</span>
      {discount ? <span className="text-muted">{t`(member discount ${discount})`}</span> : null}
      <IncludedHoursLine info={confirmation.included_hours ?? price?.included_hours} />
      {approval && confirmation.charges === "tracked"
        ? <span className="text-muted">{t`Approval uses this price if booking charges apply.`}</span> : null}
    </div>
  );
}
