import { useState } from "react";

import { Field, Modal } from "../../../components/ui";
import { staffShopError } from "./staffShopApi";
import type { ReturnRow, ShopStaffOrder } from "./staffShopOrdersApi";

type Row = { quantity: number; disposition: ReturnRow["disposition"] };

/** Taking items back: per line, how many and whether they go back on the shelf or are written off. */
export function ShopReturnDialog({ open, onClose, order, pending, error, onSubmit }: {
  open: boolean; onClose: () => void; order: ShopStaffOrder; pending: boolean; error: unknown;
  onSubmit: (rows: ReturnRow[], reason: string) => void;
}) {
  const returned = (lineId: number) => order.returns.filter(row => row.line_id === lineId).reduce((sum, row) => sum + row.quantity, 0);
  const [rows, setRows] = useState<Record<number, Row>>({});
  const [reason, setReason] = useState("");
  const chosen = Object.entries(rows).filter(([, row]) => row.quantity > 0)
    .map(([lineId, row]) => ({ line_id: Number(lineId), quantity: row.quantity, disposition: row.disposition }));
  const set = (lineId: number, patch: Partial<Row>) =>
    setRows(current => ({ ...current, [lineId]: { ...(current[lineId] ?? { quantity: 0, disposition: "restock" }), ...patch } }));
  return <Modal open={open} onClose={onClose} title="Return items" size="xl"
    footer={<div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button min-h-11" onClick={onClose} disabled={pending}>Close</button>
      <button type="submit" form="shop-return" className="desk-button-primary min-h-11" disabled={pending || !chosen.length || !reason.trim()}>
        {pending ? "Working…" : "Record return"}</button></div>}>
    <form id="shop-return" className="grid gap-4" onSubmit={event => { event.preventDefault(); onSubmit(chosen, reason.trim()); }}>
      <p className="text-sm">The refund is not paid here: a refund case opens for the money, and staff approve it in the Refunds tab.</p>
      {order.lines.map(line => {
        const left = line.quantity - returned(line.id);
        const row = rows[line.id] ?? { quantity: 0, disposition: "restock" };
        return <fieldset key={line.id} className="grid gap-2 rounded-xl border border-line p-3 sm:grid-cols-[1fr_auto_auto] sm:items-end" disabled={left <= 0}>
          <legend className="sr-only">{line.label}</legend>
          <p className="min-w-0 break-words"><span className="font-semibold">{line.label}</span>
            <span className="block text-sm text-muted">{left > 0 ? `${left} can be returned` : "Already returned"}</span></p>
          <label className="grid gap-1 text-sm font-semibold">Quantity
            <input className="desk-input min-h-11 w-24 font-normal" type="number" min={0} max={left} value={row.quantity}
              onChange={event => set(line.id, { quantity: Math.max(0, Math.min(left, Number(event.target.value) || 0)) })} /></label>
          <label className="grid gap-1 text-sm font-semibold">Goes to
            <select className="desk-input min-h-11 font-normal" value={row.disposition}
              onChange={event => set(line.id, { disposition: event.target.value as Row["disposition"] })}>
              <option value="restock">Back to stock</option><option value="write_off">Write off</option></select></label>
        </fieldset>;
      })}
      <Field label="Reason"><textarea className="desk-input" rows={2} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      {error ? <p role="alert" className="text-sm text-danger">{staffShopError(error)}</p> : null}
    </form>
  </Modal>;
}
