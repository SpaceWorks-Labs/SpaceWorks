import { useState } from "react";
import { FlowLayout } from "../../components/layouts";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow, RelativeTime, StatusPill } from "../../components/ui";
import {
  formatMoney,
  invalidatePaymentViews,
  refundErrorMessage,
  refundPayment,
  remainingRefundable,
  recordOfflineRefund,
  SETTLEMENT_METHODS,
  type PaymentRow,
} from "./paymentsApi";

// Client-side mirror of `PaymentRefundRequestSerializer` (positive, two decimals) plus the
// balance rule the service enforces under the row lock. The server is still the authority:
// two staff refunding at once both pass here and one of them gets `refund_exceeds_balance`.
export function validateRefundAmount(raw: string, remaining: number): string | null {
  const trimmed = raw.trim();
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return "Enter an amount with at most two decimals.";
  const amount = Number(trimmed);
  if (amount <= 0) return "Refund amount must be greater than zero.";
  if (amount > remaining) return "Refund amount cannot exceed the remaining balance.";
  return null;
}

/** Mount with `key={payment.id}` so the form state resets per payment. */
export function PaymentRefundDialog({
  makerspaceId,
  payment,
  onClose,
  releaseDeposit = false,
}: {
  makerspaceId: number;
  payment: PaymentRow;
  onClose: () => void;
  releaseDeposit?: boolean;
}) {
  const queryClient = useQueryClient();
  const remaining = remainingRefundable(payment);
  const offline = payment.status === "paid_offline";
  const [amount, setAmount] = useState(remaining.toFixed(2));
  const [reason, setReason] = useState("");
  const [method, setMethod] = useState<string>("cash");
  const [reference, setReference] = useState("");
  const [refundedAt, setRefundedAt] = useState(() => {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    return now.toISOString().slice(0, 16);
  });
  const [validationError, setValidationError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => offline
      ? recordOfflineRefund(makerspaceId, payment.id, {
        amount: amount.trim(), reason: reason.trim(),
        receipt: { method, reference: reference.trim(), refunded_at: new Date(refundedAt).toISOString() },
      }, releaseDeposit)
      : refundPayment(makerspaceId, payment.id, { amount: amount.trim(), reason: reason.trim() }),
    onSuccess: () => {
      invalidatePaymentViews(queryClient, makerspaceId);
      onClose();
    },
  });
  const submit = () => {
    const date = new Date(refundedAt).getTime();
    const problem = validateRefundAmount(amount, remaining) ?? (offline &&
      (!Number.isFinite(date) || date > Date.now() + 5 * 60_000)
      ? "Enter the date and time the money was returned, without a future date." : null);
    setValidationError(problem);
    if (!problem) mutation.mutate();
  };
  const error = validationError ?? (mutation.error ? refundErrorMessage(mutation.error) : null);

  return (
    <FlowLayout presentation="dialog" open onCancel={() => { if (!mutation.isPending) onClose(); }} state={{ status: "ready" }}
      title={`${releaseDeposit ? "Release deposit" : "Refund payment"} ${formatMoney(payment.amount, payment.currency)}`}
      steps={[{ key: "receipt", label: "Refund details", state: "current" }]} current="receipt"
      footer={{ next: { label: releaseDeposit ? "Record deposit release" : `Refund ${formatMoney(Number.isFinite(Number(amount)) ? amount || "0" : "0", payment.currency)}`,
        pending: mutation.isPending, pendingLabel: "Recording refund…", disabled: remaining <= 0,
        onClick: () => document.getElementById("payment-refund-form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })) } }}
      work={<>
      <p className="text-sm text-muted">
        {payment.subject_label} · refunded so far {formatMoney(payment.refunded_amount, payment.currency)} ·
        remaining {formatMoney(remaining.toFixed(2), payment.currency)}
      </p>
      <form
        id="payment-refund-form"
        className="mt-3 grid gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        {offline ? (
          <>
            <p className="text-sm text-muted">{releaseDeposit ? "After closing the loan, record the deposit money handed back to the borrower." : "Record money already returned."} This creates a permanent receipt.</p>
            <Field label="Refund method">
              <select className="desk-input" value={method} onChange={(event) => setMethod(event.target.value)}>
                {SETTLEMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </Field>
            <Field label="Refund reference (optional)">
              <input className="desk-input" maxLength={64} value={reference} onChange={(event) => setReference(event.target.value)} />
            </Field>
            <Field label="Returned at">
              <input className="desk-input" type="datetime-local" required value={refundedAt} onChange={(event) => { setRefundedAt(event.target.value); setValidationError(null); }} />
            </Field>
          </>
        ) : null}
        <Field label="Refund amount" error={validationError ?? undefined}>
          <input
            className="desk-input"
            inputMode="decimal"
            value={amount}
            disabled={remaining <= 0}
            onChange={(event) => {
              setAmount(event.target.value);
              setValidationError(null);
            }}
          />
        </Field>
        <Field label="Reason (optional)">
          <input
            className="desk-input"
            maxLength={255}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </Field>
      </form>
      {error && !validationError ? (
        <p className="mt-3 text-sm text-danger" role="alert">{error}</p>
      ) : null}
      <RefundList refunds={payment.refunds} />
      </>}
    />
  );
}

function RefundList({ refunds }: { refunds: PaymentRow["refunds"] }) {
  if (!refunds?.length) return <div className="mt-4"><EmptyState message="No refunds recorded yet. Add the refund details above to record one." /></div>;
  return <section className="mt-4 grid gap-3" aria-label="Refunds">
    <h2 className="title-panel">Refunds</h2>
    {refunds.map(refund => <ListRow key={refund.id} title={formatMoney(refund.amount, refund.currency)}
      meta={<>
        {refund.corrected ? "Replaced receipt · " : refund.amends ? "Corrected receipt · " : ""}
        <RelativeTime date={refund.created_at} />
        {refund.reason ? ` · ${refund.reason}` : ""}
        {refund.method ? ` · ${refund.method.replace(/_/g, " ")}` : ""}
        {refund.reference ? ` · ${refund.reference}` : ""}
        {refund.refunded_at ? <span> · Returned <RelativeTime date={refund.refunded_at} /></span> : null}
      </>}
      right={<StatusPill label={refund.status[0].toUpperCase() + refund.status.slice(1)}
        tone={refund.status === "succeeded" ? "success" : refund.status === "failed" ? "danger" : "warn"} />} />)}
  </section>;
}
