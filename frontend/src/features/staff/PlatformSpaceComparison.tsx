import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { consoleSessionHref } from "../../lib/api/sessionContext";
import { DataTable, type DataTableColumn } from "../../components/ui";
import { DataState } from "./panels/OperationsReportState";
import { analyticsRows, type AnalyticsPeriod } from "./panels/analyticsApi";
import type { ChartRecord } from "./panels/charts/chartSpec";
import { reportFieldLabel } from "./panels/reportFieldLabels";
import { usePlatformAnalytics } from "./platformAnalyticsApi";
import type { PlatformDashboard } from "./platformMonitoringApi";
import { LogoLoader } from "../../components/LogoLoader";

type ComparisonSpace = Pick<PlatformDashboard["tenants"][number], "id" | "name" | "slug" | "reports_enabled">;
type Row = { id: string; name: string; reportsSlug?: string; values: Record<string, number> };
// Growth of the deployment itself is not a per-space comparison.
const SKIPPED = new Set(["makerspace_growth", "app_registrations"]);

/**
 * Pivot the platform-usage rows (owner decision #115 b3): one row per space, one column per
 * counted metric over the chosen period, and a Totals row. Money and measured quantities stay
 * in the usage chart, where they keep their currency and unit apart.
 */
export function compareSpaces(rows: ChartRecord[], spaces: ComparisonSpace[] = []) {
  const metrics = new Set<string>();
  const bySpace = new Map<number, Row>();
  const totals: Row = { id: "totals", name: t`Totals`, values: {} };
  for (const row of rows) {
    const space = row.makerspace_id, metric = String(row.metric ?? ""), value = Number(row.value ?? 0);
    if (typeof space !== "number" || row.unit !== "count" || !metric || SKIPPED.has(metric) || !Number.isFinite(value)) continue;
    metrics.add(metric);
    const known = spaces.find(item => item.id === space);
    const entry = bySpace.get(space) ?? { id: String(space), name: known?.name ?? t`Space #${space}`,
      reportsSlug: known?.reports_enabled ? known.slug : undefined, values: {} };
    entry.values[metric] = (entry.values[metric] ?? 0) + value;
    totals.values[metric] = (totals.values[metric] ?? 0) + value;
    bySpace.set(space, entry);
  }
  const ordered = [...bySpace.values()].sort((a, b) => a.name.localeCompare(b.name));
  return { metrics: [...metrics].sort(), rows: ordered.length ? [...ordered, totals] : [] };
}

export function PlatformSpaceComparison({ period, spaces }: { period: AnalyticsPeriod; spaces?: ComparisonSpace[] }) {
  const query = usePlatformAnalytics("platform-usage", period);
  const { metrics, rows } = compareSpaces(analyticsRows(query.data), spaces);
  const showReports = rows.some(row => row.reportsSlug);
  const columns: DataTableColumn<Row>[] = [
    { key: "name", header: t`Space`, phone: "title", render: row => row.id === "totals" ? <strong>{row.name}</strong> : row.name },
    ...metrics.map(metric => ({ key: metric, header: reportFieldLabel(metric), phone: "detail" as const,
      render: (row: Row) => (row.values[metric] ?? 0).toLocaleString(formatLocale()) })),
  ];
  if (showReports) columns.push({ key: "actions", header: t`Reports`, render: row => row.reportsSlug
    ? <a className="desk-button" href={consoleSessionHref(`/admin/reports?space=${encodeURIComponent(row.reportsSlug)}`, "platform")}>{t`Open reports`}</a> : null });
  return <section aria-label={t`Compare spaces`} className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section mb-3">{t`Compare spaces`}</h3>
    <p className="mb-3 text-sm text-muted">{showReports
      ? t`Counted activity per space for the chosen period, with the total across every live space. Open a space's reports to see exactly what its Space Manager sees.`
      : t`Counted activity per space for the chosen period, with the total across every live space.`}</p>
    {query.isLoading ? <LogoLoader label={t`Loading the comparison…`} size={48} className="min-h-16 py-3" /> : <DataState loading={false} error={query.error} empty={!rows.length} onRetry={() => void query.refetch()}>
      <DataTable caption={t`Activity per space`} data={rows} getRowId={row => row.id} columns={columns} />
    </DataState>}
  </section>;
}
