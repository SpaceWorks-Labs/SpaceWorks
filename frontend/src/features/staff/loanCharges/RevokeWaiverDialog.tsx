import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../../../components/ui";
import { chargeErrorMessage, invalidateLoanCharges, revokeLoanWaiver, type LoanFeeWaiver } from "./loanChargesApi";

/** Revoking is a new append-only row: it changes only charges raised from now on. */
export function RevokeWaiverDialog({ makerspaceId, requestId, waiver, onClose }: {
  makerspaceId: number; requestId: number; waiver: LoanFeeWaiver; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const errorId = useId();
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => revokeLoanWaiver(makerspaceId, requestId, waiver.id, reason.trim()),
    onSuccess: () => { invalidateLoanCharges(queryClient, makerspaceId, requestId); onClose(); },
    onError: () => invalidateLoanCharges(queryClient, makerspaceId, requestId),
  });
  const close = () => { if (!mutation.isPending) onClose(); };
  const submit = () => {
    const found = reason.trim() ? null : "Give a reason. It is kept with the revocation for the audit trail.";
    setProblem(found);
    if (!found) mutation.mutate();
  };
  const error = problem ?? (mutation.error ? chargeErrorMessage(mutation.error) : null);
  return <Modal open onClose={close} title="Revoke fee waiver"
    footer={<div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button className="desk-button w-full sm:w-auto" type="button" disabled={mutation.isPending} onClick={close}>Keep waiver</button>
      <button className="desk-button-danger w-full sm:w-auto" type="button" disabled={mutation.isPending} onClick={submit}>
        {mutation.isPending ? "Revoking…" : "Revoke waiver"}</button>
    </div>}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">Revoking affects only charges not raised yet. Nothing already waived or
        sent to a refund case is reopened.</p>
      <label className="grid gap-1">
        <span className="text-sm font-semibold text-ink">Reason (required)</span>
        <textarea className="desk-input min-h-20" maxLength={500} value={reason} disabled={mutation.isPending}
          aria-required="true" aria-invalid={Boolean(problem)} aria-describedby={error ? errorId : undefined} onChange={event => { setReason(event.target.value); setProblem(null); }} />
      </label>
      {error ? <p id={errorId} className="text-sm text-danger" role="alert">{error}</p> : null}
    </div>
  </Modal>;
}
