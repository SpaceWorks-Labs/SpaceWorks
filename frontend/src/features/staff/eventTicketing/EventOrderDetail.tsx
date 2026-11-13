import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { ErrorText, KeyValueCard, Modal, RelativeTime, StatusPill } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { money, ORDER_STATUS } from "../../events/ticketing/ticketingApi";
import type { StaffOrder } from "./staffTicketingApi";
import { LogoLoader } from "../../../components/LogoLoader";

const SEAT_LABEL: Record<string, string> = { unclaimed: t`Not claimed yet`, claimed: t`Claimed`, void: t`Void` };

/** One order as the organiser sees it (`GET admin/event-orders/{id}/`, the event's manage_registrations grant). */
export function EventOrderDetail({ orderId, onClose }: { orderId: number; onClose: () => void }) {
  const order = useQuery({ queryKey: ["staff-event-order", orderId], retry: false,
    queryFn: () => staffRequest<StaffOrder>(`/admin/event-orders/${orderId}/`) });
  const row = order.data;
  return <Modal open onClose={onClose} title={t`Order #${orderId}`} size="xl">
    {order.isLoading ? <LogoLoader label={t`Loading order…`} size={48} className="min-h-16 py-3" /> : null}
    {order.error ? <ErrorText message={order.error.message} onRetry={() => void order.refetch()} /> : null}
    {row ? <div className="grid gap-4">
      <div className="flex flex-wrap gap-2">
        <StatusPill label={ORDER_STATUS[row.status].label} tone={ORDER_STATUS[row.status].tone} />
        {row.payment_disputed ? <StatusPill label={t`Payment disputed`} tone="danger" /> : null}
      </div>
      <KeyValueCard title={t`Order`} items={[
        { label: t`Buyer`, value: row.buyer_name },
        { label: t`Event`, value: row.event_title },
        { label: t`Placed`, value: <RelativeTime date={row.created_at} /> },
        { label: t`Paid`, value: row.paid_at ? <RelativeTime date={row.paid_at} /> : t`Not paid` },
        { label: t`Subtotal`, value: money(row.subtotal, row.currency) },
        ...(Number(row.discount_total) ? [{ label: t`Discount`, value: money(row.discount_total, row.currency) }] : []),
        ...(Number(row.fee_total) ? [{ label: t`Fees`, value: money(row.fee_total, row.currency) }] : []),
        { label: t`Total`, value: money(row.total, row.currency) },
      ]} />
      <section className="grid gap-2" aria-label={t`Order lines`}>
        <h3 className="title-section">{t`Lines`}</h3>
        <ul className="grid gap-1 text-sm">{row.lines.map(line => <li key={line.id} className="flex justify-between gap-3">
          <span className="text-ink">{line.quantity} × {line.label}</span><span className="text-muted">{money(line.line_total, row.currency)}</span>
        </li>)}</ul>
      </section>
      <section className="grid gap-2" aria-label={t`Places`}>
        <h3 className="title-section">{t`Places`}</h3>
        {row.seats.length ? <ul className="grid gap-1 text-sm">{row.seats.map(seat => <li key={seat.id} className="flex justify-between gap-3">
          <span className="min-w-0 break-words text-ink">{seat.attendee_email || t`No email yet`}</span>
          <span className="text-muted">{SEAT_LABEL[seat.status] ?? seat.status}</span>
        </li>)}</ul> : <p className="text-sm text-muted">{t`No places on this order.`}</p>}
      </section>
    </div> : null}
  </Modal>;
}
