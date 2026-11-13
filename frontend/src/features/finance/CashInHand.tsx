import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { HandCoins } from "lucide-react";

import { EmptyState, Field } from "../../components/ui";
import { formatMoney } from "../../lib/money";
import { CatalogChartPanel } from "../staff/panels/charts/CatalogChartPanel";
import { analyticsRows, useAnalyticsCatalog, useAnalyticsReport } from "../staff/panels/analyticsApi";
import { CashHandoverDialog, type Holder } from "./CashHandoverDialog";
import { localToday } from "./collectionSheetRows";
import { invalidateFinance } from "./financeApi";

const KEY = "cash-in-hand";
const money = (row: Record<string, unknown>, field: string) => formatMoney(String(row[field] ?? 0), String(row.currency ?? ""));

/**
 * Parity O-B3 `cash-in-hand` report: cash each collector recorded, less cash refunds they paid out and cash
 * they handed over. A hand-over (`billing.collection_sheet` + record payment) is recorded from the row.
 */
export function CashInHand({ makerspaceId, canHandover }: { makerspaceId: number; canHandover: boolean }) {
  const client = useQueryClient();
  const today = localToday();
  const [asOf, setAsOf] = useState(today);
  const [holder, setHolder] = useState<Holder | null>(null);
  const [message, setMessage] = useState("");
  const catalog = useAnalyticsCatalog(makerspaceId);
  const report = catalog.data?.results.find((entry) => entry.key === KEY);
  const available = Boolean(report && report.available !== false);
  const base = `/admin/makerspace/${makerspaceId}/analytics`;
  const query = useAnalyticsReport(base, KEY, new URLSearchParams(asOf ? { end: asOf } : {}), available);
  const rows = analyticsRows(query.data);
  return <section className="grid min-w-0 gap-4" aria-labelledby="cash-in-hand-heading">
    <header className="grid gap-1">
      <h3 id="cash-in-hand-heading" className="title-section">{t`Cash in hand`}</h3>
      <p className="max-w-prose text-sm text-muted">{t`Cash each person recorded, less cash refunds they paid out and cash they handed over. What is left should still be with them. Payments waiting for a second person are not counted until confirmed.`}</p>
    </header>
    <Field label={t`As of`} className="max-w-48"><input type="date" className="desk-input" max={today} value={asOf}
      onChange={(event) => setAsOf(event.target.value)} /></Field>
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {catalog.isLoading || query.isLoading ? <p role="status" className="text-sm text-muted">{t`Adding up the cash…`}</p> : null}
    {catalog.isSuccess && !available ? <p className="text-sm text-muted">{report?.unavailable_reason
      || t`This report needs the Reports area switched on and finance access in this space.`}</p> : null}
    {catalog.isError || query.isError ? <div role="alert" className="grid justify-items-start gap-2 text-sm text-danger">
      <p>{t`Couldn't load cash in hand.`}</p>
      <button type="button" className="desk-button" onClick={() => void (catalog.isError ? catalog.refetch() : query.refetch())}>{t`Retry`}</button>
    </div> : null}
    {query.isSuccess && !rows.length ? <EmptyState message={t`Nobody has recorded a cash payment in this space up to this date.`} /> : null}
    {rows.length ? <div role="region" aria-label={t`Cash in hand per collector`} tabIndex={0}
      className="overflow-x-auto rounded-xl border border-line bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <table className="w-full min-w-[40rem] text-sm">
        <caption className="sr-only">{t`Cash in hand per collector`}</caption>
        <thead><tr className="text-left text-xs text-muted">
          <th scope="col" className="p-2">{t`Collector`}</th>
          <th scope="col" className="p-2 text-right">{t`Cash received`}</th>
          <th scope="col" className="p-2 text-right">{t`Cash refunded`}</th>
          <th scope="col" className="p-2 text-right">{t`Handed over`}</th>
          <th scope="col" className="p-2 text-right">{t`In hand`}</th>
          {canHandover ? <th scope="col" className="p-2"><span className="sr-only">{t`Actions`}</span></th> : null}
        </tr></thead>
        <tbody>{rows.map((row) => {
          const inHand = Number(row.cash_in_hand ?? 0);
          return <tr key={`${row.collector_id}-${row.currency}`} className="border-t border-line">
            <th scope="row" className="p-2 text-left font-semibold">{String(row.collector || t`Former staff member`)}</th>
            <td className="p-2 text-right tabular-nums">{money(row, "received_cash")}</td>
            <td className="p-2 text-right tabular-nums">{money(row, "refunded_cash")}</td>
            <td className="p-2 text-right tabular-nums">{money(row, "handed_over")}</td>
            <td className={`p-2 text-right font-semibold tabular-nums ${inHand < 0 ? "text-danger" : ""}`}>{money(row, "cash_in_hand")}</td>
            {canHandover ? <td className="p-2 text-right"><button type="button" className="desk-button" disabled={!asOf || asOf !== today}
              title={asOf !== today ? t`Switch "As of" back to today to record a hand-over.` : undefined}
              onClick={() => { setMessage(""); setHolder({ collector_id: Number(row.collector_id), collector: String(row.collector || ""),
                currency: String(row.currency), cash_in_hand: String(row.cash_in_hand ?? "0") }); }}>
              <HandCoins aria-hidden="true" size={16} />{t`Record hand-over`}</button></td> : null}
          </tr>;
        })}</tbody>
      </table>
    </div> : null}
    {rows.length > 1 && report?.chart_spec ? <CatalogChartPanel title={report.title} spec={report.chart_spec} hint={report.chart_hint} rows={rows} /> : null}
    {holder ? <CashHandoverDialog makerspaceId={makerspaceId} holder={holder} onClose={() => setHolder(null)} onDone={() => {
      setMessage(t`Hand-over from ${holder.collector} recorded.`); setHolder(null);
      void client.invalidateQueries({ queryKey: ["operations-report"] }); invalidateFinance(client, makerspaceId);
    }} /> : null}
  </section>;
}
