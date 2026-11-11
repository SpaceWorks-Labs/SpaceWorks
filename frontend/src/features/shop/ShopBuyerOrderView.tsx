import { formatDateTime } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { StatusPill } from "../../components/ui";
import { orderStatus, shopMoney, type ShopBuyerOrder } from "./shopApi";
import { ShopOrderHistory } from "./ShopOrderHistory";

const when = (value: string | null) => value ? formatDateTime(value) : "";

function pickupSentence(order: ShopBuyerOrder) {
  const place = order.pickup_at === "event" && order.pickup_event_title ? order.pickup_event_title : order.space_name;
  const held = order.expires_at && ["held", "awaiting_payment"].includes(order.status) ? when(order.expires_at) : "";
  if (place && held) return t`Pick up at ${place}. Held until ${held}.`;
  if (place) return t`Pick up at ${place}.`;
  return held ? t`Pick up at the space. Held until ${held}.` : t`Pick up at the space.`;
}

/** A buyer's view of one order: what to show at the desk, what was bought and what is still owed. */
export function ShopBuyerOrderView({ order, staff = false }: { order: ShopBuyerOrder; staff?: boolean }) {
  const status = orderStatus(order.status);
  const money = (value: string) => shopMoney(value, order.currency);
  const live = !["collected", "cancelled", "unfulfilled", "refunded"].includes(order.status);
  const interrupted = live && order.pickup_requires_staff_confirmation;
  return <div className="grid gap-5">
    <div className="flex flex-wrap items-center gap-3"><StatusPill label={status.label} tone={status.tone} />
      <span className="text-sm text-muted">{t`Order #${order.id} · ${when(order.created_at)}`}</span></div>
    {interrupted ? <div role="status" className="rounded-xl border border-line bg-surface p-4">
      <p>{staff ? t`Confirm an in-person pickup arrangement before handing over this order.`
        : t`Your event pickup is unavailable. Contact the makerspace to confirm where to collect this order.`}</p>
      {order.expires_at && ["held", "awaiting_payment"].includes(order.status)
        ? <p className="mt-1 text-sm text-muted">{t`Held until ${when(order.expires_at)}.`}</p> : null}
    </div> : null}
    {live && !interrupted && order.pickup_code ? <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-sm text-muted">{t`Show this code at the desk`}</p>
      <p className="code-text text-3xl font-semibold tracking-widest text-ink">{order.pickup_code}</p>
      <p className="mt-1 text-sm text-muted">{pickupSentence(order)}</p>
    </div> : null}
    <div className="overflow-x-auto"><table className="w-full text-sm">
      <caption className="sr-only">{t`Items in this order`}</caption>
      <thead><tr className="border-b border-line text-left text-muted">
        <th scope="col" className="py-2 font-semibold">{t`Item`}</th><th scope="col" className="py-2 text-right font-semibold">{t`Qty`}</th>
        <th scope="col" className="py-2 text-right font-semibold">{t`Amount`}</th></tr></thead>
      <tbody>{order.lines.map(line => <tr key={line.id} className="border-b border-line align-top">
        <td className="py-2 pr-3">{line.label}{Number(line.discount_amount) > 0 ? <span className="block text-muted">{t`Discount −${money(line.discount_amount)}`}</span> : null}</td>
        <td className="py-2 text-right tabular-nums">{line.quantity}</td>
        <td className="py-2 text-right tabular-nums">{money(line.line_total)}</td></tr>)}</tbody>
    </table></div>
    <dl className="grid gap-1 text-sm">
      {Number(order.discount_total) > 0 ? <div className="flex justify-between"><dt className="text-muted">{t`Discount`}</dt><dd className="tabular-nums">−{money(order.discount_total)}</dd></div> : null}
      {Number(order.tax_total) > 0 ? <div className="flex justify-between"><dt className="text-muted">{t`Tax included`}</dt><dd className="tabular-nums">{money(order.tax_total)}</dd></div> : null}
      <div className="flex justify-between text-base font-semibold text-ink"><dt>{t`Total`}</dt><dd className="tabular-nums">{money(order.total)}</dd></div>
      {order.status === "awaiting_payment" && Number(order.amount_due) > 0 ? <div className="flex justify-between font-semibold text-ink"><dt>{interrupted ? t`Amount due` : t`To pay at the desk`}</dt><dd className="tabular-nums">{money(order.amount_due)}</dd></div> : null}
    </dl>
    <ShopOrderHistory order={order} />
  </div>;
}
