import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { CollapsibleSection, EmptyState, ErrorBlock, Field, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { plural } from "../../lib/plural";
import { KioskReplayDetail } from "./KioskReplayDetail";
import { KioskReplayResolution } from "./KioskReplayResolution";
import { useKioskReplays, useReplayDetail } from "./useKioskReplays";

/** `revealKey` changing (a callout's "Review failures") opens the section and scrolls it into view. */
export function KioskReplayRecoveryPanel({ makerspaceId, revealKey = 0 }: { makerspaceId: number; revealKey?: number }) {
  return <RecoveryPanel key={makerspaceId} makerspaceId={makerspaceId} revealKey={revealKey} />;
}

function RecoveryPanel({ makerspaceId, revealKey }: { makerspaceId: number; revealKey: number }) {
  const [resolution, setResolution] = useState("unresolved");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<boolean | null>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const list = useKioskReplays(makerspaceId, resolution, page);
  const detail = useReplayDetail(selected);
  useEffect(() => {
    if (!revealKey) return;
    setExpanded(true);
    anchor.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [revealKey]);
  const open = expanded ?? (list.isPending || list.isError || (list.data?.count ?? 0) > 0);
  return <div ref={anchor} className="scroll-mt-4"><CollapsibleSection title={t`Failed kiosk handovers · ${list.data?.count ?? "…"}`}
    open={open} onToggle={() => setExpanded(!open)}>
    <div className="grid gap-3 p-4">
      <p className="text-sm text-muted">{t`Review retained failed attempts for operations you may currently perform.`}</p>
      <Field label={t`Recovery status`}><select className="desk-input" value={resolution} onChange={(event) => {
        // Keep the section open on an empty filter, or the filter itself would vanish.
        setResolution(event.target.value); setPage(1); setSelected(null); setExpanded(true);
      }}><option value="unresolved">{t`Unresolved`}</option><option value="resolved">{t`Resolved`}</option><option value="all">{t`All failures`}</option></select></Field>
      {list.isPending ? <p role="status">{t`Loading failed handovers…`}</p> : list.isError
        ? <ErrorBlock error={list.error} resource="failed handovers" onRetry={() => { void list.refetch(); }} />
        : !list.data?.results.length ? <EmptyState message={t`No retained failures in this view.`} /> : <ul className="grid gap-3">
        {list.data.results.map((row) => <li key={row.id}>
          <ListRow title={`${row.operation_kind.replace(/_/g, " ")} · ${row.station_name} · ${row.failure_code}`}
            meta={<RelativeTime date={row.created_at} />} right={<div className="flex flex-wrap items-center gap-3">
              <StatusPill tone={row.resolution_code ? "success" : "warn"} label={row.resolution_code ? t`Resolved` : t`Unresolved`} />
              <button type="button" className="desk-button" aria-expanded={selected === row.id}
                aria-label={`${row.operation_kind.replace(/_/g, " ")} · ${row.station_name} · ${row.failure_code}`}
                onClick={() => setSelected(selected === row.id ? null : row.id)}>{selected === row.id ? t`Close details` : t`Review`}</button>
            </div>} />
          {selected === row.id ? detail.isPending ? <p role="status">{t`Loading failure details…`}</p> : detail.isError ? <p role="alert">{t`This failure is unavailable under your current permissions.`}</p> : detail.data ? <div className="mt-3">
            <KioskReplayDetail key={row.id} row={detail.data} />
            <KioskReplayResolution key={`${row.id}/${detail.data.resolution_code}`} row={detail.data} />
          </div> : null : null}
        </li>)}
      </ul>}
      {list.data ? <nav className="flex flex-wrap items-center gap-3 text-sm" aria-label={t`Recovery pages`}>
        <button type="button" className="desk-button" disabled={!list.data.previous || list.isFetching} onClick={() => { setPage(page - 1); setSelected(null); }}>{t`Previous failures`}</button>
        <span>{t`Page ${page} · ${plural(list.data.count, "failure")}`}</span>
        <button type="button" className="desk-button" disabled={!list.data.next || list.isFetching} onClick={() => { setPage(page + 1); setSelected(null); }}>{t`Next failures`}</button>
      </nav> : null}
    </div>
  </CollapsibleSection></div>;
}
