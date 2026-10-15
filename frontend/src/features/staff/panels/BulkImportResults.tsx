import { DataTable, ProgressBar, StatCard, StatusPill } from "../../../components/ui";
import { messageFor, type BulkImportJob, type ImportResult } from "./BulkImportHelpers";
export function ImportProgress({ job, loading }: { job?: BulkImportJob; loading: boolean }) {
 const total = job?.total_rows ?? 0, processed = job?.processed_rows ?? 0;
 return <div role="status" className="grid gap-2"><p className="text-sm text-muted">{job ? `${processed} / ${total} rows` : loading ? "Preparing import…" : "Ready"}</p><ProgressBar value={total ? processed / total : 0} label={job ? `${processed} / ${total} rows` : loading ? "Preparing import…" : "Ready"} /></div>;
}
export function ImportSummary({ result }: { result: ImportResult }) {
 const errorRows = new Map((result.errors ?? []).map(item => [item.row, item.errors]));
 const warningRows = new Map((result.warnings ?? []).map(item => [item.row, item.warnings]));
 const rows = [...(result.rows ?? [])].sort((a, b) => Number(Boolean(errorRows.get(b.row) ?? b.errors)) - Number(Boolean(errorRows.get(a.row) ?? a.errors)));
 return <div className="grid gap-6"><div className="grid gap-3 sm:grid-cols-2">{[
   ["Create", result.created ?? result.summary?.create ?? 0], ["Update", result.updated ?? result.summary?.update ?? 0], ["Errors", result.summary?.errors ?? result.errors?.length ?? 0],
   ["Warnings", result.summary?.warnings ?? result.warnings?.length ?? 0], ["Rows", result.summary?.total ?? result.rows?.length ?? 0],
 ].map(([label, value]) => <StatCard key={label} label={String(label)} value={value} />)}</div>
 <DataTable data={rows} getRowId={row => row.row} columns={[
   { key: "row", header: "Row" }, { key: "status", header: "Status", render: row => <StatusPill label={errorRows.has(row.row) || row.errors ? "Error" : row.action ?? "Ready"} tone={errorRows.has(row.row) || row.errors ? "danger" : "neutral"} /> },
   { key: "name", header: "Name", render: row => String(row.data?.name ?? "") },
   { key: "message", header: "Message", render: row => { const errors = errorRows.get(row.row) ?? row.errors, warnings = warningRows.get(row.row) ?? row.warnings; return errors ? messageFor(errors) : warnings ? messageFor(warnings) : ""; } },
 ]} /></div>;
}
