import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { Field, Modal } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { currencyExponent, decimalToMinor, formatMoney } from "../../lib/money";
import { collectionApi, type CashHandoverResult } from "./collectionApi";
import { localToday } from "./collectionSheetRows";
import { BoxArt } from "../../components/BoxSpinner";

export type Holder = { collector_id: number; collector: string; currency: string; cash_in_hand: string };

function handoverError(error: unknown) {
  if (error instanceof StructuredApiError) {
    if (error.code === "collector_invalid") return t`This person no longer records payments in this space, so a hand-over can't be recorded for them.`;
    if (error.status === 404) return t`Hand-overs need the collection sheet switched on for this space.`;
    return error.detail || error.message;
  }
  return t`Something went wrong. Try again.`;
}

/** Parity O-B3: cash a collector passed to the treasurer or the bank. A ledger transfer, never spending. */
export function CashHandoverDialog({ makerspaceId, holder, onClose, onDone }: {
  makerspaceId: number; holder: Holder; onClose: () => void; onDone: (result: CashHandoverResult) => void;
}) {
  const today = localToday();
  const held = Number(holder.cash_in_hand);
  const [amount, setAmount] = useState(held > 0 ? held.toFixed(currencyExponent(holder.currency)) : "");
  const [date, setDate] = useState(today);
  const [note, setNote] = useState("");
  const minor = decimalToMinor(amount, holder.currency);
  const amountError = amount.trim() && (minor === null || minor <= 0)
    ? t`Enter an amount above zero with at most ${currencyExponent(holder.currency)} decimals.` : undefined;
  const dateError = date > today ? t`A hand-over can't be dated in the future.` : undefined;
  const save = useMutation({
    mutationFn: () => collectionApi.handover(makerspaceId, { collector_id: holder.collector_id, amount: amount.trim(),
      currency: holder.currency, entry_date: date || undefined, note: note.trim() }),
    onSuccess: onDone,
  });
  const ready = Boolean(minor && minor > 0 && !dateError && date);
  return <Modal open onClose={() => { if (!save.isPending) onClose(); }} title={t`Cash handed over by ${holder.collector}`}>
    <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); if (ready) save.mutate(); }}>
      <p className="text-sm text-muted">{t`On record they hold ${formatMoney(holder.cash_in_hand, holder.currency)}. The hand-over is kept in the finance ledger as a transfer, not as spending, and lowers their cash in hand.`}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Amount (${holder.currency.toUpperCase()})`} error={amountError}
          hint={minor && Number(amount) > held ? t`More than they hold on record; their figure will go below zero.` : undefined}>
          <input className="desk-input tabular-nums" inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} />
        </Field>
        <Field label={t`Handed over on`} error={dateError}>
          <input type="date" className="desk-input" max={today} value={date} onChange={(event) => setDate(event.target.value)} />
        </Field>
      </div>
      <Field label={t`Note (optional)`} hint={t`For example who received it, or the bank deposit slip number.`}>
        <input className="desk-input" maxLength={200} value={note} onChange={(event) => setNote(event.target.value)} />
      </Field>
      {save.error ? <p role="alert" className="text-sm text-danger">{handoverError(save.error)}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" className="desk-button-ghost" disabled={save.isPending} onClick={onClose}>{t`Cancel`}</button>
        <button type="submit" className="desk-button-primary" disabled={!ready || save.isPending}>
          {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Record hand-over`}</button>
      </div>
    </form>
  </Modal>;
}
