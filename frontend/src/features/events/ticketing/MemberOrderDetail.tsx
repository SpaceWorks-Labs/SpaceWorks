import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Users } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DetailLayout } from "../../../components/layouts";
import { ErrorText, StatusPill } from "../../../components/ui";
import { useTenantPath } from "../../../lib/tenant";
import { shopError } from "./EventTicketShop";
import {
  assignAttendees, cancelOrder, chaseAttendees, claimOwnSeat, fetchOrder, money, ORDER_STATUS, ticketingKeys,
  type TicketOrder,
} from "./ticketingApi";

function SeatRow({ seat, order, onAssign, onClaim, busy }: {
  seat: TicketOrder["seats"][number]; order: TicketOrder; busy: boolean;
  onAssign: (seatId: number, email: string) => void; onClaim: (seatId: number) => void;
}) {
  const [email, setEmail] = useState(seat.attendee_email);
  const editable = seat.status === "unclaimed" && order.status !== "cancelled" && order.status !== "expired";
  return <li className="grid gap-2 rounded-card border border-line p-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-sm font-semibold text-ink">{seat.attendee_email || t`No one named yet`}</span>
      <StatusPill label={seat.status === "claimed" ? t`Claimed` : seat.status === "void" ? t`Cancelled` : seat.invited_at ? t`Invited` : t`Unclaimed`}
        tone={seat.status === "claimed" ? "success" : seat.status === "void" ? "neutral" : "warn"} />
    </div>
    {editable ? <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); onAssign(seat.id, email); }}>
      <label className="sr-only" htmlFor={`seat-${seat.id}`}>{t`Attendee email`}</label>
      <input id={`seat-${seat.id}`} className="desk-input min-w-0 flex-1" type="email" value={email}
        placeholder="attendee@example.com" onChange={event => setEmail(event.target.value)} />
      <button className="desk-button" type="submit" disabled={busy}>{t`Save`}</button>
      {order.status === "paid" ? <button className="desk-button" type="button" disabled={busy} onClick={() => onClaim(seat.id)}>{t`This one is mine`}</button> : null}
    </form> : null}
  </li>;
}

/** One order: lines, total, seats and who claimed them; name people, chase them or abandon an unpaid order. */
export function MemberOrderDetail({ makerspaceId, orderId, makerspaceSlug }: { makerspaceId: number; orderId: number; makerspaceSlug: string }) {
  const queryClient = useQueryClient();
  const tenantPath = useTenantPath(makerspaceSlug);
  const key = ticketingKeys.order(makerspaceId, orderId);
  const order = useQuery({ queryKey: key, enabled: Boolean(makerspaceId), queryFn: () => fetchOrder(makerspaceId, orderId) });
  const refresh = (next?: TicketOrder) => {
    if (next) queryClient.setQueryData(key, next); else void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({ queryKey: ticketingKeys.orders(makerspaceId) });
  };
  const assign = useMutation({ mutationFn: ({ seatId, email }: { seatId: number; email: string }) =>
    assignAttendees(makerspaceId, orderId, { [String(seatId)]: email }), onSuccess: refresh });
  const chase = useMutation({ mutationFn: () => chaseAttendees(makerspaceId, orderId), onSuccess: refresh });
  const cancel = useMutation({ mutationFn: () => cancelOrder(makerspaceId, orderId), onSuccess: refresh });
  const claim = useMutation({ mutationFn: (seatId: number) => claimOwnSeat(makerspaceId, orderId, seatId), onSuccess: () => refresh() });
  const current = order.data;
  const error = assign.error ?? chase.error ?? cancel.error ?? claim.error;
  const busy = assign.isPending || chase.isPending || cancel.isPending || claim.isPending;
  return <DetailLayout back={{ label: t`My orders`, href: tenantPath("member/orders") }} title={current?.event_title ?? t`Order`}
    state={order.isLoading ? { status: "loading" } : order.error ? { status: "error", error: shopError(order.error) } : { status: "ready" }}
    status={current ? <StatusPill label={ORDER_STATUS[current.status].label} tone={ORDER_STATUS[current.status].tone} /> : null}
    meta={current ? [`Order #${current.id}`, money(current.total, current.currency)] : []}
    banner={current?.payment_disputed ? { size: "banner", tone: "warn", lead: "This payment is disputed with the card provider." } : undefined}
    actions={current?.status === "pending" ? {
      primary: current.checkout_url ? { label: t`Pay now`, href: current.checkout_url, external: true } : undefined,
      overflow: [{ label: t`Abandon this order`, tone: "danger", onClick: () => cancel.mutate(),
        confirm: { title: t`Abandon this order?`, message: t`Its places go back on sale.`, confirmLabel: t`Abandon` } }] }
      : current?.status === "paid" ? { secondary: { label: t`Remind people to claim`, onClick: () => chase.mutate(), pending: chase.isPending } } : undefined}
    main={current ? <div className="grid gap-6">
      {error ? <ErrorText message={shopError(error)} /> : null}
      <section className="grid gap-2"><h2 className="eyebrow">{t`What you bought`}</h2>
        <dl className="grid gap-1 text-sm">{current.lines.map(line => <div key={line.id} className="flex justify-between gap-4">
          <dt>{line.label}{line.quantity > 1 ? ` × ${line.quantity}` : ""}</dt><dd className="tabular-nums">{money(line.line_total, current.currency)}</dd></div>)}
          {Number(current.fee_total) > 0 ? <div className="flex justify-between gap-4"><dt>{t`Booking fee`}</dt><dd className="tabular-nums">{money(current.fee_total, current.currency)}</dd></div> : null}
          <div className="flex justify-between gap-4 border-t border-line pt-1 font-semibold text-ink"><dt>{t`Total`}</dt><dd className="tabular-nums">{money(current.total, current.currency)}</dd></div>
        </dl></section>
      <section className="grid gap-2"><h2 className="flex items-center gap-2 eyebrow"><Users aria-hidden="true" size={16} />{t`Places`}</h2>
        <ul className="grid gap-2">{current.seats.map(seat => <SeatRow key={seat.id} seat={seat} order={current} busy={busy}
          onAssign={(seatId, email) => assign.mutate({ seatId, email })} onClaim={seatId => claim.mutate(seatId)} />)}</ul>
      </section>
    </div> : null} />;
}
