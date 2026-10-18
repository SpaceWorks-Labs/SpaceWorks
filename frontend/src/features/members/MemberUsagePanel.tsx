import { StructuredApiError } from "../../lib/api";
import { AnalyticsData } from "../staff/panels/AnalyticsData";
import { useMemberUsage, type MemberUsageSeries } from "./memberUsageApi";

export function MemberUsagePanel({ makerspaceId }: { makerspaceId: number }) {
  const query = useMemberUsage(makerspaceId);
  if (query.error instanceof StructuredApiError && [403, 404].includes(query.error.status)) return null;
  const data = query.data;
  return <section aria-label="My usage" className="desk-panel min-w-0 p-5">
    <h2 className="title-panel">My usage</h2>
    {query.isLoading ? <p role="status">Loading your usage…</p> : query.isError ? <div role="alert"><p>Couldn't load your usage.</p><button type="button" className="desk-button" onClick={() => void query.refetch()}>Retry</button></div> : data ? <div className="mt-4 grid min-w-0 gap-6">
      {data.usage_available && data.loans ? <Usage title="Loans" series={data.loans.monthly}
        summary={`${data.loans.count} loans, ${data.loans.returned_count} returned, ${data.loans.currently_out} currently out.`} /> : null}
      {data.usage_available && data.machines ? <>
        <Usage title="Machine hours" series={data.machines.monthly} summary={`${data.machines.hours} recorded manual machine hours. Historical usage without member attribution is excluded.`} />
        <Usage title="Your most used machines" series={data.machines.top_machines} />
      </> : null}
      {data.usage_available && data.bookings ? <Usage title="Bookings" series={data.bookings.monthly} summary={`${data.bookings.count} bookings, excluding cancellations.`} /> : null}
      {data.usage_available && data.events ? <Usage title="Events attended" series={data.events.chart} summary={`${data.events.attended_count} events attended.`} /> : null}
      {data.payments ? <section><h3 className="title-section">Payments</h3>
        <ul className="my-3 space-y-2 text-sm">{[...new Set([...Object.keys(data.payments.paid_by_currency), ...Object.keys(data.payments.outstanding_by_currency)])].map(currency => <li key={currency}>
          {`${currency.toUpperCase()}: ${data.payments!.paid_by_currency[currency] ?? "0"} paid, ${data.payments!.outstanding_by_currency[currency] ?? "0"} outstanding.`}
        </li>)}</ul>
        <AnalyticsData title="Your payments" rows={data.payments.totals.rows} spec={data.payments.totals.chart_spec} />
      </section> : null}
      {!data.loans && !data.machines && !data.bookings && !data.events && !data.payments ? <p>No usage is available for your account here.</p> : null}
    </div> : null}
  </section>;
}
function Usage({ title, summary, series }: { title: string; summary?: string; series: MemberUsageSeries }) {
  return <section className="min-w-0"><h3 className="title-section">{title}</h3>{summary ? <p className="my-2 text-sm text-muted">{summary}</p> : null}
    <AnalyticsData title={title} rows={series.rows} spec={series.chart_spec} />
  </section>;
}
