import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Landmark } from "lucide-react";

import { Field } from "../../components/ui";
import { formatMoney } from "../staff/paymentsApi";
import { DOMAIN_LABELS, financeApi, financeError, financeKeys, type SummaryRow } from "./financeApi";

const MONEY = ["income", "other_income", "refunds", "expenses", "payouts"] as const;
type Totals = Record<(typeof MONEY)[number] | "net", number>;

function isoDay(date: Date) {
  return date.toISOString().slice(0, 10);
}

function totals(rows: SummaryRow[]) {
  const byKey = new Map<string, Totals>();
  for (const row of rows) {
    const current = byKey.get(row.currency) ?? { income: 0, other_income: 0, refunds: 0, expenses: 0, payouts: 0, net: 0 };
    for (const name of MONEY) current[name] += Number(row[name]);
    current.net += Number(row.net);
    byKey.set(row.currency, current);
  }
  return [...byKey.entries()];
}

/** Income versus spending, month by month and per area, for the areas the caller sees. */
export function FinanceOverview({ makerspaceId }: { makerspaceId: number }) {
  const today = new Date();
  const [from, setFrom] = useState(isoDay(new Date(today.getFullYear(), today.getMonth() - 11, 1)));
  const [to, setTo] = useState(isoDay(today));
  const summary = useQuery({ queryKey: financeKeys.summary(makerspaceId, from, to),
    queryFn: () => financeApi.summary(makerspaceId, from, to) });
  const rows = useMemo(() => summary.data?.rows ?? [], [summary.data]);
  return <div className="grid min-w-0 gap-4">
    <div className="flex flex-wrap items-end gap-3">
      <Field label={t`From`}><input type="date" className="desk-input" value={from} max={to} onChange={event => setFrom(event.target.value)} /></Field>
      <Field label={t`To`}><input type="date" className="desk-input" value={to} min={from} onChange={event => setTo(event.target.value)} /></Field>
    </div>
    {summary.isLoading ? <p role="status" className="text-sm text-muted">{t`Adding up the money…`}</p> : null}
    {summary.error ? <p role="alert" className="text-sm text-danger">{financeError(summary.error)}</p> : null}
    <div className="grid gap-3 sm:grid-cols-2">
      {totals(rows).map(([currency, value]) => <article key={currency} className="grid gap-1 rounded-xl border border-line bg-panel p-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><Landmark aria-hidden="true" size={16} />{t`${currency.toUpperCase()} in this range`}</h3>
        <p className="text-sm">{t`In: `}<strong>{formatMoney(String(value.income + value.other_income), currency)}</strong></p>
        <p className="text-sm">{t`Out: `}<strong>{formatMoney(String(value.refunds + value.expenses + value.payouts), currency)}</strong></p>
        <p className="text-sm">{t`Net: `}<strong className={value.net < 0 ? "text-danger" : ""}>{formatMoney(String(value.net), currency)}</strong></p>
      </article>)}
    </div>
    {summary.data && !rows.length ? <p className="text-sm text-muted">{t`No money moved in this range for the areas you see.`}</p> : null}
    {rows.length ? <div role="region" aria-label={t`Income and spending by month and area`} tabIndex={0}
      className="overflow-x-auto rounded-xl border border-line focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <table className="w-full min-w-[44rem] text-sm">
        <caption className="sr-only">{t`Income and spending by month and area`}</caption>
        <thead><tr className="text-left text-muted">
          <th scope="col" className="p-2">{t`Month`}</th><th scope="col" className="p-2">{t`Area`}</th>
          <th scope="col" className="p-2 text-right">{t`Charges collected`}</th><th scope="col" className="p-2 text-right">{t`Other income`}</th>
          <th scope="col" className="p-2 text-right">{t`Refunds`}</th><th scope="col" className="p-2 text-right">{t`Expenses`}</th>
          <th scope="col" className="p-2 text-right">{t`Payouts`}</th><th scope="col" className="p-2 text-right">{t`Net`}</th>
        </tr></thead>
        <tbody>{rows.map(row => <tr key={`${row.month}-${row.domain}-${row.machine_type}-${row.currency}`} className="border-t border-line">
          <td className="p-2">{row.month}</td>
          <td className="p-2">{DOMAIN_LABELS[row.domain] ?? row.domain}{row.machine_type ? ` · ${row.machine_type}` : ""}</td>
          {MONEY.map(name => <td key={name} className="p-2 text-right tabular-nums">{formatMoney(row[name], row.currency)}</td>)}
          <td className="p-2 text-right font-semibold tabular-nums">{formatMoney(row.net, row.currency)}</td>
        </tr>)}</tbody>
      </table>
    </div> : null}
  </div>;
}
