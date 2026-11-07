import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ShoppingBag } from "lucide-react";
import { StatusPill } from "../../../components/ui";
import { money, ORDER_STATUS } from "../../events/ticketing/ticketingApi";
import { EventPanelPager } from "../EventPanelPager";
import { panelEmpty, panelRow } from "../eventPanelStyles";
import { useEventOrders } from "./staffTicketingApi";

/** G27/G35 staff view: every order with its buyer, total and seats; unclaimed seats stay visible,
 * and a disputed payment is flagged (nothing is cancelled automatically). */
export function EventOrdersList({ eventId }: { eventId: number }) {
  const [page, setPage] = useState(1);
  const orders = useEventOrders(eventId, page);
  const rows = orders.data?.results ?? [];
  return <section className="grid gap-3" aria-label={t`Ticket orders`}>
    <h3 className="title-section flex items-center gap-2"><ShoppingBag aria-hidden="true" size={18} />{t`Orders`}</h3>
    {orders.isLoading ? <p role="status" className="text-sm text-muted">{t`Loading orders…`}</p> : null}
    {orders.error ? <p role="alert" className="text-sm text-danger">{orders.error.message}</p> : null}
    {!orders.isLoading && !rows.length ? <p className={panelEmpty}>{t`No orders yet.`}</p> : null}
    <ul className="grid gap-3">{rows.map(order => {
      const unclaimed = order.seats.filter(seat => seat.status === "unclaimed");
      return <li key={order.id} className={panelRow}>
        <div className="grid min-w-0 gap-1">
          <span className="font-semibold text-ink">#{order.id} · {order.buyer_name}</span>
          <span className="text-sm text-muted">{money(order.total, order.currency)} · {order.seats.length} places
            {unclaimed.length ? t` · ${unclaimed.length} not claimed yet` : ""}</span>
          {unclaimed.length ? <span className="text-xs text-muted">{t`Waiting: ${unclaimed.map(seat => seat.attendee_email || "no email yet").join(", ")}`}</span> : null}
        </div>
        <span className="flex flex-wrap gap-2">
          {order.payment_disputed ? <StatusPill label={t`Payment disputed`} tone="danger" /> : null}
          <StatusPill label={ORDER_STATUS[order.status].label} tone={ORDER_STATUS[order.status].tone} />
        </span>
      </li>;
    })}</ul>
    <EventPanelPager page={page} setPage={setPage} previous={orders.data?.previous} next={orders.data?.next} />
  </section>;
}
