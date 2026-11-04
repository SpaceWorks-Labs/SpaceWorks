import { useReportColumns } from "./OperationsReportSelection";
import { DataTable, EmptyState } from "../../../components/ui";
import { STICKY_FIRST_COLUMN } from "../matrixColumns";
import { formatReportCell, reportHeaders, reportRows, type ReportCell, type ReportRows } from "./OperationsReportState";

export function PerMakerspaceTables({ data, nameOf, emptyLabel = "No activity in this period. Try a longer range." }: {
  data?: ReportRows; nameOf: (id: number) => string; emptyLabel?: string;
}) {
  if (!data?.rows?.length) return <EmptyState message={emptyLabel} />;
  const [header, ...body] = data.rows;
  const idx = header.findIndex(cell => cell === "makerspace_id" || cell === "makerspace");
  if (idx === -1 || !body.length) return <ReportTable data={data} />;
  const groups = new Map<string, ReportCell[][]>();
  for (const row of body) {
    const key = String(row[idx]);
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  const subHeader = header.filter((_, index) => index !== idx);
  return <div className="space-y-6">{[...groups].map(([key, rows]) => <section key={key}>
    <h4 className="eyebrow mb-3">{nameOf(Number(key))}</h4>
    <ReportTable data={{ rows: [subHeader, ...rows.map(row => row.filter((_, index) => index !== idx))] }} />
  </section>)}</div>;
}

export function ReportTable({ data }: { data?: ReportRows }) {
  const columns = useReportColumns();
  const allHeaders = reportHeaders(data);
  const indexes = columns.map(column => allHeaders.indexOf(column)).filter(index => index >= 0);
  const headers = indexes.length ? indexes.map(index => allHeaders[index]) : allHeaders;
  const rows = reportRows(data).map((cells, id) => ({ id, cells: indexes.length ? indexes.map(index => cells[index]) : cells }));
  return <div className="mt-4 min-w-0"><DataTable<{ id: number; cells: ReportCell[] }> data={rows}
    emptyTitle="No activity in this period. Try a longer range."
    columns={headers.map((header, index) => ({ key: `${header}-${index}`, header: header.replace(/_/g, " "),
      className: `${index === 0 ? STICKY_FIRST_COLUMN : ""} ${rows.some(row => typeof row.cells[index] === "number") ? "tabular-nums md:text-right" : ""}`,
      render: row => formatReportCell(row.cells[index]) }))} /></div>;
}
