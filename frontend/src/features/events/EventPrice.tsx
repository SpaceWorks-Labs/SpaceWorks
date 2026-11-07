import { t } from "@lingui/core/macro";
import type { EventTicket } from "./eventTicketTypes";

/** Display the configured price with the host's currency on public catalogues. */
export function EventPrice({ amount, currency, tickets = [], ticketRequired = false, inline = false }: { amount: string; currency: string; tickets?: EventTicket[]; ticketRequired?: boolean; inline?: boolean }) {
  const prices = tickets.map((ticket) => Number(ticket.amount));
  const lowest = prices.length ? Math.min(...prices) : Number(amount);
  const prefix = prices.length && Math.max(...prices) !== lowest ? "From " : "";
  const label = lowest === 0 ? "Free" : `${lowest.toFixed(2)} ${currency.toUpperCase()}`;
  if (inline) return <span className="tabular-nums font-semibold text-ink">{ticketRequired && !tickets.length ? t`No tickets available` : `${prefix}${label}`}</span>;
  return <dl><dt className="eyebrow">{t`Price`}</dt><dd className="tabular-nums font-semibold text-ink">
    {ticketRequired && !tickets.length ? t`No tickets available` : `${prefix}${label}`}
  </dd></dl>;
}
