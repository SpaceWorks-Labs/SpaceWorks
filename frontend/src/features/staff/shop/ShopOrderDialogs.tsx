import { useState } from "react";

import { Field, Modal, SegmentedControl } from "../../../components/ui";
import { shopMoney } from "../../shop/shopApi";
import { staffShopError } from "./staffShopApi";
import type { PayMethod, ShopStaffOrder } from "./staffShopOrdersApi";

type Base = { open: boolean; onClose: () => void; pending: boolean; error: unknown };

function Footer({ onClose, pending, label, disabled, form }: { onClose: () => void; pending: boolean; label: string; disabled?: boolean; form: string }) {
  return <div className="flex flex-wrap justify-end gap-2">
    <button type="button" className="desk-button min-h-11" onClick={onClose} disabled={pending}>Close</button>
    <button type="submit" form={form} className="desk-button-primary min-h-11" disabled={pending || disabled}>{pending ? "Working…" : label}</button>
  </div>;
}

/** Handing over: the buyer reads their pickup code aloud or shows it; a wrong code is refused by the server. */
export function CollectDialog({ open, onClose, pending, error, onSubmit }: Base & { onSubmit: (code: string) => void }) {
  const [code, setCode] = useState("");
  return <Modal open={open} onClose={onClose} title="Hand over the order"
    footer={<Footer onClose={onClose} pending={pending} label="Hand over" disabled={!code.trim()} form="shop-collect" />}>
    <form id="shop-collect" className="grid gap-3" onSubmit={event => { event.preventDefault(); onSubmit(code.trim()); }}>
      <Field label="Pickup code" hint="Ask the buyer for the code from their order."><input className="desk-input min-h-11 font-mono uppercase tracking-widest"
        autoComplete="off" value={code} onChange={event => setCode(event.target.value.toUpperCase())} /></Field>
      {error ? <p role="alert" className="text-sm text-danger">{staffShopError(error)}</p> : null}
    </form>
  </Modal>;
}

export const METHOD_OPTIONS = [{ value: "cash", label: "Cash" }, { value: "upi", label: "UPI" }, { value: "card_machine", label: "Card machine" }];

/** Paying at the desk. Cash needs an open drawer when cash-up is on; UPI and card take the transaction reference. */
export function PaymentDialog({ open, onClose, pending, error, order, onSubmit }: Base & {
  order: ShopStaffOrder; onSubmit: (body: { method: PayMethod; reference: string; hand_over: boolean }) => void;
}) {
  const [method, setMethod] = useState<PayMethod>("cash");
  const [reference, setReference] = useState("");
  const [handOver, setHandOver] = useState(true);
  const needsReference = method !== "cash";
  return <Modal open={open} onClose={onClose} title={`Take ${shopMoney(order.amount_due, order.currency)}`}
    footer={<Footer onClose={onClose} pending={pending} label="Record payment" disabled={needsReference && !reference.trim()} form="shop-pay" />}>
    <form id="shop-pay" className="grid gap-4" onSubmit={event => { event.preventDefault(); onSubmit({ method, reference: reference.trim(), hand_over: handOver }); }}>
      <SegmentedControl label="Payment method" value={method} options={METHOD_OPTIONS} onChange={value => setMethod(value as PayMethod)} fullWidth />
      <Field label={needsReference ? "Transaction reference" : "Reference (optional)"}>
        <input className="desk-input min-h-11" value={reference} onChange={event => setReference(event.target.value)} /></Field>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={handOver} onChange={event => setHandOver(event.target.checked)} />
        Hand the items over now</label>
      {error ? <p role="alert" className="text-sm text-danger">{staffShopError(error)}</p> : null}
    </form>
  </Modal>;
}

/** Cancelling a paid order opens a refund case; the money moves only when it is approved in Refunds. */
export function CancelDialog({ open, onClose, pending, error, paid, onSubmit }: Base & { paid: boolean; onSubmit: (reason: string) => void }) {
  const [reason, setReason] = useState("");
  return <Modal open={open} onClose={onClose} title="Cancel this order"
    footer={<Footer onClose={onClose} pending={pending} label="Cancel order" disabled={!reason.trim()} form="shop-cancel" />}>
    <form id="shop-cancel" className="grid gap-3" onSubmit={event => { event.preventDefault(); onSubmit(reason.trim()); }}>
      <p className="text-sm">Held stock goes back on sale.{paid ? " This order was paid, so a refund case opens for staff to approve in the Refunds tab." : ""}</p>
      <Field label="Reason"><textarea className="desk-input" rows={3} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      {error ? <p role="alert" className="text-sm text-danger">{staffShopError(error)}</p> : null}
    </form>
  </Modal>;
}
