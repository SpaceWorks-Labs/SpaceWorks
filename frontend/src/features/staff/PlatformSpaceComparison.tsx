import { consoleSessionHref } from "../../lib/api/sessionContext";
import { DataTable, type DataTableColumn } from "../../components/ui";
import { DataState } from "./panels/OperationsReportState";
import { analyticsRows, type AnalyticsPeriod } from "./panels/analyticsApi";
import type { ChartRecord } from "./panels/charts/chartSpec";
import { usePlatformAnalytics, type AnalyticsMakerspace } from "./platformAnalyticsApi";

type Row = { id: string; name: string; slug?: string; values: Record<string, number> };
// Growth of the deployment itself is not a per-space comparison.
const SKIPPED = new Set(["makerspace_growth", "app_registrations"]);

/**
 * Pivot the platform-usage rows (owner decision #115 b3): one row per space, one column per
 * counted metric over the chosen period, and a Totals row. Money and measured quantities stay
 * in the usage chart, where they keep their currency and unit apart.
 */
export function compareSpaces(rows: ChartRecord[], spaces: AnalyticsMakerspace[] = []) {
  const metrics = new Set<string>();
  const bySpace = new Map<number, Row>();
  const totals: Row = { id: "totals", name: "Totals", values: {} };
  for (const row of rows) {
    const space = row.makerspace_id, metric = String(row.metric ?? ""), value = Number(row.value ?? 0);
    if (typeof space !== "number" || row.unit !== "count" || !metric || SKIPPED.has(metric) || !Number.isFinite(value)) continue;
    metrics.add(metric);
    const known = spaces.find(item => item.id === space);
    const entry = bySpace.get(space) ?? { id: String(space), name: known?.name ?? `Makerspace #${space}`, slug: known?.slug, values: {} };
    entry.values[metric] = (entry.values[metric] ?? 0) + value;
    totals.values[metric] = (totals.values[metric] ?? 0) + value;
    bySpace.set(space, entry);
  }
  const ordered = [...bySpace.values()].sort((a, b) => a.name.localeCompare(b.name));
  return { metrics: [...metrics].sort(), rows: ordered.length ? [...ordered, totals] : [] };
}

export function PlatformSpaceComparison({ period, spaces }: { period: AnalyticsPeriod; spaces?: AnalyticsMakerspace[] }) {
  const query = usePlatformAnalytics("platform-usage", period);
  const { metrics, rows } = compareSpaces(analyticsRows(query.data), spaces);
  const columns: DataTableColumn<Row>[] = [
    { key: "name", header: "Space", phone: "title", render: row => row.id === "totals" ? <strong>{row.name}</strong> : row.name },
    ...metrics.map(metric => ({ key: metric, header: metric.replace(/_/g, " "), phone: "detail" as const,
      render: (row: Row) => (row.values[metric] ?? 0).toLocaleString() })),
    { key: "actions", header: "Reports", render: row => row.slug
      ? <a className="desk-button" href={consoleSessionHref(`/admin/reports?space=${encodeURIComponent(row.slug)}`, "platform")}>Open reports</a> : null },
  ];
  return <section aria-label="Compare spaces" className="min-w-0 rounded-xl border border-line bg-panel p-4">
    <h3 className="title-section mb-3">Compare spaces</h3>
    <p className="mb-3 text-sm text-muted">Counted activity per space for the chosen period, with the total across every live space. Open a space's reports to see exactly what its Space Manager sees.</p>
    {query.isLoading ? <p role="status">Loading the comparison…</p> : <DataState loading={false} error={query.error} empty={!rows.length} onRetry={() => void query.refetch()}>
      <DataTable caption="Activity per space" data={rows} getRowId={row => row.id} columns={columns} />
    </DataState>}
  </section>;
}
