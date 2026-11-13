import { t } from "@lingui/core/macro";
import { StructuredApiError } from "../../lib/api";
import { AnalyticsData } from "../staff/panels/AnalyticsData";
import { useMemberUsage, type MemberUsageSeries } from "./memberUsageApi";
import { LogoLoader } from "../../components/LogoLoader";

export function MemberUsagePanel({ makerspaceId }: { makerspaceId: number }) {
  const query = useMemberUsage(makerspaceId);
  if (query.error instanceof StructuredApiError && [403, 404].includes(query.error.status)) return null;
  const data = query.data;
  return <section aria-label={t`My usage`} className="desk-panel min-w-0 p-5">
    <h2 className="title-panel">{t`My usage`}</h2>
    {query.isLoading ? <LogoLoader label={t`Loading your usage…`} size={48} className="min-h-16 py-3" /> : query.isError ? <div role="alert"><p>{t`Couldn't load your usage.`}</p><button type="button" className="desk-button" onClick={() => void query.refetch()}>{t`Retry`}</button></div> : data ? <div className="mt-4 grid min-w-0 gap-6">
      {data.usage_available && data.loans ? <Usage title={t`Loans`} series={data.loans.monthly}
        summary={t`${data.loans.count} loans, ${data.loans.returned_count} returned, ${data.loans.currently_out} currently out.`} /> : null}
      {data.usage_available && data.machines ? <>
        <Usage title={t`Machine hours`} series={data.machines.monthly} summary={t`${data.machines.hours} recorded manual machine hours. Historical usage without member attribution is excluded.`} />
        <Usage title={t`Your most used machines`} series={data.machines.top_machines} />
      </> : null}
      {data.usage_available && data.bookings ? <Usage title={t`Bookings`} series={data.bookings.monthly} summary={t`${data.bookings.count} bookings, excluding cancellations.`} /> : null}
      {data.usage_available && data.events ? <Usage title={t`Events attended`} series={data.events.chart} summary={t`${data.events.attended_count} events attended.`} /> : null}
      {data.payments ? <section><h3 className="title-section">{t`Payments`}</h3>
        <ul className="my-3 space-y-2 text-sm">{[...new Set([...Object.keys(data.payments.paid_by_currency), ...Object.keys(data.payments.outstanding_by_currency)])].map(currency => <li key={currency}>
          {t`${currency.toUpperCase()}: ${data.payments!.paid_by_currency[currency] ?? "0"} paid, ${data.payments!.outstanding_by_currency[currency] ?? "0"} outstanding.`}
        </li>)}</ul>
        <AnalyticsData title={t`Your payments`} rows={data.payments.totals.rows} spec={data.payments.totals.chart_spec} />
      </section> : null}
      {!data.loans && !data.machines && !data.bookings && !data.events && !data.payments ? <p>{t`No usage is available for your account here.`}</p> : null}
    </div> : null}
  </section>;
}
function Usage({ title, summary, series }: { title: string; summary?: string; series: MemberUsageSeries }) {
  return <section className="min-w-0"><h3 className="title-section">{title}</h3>{summary ? <p className="my-2 text-sm text-muted">{summary}</p> : null}
    <AnalyticsData title={title} rows={series.rows} spec={series.chart_spec} />
  </section>;
}
