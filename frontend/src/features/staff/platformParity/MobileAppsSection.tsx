import { t } from "@lingui/core/macro";
import { useState } from "react";
import { CollapsibleSection, EmptyState, ErrorText, ListRow, Pagination, RelativeTime, StatusPill } from "../../../components/ui";
import { MobileReadinessPanel } from "./MobileReadinessPanel";
import { NativeAppForm } from "./NativeAppForm";
import { useNativeApps } from "./nativeAppsApi";
import { PAGE_SIZE } from "./parityRequest";
import { LogoLoader } from "../../../components/LogoLoader";

const TONES = { pending: "neutral", approved: "success", revoked: "danger" } as const;

/** The Space Works mobile app identities this server accepts attested sign-ins from. Never deleted: revoke instead. */
export function MobileAppsSection() {
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const list = useNativeApps(page);
  const rows = list.data?.results ?? [];
  return <div className="grid gap-4">
    <p className="text-sm text-muted">{t`Only one approved app per platform and environment serves the whole deployment. Revoking an app ends every device sign-in it issued; the record stays for the audit trail.`}</p>
    <CollapsibleSection title={t`Register an app`} open={adding} onToggle={() => setAdding(!adding)}><NativeAppForm /></CollapsibleSection>
    {list.isLoading ? <LogoLoader size={48} className="min-h-24 py-3" />
      : list.isError ? <ErrorText resource={t`mobile apps`} onRetry={() => { void list.refetch(); }} />
      : !rows.length ? <EmptyState message={t`No mobile app is registered yet.`} />
      : <div className="grid gap-3">{rows.map(row => <div key={row.id} className="grid gap-2">
        <ListRow title={row.app_id}
          meta={<>{row.platform === "apple" ? t`Apple` : t`Android`} · {row.environment} · {row.makerspace ? t`space #${row.makerspace}` : t`whole deployment`}
            {t` · changed `}<RelativeTime date={row.updated_at} exact />{row.approved_by ? t` · approved by ${row.approved_by}` : ""}</>}
          right={<div className="flex flex-wrap items-center gap-2">
            <StatusPill label={row.status[0].toUpperCase() + row.status.slice(1)} tone={TONES[row.status]} />
            <button type="button" className="desk-button" aria-expanded={editing === row.id} aria-label={t`Edit ${row.app_id}`}
              onClick={() => setEditing(editing === row.id ? null : row.id)}>{t`Edit`}</button>
          </div>} />
        {editing === row.id ? <div className="rounded-xl border border-line bg-panel"><NativeAppForm row={row} onDone={() => setEditing(null)} /></div> : null}
      </div>)}</div>}
    <Pagination page={page} totalPages={Math.max(1, Math.ceil((list.data?.count ?? 0) / PAGE_SIZE))} onChange={setPage}
      count={list.data?.count} pageSize={PAGE_SIZE} disabled={list.isFetching} />
    <MobileReadinessPanel />
  </div>;
}
