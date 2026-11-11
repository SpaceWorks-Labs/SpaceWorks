import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Field, Modal, StatusPill } from "../../components/ui";
import type { MemberRefundCase } from "../../generated/api";
import { StructuredApiError, memberRequest } from "../../lib/api";
import { formatMoney } from "../../lib/money";

type Payment = { id: number; refund_case?: MemberRefundCase | null; refund_requestable?: boolean };

// A function, not a module constant: `t` must run after the locale is active.
const chip = (status: MemberRefundCase["status"]): [string, "warn" | "success" | "danger" | "neutral"] => ({
  open: [t`Refund under review`, "warn"], approval_failed: [t`Refund under review`, "warn"],
  approved: [t`Refund approved`, "success"], declined: [t`Refund declined`, "danger"],
  withdrawn: [t`Request withdrawn`, "neutral"], void: [t`Refund closed`, "neutral"],
} as const)[status] as [string, "warn" | "success" | "danger" | "neutral"];

type Suggestion = { applies: boolean; suggested_amount: string | null; currency: string; band: string };

/** X20: what the space's membership refund policy suggests if cancelled now. Only an estimate. */
function RefundSuggestion({ makerspaceId, paymentId }: { makerspaceId: number; paymentId: number }) {
  const suggestion = useQuery({ queryKey: ["member", "refund-suggestion", makerspaceId, paymentId],
    queryFn: () => memberRequest<Suggestion>(`/member/makerspaces/${makerspaceId}/payments/${paymentId}/refund-suggestion`), retry: false });
  if (!suggestion.data?.applies || suggestion.data.suggested_amount == null) return null;
  return <p className="text-sm text-ink" role="status">{t`The space's refund policy suggests about${" "}`}
    <strong>{formatMoney(suggestion.data.suggested_amount, suggestion.data.currency)}</strong> {t` if you cancel today. Staff decide the final amount.`}</p>;
}

function errorText(error: unknown) {
  if (error instanceof StructuredApiError && error.code === "refund_request_exists") {
    return t`You already asked for a refund on this charge. Staff will reply here.`;
  }
  return error instanceof Error ? error.message : t`That did not work. Try again.`;
}

/** Where a refund stands, plus the one action the member can take on it. */
export function MemberRefundControl({ makerspaceId, payment }: { makerspaceId: number; payment: Payment }) {
  const queryClient = useQueryClient();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["member"] });
  const request = useMutation({
    mutationFn: () => memberRequest<MemberRefundCase>(`/member/makerspaces/${makerspaceId}/payments/${payment.id}/refund-request`, {
      method: "POST", body: JSON.stringify({ reason: reason.trim() }),
    }),
    onSuccess: () => { setAsking(false); setReason(""); void refresh(); },
  });
  const withdraw = useMutation({
    mutationFn: (caseId: number) => memberRequest<MemberRefundCase>(`/member/makerspaces/${makerspaceId}/refund-requests/${caseId}/withdraw`, {
      method: "POST", body: "{}",
    }),
    onSuccess: () => { void refresh(); },
  });
  const current = payment.refund_case;
  const [label, tone] = current ? chip(current.status) : ["", "neutral" as const];
  if (!current && !payment.refund_requestable) return null;
  return <span className="mt-3 grid gap-2">
    {current ? <span className="flex flex-wrap items-center gap-2">
      <StatusPill label={label} tone={tone} />
      {current.decision_note ? <span className="text-ink">“{current.decision_note}”</span> : null}
      {current.withdrawable ? <button className="desk-button" type="button" disabled={withdraw.isPending}
        onClick={() => withdraw.mutate(current.id)}>{t`Withdraw request`}</button> : null}
    </span> : null}
    {payment.refund_requestable ? <span className="flex">
      <button className="desk-button w-full sm:w-auto" type="button" onClick={() => setAsking(true)}>{t`Request refund`}</button>
    </span> : null}
    {withdraw.error ? <span className="text-danger" role="alert">{errorText(withdraw.error)}</span> : null}
    <Modal open={asking} onClose={() => { if (!request.isPending) setAsking(false); }} title={t`Request a refund`}
      footer={<div className="flex flex-wrap justify-end gap-2">
        <button className="desk-button" type="button" onClick={() => setAsking(false)} disabled={request.isPending}>{t`Cancel`}</button>
        <button className="desk-button-brand" type="button" disabled={request.isPending || !reason.trim()}
          onClick={() => request.mutate()}>{request.isPending ? t`Sending…` : t`Send request`}</button>
      </div>}>
      <div className="grid gap-3">
        <p className="text-sm text-muted">{t`Staff review every request. Nothing is refunded until they approve it, and you will see their answer here.`}</p>
        {asking ? <RefundSuggestion makerspaceId={makerspaceId} paymentId={payment.id} /> : null}
        <Field label={t`Why are you asking?`}>
          <textarea className="desk-input min-h-24" maxLength={500} value={reason}
            onChange={(event) => setReason(event.target.value)} />
        </Field>
        {request.error ? <p className="text-sm text-danger" role="alert">{errorText(request.error)}</p> : null}
      </div>
    </Modal>
  </span>;
}
