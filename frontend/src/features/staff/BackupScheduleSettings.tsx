import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ErrorText, RelativeTime, SettingsActions, SettingsRow } from "../../components/ui";
import type { BackupSettings } from "./backupApi";
import { DeploymentNotices } from "../deployment/DeploymentNotices";
import type { DeploymentNoticeData } from "../deployment/types";

export function BackupScheduleSettings({ data, pending, onSave, deployment }: { data: BackupSettings; pending: boolean; onSave: (payload: Partial<BackupSettings>, onSaved?: () => void) => void; deployment?: DeploymentNoticeData }) {
  const [draft, setDraft] = useState<number | null>(null);
  const days = draft ?? data.retention_days;
  const dirty = days !== data.retention_days;
  if (deployment?.mode === "managed" || deployment?.profile === "free") return <DeploymentNotices data={deployment} />;
  return <>
    <SettingsRow label={t`Daily full backup`} helper={`Create a full deployment archive each day. Each is kept ${data.daily_keep_days} days, and the first of each week is kept ${data.weekly_keep_weeks} weeks.`}>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input className="h-5 w-5 accent-accent" role="switch" aria-label={t`Create a full deployment archive each day`} type="checkbox" checked={data.automatic_backups_enabled} disabled={pending} onChange={event => onSave({ automatic_backups_enabled: event.target.checked })} />{data.automatic_backups_enabled ? t`On` : t`Off`}</label>
      <p className="mt-2 text-sm text-muted">{t`Last successful archive: `}{data.last_success_at ? <RelativeTime date={data.last_success_at} /> : t`Never`}</p>
    </SettingsRow>
    <SettingsRow label={t`Keep on-demand archives for`} helper="Archives you request by hand. Choose between 1 and 3,650 days."><label className="grid gap-2 text-sm">{t`On-demand archive retention (days)`}<input className="desk-input" type="number" min={1} max={3650} disabled={pending} value={days} onChange={event => setDraft(Number(event.target.value))} /></label></SettingsRow>
    {data.last_error ? <ErrorText message={data.last_error} /> : null}
    {dirty ? <SettingsActions onDiscard={() => setDraft(null)} onSave={() => onSave({ retention_days: days }, () => setDraft(null))} pending={pending} disabled={!Number.isInteger(days) || days < 1 || days > 3650} /> : null}
  </>;
}
