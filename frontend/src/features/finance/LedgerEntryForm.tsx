import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, Modal } from "../../components/ui";
import {
  DOMAIN_LABELS, EXPENSE_CATEGORIES, METHODS, RECEIPT_CATEGORIES, financeApi, financeError, invalidateFinance,
  uploadReceipt, words, type FinanceAccess,
} from "./financeApi";

/** Record an expense or another receipt in an area the caller may record in. Append-only. */
export function LedgerEntryForm({ makerspaceId, access, onClose }: {
  makerspaceId: number; access: FinanceAccess; onClose: () => void;
}) {
  const client = useQueryClient();
  const domains = access.record_everything ? Object.keys(DOMAIN_LABELS) : access.record_domains;
  const [kind, setKind] = useState<"expense" | "receipt">("expense");
  const [form, setForm] = useState({ domain: domains[0] ?? "general", category: "to_buy", method: "cash", amount: "",
    currency: "inr", entry_date: new Date().toISOString().slice(0, 10), description: "", counterparty: "", reference: "" });
  const [file, setFile] = useState<File | null>(null);
  const categories = kind === "expense" ? EXPENSE_CATEGORIES : RECEIPT_CATEGORIES;
  const save = useMutation({
    mutationFn: async () => {
      const receipt_id = file ? await uploadReceipt(makerspaceId, file) : undefined;
      return financeApi.createEntry(makerspaceId, { ...form, kind, receipt_id });
    },
    onSuccess: () => { invalidateFinance(client, makerspaceId); onClose(); },
  });
  const set = (name: keyof typeof form) => (event: { target: { value: string } }) => setForm({ ...form, [name]: event.target.value });
  return <Modal open onClose={onClose} title={kind === "expense" ? "Record an expense" : "Record other income"}>
    <form className="grid gap-3" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
      <fieldset className="flex gap-4"><legend className="text-sm font-semibold">Money</legend>
        {(["expense", "receipt"] as const).map(value => <label key={value} className="flex min-h-11 items-center gap-2">
          <input type="radio" name="kind" checked={kind === value} onChange={() => {
            setKind(value); setForm({ ...form, category: value === "expense" ? "to_buy" : "donation" });
          }} />{value === "expense" ? "Paid out" : "Received"}</label>)}
      </fieldset>
      <Field label="Area"><select className="desk-input" value={form.domain} onChange={set("domain")}>
        {domains.map(domain => <option key={domain} value={domain}>{DOMAIN_LABELS[domain] ?? domain}</option>)}</select></Field>
      <Field label="Category"><select className="desk-input" value={form.category} onChange={set("category")}>
        {categories.map(category => <option key={category} value={category}>{words(category)}</option>)}</select></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Amount"><input className="desk-input" inputMode="decimal" required pattern="[0-9]+(\.[0-9]{1,2})?" value={form.amount} onChange={set("amount")} /></Field>
        <Field label="Currency"><input className="desk-input" required maxLength={3} value={form.currency} onChange={set("currency")} /></Field>
        <Field label="Method"><select className="desk-input" value={form.method} onChange={set("method")}>
          {METHODS.map(method => <option key={method} value={method}>{words(method)}</option>)}</select></Field>
        <Field label="Date"><input type="date" className="desk-input" required value={form.entry_date} onChange={set("entry_date")} /></Field>
      </div>
      <Field label="What it was for"><input className="desk-input" required maxLength={300} value={form.description} onChange={set("description")} /></Field>
      <Field label={kind === "expense" ? "Paid to (supplier)" : "Received from"}><input className="desk-input" maxLength={150} value={form.counterparty} onChange={set("counterparty")} /></Field>
      <Field label="Reference (bill or transaction number)"><input className="desk-input" maxLength={64} value={form.reference} onChange={set("reference")} /></Field>
      <Field label="Receipt photo or PDF (optional)" hint="JPEG, PNG, WebP or PDF, up to 10 MB."><input type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf" className="desk-input"
        onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
      {save.error ? <p role="alert" className="text-sm text-danger">{financeError(save.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" onClick={onClose}>Cancel</button>
        <button type="submit" className="desk-button" disabled={save.isPending}>{save.isPending ? "Saving…" : "Record"}</button>
      </div>
    </form>
  </Modal>;
}
