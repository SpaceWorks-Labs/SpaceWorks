import { t } from "@lingui/core/macro";
import type { Booking } from "../bookingsApi";
import { formatMoney } from "../paymentsApi";

/**
 * #159: the price frozen when a booking awaiting approval was requested. Approval uses
 * this price when booking charges apply. Money formatting matches `StaffPriceConfirmation`.
 */
export function RequestedPrice({ booking }: { booking: Booking }) {
  const price = booking.requested_price;
  if (booking.status !== "pending" || !price || price.total == null) return null;
  const currency = price.currency ?? "";
  const money = (value: string) => (currency ? formatMoney(value, currency) : value);
  const discount = price.discount_total && Number(price.discount_total) > 0 ? money(price.discount_total) : "";
  const saved = discount ? t`(member discount ${discount})` : "";
  return (
    <span className="mt-1 block text-sm text-muted">
      {t`Requested price:`}{" "}<span className="font-medium text-ink">{Number(price.total) > 0 ? money(price.total) : t`Free`}</span>{saved ? <> {saved}</> : null} <span>{t`Approval uses this price if booking charges apply.`}</span></span>
  );
}
