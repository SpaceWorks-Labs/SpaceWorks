import { useQuery } from "@tanstack/react-query";
import { KeyValueCard, RelativeTime, StatusPill } from "../../../components/ui";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { getMakerspaceBackupStatus } from "../backupApi";
import { staffTabPath } from "../staffTabs";

type Props = { makerspaceId: number; slug: string; guestOnly: boolean; singleTenantLocked: boolean };

/** The read-only "Last backup" items for this makerspace. A missing archive is a warning, never a silent zero. */
export function BackupStatusCard({ makerspaceId }: { makerspaceId: number }) {
  const status = useQuery({ queryKey: ["backup-status", makerspaceId], queryFn: () => getMakerspaceBackupStatus(makerspaceId) });
  if (!status.isSuccess) return null;
  const data = status.data;
  return <KeyValueCard title="Backup status" items={[
    { label: "Last backup", value: data.last_backed_up_at
      ? <RelativeTime date={data.last_backed_up_at} />
      : <StatusPill tone="warn" label="No backup yet" /> },
    { label: "Nightly backups", value: <StatusPill label={data.nightly_backups_enabled ? "On" : "Off"}
      tone={data.nightly_backups_enabled ? "success" : "warn"} /> },
  ]} />;
}

/** BK-17: the Space Manager's own backup status on the dashboard. */
export function DashboardArchiveStatus({ makerspaceId, slug, guestOnly, singleTenantLocked }: Props) {
  return <section aria-label="Backup status" className="grid gap-3">
    <BackupStatusCard makerspaceId={makerspaceId} />
    <a className="desk-button" href={consoleSessionHref(staffTabPath("backups", guestOnly, slug, singleTenantLocked))}>Backups</a>
  </section>;
}
