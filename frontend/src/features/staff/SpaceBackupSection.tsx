import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EmptyState, ErrorText, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import { ACTIVE_RESTORE_STAGES, listSpaceBackups, listSpaceRestores, requestSpaceBackup, startSpaceRestore } from "./spaceRestoreApi";
import { SpaceRestoreFlow } from "./SpaceRestoreFlow";

const TRIGGER: Record<string, string> = { nightly: "Nightly", on_demand: "Back up now", safety: "Before a restore",
  extracted: "From a whole-platform backup" };

/** One space's restore points, "Back up now" and its restores (superadmin, #111 SEAMLESS). */
export function SpaceBackupSection({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [openRestore, setOpenRestore] = useState<string | null>(null);
  const backupsKey = ["space-backups", makerspaceId];
  const backups = useQuery({ queryKey: backupsKey, queryFn: () => listSpaceBackups(makerspaceId) });
  const restores = useQuery({ queryKey: ["space-restores", makerspaceId], queryFn: () => listSpaceRestores(makerspaceId),
    refetchInterval: (state) => (state.state.data?.some(row => ACTIVE_RESTORE_STAGES.includes(row.stage)) ? 3000 : false) });
  const backupNow = useMutation({ mutationFn: () => requestSpaceBackup(makerspaceId),
    onSuccess: () => client.invalidateQueries({ queryKey: backupsKey }) });
  const restore = useMutation({ mutationFn: (archive: string) => startSpaceRestore(makerspaceId, archive),
    onSuccess: (op) => { setOpenRestore(op.id); return client.invalidateQueries({ queryKey: ["space-restores", makerspaceId] }); } });
  const active = restores.data?.find(row => ACTIVE_RESTORE_STAGES.includes(row.stage));
  const points = (backups.data ?? []).filter(row => row.status === "available");
  return <div className="grid gap-4">
    <div className="flex flex-wrap items-center gap-3">
      <button className="desk-button-primary" type="button" disabled={backupNow.isPending} onClick={() => backupNow.mutate()}>
        {backupNow.isPending ? "Starting backup…" : "Back up now"}</button>
      {backupNow.isSuccess ? <span role="status" className="text-sm text-muted">Backup started; it appears below when it completes.</span> : null}
    </div>
    {backupNow.error ? <ErrorText message={backupNow.error.message} /> : null}
    {active ? <ListRow title="Restore in progress" identity={{ kind: "date", date: active.created_at }}
      meta={<StatusPill label={active.stage.replace(/_/g, " ")} tone="warn" />}
      right={<button className="desk-button" type="button" onClick={() => setOpenRestore(active.id)}>Open</button>} /> : null}
    {backups.isError ? <ErrorText resource="restore points" onRetry={() => { void backups.refetch(); }} /> : null}
    {backups.isSuccess && !points.length ? <EmptyState message="No restore points for this space yet. Back it up now, or wait for tonight's backup." /> : null}
    <ul className="grid gap-3" aria-label="Restore points">{points.map(row => <li key={row.id}><ListRow
      title={TRIGGER[row.trigger] ?? "Backup"} identity={{ kind: "date", date: row.completed_at ?? row.created_at }}
      meta={<><RelativeTime date={row.completed_at ?? row.created_at} /> · {row.size_bytes ? `${(row.size_bytes / 1024 / 1024).toFixed(1)} MB` : "—"}</>}
      right={row.restorable_in_app
        ? <button className="desk-button-danger-outline" type="button" disabled={Boolean(active) || restore.isPending}
            onClick={() => restore.mutate(row.id)}>Restore…</button>
        : <span className="text-sm text-muted">Not restorable here</span>} /></li>)}</ul>
    {restore.error ? <ErrorText message={restore.error.message} /> : null}
    {restores.data?.filter(row => !ACTIVE_RESTORE_STAGES.includes(row.stage)).slice(0, 5).map(row => <ListRow key={row.id}
      title={`Restore ${row.stage}`} identity={{ kind: "date", date: row.created_at }}
      meta={row.error_detail || (row.finished_at ? <RelativeTime date={row.finished_at} /> : null)}
      right={<button className="desk-button" type="button" onClick={() => setOpenRestore(row.id)}>Details</button>} />)}
    {openRestore ? <SpaceRestoreFlow restoreId={openRestore} onClose={() => setOpenRestore(null)} /> : null}
  </div>;
}
