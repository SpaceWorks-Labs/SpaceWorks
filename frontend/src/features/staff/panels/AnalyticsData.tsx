import { useId, useState } from "react";
import { CatalogChartPanel } from "./charts/CatalogChartPanel";
import type { ChartRecord, ChartSpec } from "./charts/chartSpec";
import type { ReportChartSpec } from "./analyticsApi";
import { useReportColumns } from "./OperationsReportSelection";

/** The full source table remains available even when a chart omits null axes or shows top N. */
export function AnalyticsData({ title, rows, spec, hint, meta }: {
  title: string; rows: readonly ChartRecord[]; spec?: ReportChartSpec | ChartSpec | null;
  hint?: string; meta?: Record<string, unknown>;
}) {
  const [table, setTable] = useState(false);
  const id = useId();
  const columns = useReportColumns();
  const allFields = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const selectedFields = columns.filter(column => allFields.includes(column));
  const fields = selectedFields.length ? selectedFields : allFields;
  const notes = ["definition", "basis", "limitations", "measurement", "coverage", "unknown_history"]
    .flatMap(key => typeof meta?.[key] === "string" ? [String(meta[key])] : []);
  if (!rows.length) return <p className="text-sm text-muted">No activity in this period. Try a longer range.</p>;
  return <div className="min-w-0 space-y-3">
    {notes.map((note, index) => <p key={index} className="text-sm text-muted">{note}</p>)}
    {spec ? <CatalogChartPanel title={title} rows={rows} spec={spec} hint={hint} /> : <p className="text-sm text-muted">This report is available as a data table.</p>}
    <button type="button" className="desk-button focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      aria-expanded={table} aria-controls={id} onClick={() => setTable(!table)}>{table ? "Hide report data" : "Show report data"}</button>
    {table ? <div id={id} className="overflow-x-auto"><table tabIndex={0}
      className="w-full text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <caption>{title} {selectedFields.length ? "selected columns" : "full report data"}</caption>
      <thead><tr>{fields.map(field => <th scope="col" className="p-2" key={field}>{field.replace(/_/g, " ")}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={index}>{fields.map((field, column) => {
        const value = row[field];
        const text = value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
        return column ? <td key={field} className="p-2">{text}</td> : <th key={field} scope="row" className="p-2">{text}</th>;
      })}</tr>)}</tbody>
    </table></div> : null}
  </div>;
}
