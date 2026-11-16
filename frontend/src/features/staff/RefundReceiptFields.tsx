import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Field } from "../../components/ui";
import { SETTLEMENT_METHODS, type RefundReceipt } from "./paymentsApi";

/** Local wall-clock "now" for a datetime-local input. */
function localNow() {
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return now.toISOString().slice(0, 16);
}

/** Receipt state for money handed back in person: method, reference and when. */
export function useRefundReceipt() {
  const [method, setMethod] = useState<string>("cash");
  const [reference, setReference] = useState("");
  const [refundedAt, setRefundedAt] = useState(localNow);
  const receipt = (): RefundReceipt => ({
    method, reference: reference.trim(), refunded_at: new Date(refundedAt).toISOString(),
  });
  // The API refuses a date more than five minutes ahead; say so before the round trip.
  const dateProblem = () => {
    const date = new Date(refundedAt).getTime();
    return !Number.isFinite(date) || date > Date.now() + 5 * 60_000
      ? "Enter the date and time the money was returned, without a future date." : null;
  };
  return { method, setMethod, reference, setReference, refundedAt, setRefundedAt, receipt, dateProblem };
}

export type RefundReceiptState = ReturnType<typeof useRefundReceipt>;

/** Shared by the ledger's offline refund and a refund-case approval on a cash charge. */
export function RefundReceiptFields({ state, onEdit }: { state: RefundReceiptState; onEdit?: () => void }) {
  return <>
    <Field label={t`Refund method`}>
      <select className="desk-input" value={state.method} onChange={(event) => state.setMethod(event.target.value)}>
        {SETTLEMENT_METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
    </Field>
    <Field label={t`Refund reference (optional)`}>
      <input className="desk-input" maxLength={64} value={state.reference}
        onChange={(event) => state.setReference(event.target.value)} />
    </Field>
    <Field label={t`Returned at`}>
      <input className="desk-input" type="datetime-local" required value={state.refundedAt}
        onChange={(event) => { state.setRefundedAt(event.target.value); onEdit?.(); }} />
    </Field>
  </>;
}
