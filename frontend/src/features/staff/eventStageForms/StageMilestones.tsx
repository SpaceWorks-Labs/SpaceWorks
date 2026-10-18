import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { useUnsavedChanges } from "../../events/stagedForms/UnsavedChanges";
import { stageAdminPath, useMilestoneCommand } from "./api";
import { parseParticipantIds } from "./StageActivation";
export function StageMilestones({ scope, eventVersion, allowedActions, onDirtyChange }: { scope: EventScope; eventVersion: number; allowedActions: string[]; onDirtyChange?: (dirty: boolean) => void }) {
  const [participants, setParticipants] = useState("");
  const [published, setPublished] = useState(true);
  const [code, setCode] = useState("shortlist_published");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const mutation = useMilestoneCommand(scope);
  useUnsavedChanges(Boolean(participants) && !mutation.isSuccess, onDirtyChange);
  return <FormPageLayout header={{ title: "Shortlist milestone" }} state={{ status: "ready" }}
    submit={{ label: published ? "Publish checklist milestone" : "Withdraw checklist milestone", pending: mutation.isPending, disabled: !confirmed || !allowedActions.includes("stage_shortlist"),
      disabledReason: "Review the selection and confirm this checklist change.", onClick: () => {
        try { const ids = parseParticipantIds(participants); if (ids.length > 100) throw new Error("Choose at most 100 participants."); setError("");
          mutation.mutate({ path: `${stageAdminPath(scope)}stage-milestones/shortlist/`, body: { expected_version: eventVersion, participant_ids: ids, published, reason_code: code } });
        } catch (failure) { setError(failure instanceof Error ? failure.message : "Check participant IDs."); }
      } }} form={<div className="grid gap-4"><p>This publishes or withdraws a checklist milestone. Registration, admission and seat allocation follow their own workflows.</p>
      <Field label="Participant member IDs"><textarea className="desk-input" required value={participants} onChange={event => { setParticipants(event.target.value); setConfirmed(false); }} /></Field>
      <Field label="Milestone action"><select className="desk-input" value={String(published)} onChange={event => { setPublished(event.target.value === "true"); setConfirmed(false); }}><option value="true">Publish shortlist</option><option value="false">Withdraw shortlist</option></select></Field>
      <Field label="Reason code"><input className="desk-input" required pattern="[a-z][a-z0-9_]{0,63}" maxLength={64} value={code} onChange={event => setCode(event.target.value)} /></Field>
      <label className="flex min-h-11 items-start gap-3"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />I confirm this checklist change for the selected participants.</label>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : mutation.isSuccess ? <p role="status">Milestone saved.</p> : null}</div>} />;
}
