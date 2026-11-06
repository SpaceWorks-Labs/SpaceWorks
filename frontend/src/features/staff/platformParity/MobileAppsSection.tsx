import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, Skeleton, StatusPill } from "../../../components/ui";
import { MobileReadinessPanel } from "./MobileReadinessPanel";
import { NativeAppForm } from "./NativeAppForm";
import { useNativeApps } from "./nativeAppsApi";
import { PAGE_SIZE } from "./parityRequest";

const TONES = { pending: "neutral", approved: "success", revoked: "danger" } as const;

/** The Space Works mobile app identities this server accepts attested sign-ins from. Never deleted: revoke instead. */
export function MobileAppsSection() {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const list = useNativeApps(page);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">Only one approved app per platform and environment serves the whole deployment. Revoking an app ends every
      device sign-in it issued; the record stays for the audit trail.</p>
    <CollapsibleSection title="Register an app" open={adding} onToggle={() => setAdding(!adding)}><NativeAppForm /></CollapsibleSection>
    {list.isLoading ? <Skeleton className="h-24 w-full" />
      : list.isError ? <ErrorText resource="mobile apps" onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message="No mobile app is registered yet." />
      : <div className="grid gap-3">{rows.map(row => <div key={row.id} className="grid gap-2">
        <ListRow title={row.app_id}
          meta={<>{row.platform === "apple" ? "Apple" : "Android"} · {row.environment} · {row.makerspace ? `space #${row.makerspace}` : "whole deployment"}
            {" · changed "}<RelativeTime date={row.updated_at} exact />{row.approved_by ? ` · approved by ${row.approved_by}` : ""}</>}
          right={<div className="flex flex-wrap items-center gap-2">
            <StatusPill label={row.status[0].toUpperCase() + row.status.slice(1)} tone={TONES[row.status]} />
            <button type="button" className="desk-button" aria-expanded={editing === row.id} aria-label={`Edit ${row.app_id}`}
              onClick={() => setEditing(editing === row.id ? null : row.id)}>Edit</button>
          </div>} />
        {editing === row.id ? <div className="rounded-xl border border-line bg-panel"><NativeAppForm row={row} onDone={() => setEditing(null)} /></div> : null}
      </div>)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    <MobileReadinessPanel />
  </div>;
}
