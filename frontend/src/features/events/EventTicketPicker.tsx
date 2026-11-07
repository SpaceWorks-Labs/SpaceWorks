import { t } from "@lingui/core/macro";
import type { EventTicket } from "./eventTicketTypes";

/** `showPrice` false (event charges off, #184) lists ticket names without any price. */
export function EventTicketPicker({ tickets, value, onChange, currency, disabled = false, showPrice = true }: {
  tickets: EventTicket[]; value: number | null; onChange: (id: number | null) => void;
  currency: string; disabled?: boolean; showPrice?: boolean;
}) {
  if (!tickets.length) return null;
  return <label className="grid gap-1 text-sm font-semibold">{t`Ticket type`}<select className="desk-input" required value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">{t`Choose a ticket`}</option>
      {tickets.map((ticket) => <option key={ticket.id} value={ticket.id}>
        {ticket.name}{showPrice ? ` · ${Number(ticket.amount) === 0 ? "Free" : `${ticket.amount} ${currency}`}` : ""}{ticket.spots_left === 0 ? t` · Waitlist` : ""}
      </option>)}
    </select>
  </label>;
}
