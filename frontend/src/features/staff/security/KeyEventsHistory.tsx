import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorText, Pagination, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { formatLocale } from "../../../lib/format";

export type KeyEvent = {
  id: number; kind: string; status: string; from_version: number | null; to_version: number | null;
  rows_done: number; rows_skipped: number; retained_versions: number[] | null; error_code: string;
  started_at: string | null; updated_at: string; completed_at: string | null;
};
type Page = { count: number; results: KeyEvent[] };

const TONE: Record<string, "success" | "warn" | "danger" | "neutral"> = {
  completed: "success", running: "warn", pending: "warn", failed: "danger",
};
const PAGE_SIZE = 24;
const kindLabel = (kind: string) => ({ rotation: t`Key rotation`, emergency_rekey: t`Emergency key change`,
  search_reindex: t`Search key rotation` } as Record<string, string>)[kind] ?? kind.replace(/_/g, " ");
const statusLabel = (status: string) => ({ running: t`Running`, pending: t`Pending`, completed: t`Completed`,
  failed: t`Failed` } as Record<string, string>)[status] ?? status.replace(/_/g, " ");
const when = (value: string | null) => value ? new Date(value).toLocaleString(formatLocale()) : "—";

/**
 * Read-only history of this space's key rotations, re-keys and re-indexes. Starting one is a
 * platform action in /control/; no key material is ever returned here.
 */
export function KeyEventsHistory({ makerspaceId }: { makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["security-key-events", makerspaceId, page], retry: false,
    queryFn: () => staffRequest<Page | KeyEvent[]>(`/admin/makerspaces/${makerspaceId}/security/key-events?page=${page}`) });
  const results = Array.isArray(query.data) ? query.data : query.data?.results ?? [];
  const count = Array.isArray(query.data) ? query.data.length : query.data?.count ?? results.length;
  if (query.isLoading) return <LogoLoader label={t`Loading key history…`} size={48} className="min-h-16 py-3" />;
  if (query.error) return <ErrorText message={query.error.message} />;
  if (!results.length) return <p className="text-sm text-muted">{t`No key rotations have run for this space yet.`}</p>;
  return <div className="grid gap-2">
    <ul className="grid gap-2">
      {results.map(row => <li key={row.id} className="grid gap-1 rounded-lg border border-line bg-panel p-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="grid gap-1">
          <p className="font-semibold">{kindLabel(row.kind)}{row.to_version !== null ? t` · version ${row.from_version ?? "—"} → ${row.to_version}` : ""}</p>
          <p className="text-sm text-muted">{t`Started ${when(row.started_at)} · finished ${when(row.completed_at)} · ${row.rows_done} rows done, ${row.rows_skipped} skipped`}</p>
          {row.error_code ? <p className="text-sm text-danger">{t`Error: ${row.error_code}`}</p> : null}
        </div>
        <StatusPill label={statusLabel(row.status)} tone={TONE[row.status] ?? "neutral"} />
      </li>)}
    </ul>
    {count > PAGE_SIZE ? <Pagination page={page} totalPages={Math.ceil(count / PAGE_SIZE)}
      count={count} pageSize={PAGE_SIZE} onChange={setPage} /> : null}
  </div>;
}
