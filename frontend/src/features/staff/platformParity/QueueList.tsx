import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { EmptyState, ErrorText, Field, Pagination, type Tone } from "../../../components/ui";
import { PAGE_SIZE } from "./parityRequest";
import { useQueue, type QueueKind } from "./requestsApi";
import { LogoLoader } from "../../../components/LogoLoader";

export const QUEUE_TONES: Record<string, Tone> = {
  pending: "info", approved: "success", declined: "neutral", rejected: "neutral", withdrawn: "neutral",
};

type Props<T> = {
  kind: QueueKind; title: string; resource: string;
  /** Status key → label; the first entry, "pending", is the default filter. */
  statuses: Record<string, string>;
  renderRow: (row: T) => ReactNode;
};

/** One request queue: a status filter (pending first), the rows, and paging. */
export function QueueList<T extends { id: number }>({ kind, title, resource, statuses, renderRow }: Props<T>) {
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useState(1);
  const list = useQueue<T>(kind, status, page);
  const rows = list.data?.results ?? [];
  const headingId = `queue-${kind}`;
  return <section className="grid gap-3" aria-labelledby={headingId}>
    <h3 id={headingId} className="title-section">{title}</h3>
    <Field label={t`Status`} className="sm:max-w-64">
      <select className="desk-input" aria-label={`${title} status`} value={status} onChange={event => { setStatus(event.target.value); setPage(1); }}>
        {Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        <option value="">{t`Every status`}</option>
      </select>
    </Field>
    {list.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" />
      : list.isError ? <ErrorText resource={resource} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={status === "pending" ? t`Nothing is waiting.` : t`Nothing here.`} />
      : <div className="grid gap-3">{rows.map(row => <div key={row.id}>{renderRow(row)}</div>)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
  </section>;
}
