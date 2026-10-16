import { useState } from "react";
import { Card, Skeleton, StatusBadge } from "../../components/ui";
import { useEventBroadcasts } from "./eventCommunicationsApi";
import { opsStatusLabel } from "./opsPresentation";
import { eventErrorText } from "./eventUi";

const STATUSES = ["registered", "attended", "pending_approval", "waitlisted", "rejected", "cancelled"];
const fieldLabel = "grid gap-1 text-sm font-semibold text-ink";

export function EventBroadcastsPanel({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const [page, setPage] = useState(1);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [statuses, setStatuses] = useState(["registered", "attended"]);
  const [attendance, setAttendance] = useState("any");
  const [preview, setPreview] = useState<number | null>(null);
  const { history, compose, action } = useEventBroadcasts(makerspaceId, eventId, page);
  const error = history.error || compose.error || action.error;
  return <section className="grid gap-4" aria-label="Event broadcasts">
    <div><h3 className="title-section">Email registrants</h3>
      <p className="mt-1 text-sm text-muted">Verified email only. Member preferences and quiet hours apply. You can cancel queued sends; accepted emails cannot be recalled.</p></div>
    <Card><form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); compose.mutate({ subject, body, statuses, attendance },
      { onSuccess: () => { setSubject(""); setBody(""); setPage(1); } }); }}>
      <label className={fieldLabel}>Subject<input required maxLength={200} className="desk-input w-full min-w-0 font-normal" value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
      <label className={fieldLabel}>Message<textarea required maxLength={10000} className="desk-input min-h-28 w-full min-w-0 font-normal" value={body} onChange={(e) => setBody(e.target.value)} /></label>
      <p className="text-xs text-muted [overflow-wrap:anywhere]">Placeholders: {"{{ name }}, {{ event_title }}, {{ event_date }}, {{ event_location }}, {{ ticket_url }}"}. Ticket links require sign-in.</p>
      <fieldset className="grid min-w-0 gap-x-4 sm:grid-cols-3"><legend className="mb-1 text-sm font-semibold text-ink">Registration states</legend>
        {STATUSES.map((status) => <label key={status} className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={statuses.includes(status)} onChange={(e) => setStatuses(e.target.checked ? [...statuses, status] : statuses.filter((s) => s !== status))} />{status.replace(/_/g, " ")}</label>)}
      </fieldset>
      <label className={fieldLabel}>Attendance<select className="desk-input w-full min-w-0 font-normal" value={attendance} onChange={(e) => setAttendance(e.target.value)}><option value="any">Any</option><option value="attended">Attended</option><option value="not_attended">Not attended</option></select></label>
      <div className="flex justify-end"><button className="desk-button-primary" type="submit" disabled={compose.isPending || !statuses.length}>{compose.isPending ? "Saving…" : "Save draft"}</button></div>
    </form></Card>
    {history.isLoading ? <div role="status" className="grid gap-3"><span className="sr-only">Loading broadcasts…</span><Skeleton className="h-20 w-full" /><Skeleton className="h-20 w-full" /></div> : null}
    {error ? <p className="text-sm text-danger" role="alert">{eventErrorText(error)}</p> : null}
    {history.data?.results.length ? <ul className="grid gap-3" aria-label="Sent and draft broadcasts">{history.data.results.map((row) => <li key={row.id} className="grid min-w-0 gap-3 rounded-2xl border border-line bg-panel p-4">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2"><p className="title-section min-w-0 break-words">{row.subject}</p><StatusBadge status={row.status} label={opsStatusLabel(row.status)} /></div>
      <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" aria-expanded={preview === row.id} onClick={() => setPreview(preview === row.id ? null : row.id)}>Preview message</button>
        {row.status === "draft" ? <button className="desk-button-primary" type="button" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "queue" })}>Send broadcast</button> : null}
        {["draft", "queued", "sending"].includes(row.status) ? <button className="desk-button-danger-outline" type="button" disabled={action.isPending} onClick={() => action.mutate({ id: row.id, action: "cancel" })}>Cancel broadcast</button> : null}</div>
      {preview === row.id ? <div className="whitespace-pre-wrap rounded-control border border-line bg-surface p-3 text-sm text-ink [overflow-wrap:anywhere]"><p className="mb-2 text-muted">Placeholders are filled with current participant data at delivery.</p>{row.body}</div> : null}
    </li>)}</ul> : null}
    {history.data?.count === 0 ? <p className="rounded-2xl border border-dashed border-line p-6 text-center text-sm text-muted">No broadcasts yet.</p> : null}
    {history.data?.previous || history.data?.next ? <nav aria-label="Broadcast pages" className="flex flex-wrap items-center justify-end gap-2 text-sm text-muted">
      <button className="desk-button" type="button" disabled={!history.data?.previous} onClick={() => setPage(page - 1)}>Previous broadcasts</button>
      <span>Page {page}</span>
      <button className="desk-button" type="button" disabled={!history.data?.next} onClick={() => setPage(page + 1)}>Next broadcasts</button>
    </nav> : null}
  </section>;
}
