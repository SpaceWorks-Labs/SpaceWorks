import { useState } from "react";
import { useEventBroadcasts } from "./eventCommunicationsApi";
import { eventErrorText } from "./eventUi";

const STATUSES = ["registered", "attended", "pending_approval", "waitlisted", "rejected", "cancelled"];

export function EventBroadcastsPanel({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const [page, setPage] = useState(1);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [statuses, setStatuses] = useState(["registered", "attended"]);
  const [attendance, setAttendance] = useState("any");
  const [preview, setPreview] = useState<number | null>(null);
  const { history, compose, action } = useEventBroadcasts(makerspaceId, eventId, page);
  const error = history.error || compose.error || action.error;
  return <section className="grid gap-3" aria-label="Event broadcasts">
    <h3 className="title-section">Email registrants</h3>
    <p className="text-sm text-muted">Verified email only. Member preferences and quiet hours apply. You can cancel queued sends; accepted emails cannot be recalled.</p>
    <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); compose.mutate({ subject, body, statuses, attendance },
      { onSuccess: () => { setSubject(""); setBody(""); setPage(1); } }); }}>
      <label>Subject<input required maxLength={200} className="desk-input" value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
      <label>Message<textarea required maxLength={10000} className="desk-input min-h-28" value={body} onChange={(e) => setBody(e.target.value)} /></label>
      <p className="text-xs text-muted">Placeholders: {"{{ name }}, {{ event_title }}, {{ event_date }}, {{ event_location }}, {{ ticket_url }}"}. Ticket links require sign-in.</p>
      <fieldset><legend className="font-medium">Registration states</legend><div className="flex flex-wrap gap-3">{STATUSES.map((status) => <label key={status} className="flex gap-2"><input type="checkbox" checked={statuses.includes(status)} onChange={(e) => setStatuses(e.target.checked ? [...statuses, status] : statuses.filter((s) => s !== status))} />{status.replace(/_/g, " ")}</label>)}</div></fieldset>
      <label>Attendance<select className="desk-input" value={attendance} onChange={(e) => setAttendance(e.target.value)}><option value="any">Any</option><option value="attended">Attended</option><option value="not_attended">Not attended</option></select></label>
      <button className="desk-button-primary w-fit" disabled={compose.isPending || !statuses.length}>{compose.isPending ? "Saving…" : "Save draft"}</button>
    </form>
    {history.isLoading ? <p role="status">Loading broadcasts…</p> : null}
    {error ? <p className="text-danger" role="alert">{eventErrorText(error)}</p> : null}
    <ul className="grid gap-3">{history.data?.results.map((row) => <li key={row.id} className="rounded-lg border border-border p-3">
      <p className="font-medium">{row.subject} <span className="text-sm text-muted">· {row.status}</span></p>
      <div className="mt-2 flex gap-2"><button className="desk-button" onClick={() => setPreview(preview === row.id ? null : row.id)}>Preview message</button>
        {row.status === "draft" ? <button className="desk-button-primary" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "queue" })}>Send broadcast</button> : null}
        {["draft", "queued", "sending"].includes(row.status) ? <button className="desk-button-danger" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "cancel" })}>Cancel broadcast</button> : null}</div>
      {preview === row.id ? <div className="mt-3 whitespace-pre-wrap text-sm"><p className="text-muted">Placeholders are filled with current participant data at delivery.</p>{row.body}</div> : null}
    </li>)}</ul>
    {history.data?.count === 0 ? <p className="text-sm text-muted">No broadcasts yet.</p> : null}
    <div className="flex gap-2"><button className="desk-button" disabled={!history.data?.previous} onClick={() => setPage(page - 1)}>Previous broadcasts</button><button className="desk-button" disabled={!history.data?.next} onClick={() => setPage(page + 1)}>Next broadcasts</button></div>
  </section>;
}
