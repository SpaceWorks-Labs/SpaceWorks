import { t } from "@lingui/core/macro";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatNumber, type ChartRow } from "./OperationsReportState";
import { ChartFrame } from "./charts/ChartFrame";
import { legacyChartData } from "./charts/legacyChartData";
import { CasedLine } from "./charts/CasedLine";
import { edge, markStyle, seriesColor } from "./charts/chartStyle";
import type { ChartData } from "./charts/chartSpec";
export { REPORT_CHART_COLORS } from "./charts/chartStyle";

type ChartOptions = { valueLabel?: string; title?: string; chartData?: ChartData };

export function BarChart({ rows, valueLabel, title, chartData }: { rows: ChartRow[] } & ChartOptions) {
  const maxValue = Math.max(...rows.map((row) => Math.abs(row.value)), 1);
  if (!rows.length) return <EmptyState message={t`No chart data.`} />;
  return <ChartFrame title={title ?? (valueLabel ? t`Bar chart of ${valueLabel}` : t`Bar chart of values`)} data={chartData ?? legacyChartData(rows, valueLabel)}>
    <div className="space-y-2">
      {rows.map((row, index) => <div key={`${row.label}-${index}`} className="grid grid-cols-[minmax(0,1fr)_minmax(4rem,2fr)_auto] items-center gap-2 text-sm sm:grid-cols-[minmax(7rem,11rem)_1fr_auto]">
        <span className="truncate text-ink" title={row.label}>{row.label}</span>
        <div className="flex h-3 overflow-hidden rounded border border-line bg-bg" aria-hidden="true">
          {rows.some((item) => item.value < 0) ? <>
            <div className="flex w-1/2 justify-end border-r border-ink"><div style={{ width: `${Math.max(0, -row.value) / maxValue * 100}%`, ...markStyle(row.label) }} /></div>
            <div className="w-1/2"><div className="h-full" style={{ width: `${Math.max(0, row.value) / maxValue * 100}%`, ...markStyle(row.label) }} /></div>
          </> : <div className="h-full rounded" style={{ width: `${row.value / maxValue * 100}%`, ...markStyle(row.label) }} />}
        </div>
        <span className="min-w-14 text-right tabular-nums text-xs text-muted">{formatNumber(row.value)} {valueLabel ?? ""}</span>
      </div>)}
    </div>
  </ChartFrame>;
}

export function LineChart({ rows, valueLabel, title, chartData }: { rows: ChartRow[] } & ChartOptions) {
  const width = 640;
  const height = 180;
  const low = Math.min(0, ...rows.map((row) => row.value));
  const high = Math.max(0, ...rows.map((row) => row.value));
  if (!rows.length) return <EmptyState message={t`No chart data.`} />;
  const points = rows.map((row, index) => ({ ...row,
    x: rows.length === 1 ? width / 2 : index / (rows.length - 1) * (width - 32) + 16,
    y: height - 16 - (row.value - low) / (high - low || 1) * (height - 32),
  }));
  return <ChartFrame title={title ?? (valueLabel ? t`Line chart of ${valueLabel}` : t`Line chart of values`)} data={chartData ?? legacyChartData(rows, valueLabel)}>
    <svg viewBox={`0 0 ${width} ${height}`} className="h-44 w-full" role="img" aria-label={valueLabel ? t`Line chart of ${valueLabel}; exact values in the table.` : t`Line chart of values; exact values in the table.`}>
      <CasedLine color={seriesColor(valueLabel ?? "values")} points={points.map((point) => `${point.x},${point.y}`).join(" ")} />
      {points.map((point, index) => <circle key={`${point.label}-${index}`} cx={point.x} cy={point.y} r="5" fill={seriesColor(valueLabel ?? "values")} stroke={edge} strokeWidth="1.5" />)}
    </svg>
  </ChartFrame>;
}

export type StackedChartRow = { label: string; segments: { label: string; value: number }[] };

