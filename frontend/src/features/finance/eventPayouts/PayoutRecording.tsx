import { useState } from "react";
import { usePayoutCommand } from "./api";
import type { FinanceScope, PayoutDetail, PayoutEntry } from "./types";

export function PayoutRecording({ scope, payout, amends }: { scope: FinanceScope; payout: PayoutDetail; amends?: PayoutEntry }) {
  const [amount, setAmount] = useState(amends ? String(amends.amount_minor) : "");
  const [method, setMethod] = useState(amends?.method ?? payout.payee?.method ?? "cash");
  const [reference, setReference] = useState(amends?.reference ?? "");
  const [paidAt, setPaidAt] = useState(amends ? new Date(amends.paid_at).toISOString().slice(0, 16) : "");
  const [reason, setReason] = useState("");
  const [isVoid, setIsVoid] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const mutation = usePayoutCommand(scope, payout.id, amends ? `entries/${amends.id}/amend` : "record");
  const minor = Number(amount);
  const validAmount = Boolean(isVoid && amends) || Number.isSafeInteger(minor) && minor > 0;
  const valid = validAmount && reference.trim() && paidAt && confirmed
    && (!(amends || method === "other") || /^[a-z][a-z0-9_]{0,63}$/.test(reason));
  return <section className="grid gap-3 rounded-2xl border border-line bg-panel p-5" aria-label={amends ? "Amend payout record" : "Record payout"}>
    <h2 className="font-semibold">{amends ? "Correct a recording error" : "Record a completed payout"}</h2>
    <p className="text-sm text-muted">Record the payment you already made. Space Works does not send money.</p>
    <label className="grid gap-1">Amount in {payout.currency} minor units<input className="desk-input" inputMode="numeric" pattern="[0-9]+" value={amount} onChange={event => setAmount(event.target.value)} /></label>
    <label className="grid gap-1">Method<select className="desk-input" value={method} onChange={event => setMethod(event.target.value)}>{["cash", "upi", "bank_transfer", "cheque", "other", "paypal", "wise"].map(value => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}</select></label>
    <label className="grid gap-1">Payment reference<input className="desk-input" maxLength={64} value={reference} onChange={event => setReference(event.target.value)} /></label>
    <label className="grid gap-1">Paid at (UTC)<input className="desk-input" type="datetime-local" value={paidAt} onChange={event => setPaidAt(event.target.value)} /></label>
    {method === "other" && !amends ? <label className="grid gap-1">Finance reason code<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label> : null}
    {amends ? <><label className="grid gap-1">Correction reason code<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label>
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={isVoid} onChange={event => setIsVoid(event.target.checked)} />Void an erroneous record (does not return money)</label></> : null}
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm this records a payment or corrects its history.</label>
    <button className="desk-button min-h-11" type="button" disabled={!valid || mutation.isPending} onClick={() => mutation.mutate({
      expected_version: payout.version, amount_minor: isVoid ? 0 : minor, currency: payout.currency, method, reference,
      paid_at: `${paidAt}:00Z`, payee_revision: amends ? amends.payee_revision_id : payout.payee.id,
      expected_payee_version: payout.payee?.version ?? 1, eligibility_revision: payout.eligibility_revision,
      ...(amends ? { reason_code: reason, is_void: isVoid } : method === "other" ? { reason_code: reason } : {}),
    })}>{mutation.isPending ? "Saving…" : amends ? "Append correction" : "Record completed payout"}</button>
    {mutation.error ? <p role="alert">This record was not saved. Refresh the obligation and verify your finance access and recent authentication.</p> : null}
    {mutation.isSuccess ? <p role="status">The payout history was saved.</p> : null}
  </section>;
}
