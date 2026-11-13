import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { DashboardLayout } from "../../../components/layouts";
import { shopMoney } from "../../shop/shopApi";
import { staffShopError, staffShopKeys } from "./staffShopApi";
import { CHANNEL_LABELS, fetchReport, METHOD_LABELS } from "./staffShopOrdersApi";

const iso = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
const monthName = (month: string) => {
  const [year, number] = month.split("-").map(Number);
  return year && number ? new Date(year, number - 1, 1).toLocaleDateString(formatLocale(), { month: "short", year: "numeric" }) : month;
};

function Table({ caption, head, rows }: { caption: string; head: string[]; rows: ReactNode[][] }) {
  return <div className="overflow-x-auto rounded-xl border border-line bg-panel p-4"><table className="w-full text-sm">
    <caption className="sr-only">{caption}</caption>
    <thead><tr className="border-b border-line text-left text-muted">{head.map((cell, index) =>
      <th key={cell} scope="col" className={`py-2 ${index ? "text-right" : ""}`}>{cell}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index} className="border-b border-line last:border-0">{row.map((cell, at) =>
      <td key={at} className={`py-2 ${at ? "text-right tabular-nums" : ""}`}>{cell}</td>)}</tr>)}</tbody>
  </table></div>;
}

/** Shop takings for a date range: sales, refunds and tax, by channel, payment method and month, and the best sellers. */
export function ShopReports({ makerspaceId }: { makerspaceId: number }) {
  const today = new Date();
  const [from, setFrom] = useState(iso(new Date(today.getFullYear(), today.getMonth() - 2, 1)));
  const [to, setTo] = useState(iso(today));
  const valid = Boolean(from && to && from <= to);
  const query = useQuery({ queryKey: staffShopKeys.report(makerspaceId, from, to), queryFn: () => fetchReport(makerspaceId, from, to),
    enabled: valid, placeholderData: keepPreviousData });
  const report = query.data;
  const money = (value: string) => shopMoney(value, report?.currency ?? "inr");
  const empty = { message: t`Nothing in this period.` };
  // The date range stays usable whatever the query does, so a failed or empty range can always be changed.
  return <DashboardLayout header={{ eyebrow: t`Shop`, title: t`Shop reports`, subtitle: t`Online orders and desk sales in the chosen period.` }}
    state={valid && query.isPending ? { status: "loading" } : { status: "ready" }}
    callout={!valid ? { size: "inline", tone: "warn", lead: "Choose a start date on or before the end date." }
      : query.error ? { size: "inline", tone: "danger", lead: staffShopError(query.error), action: { label: t`Try again`, onClick: () => { void query.refetch(); } } } : undefined}
    progress={<div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-sm font-semibold">{t`From`}<input className="desk-input min-h-11 font-normal" type="date" value={from}
        onChange={event => setFrom(event.target.value)} /></label>
      <label className="grid gap-1 text-sm font-semibold">{t`To`}<input className="desk-input min-h-11 font-normal" type="date" value={to}
        onChange={event => setTo(event.target.value)} /></label>
      {query.isFetching && report ? <span role="status" className="min-h-11 py-3 text-sm text-muted">{t`Updating…`}</span> : null}
    </div>}
    stats={report ? [
      { label: t`Orders`, value: report.totals.orders }, { label: t`Sales`, value: money(report.totals.sales) },
      { label: t`Refunds`, value: money(report.totals.refunds), tone: Number(report.totals.refunds) > 0 ? "attention" : "neutral" },
      { label: t`Net`, value: money(report.totals.net) },
      ...(Number(report.totals.tax) > 0 ? [{ label: t`Tax included`, value: money(report.totals.tax) }] : []),
    ] : []}
    main={report ? [
      { title: t`By channel`, empty, isEmpty: !report.by_channel.length, content: <Table caption={t`By channel`} head={["Channel", "Orders", "Sales"]}
        rows={report.by_channel.map(row => [CHANNEL_LABELS()[row.channel] ?? row.channel, row.orders, money(row.sales)])} /> },
      { title: t`By payment method`, empty, isEmpty: !report.by_method.length, content: <Table caption={t`By payment method`} head={["Method", "Amount"]}
        rows={report.by_method.map(row => [METHOD_LABELS[row.method] ?? row.method, money(row.amount)])} /> },
      { title: t`By month`, empty, isEmpty: !report.by_month.length, content: <Table caption={t`By month`} head={["Month", "Sales", "Refunds"]}
        rows={report.by_month.map(row => [monthName(row.month), money(row.sales), money(row.refunds)])} /> },
      { title: t`Best sellers`, empty, isEmpty: !report.top_items.length, content: <Table caption={t`Best sellers`} head={["Item", "Quantity", "Sales"]}
        rows={report.top_items.map(row => [row.label, row.quantity, money(row.sales)])} /> },
    ] : []} />;
}
