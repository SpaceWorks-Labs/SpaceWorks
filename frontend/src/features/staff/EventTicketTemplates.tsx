import { t } from "@lingui/core/macro";
import { useStaffChargesOn } from "./useStaffChargesOn";

export type TicketTemplate = { name: string; amount: string; audience: "public" | "member"; capacity: number; sales_start_at?: string | null; sales_end_at?: string | null };

/** Templates are copied when occurrences are materialized; existing sales stay intact. */
export function EventTicketTemplates({ value, onChange, disabled = false }: {
  value: TicketTemplate[]; onChange: (tickets: TicketTemplate[]) => void; disabled?: boolean;
}) {
  const chargesOn = useStaffChargesOn("events"); // #184: no ticket price input while events are free
  return <fieldset className="grid gap-2"><legend className="title-section">{t`Ticket templates`}</legend>
    {chargesOn ? null : <p className="text-sm text-muted">{t`Event charges are off in this space, so events are free.`}</p>}
    {value.map((ticket, index) => {
      const update = (changes: Partial<TicketTemplate>) => onChange(value.map((row, i) => i === index ? { ...row, ...changes } : row));
      return <div className="grid gap-2 rounded border border-line p-3" key={index}>
        <label className="grid gap-1 text-sm">{t`Ticket name`}<input className="desk-input" required maxLength={100} value={ticket.name} disabled={disabled} onChange={(e) => update({ name: e.target.value })} /></label>
        {chargesOn ? <label className="grid gap-1 text-sm">{t`Ticket price`}<input className="desk-input" type="number" min="0" step="any" value={ticket.amount} disabled={disabled} onChange={(e) => update({ amount: e.target.value })} /></label> : null}
        <label className="grid gap-1 text-sm">{t`Ticket audience`}<select className="desk-input" value={ticket.audience} disabled={disabled} onChange={(e) => update({ audience: e.target.value as TicketTemplate["audience"] })}><option value="public">{t`All accounts`}</option><option value="member">{t`Active members`}</option></select></label>
        <label className="grid gap-1 text-sm">{t`Ticket capacity`}<input className="desk-input" type="number" min="0" value={ticket.capacity} disabled={disabled} onChange={(e) => update({ capacity: Number(e.target.value) })} /></label>
        <label className="grid gap-1 text-sm">{t`Ticket sales start`}<input className="desk-input w-full min-w-0" type="datetime-local" value={ticket.sales_start_at ?? ""} disabled={disabled} onChange={(e) => update({ sales_start_at: e.target.value })} /></label>
        <label className="grid gap-1 text-sm">{t`Ticket sales end`}<input className="desk-input w-full min-w-0" type="datetime-local" value={ticket.sales_end_at ?? ""} disabled={disabled} onChange={(e) => update({ sales_end_at: e.target.value })} /></label>
        <button className="desk-button-danger" type="button" disabled={disabled} onClick={() => onChange(value.filter((_, i) => i !== index))}>{t`Remove ticket`}</button>
      </div>;
    })}
    <button className="desk-button" type="button" disabled={disabled} onClick={() => onChange([...value, { name: "", amount: "0.00", audience: "public", capacity: 0 }])}>{t`Add ticket template`}</button>
  </fieldset>;
}
