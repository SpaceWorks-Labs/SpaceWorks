import { useQuery } from "@tanstack/react-query";
import { Card } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { sessionScope, useClearDeniedQuery } from "./sessionScope";

type Count = { label: string; count: number };
export type AnalyticsExtras = {
  event_id: number; timezone_name: string; window_minutes: number;
  arrivals: { window_start: string; count: number }[];
  checkin_methods: { method: string; count: number }[];
  answers: { question_id: string; label: string; type: string; answers: Count[]; total: number }[];
  waitlist: { ever_waitlisted: number; promoted: number; still_waiting: number; conversion_percent: number | null };
  series: { event_id: number; title: string; starts_at: string; registered: number; attended: number }[];
  short_link_visits: { day: string; count: number }[] | null;
};
const METHOD: Record<string, string> = { online: "Staff confirmed", qr: "QR scan", offline_sync: "Offline sync", venue_station: "Venue station", legacy: "Earlier records" };

/** Horizontal bars in the brand accent; every chart also states its numbers in text. */
function Bars({ title, rows, summary }: { title: string; rows: Count[]; summary: string }) {
  const max = Math.max(1, ...rows.map(row => row.count));
  return <figure className="grid gap-2"><figcaption className="font-semibold">{title}</figcaption>
    {rows.length ? <ul className="grid gap-1">{rows.map(row => <li key={row.label} className="grid grid-cols-[minmax(6rem,10rem)_1fr_auto] items-center gap-2 text-sm">
      <span className="truncate">{row.label}</span>
      <span aria-hidden="true" className="h-3 rounded-full bg-surface"><span className="block h-3 rounded-full bg-brand" style={{ width: `${(row.count / max) * 100}%` }} /></span>
      <span className="tabular-nums">{row.count}</span></li>)}</ul> : null}
    <p className="text-xs text-muted">{summary}</p></figure>;
}

const time = (value: string, zone: string) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: zone });

export function EventAnalyticsExtras({ makerspaceId, eventId }: { makerspaceId: number; eventId: number }) {
  const key = ["event-analytics-extras", makerspaceId, eventId, ...sessionScope()];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<AnalyticsExtras>(`/admin/events/${eventId}/analytics/extras/`) });
  useClearDeniedQuery(query.error, key);
  const data = query.data;
  if (!data) return query.isLoading ? <p role="status" className="text-sm">Loading arrivals and answers…</p> : null;
  const arrived = data.arrivals.reduce((sum, row) => sum + row.count, 0);
  const busiest = [...data.arrivals].sort((a, b) => b.count - a.count)[0];
  const visits = data.short_link_visits?.reduce((sum, row) => sum + row.count, 0) ?? 0;
  return <Card><section className="grid gap-6" aria-label="More event analytics">
    <h4 className="font-semibold">Arrivals, answers and reach</h4>
    <div className="grid gap-6 lg:grid-cols-2">
      <Bars title={`Arrivals by ${data.window_minutes}-minute window`} rows={data.arrivals.map(row => ({ label: time(row.window_start, data.timezone_name), count: row.count }))}
        summary={arrived ? `${arrived} people checked in; the busiest window started at ${time(busiest.window_start, data.timezone_name)} with ${busiest.count}.` : "Nobody has checked in yet."} />
      <Bars title="How people checked in" rows={data.checkin_methods.map(row => ({ label: METHOD[row.method] ?? row.method, count: row.count }))}
        summary={data.checkin_methods.length ? data.checkin_methods.map(row => `${METHOD[row.method] ?? row.method}: ${row.count}`).join(" · ") : "No check-ins to split yet."} />
    </div>
    {data.answers.map(chart => <Bars key={chart.question_id} title={chart.label || "Feedback question"} rows={chart.answers}
      summary={`${chart.total} answers. Only choice questions are charted; written answers never are.`} />)}
    <dl className="grid gap-3 text-sm sm:grid-cols-3">
      <div><dt className="text-muted">Joined the waitlist</dt><dd className="text-xl font-semibold tabular-nums">{data.waitlist.ever_waitlisted}</dd></div>
      <div><dt className="text-muted">Got a place from it</dt><dd className="text-xl font-semibold tabular-nums">{data.waitlist.promoted}</dd></div>
      <div><dt className="text-muted">Conversion</dt><dd className="text-xl font-semibold tabular-nums">{data.waitlist.conversion_percent === null ? "—" : `${data.waitlist.conversion_percent}%`}</dd></div>
    </dl>
    {data.series.length > 1 ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="mb-2 text-left font-semibold">Turnout across the series</caption>
      <thead><tr><th scope="col" className="p-2">Date</th><th scope="col" className="p-2">Going</th><th scope="col" className="p-2">Came</th></tr></thead>
      <tbody>{data.series.map(row => <tr key={row.event_id}><th scope="row" className="p-2 font-normal">{new Date(row.starts_at).toLocaleDateString()}</th><td className="p-2 tabular-nums">{row.registered}</td><td className="p-2 tabular-nums">{row.attended}</td></tr>)}</tbody></table></div> : null}
    {data.short_link_visits ? <p className="text-sm">Short link: {visits} {visits === 1 ? "visit" : "visits"} in the last 30 days. Only a daily count is kept, never who visited.</p> : null}
  </section></Card>;
}
