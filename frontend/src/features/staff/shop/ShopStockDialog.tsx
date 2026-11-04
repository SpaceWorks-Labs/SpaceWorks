import { useState } from "react";

import { Field, Modal, SegmentedControl } from "../../../components/ui";
import { staffShopError, type StockMove } from "./staffShopApi";

export type StockTarget = { variantId: number; label: string; onHand: number };
type Mode = "restock" | "adjust";
const ADJUST_KINDS = [{ value: "count", label: "Shelf count" }, { value: "damage", label: "Damaged" }, { value: "internal_use", label: "Used in the space" }];

/**
 * Restock adds what arrived. An adjustment records why the count changed: a shelf count sets the
 * difference to the counted number; damage and internal use take items out. Every move is kept in history.
 */
export function ShopStockDialog({ target, mode, pending, error, onClose, onSubmit }: {
  target: StockTarget; mode: Mode; pending: boolean; error: unknown; onClose: () => void; onSubmit: (move: StockMove) => void;
}) {
  const [kind, setKind] = useState<StockMove["kind"]>(mode === "restock" ? "restock" : "count");
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const number = Number(value);
  const valid = value.trim() !== "" && Number.isInteger(number) && (kind === "count" ? number >= 0 : number > 0);
  // Adjustments are a signed delta; a count is turned into the delta from what is on hand now.
  const quantity = kind === "restock" ? number : kind === "count" ? number - target.onHand : -number;
  const label = kind === "restock" ? "How many arrived" : kind === "count" ? "Counted on the shelf" : "How many to take out";
  return <Modal open onClose={onClose} title={`${mode === "restock" ? "Restock" : "Adjust"} ${target.label}`}
    footer={<div className="flex flex-wrap justify-end gap-2">
      <button type="button" className="desk-button min-h-11" onClick={onClose} disabled={pending}>Close</button>
      <button type="submit" form="shop-stock" className="desk-button-primary min-h-11" disabled={pending || !valid || quantity === 0 || (kind !== "restock" && !reason.trim())}>
        {pending ? "Saving…" : "Record"}</button></div>}>
    <form id="shop-stock" className="grid gap-4" onSubmit={event => { event.preventDefault(); onSubmit({ kind, quantity, reason: reason.trim() }); }}>
      <p className="text-sm text-muted">On hand now: <span className="font-semibold tabular-nums text-ink">{target.onHand}</span></p>
      {mode === "adjust" ? <SegmentedControl label="Why the count changes" value={kind} options={ADJUST_KINDS} onChange={next => setKind(next as StockMove["kind"])} /> : null}
      <Field label={label}><input className="desk-input min-h-11 w-32 tabular-nums" type="number" min={0} step={1} value={value}
        onChange={event => setValue(event.target.value)} /></Field>
      {kind === "count" && valid ? <p role="status" className="text-sm">{quantity === 0 ? "No change." : `${quantity > 0 ? "+" : ""}${quantity} against the record.`}</p> : null}
      <Field label={kind === "restock" ? "Note (optional)" : "Reason"}><input className="desk-input min-h-11" value={reason}
        onChange={event => setReason(event.target.value)} /></Field>
      {error ? <p role="alert" className="text-sm text-danger">{staffShopError(error)}</p> : null}
    </form>
  </Modal>;
}
