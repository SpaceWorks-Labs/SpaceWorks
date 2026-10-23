import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { eventErrorText } from "../eventUi";
import { CustomAnswersView } from "../../forms/CustomAnswersView";
import type { CustomAnswerSnapshot, CustomAnswerSnapshotV2 } from "../../forms/customFormTypes";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";
type Guest = { member_id: number | null; registration_id: number | null; name?: string; occurrences: { event_id: number; registration_id: number; name?: string; status: string; attended_at: string | null; email?: string; phone?: string; custom_answers?: CustomAnswerSnapshot | CustomAnswerSnapshotV2 | null }[] };
export function SeriesGuestList({ seriesId }: { seriesId: number }) {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [attendance, setAttendance] = useState("");
  const [event, setEvent] = useState("");
  const filters = new URLSearchParams({ page: String(page), ...(status ? { status } : {}), ...(attendance ? { attendance } : {}), ...(event ? { event_id: event } : {}) });
  const key = ["event-series-guests", seriesId, filters.toString(), ...sessionScope()];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<{ count: number; next: string | null; previous: string | null; results: Guest[] }>(`/admin/event-series/${seriesId}/guests/?${filters}`) });
  const denied = useClearDeniedQuery(query.error, key);
  if (denied) return <p role="alert" className="text-sm text-danger">This guest list is no longer available for your access.</p>;
  return <section className="grid gap-4" aria-label="Series guest list"><h3 className="title-section">Guests across this series</h3><p className="text-sm text-muted">Guests are counted once across occurrences you may access. Each occurrence keeps its own attendance and registration state.</p>
    <div className="grid gap-3 sm:grid-cols-3"><label className="grid gap-1 text-sm">Registration status<select className="desk-input" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option>{["registered", "attended", "waitlisted", "cancelled", "pending_approval", "rejected"].map(item => <option key={item}>{item}</option>)}</select></label>
      <label className="grid gap-1 text-sm">Attendance<select className="desk-input" value={attendance} onChange={e => { setAttendance(e.target.value); setPage(1); }}><option value="">Any</option><option value="attended">Attended</option><option value="not_attended">Not attended</option></select></label>
      <label className="grid gap-1 text-sm">Occurrence ID<input type="number" min={1} className="desk-input" value={event} onChange={e => { setEvent(e.target.value); setPage(1); }} /></label></div>
    {query.isLoading ? <p role="status">Loading series guests…</p> : null}{query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    <ul className="grid gap-3">{query.data?.results.map((guest, index) => <li key={`${guest.member_id}-${guest.registration_id}-${index}`} className="grid gap-2 rounded-2xl border border-line bg-panel p-4"><h4 className="font-semibold">{guest.name ?? guest.occurrences[0]?.name ?? `Guest ${index + 1 + (page - 1) * 24}`}</h4><ul className="grid gap-1 text-sm text-muted">{guest.occurrences.map(occurrence => <li key={occurrence.registration_id} className="grid gap-2">Occurrence {occurrence.event_id} · {occurrence.status.replace(/_/g, " ")}{occurrence.attended_at ? ` · checked in ${new Date(occurrence.attended_at).toLocaleString()}` : ""}
      {occurrence.email !== undefined || occurrence.phone !== undefined || occurrence.custom_answers !== undefined ? <details><summary className="min-h-11 cursor-pointer text-ink">Authorized registration details</summary><div className="grid gap-2 py-2">{occurrence.email ? <p>Email: {occurrence.email}</p> : null}{occurrence.phone ? <p>Phone: {occurrence.phone}</p> : null}{occurrence.custom_answers ? <CustomAnswersView snapshot={occurrence.custom_answers} /> : null}</div></details> : null}
    </li>)}</ul></li>)}</ul>
    {query.data?.count === 0 ? <p className="text-sm text-muted">No guests match these filters.</p> : null}
    {query.data?.previous || query.data?.next ? <nav className="flex flex-wrap justify-end gap-2" aria-label="Series guest pages"><button className="desk-button" disabled={!query.data.previous} onClick={() => setPage(page - 1)}>Previous</button><span className="self-center text-sm">Page {page}</span><button className="desk-button" disabled={!query.data.next} onClick={() => setPage(page + 1)}>Next</button></nav> : null}
  </section>;
}
