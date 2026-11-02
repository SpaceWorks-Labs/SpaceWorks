import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getJobSession, trackJob } from "../../components/ui/jobStore";

import {
  decideRestore,
  getBackupSettings,
  getRestore,
  issueBackupDownload,
  listDeploymentBackups,
  listRestores,
  requestDeploymentBackup,
  requestRestore,
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
import { BackupStatusCard } from "./panels/DashboardArchiveStatus";
export { RestoreDecision } from "./RestoreDecision";

import { getPlatformDashboard } from "./platformMonitoringApi";
import { SpaceBackupSection } from "./SpaceBackupSection";
import { BackupScheduleView } from "./BackupScheduleView";
import { getBackupSchedule } from "./spaceRestoreApi";
import { DeploymentNotices } from "../deployment/DeploymentNotices";
import { SelfHostMoveCard } from "./SelfHostMoveCard";

export function BackupRestorePanel({ makerspaceId, isSuperadmin }: { makerspaceId: number; isSuperadmin: boolean }) {
  const runtime = useQuery({ queryKey: ["platform-dashboard"], queryFn: getPlatformDashboard, enabled: isSuperadmin });
  const deploymentInfo = runtime.data?.deployment;
  const hostControls = isSuperadmin && deploymentInfo?.mode === "host";
  const client = useQueryClient();
  const [restoreOpen, setRestoreOpen] = useState(false);
  // One flow for both scopes (#111 SEAMLESS): the whole platform, or one space.
  const [scope, setScope] = useState<"platform" | number>("platform");
  const schedule = useQuery({ queryKey: ["backup-schedule"], queryFn: getBackupSchedule, enabled: isSuperadmin });
  const deploymentKey = ["deployment-backups"];
  const deployment = useQuery({ queryKey: deploymentKey, queryFn: listDeploymentBackups, enabled: hostControls, refetchInterval: pollArchives });
  const settings = useQuery({ queryKey: ["backup-settings"], queryFn: getBackupSettings, enabled: hostControls });
  const restores = useQuery({ queryKey: ["restore-operations"], queryFn: listRestores, enabled: hostControls, refetchInterval: 3000 });
  const activeRestore = restores.data?.find((row) => !["completed", "failed", "aborted", "restored_quarantined"].includes(row.stage));
  const restoreDetail = useQuery({ queryKey: ["restore-operation", activeRestore?.id], queryFn: () => getRestore(activeRestore!.id), enabled: Boolean(activeRestore), refetchInterval: 1000 });
  const createDeployment = useMutation({ onMutate: getJobSession, mutationFn: requestDeploymentBackup, onSuccess: (job, _variables, session) => { trackJob({ key: `backup:${job.id}`, label: "Deployment backup", makerspaceId: 0, status: job.status, endpoint: "/admin/platform/backups", collectionId: job.id }, session); return client.invalidateQueries({ queryKey: deploymentKey }); } });
  const saveSettings = useMutation({ mutationFn: updateBackupSettings, onSuccess: (data) => { client.setQueryData(["backup-settings"], data); toast("Backup settings saved."); } });
  const download = useMutation({ mutationFn: issueBackupDownload, onSuccess: ({ url }) => window.location.assign(url) });
  const startRestore = useMutation({ mutationFn: ({ archive, kind }: { archive: string; kind: "rollback_in_place" | "disaster" }) => requestRestore(archive, kind), onSuccess: () => { setRestoreOpen(false); return client.invalidateQueries({ queryKey: ["restore-operations"] }); } });
  const decision = useMutation({ mutationFn: ({ id, value }: { id: string; value: "proceed" | "reset" | "abort" }) => decideRestore(id, value), onSuccess: () => client.invalidateQueries({ queryKey: ["restore-operations"] }) });

  const available = (deployment.data ?? []).filter(row => row.status === "available");
  const primary = hostControls && scope === "platform" ? { label: "Create full deployment archive", onClick: () => createDeployment.mutate(), pending: createDeployment.isPending, pendingLabel: "Requesting…" } : undefined;
  return <>
    <SettingsLayout header={{ title: "Backup & restore", subtitle: "Keep encrypted copies of your space and review every restore before it changes live data.", primary }}
      state={{ status: "ready" }} sections={[
        ...(isSuperadmin && runtime.isError ? [{ id: "deployment-status", title: "Deployment information", rows: <ErrorText resource="deployment information" onRetry={() => { void runtime.refetch(); }} /> }] : []),
        // Managers no longer request or download archives (owner decision #111 Q2): the
        // superadmin backs up and restores; a manager reads the last backup and keeps their
        // own copy through data export.
        ...(!isSuperadmin ? [{ id: "this-space", title: "This space", rows: <div className="grid gap-3">
          <BackupStatusCard makerspaceId={makerspaceId} />
          <p className="text-sm text-muted">The platform backs up and restores this space. For your own copy of its data, use Data export.</p>
        </div> }] : []),
        ...(!isSuperadmin ? [{ id: "self-host-move", title: "Move to your own server", rows: <SelfHostMoveCard makerspaceId={makerspaceId} /> }] : []),
        ...(isSuperadmin ? [{ id: "scope", title: "What to back up or restore", rows: <label className="grid gap-2 text-sm">Scope
          <select className="desk-input max-w-full" value={String(scope)} onChange={event => setScope(event.target.value === "platform" ? "platform" : Number(event.target.value))}>
            <option value="platform">Whole platform</option>
            {(schedule.data?.spaces ?? []).map(space => <option key={space.makerspace_id} value={space.makerspace_id}>One space: {space.name}</option>)}
          </select></label> }] : []),
        ...(isSuperadmin && scope !== "platform" ? [{ id: "space", title: "This space's restore points", rows: <SpaceBackupSection key={scope} makerspaceId={scope} /> }] : []),
        ...(isSuperadmin ? [{ id: "schedule", title: "Schedule", rows: <BackupScheduleView onPickSpace={setScope} /> }] : []),
        ...(deploymentInfo?.mode === "managed" && scope === "platform" ? [{ id: "managed-deployment", title: "Deployment recovery", rows: <DeploymentNotices data={deploymentInfo} /> }] : []),
        ...(hostControls && scope === "platform" ? [{ id: "deployment", title: "Whole platform", rows: <div className="grid gap-4">
          <ArchiveDisclosure deployment />
          <p className="text-sm text-muted">One space from a whole-platform backup: restore via host command (see docs). It becomes a restore point of that space here.</p>
          <BackupQuery query={settings} resource="backup settings">{settings.data ? <BackupScheduleSettings deployment={deploymentInfo} key={makerspaceId} data={settings.data} pending={saveSettings.isPending} onSave={(value, onSaved) => saveSettings.mutate(value, { onSuccess: onSaved })} /> : null}</BackupQuery>
          {saveSettings.error ? <ErrorText message={saveSettings.error.message} /> : null}
          <BackupQuery query={deployment} resource="deployment backups"><BackupArchiveRows rows={deployment.data ?? []} onDownload={id => download.mutate(id)} downloading={download.isPending ? download.variables : undefined} /></BackupQuery>
          {createDeployment.error ? <ErrorText message={createDeployment.error.message} /> : null}
          {restoreDetail.data ? <RestoreDecision operation={restoreDetail.data} pending={decision.isPending} onDecide={value => decision.mutate({ id: restoreDetail.data!.id, value })} /> : null}
          {restores.isError ? <ErrorText resource="restore operations" onRetry={() => { void restores.refetch(); }} /> : null}
          {restoreDetail.isError ? <ErrorText resource="restore report" onRetry={() => { void restoreDetail.refetch(); }} /> : null}
          {decision.error ? <ErrorText message={decision.error.message} /> : null}
        </div> }] : []),
        ...(download.error ? [{ id: "download-error", title: "Download", rows: <ErrorText message={download.error.message} /> }] : []),
      ]} danger={hostControls && scope === "platform" ? [{ title: "Restore from a backup", consequence: "A restore replaces live deployment data. Review the archive and recovery kind before starting.",
        action: { label: "Restore from a backup…", onClick: () => setRestoreOpen(true), disabled: !available.length, disabledReason: "Create a full deployment archive before restoring." } }] : []} />
    {hostControls && restoreOpen ? <BackupRestoreDialog archives={available} pending={startRestore.isPending} error={startRestore.error} onCancel={() => setRestoreOpen(false)} onRestore={(archive, kind) => startRestore.mutate({ archive, kind })} /> : null}
  </>;
}

import { QueryContent } from "../../components/layouts/LayoutFrame";
import type { ReactNode } from "react";
function BackupQuery({ query, resource, children }: { query: Parameters<typeof adminQueryState>[0]; resource: string; children: ReactNode }) {
  return <QueryContent state={adminQueryState(query, resource)}>{children}</QueryContent>;
}
function pollArchives(query: { state: { data?: BackupArchive[] } }) { return query.state.data?.some(row => row.status === "pending" || row.status === "running" || row.status === "promoting") ? 2000 : false; }
