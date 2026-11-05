import { useState } from "react";
import { Card } from "../../components/ui";
import { useEventTicketing, type StaffTicket } from "./eventTicketingApi";
import { EventPanelPager } from "./EventPanelPager";
import { panelEmpty, panelField, panelInput } from "./eventPanelStyles";
import { EventTicketRow } from "./EventTicketRow";
import { useStaffChargesOn } from "./useStaffChargesOn";

export function EventTicketsPanel({ visible = true,  eventId, disabled = false }: { visible?: boolean;  eventId: number; disabled?: boolean }) {
  const [page, setPage] = useState(1);
  const { rows, create } = useEventTicketing<StaffTicket>(eventId, "ticket-types", page);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [audience, setAudience] = useState("public");
  const [capacity, setCapacity] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const error = rows.error || create.error;
  const chargesOn = useStaffChargesOn("events"); // #184: free events take no ticket price
  if (!visible) return null;
  return <section className="grid gap-4" aria-label="Event ticket types">
    <div><h3 className="title-section">Ticket types</h3>
      <p className="mt-1 text-sm text-muted">Member tickets are available only while membership is enabled and the attendee is an active member.{chargesOn ? " Quotes are fixed at registration." : ""}</p>
      {chargesOn ? null : <p className="mt-1 text-sm text-muted">Event charges are off in this space, so events are free.</p>}</div>
    <Card><form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); create.mutate({ name, amount, audience, capacity, sales_start_at: start ? new Date(start).toISOString() : null, sales_end_at: end ? new Date(end).toISOString() : null }, { onSuccess: () => setName("") }); }}>
      <label className={panelField}>Ticket name<input className={panelInput} required maxLength={100} value={name} disabled={disabled} onChange={(e) => setName(e.target.value)} /></label>
      {chargesOn ? <label className={panelField}>Price<input className={panelInput} type="number" min="0" step="0.01" required value={amount} disabled={disabled} onChange={(e) => setAmount(e.target.value)} /></label> : null}
      <label className={panelField}>Ticket audience<select className={panelInput} value={audience} disabled={disabled} onChange={(e) => setAudience(e.target.value)}><option value="public">All accounts</option><option value="member">Active members</option></select></label>
      <label className={panelField}>Ticket capacity (0 = unlimited)<input className={panelInput} type="number" min="0" value={capacity} disabled={disabled} onChange={(e) => setCapacity(Number(e.target.value))} /></label>
      <label className={panelField}>Sales start<input className={panelInput} type="datetime-local" value={start} disabled={disabled} onChange={(e) => setStart(e.target.value)} /></label>
      <label className={panelField}>Sales end<input className={panelInput} type="datetime-local" value={end} disabled={disabled} onChange={(e) => setEnd(e.target.value)} /></label>
      <button className="desk-button-primary justify-self-start" type="submit" disabled={disabled || create.isPending}>Add ticket type</button>
    </form></Card>
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
    {rows.isLoading ? <p role="status" className="text-sm text-muted">Loading ticket types…</p> : null}
    {rows.data?.results.length === 0 ? <p className={panelEmpty}>No ticket types yet.</p> : null}
    {rows.data?.results.length ? <ul className="grid gap-3">{rows.data.results.map((row) => <EventTicketRow key={row.id} row={row} eventId={eventId} disabled={disabled} />)}</ul> : null}
    <EventPanelPager page={page} setPage={setPage} previous={rows.data?.previous} next={rows.data?.next} />
  </section>;
}
