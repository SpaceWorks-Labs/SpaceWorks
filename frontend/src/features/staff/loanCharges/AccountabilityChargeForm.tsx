import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { formatMoney } from "../paymentsApi";
import {
  chargeAccountability, chargeErrorMessage, invalidateLoanCharges, suggestionHint,
  type LoanAccountabilityChargeResult, type LoanAccountabilityRow,
} from "./loanChargesApi";

const AMOUNT = /^\d+(\.\d{1,3})?$/;

export function rowTitle(row: Pick<LoanAccountabilityRow, "issue_type" | "quantity" | "item_label">) {
  const what = row.issue_type === "missing" ? "lost" : "damaged";
  return `${row.item_label || "Item"} · ${row.quantity} ${what}`;
}

/**
 * Staff decide one damaged or lost item: the suggested amount, or No charge. An amount above
 * zero needs the return photo that recorded the item, so without one only No charge is offered.
 */
export function AccountabilityChargeForm({ makerspaceId, requestId, currency, row, onDone }: {
  makerspaceId: number; requestId: number; currency: string; row: LoanAccountabilityRow;
  onDone?: (result: LoanAccountabilityChargeResult) => void;
}) {
  const queryClient = useQueryClient();
  const ids = useId();
  const canCharge = row.has_return_photo;
  const [noCharge, setNoCharge] = useState(!canCharge || !(Number(row.suggested_amount) > 0));
  const [amount, setAmount] = useState(row.suggested_amount);
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => chargeAccountability(makerspaceId, requestId, row.id, noCharge ? "0" : amount.trim(), note.trim()),
    onSuccess: (result) => { invalidateLoanCharges(queryClient, makerspaceId, requestId); onDone?.(result); },
    onError: () => invalidateLoanCharges(queryClient, makerspaceId, requestId),
  });
  const save = () => {
    const value = amount.trim();
    const found = noCharge ? null : !AMOUNT.test(value) ? "Enter an amount like 12.50, or choose No charge."
      : Number(value) <= 0 ? "Choose No charge instead of a zero amount." : null;
    setProblem(found);
    if (!found) mutation.mutate();
  };
  const error = problem ?? (mutation.error ? chargeErrorMessage(mutation.error) : null);
  const saveLabel = noCharge ? "Save: no charge" : `Save charge of ${formatMoney(amount.trim() || "0", currency)}`;

  return <form aria-label={rowTitle(row)} className="grid gap-3 rounded-xl border border-line p-4"
    onSubmit={event => { event.preventDefault(); save(); }}>
    <p className="text-sm font-semibold text-ink">{rowTitle(row)}</p>
    <fieldset className="grid gap-3" disabled={mutation.isPending}>
      <legend className="sr-only">{t`Charge for ${rowTitle(row)}`}</legend>
      <label className="grid gap-1" htmlFor={`${ids}-amount`}>
        <span className="text-sm font-semibold text-ink">{t`Amount (${currency.toUpperCase()})`}</span>
        <input id={`${ids}-amount`} className="desk-input" inputMode="decimal" value={noCharge ? "0.00" : amount}
          disabled={noCharge || !canCharge} aria-invalid={Boolean(problem)}
          aria-describedby={problem ? `${ids}-hint ${ids}-error` : `${ids}-hint`}
          onChange={event => { setAmount(event.target.value); setProblem(null); }} />
        <span id={`${ids}-hint`} className="text-xs text-muted">{canCharge ? suggestionHint(row.suggested_source)
          : t`No return photo recorded this item, so it cannot be charged. Save No charge, or decide later.`}</span>
      </label>
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={noCharge} disabled={!canCharge}
          onChange={event => { setNoCharge(event.target.checked); setProblem(null); }} />
        {t`No charge`}</label>
      <label className="grid gap-1" htmlFor={`${ids}-note`}>
        <span className="text-sm font-semibold text-ink">{t`Note for the audit log (optional)`}</span>
        <textarea id={`${ids}-note`} className="desk-input min-h-16" maxLength={300} value={note}
          onChange={event => setNote(event.target.value)} />
      </label>
      {error ? <p id={`${ids}-error`} className="text-sm text-danger" role="alert">{error}</p> : null}
      <button className="desk-button-primary w-full sm:w-fit" type="submit">
        {mutation.isPending ? t`Saving…` : saveLabel}
      </button>
    </fieldset>
  </form>;
}
