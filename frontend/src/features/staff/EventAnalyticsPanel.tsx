import { Skeleton, StatCard } from "../../components/ui";
import { useEventAnalytics } from "./eventCommunicationsApi";
import { eventErrorText } from "./eventUi";
import { EventProgrammeAnalytics } from "./eventProgramme/EventProgrammeAnalytics";

const METRICS = [["registrations", "Registrations"], ["registered", "Registered"], ["attended", "Attended"],
  ["waitlisted", "Waitlisted"], ["cancelled", "Cancelled"], ["feedback_responses", "Feedback responses"],
  ["attendance_rate_percent", "Completed-event attendance (%)"]] as const;

export function EventAnalyticsPanel({ makerspaceId, eventId, endsAt, features }: {
  makerspaceId: number; eventId: number; endsAt: string; features: string[];
}) {
  const { query, download } = useEventAnalytics(makerspaceId, eventId);
  const row = query.data?.typed_rows[0];
  const save = (key: string, format: "csv" | "pdf") => download.mutate({ key, format }, { onSuccess: (blob) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = `${key}.${format}`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } });
  const exports = features.includes("exports");
  const pdf = features.includes("pdf");
  return <section className="grid gap-4" aria-label="Event analytics">
    <h3 className="title-section">Analytics and exports</h3>
    <EventProgrammeAnalytics makerspaceId={makerspaceId} eventId={eventId} />
    {query.isLoading ? <div role="status" className="grid gap-3"><span className="sr-only">Loading analytics…</span>
      <div className="sw-stats">{[0, 1, 2, 3].map((n) => <Skeleton key={n} className="h-28 w-full" />)}</div></div> : null}
    {query.error || download.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error || download.error)}</p> : null}
    {row ? <div className="sw-stats">{METRICS.map(([key, label]) => <StatCard key={key} label={label} value={row[key] == null ? "—" : String(row[key])} />)}</div> : null}
    {exports || pdf ? <div className="grid gap-2">
      <p className="text-sm text-muted">Download a report for this event.{pdf ? " The post-event PDF is available once the event has ended." : ""}</p>
      <div className="flex flex-wrap gap-2">
        {exports ? <><button className="desk-button" type="button" disabled={download.isPending} onClick={() => save("event-registrations", "csv")}>Registration CSV</button><button className="desk-button" type="button" disabled={download.isPending} onClick={() => save("event-feedback", "csv")}>Feedback CSV</button></> : null}
        {pdf ? <button className="desk-button" type="button" disabled={download.isPending || new Date(endsAt).getTime() > Date.now()} onClick={() => save("event-attendance-pdf", "pdf")}>Post-event PDF</button> : null}
      </div>
    </div> : null}
    {download.isPending ? <p role="status" className="text-sm text-muted">Preparing download…</p> : null}
  </section>;
}
