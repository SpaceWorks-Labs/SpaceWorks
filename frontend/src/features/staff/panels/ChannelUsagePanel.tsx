import { t } from "@lingui/core/macro";
import { useMemo } from "react";
import { formatLocale } from "../../../lib/format";
import { DataTable, type DataTableColumn } from "../../../components/ui";
import { BoxSpinner } from "../../../components/BoxSpinner";
import { CatalogChartPanel } from "./charts/CatalogChartPanel";
import type { ChartRecord } from "./charts/chartSpec";
import { DataState } from "./OperationsReportState";
import { reportFieldLabel } from "./reportFieldLabels";
import {
  CHANNEL_ORDER, SESSION_DAYS, TREND_SPEC, accountTotals, appVersions, channelCsv, channelTotals, flowShares, perSpace,
  topAreas, trendRows, type SpaceChannelRow,
} from "./channelUsage";
import { AccountsSection, FlowsSection, VersionsSection } from "./ChannelUsageSections";

const count = (value: number) => value.toLocaleString(formatLocale());

/**
 * "Web and app use": who reaches the system from the browser, the iOS and Android apps and signed API clients,
 * and which areas (features) each channel uses. Counts only. The same panel serves the superadmin platform
 * view and a space's reports, fed by the same report rows.
 */
export function ChannelUsagePanel({ rows, meta, loading = false, error, onRetry, spaceName }: {
  rows: readonly ChartRecord[]; meta?: { definition?: string; limitations?: string };
  loading?: boolean; error?: unknown; onRetry?: () => void; spaceName?: (id: number | null) => string;
}) {
  const totals = useMemo(() => channelTotals(rows, SESSION_DAYS), [rows]);
  const trend = useMemo(() => trendRows(rows), [rows]);
  const areas = useMemo(() => topAreas(rows), [rows]);
  const accounts = useMemo(() => accountTotals(rows), [rows]);
  const flows = useMemo(() => flowShares(rows), [rows]);
  const versions = useMemo(() => appVersions(rows), [rows]);
  const download = () => {
    const url = URL.createObjectURL(new Blob([channelCsv(rows)], { type: "text/csv" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: "web-and-app-use.csv" });
    link.click();
    URL.revokeObjectURL(url);
  };
  const spaces = useMemo(() => spaceName ? perSpace(rows, spaceName) : [], [rows, spaceName]);
  const spaceColumns: DataTableColumn<SpaceChannelRow>[] = [
    { key: "name", header: t`Space`, phone: "title", render: row => row.name },
    ...CHANNEL_ORDER.filter(channel => channel !== "api_client").map(channel => ({
      key: channel, header: reportFieldLabel(channel), phone: "detail" as const,
      render: (row: SpaceChannelRow) => count(row.values[channel] ?? 0),
    })),
    { key: "total", header: t`Total`, render: row => <strong>{count(row.total)}</strong> },
  ];
  if (loading) return <div className="flex min-h-16 items-center justify-center py-3"><BoxSpinner label={t`Loading web and app use…`} size={32} /></div>;
  return <DataState loading={false} error={error} empty={!rows.length} onRetry={onRetry}>
    <div className="grid min-w-0 gap-5">
      {meta?.definition ? <p className="text-sm text-muted">{meta.definition}</p> : null}
      <section aria-label={t`Share of active sessions by channel`}>
        <h4 className="title-section mb-2">{t`Where people connect from`}</h4>
        {totals.length ? <ul className="grid gap-3 sm:grid-cols-3">{totals.map(item => <li key={item.channel} className="rounded-lg border border-line p-3">
          <p className="text-sm text-muted">{reportFieldLabel(item.channel)}</p>
          <p className="text-2xl font-semibold">{item.share}%</p>
          <p className="text-xs text-muted">{t`${count(item.total)} active session-days`}</p>
        </li>)}</ul> : <p className="text-sm text-muted">{t`No sessions recorded in this period.`}</p>}
      </section>
      <AccountsSection items={accounts} />
      <section aria-label={t`Active sessions over time`}>
        <h4 className="title-section mb-2">{t`Active sessions over time`}</h4>
        <CatalogChartPanel title={t`Active sessions by channel`} spec={TREND_SPEC} hint="multi_line" rows={trend} />
      </section>
      {spaces.length ? <section aria-label={t`Channel use per space`}>
        <h4 className="title-section mb-2">{t`By space`}</h4>
        <DataTable caption={t`Active session-days per space and channel`} data={spaces} getRowId={row => row.id} columns={spaceColumns} />
      </section> : null}
      <section aria-label={t`Top features by channel`}>
        <h4 className="title-section mb-2">{t`Top features by channel`}</h4>
        {areas.length ? <div className="grid gap-3 sm:grid-cols-2">{areas.map(group => <div key={group.channel} className="rounded-lg border border-line p-3">
          <p className="mb-1 font-medium">{reportFieldLabel(group.channel)}</p>
          <ol className="space-y-1 text-sm">{group.areas.map(item => <li key={item.area} className="flex justify-between gap-3">
            <span>{reportFieldLabel(item.area)}</span><span className="tabular-nums text-muted">{count(item.value)}</span>
          </li>)}</ol>
        </div>)}</div> : <p className="text-sm text-muted">{t`No calls recorded in this period.`}</p>}
      </section>
      <FlowsSection items={flows} />
      <VersionsSection items={versions} />
      <div><button type="button" className="desk-button" onClick={download}>{t`Download CSV`}</button></div>
      {meta?.limitations ? <p className="text-xs text-muted">{meta.limitations}</p> : null}
    </div>
  </DataState>;
}
