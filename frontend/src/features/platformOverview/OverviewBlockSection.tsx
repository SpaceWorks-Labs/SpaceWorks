import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { Badge, DataTable, type DataTableColumn } from "../../components/ui";
import { DRILL_TAB, EXCLUDED_LABEL, drillHref, formatValue, isLiveSpace, offText } from "./overviewFormat";
import type { OverviewBlock, OverviewMetric, OverviewSpace } from "./platformOverviewApi";

type Row = { id: string; space?: OverviewSpace; total?: boolean; values: Record<string, number | null> | null };

/** A figure tile: the label, the number, and whether it is "now" or "in the period". */
export function Figure({ label, value, timing }: { label: string; value: ReactNode; timing?: string }) {
  return <div className="flex min-h-16 flex-col justify-between gap-1 rounded-xl border border-line bg-panel px-4 py-3">
    <dt className="text-sm text-muted">{label}{timing === "snapshot" ? <span className="text-xs"> {t` · now`}</span> : null}</dt>
    <dd className="text-lg font-semibold tabular-nums text-ink">{value}</dd>
  </div>;
}

export function SpaceCell({ space, tab }: { space?: OverviewSpace; tab: string }) {
  if (!space) return <strong>{t`All spaces`}</strong>;
  const href = drillHref(space, tab);
  return <span className="inline-flex flex-wrap items-center gap-2">
    {href ? <a className="font-semibold text-ink underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      href={href} aria-label={t`Open ${space.name} in the console`}>{space.name}</a> : <span>{space.name}</span>}
    {!isLiveSpace(space) && space.excluded_reason ? <Badge tone="warn">{EXCLUDED_LABEL[space.excluded_reason] ?? space.excluded_reason}</Badge> : null}
    {space.directory_hidden ? <Badge tone="neutral">{t`Not in directory`}</Badge> : null}
  </span>;
}

function cell(metric: OverviewMetric, row: Row) {
  if (row.values === null) return <span className="text-muted">{t`Off`}</span>;
  const value = formatValue(metric.unit, row.values[metric.key]);
  return row.total ? <strong>{value}</strong> : value;
}

export function OverviewBlockSection({ block, spaces }: { block: OverviewBlock; spaces: Map<number, OverviewSpace> }) {
  const tab = DRILL_TAB[block.key] ?? "dashboard";
  const rows: Row[] = [
    ...block.rows.map(row => ({ id: String(row.makerspace_id), space: spaces.get(row.makerspace_id), values: row.values })),
    { id: "total", total: true, values: block.totals },
  ];
  const columns: DataTableColumn<Row>[] = [
    { key: "space", header: "Space", phone: "title", render: row => <SpaceCell space={row.space} tab={tab} /> },
    ...block.metrics.map(metric => ({ key: metric.key, header: metric.label, phone: "detail" as const,
      className: "tabular-nums", render: (row: Row) => cell(metric, row) })),
  ];
  return <div className="grid min-w-0 gap-4">
    {block.switches.length ? <p className="text-sm text-muted">{t`${offText(block.off_in)} · switch: ${block.switches.join(", ")}`}</p> : null}
    <dl className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {block.metrics.map(metric => <Figure key={metric.key} label={metric.label} timing={metric.timing}
        value={formatValue(metric.unit, block.totals[metric.key])} />)}
    </dl>
    {block.platform_metrics.length ? <div className="grid gap-2">
      <h3 className="text-sm font-semibold text-ink">{t`Platform-wide, not split by space`}</h3>
      <dl className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {block.platform_metrics.map(metric => <Figure key={metric.key} label={metric.label} timing={metric.timing}
          value={formatValue(metric.unit, metric.value)} />)}
      </dl>
    </div> : null}
    <DataTable caption={t`${block.label} per space, with the total across all spaces`} data={rows}
      getRowId={row => row.id} columns={columns} emptyTitle={t`No spaces`} />
  </div>;
}
