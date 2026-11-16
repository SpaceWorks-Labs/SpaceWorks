import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { Receipt } from "lucide-react";

import { RouteLink } from "../../components/ui/RouteLink";
import { shopMoney, type ShopBuyerOrder } from "./shopApi";

export type Placed = { order: ShopBuyerOrder; status_token: string; signedIn: boolean };

/** No online payment: the order is held and paid at the desk; the pickup code is what staff ask for. */
export function ShopOrderPlaced({ placed, path }: { placed: Placed; path: (part?: string) => string }) {
  const { order } = placed;
  const href = placed.signedIn ? path(`member/shop-orders/${order.id}`)
    : placed.status_token ? path(`shop/order/${encodeURIComponent(placed.status_token)}`) : "";
  const due = Number(order.amount_due) > 0;
  return <div role="status" className="grid gap-3">
    <p className="flex items-center gap-2 title-section"><Receipt aria-hidden="true" size={20} />{t`Order placed`}</p>
    <p>{due ? t`Pay ${shopMoney(order.amount_due, order.currency)} at the desk when you collect.` : t`Nothing to pay. Collect it at the desk.`}</p>
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-sm text-muted">{t`Your pickup code`}</p>
      <p className="code-text text-3xl font-semibold tracking-widest text-ink">{order.pickup_code}</p>
      {order.expires_at ? <p className="mt-1 text-sm text-muted">{t`Held until ${new Date(order.expires_at).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" })}.`}</p> : null}
    </div>
    <p className="text-sm text-muted">{placed.signedIn ? t`Your orders are listed in your member area.` : t`We emailed you this code and a link to follow your order.`}</p>
    {href ? <RouteLink href={href} className="desk-button min-h-11 justify-self-start">{t`Follow this order`}</RouteLink> : null}
  </div>;
}
