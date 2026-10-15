import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getJobSession, trackJob } from "../../components/ui/jobStore";

import {
  decideRestore,
  getBackupSettings,
  getRestore,
  issueBackupDownload,
  listDeploymentBackups,
  listRestores,
  listTenantBackups,
  requestDeploymentBackup,
  requestRestore,
  requestTenantBackup,
  updateBackupSettings,
  type BackupArchive,
} from "./backupApi";
import { useState } from "react";
import { SettingsLayout } from "../../components/layouts";
import { ErrorText } from "../../components/ui";
import { toast } from "../../components/ui/toastStore";
import { adminQueryState } from "./adminPresentation";
import { ArchiveDisclosure, BackupArchiveRows } from "./BackupArchiveRows";
import { BackupScheduleSettings } from "./BackupScheduleSettings";
import { BackupRestoreDialog } from "./BackupRestoreDialog";
import { RestoreDecision } from "./RestoreDecision";
export { RestoreDecision } from "./RestoreDecision";

export function BackupRestorePanel({ makerspaceId, isSuperadmin, tenantBackupsEnabled = true }: { makerspaceId: number; isSuperadmin: boolean; tenantBackupsEnabled?: boolean }) {
  const client = useQueryClient();
  const [restoreOpen, setRestoreOpen] = useState(false);
  const tenantKey = ["tenant-backups", makerspaceId];
  const deploymentKey = ["deployment-backups"];
  const tenant = useQuery({ queryKey: tenantKey, queryFn: () => listTenantBackups(makerspaceId), enabled: tenantBackupsEnabled, refetchInterval: pollArchives });
  const deployment = useQuery({ queryKey: deploymentKey, queryFn: listDeploymentBackups, enabled: isSuperadmin, refetchInterval: pollArchives });
  const settings = useQuery({ queryKey: ["backup-settings"], queryFn: getBackupSettings, enabled: isSuperadmin });
  const restores = useQuery({ queryKey: ["restore-operations"], queryFn: listRestores, enabled: isSuperadmin, refetchInterval: 3000 });
  const activeRestore = restores.data?.find((row) => !["completed", "failed", "aborted", "restored_quarantined"].includes(row.stage));
  const restoreDetail = useQuery({ queryKey: ["restore-operation", activeRestore?.id], queryFn: () => getRestore(activeRestore!.id), enabled: Boolean(activeRestore), refetchInterval: 1000 });
  const createTenant = useMutation({ onMutate: getJobSession, mutationFn: () => requestTenantBackup(makerspaceId), onSuccess: (job, _variables, session) => { trackJob({ key: `backup:${job.id}`, label: "Makerspace backup", makerspaceId, status: job.status, endpoint: `/admin/makerspace/${makerspaceId}/backups`, collectionId: job.id }, session); return client.invalidateQueries({ queryKey: tenantKey }); } });
  const createDeployment = useMutation({ onMutate: getJobSession, mutationFn: requestDeploymentBackup, onSuccess: (job, _variables, session) => { trackJob({ key: `backup:${job.id}`, label: "Deployment backup", makerspaceId: 0, status: job.status, endpoint: "/admin/platform/backups", collectionId: job.id }, session); return client.invalidateQueries({ queryKey: deploymentKey }); } });
  const saveSettings = useMutation({ mutationFn: updateBackupSettings, onSuccess: (data) => { client.setQueryData(["backup-settings"], data); toast("Backup settings saved."); } });
  const download = useMutation({ mutationFn: issueBackupDownload, onSuccess: ({ url }) => window.location.assign(url) });
  const startRestore = useMutation({ mutationFn: ({ archive, kind }: { archive: string; kind: "rollback_in_place" | "disaster" }) => requestRestore(archive, kind), onSuccess: () => { setRestoreOpen(false); return client.invalidateQueries({ queryKey: ["restore-operations"] }); } });
  const decision = useMutation({ mutationFn: ({ id, value }: { id: string; value: "proceed" | "reset" | "abort" }) => decideRestore(id, value), onSuccess: () => client.invalidateQueries({ queryKey: ["restore-operations"] }) });

  const available = (deployment.data ?? []).filter(row => row.status === "available");
  const primary = tenantBackupsEnabled
    ? { label: "Create makerspace archive", onClick: () => createTenant.mutate(), pending: createTenant.isPending, pendingLabel: "Requesting…" }
    : isSuperadmin ? { label: "Create full deployment archive", onClick: () => createDeployment.mutate(), pending: createDeployment.isPending, pendingLabel: "Requesting…" } : undefined;
  return <>
    <SettingsLayout header={{ title: "Backup & restore", subtitle: "Keep encrypted copies of your space and review every restore before it changes live data.", primary }}
      state={{ status: "ready" }} sections={[
        { id: "this-space", title: "This space", rows: tenantBackupsEnabled ? <div className="grid gap-4">
          <ArchiveDisclosure deployment={false} />
          <BackupQuery query={tenant} resource="makerspace backups"><BackupArchiveRows rows={tenant.data ?? []} onDownload={id => download.mutate(id)} downloading={download.isPending ? download.variables : undefined} /></BackupQuery>
          {createTenant.error ? <ErrorText message={createTenant.error.message} /> : null}
        </div> : <p className="text-sm text-muted">The backup module is not installed for this makerspace; the deployment's own backups still cover it.</p> },
        ...(isSuperadmin ? [{ id: "deployment", title: "Deployment", rows: <div className="grid gap-4">
          <ArchiveDisclosure deployment />
          <BackupQuery query={settings} resource="backup settings">{settings.data ? <BackupScheduleSettings key={makerspaceId} data={settings.data} pending={saveSettings.isPending} onSave={(value, onSaved) => saveSettings.mutate(value, { onSuccess: onSaved })} /> : null}</BackupQuery>
          {saveSettings.error ? <ErrorText message={saveSettings.error.message} /> : null}
          {tenantBackupsEnabled ? <button type="button" className="desk-button w-fit" disabled={createDeployment.isPending} onClick={() => createDeployment.mutate()}>{createDeployment.isPending ? "Requesting…" : "Create full deployment archive"}</button> : null}
          <BackupQuery query={deployment} resource="deployment backups"><BackupArchiveRows rows={deployment.data ?? []} onDownload={id => download.mutate(id)} downloading={download.isPending ? download.variables : undefined} /></BackupQuery>
          {createDeployment.error ? <ErrorText message={createDeployment.error.message} /> : null}
          {restoreDetail.data ? <RestoreDecision operation={restoreDetail.data} pending={decision.isPending} onDecide={value => decision.mutate({ id: restoreDetail.data!.id, value })} /> : null}
          {restores.isError ? <ErrorText resource="restore operations" onRetry={() => { void restores.refetch(); }} /> : null}
          {restoreDetail.isError ? <ErrorText resource="restore report" onRetry={() => { void restoreDetail.refetch(); }} /> : null}
          {decision.error ? <ErrorText message={decision.error.message} /> : null}
        </div> }] : []),
        ...(download.error ? [{ id: "download-error", title: "Download", rows: <ErrorText message={download.error.message} /> }] : []),
      ]} danger={isSuperadmin ? [{ title: "Restore from a backup", consequence: "A restore replaces live deployment data. Review the archive and recovery kind before starting.",
        action: { label: "Restore from a backup…", onClick: () => setRestoreOpen(true), disabled: !available.length, disabledReason: "Create a full deployment archive before restoring." } }] : []} />
    {restoreOpen ? <BackupRestoreDialog archives={available} pending={startRestore.isPending} error={startRestore.error} onCancel={() => setRestoreOpen(false)} onRestore={(archive, kind) => startRestore.mutate({ archive, kind })} /> : null}
  </>;
}

import { QueryContent } from "../../components/layouts/LayoutFrame";
import type { ReactNode } from "react";
function BackupQuery({ query, resource, children }: { query: Parameters<typeof adminQueryState>[0]; resource: string; children: ReactNode }) {
  return <QueryContent state={adminQueryState(query, resource)}>{children}</QueryContent>;
}
function pollArchives(query: { state: { data?: BackupArchive[] } }) { return query.state.data?.some(row => row.status === "pending" || row.status === "running" || row.status === "promoting") ? 2000 : false; }
