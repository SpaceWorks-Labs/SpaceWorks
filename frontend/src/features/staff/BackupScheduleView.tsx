import { useQuery } from "@tanstack/react-query";
import { ErrorText, RelativeTime } from "../../components/ui";
import { getBackupSchedule } from "./spaceRestoreApi";

/** One schedule view: the whole-platform nightly backup and every space's nightly backup. */
export function BackupScheduleView({ onPickSpace }: { onPickSpace: (makerspaceId: number) => void }) {
  const schedule = useQuery({ queryKey: ["backup-schedule"], queryFn: getBackupSchedule });
  if (schedule.isError) return <ErrorText resource="the backup schedule" onRetry={() => { void schedule.refetch(); }} />;
  const data = schedule.data;
  if (!data) return <p role="status" className="text-sm text-muted">Loading the schedule…</p>;
  return <div className="grid gap-3 text-sm">
    <p>Automatic backups are <strong>{data.automatic_backups_enabled ? "on" : "off"}</strong>. Whole platform: {data.platform_nightly}. Each space: {data.spaces_nightly}. Nightly backups keep {data.daily_keep_days} days plus {data.weekly_keep_weeks} weekly copies; “Back up now” keeps {data.on_demand_keep_days} days.</p>
    {!data.server_restore_key_configured ? <p className="text-danger">This server has no restore key, so one-space backups cannot be restored in the app.</p> : null}
    <div className="overflow-x-auto"><table className="w-full text-left">
      <thead><tr><th scope="col" className="py-2">Space</th><th scope="col">Last nightly</th><th scope="col">Last backup</th></tr></thead>
      <tbody>{(data.spaces ?? []).map(row => <tr key={row.makerspace_id} className="border-t border-line">
        <td className="py-2"><button className="underline" type="button" onClick={() => onPickSpace(row.makerspace_id)}>{row.name}</button></td>
        <td>{row.last_nightly_at ? <RelativeTime date={row.last_nightly_at} /> : "Never"}</td>
        <td>{row.last_backup_at ? <RelativeTime date={row.last_backup_at} /> : "Never"}</td></tr>)}</tbody>
    </table></div>
  </div>;
}
