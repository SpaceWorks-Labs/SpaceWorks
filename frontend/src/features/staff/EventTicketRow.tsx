import { useState } from "react";

import { ConfirmDialog, StatusPill } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { useTicketTypeChanges, type StaffTicket, type StaffTicketPatch } from "./eventTicketingApi";
import { panelField, panelInput } from "./eventPanelStyles";
import { eventErrorText } from "./eventUi";

const local = (value: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
};
const iso = (value: string) => value ? new Date(value).toISOString() : null;
const referenced = (error: unknown) => error instanceof StructuredApiError && error.status === 409 && error.code === "ticket_type_referenced";

/** One ticket type: inline edit, and delete that falls back to deactivating a type already in use. */
export function EventTicketRow({ row, eventId, disabled }: { row: StaffTicket; eventId: number; disabled: boolean }) {
  const { update, remove } = useTicketTypeChanges(eventId);
  const [editing, setEditing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [draft, setDraft] = useState(() => ({ name: row.name, amount: row.amount, audience: row.audience, capacity: row.capacity,
    start: local(row.sales_start_at), end: local(row.sales_end_at), active: row.is_active ?? true }));
  const active = row.is_active ?? true;
  const used = (row.registration_count ?? 0) > 0;
  const open = () => { update.reset(); remove.reset(); setDraft({ name: row.name, amount: row.amount, audience: row.audience, capacity: row.capacity, start: local(row.sales_start_at), end: local(row.sales_end_at), active }); setEditing(true); };
  // Only changed fields travel, so an untouched price on a ticket in use never trips the 409.
  const save = () => {
    const next: StaffTicketPatch = { name: draft.name, amount: draft.amount, audience: draft.audience, capacity: draft.capacity,
      sales_start_at: iso(draft.start), sales_end_at: iso(draft.end), is_active: draft.active };
    const current: StaffTicketPatch = { name: row.name, amount: row.amount, audience: row.audience, capacity: row.capacity,
      sales_start_at: iso(local(row.sales_start_at)), sales_end_at: iso(local(row.sales_end_at)), is_active: active };
    const patch = Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== current[key as keyof StaffTicketPatch])) as StaffTicketPatch;
    if (!Object.keys(patch).length) { setEditing(false); return; }
    update.mutate({ id: row.id, patch }, { onSuccess: () => setEditing(false) });
  };
  const deactivate = () => update.mutate({ id: row.id, patch: { is_active: false } }, { onSuccess: () => remove.reset() });
  const name = row.name || `Ticket ${row.id}`;
  return <li className="grid min-w-0 gap-3 rounded-2xl border border-line bg-panel p-4">
    <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
      <div className="min-w-0"><p className="title-section break-words">{row.name}</p>
        <p className="mt-1 text-sm tabular-nums text-muted">{row.amount} · {row.audience} · {row.capacity || "Unlimited"} places · {row.registration_count ?? 0} registered</p></div>
      <div className="flex flex-wrap items-center gap-2">
        {!active ? <StatusPill label="Inactive" /> : null}
        {!disabled && !editing ? <><button className="desk-button" type="button" onClick={open}>Edit {name}</button>
          <button className="desk-button-danger-outline" type="button" disabled={remove.isPending} onClick={() => { remove.reset(); setConfirming(true); }}>Delete {name}</button></> : null}
      </div>
    </div>
    {editing ? <form className="grid gap-4 sm:grid-cols-2" aria-label={`Edit ${name}`} onSubmit={(e) => { e.preventDefault(); save(); }}>
      <label className={panelField}>Ticket name<input className={panelInput} required maxLength={100} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
      <label className={panelField}>Price<input className={panelInput} type="number" min="0" step="0.01" required value={draft.amount} disabled={used} onChange={(e) => setDraft({ ...draft, amount: e.target.value })} /></label>
      <label className={panelField}>Ticket audience<select className={panelInput} value={draft.audience} disabled={used} onChange={(e) => setDraft({ ...draft, audience: e.target.value as StaffTicket["audience"] })}><option value="public">All accounts</option><option value="member">Active members</option></select></label>
      <label className={panelField}>Ticket capacity (0 = unlimited)<input className={panelInput} type="number" min="0" value={draft.capacity} onChange={(e) => setDraft({ ...draft, capacity: Number(e.target.value) })} /></label>
      <label className={panelField}>Sales start<input className={panelInput} type="datetime-local" value={draft.start} onChange={(e) => setDraft({ ...draft, start: e.target.value })} /></label>
      <label className={panelField}>Sales end<input className={panelInput} type="datetime-local" value={draft.end} onChange={(e) => setDraft({ ...draft, end: e.target.value })} /></label>
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink sm:col-span-2"><input type="checkbox" checked={draft.active} onChange={(e) => setDraft({ ...draft, active: e.target.checked })} />Available for new registrations</label>
      {used ? <p className="text-sm text-muted sm:col-span-2">Price and audience are fixed because registrations already use this ticket type.</p> : null}
      <div className="flex flex-wrap justify-end gap-2 sm:col-span-2">
        <button className="desk-button" type="button" disabled={update.isPending} onClick={() => setEditing(false)}>Cancel</button>
        <button className="desk-button-primary" type="submit" disabled={update.isPending}>{update.isPending ? "Saving…" : "Save ticket type"}</button>
      </div>
    </form> : null}
    {update.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(update.error)}</p> : null}
    {remove.error ? <div role="alert" className="grid justify-items-start gap-2 text-sm text-danger">
      <p>{referenced(remove.error) ? (remove.error as StructuredApiError).detail ?? "Registrations use this ticket type, so it can't be deleted." : eventErrorText(remove.error)}</p>
      {referenced(remove.error) && active ? <button className="desk-button" type="button" disabled={update.isPending} onClick={deactivate}>Deactivate instead</button> : null}
    </div> : null}
    <ConfirmDialog open={confirming} title="Delete ticket type" tone="danger" confirmLabel="Delete ticket type" pending={remove.isPending}
      message={`Delete ${name}? A ticket type that registrations already use can only be deactivated.`}
      onCancel={() => setConfirming(false)} onConfirm={() => remove.mutate(row.id, { onSettled: () => setConfirming(false) })} />
  </li>;
}
