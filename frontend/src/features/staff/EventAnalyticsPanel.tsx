import { useEventAnalytics } from "./eventCommunicationsApi";
import { eventErrorText } from "./eventUi";

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
  return <section className="grid gap-3" aria-label="Event analytics">
    <h3 className="title-section">Analytics and exports</h3>
    {query.isLoading ? <p role="status">Loading analytics…</p> : null}
    {query.error || download.error ? <p role="alert" className="text-danger">{eventErrorText(query.error || download.error)}</p> : null}
    {row ? <dl className="grid grid-cols-2 gap-3">{METRICS.map(([key, label]) => <div key={key}><dt className="text-sm text-muted">{label}</dt><dd className="font-semibold">{row[key] == null ? "—" : String(row[key])}</dd></div>)}</dl> : null}
    <div className="flex flex-wrap gap-2">
      {features.includes("exports") ? <><button className="desk-button" disabled={download.isPending} onClick={() => save("event-registrations", "csv")}>Registration CSV</button><button className="desk-button" disabled={download.isPending} onClick={() => save("event-feedback", "csv")}>Feedback CSV</button></> : null}
      {features.includes("pdf") ? <button className="desk-button" disabled={download.isPending || new Date(endsAt).getTime() > Date.now()} onClick={() => save("event-attendance-pdf", "pdf")}>Post-event PDF</button> : null}
    </div>
    {download.isPending ? <p role="status">Preparing download…</p> : null}
  </section>;
}
