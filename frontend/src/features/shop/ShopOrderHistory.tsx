import { t } from "@lingui/core/macro";

import { formatLocale } from "../../lib/format";
import { orderStatus, shopMoney, type ShopBuyerOrder } from "./shopApi";

const when = (value: string) => new Date(value).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });

/** Fulfilment facts belong to the order; actual refunds belong to the payment ledger. */
export function ShopOrderHistory({ order }: { order: ShopBuyerOrder }) {
  const stages = [
    { label: t`Order placed`, at: order.created_at },
    { label: Number(order.amount_due) > 0 ? t`Payment received` : t`No payment due`, at: order.paid_at },
    { label: t`Ready to collect`, at: order.ready_at },
    { label: t`Collected`, at: order.collected_at },
    ...(["cancelled", "unfulfilled"].includes(order.status)
      ? [{ label: orderStatus(order.status).label, at: order.closed_at }] : []),
  ].filter((stage): stage is { label: string; at: string } => Boolean(stage.at));
  const returns = order.returns ?? [];
  return <section className="grid gap-3" aria-label={t`Order history`}>
    <h2 className="title-panel">{t`Order history`}</h2>
    <ol className="grid gap-2">{stages.map(stage => <li key={stage.label} className="flex flex-wrap justify-between gap-x-4 gap-y-1 text-sm">
      <span>{stage.label}</span><time className="text-muted" dateTime={stage.at}>{when(stage.at)}</time>
    </li>)}</ol>
    {returns.length ? <div className="grid gap-2">
      <h3 className="font-semibold text-ink">{t`Items returned`}</h3>
      <p className="text-sm text-muted">{t`These goods were taken back. Return values do not confirm a refund; staff review refunds separately.`}</p>
      <ul className="grid gap-2">{returns.map((row, index) => {
        const label = order.lines.find(line => line.id === row.line_id)?.label ?? t`Item`;
        return <li key={`${row.line_id}-${row.created_at}-${index}`} className="grid gap-1 text-sm">
          <span>{t`${label} · ${row.quantity} returned · ${shopMoney(row.amount, order.currency)}`}</span>
          <time className="text-muted" dateTime={row.created_at}>{when(row.created_at)}</time>
        </li>;
      })}</ul>
    </div> : null}
  </section>;
}
