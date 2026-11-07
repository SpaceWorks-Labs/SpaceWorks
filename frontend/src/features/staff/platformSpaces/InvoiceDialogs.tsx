import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { formatMoney, useInvoiceAction, type HostingInvoice } from "./plansApi";
import { healthKey, listSpaceHealth } from "./spacesApi";

const today = () => new Date().toISOString().slice(0, 10);
const METHODS = [["bank_transfer", "Bank transfer"], ["cash", "Cash"], ["cheque", "Cheque"], ["card_offline", "Card (offline)"], ["other", "Other"]];

export function CreateInvoiceDialog({ onClose }: { onClose: () => void }) {
  const action = useInvoiceAction();
  const spaces = useQuery({ queryKey: [...healthKey, "", "", 1], queryFn: () => listSpaceHealth({ page: 1 }) });
  const [form, setForm] = useState({ space: "", amount: "", currency: "USD", description: "", due: today(), start: "", end: "" });
  const set = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  const canSubmit = Boolean(form.space) && Number(form.amount) > 0 && /^[A-Za-z]{3}$/.test(form.currency) && form.description.trim() !== "" && Boolean(form.due);
  return <ActionDialog title={t`New invoice`} confirmLabel={t`Create invoice`} pending={action.isPending} error={action.error} canSubmit={canSubmit}
    message={t`The Space Manager sees it under Usage & limits and can pay it online when online billing is on.`} onCancel={onClose}
    onSubmit={() => action.mutate({ path: "", body: { makerspace_id: Number(form.space), amount_minor: Math.round(Number(form.amount) * 100),
      currency: form.currency.toUpperCase(), description: form.description.trim(), due_on: form.due,
      ...(form.start ? { period_start: form.start } : {}), ...(form.end ? { period_end: form.end } : {}) } },
    { onSuccess: () => { toast(t`Invoice created.`); onClose(); } })}>
    <Field label={t`Space`}>
      <select className="desk-input" value={form.space} onChange={event => set("space", event.target.value)}>
        <option value="">{spaces.isLoading ? t`Loading…` : t`Choose a space`}</option>
        {(spaces.data?.results ?? []).map(space => <option key={space.id} value={space.id}>{space.name}</option>)}
      </select>
    </Field>
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Amount`}><input className="desk-input" type="number" min={0} step="0.01" value={form.amount} onChange={event => set("amount", event.target.value)} /></Field>
      <Field label={t`Currency`}><input className="desk-input" maxLength={3} value={form.currency} onChange={event => set("currency", event.target.value)} /></Field>
      <Field label={t`Due on`}><input className="desk-input" type="date" value={form.due} onChange={event => set("due", event.target.value)} /></Field>
      <Field label={t`Period start (optional)`}><input className="desk-input" type="date" value={form.start} onChange={event => set("start", event.target.value)} /></Field>
      <Field label={t`Period end (optional)`}><input className="desk-input" type="date" value={form.end} onChange={event => set("end", event.target.value)} /></Field>
    </div>
    <Field label={t`Description`}><input className="desk-input" value={form.description} onChange={event => set("description", event.target.value)} /></Field>
  </ActionDialog>;
}

export function RecordPaymentDialog({ invoice, onClose }: { invoice: HostingInvoice; onClose: () => void }) {
  const action = useInvoiceAction();
  const [form, setForm] = useState({ method: "bank_transfer", reference: "", received: today(), note: "" });
  const set = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  return <ActionDialog title={t`Record payment for ${invoice.number}`} confirmLabel={t`Record payment`} pending={action.isPending} error={action.error}
    canSubmit={form.reference.trim() !== "" && Boolean(form.received)} onCancel={onClose}
    message={t`${formatMoney(invoice.amount_minor, invoice.currency)} from ${invoice.makerspace_name}, received outside the online rail. The receipt cannot be edited later.`}
    onSubmit={() => action.mutate({ path: `${invoice.id}/record-payment`, body: { method: form.method, reference: form.reference.trim(),
      received_on: form.received, ...(form.note.trim() ? { note: form.note.trim() } : {}) } }, { onSuccess: () => { toast(t`Payment recorded.`); onClose(); } })}>
    <Field label={t`Method`}>
      <select className="desk-input" value={form.method} onChange={event => set("method", event.target.value)}>
        {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </Field>
    <Field label={t`Reference`} hint={t`A bank reference, receipt or cheque number.`}><input className="desk-input" value={form.reference} onChange={event => set("reference", event.target.value)} /></Field>
    <Field label={t`Received on`}><input className="desk-input" type="date" value={form.received} onChange={event => set("received", event.target.value)} /></Field>
    <Field label={t`Note (optional)`}><input className="desk-input" value={form.note} onChange={event => set("note", event.target.value)} /></Field>
  </ActionDialog>;
}

export function VoidInvoiceDialog({ invoice, onClose }: { invoice: HostingInvoice; onClose: () => void }) {
  const action = useInvoiceAction();
  return <ActionDialog title={t`Void ${invoice.number}`} confirmLabel={t`Void invoice`} tone="danger" pending={action.isPending} error={action.error}
    reason={{ label: t`Reason`, min: 3, max: 500 }} onCancel={onClose}
    message={t`${invoice.makerspace_name} no longer owes ${formatMoney(invoice.amount_minor, invoice.currency)} for this invoice.`}
    onSubmit={reason => action.mutate({ path: `${invoice.id}/void`, body: { reason } }, { onSuccess: () => { toast(t`Invoice voided.`); onClose(); } })} />;
}
