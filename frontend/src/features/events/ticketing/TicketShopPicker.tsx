import { Minus, Plus, Ticket } from "lucide-react";
import { money, type ShopAddon, type ShopTicket } from "./ticketingApi";

export type Basket = {
  tickets: Record<number, number>;
  amounts: Record<number, string>;
  addons: Record<number, { quantity: number; variantId: number | null }>;
};

export const emptyBasket = (): Basket => ({ tickets: {}, amounts: {}, addons: {} });

function Stepper({ label, value, max, onChange }: { label: string; value: number; max: number; onChange: (next: number) => void }) {
  return <div className="flex items-center gap-2" role="group" aria-label={label}>
    <button type="button" className="desk-button px-2" aria-label={`Fewer ${label}`} disabled={value <= 0}
      onClick={() => onChange(Math.max(value - 1, 0))}><Minus aria-hidden="true" size={16} /></button>
    <output className="w-8 text-center font-semibold tabular-nums" aria-live="polite">{value}</output>
    <button type="button" className="desk-button px-2" aria-label={`More ${label}`} disabled={value >= max}
      onClick={() => onChange(Math.min(value + 1, max))}><Plus aria-hidden="true" size={16} /></button>
  </div>;
}

function ticketMax(ticket: ShopTicket, orderMax: number) {
  const limits = [orderMax, ticket.per_order_limit || orderMax];
  if (ticket.spots_left != null) limits.push(Math.floor(ticket.spots_left / Math.max(ticket.seats_per_ticket, 1)));
  if (ticket.audience === "member") limits.push(1);
  return Math.max(Math.min(...limits), 0);
}

/** Ticket types and add-ons with quantity steppers. Prices are the server's; nothing is priced here.
 * `free` (#184: event charges off in this space) shows no price at all; everything is free. */
export function TicketShopPicker({ tickets, addons, currency, orderMax, basket, onChange, free = false }: {
  tickets: ShopTicket[]; addons: ShopAddon[]; currency: string; orderMax: number;
  basket: Basket; onChange: (next: Basket) => void; free?: boolean;
}) {
  const setTicket = (id: number, quantity: number) => onChange({ ...basket, tickets: { ...basket.tickets, [id]: quantity } });
  const setAddon = (id: number, patch: Partial<{ quantity: number; variantId: number | null }>) => onChange({
    ...basket, addons: { ...basket.addons, [id]: { ...(basket.addons[id] ?? { quantity: 0, variantId: null }), ...patch } } });
  return <div className="grid gap-4">
    <ul className="grid gap-3" aria-label="Tickets">
      {tickets.map(ticket => <li key={ticket.id} className="grid gap-2 rounded-card border border-line p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="grid gap-0.5">
            <span className="flex items-center gap-2 font-semibold text-ink"><Ticket aria-hidden="true" size={18} />{ticket.name}</span>
            <span className="text-sm text-muted">
              {free ? "Free" : ticket.pricing_mode === "pwyw" ? `Pay what you want, from ${money(ticket.min_amount, currency)}` : money(ticket.amount, currency)}
              {ticket.seats_per_ticket > 1 ? ` · admits ${ticket.seats_per_ticket}` : ""}
              {ticket.min_quantity > 1 ? ` · at least ${ticket.min_quantity}` : ""}
              {ticket.spots_left != null && !ticket.sold_out ? ` · ${ticket.spots_left} left` : ""}
            </span>
            {ticket.next_tier && !free ? <span className="text-xs text-muted">Next: {ticket.next_tier.name} at {money(ticket.next_tier.amount, currency)}</span> : null}
          </div>
          {ticket.sold_out ? <span className="text-sm font-semibold text-muted">Sold out</span>
            : <Stepper label={ticket.name} value={basket.tickets[ticket.id] ?? 0} max={ticketMax(ticket, orderMax)}
              onChange={next => setTicket(ticket.id, next)} />}
        </div>
        {!free && ticket.pricing_mode === "pwyw" && (basket.tickets[ticket.id] ?? 0) > 0 ? <label className="grid gap-1 text-sm font-semibold">
          Amount per ticket ({currency.toUpperCase()})
          <input className="desk-input" inputMode="decimal" value={basket.amounts[ticket.id] ?? ticket.amount}
            onChange={event => onChange({ ...basket, amounts: { ...basket.amounts, [ticket.id]: event.target.value } })} />
        </label> : null}
      </li>)}
    </ul>
    {addons.length ? <fieldset className="grid gap-3">
      <legend className="eyebrow">Add-ons</legend>
      {addons.map(addon => {
        const current = basket.addons[addon.id] ?? { quantity: 0, variantId: null };
        return <div key={addon.id} className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-line p-3">
          <span className="grid gap-0.5"><span className="font-semibold text-ink">{addon.name}</span>
            <span className="text-sm text-muted">{free ? "Free" : money(addon.amount, currency)}{addon.description ? ` · ${addon.description}` : ""}</span></span>
          {addon.sold_out ? <span className="text-sm font-semibold text-muted">Sold out</span> : <div className="flex items-center gap-2">
            {addon.variants.length ? <label className="text-sm">Option
              <select className="desk-input ml-2" value={current.variantId ?? ""} onChange={event => setAddon(addon.id, { variantId: event.target.value ? Number(event.target.value) : null })}>
                <option value="">Choose</option>
                {addon.variants.map(variant => <option key={variant.id} value={variant.id} disabled={variant.sold_out}>{variant.label}{variant.sold_out ? " (sold out)" : ""}</option>)}
              </select></label> : null}
            <Stepper label={addon.name} value={current.quantity} max={addon.per_order_limit || 10} onChange={next => setAddon(addon.id, { quantity: next })} />
          </div>}
        </div>;
      })}
    </fieldset> : null}
  </div>;
}

export function basketRequest(basket: Basket, tickets: ShopTicket[]) {
  return {
    tickets: tickets.filter(ticket => (basket.tickets[ticket.id] ?? 0) > 0).map(ticket => ({
      ticket_type_id: ticket.id, quantity: basket.tickets[ticket.id],
      ...(ticket.pricing_mode === "pwyw" ? { amount: basket.amounts[ticket.id] ?? ticket.amount } : {}),
    })),
    addons: Object.entries(basket.addons).filter(([, item]) => item.quantity > 0).map(([id, item]) => ({
      addon_id: Number(id), variant_id: item.variantId, quantity: item.quantity })),
  };
}
