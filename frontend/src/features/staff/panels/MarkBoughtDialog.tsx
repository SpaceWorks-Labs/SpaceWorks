import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Field, Modal } from "../../../components/ui";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import { METHODS, uploadReceipt, words } from "../../finance/financeApi";
import type { ToBuyItem } from "./ProcurementPanelRows";
import { vendorKeys, vendorsApi } from "./vendorsApi";

/** Says what went wrong in words a buyer can act on; a 409 carries a machine code from the ledger. */
export function markBoughtError(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.status === 403) return t`You can't record spending for this item. Ask a manager who looks after this area's money.`;
    if (error.code === "ledger_source_conflict") return `This purchase is already in the finance ledger with a different amount or currency. ${error.detail ?? ""}`.trim();
    if (error.code === "receipt_invalid") return error.detail ? t`${error.detail} Choose the file again and retry.` : t`The receipt could not be used. Choose the file again and retry.`;
    return error.message;
  }
  return error instanceof Error ? error.message : t`Couldn't mark it bought. Try again.`;
}

/** Records what was paid (once, in the ledger), marks the item received and restocks a consumable it came from. */
export function MarkBoughtDialog({ item, makerspaceId, vendorsEnabled, onClose, onDone }: {
  item: ToBuyItem; makerspaceId: number; vendorsEnabled: boolean; onClose: () => void; onDone: () => void;
}) {
  const [form, setForm] = useState({ amount: "", currency: "", method: "cash", reference: "", vendor: item.vendor ? String(item.vendor) : "",
    vendor_name: item.vendor_name ?? "", refill_amount: "", entry_date: new Date().toISOString().slice(0, 10) });
  const [file, setFile] = useState<File | null>(null);
  const vendors = useQuery({ queryKey: vendorKeys.list(makerspaceId, false), queryFn: () => vendorsApi.list(makerspaceId), enabled: vendorsEnabled });
  const needsRefill = Boolean(item.source_consumable);
  const usePicked = vendorsEnabled && form.vendor !== "";
  const save = useMutation({
    mutationFn: async () => {
      const receipt_id = file ? await uploadReceipt(makerspaceId, file) : undefined;
      return staffRequest<ToBuyItem>(`/procurement/to-buy/${item.id}/mark-bought`, { method: "POST", body: JSON.stringify({
        amount: form.amount.trim(), method: form.method, reference: form.reference.trim(), entry_date: form.entry_date || undefined,
        ...(form.currency.trim() ? { currency: form.currency.trim().toLowerCase() } : {}),
        ...(receipt_id ? { receipt_id } : {}),
        ...(usePicked ? { vendor_id: Number(form.vendor) } : { vendor_name: form.vendor_name.trim() }),
        ...(needsRefill ? { refill_amount: form.refill_amount.trim() } : {}),
      }) });
    },
    onSuccess: onDone,
  });
  const set = (key: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [key]: event.target.value });
  const ready = /^\d+(\.\d{1,3})?$/.test(form.amount.trim()) && Number(form.amount) > 0 && (!needsRefill || Number(form.refill_amount) > 0);
  return <Modal open onClose={onClose} title={t`Mark ${item.name} bought`}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault(); if (ready) save.mutate(); }}>
      <p className="text-sm text-muted">{t`This records what was paid in the finance ledger and moves the item to Received. Nothing is paid out.`}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t`Amount paid`}><input className="desk-input" inputMode="decimal" required pattern="[0-9]+(\.[0-9]{1,3})?" value={form.amount} onChange={set("amount")} /></Field>
        <Field label={t`Currency`} hint={t`Leave blank for the space's currency.`}><input className="desk-input" maxLength={3} placeholder={t`e.g. INR`} value={form.currency} onChange={set("currency")} /></Field>
        <Field label={t`Paid by`}><select className="desk-input" value={form.method} onChange={set("method")}>
          {METHODS.map(method => <option key={method} value={method}>{words(method)}</option>)}</select></Field>
        <Field label={t`Date paid`}><input className="desk-input" type="date" value={form.entry_date} onChange={set("entry_date")} /></Field>
      </div>
      <Field label={t`Reference (bill or transaction number)`}><input className="desk-input" maxLength={64} value={form.reference} onChange={set("reference")} /></Field>
      {vendorsEnabled ? <Field label={t`Supplier`}><select className="desk-input" value={form.vendor} onChange={set("vendor")}>
        <option value="">{t`Not a saved vendor (type the name)`}</option>
        {(vendors.data ?? []).map(vendor => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}</select></Field> : null}
      {!usePicked ? <Field label={vendorsEnabled ? t`Supplier name` : t`Supplier`}><input className="desk-input" maxLength={200} value={form.vendor_name} onChange={set("vendor_name")} /></Field> : null}
      {needsRefill ? <Field label={t`Amount received (grams)`} hint={t`Added back to the machine consumable this request came from.`}>
        <input className="desk-input" inputMode="decimal" required value={form.refill_amount} onChange={set("refill_amount")} /></Field> : null}
      <Field label={t`Receipt photo or PDF (optional)`} hint={t`JPEG, PNG, WebP or PDF, up to 10 MB.`}><input type="file" className="desk-input"
        accept="image/jpeg,image/png,image/webp,application/pdf" onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
      {save.error ? <p role="alert" className="text-sm text-danger">{markBoughtError(save.error)}</p> : null}
      {vendors.error ? <p role="alert" className="text-sm text-danger">{t`Couldn't load vendors. Type the supplier name instead.`}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || save.isPending}>{save.isPending ? t`Saving…` : t`Mark bought`}</button>
      </div>
    </form>
  </Modal>;
}
