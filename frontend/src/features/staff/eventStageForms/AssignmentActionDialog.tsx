import { useState } from "react";
import { Modal } from "../../../components/ui/Modal";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { stageAdminPath, useAssignmentCommand } from "./api";
import type { AssignmentAction, ManagedAssignment } from "./types";

export function AssignmentActionDialog({ scope, assignment, action, onClose }: { scope: EventScope; assignment: ManagedAssignment; action: AssignmentAction; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const [code, setCode] = useState(action === "cancel" ? "no_longer_required" : action === "reassign" ? "replacement_revision" : "deadline_extension");
  const [due, setDue] = useState("");
  const [revision, setRevision] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const mutation = useAssignmentCommand(scope);
  const dirty = Boolean(reason || due || revision || confirmed || code !== (action === "cancel" ? "no_longer_required" : action === "reassign" ? "replacement_revision" : "deadline_extension"));
  return <Modal open title={`${action[0].toUpperCase()}${action.slice(1)} assignment`} onClose={() => { if (!mutation.isPending && (!dirty || window.confirm("Discard this unsaved assignment change?"))) onClose(); }}>
    <form className="grid gap-4" onSubmit={event => { event.preventDefault();
      try {
        const dueAt = action === "cancel" ? undefined : utcInstant(due);
        if (dueAt && Date.parse(dueAt) <= Date.now()) { setError("Choose a future deadline."); return; }
        setError("");
        mutation.mutate({ path: `${stageAdminPath(scope)}stage-assignments/${assignment.id}/${action}/`, body: {
          expected_version: assignment.version, expected_response_version: assignment.response_version ?? null,
          expected_stage_form_version: assignment.stage_form_version, reason_code: code, reason: reason.trim(), confirmed: true,
          ...(dueAt ? { due_at: dueAt } : {}), ...(action === "reassign" ? { replacement_form_revision_id: Number(revision) } : {}),
        } }, { onSuccess: onClose });
      } catch { setError("Choose a valid future date and time."); }
    }}><p><strong>{assignment.title}</strong> · {assignment.owner_label}</p><p>Pinned revision ID {assignment.pinned_form_revision_id}. Current deadline: {new Date(assignment.due_at).toLocaleString()}.</p>
      <p>{action === "cancel" ? "Cancelling exempts this assignment from later requirements. Submitted history and files are retained." : action === "reassign" ? "Reassignment opens an empty draft with the replacement questions. The participant must submit again before configured later actions. Submitted history is retained." : "The participant receives the new deadline. Earlier submitted revisions are retained."}</p>
      <fieldset disabled={mutation.isPending} className="grid gap-4"><legend className="sr-only">Assignment change</legend>
        {action === "reassign" ? <Field label="Published replacement revision"><select className="desk-input" required value={revision} onChange={event => { setRevision(event.target.value); setConfirmed(false); }}><option value="">Choose a revision</option>{assignment.published_revisions.map(row => <option value={row.id} key={row.id}>Revision {row.revision} · ID {row.id}</option>)}</select></Field> : null}
        {action !== "cancel" ? <Field label="New deadline (your local time)"><input className="desk-input" required type="datetime-local" value={due} onChange={event => { setDue(event.target.value); setConfirmed(false); }} /></Field> : null}
        <Field label="Reason code"><input className="desk-input" required maxLength={64} pattern="[a-z][a-z0-9_]{0,63}" value={code} onChange={event => setCode(event.target.value)} /></Field>
        <Field label="Reason for participant"><textarea className="desk-input" required maxLength={5000} rows={3} value={reason} onChange={event => setReason(event.target.value)} /></Field>
        <label className="flex min-h-11 items-start gap-3"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} /><span>I confirm the assignment, revision, deadline and requirement change shown above.</span></label>
        <button type="submit" className={action === "cancel" ? "desk-button-danger-outline" : "desk-button-primary"} disabled={!confirmed || !assignment.allowed_actions.includes(action)}>{mutation.isPending ? "Saving…" : `Confirm ${action}`}</button></fieldset>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : null}
    </form></Modal>;
}
