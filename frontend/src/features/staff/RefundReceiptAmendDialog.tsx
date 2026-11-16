import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FlowLayout } from "../../components/layouts";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { amendRefund, invalidatePaymentViews, SETTLEMENT_METHODS, type RefundRow } from "./paymentsApi";

export function RefundReceiptAmendDialog({ makerspaceId, paymentId, refund, onClose }: {
  makerspaceId: number; paymentId: number; refund: RefundRow; onClose: () => void;
}) {
  const client = useQueryClient();
  const [method, setMethod] = useState(refund.method ?? "cash");
  const [reference, setReference] = useState(refund.reference ?? "");
  const [date, setDate] = useState(() => {
    const value = new Date(refund.refunded_at ?? refund.created_at);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
  });
  const mutation = useMutation({
    mutationFn: () => amendRefund(makerspaceId, paymentId, refund.id, {
      method, reference, refunded_at: new Date(date).toISOString(),
    }),
    onSuccess: () => { invalidatePaymentViews(client, makerspaceId); onClose(); },
  });
  return <FlowLayout presentation="dialog" open onCancel={onClose} title={t`Correct refund receipt`}
    state={{ status: "ready" }} steps={[{ key: "receipt", label: t`Receipt correction`, state: "current" }]} current="receipt"
    footer={{ next: { label: t`Save correction`, pending: mutation.isPending,
      onClick: () => (document.getElementById("amend-refund-form") as HTMLFormElement | null)?.requestSubmit() } }}
    work={<>
    <p className="text-sm text-muted">{t`The amount stays the same. This appends a receipt correction and does not return money again.`}</p>
    <form id="amend-refund-form" className="mt-3 grid gap-3" onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
      <Field label={t`Refund method`}><select className="desk-input" value={method} onChange={(event) => setMethod(event.target.value)}>
        {SETTLEMENT_METHODS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></Field>
      <Field label={t`Refund reference`}><input className="desk-input" maxLength={64} value={reference} onChange={(event) => setReference(event.target.value)} /></Field>
      <Field label={t`Returned at`}><input className="desk-input" type="datetime-local" required value={date} onChange={(event) => setDate(event.target.value)} /></Field>
      {mutation.error ? <p role="alert" className="text-danger">{mutation.error.message}</p> : null}
    </form>
  </>} />;
}
