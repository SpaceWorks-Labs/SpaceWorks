import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, EmptyState, PagePager, StatusPill } from "../../components/ui";
import { formatDate } from "../../lib/format";
import { accessKeys, listAccess, revokeAccess, type AccessStatus, type MachineAccessGrant } from "./api";
import { MachineAccessGrantForm, type AccessTarget } from "./MachineAccessGrantForm";
import { LogoLoader } from "../../components/LogoLoader";

const everyMachineOf = (typeName: string | null) => { const label = typeName ?? ""; return t`Every ${label} machine`; };

const statusLabel = (status: AccessStatus) => status === "live" ? t`Has access` : status === "expired" ? t`Expired` : t`Revoked`;
const targetName = (row: MachineAccessGrant) => row.machine_name ?? everyMachineOf(row.machine_type_name);

/** Who may use which machine (decision 319). Staff-only; a Machine Manager sees only their own machine scope. */
export function MachineAccessPanel({ makerspaceId, targets, machineId, machineTypeId, memberId, preselected, showForm = true }: {
  makerspaceId: number; targets: AccessTarget; machineId?: number; machineTypeId?: number; memberId?: number;
  preselected?: { user_id: number; name: string }[]; showForm?: boolean;
}) {
  const client = useQueryClient();
  const [status, setStatus] = useState<AccessStatus | "all">("live");
  const [page, setPage] = useState(1);
  const [convertedOnly, setConvertedOnly] = useState(false);
  const [revoking, setRevoking] = useState<MachineAccessGrant | null>(null);
  const filters = { machineId, machineTypeId, memberId, status, page, ...(convertedOnly ? { source: "migration" as const } : {}) };
  const rows = useQuery({ queryKey: accessKeys.list(makerspaceId, filters), queryFn: () => listAccess(makerspaceId, filters) });
  const revoke = useMutation({ mutationFn: (row: MachineAccessGrant) => revokeAccess(row.id),
    onSuccess: async () => { setRevoking(null); await client.invalidateQueries({ queryKey: accessKeys.all(makerspaceId) }); } });
  const fixed = machineId ? `machine:${machineId}` : machineTypeId ? `type:${machineTypeId}` : undefined;
  return <section className="grid gap-3" aria-label={t`Machine access`}>
    <div className="flex flex-wrap items-end justify-between gap-2">
      <div><h3 className="title-panel">{t`Machine access`}</h3>
        <p className="text-sm text-muted">{t`Members can use a machine only when a space manager has given them access, unless the machine is open to all members.`}</p></div>
      <label className="grid gap-1 text-sm">{t`Show`}<select className="desk-input" value={status} onChange={event => { setStatus(event.target.value as AccessStatus | "all"); setPage(1); }}>
        <option value="live">{t`Has access`}</option><option value="expired">{t`Expired`}</option><option value="revoked">{t`Revoked`}</option><option value="all">{t`Everything`}</option></select></label>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={convertedOnly} onChange={event => { setConvertedOnly(event.target.checked); setPage(1); }} />
        {t`Only access carried over at the upgrade (review these)`}</label>
    </div>
    {rows.isLoading ? <LogoLoader label={t`Loading machine access…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.isSuccess && !rows.data?.count ? <EmptyState message={t`No one has machine access here yet. Give access to a member below.`} /> : null}
    <ul className="grid gap-2">{(rows.data?.results ?? []).map(row => <li key={row.id} className="grid gap-1 rounded-lg border border-line p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2"><strong>{row.member_name}</strong>
        <span className="flex flex-wrap gap-1">{row.source === "migration" ? <StatusPill label={t`Carried over`} tone="info" /> : null}
          <StatusPill label={statusLabel(row.status)} tone={row.status === "live" ? "success" : "warn"} /></span></div>
      <p className="text-muted">{targetName(row)} · {t`Given ${formatDate(row.granted_at)}`}{row.granted_by_name ? t` by ${row.granted_by_name}` : ""} · {row.expires_at ? t`Ends ${formatDate(row.expires_at)}` : t`No end date`}</p>
      {row.note ? <p>{row.note}</p> : null}
      {row.status !== "revoked" ? <div><button className="desk-button-danger min-h-11" disabled={revoke.isPending} onClick={() => setRevoking(row)}>{t`Revoke access`}</button></div> : null}
    </li>)}</ul>
    {rows.data ? <PagePager page={page} setPage={setPage} count={rows.data.count} next={rows.data.next} disabled={rows.isFetching} /> : null}
    {rows.error instanceof Error ? <p role="alert" className="text-sm text-danger">{rows.error.message}</p> : null}
    {revoke.error instanceof Error ? <p role="alert" className="text-sm text-danger">{revoke.error.message}</p> : null}
    {showForm ? <MachineAccessGrantForm makerspaceId={makerspaceId} targets={targets} fixed={fixed} preselected={preselected} /> : null}
    <ConfirmDialog open={revoking !== null} title={t`Revoke machine access?`} message={t`The member can no longer use this machine, starting now. The record stays in history.`}
      confirmLabel={t`Revoke`} tone="danger" pending={revoke.isPending} onConfirm={() => { if (revoking) revoke.mutate(revoking); }} onCancel={() => setRevoking(null)} />
  </section>;
}
