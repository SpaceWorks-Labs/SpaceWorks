import { t } from "@lingui/core/macro";
import { BarChart, LineChart, PieChart, StackedBarChart } from "../OperationsReportCharts";
import { CatalogChartPanel } from "./CatalogChartPanel";
import { toChartData, type ChartSpec } from "./chartSpec";
import { FunnelChart } from "./FunnelChart";
import { Heatmap } from "./Heatmap";
import { Histogram } from "./Histogram";
import { MultiLineChart } from "./MultiLineChart";

const spec: ChartSpec = {
  kind: "heatmap", series_fields: ["team"], x: { field: "bucket", kind: "category", label: t`Bucket` },
  value_fields: [{ field: "count", unit: "visits" }], negative_values: "preserve",
  alt_text_template: "{series} series, {points} observations in {units} by {x}.",
};
const rows = [
  { team: "Workshop", bucket: "0–2", count: 12 }, { team: "Workshop", bucket: "2–4", count: 7 },
  { team: "Studio", bucket: "0–2", count: 4 }, { team: "Studio", bucket: "2–4", count: 2 },
];
const data = toChartData(spec, rows);
const timeSpec: ChartSpec = { ...spec, kind: "multi_line", x: { field: "bucket", kind: "time", label: t`Date` } };
const timeData = toChartData(timeSpec, ["Workshop", "Studio"].flatMap((team, index) => [
  { team, bucket: "2026-10-01", count: 3 + index }, { team, bucket: "2026-10-02", count: 5 + index },
  { team, bucket: "2026-10-10", count: 9 + index },
]));
const legacyRows = [{ label: t`Workshop`, value: 12 }, { label: t`Studio`, value: 7 }];

/** Deliberately no network, login or seed dependency: these are real chart components. */
export default function ChartTestPage() {
  const kind = new URLSearchParams(window.location.search).get("chart") ?? "multi_line";
  const chart = {
    multi_line: <MultiLineChart title={t`Visits over time`} data={timeData} />,
    heatmap: <Heatmap title={t`Visits by cohort`} data={data} />,
    funnel: <FunnelChart title={t`Request stages`} data={data} />,
    histogram: <Histogram title={t`Visit distribution`} data={data} />,
    bar: <BarChart rows={legacyRows} valueLabel="visits" />,
    line: <LineChart rows={legacyRows} valueLabel="visits" />,
    stacked_bar: <StackedBarChart rows={legacyRows.map((row) => ({ label: row.label, segments: [{ label: t`Returned`, value: row.value }, { label: t`Issued`, value: 3 }] }))} valueLabel="visits" />,
    pie: <PieChart rows={legacyRows} valueLabel="visits" />,
    catalog: <CatalogChartPanel title={t`Catalog visits`} spec={timeSpec} rows={[
      { team: "Workshop", bucket: "2026-10-01", count: 12 }, { team: "Studio", bucket: "2026-10-02", count: 7 },
    ]} />,
  }[kind];
  return <main className="min-h-screen bg-bg p-6 text-ink"><h1 className="title-page mb-6">{t`Chart accessibility fixture`}</h1>
    <section aria-label={t`Chart fixture`} className="max-w-5xl rounded-2xl border border-line bg-panel p-6">{chart ?? <p>{t`Unknown fixture.`}</p>}</section>
  </main>;
}
