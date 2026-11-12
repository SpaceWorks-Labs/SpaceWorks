import { t } from "@lingui/core/macro";
import { decimalToMinor, minorToDecimal, paymentMethodLabel } from "../../../lib/money";
import { useState } from "react";
import { usePayoutCommand } from "./api";
import { money, reasonIsValid, utcInstant } from "./format";
import { collectedPayee, permits } from "./types";
import type { FinanceScope, PayoutDetail, PayoutEntry } from "./types";
import { BoxArt } from "../../../components/BoxSpinner";

export function PayoutRecording({ scope, payout, amends }: { scope: FinanceScope; payout: PayoutDetail; amends?: PayoutEntry }) {
  const payee = collectedPayee(payout.payee);
  const [amount, setAmount] = useState(amends ? minorToDecimal(amends.amount_minor, payout.currency) : "");
  const [method, setMethod] = useState(amends?.method ?? payee?.method ?? "cash");
  const [reference, setReference] = useState(amends?.reference ?? "");
  const [paidAt, setPaidAt] = useState(amends ? new Date(amends.paid_at).toISOString().replace(/Z$/, "") : "");
  const [paidAtEdited, setPaidAtEdited] = useState(false);
  const [reason, setReason] = useState("");
  const [isVoid, setIsVoid] = useState(amends?.is_void ?? false);
  const [confirmed, setConfirmed] = useState(false);
  const mutation = usePayoutCommand(scope, payout.id, amends ? `entries/${encodeURIComponent(amends.id)}/amend` : "record");
  const minor = decimalToMinor(amount, payout.currency) ?? Number.NaN;
  // A metadata-only correction preserves server timestamp precision, including microseconds.
  const instant = amends && !paidAtEdited ? amends.paid_at : utcInstant(paidAt);
  const maximum = payout.remaining_minor + (amends && !amends.is_void ? amends.amount_minor : 0);
  const validAmount = Boolean(isVoid && amends) || Number.isSafeInteger(minor) && minor > 0 && minor <= maximum;
  const authorized = amends ? permits(payout, "amend") && permits(amends, "amend") : permits(payout, "record");
  const valid = authorized && validAmount && reference.trim() && instant && Date.parse(instant) <= Date.now() && confirmed
    && (!(amends || method === "other") || reasonIsValid(reason));
  if (!authorized || !amends && !payee) return null;
  return <form className="grid gap-3 rounded-2xl border border-line bg-panel p-5" aria-label={amends ? t`Amend payout record` : t`Record payout`}
    onSubmit={event => { event.preventDefault(); if (!valid || !instant || mutation.isPending) return;
      mutation.mutate({ expected_version: payout.version, amount_minor: isVoid ? 0 : minor, currency: payout.currency,
        method, reference: reference.trim(), paid_at: instant,
        payee_revision: amends ? amends.payee_revision_id : payee!.id,
        expected_payee_version: payee?.version ?? 1, eligibility_revision: payout.eligibility_revision,
        ...(amends ? { reason_code: reason, is_void: isVoid } : method === "other" ? { reason_code: reason } : {}),
      }); }}>
    <h2 className="font-semibold">{amends ? t`Correct a recording error` : t`Record a completed payout`}</h2>
    <p className="text-sm text-muted">{t`Record the payment you already made. Space Works does not send money. Use a non-sensitive receipt reference, never bank details.`}</p>
    <p>{t`Maximum for this record: ${money(maximum, payout.currency)}`}</p>
    <label className="grid gap-1">{t`Amount (${payout.currency})`}<input className="desk-input" inputMode="decimal" placeholder={minorToDecimal(0, payout.currency)} disabled={isVoid} value={amount} onChange={event => { setAmount(event.target.value); setConfirmed(false); }} /></label>
    <label className="grid gap-1">{t`Method`}<select className="desk-input" value={method} onChange={event => { setMethod(event.target.value); setConfirmed(false); }}>{["cash", "upi", "bank_transfer", "cheque", "other", "paypal", "wise"].map(value => <option key={value} value={value}>{paymentMethodLabel(value)}</option>)}</select></label>
    <label className="grid gap-1">{t`Payment reference`}<input className="desk-input" maxLength={64} value={reference} onChange={event => { setReference(event.target.value); setConfirmed(false); }} /></label>
    <label className="grid gap-1">{t`Paid at (UTC)`}<input className="desk-input" type="datetime-local" step="0.001" value={paidAt} onChange={event => { setPaidAt(event.target.value); setPaidAtEdited(true); setConfirmed(false); }} /></label>
    {method === "other" || amends ? <label className="grid gap-1">{amends ? t`Correction reason code` : t`Finance reason code`}<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label> : null}
    {amends ? <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={isVoid} onChange={event => { setIsVoid(event.target.checked); setConfirmed(false); }} />{t`Void an erroneous record (does not return money)`}</label> : null}
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t`I confirm this records a payment or corrects its history.`}</label>
    <button className="desk-button min-h-11" type="submit" disabled={!valid || mutation.isPending}>{mutation.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : amends ? t`Append correction` : t`Record completed payout`}</button>
    {mutation.error ? <p role="alert">{t`This record was not saved. Reload current versions and confirm your recent finance authentication.`}</p> : null}
    {mutation.isSuccess ? <p role="status">{t`The payout history was saved.`}</p> : null}
  </form>;
}
