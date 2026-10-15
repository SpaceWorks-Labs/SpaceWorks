import type { ReactNode } from "react";
import { Card, EmptyState, ListRow, ProgressBar, StatCard } from "../../components/ui";

type ChartRow = { label: string; value: number };
export type StatTone = "blue" | "yellow" | "mint" | "emphasis";
export function StatTile({ label, value }: { label: string; value: number | string; tone?: StatTone }) {
  return <StatCard label={label} value={value} />;
}
export function Section({ title, children }: { title: string; children: ReactNode }) {
  return <Card><h2 className="title-panel mb-6">{title}</h2><div className="grid gap-6">{children}</div></Card>;
}
export function CompactList({ rows, empty }: { rows: { label: string; value: string }[]; empty: string }) {
  if (!rows.length) return <EmptyState message={empty} />;
  return <div className="mt-3 grid gap-3">{rows.map((row, index) => <ListRow key={`${row.label}-${index}`} title={row.label} right={<span className="text-sm tabular-nums text-muted">{row.value}</span>} />)}</div>;
}
export function BarChart({ rows, valueLabel }: { rows: ChartRow[]; valueLabel: string }) {
  const maximum = Math.max(...rows.map(row => row.value), 0);
  if (!rows.length || maximum <= 0) return <EmptyState message="No chart data yet. Activity will appear as jobs are recorded." />;
  return <div className="grid gap-4">{rows.map(row => <div key={row.label} className="grid gap-2">
    <div className="flex justify-between gap-3 text-sm"><span>{row.label}</span><span className="tabular-nums text-muted">{formatNumber(row.value)} {valueLabel}</span></div>
    <ProgressBar value={row.value / maximum} label={`${row.label}: ${formatNumber(row.value)} ${valueLabel}`} />
  </div>)}</div>;
}
export function formatNumber(value: number) { return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value); }
export function formatDate(value: string) { return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
