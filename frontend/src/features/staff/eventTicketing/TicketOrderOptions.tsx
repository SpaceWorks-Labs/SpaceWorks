import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useEventTicketing, useTicketTypeChanges, type StaffTicket, type TicketOrderFields as OrderFields } from "../eventTicketingApi";
import { panelField, panelInput, panelRow } from "../eventPanelStyles";

type OrderTicket = StaffTicket & Partial<OrderFields>;

function OptionsRow({ ticket, eventId, disabled }: { ticket: OrderTicket; eventId: number; disabled: boolean }) {
  const { update } = useTicketTypeChanges(eventId);
  const [values, setValues] = useState<OrderFields>({ tier_group: ticket.tier_group ?? "", tier_rank: ticket.tier_rank ?? 0,
    pricing_mode: ticket.pricing_mode ?? "fixed", min_amount: ticket.min_amount ?? "0.00", seats_per_ticket: ticket.seats_per_ticket ?? 1,
    is_hidden: ticket.is_hidden ?? false, min_quantity: ticket.min_quantity ?? 1, per_order_limit: ticket.per_order_limit ?? 0 });
  const set = <K extends keyof OrderFields>(key: K, value: OrderFields[K]) => setValues(current => ({ ...current, [key]: value }));
  return <li className={`${panelRow} grid`}>
    <form className="grid w-full gap-3 sm:grid-cols-2" aria-label={t`Order options for ${ticket.name}`}
      onSubmit={event => { event.preventDefault(); update.mutate({ id: ticket.id, patch: values }); }}>
      <p className="font-semibold text-ink sm:col-span-2">{ticket.name}</p>
      <label className={panelField}>{t`Tier group`}<input className={panelInput} value={values.tier_group} disabled={disabled} onChange={event => set("tier_group", event.target.value)} /></label>
      <label className={panelField}>{t`Tier order`}<input className={panelInput} type="number" min="0" value={values.tier_rank} disabled={disabled} onChange={event => set("tier_rank", Number(event.target.value))} /></label>
      <label className={panelField}>{t`Pricing`}<select className={panelInput} value={values.pricing_mode} disabled={disabled}
        onChange={event => set("pricing_mode", event.target.value as OrderFields["pricing_mode"])}><option value="fixed">{t`Fixed price`}</option><option value="pwyw">{t`Pay what you want`}</option></select></label>
      {values.pricing_mode === "pwyw" ? <label className={panelField}>{t`Lowest amount`}<input className={panelInput} type="number" min="0" step="0.01" value={values.min_amount} disabled={disabled} onChange={event => set("min_amount", event.target.value)} /></label> : null}
      <label className={panelField}>{t`People per ticket`}<input className={panelInput} type="number" min="1" value={values.seats_per_ticket} disabled={disabled} onChange={event => set("seats_per_ticket", Number(event.target.value))} /></label>
      <label className={panelField}>{t`Fewest per order`}<input className={panelInput} type="number" min="1" value={values.min_quantity} disabled={disabled} onChange={event => set("min_quantity", Number(event.target.value))} /></label>
      <label className={panelField}>{t`Most per order (0 = no limit)`}<input className={panelInput} type="number" min="0" value={values.per_order_limit} disabled={disabled} onChange={event => set("per_order_limit", Number(event.target.value))} /></label>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={values.is_hidden} disabled={disabled} onChange={event => set("is_hidden", event.target.checked)} />{t`Hidden: sold only with an access code`}</label>
      {update.error ? <p role="alert" className="text-sm text-danger sm:col-span-2">{update.error.message}</p> : null}
      <button className="desk-button justify-self-start" type="submit" disabled={disabled || update.isPending}>{t`Save options`}</button>
    </form>
  </li>;
}

/** G29: tiers, pay-what-you-want, group tickets, hidden tickets and quantity rules per ticket type. */
export function TicketOrderOptions({ eventId, disabled = false }: { eventId: number; disabled?: boolean }) {
  const { rows } = useEventTicketing<OrderTicket>(eventId, "ticket-types", 1);
  if (!rows.data?.results.length) return <p className="text-sm text-muted">{t`Add a ticket type first.`}</p>;
  return <ul className="grid gap-3" aria-label={t`Ticket order options`}>
    {rows.data.results.map(ticket => <OptionsRow key={ticket.id} ticket={ticket} eventId={eventId} disabled={disabled} />)}
  </ul>;
}
