import { formatDateTime } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Modal } from "../../../components/ui/Modal";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { stageAdminPath, useAssignmentCommand } from "./api";
import type { AssignmentAction, ManagedAssignment } from "./types";

const titles = (): Record<AssignmentAction, string> => ({ extend: t`Extend assignment`, reopen: t`Reopen assignment`, cancel: t`Cancel assignment`, reassign: t`Reassign assignment` });
const confirmLabels = (): Record<AssignmentAction, string> => ({ extend: t`Confirm extend`, reopen: t`Confirm reopen`, cancel: t`Confirm cancel`, reassign: t`Confirm reassign` });

export function AssignmentActionDialog({ scope, assignment, action, onClose }: { scope: EventScope; assignment: ManagedAssignment; action: AssignmentAction; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const [code, setCode] = useState(action === "cancel" ? "no_longer_required" : action === "reassign" ? "replacement_revision" : "deadline_extension");
  const [due, setDue] = useState("");
  const [revision, setRevision] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const mutation = useAssignmentCommand(scope);
  const dirty = Boolean(reason || due || revision || confirmed || code !== (action === "cancel" ? "no_longer_required" : action === "reassign" ? "replacement_revision" : "deadline_extension"));
  return <Modal open title={titles()[action]} onClose={() => { if (!mutation.isPending && (!dirty || window.confirm(t`Discard this unsaved assignment change?`))) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault();
      try {
        const dueAt = action === "cancel" ? undefined : utcInstant(due);
        if (dueAt && Date.parse(dueAt) <= Date.now()) { setError(t`Choose a future deadline.`); return; }
        setError("");
        mutation.mutate({ path: `${stageAdminPath(scope)}stage-assignments/${assignment.id}/${action}/`, body: {
          expected_version: assignment.version, expected_response_version: assignment.response_version ?? null,
          expected_stage_form_version: assignment.stage_form_version, reason_code: code, reason: reason.trim(), confirmed: true,
          ...(dueAt ? { due_at: dueAt } : {}), ...(action === "reassign" ? { replacement_form_revision_id: Number(revision) } : {}),
        } }, { onSuccess: onClose });
      } catch { setError(t`Choose a valid future date and time.`); }
    }}><p><strong>{assignment.title}</strong> · {assignment.owner_label}</p><p>{t`Pinned revision ID ${assignment.pinned_form_revision_id}. Current deadline: ${formatDateTime(assignment.due_at)}.`}</p>
      <p>{action === "cancel" ? t`Cancelling exempts this assignment from later requirements. Submitted history and files are retained.` : action === "reassign" ? t`Reassignment opens an empty draft with the replacement questions. The participant must submit again before configured later actions. Submitted history is retained.` : t`The participant receives the new deadline. Earlier submitted revisions are retained.`}</p>
      <fieldset disabled={mutation.isPending} className="grid gap-4"><legend className="sr-only">{t`Assignment change`}</legend>
        {action === "reassign" ? <Field label={t`Published replacement revision`}><select className="desk-input" required value={revision} onChange={event => { setRevision(event.target.value); setConfirmed(false); }}><option value="">{t`Choose a revision`}</option>{assignment.published_revisions.map(row => <option value={row.id} key={row.id}>{t`Revision ${row.revision} · ID ${row.id}`}</option>)}</select></Field> : null}
        {action !== "cancel" ? <Field label={t`New deadline (your local time)`}><input className="desk-input" required type="datetime-local" value={due} onChange={event => { setDue(event.target.value); setConfirmed(false); }} /></Field> : null}
        <Field label={t`Reason code`}><input className="desk-input" required maxLength={64} pattern="[a-z][a-z0-9_]{0,63}" value={code} onChange={event => setCode(event.target.value)} /></Field>
        <Field label={t`Reason for participant`}><textarea className="desk-input" required maxLength={5000} rows={3} value={reason} onChange={event => setReason(event.target.value)} /></Field>
        <label className="flex min-h-11 items-start gap-3"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>{t`I confirm the assignment, revision, deadline and requirement change shown above.`}</span></label>
        <button type="submit" className={action === "cancel" ? "desk-button-danger-outline" : "desk-button-primary"} disabled={!confirmed || !assignment.allowed_actions.includes(action)}>{mutation.isPending ? t`Saving…` : confirmLabels()[action]}</button></fieldset>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : null}
    </form></Modal>;
}
