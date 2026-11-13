import { t } from "@lingui/core/macro";
import { BarChart, LineChart, PieChart, StackedBarChart } from "../OperationsReportCharts";
import { DataState } from "../OperationsReportState";
import { ChartFrame, type ChartProps } from "./ChartFrame";
import { chartSummary, toChartData, type ChartRecord, type ChartSpec } from "./chartSpec";
import { FunnelChart } from "./FunnelChart";
import { Heatmap } from "./Heatmap";
import { Histogram } from "./Histogram";
import { MultiLineChart } from "./MultiLineChart";
import type { ReportChartSpec } from "../analyticsApi";
import { funnelInput, reportAlternative, wireChartSpec } from "./wireChartSpec";
import { rankedTimeSeries } from "./rankedTimeSeries";
import { ReportTable } from "../OperationsReportTable";
import { LogoLoader } from "../../../../components/LogoLoader";

function Chart({ spec, ...props }: ChartProps & { spec: ChartSpec }) {
  switch (spec.kind) {
    case "multi_line": return <MultiLineChart {...props} />;
    case "heatmap": return <Heatmap {...props} />;
    case "funnel": return <FunnelChart {...props} />;
    case "histogram": return <Histogram {...props} />;
    case "line":
      if (props.data.xKind === "time") return <MultiLineChart {...props} />;
      break;
    case "stacked_bar": {
      const categories = [...new Set(props.data.series.flatMap((series) => series.points.map((point) => point.x)))];
      return <StackedBarChart title={props.title} chartData={props.data} valueLabel={props.data.series[0]?.unit} rows={categories.map((x) => ({
        label: props.data.series.flatMap((series) => series.points).find((point) => point.x === x)!.label,
        segments: props.data.series.map((series) => ({ label: series.label, value: series.points.find((point) => point.x === x)?.value ?? 0 })),
      }))} />;
    }
    case "pie": return <PieChart title={props.title} chartData={props.data} valueLabel={props.data.series[0]?.unit}
      rows={props.data.series.flatMap(series => series.points.map(point => ({ label: `${series.label} — ${point.label}`, value: point.value })))} />;
    case "bar": break;
    default: return <ChartFrame {...props}><p>{t`Chart type unavailable. Show the table to explore this report.`}</p></ChartFrame>;
  }
  const Component = spec.kind === "line" ? LineChart : BarChart;
  return <div className="space-y-4">{props.data.series.map((series) => <Component key={series.id}
    title={`${props.title} — ${series.label}`} chartData={{ ...props.data, series: [series], summary: chartSummary(spec, [series]) }}
    valueLabel={[series.label, series.currency, series.unit].filter(Boolean).join(" · ")}
    rows={series.points.map((point) => ({ label: point.label, value: point.value }))} />)}</div>;
}

export function CatalogChartPanel({ spec: inputSpec, hint, rows, title, loading = false, error, onRetry }: {
  spec: ChartSpec | ReportChartSpec; hint?: string; rows: readonly ChartRecord[]; title: string; loading?: boolean; error?: unknown; onRetry?: () => void;
}) {
  // Detail specs deliberately have no measures: render the projected rows without
  // converting record identifiers into numbers to sum on a chart.
  if ("values" in inputSpec && inputSpec.values.length === 0) {
    const headers = [...new Set(rows.flatMap(row => Object.keys(row)))];
    const cells = rows.map(row => headers.map(field => {
      const value = row[field];
      return value == null ? null : typeof value === "object" ? JSON.stringify(value) : String(value);
    }));
    return <DataState loading={loading} error={error} onRetry={onRetry} empty={!rows.length}>
      <ReportTable data={{ rows: [headers, ...cells] }} />
    </DataState>;
  }
  let data;
  let spec: ChartSpec;
  let invalid = false;
  try {
    const input = funnelInput(wireChartSpec(inputSpec, hint, rows), rows);
    spec = input.spec; data = rankedTimeSeries(inputSpec, toChartData(spec, input.rows));
  } catch { invalid = true; }
  if (loading) return <LogoLoader label={t`Loading chart…`} size={48} className="min-h-16 py-3" />;
  if (invalid && !error) return <p role="alert" className="text-danger">{t`This report has an invalid chart specification.`}</p>;
  const panels = [...new Set(data?.series.map((series) => series.panelKey))];
  return <DataState loading={false} error={error} onRetry={onRetry} empty={!data?.series.length}>
    <div className="space-y-6">{reportAlternative(inputSpec, rows) ? <p className="text-sm text-muted">{reportAlternative(inputSpec, rows)}</p> : null}{panels.map((key) => {
      const series = data!.series.filter((series) => series.panelKey === key);
      const partitionLabel = [...new Set([series[0].partition, series[0].currency, series[0].unit].filter(Boolean))].join(" · ");
      return <Chart key={key} spec={spec!} title={`${title} — ${partitionLabel}`} data={{ ...data!, series, summary: chartSummary(spec!, series) }} />;
    })}</div>
  </DataState>;
}
