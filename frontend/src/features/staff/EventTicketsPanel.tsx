import { useState } from "react";
import { useEventTicketing, type StaffTicket } from "./eventTicketingApi";

export function EventTicketsPanel({ visible = true,  eventId, disabled = false }: { visible?: boolean;  eventId: number; disabled?: boolean }) {
  const [page, setPage] = useState(1);
  const { rows, create } = useEventTicketing<StaffTicket>(eventId, "ticket-types", page);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("0.00");
  const [audience, setAudience] = useState("public");
  const [capacity, setCapacity] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  if (!visible) return null;
  return <section className="grid gap-3" aria-label="Event ticket types">
    <h3 className="title-section">Ticket types</h3>
    <p className="text-sm text-muted">Member tickets are available only while membership is enabled and the attendee is an active member. Quotes are fixed at registration.</p>
    <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); create.mutate({ name, amount, audience, capacity, sales_start_at: start ? new Date(start).toISOString() : null, sales_end_at: end ? new Date(end).toISOString() : null }, { onSuccess: () => setName("") }); }}>
      <label className="grid gap-1 text-sm">Ticket name<input className="desk-input" required maxLength={100} value={name} disabled={disabled} onChange={(e) => setName(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">Price<input className="desk-input" type="number" min="0" step="0.01" required value={amount} disabled={disabled} onChange={(e) => setAmount(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">Ticket audience<select className="desk-input" value={audience} disabled={disabled} onChange={(e) => setAudience(e.target.value)}><option value="public">All accounts</option><option value="member">Active members</option></select></label>
      <label className="grid gap-1 text-sm">Ticket capacity (0 = unlimited)<input className="desk-input" type="number" min="0" value={capacity} disabled={disabled} onChange={(e) => setCapacity(Number(e.target.value))} /></label>
      <label className="grid gap-1 text-sm">Sales start<input className="desk-input w-full min-w-0" type="datetime-local" value={start} disabled={disabled} onChange={(e) => setStart(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">Sales end<input className="desk-input w-full min-w-0" type="datetime-local" value={end} disabled={disabled} onChange={(e) => setEnd(e.target.value)} /></label>
      <button className="desk-button" disabled={disabled || create.isPending}>Add ticket type</button>
    </form>
    {rows.error || create.error ? <p role="alert">{(rows.error || create.error)?.message}</p> : null}
    {rows.isLoading ? <p role="status">Loading ticket types...</p> : null}
    <ul>{rows.data?.results.map((row) => <li key={row.id}>{row.name} · {row.amount} · {row.audience} · {row.capacity || "Unlimited"} places</li>)}</ul>
    <div className="flex flex-wrap gap-2"><button className="desk-button" disabled={!rows.data?.previous} onClick={() => setPage(page - 1)}>Previous</button><button className="desk-button" disabled={!rows.data?.next} onClick={() => setPage(page + 1)}>Next</button></div>
  </section>;
}
