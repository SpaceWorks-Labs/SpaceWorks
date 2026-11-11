import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Download, ShoppingBag } from "lucide-react";
import { StatusPill } from "../../../components/ui";
import { staffRequestBlob } from "../../../lib/api";
import { useMutation } from "@tanstack/react-query";
import { TestModeNotice } from "../paymentTestMode";
import { money, ORDER_STATUS } from "../../events/ticketing/ticketingApi";
import { EventPanelPager } from "../EventPanelPager";
import { panelEmpty, panelRow } from "../eventPanelStyles";
import { useEventOrders } from "./staffTicketingApi";
import { EventOrderDetail } from "./EventOrderDetail";

/** G27/G35 staff view: every order with its buyer, total and seats; unclaimed seats stay visible,
 * and a disputed payment is flagged (nothing is cancelled automatically). */
export function EventOrdersList({ eventId, makerspaceId, exportsOn = false }: { eventId: number; makerspaceId?: number; exportsOn?: boolean }) {
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number>();
  const orders = useEventOrders(eventId, page);
  const rows = orders.data?.results ?? [];
  // Parity C24: one CSV row per order, with test-mode money in its own `test_paid` column.
  const csv = useMutation({ mutationFn: async () => {
    const blob = await staffRequestBlob(`/admin/makerspace/${makerspaceId}/reports/event-orders/export?subject_kind=event&subject_id=${eventId}&format=csv`);
    const url = URL.createObjectURL(blob);
    Object.assign(document.createElement("a"), { href: url, download: `event-${eventId}-orders.csv` }).click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } });
  return <section className="grid gap-3" aria-label={t`Ticket orders`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="title-section flex items-center gap-2"><ShoppingBag aria-hidden="true" size={18} />{t`Orders`}</h3>
      {exportsOn && makerspaceId ? <button type="button" className="desk-button min-h-11" disabled={csv.isPending || !rows.length} onClick={() => csv.mutate()}>
        <Download aria-hidden="true" size={16} />{csv.isPending ? t`Preparing CSV…` : t`Download orders CSV`}</button> : null}
    </div>
    <TestModeNotice makerspaceId={makerspaceId} />
    {csv.error ? <p role="alert" className="text-sm text-danger">{t`The orders CSV could not be prepared. Try again.`}</p> : null}
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
          <button type="button" className="desk-button min-h-11" aria-label={t`View order #${order.id}`} onClick={() => setOpen(order.id)}>{t`View`}</button>
        </span>
      </li>;
    })}</ul>
    {open ? <EventOrderDetail orderId={open} onClose={() => setOpen(undefined)} /> : null}
    <EventPanelPager page={page} setPage={setPage} count={orders.data?.count} previous={orders.data?.previous} next={orders.data?.next} />
  </section>;
}
