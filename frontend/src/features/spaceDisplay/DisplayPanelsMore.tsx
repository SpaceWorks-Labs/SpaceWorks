import { t } from "@lingui/core/macro";
import { formatLocale } from "../../lib/format";
import type { PublicStatsMetric } from "../stats/api";
import { formatMetric } from "../stats/StatsMetrics";
import type { OpeningHoursData, StatsPanelData } from "./api";

const heading = "mb-6 text-4xl font-semibold text-ink";
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

/** Big-number tiles for a TV. Only the metrics the public stats page itself publishes; suppression is kept. */
export function StatsTiles({ data, tv = true }: { data: StatsPanelData; tv?: boolean }) {
  return <dl className={`grid gap-4 ${tv ? "sm:grid-cols-2 xl:grid-cols-4" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
    {data.metrics.map((metric) => <div key={metric.key} className="min-w-0 rounded-xl border border-line bg-panel p-6">
      <dt className={`text-muted ${tv ? "text-2xl" : "text-sm"}`}>{metric.label}</dt>
      <dd className={`mt-2 break-words font-display font-semibold tabular-nums text-ink ${tv ? "text-7xl" : "text-3xl"}`}>
        {formatMetric({ ...metric, section: "events" } as PublicStatsMetric)}</dd>
    </div>)}
  </dl>;
}

export function PublicStatsPanel({ data }: { data: StatsPanelData }) {
  return <section aria-labelledby="tv-stats" className="grid gap-6">
    <h2 id="tv-stats" className={heading}>{t`In numbers`} <span className="text-2xl font-normal text-muted">{data.period}</span></h2>
    <StatsTiles data={data} />
  </section>;
}

const dayName = (key: (typeof DAYS)[number]) =>
  new Intl.DateTimeFormat(formatLocale(), { weekday: "long", timeZone: "UTC" }).format(new Date(Date.UTC(2024, 0, 1 + DAYS.indexOf(key))));

/** The weekly opening hours; `{}` (no schedule) means the space is always open. Exceptions are not shown here. */
export function OpeningHoursList({ data, tv = true }: { data: OpeningHoursData; tv?: boolean }) {
  const weekly = data.weekly;
  if (!weekly || Object.keys(weekly).length === 0) return <p className={tv ? "text-3xl text-muted" : "text-muted"}>{t`Open any time.`}</p>;
  return <ul className={`grid gap-2 ${tv ? "text-3xl" : "text-base"}`}>{DAYS.map((day) => {
    const intervals = weekly[day] ?? [];
    return <li key={day} className="flex flex-wrap justify-between gap-4 border-b border-line py-2">
      <span className="font-semibold text-ink">{dayName(day)}</span>
      <span className="tabular-nums text-muted">{intervals.length ? intervals.map((i) => `${i.start}–${i.end}`).join(", ") : t`Closed`}</span>
    </li>;
  })}</ul>;
}

export function OpeningHoursPanel({ data }: { data: OpeningHoursData }) {
  return <section aria-labelledby="tv-hours" className="grid max-w-4xl gap-6">
    <h2 id="tv-hours" className={heading}>{t`Opening hours`}</h2>
    <OpeningHoursList data={data} />
  </section>;
}
