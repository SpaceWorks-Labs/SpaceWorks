import type { ChartRow } from "../OperationsReportState";
import type { ChartData } from "./chartSpec";

export function legacyChartData(rows: ChartRow[], valueLabel = "values"): ChartData {
  return {
    summary: `${rows.length} observations of ${valueLabel}.`, xKind: "category", xLabel: "Category",
    series: [{ id: valueLabel, label: valueLabel, unit: valueLabel, panelKey: valueLabel,
      points: rows.map((row) => ({ x: row.label, label: row.label, value: row.value })) }],
  };
}
