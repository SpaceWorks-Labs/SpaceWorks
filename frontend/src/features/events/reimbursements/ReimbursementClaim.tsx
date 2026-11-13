import { formatDateTime } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { commandError } from "../stagedForms/privateQueries";
import { useFormUploads } from "../stagedForms/uploads";
import { useNow } from "../stagedForms/useNow";
import { useUnsavedChanges } from "../stagedForms/UnsavedChanges";
import { useApplicantCommand, useReimbursement, reimbursementPath } from "./api";
import { latestDecision, reimbursementStateLabel } from "./labels";
import { ClaimLineEditor, newClaimLine } from "./ClaimLineEditor";
import { CATEGORIES, type Category, type ClaimSummary, type ReimbursementScope } from "./types";
import { claimDraftLines } from "./claimPayload";
import { LogoLoader } from "../../../components/LogoLoader";

export function ReimbursementClaim({ scope, onDirtyChange }: { scope: ReimbursementScope; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useReimbursement(scope);
  const start = useApplicantCommand(scope);
  const row = query.data;
  if (!row) return <div>{query.error ? <p role="alert">{commandError(query.error)}</p> : <LogoLoader label={t`Loading claim…`} size={48} className="min-h-16 py-3" />}
    {query.error ? <button type="button" className="desk-button" onClick={() => void query.refetch()}>{t`Retry`}</button> : null}</div>;
  const categories: Category[] = row.programme.allowed_categories?.length ? row.programme.allowed_categories : CATEGORIES;
  const currency = row.award?.currency ?? row.programme.currency ?? "";
  if (!row.claim) {
    // The first save opens the claim (an empty draft), so receipts can be uploaded against it.
    return <div className="grid gap-4">{row.allowed_actions.includes("create_claim") ? <>
      <p>{t`Start your expense claim, then add each expense with its receipt. Nothing is sent to finance until you submit.`}</p>
      <button type="button" className="desk-button-primary justify-self-start" disabled={start.isPending} onClick={() => start.mutate({
        path: `${reimbursementPath(scope)}claim/`, method: "PUT", body: { expected_version: 0, lines: [] } })}>{t`Start expense claim`}</button>
      {start.error ? <p role="alert">{commandError(start.error)}</p> : null}</>
      : <p role="status">{t`An expense claim opens after you accept an award and the event has ended.`}</p>}</div>;
  }
  return <ClaimEditor key={row.claim.version} scope={scope} claim={row.claim} categories={categories} currency={currency} onDirtyChange={onDirtyChange} />;
}

function ClaimEditor({ scope, claim, categories, currency, onDirtyChange }: { scope: ReimbursementScope; claim: ClaimSummary;
  categories: Category[]; currency: string; onDirtyChange?: (dirty: boolean) => void }) {
  const [lines, setLines] = useState(claim.draft?.lines ?? []);
  const [dirty, setDirty] = useState(false);
  const [validation, setValidation] = useState("");
  const mutation = useApplicantCommand(scope);
  const uploads = useFormUploads(`${reimbursementPath(scope)}receipt-files/`, { claim_uuid: claim.uuid });
  const now = useNow();
  useUnsavedChanges(dirty || uploads.busy, onDirtyChange);
  const due = claim.info_due_at ?? claim.effective_due_at;
  const canEdit = claim.allowed_actions.includes("edit") && now < Date.parse(due);
  const canSubmit = claim.allowed_actions.includes("submit") && now < Date.parse(due) && lines.length > 0;
  const reason = latestDecision(claim)?.reason;
  const save = () => {
    try {
      const normalized = claimDraftLines(lines); setValidation("");
      mutation.mutate({ path: `${reimbursementPath(scope)}claim/`, method: "PUT", body: { expected_version: claim.version, lines: normalized } },
        { onSuccess: () => setDirty(false) });
    } catch (error) { setValidation(error instanceof Error ? error.message : t`Check your claim fields.`); }
  };
  return <FormPageLayout header={{ title: t`Your expense claim`, subtitle: t`Due ${formatDateTime(due)}` }} state={{ status: "ready" }}
    submit={{ label: t`Submit saved claim`, pending: mutation.isPending, disabled: !canSubmit || dirty || uploads.busy,
      disabledReason: dirty ? t`Save your draft before submitting it.` : uploads.busy ? t`Wait for files to finish checking.` : !lines.length ? t`Add at least one expense.` : t`Claim submission is closed.`,
      onClick: () => mutation.mutate({ path: `${reimbursementPath(scope)}claim/submit/`, body: { expected_version: claim.version, current_revision: claim.current_revision } }) }}
    form={<div className="grid gap-5"><p>{t`Enter each eligible expense in its original currency. Finance reviews exchange rates and applies your accepted cap. Approval creates an amount owed; payments are recorded after a human makes them.`}</p>
      <p role="status">{canEdit ? t`Claim status: ${reimbursementStateLabel(claim.display_state)}` : t`Claim status: ${reimbursementStateLabel(claim.display_state)} · Read-only`}</p>{reason ? <p>{reason}</p> : null}
      {lines.map(line => <ClaimLineEditor key={line.line_uuid} line={line} categories={categories} readOnly={!canEdit || mutation.isPending || uploads.busy}
        upload={uploads.upload} onChange={next => { setLines(current => current.map(item => item.line_uuid === next.line_uuid ? next : item)); setDirty(true); }}
        onRemove={() => { setLines(lines.filter(item => item.line_uuid !== line.line_uuid)); setDirty(true); }} />)}
      {canEdit ? <button type="button" className="desk-button justify-self-start" disabled={lines.length >= 50 || mutation.isPending || uploads.busy} onClick={() => {
        setLines([...lines, newClaimLine(currency, categories[0])]); setDirty(true);
      }}>{t`Add expense`}</button> : null}
      <button type="button" className="desk-button" disabled={!canEdit || mutation.isPending || uploads.busy} onClick={save}>{t`Save claim draft`}</button>
      {validation || mutation.error ? <p role="alert">{validation || commandError(mutation.error)}</p> : null}
      {mutation.isSuccess ? <p role="status">{t`Your claim was saved.`}</p> : dirty ? <p role="status">{t`You have unsaved expenses.`}</p> : null}</div>} />;
}
