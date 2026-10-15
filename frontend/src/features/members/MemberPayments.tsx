import { EmptyState, ListRow, StatusPill } from "../../components/ui";
import type { MemberPayment as GeneratedMemberPayment } from "../../generated/api";
import { useState } from "react";
import { DUE_OPTIONS, PaymentDueBadge } from "../staff/PaymentDueBadge";
import { PaymentDocuments } from "../payments/PaymentDocuments";

// Additive API field until the coordinator regenerates the OpenAPI client.
export type MemberPayment = Omit<GeneratedMemberPayment, "refunded_amount" | "refunds" | "subject_type"> & {
  subject_type: GeneratedMemberPayment["subject_type"] | "membership_request";
  refunded_amount?: string | number; due_at?: string | null; due_date?: string | null; due_state?: string;
  refunds: Array<GeneratedMemberPayment["refunds"][number] & {
    method?: string; reference?: string; refunded_at?: string | null;
  }>;
};

export function MemberPaymentRows({
  payments,
  checkoutPaymentId,
  onCheckout,
  makerspaceId,
}: {
  payments: MemberPayment[];
  checkoutPaymentId?: number;
  onCheckout: (paymentId: number) => void;
  makerspaceId?: number;
}) {
  const [dueFilter, setDueFilter] = useState("");
  return (
    <>
    <label className="grid gap-1 text-xs text-muted sm:max-w-xs"><span>Payment due dates</span>
      <select className="desk-input" value={dueFilter} onChange={(event) => setDueFilter(event.target.value)}>
        <option value="">All due dates</option>{DUE_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
    </label>
    <ul className="mt-3 space-y-2 text-sm text-muted [&>li>div>:first-child]:basis-48">
      {payments.filter((payment) => !dueFilter || payment.due_state === dueFilter).map((payment) => (
        <li key={payment.id}><ListRow title={payment.subject_label} right={<div className="grid justify-items-end gap-1 text-right"><span className="font-display text-lg tabular-nums text-ink">{payment.amount} {(payment.currency ?? "").toUpperCase()}</span><StatusPill label={(payment.status || "Unknown").replace(/_/g, " ")} tone={["paid_online", "paid_offline"].includes(payment.status || "") ? "success" : payment.status === "pending" ? "warn" : "neutral"} /></div>} meta={<>
          {/* Facts wrap as chips on a phone; the one action gets its own full-width line
              below them instead of sitting mid-sentence between separators. */}
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <PaymentDueBadge payment={payment} />
            {/* No rail behind this charge: the space takes it in person. Offering a
                payment link here called an endpoint that could not succeed. */}
            {!payment.checkout_url && payment.status === "pending" && !payment.online_payment_available ? <span>Pay at the space</span> : null}
            {payment.settlement ? (
              <span>
                Received {new Date(payment.settlement.received_at).toLocaleDateString()}
                {" by "}
                {payment.settlement.method.replace(/_/g, " ")}
              </span>
            ) : null}
            {/* Money sent back on this charge. Pending refunds are shown too, so a payer
                who was told a refund is on its way can see it is recorded. */}
            {(payment.refunds ?? []).filter((refund) => refund.status !== "failed").map((refund, index) => (
              <span key={index} className="break-words">
                {refund.status === "succeeded" ? "Refunded" : "Refund pending"}{" "}
                <span className="tabular-nums">
                  {refund.amount} {(refund.currency ?? "").toUpperCase()}
                </span>
                {refund.reason ? ` (${refund.reason})` : null}
                {refund.method ? ` by ${refund.method.replace(/_/g, " ")}` : ""}
                {refund.reference ? ` · ${refund.reference}` : ""}
              </span>
            ))}
          </span>
          {payment.checkout_url ? (
            <span className="mt-3 flex"><a className="desk-button-brand w-full sm:w-auto" href={payment.checkout_url}>Pay now</a></span>
          ) : payment.status === "pending" && payment.online_payment_available ? (
            <span className="mt-3 flex">
              <button
                className="desk-button w-full sm:w-auto"
                disabled={checkoutPaymentId !== undefined}
                onClick={() => onCheckout(payment.id)}
                type="button"
              >
                Generate payment link
              </button>
            </span>
          ) : null}
        </>} /></li>
      ))}
    </ul>
    {payments.length > 0 && !payments.some(payment => !dueFilter || payment.due_state === dueFilter) ? <EmptyState message="No payments match this due date. Choose another filter." /> : null}
    {makerspaceId ? <PaymentDocuments key={makerspaceId} makerspaceId={makerspaceId} audience="member" /> : null}
    </>
  );
}
