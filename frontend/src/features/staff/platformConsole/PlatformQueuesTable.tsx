import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { DataTable, EmptyState, ErrorText, Skeleton } from "../../../components/ui";
import { openSpaceTab } from "./openSpaceTab";
import { crossSpaceKeys, getQueues, QUEUE_COLUMNS, sumKeys, type QueueRow } from "./crossSpaceApi";

function Count({ value, urgent }: { value: number; urgent?: boolean }) {
  if (!value) return <span className="tabular-nums text-muted">0</span>;
  return <span className={`rounded-full px-2.5 py-0.5 text-sm font-semibold tabular-nums ${urgent ? "bg-danger text-on-danger" : "bg-emphasis text-on-emphasis"}`}>{value}</span>;
}

/**
 * Decision 242(l) / U7: what is waiting in each space, counts only (no rows from inside a space).
 * Busiest spaces first; "Only spaces with something waiting" hides the quiet ones on a big install.
 */
export function PlatformQueuesTable() {
  const queues = useQuery({ queryKey: crossSpaceKeys.queues, queryFn: getQueues, refetchInterval: 120_000 });
  const [busyOnly, setBusyOnly] = useState(true);
  if (queues.isLoading) return <div role="status" aria-label={t`Loading queues by space`}><Skeleton className="h-32 w-full" /></div>;
  if (queues.isError) return <ErrorText resource={t`queues by space`} onRetry={() => { void queues.refetch(); }} />;
  const all = [...queues.data?.spaces ?? []].sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  const rows = busyOnly ? all.filter(row => row.total > 0) : all;
  return <div className="grid gap-3">
    <label className="flex min-h-11 w-fit items-center gap-2 text-sm">
      <input type="checkbox" className="h-4 w-4" checked={busyOnly} onChange={event => setBusyOnly(event.target.checked)} />
      {t`Only spaces with something waiting`}
    </label>
    {rows.length ? <DataTable<QueueRow> caption={t`Queues and safety by space`} data={rows} getRowId={row => row.id} columns={[
      { key: "name", header: t`Space`, phone: "title", render: row => <span className="font-semibold">{row.name}</span> },
      ...QUEUE_COLUMNS.map(column => ({ key: column.key, header: column.label(),
        render: (row: QueueRow) => <Count value={sumKeys(row.counts, column.keys)} urgent={column.urgent} /> })),
      { key: "actions", header: t`Open`, render: row => <button type="button" className="desk-button min-h-11"
        onClick={() => openSpaceTab(row.id, "/admin/dashboard")}>{t`Open ${row.name}`}</button> },
    ]} /> : <EmptyState message={busyOnly && all.length ? t`Nothing is waiting in any space right now.` : t`No live spaces yet.`} />}
  </div>;
}
