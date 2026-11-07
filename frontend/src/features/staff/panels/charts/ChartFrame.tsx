import { formatLocale } from "../../../../lib/format";
import { t } from "@lingui/core/macro";
import { useId, useState, type ReactNode } from "react";
import type { ChartData, ChartSeries } from "./chartSpec";
import { focusClass, seriesColor, seriesDash } from "./chartStyle";

export type ChartProps = { title: string; data: ChartData };
export const valueText = (value: number, series: ChartSeries) => `${new Intl.NumberFormat(formatLocale(), { maximumFractionDigits: 3 }).format(value)} ${series.currency ?? ""} ${series.unit}`.trim();

/** A single keyboard entry opens the full data, avoiding hundreds of SVG tab stops. */
export function ChartFrame({ title, data, children }: ChartProps & { children: ReactNode }) {
  const id = useId();
  const [table, setTable] = useState(false);
  return <figure aria-labelledby={`${id}-caption`} className="min-w-0 space-y-3 text-ink">
    <figcaption id={`${id}-caption`} className="text-sm font-semibold">{title}</figcaption>
    <p className="text-sm text-muted">{data.summary}</p>
    {!data.series.length ? <p>{t`No chart data.`}</p> : <>
      <div className="overflow-x-auto">{children}</div>
      <button type="button" className={`desk-button ${focusClass}`} aria-expanded={table} aria-controls={`${id}-table`} onClick={() => setTable(!table)}>
        {table ? t`Hide table` : t`Show as table`}
      </button>
      {table && <div id={`${id}-table`} className="overflow-x-auto">
        <table tabIndex={0} className={`w-full text-left text-sm ${focusClass}`}>
          <caption>{title} data</caption>
          <thead><tr>{["Series", data.xLabel, "Value", "Unit", "Currency", "Partition"].map((header) => <th key={header} scope="col" className="p-2">{header}</th>)}</tr></thead>
          <tbody>{data.series.flatMap((series) => series.points.map((point, index) => <tr key={`${series.id}-${index}`}>
            <th scope="row" className="p-2">{series.label}</th><td className="p-2">{point.label}</td>
            <td className="p-2 tabular-nums">{point.value}</td><td className="p-2">{series.unit}</td>
            <td className="p-2">{series.currency ?? "—"}</td><td className="p-2">{series.partition ?? "—"}</td>
          </tr>))}</tbody>
        </table>
      </div>}
    </>}
  </figure>;
}

export function ChartLegend({ series }: { series: ChartSeries[] }) {
  return <ul aria-label={t`Series legend`} className="flex flex-wrap gap-4 text-sm">{series.map((item, index) => <li key={item.id} className="flex items-center gap-2">
    <svg width="28" height="12" aria-hidden="true"><path d="M0 6 H28" stroke={seriesColor(item.id)} strokeWidth="3" strokeDasharray={seriesDash(item.id)} /></svg>
    {index + 1}. {item.label} ({[item.currency, item.unit].filter(Boolean).join(" ")})
  </li>)}</ul>;
}
