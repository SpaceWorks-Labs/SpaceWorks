import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { DashboardLayout } from "../../components/layouts";
import type { Stat } from "../../components/ui";
import { eventErrorText } from "../staff/eventUi";
import { OverviewBlockSection } from "./OverviewBlockSection";
import { OverviewModulesSection } from "./OverviewModulesSection";
import { OverviewMoneySection } from "./OverviewMoneySection";
import { PlatformOverviewControls } from "./PlatformOverviewControls";
import { formatValue } from "./overviewFormat";
import {
  isComputing, overviewReady, readyOverview, refreshOverview, usePlatformOverview,
  type OverviewQuery, type PlatformOverview,
} from "./platformOverviewApi";

const HEADLINE: [block: string, metric: string, label: string][] = [
  ["people", "members", "Active members"], ["lending", "loans_out", "Loans out now"],
  ["events", "events_held", "Events held"], ["machines", "session_hours", "Machine hours"],
];

function headline(data: PlatformOverview): Stat[] {
  const stats: Stat[] = [{ label: t`Spaces counted`, value: data.spaces.length }];
  for (const [blockKey, metricKey, label] of HEADLINE) {
    const block = data.blocks.find(item => item.key === blockKey);
    const metric = block?.metrics.find(item => item.key === metricKey);
    if (block && metric) stats.push({ label, value: formatValue(metric.unit, block.totals[metricKey]) });
  }
  return stats;
}

function windowText(data: PlatformOverview) {
  const end = new Date(data.window.ends_at).toLocaleDateString(formatLocale());
  const start = data.window.starts_at ? new Date(data.window.starts_at).toLocaleDateString(formatLocale()) : "the beginning";
  return t`From ${start} to ${end} (UTC days). Computed ${new Date(data.computed_at).toLocaleString(formatLocale())}.`;
}

/**
 * Superadmin platform overview (#183A): every live space's totals combined, with the per-space
 * breakdown beside each total. Counts and money only; money stays per currency.
 */
export function PlatformOverviewPage() {
  const [query, setQuery] = useState<OverviewQuery>({ preset: "this_month", start: "", end: "", includeExcluded: false });
  const [refreshing, setRefreshing] = useState(false);
  const client = useQueryClient();
  const result = usePlatformOverview(query);
  const response = result.data;
  const data = readyOverview(response);
  const spaces = useMemo(() => {
    const reportsSpaceIds = new Set(data?.reports_space_ids);
    return new Map((data?.spaces ?? []).map(space => [space.id, { ...space, reportsEnabled: reportsSpaceIds.has(space.id) }]));
  }, [data]);
  const refresh = async () => {
    setRefreshing(true);
    try { await refreshOverview(query); } finally {
      setRefreshing(false);
      void client.invalidateQueries({ queryKey: ["platform-overview"] });
    }
  };
  const computing = isComputing(response) || result.isPlaceholderData;
  const main = data ? [
    ...data.blocks.map(block => ({ title: block.label, empty: { message: t`No spaces in this view.` }, isEmpty: !block.rows.length,
      content: <OverviewBlockSection block={block} spaces={spaces} /> })),
    ...(data.money ? [{ title: t`Money`, empty: { message: t`Money is off in every space.` },
      content: <OverviewMoneySection money={data.money} spaces={spaces} /> }] : []),
    { title: t`Modules`, empty: { message: t`No modules ship in this deployment.` }, isEmpty: !data.modules.length,
      content: <OverviewModulesSection data={data} spaces={spaces} /> },
  ] : [];
  return <DashboardLayout width="wide"
    header={{ eyebrow: t`Platform`, title: t`Platform overview`,
      subtitle: t`Every space's totals combined, with each space's own numbers beside them. Counts and money only; no member names.` }}
    state={{ status: result.isLoading ? "loading" : "ready" }}
    progress={<div className="grid gap-3">
      <PlatformOverviewControls query={query} onChange={setQuery} ready={Boolean(data) && !computing}
        excludedCount={data ? data.excluded_count : null} onRefresh={() => void refresh()} refreshing={refreshing} />
      {result.error && !data ? <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-ink">
        <span>{eventErrorText(result.error)}</span>
        <button type="button" className="desk-button min-h-11" onClick={() => { void result.refetch(); }}>{t`Try again`}</button>
      </div> : null}
      <p role="status" className="text-sm text-muted">
        {!overviewReady(query) ? t`Choose a start and an end date to see a custom period.`
          : computing ? t`Working out the totals. Large platforms can take a minute; this page updates by itself.`
            : data ? windowText(data) : ""}
      </p>
    </div>}
    stats={data ? headline(data) : []}
    main={main} />;
}
