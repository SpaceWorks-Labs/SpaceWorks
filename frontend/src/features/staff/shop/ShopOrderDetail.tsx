import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DetailLayout } from "../../../components/layouts";
import { KeyValueCard, StatusPill, type Action } from "../../../components/ui";
import { isUnpaid, orderStatus, shopMoney } from "../../shop/shopApi";
import { ShopBuyerOrderView } from "../../shop/ShopBuyerOrderView";
import type { ShopAccess } from "./shopAccess";
import { CancelDialog, CollectDialog, PaymentDialog } from "./ShopOrderDialogs";
import { ShopReceipt } from "./ShopReceipt";
import { ShopReturnDialog } from "./ShopReturnDialog";
import { staffShopError, staffShopKeys } from "./staffShopApi";
import { cancelOrder, CHANNEL_LABELS, collectOrder, fetchOrder, markReady, returnItems, takePayment, type ShopStaffOrder } from "./staffShopOrdersApi";

type Dialog = "collect" | "pay" | "cancel" | "return" | null;
const FINAL = ["collected", "cancelled", "unfulfilled", "refunded"];

/** One order at the desk: take payment, mark ready, hand over with the pickup code, cancel, return, receipt. */
export function ShopOrderDetail({ makerspaceId, orderId, access, onBack }: {
  makerspaceId: number; orderId: number; access: ShopAccess; onBack: () => void;
}) {
  const client = useQueryClient();
  const [dialog, setDialog] = useState<Dialog>(null);
  const [receipt, setReceipt] = useState(false);
  const query = useQuery({ queryKey: staffShopKeys.order(makerspaceId, orderId), queryFn: () => fetchOrder(orderId) });
  const done = (order: ShopStaffOrder) => {
    client.setQueryData(staffShopKeys.order(makerspaceId, orderId), order);
    void client.invalidateQueries({ queryKey: staffShopKeys.all(makerspaceId) });
    setDialog(null);
  };
  const ready = useMutation({ mutationFn: () => markReady(orderId), onSuccess: done });
  const collect = useMutation({ mutationFn: (code: string) => collectOrder(orderId, code), onSuccess: done });
  const pay = useMutation({ mutationFn: (body: Parameters<typeof takePayment>[1]) => takePayment(orderId, body), onSuccess: done });
  const cancel = useMutation({ mutationFn: (reason: string) => cancelOrder(orderId, reason), onSuccess: done });
  const giveBack = useMutation({ mutationFn: ({ rows, reason }: { rows: Parameters<typeof returnItems>[1]; reason: string }) =>
    returnItems(orderId, rows, reason), onSuccess: done });
  const order = query.data;
  if (order && receipt) return <ShopReceipt orderId={order.id} onBack={() => setReceipt(false)} />;
  const status = order?.status ?? "";
  const label = orderStatus(status);
  const open = (next: Dialog) => () => setDialog(next);
  const primary: Action | undefined = !order || !access.sell ? undefined
    : isUnpaid(status) && Number(order.amount_due) > 0 ? { label: t`Take payment`, onClick: open("pay") }
    : status === "paid" ? { label: t`Mark ready`, onClick: () => ready.mutate(), pending: ready.isPending, pendingLabel: "Marking…" }
    : status === "ready" || (isUnpaid(status) && Number(order.amount_due) <= 0) ? { label: t`Hand over`, onClick: open("collect") } : undefined;
  const overflow: Action[] = [
    ...(order && access.features.receipts ? [{ label: t`Receipt`, onClick: () => setReceipt(true) }] : []),
    ...(order && status === "paid" && access.sell ? [{ label: t`Hand over`, onClick: open("collect") }] : []),
    ...(order && access.manage && access.features.returns && status === "collected" ? [{ label: t`Return items`, onClick: open("return") }] : []),
    ...(order && access.manage && !FINAL.includes(status) ? [{ label: t`Cancel order`, tone: "danger" as const, onClick: open("cancel") }] : []),
  ];
  const buyer = order ? order.buyer_name || order.guest_name || "Walk-in" : "";
  const error = ready.error;
  return <>
    <DetailLayout back={{ label: t`All orders`, onClick: onBack }} title={order ? t`Order #${order.id}` : t`Order`}
      status={order ? <StatusPill label={label.label} tone={label.tone} /> : undefined}
      meta={order ? [buyer, CHANNEL_LABELS[order.channel ?? ""] ?? order.channel ?? ""] : undefined}
      state={query.isPending ? { status: "loading" } : query.error ? { status: "error", error: staffShopError(query.error),
        onRetry: () => { void query.refetch(); } } : { status: "ready" }}
      actions={{ primary, overflow }}
      banner={error ? { size: "inline", tone: "danger", lead: staffShopError(error) } : undefined}
      main={order ? <div className="grid gap-6">
        <ShopBuyerOrderView order={{ ...order, status, channel: order.channel ?? "", pickup_at: order.pickup_at ?? "space", space_name: "",
          subtotal: order.subtotal ?? "0", discount_total: order.discount_total ?? "0", total: order.total ?? "0", tax_total: order.tax_total ?? "0",
          amount_due: order.amount_due ?? "0", expires_at: order.expires_at ?? null, paid_at: order.paid_at ?? null,
          ready_at: order.ready_at ?? null, collected_at: order.collected_at ?? null, closed_at: order.closed_at ?? null }} />
        {order.returns.length ? <section aria-label={t`Returns`} className="grid gap-2">
          <h2 className="title-section">{t`Returns`}</h2>
          <ul className="grid gap-2">{order.returns.map(row => <li key={row.id} className="rounded-xl border border-line p-3 text-sm">
            {row.quantity} × {order.lines.find(line => line.id === row.line_id)?.label ?? t`Item`} · {row.disposition === "restock" ? t`back to stock` : t`written off`}
            {" · "}{shopMoney(row.amount, order.currency)}
            {row.refund_case_id ? <span className="block text-muted">{t`Refund case #${row.refund_case_id}: approve it in the Refunds tab.`}</span> : null}
          </li>)}</ul></section> : null}
      </div> : null}
      aside={order ? <KeyValueCard items={[
        { label: t`Buyer`, value: buyer },
        ...(order.buyer_email || order.guest_email ? [{ label: t`Email`, value: order.buyer_email || order.guest_email }] : []),
        { label: t`Payment`, value: order.payment_status || (isUnpaid(status) ? "Not paid" : "—") },
        { label: t`Pickup`, value: order.pickup_at === "event" ? order.pickup_event_title || "At an event" : "At the space" },
        ...(order.close_reason ? [{ label: t`Closed because`, value: order.close_reason }] : []),
      ]} /> : undefined} />
    {order && dialog === "collect" ? <CollectDialog open onClose={() => setDialog(null)} pending={collect.isPending} error={collect.error} onSubmit={code => collect.mutate(code)} /> : null}
    {order && dialog === "pay" ? <PaymentDialog open order={order} onClose={() => setDialog(null)} pending={pay.isPending} error={pay.error} onSubmit={body => pay.mutate(body)} /> : null}
    {order && dialog === "cancel" ? <CancelDialog open paid={Boolean(order.paid_at)} onClose={() => setDialog(null)} pending={cancel.isPending}
      error={cancel.error} onSubmit={reason => cancel.mutate(reason)} /> : null}
    {order && dialog === "return" ? <ShopReturnDialog open order={order} onClose={() => setDialog(null)} pending={giveBack.isPending}
      error={giveBack.error} onSubmit={(rows, reason) => giveBack.mutate({ rows, reason })} /> : null}
  </>;
}
