import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { DataTable, type DataTableColumn } from "../../components/ui";
import { Figure, SpaceCell } from "./OverviewBlockSection";
import { formatMoney, offText, type OverviewDrillSpace } from "./overviewFormat";
import type { OverviewCurrency, OverviewMoney } from "./platformOverviewApi";

type Figures = { charges: number; amounts: Record<string, string> };
type Row = { id: string; space?: OverviewDrillSpace; total?: boolean; figures: Figures };

function value(currency: string, key: string, figures: Figures) {
  return key === "charges" ? figures.charges.toLocaleString(formatLocale()) : formatMoney(currency, figures.amounts[key] ?? "0");
}

/** One currency's table. Totals only ever add rows of this same currency. */
function CurrencyTable({ money, entry, spaces }: { money: OverviewMoney; entry: OverviewCurrency; spaces: ReadonlyMap<number, OverviewDrillSpace> }) {
  const rows: Row[] = [
    ...entry.rows.map(row => ({ id: String(row.makerspace_id), space: spaces.get(row.makerspace_id), figures: row })),
    { id: "total", total: true, figures: entry.totals },
  ];
  const columns: DataTableColumn<Row>[] = [
    { key: "space", header: "Space", phone: "title", render: row => <SpaceCell space={row.space} tab="finance" /> },
    ...money.metrics.map(metric => ({ key: metric.key, header: metric.label, phone: "detail" as const, className: "tabular-nums",
      render: (row: Row) => row.total ? <strong>{value(entry.currency, metric.key, row.figures)}</strong> : value(entry.currency, metric.key, row.figures) })),
  ];
  const headingId = `overview-money-${entry.currency}`;
  return <section aria-labelledby={headingId} className="grid min-w-0 gap-3">
    <h3 id={headingId} className="title-panel">{entry.currency.toUpperCase()}</h3>
    <dl className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {money.metrics.map(metric => <Figure key={metric.key} label={metric.label} value={value(entry.currency, metric.key, entry.totals)} />)}
    </dl>
    <DataTable caption={t`Money in ${entry.currency.toUpperCase()} per space, with the ${entry.currency.toUpperCase()} total`} data={rows}
      getRowId={row => row.id} columns={columns} />
  </section>;
}

export function OverviewMoneySection({ money, spaces }: { money: OverviewMoney; spaces: ReadonlyMap<number, OverviewDrillSpace> }) {
  return <div className="grid min-w-0 gap-4">
    <p className="text-sm text-muted">{offText(money.off_in)}. Each currency is shown on its own and never added to another. Outstanding is what is still owed on the charges raised in this period.</p>
    {money.currencies.length ? money.currencies.map(entry => <CurrencyTable key={entry.currency} money={money} entry={entry} spaces={spaces} />)
      : <p className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">{t`No money was recorded in this period.`}</p>}
  </div>;
}
