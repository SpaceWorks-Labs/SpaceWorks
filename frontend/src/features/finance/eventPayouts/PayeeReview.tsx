import { t } from "@lingui/core/macro";
import { useState } from "react";
import { usePayoutCommand } from "./api";
import { reasonIsValid } from "./format";
import { collectedPayee, permits } from "./types";
import type { FinanceScope, PayoutDetail } from "./types";

export function PayeeReview({ scope, payout }: { scope: FinanceScope; payout: PayoutDetail }) {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [inspected, setInspected] = useState(false);
  const verify = usePayoutCommand(scope, payout.id, "payee/verify");
  const correction = usePayoutCommand(scope, payout.id, "payee/request-correction");
  const payee = collectedPayee(payout.payee);
  if (!payee || (!permits(payout, "verify_payee") && !permits(payout, "request_payee_correction"))) return null;
  const payload = { expected_version: payout.version, payee_revision_id: payee.id, expected_payee_version: payee.version };
  const pending = verify.isPending || correction.isPending;
  return <section className="grid gap-3 rounded-2xl border border-line p-4" aria-label={t`Review payee routing`}>
    <h2 className="font-semibold">{t`Review payee routing`}</h2>
    <p>{t`Only the owner can change routing details. A correction request pauses readiness until a new revision is submitted and verified.`}</p>
    <label className="grid gap-1">{t`Payee review reason code`}<input className="desk-input" value={reason} onChange={event => setReason(event.target.value)} /></label>
    <label className="grid gap-1">{t`Correction explanation`}<textarea className="desk-input" maxLength={5000} value={note} onChange={event => setNote(event.target.value)} /></label>
    {permits(payout, "verify_payee") ? <><label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={inspected} onChange={event => setInspected(event.target.checked)} />{t`I inspected this payee revision and confirmed its routing.`}</label>
      <button type="button" className="desk-button min-h-11" disabled={!inspected || pending || (payee.method === "other" && !reasonIsValid(reason))}
        onClick={() => verify.mutate({ ...payload, ...(reasonIsValid(reason) ? { reason_code: reason } : {}) })}>{t`Verify inspected routing`}</button></> : null}
    {permits(payout, "request_payee_correction") ? <button type="button" className="desk-button min-h-11" disabled={pending || !reasonIsValid(reason) || !note.trim()}
      onClick={() => correction.mutate({ ...payload, reason_code: reason, note })}>{t`Request owner correction`}</button> : null}
    {verify.error || correction.error ? <p role="alert">{t`Payee review failed. Reload the current revision and confirm recent authentication.`}</p> : null}
    {verify.isSuccess || correction.isSuccess ? <p role="status">{t`Payee review recorded.`}</p> : null}
  </section>;
}
