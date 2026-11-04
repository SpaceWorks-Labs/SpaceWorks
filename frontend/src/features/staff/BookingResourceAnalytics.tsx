import { useState } from "react";

import { Card, EmptyState, ErrorText, Field, Skeleton } from "../../components/ui";
import { BookingUtilizationSummary } from "./panels/OperationsReportsBookings";
import { StatCards } from "./panels/OperationsReportsParts";
import { useBookingResourceReports, type BookingReportKey } from "./bookingReportsApi";

export function BookingResourceAnalytics({ makerspaceId, spaceId, features }: {
  makerspaceId: number; spaceId: number; features: string[];
}) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const analytics = features.includes("analytics");
  const { query, download, validPeriod } = useBookingResourceReports(makerspaceId, spaceId, start, end, analytics);
  const save = (key: BookingReportKey, format: "csv" | "pdf") => download.mutate({ key, format }, { onSuccess: (blob) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a"); link.href = url; link.download = `${key}.${format}`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } });
  const pending = download.isPending;
  const loadError = query.error || download.error;
  return <section className="grid gap-6" aria-label="Resource analytics and exports">
    <div><h2 className="title-panel">Resource analytics and exports</h2>
      <p className="mt-1 text-sm text-muted">Dates use the makerspace timezone. Utilization needs both bounds and measures calendar reservation occupancy, not physical presence. Reservation and answer exports include bookings overlapping this period.</p></div>
    <Card className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Start date"><input className="desk-input w-full min-w-0" type="date" value={start} onChange={(event) => setStart(event.target.value)} /></Field>
        <Field label="End date (inclusive)"><input className="desk-input w-full min-w-0" type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></Field>
      </div>
      {!validPeriod ? <ErrorText message="End date must be on or after start date." /> : null}
      <div className="flex flex-wrap gap-2">
        {analytics ? <button className="desk-button" type="button" disabled={pending || !validPeriod} onClick={() => save("booking-resource-utilization", "csv")}>Utilization CSV</button> : null}
        {features.includes("exports") ? <>
          <button className="desk-button" type="button" disabled={pending || !validPeriod} onClick={() => save("booking-reservations", "csv")}>Reservation CSV</button>
          <button className="desk-button" type="button" disabled={pending || !validPeriod} onClick={() => save("booking-answers", "csv")}>Custom answers CSV</button>
        </> : null}
        {features.includes("pdf") ? <button className="desk-button" type="button" disabled={pending || !validPeriod || !start || !end} onClick={() => save("booking-resource-utilization-pdf", "pdf")}>Utilization PDF</button> : null}
      </div>
      {features.includes("pdf") && (!start || !end) ? <p className="text-xs text-muted">Select both dates to download a PDF.</p> : null}
      {pending ? <p role="status" className="text-sm text-muted">Preparing download...</p> : null}
    </Card>
    {analytics && query.isLoading ? <div role="status" aria-label="Loading resource analytics..." className="grid gap-3"><span className="sr-only">Loading resource analytics...</span><Skeleton className="h-28 w-full" /><Skeleton className="h-48 w-full" /></div> : null}
    {loadError ? <ErrorText message={loadError.message} /> : null}
    {analytics && validPeriod && !query.error && query.data ? query.data.typed_rows.length
      ? <div className="grid gap-6">
        <BookingUtilizationSummary rows={query.data.typed_rows} data={query.data} />
        {query.data.meta.arrival_counts_available ? <section aria-label="Recorded booking arrivals">
          <h3 className="title-section">Recorded arrivals</h3>
          <p className="mt-1 text-sm text-muted">Current, unreversed arrivals for reservations overlapping this period. These counts do not measure physical use or reservation hours.</p>
          <StatCards stats={[
            ["Arrived reservations", query.data.typed_rows.reduce((total, row) => total + row.arrived_reservations, 0)],
            ["Confirmed without recorded arrival", query.data.typed_rows.reduce((total, row) => total + row.confirmed_without_recorded_arrival, 0)],
          ]} />
        </section> : null}
      </div>
      : <EmptyState message="No records in this resource report." /> : null}
  </section>;
}
