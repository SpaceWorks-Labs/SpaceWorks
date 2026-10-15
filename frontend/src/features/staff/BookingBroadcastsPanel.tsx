import { useState } from "react";
import { useBookingBroadcasts, type BookingCampaign } from "./bookingBroadcastsApi";

function localInput(date: Date) {
  const value = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return value.toISOString().slice(0, 16);
}

export function BookingBroadcastsPanel({ makerspaceId, spaceId }: { makerspaceId: number; spaceId: number }) {
  const [page, setPage] = useState(1);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState(() => localInput(new Date(Date.now() + 7 * 86400000)));
  const [statuses, setStatuses] = useState<BookingCampaign["statuses"]>(["confirmed"]);
  const [preview, setPreview] = useState<number | null>(null);
  const { history, compose, action } = useBookingBroadcasts(makerspaceId, spaceId, page);
  const error = history.error || compose.error || action.error;
  return <section className="grid gap-3" aria-label="Booker broadcasts">
    <h3 className="title-section">Email upcoming bookers</h3>
    <p className="text-sm text-muted">One email per account with a matching future reservation. Verified email, requester settings, preferences and quiet hours apply. Accepted emails cannot be recalled.</p>
    <form className="grid gap-3" onSubmit={(event) => {
      event.preventDefault();
      compose.mutate({ subject, body, statuses, window_start: start ? new Date(start).toISOString() : new Date().toISOString(), window_end: new Date(end).toISOString() },
        { onSuccess: () => { setSubject(""); setBody(""); setPage(1); } });
    }}>
      <label>Subject<input required maxLength={200} className="desk-input" value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
      <label>Message<textarea required maxLength={10000} className="desk-input min-h-28" value={body} onChange={(event) => setBody(event.target.value)} /></label>
      <p className="text-xs text-muted">Placeholders: {"{{ name }}, {{ resource_name }}, {{ booking_start }}, {{ booking_end }}, {{ booking_url }}"}. Booking links require sign-in. Times refer to the earliest matching reservation.</p>
      <label>Booking starts from (blank means now)<input type="datetime-local" className="desk-input" value={start} onChange={(event) => setStart(event.target.value)} /></label>
      <label>Booking starts before<input required type="datetime-local" className="desk-input" value={end} onChange={(event) => setEnd(event.target.value)} /></label>
      <p className="text-xs text-muted">Dates use your device timezone. Choose a future window ending within 366 days.</p>
      <fieldset><legend>Reservation states</legend><div className="flex gap-3">{(["confirmed", "pending"] as const).map((status) => <label key={status} className="flex gap-2">
        <input type="checkbox" checked={statuses.includes(status)} onChange={(event) => setStatuses(event.target.checked ? [...statuses, status] : statuses.filter((value) => value !== status))} />{status}
      </label>)}</div></fieldset>
      <button className="desk-button-primary w-fit" disabled={compose.isPending || !statuses.length}>{compose.isPending ? "Saving?" : "Save draft"}</button>
    </form>
    {history.isLoading ? <p role="status">Loading broadcasts?</p> : null}
    {error ? <p role="alert" className="text-danger">{error.message}</p> : null}
    <ul className="grid gap-3">{history.data?.results.map((row) => <li key={row.id} className="rounded-lg border border-line p-3">
      <p className="font-medium">{row.subject} ? <span className="text-sm text-muted">{row.status}</span></p>
      <p className="text-xs text-muted">{new Date(row.window_start).toLocaleString()} ? {new Date(row.window_end).toLocaleString()} ? {row.statuses.join(", ")}</p>
      <div className="mt-2 flex gap-2"><button type="button" className="desk-button" onClick={() => setPreview(preview === row.id ? null : row.id)}>Preview message</button>
        {row.status === "draft" ? <button type="button" className="desk-button-primary" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "queue" })}>Send broadcast</button> : null}
        {["draft", "queued", "sending"].includes(row.status) ? <button type="button" className="desk-button-danger" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "cancel" })}>Cancel broadcast</button> : null}
      </div>
      {preview === row.id ? <div className="mt-3 whitespace-pre-wrap text-sm"><p className="text-muted">Placeholders use current account and reservation data at delivery.</p>{row.body}</div> : null}
    </li>)}</ul>
    {history.data?.count === 0 ? <p className="text-sm text-muted">No broadcasts yet.</p> : null}
    <div className="flex gap-2"><button type="button" className="desk-button" disabled={!history.data?.previous} onClick={() => setPage(page - 1)}>Previous broadcasts</button><button type="button" className="desk-button" disabled={!history.data?.next} onClick={() => setPage(page + 1)}>Next broadcasts</button></div>
  </section>;
}
