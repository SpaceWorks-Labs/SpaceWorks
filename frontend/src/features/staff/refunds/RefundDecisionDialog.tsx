import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { FlowLayout } from "../../../components/layouts";
import { Field, KeyValueCard, SegmentedControl } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { validateRefundAmount } from "../PaymentRefundDialog";
import { RefundReceiptFields, useRefundReceipt } from "../RefundReceiptFields";
import {
  EVENT_TICKET_SUBJECTS, REASON_LABELS, approveRefundCase, caseErrorMessage, declineRefundCase, invalidateRefundViews, type RefundCase,
} from "./refundsApi";
import { PolicySnapshotLine } from "./RefundCaseRow";
import { MembershipRefundExtras } from "./MembershipRefundExtras";

type Mode = "approve" | "decline";

/** The amount staff start from: what the policy owes, else everything still refundable. */
export function suggestedAmount(row: Pick<RefundCase, "due_amount" | "refundable_balance">) {
  // Hand back the server's own string so a KWD fils (12.345) is never rounded to two places.
  const balance = Number(row.refundable_balance);
  const due = Number(row.due_amount);
  return due > 0 && due < balance ? row.due_amount : row.refundable_balance;
}

/** Mount with `key={case.id}` so each case starts from its own suggestion. */
export function RefundDecisionDialog({ makerspaceId, refundCase, onClose, cancelTicketsAvailable = false }: {
  makerspaceId: number; refundCase: RefundCase; onClose: () => void;
  /** The space's `events.refund_cancels_tickets` switch; the tick shows only on an event ticket charge. */
  cancelTicketsAvailable?: boolean;
}) {
  const queryClient = useQueryClient();
  const offline = refundCase.payment.status === "paid_offline";
  const balance = Number(refundCase.refundable_balance);
  const [mode, setMode] = useState<Mode>("approve");
  const [amount, setAmount] = useState(() => suggestedAmount(refundCase));
  const [note, setNote] = useState("");
  const [keepMembership, setKeepMembership] = useState(false);
  const [cancelTickets, setCancelTickets] = useState(false);
  const ticketCharge = cancelTicketsAvailable && EVENT_TICKET_SUBJECTS.has(refundCase.payment.subject_type);
  // A price-difference refund never ends the term (lane L24), so it has no keep-membership choice.
  const membership = refundCase.area === "membership" && refundCase.reason_code !== "price_drop";
  const receipt = useRefundReceipt();
  const [problem, setProblem] = useState<string | null>(null);
  const money = (value: string) => formatMoney(value, refundCase.payment.currency);
  const mutation = useMutation({
    mutationFn: () => mode === "decline"
      ? declineRefundCase(makerspaceId, refundCase.id, note.trim())
      : approveRefundCase(makerspaceId, refundCase.id, {
        amount: amount.trim(), note: note.trim(), ...(offline ? { receipt: receipt.receipt() } : {}),
        ...(membership ? { keep_membership: keepMembership } : {}),
        ...(ticketCharge && cancelTickets ? { cancel_tickets: true } : {}),
      }),
    onSuccess: () => { invalidateRefundViews(queryClient, makerspaceId); onClose(); },
    onError: () => invalidateRefundViews(queryClient, makerspaceId),
  });
  const submit = () => {
    const found = mode === "decline"
      ? (note.trim() ? null : "Tell the member why. They will see this note.")
      : validateRefundAmount(amount, balance) ?? (offline ? receipt.dateProblem() : null);
    setProblem(found);
    if (!found) mutation.mutate();
  };
  const label = mode === "decline" ? "Decline refund"
    : offline ? `Record ${money(amount || "0")} returned` : `Refund ${money(amount || "0")}`;
  const error = problem ?? (mutation.error ? caseErrorMessage(mutation.error) : null);

  return <FlowLayout presentation="dialog" open onCancel={() => { if (!mutation.isPending) onClose(); }}
    state={{ status: "ready" }} title={t`Refund for ${refundCase.payment.member_name || "a member"}`}
    steps={[{ key: "decide", label: t`Decision`, state: "current" }]} current="decide"
    footer={{ next: { label, pending: mutation.isPending, pendingLabel: t`Saving decision…`, onClick: submit,
      disabled: mode === "approve" && balance <= 0 } }}
    work={<div className="grid gap-4">
      <KeyValueCard title={refundCase.payment.subject_label} items={[
        { label: t`Paid`, value: `${money(refundCase.payment.amount)} · ${offline ? "in person" : "online"}` },
        { label: t`Policy says`, value: money(refundCase.due_amount) },
        { label: t`Left to refund`, value: money(refundCase.refundable_balance) },
        { label: t`Why`, value: REASON_LABELS[refundCase.reason_code] },
      ]} />
      <PolicySnapshotLine snapshot={refundCase.policy_snapshot} />
      {refundCase.needs_finance_approval ? <p className="text-sm text-muted">{t`A price difference: only the Space Manager or a finance admin (view finance and record payments) can approve or decline it.`}</p> : null}
      {refundCase.member_reason ? <blockquote className="border-l-2 border-line pl-3 text-sm text-ink">
        “{refundCase.member_reason}”</blockquote> : null}
      <SegmentedControl label={t`Decision`} value={mode} fullWidth onChange={(value) => { setMode(value as Mode); setProblem(null); }}
        options={[{ value: "approve", label: t`Approve` }, { value: "decline", label: t`Decline` }]} />
      {mode === "approve" ? <>
        <Field label={t`Amount to refund`}>
          <input className="desk-input" inputMode="decimal" value={amount}
            onChange={(event) => { setAmount(event.target.value); setProblem(null); }} />
        </Field>
        {membership ? <MembershipRefundExtras makerspaceId={makerspaceId} caseId={refundCase.id}
          keepMembership={keepMembership} onKeepMembership={setKeepMembership} /> : null}
        {ticketCharge ? <div className="grid gap-1">
          <label className="flex min-h-11 items-center gap-2 text-sm">
            <input className="h-4 w-4" type="checkbox" checked={cancelTickets} onChange={(event) => { setCancelTickets(event.target.checked); setProblem(null); }} />
            {t`Also cancel the tickets this payment bought`}</label>
          <p className="text-sm text-muted">{cancelTickets
            ? t`The places are freed and the waitlist moves up. If cancelling fails, the refund still stands and you can cancel the tickets from the event.`
            : t`Unticked, the money goes back and the tickets stay valid.`}</p>
        </div> : null}
        {offline ? <>
          <p className="text-sm text-muted">{t`This charge was paid in person, so the money goes back the same way. Record how it was returned; the receipt is permanent.`}</p>
          <RefundReceiptFields state={receipt} onEdit={() => setProblem(null)} />
        </> : <p className="text-sm text-muted">{t`The refund goes back through the provider that took the payment.`}</p>}
      </> : null}
      <Field label={mode === "decline" ? t`Note to the member` : t`Note to the member (optional)`}>
        <textarea className="desk-input min-h-20" maxLength={500} value={note}
          onChange={(event) => { setNote(event.target.value); setProblem(null); }} />
      </Field>
      {error ? <p className="text-sm text-danger" role="alert">{error}</p> : null}
    </div>}
  />;
}
