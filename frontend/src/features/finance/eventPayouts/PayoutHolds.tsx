import { t } from "@lingui/core/macro";
import { holdKindLabel, payoutEligibilityLabel, reasonCodeText } from "./labels";
import { useState } from "react";
import { usePayoutCommand } from "./api";
import { reasonIsValid, utcInstant } from "./format";
import { permits } from "./types";
import { EvidenceDetails } from "./DecisionHistory";
import type { FinanceScope, Hold, PayoutDetail } from "./types";

function HoldForm({ scope, payout, hold }: { scope: FinanceScope; payout: PayoutDetail; hold?: Hold }) {
  const [kind, setKind] = useState<Hold["kind"]>(hold?.kind ?? "eligibility");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [until, setUntil] = useState("");
  const [evidence, setEvidence] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const mutation = usePayoutCommand(scope, payout.id, hold ? "release-hold" : "hold");
  const references = evidence.trim() ? evidence.split(",").map(value => Number(value.trim())) : [];
  const valid = reasonIsValid(reason) && confirmed && references.length <= 100
    && references.every(id => Number.isSafeInteger(id) && id > 0) && (!until || Boolean(utcInstant(until)));
  const authorized = hold ? permits(payout, "release_hold") && permits(hold, "release_hold") : permits(payout, "hold");
  if (!authorized) return null;
  return <form className="grid gap-3 rounded-2xl border border-line p-4" aria-label={hold ? t`Release hold ${hold.id}` : t`Place finance hold`}
    onSubmit={event => { event.preventDefault(); if (!valid || mutation.isPending) return;
      mutation.mutate({ expected_version: payout.version, eligibility_revision: payout.eligibility_revision,
        kind, reason_code: reason, note, evidence_refs: references, hold_until: until ? utcInstant(until) : null,
        ...(hold ? { hold_id: hold.id } : {}) }); }}>
    <h3 className="font-semibold">{hold ? (hold.kind === "retention" ? t`Release retention hold` : t`Release eligibility hold`) : t`Place finance hold`}</h3>
    {hold ? <p>{hold.note ? t`Reason: ${reasonCodeText(hold.reason_code)} · ${hold.note}` : t`Reason: ${reasonCodeText(hold.reason_code)}`}</p>
      : <label className="grid gap-1">{t`Hold kind`}<select className="desk-input" value={kind} onChange={event => setKind(event.target.value as Hold["kind"])}>
        <option value="eligibility">{t`Pause new payouts`}</option><option value="retention">{t`Retain finance evidence`}</option></select></label>}
    <p className="text-sm text-muted">{t`Eligibility holds pause new payouts. Retention holds preserve documents. Releasing a hold does not change the approved amount.`}</p>
    <label className="grid gap-1">{t`Hold reason code`}<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label>
    <label className="grid gap-1">{t`Finance explanation`}<textarea className="desk-input" maxLength={5000} value={note} onChange={event => setNote(event.target.value)} /></label>
    <label className="grid gap-1">{t`Evidence IDs (comma separated)`}<input className="desk-input" value={evidence} onChange={event => setEvidence(event.target.value)} /></label>
    {!hold ? <label className="grid gap-1">{t`Review at (UTC, optional)`}<input className="desk-input" type="datetime-local" value={until} onChange={event => setUntil(event.target.value)} /></label> : null}
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{hold ? t`I confirm this finance release.` : t`I confirm this finance hold.`}</label>
    <button className="desk-button min-h-11" disabled={!valid || mutation.isPending} type="submit">{hold ? t`Release hold` : t`Place hold`}</button>
    {mutation.error ? <p role="alert">{t`The hold change failed. Reload current eligibility and confirm recent authentication.`}</p> : null}
    {mutation.isSuccess ? <p role="status">{t`The hold change was recorded.`}</p> : null}
  </form>;
}

function Acknowledgement({ scope, payout }: { scope: FinanceScope; payout: PayoutDetail }) {
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const mutation = usePayoutCommand(scope, payout.id, "acknowledge-eligibility");
  if (!permits(payout, "acknowledge_eligibility")) return null;
  return <form className="grid gap-3 rounded-2xl border border-line p-4" aria-label={t`Acknowledge eligibility correction`}
    onSubmit={event => { event.preventDefault(); if (!payout.eligibility_evidence || !confirmed || !reasonIsValid(reason) || mutation.isPending) return;
      mutation.mutate({ expected_version: payout.version, eligibility_revision: payout.eligibility_revision, reason_code: reason }); }}>
    <h3 className="font-semibold">{t`Acknowledge corrected eligibility`}</h3><p>{t`Review the latest attendance and project evidence before acknowledging revision ${payout.eligibility_revision}. This does not release a hold or record a payment.`}</p>
    <label className="grid gap-1">{t`Acknowledgement reason code`}<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t`I reviewed the corrected evidence.`}</label>
    <button className="desk-button min-h-11" type="submit" disabled={!payout.eligibility_evidence || !confirmed || !reasonIsValid(reason) || mutation.isPending}>{t`Acknowledge eligibility`}</button>
    {mutation.error ? <p role="alert">{t`Acknowledgement failed. Reload the latest evidence revision.`}</p> : null}
    {mutation.isSuccess ? <p role="status">{t`Acknowledgement recorded.`}</p> : null}
  </form>;
}

export function PayoutHolds({ scope, payout }: { scope: FinanceScope; payout: PayoutDetail }) {
  return <section aria-label={t`Eligibility and retention`} className="grid gap-4">
    <h2 className="font-semibold">{t`Eligibility and retention`}</h2>
    <p>{t`Eligibility: ${payoutEligibilityLabel(payout.eligibility_status)} · evidence revision ${payout.eligibility_revision}`}</p>
    {payout.eligibility_evidence ? <details className="rounded-2xl border border-line p-4"><summary className="min-h-11 cursor-pointer font-semibold">{t`Current eligibility evidence`}</summary>
      <EvidenceDetails value={payout.eligibility_evidence} /></details> : <p className="text-sm text-muted">{t`Current evidence is unavailable. Reload before acknowledging eligibility.`}</p>}
    {payout.holds?.map(hold => <div key={hold.id} className="grid gap-2">
      <p>{t`${holdKindLabel(hold.kind)} · ${reasonCodeText(hold.reason_code)}`}{hold.hold_until ? t` · review ${hold.hold_until}` : ""}</p>
      <HoldForm scope={scope} payout={payout} hold={hold} />
    </div>)}
    <Acknowledgement scope={scope} payout={payout} />
    <HoldForm scope={scope} payout={payout} />
  </section>;
}
