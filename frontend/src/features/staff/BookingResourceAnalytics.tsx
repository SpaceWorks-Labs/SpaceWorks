import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Card, EmptyState, ErrorText, Field } from "../../components/ui";
import { BookingUtilizationSummary } from "./panels/OperationsReportsBookings";
import { StatCards } from "./panels/OperationsReportsParts";
import { useBookingResourceReports, type BookingReportKey } from "./bookingReportsApi";
import { LogoLoader } from "../../components/LogoLoader";

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
  return <section className="grid gap-6" aria-label={t`Resource analytics and exports`}>
    <div><h2 className="title-panel">{t`Resource analytics and exports`}</h2>
      <p className="mt-1 text-sm text-muted">{t`Dates use the makerspace timezone. Utilization needs both bounds and measures calendar reservation occupancy, not physical presence. Reservation and answer exports include bookings overlapping this period.`}</p></div>
    <Card className="grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t`Start date`}><input className="desk-input w-full min-w-0" type="date" value={start} onChange={(event) => setStart(event.target.value)} /></Field>
        <Field label={t`End date (inclusive)`}><input className="desk-input w-full min-w-0" type="date" value={end} onChange={(event) => setEnd(event.target.value)} /></Field>
      </div>
      {!validPeriod ? <ErrorText message={t`End date must be on or after start date.`} /> : null}
      <div className="flex flex-wrap gap-2">
        {analytics ? <button className="desk-button" type="button" disabled={pending || !validPeriod} onClick={() => save("booking-resource-utilization", "csv")}>{t`Utilization CSV`}</button> : null}
        {features.includes("exports") ? <>
          <button className="desk-button" type="button" disabled={pending || !validPeriod} onClick={() => save("booking-reservations", "csv")}>{t`Reservation CSV`}</button>
          <button className="desk-button" type="button" disabled={pending || !validPeriod} onClick={() => save("booking-answers", "csv")}>{t`Custom answers CSV`}</button>
        </> : null}
        {features.includes("pdf") ? <button className="desk-button" type="button" disabled={pending || !validPeriod || !start || !end} onClick={() => save("booking-resource-utilization-pdf", "pdf")}>{t`Utilization PDF`}</button> : null}
      </div>
      {features.includes("pdf") && (!start || !end) ? <p className="text-xs text-muted">{t`Select both dates to download a PDF.`}</p> : null}
      {pending ? <LogoLoader label={t`Preparing download...`} size={48} className="min-h-16 py-3" /> : null}
    </Card>
    {analytics && query.isLoading ? <LogoLoader label={t`Loading resource analytics...`} size={48} className="min-h-28 py-3" /> : null}
    {loadError ? <ErrorText message={loadError.message} /> : null}
    {analytics && validPeriod && !query.error && query.data ? query.data.typed_rows.length
      ? <div className="grid gap-6">
        <BookingUtilizationSummary rows={query.data.typed_rows} data={query.data} />
        {query.data.meta.arrival_counts_available ? <section aria-label={t`Recorded booking arrivals`}>
          <h3 className="title-section">{t`Recorded arrivals`}</h3>
          <p className="mt-1 text-sm text-muted">{t`Current, unreversed arrivals for reservations overlapping this period. These counts do not measure physical use or reservation hours.`}</p>
          <StatCards stats={[
            ["Arrived reservations", query.data.typed_rows.reduce((total, row) => total + row.arrived_reservations, 0)],
            ["Confirmed without recorded arrival", query.data.typed_rows.reduce((total, row) => total + row.confirmed_without_recorded_arrival, 0)],
          ]} />
        </section> : null}
      </div>
      : <EmptyState message={t`No records in this resource report.`} /> : null}
  </section>;
}
