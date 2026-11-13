import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { ChannelUsagePanel } from "./panels/ChannelUsagePanel";
import { analyticsMeta, analyticsRows, periodParams, useAnalyticsReport, type AnalyticsPeriod } from "./panels/analyticsApi";
import { usePlatformAnalytics } from "./platformAnalyticsApi";
import type { PlatformDashboard } from "./platformMonitoringApi";

/** Superadmin "Web and app use": web versus iOS, Android and API-client activity, by space and by feature, with a per-space drill-down. */
export function PlatformChannelUsage({ period, spaces = [] }: { period: AnalyticsPeriod; spaces?: PlatformDashboard["tenants"] }) {
  const query = usePlatformAnalytics("platform-channel-usage", period);
  const [drill, setDrill] = useState("");
  const spaceName = (id: number | null) => id == null ? t`Deployment (unattributed)` : spaces.find(space => space.id === id)?.name ?? t`Space #${id}`;
  const all = useMemo(() => analyticsRows(query.data), [query.data]);
  const present = useMemo(() => {
    if (query.error) return [];
    const ids = query.data?.meta?.space_ids;
    return Array.isArray(ids) ? ids.filter((id): id is number => typeof id === "number")
      : [...new Set(all.flatMap(row => typeof row.makerspace_id === "number" ? [row.makerspace_id] : []))];
  }, [all, query.data, query.error]);
  // Platform totals deduplicate a shared session into one tenant. A real tenant read
  // is needed for drill-down; filtering those totals silently omitted shared sessions.
  const selected = present.includes(Number(drill)) ? drill : "";
  const tenant = useAnalyticsReport(`/admin/platform/analytics/makerspaces/${selected}/analytics`, "channel-usage", periodParams(period), Boolean(selected));
  const source = selected ? tenant : query;
  const rows = selected ? analyticsRows(tenant.data) : all;
  return <section aria-label={t`Web and app use`} className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section mb-3">{t`Web and app use`}</h3>
    <p className="mb-3 text-sm text-muted">{t`How people reach the platform: the web console, the iOS and Android apps and API clients, and which features each one uses. Counts only, never people.`}</p>
    {present.length ? <label className="mb-3 flex flex-wrap items-center gap-2 text-sm">{t`Drill into a space`}
      <select className="desk-input" value={selected} onChange={event => setDrill(event.target.value)}>
        <option value="">{t`Every space`}</option>
        {present.map(id => <option key={id} value={id}>{spaceName(id)}</option>)}
      </select></label> : null}
    <ChannelUsagePanel rows={rows} meta={analyticsMeta(source.data) as { definition?: string; limitations?: string } | undefined}
      loading={source.isLoading} error={source.error} onRetry={() => void source.refetch()} spaceName={selected ? undefined : spaceName} />
  </section>;
}
