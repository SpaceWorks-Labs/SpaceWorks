import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorBlock, Field, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { plural } from "../../lib/plural";
import { KioskReplayDetail } from "./KioskReplayDetail";
import { KioskReplayResolution } from "./KioskReplayResolution";
import { useKioskReplays, useReplayDetail } from "./useKioskReplays";

export function KioskReplayRecoveryPanel({ makerspaceId }: { makerspaceId: number }) {
  return <RecoveryPanel key={makerspaceId} makerspaceId={makerspaceId} />;
}

function RecoveryPanel({ makerspaceId }: { makerspaceId: number }) {
  const [resolution, setResolution] = useState("unresolved");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<boolean | null>(null);
  const list = useKioskReplays(makerspaceId, resolution, page);
  const detail = useReplayDetail(selected);
  const open = expanded ?? (list.isPending || list.isError || (list.data?.count ?? 0) > 0);
  return <CollapsibleSection title={`Failed kiosk handovers · ${list.data?.count ?? "…"}`}
    open={open} onToggle={() => setExpanded(!open)}>
    <div className="grid gap-3 p-4">
      <p className="text-sm text-muted">Review retained failed attempts for operations you may currently perform.</p>
      <Field label="Recovery status"><select className="desk-input" value={resolution} onChange={(event) => {
        setResolution(event.target.value); setPage(1); setSelected(null);
      }}><option value="unresolved">Unresolved</option><option value="resolved">Resolved</option><option value="all">All failures</option></select></Field>
      {list.isPending ? <p role="status">Loading failed handovers…</p> : list.isError
        ? <ErrorBlock error={list.error} resource="failed handovers" onRetry={() => { void list.refetch(); }} />
        : !list.data?.results.length ? <EmptyState message="No retained failures in this view." /> : <ul className="grid gap-3">
        {list.data.results.map((row) => <li key={row.id}>
          <ListRow title={`${row.operation_kind.replace(/_/g, " ")} · ${row.station_name} · ${row.failure_code}`}
            meta={<RelativeTime date={row.created_at} />} right={<div className="flex flex-wrap items-center gap-3">
              <StatusPill tone={row.resolution_code ? "success" : "warn"} label={row.resolution_code ? "Resolved" : "Unresolved"} />
              <button type="button" className="desk-button" aria-expanded={selected === row.id}
                aria-label={`${row.operation_kind.replace(/_/g, " ")} · ${row.station_name} · ${row.failure_code}`}
                onClick={() => setSelected(selected === row.id ? null : row.id)}>{selected === row.id ? "Close details" : "Review"}</button>
            </div>} />
          {selected === row.id ? detail.isPending ? <p role="status">Loading failure details…</p> : detail.isError ? <p role="alert">This failure is unavailable under your current permissions.</p> : detail.data ? <div className="mt-3">
            <KioskReplayDetail key={row.id} row={detail.data} />
            <KioskReplayResolution key={`${row.id}/${detail.data.resolution_code}`} row={detail.data} />
          </div> : null : null}
        </li>)}
      </ul>}
      {list.data ? <nav className="flex gap-3 text-sm" aria-label="Recovery pages">
        <button type="button" className="desk-button" disabled={!list.data.previous || list.isFetching} onClick={() => { setPage(page - 1); setSelected(null); }}>Previous failures</button>
        <span>Page {page} · {plural(list.data.count, "failure")}</span>
        <button type="button" className="desk-button" disabled={!list.data.next || list.isFetching} onClick={() => { setPage(page + 1); setSelected(null); }}>Next failures</button>
      </nav> : null}
    </div>
  </CollapsibleSection>;
}
