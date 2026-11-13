import { t } from "@lingui/core/macro";
import { formatMoney, formatPrice } from "../../lib/money";
import type { EventTicket } from "./eventTicketTypes";

/** Display the configured price with the host's currency on public catalogues. */
export function EventPrice({ amount, currency, tickets = [], ticketRequired = false, inline = false }: { amount: string; currency: string; tickets?: EventTicket[]; ticketRequired?: boolean; inline?: boolean }) {
  const prices = tickets.map((ticket) => Number(ticket.amount));
  const lowest = prices.length ? Math.min(...prices) : Number(amount);
  const highest = prices.length ? Math.max(...prices) : lowest;
  const price = formatPrice(lowest, currency);
  // A free tier beside paid ones reads as a range ("Free – ₹25.00"), never "From Free".
  const label = highest === lowest ? price
    : lowest <= 0 ? t`Free – ${formatMoney(highest, currency)}` : t`From ${price}`;
  const text = ticketRequired && !tickets.length ? t`No tickets available` : label;
  if (inline) return <span className="tabular-nums font-semibold text-ink">{text}</span>;
  return <dl><dt className="eyebrow">{t`Price`}</dt><dd className="tabular-nums font-semibold text-ink">{text}</dd></dl>;
}
