import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { FormV2Fields } from "../../forms/FormV2Fields";
import type { FormState } from "../../forms/types";
import type { UploadFormFiles } from "../../forms/FileInput";
import { FormSaveIntentsNotice, SaveIntentNotice, useRegistrationSavedDetails } from "../../accountSavedDetails/RegistrationSavedDetails";
import type { StageResponse, StageScope, CommandResult } from "./types";
import { stagePath, useStageCommand, useStageResponse } from "./api";
import { applyStageSuggestions, stagePayload } from "./formPayload";
import { useUnsavedChanges } from "./UnsavedChanges";
import { commandError } from "./privateQueries";
import { useFormUploads } from "./uploads";
import { useNow } from "./useNow";

export function StageForm({ scope, responseId, uploadFiles, onDirtyChange }: { scope: StageScope; responseId: number;
  uploadFiles?: UploadFormFiles; onDirtyChange?: (dirty: boolean) => void }) {
  const query = useStageResponse(scope, responseId);
  const [saved, setSaved] = useState<CommandResult | null>(null);
  if (!query.data) return <div><p role={query.error ? "alert" : "status"}>{query.error ? commandError(query.error) : "Loading form…"}</p>
    {query.error ? <button type="button" className="desk-button" onClick={() => void query.refetch()}>Retry</button> : null}</div>;
  return <><StageEditor key={`${query.data.id}:${query.data.version}`} scope={scope} response={query.data} uploadFiles={uploadFiles} onSaved={setSaved} onDirtyChange={onDirtyChange} />
    {saved?.form_save_intents ? <FormSaveIntentsNotice actorId={scope.actorId} intents={saved.form_save_intents} /> : saved?.save_operation_id ? <SaveIntentNotice actorId={scope.actorId} operationId={saved.save_operation_id} /> : null}</>;
}
function StageEditor({ scope, response, uploadFiles, onSaved, onDirtyChange }: { scope: StageScope; response: StageResponse;
  uploadFiles?: UploadFormFiles; onSaved: (result: CommandResult) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const initial: FormState = { answers: Object.fromEntries(response.answers.answers.map(row => [row.id, row.value])), derivations: {}, save_choices: {}, saved_detail_versions: {} };
  const [value, setValue] = useState(initial);
  const [dirty, setDirty] = useState(false);
  const mutation = useStageCommand(scope);
  const uploads = useFormUploads(`${stagePath(scope)}/stage-forms/${response.assignment.stage_form_id}/files/`, {
    response_id: response.id, expected_response_version: response.version, form_revision_id: response.assignment.pinned_form_revision_id });
  useUnsavedChanges(dirty || uploads.busy, onDirtyChange);
  const now = useNow();
  const closed = response.state === "locked" || response.state === "withdrawn" || response.assignment.state === "cancelled"
    || Boolean(response.assignment.next_stage_locked_at) || now >= Date.parse(response.assignment.due_at) || now < Date.parse(response.assignment.opens_at);
  const prefill = useRegistrationSavedDetails(scope.actorId, {
    context: { subject_kind: "stage_response", subject_id: response.id, stage_form_id: response.assignment.stage_form_id,
      event_id: scope.eventId, makerspace_id: scope.makerspaceId }, form_id: response.schema.form_id,
    form_revision: response.schema.revision, event_date_revision: response.event_date_revision,
  }, !closed);
  const change = (next: FormState) => { setValue(next); setDirty(true); };
  const submit = (isSubmit: boolean) => mutation.mutate({ method: isSubmit ? "POST" : "PUT",
    path: `${stagePath(scope)}/stage-responses/${response.id}/${isSubmit ? "submit/" : ""}`, body: {
      expected_version: response.version, expected_assignment_version: response.assignment.version,
      ...stagePayload(response.schema, value, response.event_date_revision),
    } }, { onSuccess: result => { setDirty(false); onSaved(result); } });
  const blocked = closed || uploads.busy;
  const canSave = response.allowed_actions?.includes("stage_save") === true;
  const canSubmit = response.allowed_actions?.includes("stage_submit") === true;
  return <FormPageLayout header={{ title: response.assignment.title, subtitle: `Due ${new Date(response.assignment.due_at).toLocaleString()}` }}
    state={{ status: "ready" }} submit={{ label: response.selected_revision ? "Resubmit form" : "Submit form", onClick: () => submit(true), pending: mutation.isPending,
      disabled: blocked || !canSubmit, disabledReason: uploads.busy ? "Wait for files to finish checking." : "Submission is unavailable. Ask the organizer if you need an extension." }}
    form={<div className="grid gap-5">
      {closed ? <p role="status">This form is read-only. Your previous submissions remain available.</p> : null}
      {response.selected_revision ? <p role="status">Submitted revision {response.selected_revision}. A new submission preserves your earlier answers.</p> : null}
      {!closed ? <div className="grid gap-2"><p className="text-sm text-muted">Saved details are suggestions. Review them before submitting. Saving sensitive details is optional.</p>
        {prefill.isPending ? <p role="status">Loading saved suggestions…</p> : prefill.error ? <p role="status">Saved suggestions are unavailable. You can fill in this form yourself.</p> : null}
        {prefill.data ? <button type="button" className="desk-button min-h-11" onClick={() => change(applyStageSuggestions(response.schema, value, prefill.data!))}>Use saved details for empty answers</button> : null}</div> : null}
      <fieldset disabled={closed || !canSave || mutation.isPending} className="grid min-w-0 gap-4"><legend className="sr-only">Stage answers</legend>
        <FormV2Fields schema={response.schema} value={value} onChange={change} context="stage" uploadFiles={uploadFiles ?? uploads.upload} />
      </fieldset>
      {dirty ? <p role="status">You have unsaved answers.</p> : null}
      <div className="flex flex-wrap gap-3"><button type="button" className="desk-button min-h-11" disabled={blocked || !canSave || mutation.isPending} onClick={() => submit(false)}>Save draft</button>
        <button type="button" className="desk-button" disabled={!dirty || mutation.isPending || uploads.busy} onClick={() => { if (window.confirm("Discard unsaved answers?")) { setValue(initial); setDirty(false); } }}>Discard changes</button></div>
      {mutation.error ? <p role="alert">{commandError(mutation.error)}</p> : mutation.isSuccess ? <p role="status">Your form was saved.</p> : null}
    </div>} />;
}
