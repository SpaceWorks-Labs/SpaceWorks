import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { ChannelUsagePanel } from "./panels/ChannelUsagePanel";
import { analyticsRows, type AnalyticsPeriod } from "./panels/analyticsApi";
import { forSpace } from "./panels/channelUsage";
import { usePlatformAnalytics } from "./platformAnalyticsApi";
import type { PlatformDashboard } from "./platformMonitoringApi";

/** Superadmin "Web and app use": web versus iOS, Android and API-client activity, by space and by feature, with a per-space drill-down. */
export function PlatformChannelUsage({ period, spaces = [] }: { period: AnalyticsPeriod; spaces?: PlatformDashboard["tenants"] }) {
  const query = usePlatformAnalytics("platform-channel-usage", period);
  const [drill, setDrill] = useState("");
  const spaceName = (id: number | null) => id == null ? t`Deployment (unattributed)` : spaces.find(space => space.id === id)?.name ?? t`Space #${id}`;
  const all = useMemo(() => analyticsRows(query.data), [query.data]);
  const present = useMemo(() => [...new Set(all.flatMap(row => typeof row.makerspace_id === "number" ? [row.makerspace_id] : []))], [all]);
  const rows = drill ? forSpace(all, Number(drill)) : all;
  return <section aria-label={t`Web and app use`} className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section mb-3">{t`Web and app use`}</h3>
    <p className="mb-3 text-sm text-muted">{t`How people reach the platform: the web console, the iOS and Android apps and API clients, and which features each one uses. Counts only, never people.`}</p>
    {present.length ? <label className="mb-3 flex flex-wrap items-center gap-2 text-sm">{t`Drill into a space`}
      <select className="desk-input" value={drill} onChange={event => setDrill(event.target.value)}>
        <option value="">{t`Every space`}</option>
        {present.map(id => <option key={id} value={id}>{spaceName(id)}</option>)}
      </select></label> : null}
    <ChannelUsagePanel rows={rows} meta={query.data?.meta as { definition?: string; limitations?: string } | undefined}
      loading={query.isLoading} error={query.error} onRetry={() => void query.refetch()} spaceName={drill ? undefined : spaceName} />
  </section>;
}
