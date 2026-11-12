import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { ErrorText, KeyValueCard } from "../../../components/ui";
import { openSpaceTab } from "../platformConsole/openSpaceTab";
import { crossSpaceKeys, getSnapshot, metricLabel } from "../platformConsole/crossSpaceApi";
import { usageAmount } from "../platformMonitoringApi";
import { limitLabel } from "./limitCopy";
import { LogoLoader } from "../../../components/LogoLoader";

/**
 * Decision 242(l) / U8: a read-only count snapshot of one space (no rows, no impersonation). Usage is
 * ALWAYS shown (decision 236): an Own space has no limits, so its numbers read "no limit" instead of
 * being hidden, and the superadmin can still see how big it is.
 */
export function SpaceSnapshotSection({ makerspaceId }: { makerspaceId: number }) {
  const snapshot = useQuery({ queryKey: crossSpaceKeys.snapshot(makerspaceId), queryFn: () => getSnapshot(makerspaceId) });
  if (snapshot.isLoading) return <LogoLoader label={t`Loading this space's snapshot`} size={48} className="min-h-24 py-3" />;
  if (snapshot.isError || !snapshot.data) return <ErrorText resource={t`this space's snapshot`} onRetry={() => { void snapshot.refetch(); }} />;
  const data = snapshot.data;
  const counts = Object.entries(data.counts).filter(([, value]) => value > 0);
  const resources = data.usage.resources ?? [];
  return <div className="grid gap-4">
    <KeyValueCard title={t`Waiting in this space`} items={[
      { label: t`Hosting`, value: data.hosted ? t`Hosted space (plan and limits apply)` : t`Own space (no plan, no limits)` },
      ...(counts.length ? counts.map(([key, value]) => ({ label: metricLabel(key), value: String(value) }))
        : [{ label: t`Queues`, value: t`Nothing waiting` }]),
    ]} />
    <KeyValueCard title={t`Usage`} items={resources.length ? resources.map(row => ({ label: limitLabel(row.key ?? row.label, row.label),
      value: `${usageAmount(row.used, row.unit ?? "count")}${row.limit !== null ? ` ${t`of`} ${usageAmount(row.limit, row.unit ?? "count")}` : ` · ${t`no limit`}`}` }))
      : [{ label: t`Usage`, value: t`No usage recorded yet` }]} />
    <button type="button" className="desk-button min-h-11 w-fit" onClick={() => openSpaceTab(data.id, "/admin/dashboard")}>{t`Open this space's dashboard`}</button>
  </div>;
}
