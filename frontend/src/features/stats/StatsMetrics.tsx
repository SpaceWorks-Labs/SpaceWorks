import type { PublicCount, PublicStatsMetric, StatsSectionKey } from "./api";
import { StatTile, formatNumber } from "./StatsParts";

/** #170: a suppressed count is never shown as a number, only as "fewer than 3". */
export function formatCount(count: PublicCount | null | undefined) {
  if (!count) return "Not tracked";
  return count.suppressed || count.value === null ? "Fewer than 3" : formatNumber(count.value);
}

export function formatMetric(metric: PublicStatsMetric) {
  if (metric.kind === "hours") return `${formatNumber(metric.value ?? 0)} h`;
  return formatCount(metric);
}

export function metricsFor(metrics: PublicStatsMetric[], section: StatsSectionKey) {
  return metrics.filter(metric => metric.section === section);
}

/** The period figures of one section as tiles, labelled with the space's fixed period. */
export function PeriodTiles({ metrics, period }: { metrics: PublicStatsMetric[]; period: string }) {
  if (!metrics.length) return null;
  return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
    {metrics.map(metric => <StatTile key={metric.key} label={isSnapshot(metric.key) ? `${metric.label} now` : `${metric.label}, ${period}`}
      value={formatMetric(metric)} />)}
  </div>;
}

/** Up to four headline numbers above every section; empty when the Space Manager picked none. */
export function HeadlineRow({ metrics, period, size = "page" }: { metrics: PublicStatsMetric[]; period: string; size?: "page" | "tv" }) {
  if (!metrics.length) return null;
  const tv = size === "tv";
  return <section aria-label="Headline numbers" className={`grid sm:grid-cols-2 ${tv ? "gap-6 xl:grid-cols-4" : "gap-4 lg:grid-cols-4"}`}>
    {metrics.map(metric => <div key={metric.key} className={`min-w-0 rounded-xl border border-line bg-panel ${tv ? "p-8" : "p-5"}`}>
      <p className={tv ? "text-2xl text-muted" : "text-sm text-muted"}>{metric.label}</p>
      <p className={`mt-2 break-words font-display font-semibold tabular-nums text-ink ${tv ? "text-heading 2xl:text-display" : "text-display-sub"}`}>{formatMetric(metric)}</p>
      <p className={tv ? "mt-2 text-xl text-muted" : "mt-1 text-xs text-muted"}>{isSnapshot(metric.key) ? "Right now" : period}</p>
    </div>)}
  </section>;
}

/** Library size and upcoming events describe now, not the period. */
function isSnapshot(key: string) {
  return key === "lending.library" || key === "events.upcoming";
}
