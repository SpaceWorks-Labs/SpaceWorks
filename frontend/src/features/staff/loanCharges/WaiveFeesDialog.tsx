import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Modal } from "../../../components/ui";
import {
  WAIVER_COMPONENTS, chargeErrorMessage, invalidateLoanCharges, waiveLoanFees,
  type LoanCharge, type LoanFeeWaiverResult, type WaiverComponent,
} from "./loanChargesApi";

export const WAIVE_SUMMARY = "Pending charges become waived. Paid charges are not reversed: each opens a refund "
  + "case for staff approval. The refundable deposit is never waived.";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** What the chosen fees touch today, so staff see the effect before they confirm. */
export function waiverPreview(charges: LoanCharge[], chosen: WaiverComponent[]) {
  const subjects = new Set(WAIVER_COMPONENTS.filter(([key]) => chosen.includes(key)).map(([, , subject]) => subject));
  const hit = charges.filter(charge => subjects.has(charge.subject_type));
  return {
    pending: hit.filter(charge => charge.status === "pending").length,
    paid: hit.filter(charge => charge.status === "paid_online" || charge.status === "paid_offline").length,
  };
}

export function WaiveFeesDialog({ makerspaceId, requestId, charges, onClose }: {
  makerspaceId: number; requestId: number; charges: LoanCharge[]; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const countId = useId();
  const errorId = useId();
  const [chosen, setChosen] = useState<WaiverComponent[]>(WAIVER_COMPONENTS.map(([key]) => key));
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [result, setResult] = useState<LoanFeeWaiverResult | null>(null);
  const mutation = useMutation({
    // Every fee chosen is sent as "all loan fees", which also covers fees raised later.
    mutationFn: () => waiveLoanFees(makerspaceId, requestId,
      chosen.length === WAIVER_COMPONENTS.length ? [] : chosen, reason.trim()),
    onSuccess: (data) => { setResult(data); invalidateLoanCharges(queryClient, makerspaceId, requestId); },
    onError: () => invalidateLoanCharges(queryClient, makerspaceId, requestId),
  });
  const close = () => { if (!mutation.isPending) onClose(); };
  const toggle = (key: WaiverComponent, on: boolean) => {
    setChosen(current => on ? [...current, key] : current.filter(value => value !== key));
    setProblem(null);
  };
  const submit = () => {
    const found = !chosen.length ? "Choose at least one fee to waive."
      : !reason.trim() ? "Give a reason. It is kept with the waiver for the audit trail." : null;
    setProblem(found);
    if (!found) mutation.mutate();
  };
  const preview = waiverPreview(charges, chosen);
  const error = problem ?? (mutation.error ? chargeErrorMessage(mutation.error) : null);

  if (result) {
    return <Modal key="result" open onClose={onClose} title="Fees waived"
      footer={<div className="flex justify-end"><button className="desk-button-primary w-full sm:w-auto" type="button" onClick={onClose}>Done</button></div>}>
      <div className="grid gap-2 text-sm text-ink" role="status">
        <p>{plural(result.waived_payment_ids.length, "pending charge waived", "pending charges waived")}.</p>
        <p>{plural(result.refund_case_ids.length, "refund case opened", "refund cases opened")}
          {result.refund_case_ids.length ? " for staff approval in Refunds. No money has moved yet." : "."}</p>
        <p className="text-muted">Fees of these kinds raised later on this loan come to zero.</p>
      </div>
    </Modal>;
  }

  return <Modal key="form" open onClose={close} title="Waive loan fees"
    footer={<div className="desk-actions flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <button className="desk-button w-full sm:w-auto" type="button" disabled={mutation.isPending} onClick={close}>Cancel</button>
      <button className="desk-button-primary w-full sm:w-auto" type="button" disabled={mutation.isPending} onClick={submit}>
        {mutation.isPending ? "Waiving…" : "Waive fees"}</button>
    </div>}>
    <div className="grid gap-4">
      <fieldset className="grid gap-1" disabled={mutation.isPending}>
        <legend className="mb-1 text-sm font-semibold text-ink">Fees to waive</legend>
        {WAIVER_COMPONENTS.map(([key, label]) => <label key={key} className="flex min-h-11 items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={chosen.includes(key)} onChange={event => toggle(key, event.target.checked)} />{label}
        </label>)}
      </fieldset>
      <label className="grid gap-1">
        <span className="text-sm font-semibold text-ink">Reason (required)</span>
        <textarea className="desk-input min-h-20" maxLength={500} value={reason} disabled={mutation.isPending}
          aria-required="true" aria-invalid={Boolean(problem) && Boolean(chosen.length)}
          aria-describedby={error ? `${countId} ${errorId}` : countId} onChange={event => { setReason(event.target.value); setProblem(null); }} />
        <span id={countId} className="text-xs text-muted">{reason.length} / 500</span>
      </label>
      <div className="grid gap-1 rounded-xl border border-line p-4 text-sm">
        <p className="font-semibold text-ink">Before you confirm</p>
        <p className="text-muted">{WAIVE_SUMMARY}</p>
        <p className="text-ink" aria-live="polite">On this loan now: {plural(preview.pending, "pending charge", "pending charges")} to waive,
          {" "}{plural(preview.paid, "paid charge", "paid charges")} to send to a refund case.</p>
      </div>
      {error ? <p id={errorId} className="text-sm text-danger" role="alert">{error}</p> : null}
    </div>
  </Modal>;
}
