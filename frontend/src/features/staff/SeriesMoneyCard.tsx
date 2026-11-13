import { plural, t } from "@lingui/core/macro";
import { formatMoney } from "../../lib/money";

/** Parity C24: what a recurring series earned and spent over every occurrence, one block per currency. */
export type SeriesMoney = {
  occurrences: number;
  currencies: { currency: string; income: string; refunds: string; other_income: string; expenses: string; payouts: string; net: string }[];
};

const ROWS = () => [
  ["income", t`Ticket income`], ["refunds", t`Refunded`], ["other_income", t`Other income`],
  ["expenses", t`Spending`], ["payouts", t`Payouts`],
] as const;

/** The server sends `null` when the viewer may not see event money or the space tracks none; nothing renders then. */
export function SeriesMoneyCard({ money }: { money: SeriesMoney | null | undefined }) {
  if (!money) return null;
  return <section aria-labelledby="series-money" className="grid gap-3 rounded-xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 id="series-money" className="title-panel">{t`Money across the series`}</h2>
      <span className="text-sm text-muted">{plural(money.occurrences, { one: "# occurrence", other: "# occurrences" })}</span>
    </div>
    {!money.currencies.length ? <p className="text-sm text-muted">{t`No money recorded for this series yet.`}</p> : null}
    {money.currencies.map(row => <dl key={row.currency} aria-label={t`Totals in ${row.currency.toUpperCase()}`} className="grid gap-1 text-sm">
      {ROWS().map(([key, label]) => <div key={key} className="flex items-baseline justify-between gap-3 border-b border-line py-1.5">
        <dt className="text-muted">{label}</dt><dd className="tabular-nums text-ink">{formatMoney(row[key], row.currency)}</dd></div>)}
      <div className="flex items-baseline justify-between gap-3 pt-1.5">
        <dt className="font-semibold text-ink">{t`Net`}</dt>
        <dd className={`tabular-nums font-semibold ${Number(row.net) < 0 ? "text-danger" : "text-ink"}`}>{formatMoney(row.net, row.currency)}</dd></div>
    </dl>)}
    <p className="text-xs text-muted">{t`Each currency is totalled on its own. Budgets are set per event, so they are not shown here.`}</p>
  </section>;
}
