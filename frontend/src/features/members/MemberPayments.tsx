import { formatDate } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, StatusPill } from "../../components/ui";
import type { MemberPayment as GeneratedMemberPayment } from "../../generated/api";
import { useState } from "react";
import { DUE_OPTIONS, PaymentDueBadge } from "../staff/PaymentDueBadge";
import { formatMoney, paymentStatusLabel, settlementMethodLabel } from "../staff/paymentsApi";
import { PaymentDocuments } from "../payments/PaymentDocuments";
import { MemberRefundControl } from "./MemberRefundRequest";
import { MemberPaymentOffline, type OfflineCollection } from "./MemberPaymentOffline";

// Additive API field until the coordinator regenerates the OpenAPI client.
export type MemberPayment = Omit<GeneratedMemberPayment, "refunded_amount" | "refunds" | "subject_type" | "refund_case" | "refund_requestable"> & {
  subject_type: GeneratedMemberPayment["subject_type"] | "membership_request" | "membership_term_start";
  // Optional so older fixtures and the archived read-only list need not carry them.
  refund_case?: GeneratedMemberPayment["refund_case"]; refund_requestable?: boolean;
  refunded_amount?: string | number; due_at?: string | null; due_date?: string | null; due_state?: string;
  // Lane L5: UPI QR and claim (with billing.offline_claims) and the provider's masked method label.
  offline_collection?: OfflineCollection; method_label?: string;
  refunds: Array<GeneratedMemberPayment["refunds"][number] & {
    method?: string; reference?: string; refunded_at?: string | null;
  }>;
};

// An "I paid" note staff have not decided yet: paying online too would pay the debt twice.
const claimOpen = (payment: MemberPayment) =>
  ["submitted", "awaiting_confirmation"].includes(payment.offline_collection?.claim?.status ?? "");

// A pending donation is an unfinished gift, never a debt (payments audit B-7): neutral, not "Pending".
const unpaidGift = (payment: MemberPayment) => payment.subject_type === "donation" && payment.status === "pending";

// One locale-formatted amount; a row without a currency keeps the bare number.
const money = (amount: string, currency?: string | null) => (currency ? formatMoney(amount, currency) : amount);

export function MemberPaymentRows({
  payments,
  checkoutPaymentId,
  onCheckout,
  makerspaceId,
  refunds = false,
  offlineClaims = refunds,
}: {
  payments: MemberPayment[];
  checkoutPaymentId?: number;
  onCheckout: (paymentId: number) => void;
  makerspaceId?: number;
  /** Offer "Request refund" on paid charges. Off for archived spaces' read-only history. */
  refunds?: boolean;
  /** Show the UPI / "I paid" block. Archived spaces keep it: the server still takes claims there. */
  offlineClaims?: boolean;
}) {
  const [dueFilter, setDueFilter] = useState("");
  return (
    <>
    <label className="grid gap-1 text-xs text-muted sm:max-w-xs"><span>{t`Payment due dates`}</span>
      <select className="desk-input" value={dueFilter} onChange={(event) => setDueFilter(event.target.value)}>
        <option value="">{t`All due dates`}</option>{DUE_OPTIONS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
    </label>
    <ul className="mt-3 space-y-2 text-sm text-muted [&>li>div>:first-child]:basis-48">
      {payments.filter((payment) => !dueFilter || payment.due_state === dueFilter).map((payment) => (
        <li key={payment.id}><ListRow title={payment.subject_label} right={<div className="grid justify-items-end gap-1 text-right"><span className="font-display text-lg tabular-nums text-ink">{money(payment.amount, payment.currency)}</span><StatusPill label={unpaidGift(payment) ? t`Gift not completed` : payment.status ? paymentStatusLabel(payment.status) : t`Unknown`} tone={["paid_online", "paid_offline"].includes(payment.status || "") ? "success" : payment.status === "pending" && !unpaidGift(payment) ? "warn" : "neutral"} /></div>} meta={<>
          {/* Facts wrap as chips on a phone; the one action gets its own full-width line
              below them instead of sitting mid-sentence between separators. */}
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <PaymentDueBadge payment={payment} />
            {/* No rail behind this charge: the space takes it in person. Offering a
                payment link here called an endpoint that could not succeed. */}
            {!payment.checkout_url && payment.status === "pending" && !payment.online_payment_available ? <span>{t`Pay at the space`}</span> : null}
            {payment.settlement ? (
              <span>
                {t`Received ${formatDate(payment.settlement.received_at)} by ${settlementMethodLabel(payment.settlement.method)}`}
              </span>
            ) : null}
            {payment.method_label ? <span>{t`Paid with ${payment.method_label}`}</span> : null}
            {/* Money sent back on this charge. Pending refunds are shown too, so a payer
                who was told a refund is on its way can see it is recorded. */}
            {(payment.refunds ?? []).filter((refund) => refund.status !== "failed").map((refund, index) => (
              <span key={index} className="break-words">
                {refund.status === "succeeded" ? t`Refunded` : t`Refund pending`}{" "}
                <span className="tabular-nums">
                  {money(refund.amount, refund.currency)}
                </span>
                {refund.reason ? ` (${refund.reason})` : null}
                {refund.method ? <> {t`by ${settlementMethodLabel(refund.method)}`}</> : ""}
                {refund.reference ? ` · ${refund.reference}` : ""}
              </span>
            ))}
          </span>
          {payment.checkout_url ? (
            <span className="mt-3 flex"><a className="desk-button-brand w-full sm:w-auto" href={payment.checkout_url}>{t`Pay now`}</a></span>
          ) : payment.status === "pending" && payment.online_payment_available && !claimOpen(payment) ? (
            <span className="mt-3 flex">
              <button
                className="desk-button w-full sm:w-auto"
                disabled={checkoutPaymentId !== undefined}
                onClick={() => onCheckout(payment.id)}
                type="button"
              >
                {t`Generate payment link`}</button>
            </span>
          ) : null}
          {offlineClaims && makerspaceId !== undefined && payment.offline_collection
            ? <MemberPaymentOffline makerspaceId={makerspaceId} paymentId={payment.id} offline={payment.offline_collection} /> : null}
          {refunds && makerspaceId !== undefined ? <MemberRefundControl makerspaceId={makerspaceId} payment={payment} /> : null}
        </>} /></li>
      ))}
    </ul>
    {payments.length > 0 && !payments.some(payment => !dueFilter || payment.due_state === dueFilter) ? <EmptyState message={t`No payments match this due date. Choose another filter.`} /> : null}
    {makerspaceId ? <PaymentDocuments key={makerspaceId} makerspaceId={makerspaceId} audience="member" /> : null}
    </>
  );
}
