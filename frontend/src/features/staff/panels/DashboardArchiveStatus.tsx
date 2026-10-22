import type { BackupCustody } from "../../../generated/api";
import { KeyValueCard, RelativeTime, StatusPill } from "../../../components/ui";
import { consoleSessionHref } from "../../../lib/api/sessionContext";
import { staffTabPath } from "../staffTabs";
import { useStaffGet } from "./shared";

type Props = { makerspaceId: number; slug: string; guestOnly: boolean; singleTenantLocked: boolean };

const CUSTODY_LABELS: Record<string, { label: string; tone: "success" | "warn" | "danger" | "neutral" }> = {
  healthy: { label: "Healthy", tone: "success" },
  not_applicable: { label: "Not needed", tone: "neutral" },
  degraded_one_recipient: { label: "One recipient left", tone: "warn" },
  floor_breached_zero: { label: "No recipients", tone: "danger" },
};

/** BK-17: the Space Manager's own archive status. A missing archive is a warning, never a silent zero. */
export function DashboardArchiveStatus({ makerspaceId, slug, guestOnly, singleTenantLocked }: Props) {
  const custody = useStaffGet<BackupCustody>(["backup-custody", makerspaceId], `/admin/makerspace/${makerspaceId}/backup-custody`);
  if (!custody.isSuccess) return null;
  const data = custody.data;
  const archive = data.archive_custody ? CUSTODY_LABELS[data.archive_custody.state] : undefined;
  return <section aria-label="Archive status" className="grid gap-3">
    <KeyValueCard title="Archive status" items={[
      { label: "Last backup", value: data.last_backed_up_at
        ? <RelativeTime date={data.last_backed_up_at} />
        : <StatusPill tone="warn" label="No backup yet" /> },
      { label: "Nightly backups", value: <StatusPill label={data.nightly_backups_enabled ? "On" : "Off"}
        tone={data.nightly_backups_enabled ? "success" : "warn"} /> },
      { label: "Held by", value: data.superadmin_access_enabled ? "Deployment backup" : "Your archive keys" },
      ...(data.superadmin_access_enabled ? [] : [{ label: "Verified recipients", value: data.verified_recipient_count > 0
        ? String(data.verified_recipient_count) : <StatusPill tone="danger" label="None" /> }]),
      ...(archive ? [{ label: "Key custody", value: <StatusPill tone={archive.tone} label={archive.label} /> }] : []),
    ]} />
    <a className="desk-button" href={consoleSessionHref(staffTabPath("backups", guestOnly, slug, singleTenantLocked))}>Backups</a>
  </section>;
}