export function StackedBarChart({ rows, valueLabel, title, chartData }: { rows: StackedChartRow[] } & ChartOptions) {
  if (!rows.length) return <EmptyState message={t`No chart data.`} />;
  const positive = Math.max(0, ...rows.map((row) => row.segments.reduce((sum, segment) => sum + Math.max(0, segment.value), 0)));
  const negative = Math.max(0, ...rows.map((row) => row.segments.reduce((sum, segment) => sum + Math.max(0, -segment.value), 0)));
  const max = positive + negative || 1;
  const labels = [...new Set(rows.flatMap((row) => row.segments.map((segment) => segment.label)))].sort();
  const data = legacyChartData([], valueLabel);
  data.series = labels.map((label) => ({ id: label, label, unit: valueLabel ?? "values", panelKey: "stacked",
    points: rows.flatMap((row) => row.segments.filter((segment) => segment.label === label).map((segment) => ({ x: row.label, label: row.label, value: segment.value }))) }));
  data.summary = `${rows.length} categories with ${labels.length} segments.`;
  return <ChartFrame title={title ?? (valueLabel ? t`Stacked bar chart of ${valueLabel}` : t`Stacked bar chart of values`)} data={chartData ?? data}>
    <div className="space-y-3">{rows.map((row) => <div key={row.label} className="space-y-1 text-sm">
      <p>{row.label}</p>
      <div className="flex h-4 overflow-hidden rounded border border-line bg-bg" aria-hidden="true">
        <div className="flex justify-end border-r border-ink" style={{ width: `${negative / max * 100}%` }}>{row.segments.filter((segment) => segment.value < 0).map((segment) => <span key={segment.label} style={{ width: `${-segment.value / (negative || 1) * 100}%`, ...markStyle(segment.label) }} />)}</div>
        <div className="flex" style={{ width: `${positive / max * 100}%` }}>{row.segments.filter((segment) => segment.value >= 0).map((segment) => <span key={segment.label} style={{ width: `${segment.value / (positive || 1) * 100}%`, ...markStyle(segment.label) }} />)}</div>
      </div>
      <ul className="flex flex-wrap gap-3 text-xs text-muted">{row.segments.map((segment) => <li key={segment.label}>{segment.label}: {formatNumber(segment.value)} {valueLabel}</li>)}</ul>
    </div>)}</div>
  </ChartFrame>;
}

export function PieChart({ rows, valueLabel, title, chartData }: { rows: ChartRow[] } & ChartOptions) {
  const data = rows.filter((row) => row.value > 0);
  const total = data.reduce((sum, row) => sum + row.value, 0);
  if (!rows.length) return <EmptyState message={t`No chart data.`} />;
  let consumed = 0;
  const circumference = 2 * Math.PI * 60;
  return <ChartFrame title={title ?? (valueLabel ? t`Pie chart of ${valueLabel}` : t`Pie chart of values`)} data={chartData ?? legacyChartData(rows, valueLabel)}>
    {rows.some((row) => row.value < 0) ? <p>{t`Negative values cannot be represented as pie segments. Show the table for all values.`}</p> : <div className="flex flex-wrap items-center gap-4">
      <svg width="160" height="160" viewBox="0 0 160 160" role="img" aria-label={(valueLabel ? t`Pie chart of ${valueLabel}` : t`Pie chart of values`)}><g transform="rotate(-90 80 80)">{data.map((row) => {
        const dash = row.value / total * circumference;
        const offset = -consumed;
        consumed += dash;
        const gap = Math.min(2, dash);
        return <g key={row.label} fill="none">
          <circle cx="80" cy="80" r="60" stroke={edge} strokeWidth="28" strokeDasharray={`${dash} ${circumference - dash}`} strokeDashoffset={offset} />
          <circle cx="80" cy="80" r="60" stroke={seriesColor(row.label)} strokeWidth="26" strokeDasharray={`${dash - gap} ${circumference - dash + gap}`} strokeDashoffset={offset - gap / 2} />
        </g>;
      })}</g></svg>
      <ul className="min-w-0 flex-1 space-y-1 text-sm">{rows.map((row) => <li key={row.label} className="flex gap-2"><span aria-hidden="true" className="h-3 w-3" style={markStyle(row.label)} />{row.label}<span className="ml-auto tabular-nums text-xs">{formatNumber(row.value)} - {(total ? row.value / total * 100 : 0).toFixed(0)}%</span></li>)}</ul>
    </div>}
  </ChartFrame>;
}
