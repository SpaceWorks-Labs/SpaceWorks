import { t } from "@lingui/core/macro";
import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { Field } from "../../../components/ui/Field";
import { commandError, type EventScope } from "../../events/stagedForms/privateQueries";
import { utcInstant } from "../../events/stagedForms/formPayload";
import { useUnsavedChanges } from "../../events/stagedForms/UnsavedChanges";
import { stageAdminPath, useActivationCommand, useStageDefinition } from "./api";

export function parseParticipantIds(value: string) {
  const ids = value.split(",").map(part => Number(part.trim()));
  if (!value.trim() || ids.length > 1000 || ids.some(id => !Number.isSafeInteger(id) || id < 1) || new Set(ids).size !== ids.length) throw new Error(t`Use unique positive participant IDs, separated by commas.`);
  return ids;
}
export function StageActivation({ scope, stageFormId, onDirtyChange }: { scope: EventScope; stageFormId: number; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useStageDefinition(scope, stageFormId);
  const [participants, setParticipants] = useState("");
  const [due, setDue] = useState("");
  const [reviewed, setReviewed] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const mutation = useActivationCommand(scope);
  const signature = JSON.stringify([participants, due, query.data?.version]);
  const previewReady = reviewed === signature;
  useUnsavedChanges(Boolean(participants || due) && !mutation.data?.id, onDirtyChange);
  const run = (preview: boolean) => {
    try {
      if (!query.data) return;
      const body = { expected_version: query.data.version, participant_ids: parseParticipantIds(participants), due_at: utcInstant(due), preview, confirmed: !preview && confirmed };
      if (Date.parse(body.due_at) <= Date.now()) throw new Error(t`Choose a future deadline.`);
      setError(""); mutation.mutate({ path: `${stageAdminPath(scope)}stage-forms/${stageFormId}/activate/`, body }, { onSuccess: result => { if (result.preview) setReviewed(signature); } });
    } catch (failure) { setError(failure instanceof Error ? failure.message : t`Check your activation settings.`); }
  };
  return <FormPageLayout header={{ title: t`Activate stage assignments`, subtitle: query.data?.title }}
    state={{ status: query.isPending ? "loading" : query.error ? "error" : "ready", error: "The stage definition could not be loaded.", onRetry: () => void query.refetch() }}
    submit={{ label: t`Confirm activation`, pending: mutation.isPending, disabled: !previewReady || !confirmed || !query.data?.allowed_actions?.includes("stage_activate") || mutation.data?.state === "pending",
      disabledReason: "Preview the current selection and confirm the deadline first.", onClick: () => run(false) }} form={<div className="grid gap-4">
      <Field label={t`Participant member IDs`} hint={t`Comma separated; up to 1000. Preview checks each participant's trigger eligibility.`}><textarea className="desk-input" required value={participants} onChange={event => { setParticipants(event.target.value); setConfirmed(false); }} /></Field>
      <Field label={t`Reviewed deadline (your local time)`}><input className="desk-input" required type="datetime-local" value={due} onChange={event => { setDue(event.target.value); setConfirmed(false); }} /></Field>
      <button type="button" className="desk-button" disabled={mutation.isPending || !query.data?.allowed_actions?.includes("stage_activate")} onClick={() => run(true)}>{t`Preview eligible participants`}</button>
      {previewReady && mutation.data?.eligible_participant_ids ? <p role="status">{t`Eligible participants: `}{mutation.data.eligible_participant_ids.join(", ") || t`None`}.</p> : null}
      <label className="flex min-h-11 items-start gap-3"><input type="checkbox" required checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{t`I reviewed the participant selection and effective deadline.`}</label>
      {error || mutation.error ? <p role="alert">{error || commandError(mutation.error)}</p> : mutation.data?.id ? <p role="status">{t`Activation queued. Open completion to check assignments as they are created.`}</p> : null}
    </div>} />;
}
