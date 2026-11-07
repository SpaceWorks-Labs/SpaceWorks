import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { useUnsavedChanges } from "../../events/stagedForms/UnsavedChanges";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { reimbursementAdminPath, useClaimReviewCommand } from "./api";
import type { ClaimReviewDetail, DecisionCommand, DecisionOutcome, LineDecision } from "./types";

export function decisionBody(row: ClaimReviewDetail, outcome: DecisionOutcome, lines: LineDecision[], reason: string, note: string, due: string): DecisionCommand {
  const total = lines.reduce((sum, line) => sum + line.approved_minor, 0);
  if (!Number.isSafeInteger(total) || total > row.accepted_cap_minor || lines.some(line => !Number.isSafeInteger(line.approved_minor) || line.approved_minor < 0)) throw new Error(t`Approved amounts must be whole minor units within the accepted cap.`);
  if (lines.length !== row.lines.length || new Set(lines.map(line => line.line_uuid)).size !== lines.length || lines.some(line => {
    const source = row.lines.find(item => item.line_uuid === line.line_uuid); return !source || line.approved_minor > source.converted_minor || !line.reason_code;
  })) throw new Error(t`Review every current claim line and its converted amount.`);
  if (["rejected", "returned_for_info"].includes(outcome) && total !== 0) throw new Error(t`Rejection or return for information must have zero approved allocations.`);
  if (outcome === "approved" && (total <= 0 || total !== row.claimed_minor)) throw new Error(t`Full approval must match the claim total. Choose partial approval when reducing it.`);
  if (outcome === "partially_approved" && (total <= 0 || total >= row.claimed_minor)) throw new Error(t`Partial approval needs a positive amount below the claim total.`);
  if (!reason || !note.trim()) throw new Error(t`Give a reason code and decision note.`);
  return { expected_version: row.version, mode: "decide", claim_revision_id: row.claim_revision_id,
    expected_pool_version: row.pool.version, expected_decision_sequence: row.decision_sequence,
    expected_obligation_version: row.obligation_version, eligibility_revision: row.eligibility_revision,
    outcome, line_decisions: lines, reason_code: reason, note: note.trim(),
    ...(outcome === "returned_for_info" ? { info_due_at: utcInstant(due) } : {}) };
}
export function ClaimDecision({ scope, row, correction = false, onDirtyChange }: { scope: EventScope; row: ClaimReviewDetail; correction?: boolean; onDirtyChange?: (dirty: boolean) => void }) {
  const [outcome, setOutcome] = useState<DecisionOutcome>(correction ? "partially_approved" : "returned_for_info");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [due, setDue] = useState("");
  const [lines, setLines] = useState<LineDecision[]>(row.lines.map(line => ({ line_uuid: line.line_uuid, approved_minor: 0, reason_code: "policy_review" })));
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const mutation = useClaimReviewCommand(scope);
  useUnsavedChanges(Boolean(note || reason) && !mutation.isSuccess, onDirtyChange);
  const total = lines.reduce((sum, line) => sum + line.approved_minor, 0);
  return <form className="grid gap-4 rounded-2xl border border-line bg-panel p-5" onSubmit={event => { event.preventDefault();
    try {
      const command = decisionBody(row, outcome, lines, reason, note, due); setError("");
      if (correction) {
        const { mode: _mode, eligibility_revision: _eligibility, info_due_at: _due, ...body } = command;
        mutation.mutate({ path: `${reimbursementAdminPath(scope)}claims/${row.id}/correct-decision/`, body });
      } else mutation.mutate({ path: `${reimbursementAdminPath(scope)}claims/${row.id}/review/`, body: command });
    } catch (failure) { setError(failure instanceof Error ? failure.message : t`Check the decision fields.`); }
  }}><h2 className="title-section">{correction ? t`Correct unpaid decision` : t`Final finance decision`}</h2>
    <p>{t`Accepted cap: ${row.accepted_cap_minor} minor units (${row.currency}). Approved total: ${total}. A positive approval records an amount owed.`}</p>
    <fieldset disabled={mutation.isPending || mutation.isSuccess} className="grid gap-4"><legend className="sr-only">{t`Finance decision`}</legend>
      <Field label={t`Outcome`}><select className="desk-input" value={outcome} onChange={event => { setOutcome(event.target.value as DecisionOutcome); setConfirmed(false); }}>
        {(["approved", "partially_approved", "rejected", ...(correction ? [] : ["returned_for_info"])]).map(value => <option key={value} value={value}>{value.replace(/_/g, " ")}</option>)}
      </select></Field>
      {row.lines.map((line, index) => <div key={line.line_uuid} className="grid gap-3 rounded-xl border border-line p-3 md:grid-cols-2"><p className="md:col-span-2">{t`${line.category} · Converted ${line.converted_minor} minor units (${row.currency})`}</p>
        <Field label={t`Approved minor units for expense ${index + 1}`}><input className="desk-input" type="number" min={0} max={line.converted_minor} step={1} required value={lines[index].approved_minor} onChange={event => { setLines(lines.map((item, i) => i === index ? { ...item, approved_minor: event.target.valueAsNumber } : item)); setConfirmed(false); }} /></Field>
        <Field label={t`Reason code for expense ${index + 1}`}><input className="desk-input" required pattern="[a-z][a-z0-9_]{0,63}" maxLength={64} value={lines[index].reason_code} onChange={event => { setLines(lines.map((item, i) => i === index ? { ...item, reason_code: event.target.value } : item)); setConfirmed(false); }} /></Field></div>)}
      {outcome === "returned_for_info" ? <Field label={t`Information due (your local time)`}><input className="desk-input" required type="datetime-local" value={due} onChange={event => { setDue(event.target.value); setConfirmed(false); }} /></Field> : null}
      <Field label={t`Decision reason code`}><input className="desk-input" required maxLength={64} pattern="[a-z][a-z0-9_]{0,63}" value={reason} onChange={event => { setReason(event.target.value); setConfirmed(false); }} /></Field>
      <Field label={t`Decision note`}><textarea className="desk-input" required maxLength={5000} rows={4} value={note} onChange={event => { setNote(event.target.value); setConfirmed(false); }} /></Field>
      <label className="flex min-h-11 items-start gap-3"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t`I reviewed the expense allocations, eligibility evidence, cap and decision.`}</label>
      <button type="submit" className="desk-button-primary" disabled={!confirmed}>{mutation.isPending ? t`Saving…` : correction ? t`Append corrected decision` : t`Confirm finance decision`}</button></fieldset>
    {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : mutation.isSuccess ? <p role="status">{t`Decision recorded.`}</p> : null}
  </form>;
}
