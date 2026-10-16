import { useState } from "react";
import { useEventTicketing, type EventCode } from "./eventTicketingApi";
import { EventBulkInvites } from "./EventBulkInvites";

export function EventInvitesPanel({ visible = true,  eventId, disabled = false }: { visible?: boolean;  eventId: number; disabled?: boolean }) {
  const [page, setPage] = useState(1);
  const { rows, create, revoke } = useEventTicketing<EventCode>(eventId, "invites", page);
  const [email, setEmail] = useState("");
  const [limit, setLimit] = useState(1);
  const [expires, setExpires] = useState("");
  const [code, setCode] = useState("");
  const error = rows.error || create.error || revoke.error;
  if (!visible) return null;
  return <section className="grid gap-3" aria-label="Event invitations">
    <h3 className="title-section">Invitations</h3>
    <EventBulkInvites eventId={eventId} disabled={disabled} />
    <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); create.mutate({ email, max_uses: limit, expires_at: expires ? new Date(expires).toISOString() : null }, { onSuccess: (row) => setCode(row.code ?? "") }); }}>
      <label className="grid gap-1 text-sm">Recipient email (optional)<input className="desk-input" type="email" value={email} disabled={disabled} onChange={(e) => setEmail(e.target.value)} /></label>
      <label className="grid gap-1 text-sm">Maximum uses<input className="desk-input" type="number" min="1" required value={limit} disabled={disabled} onChange={(e) => setLimit(Number(e.target.value))} /></label>
      <label className="grid gap-1 text-sm">Expires<input className="desk-input w-full min-w-0" type="datetime-local" value={expires} disabled={disabled} onChange={(e) => setExpires(e.target.value)} /></label>
      <button className="desk-button" disabled={disabled || create.isPending}>Create invitation</button>
    </form>
    {code ? <div role="status" className="grid justify-items-start gap-2"><p>Copy this code now. It is shown once.</p><output className="break-all code-text">{code}</output><button className="desk-button" onClick={() => setCode("")}>Hide code</button></div> : null}
    {error ? <p role="alert">{error.message}</p> : null}
    {rows.isLoading ? <p role="status">Loading invitations…</p> : null}
    <ul>{rows.data?.results.map((row) => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 py-2">Invitation {row.id} · {row.uses}/{row.max_uses} uses {row.revoked_at ? "· Revoked" : <button className="desk-button-danger" disabled={disabled || revoke.isPending} onClick={() => revoke.mutate(row.id)}>Revoke invitation {row.id}</button>}</li>)}</ul>
    <div className="flex flex-wrap gap-2"><button className="desk-button" disabled={!rows.data?.previous} onClick={() => setPage(page - 1)}>Previous</button><button className="desk-button" disabled={!rows.data?.next} onClick={() => setPage(page + 1)}>Next</button></div>
  </section>;
}
