import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { FormV2Fields } from "../../forms/FormV2Fields";
import type { FormState } from "../../forms/types";
import { commandError } from "../stagedForms/privateQueries";
import { stagePayload } from "../stagedForms/formPayload";
import { useFormUploads } from "../stagedForms/uploads";
import { useNow } from "../stagedForms/useNow";
import { useUnsavedChanges } from "../stagedForms/UnsavedChanges";
import { useApplicantCommand, useClaim, reimbursementPath } from "./api";
import { ClaimLineEditor, newClaimLine } from "./ClaimLineEditor";
import type { ClaimDetail, ReimbursementScope } from "./types";
import { claimDraftLines } from "./claimPayload";

export function ReimbursementClaim({ scope, onDirtyChange }: { scope: ReimbursementScope; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useClaim(scope);
  if (!query.data) return <div><p role={query.error ? "alert" : "status"}>{query.error ? commandError(query.error) : t`Loading claim…`}</p>
    {query.error ? <button type="button" className="desk-button" onClick={() => void query.refetch()}>{t`Retry`}</button> : null}</div>;
  return <ClaimEditor key={query.data.claim.version} scope={scope} detail={query.data} onDirtyChange={onDirtyChange} />;
}
function ClaimEditor({ scope, detail, onDirtyChange }: { scope: ReimbursementScope; detail: ClaimDetail; onDirtyChange?: (dirty: boolean) => void }) {
  const [lines, setLines] = useState(detail.lines);
  const [dirty, setDirty] = useState(false);
  const [validation, setValidation] = useState("");
  const [formValue, setFormValue] = useState<FormState>({ answers: detail.form_context?.answers ?? {}, derivations: {}, save_choices: {}, saved_detail_versions: {} });
  const mutation = useApplicantCommand(scope);
  const uploads = useFormUploads(`${reimbursementPath(scope)}receipt-files/`, { claim_uuid: detail.claim.uuid });
  const now = useNow();
  useUnsavedChanges(dirty || uploads.busy, onDirtyChange);
  const due = detail.claim.info_due_at ?? detail.claim.due_at;
  const canEdit = detail.claim.allowed_actions.includes("claim_edit") && now < Date.parse(due);
  const canSubmit = detail.claim.allowed_actions.includes("claim_submit") && now < Date.parse(due);
  const save = () => {
    try {
      const normalized = claimDraftLines(lines); setValidation("");
      mutation.mutate({ path: `${reimbursementPath(scope)}claim/`, method: "PUT", body: { expected_version: detail.claim.version, lines: normalized,
      ...(detail.form_context ? stagePayload(detail.form_context.schema, formValue, detail.form_context.event_date_revision) : {}) } }, { onSuccess: () => setDirty(false) });
    } catch (error) { setValidation(error instanceof Error ? error.message : "Check your claim fields."); }
  };
  return <FormPageLayout header={{ title: t`Your expense claim`, subtitle: t`Due ${new Date(due).toLocaleString(formatLocale())}` }} state={{ status: "ready" }}
    submit={{ label: t`Submit saved claim`, pending: mutation.isPending, disabled: !canSubmit || dirty || uploads.busy,
      disabledReason: dirty ? "Save your draft before submitting it." : uploads.busy ? "Wait for files to finish checking." : "Claim submission is closed.",
      onClick: () => mutation.mutate({ path: `${reimbursementPath(scope)}claim/submit/`, body: { expected_version: detail.claim.version, current_revision: detail.claim.current_revision } }) }}
    form={<div className="grid gap-5"><p>{t`Enter each eligible expense in its original currency. Finance reviews exchange rates and applies your accepted cap. Approval creates an amount owed; payments are recorded after a human makes them.`}</p>
      <p role="status">{t`Claim ${detail.claim.state.replace(/_/g, " ")}`}{!canEdit ? t` · Read-only` : ""}</p>{detail.claim.reason ? <p>{detail.claim.reason}</p> : null}
      {lines.map(line => <ClaimLineEditor key={line.line_uuid} line={line} categories={detail.allowed_categories} readOnly={!canEdit || mutation.isPending || uploads.busy}
        upload={uploads.upload} onChange={next => { setLines(current => current.map(item => item.line_uuid === next.line_uuid ? next : item)); setDirty(true); }}
        onRemove={() => { setLines(lines.filter(item => item.line_uuid !== line.line_uuid)); setDirty(true); }} />)}
      {canEdit ? <button type="button" className="desk-button justify-self-start" disabled={lines.length >= 50 || mutation.isPending || uploads.busy} onClick={() => {
        setLines([...lines, newClaimLine(detail.claim.currency, detail.allowed_categories[0])]); setDirty(true);
      }}>{t`Add expense`}</button> : null}
      {detail.form_context ? <fieldset disabled={!canEdit || mutation.isPending}><FormV2Fields schema={detail.form_context.schema} value={formValue} context="claim" uploadFiles={uploads.upload} onChange={next => { setFormValue(next); setDirty(true); }} /></fieldset> : null}
      <button type="button" className="desk-button" disabled={!canEdit || mutation.isPending || uploads.busy} onClick={save}>{t`Save claim draft`}</button>
      {validation || mutation.error ? <p role="alert">{validation || commandError(mutation.error)}</p> : null}
      {mutation.isSuccess ? <p role="status">{t`Your claim was saved.`}</p> : dirty ? <p role="status">{t`You have unsaved expenses.`}</p> : null}</div>} />;
}
