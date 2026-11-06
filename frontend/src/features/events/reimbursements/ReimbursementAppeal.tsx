import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { reimbursementPath, useApplicantCommand, useClaim } from "./api";
import { commandError } from "../stagedForms/privateQueries";
import { useUnsavedChanges } from "../stagedForms/UnsavedChanges";
import { useNow } from "../stagedForms/useNow";
import type { ReimbursementScope } from "./types";
export function ReimbursementAppeal({ scope, onDirtyChange }: { scope: ReimbursementScope; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useClaim(scope);
  const mutation = useApplicantCommand(scope);
  const [statement, setStatement] = useState("");
  const now = useNow();
  useUnsavedChanges(Boolean(statement) && !mutation.isSuccess, onDirtyChange);
  const claim = query.data?.claim;
  const allowed = claim?.allowed_actions.includes("claim_appeal") && Boolean(claim.appeal_due_at && now < Date.parse(claim.appeal_due_at));
  return <FormPageLayout header={{ title: t`Appeal your claim decision`, subtitle: claim?.appeal_due_at ? t`Due ${new Date(claim.appeal_due_at).toLocaleString(formatLocale())}` : undefined }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "The claim could not be loaded.", onRetry: () => void query.refetch() }}
    submit={{ label: t`Submit appeal`, pending: mutation.isPending, disabled: !allowed || mutation.isSuccess, disabledReason: "An appeal is unavailable or its deadline has passed.", onClick: () => {
      if (claim) mutation.mutate({ path: `${reimbursementPath(scope)}claim/appeal/`, body: { expected_version: claim.version, current_revision: claim.current_revision, statement: statement.trim() } });
    } }} form={<div className="grid gap-4"><p>{claim?.reason}</p><p>{t`You may appeal once within the stated deadline. An appeal cannot increase the cap of your accepted award.`}</p>
      <Field label={t`Appeal statement`}><textarea className="desk-input" rows={6} required maxLength={5000} value={statement} onChange={event => setStatement(event.target.value)} disabled={!allowed || mutation.isPending || mutation.isSuccess} /></Field>
      {mutation.error ? <p role="alert">{commandError(mutation.error)}</p> : mutation.isSuccess ? <p role="status">{t`Your appeal was submitted.`}</p> : null}</div>} />;
}
