import { StatusPill } from "../../components/ui";
import { orderStatus, shopMoney, type ShopBuyerOrder } from "./shopApi";

const when = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";

/** A buyer's view of one order: what to show at the desk, what was bought and what is still owed. */
export function ShopBuyerOrderView({ order }: { order: ShopBuyerOrder }) {
  const status = orderStatus(order.status);
  const money = (value: string) => shopMoney(value, order.currency);
  const live = !["collected", "cancelled", "unfulfilled", "refunded"].includes(order.status);
  return <div className="grid gap-5">
    <div className="flex flex-wrap items-center gap-3"><StatusPill label={status.label} tone={status.tone} />
      <span className="text-sm text-muted">Order #{order.id} · {when(order.created_at)}</span></div>
    {live && order.pickup_code ? <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-sm text-muted">Show this code at the desk</p>
      <p className="font-mono text-3xl font-semibold tracking-widest text-ink">{order.pickup_code}</p>
      <p className="mt-1 text-sm text-muted">Pick up {order.pickup_at === "event" && order.pickup_event_title ? `at ${order.pickup_event_title}` : `at ${order.space_name || "the space"}`}.
        {order.expires_at && ["held", "awaiting_payment"].includes(order.status) ? ` Held until ${when(order.expires_at)}.` : ""}</p>
    </div> : null}
    <table className="w-full text-sm">
      <caption className="sr-only">Items in this order</caption>
      <thead><tr className="border-b border-line text-left text-muted">
        <th scope="col" className="py-2 font-semibold">Item</th><th scope="col" className="py-2 text-right font-semibold">Qty</th>
        <th scope="col" className="py-2 text-right font-semibold">Amount</th></tr></thead>
      <tbody>{order.lines.map(line => <tr key={line.id} className="border-b border-line align-top">
        <td className="py-2 pr-3">{line.label}{Number(line.discount_amount) > 0 ? <span className="block text-muted">Discount −{money(line.discount_amount)}</span> : null}</td>
        <td className="py-2 text-right tabular-nums">{line.quantity}</td>
        <td className="py-2 text-right tabular-nums">{money(line.line_total)}</td></tr>)}</tbody>
    </table>
    <dl className="grid gap-1 text-sm">
      {Number(order.discount_total) > 0 ? <div className="flex justify-between"><dt className="text-muted">Discount</dt><dd className="tabular-nums">−{money(order.discount_total)}</dd></div> : null}
      {Number(order.tax_total) > 0 ? <div className="flex justify-between"><dt className="text-muted">Tax included</dt><dd className="tabular-nums">{money(order.tax_total)}</dd></div> : null}
      <div className="flex justify-between text-base font-semibold text-ink"><dt>Total</dt><dd className="tabular-nums">{money(order.total)}</dd></div>
      {Number(order.amount_due) > 0 && live ? <div className="flex justify-between font-semibold text-ink"><dt>To pay at the desk</dt><dd className="tabular-nums">{money(order.amount_due)}</dd></div> : null}
    </dl>
  </div>;
}
