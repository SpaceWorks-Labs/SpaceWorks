import { t } from "@lingui/core/macro";
import { useCallback, useEffect, useState } from "react";
import { DetailLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { useUnsavedChanges } from "../../events/stagedForms/UnsavedChanges";
import { reimbursementAdminPath, useClaimReview, useClaimReviewCommand } from "./api";
import { ClaimDecision } from "./ClaimDecision";
import { ClaimFinanceAction } from "./ClaimFinanceAction";
import type { ClaimReviewDetail } from "./types";

export function ClaimReview({ scope, claimId, onReceipt, onDirtyChange }: { scope: EventScope; claimId: number;
  onReceipt: (assetId: number) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useClaimReview(scope, claimId);
  const [action, setAction] = useState<"extend" | "attendance-attestations" | "receipt-allocation-overrides" | null>(null);
  const [dirtySections, setDirtySections] = useState({ recommendation: false, decision: false, correction: false });
  const recommendationDirty = useCallback((dirty: boolean) => setDirtySections(current => current.recommendation === dirty ? current : { ...current, recommendation: dirty }), []);
  const decisionDirty = useCallback((dirty: boolean) => setDirtySections(current => current.decision === dirty ? current : { ...current, decision: dirty }), []);
  const correctionDirty = useCallback((dirty: boolean) => setDirtySections(current => current.correction === dirty ? current : { ...current, correction: dirty }), []);
  useEffect(() => { onDirtyChange?.(Object.values(dirtySections).some(Boolean)); }, [dirtySections, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  const row = query.data;
  return <DetailLayout title={t`Claim review`} state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "This claim is unavailable for your access.", onRetry: () => void query.refetch() }}
    main={row ? <div className="grid gap-5"><section className="grid gap-3 rounded-2xl border border-line bg-panel p-5"><h2 className="title-section">{row.owner_label}</h2>
      <p>{t`${row.state.replace(/_/g, " ")} · ${row.claimed_minor} minor units (${row.currency}) · Accepted cap ${row.accepted_cap_minor}`}</p>
      <ul className="list-disc pl-5">{row.eligibility_facts.map(fact => <li key={fact}>{fact}</li>)}</ul>
      {row.decision_reason ? <p>{t`Decision: ${row.decision_reason}`}</p> : null}{row.appeal_statement ? <p>{t`Appeal: ${row.appeal_statement}`}</p> : null}
      {row.recommendations.length ? <section aria-label={t`Previous recommendations`}><h3 className="font-semibold">{t`Previous screening`}</h3><ul className="grid gap-2">{row.recommendations.map((review, index) => <li key={index}>{review.recommendation} · {review.reason_code}<p>{review.note}</p></li>)}</ul></section> : null}
      <ul className="grid gap-3">{row.lines.map(line => <li className="rounded-xl border border-line p-3" key={line.line_uuid}>
        <p>{t`${line.category} · ${line.original_amount_minor} minor units (${line.original_currency}) · Converted ${line.converted_minor} (${row.currency})`}</p>
        <p>{t`Receipt ${line.receipt_present ? "present" : "missing"}`}{line.duplicate_receipt ? t` · Duplicate allocation needs finance review` : ""}</p>
        {line.vendor ? <p>{line.vendor} · {line.expense_date} · {line.description}</p> : null}
        {row.allowed_actions.includes("receipt_read") ? <button type="button" className="desk-button" onClick={() => onReceipt(line.receipt_asset_id)}>{t`Open receipt in finance viewer`}</button> : null}</li>)}</ul>
    </section>
      {row.allowed_actions.includes("claim_recommend") ? <Recommendation key={`${row.id}:${row.version}`} scope={scope} row={row} onDirtyChange={recommendationDirty} /> : null}
      {row.allowed_actions.includes("claim_decide") ? <ClaimDecision key={`decision:${row.version}`} scope={scope} row={row} onDirtyChange={decisionDirty} /> : null}
      {row.allowed_actions.includes("claim_correct_decision") ? <ClaimDecision key={`correction:${row.version}`} scope={scope} row={row} correction onDirtyChange={correctionDirty} /> : null}
      <div className="flex flex-wrap gap-3">{([
        ["claim_extend", "extend", "Extend claim deadline"], ["attendance_attest", "attendance-attestations", "Record exceptional attendance attestation"],
        ["receipt_override", "receipt-allocation-overrides", "Review receipt allocation override"],
      ] as const).map(([permission, route, label]) => row.allowed_actions.includes(permission) ? <button type="button" className="desk-button" key={route} onClick={() => setAction(route)}>{label}</button> : null)}</div>
      {action ? <ClaimFinanceAction key={`${action}:${row.version}`} scope={scope} row={row} action={action} onClose={() => setAction(null)} /> : null}
    </div> : null} />;
}
function Recommendation({ scope, row, onDirtyChange }: { scope: EventScope; row: ClaimReviewDetail; onDirtyChange?: (dirty: boolean) => void }) {
  const [recommendation, setRecommendation] = useState("return_for_info");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const mutation = useClaimReviewCommand(scope);
  useUnsavedChanges(Boolean(reason || note) && !mutation.isSuccess, onDirtyChange);
  return <form className="grid gap-4 rounded-2xl border border-line bg-panel p-5" onSubmit={event => { event.preventDefault(); mutation.mutate({
    path: `${reimbursementAdminPath(scope)}claims/${row.id}/review/`, body: { expected_version: row.version, claim_revision_id: row.claim_revision_id,
      mode: "recommend", recommendation, reason_code: reason, note: note.trim() },
  }); }}><h2 className="title-section">{t`Screening recommendation`}</h2><p>{t`Your recommendation goes to finance for the final decision.`}</p>
    <fieldset disabled={mutation.isPending || mutation.isSuccess} className="grid gap-4"><legend className="sr-only">{t`Recommendation`}</legend>
      <Field label={t`Recommendation`}><select className="desk-input" value={recommendation} onChange={event => setRecommendation(event.target.value)}><option value="approve">{t`Approve`}</option><option value="partial">{t`Partially approve`}</option><option value="reject">{t`Reject`}</option><option value="return_for_info">{t`Request more information`}</option></select></Field>
      <Field label={t`Reason code`}><input className="desk-input" required pattern="[a-z][a-z0-9_]{0,63}" maxLength={64} value={reason} onChange={event => setReason(event.target.value)} /></Field>
      <Field label={t`Screening note`}><textarea className="desk-input" required rows={4} maxLength={5000} value={note} onChange={event => setNote(event.target.value)} /></Field>
      <button type="submit" className="desk-button-primary">{mutation.isPending ? t`Saving…` : t`Submit recommendation`}</button></fieldset>
    {mutation.error ? <p role="alert">{commandError(mutation.error)}</p> : mutation.isSuccess ? <p role="status">{t`Recommendation saved.`}</p> : null}
  </form>;
}
