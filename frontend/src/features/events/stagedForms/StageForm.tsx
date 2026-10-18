import { useState } from "react";
import { FormPageLayout } from "../../../components/layouts";
import { FormV2Fields } from "../../forms/FormV2Fields";
import type { FormState } from "../../forms/types";
import type { UploadFormFiles } from "../../forms/FileInput";
import { SaveIntentNotice, useRegistrationSavedDetails } from "../../accountSavedDetails/RegistrationSavedDetails";
import type { StageResponse, StageScope } from "./types";
import { useStageCommand, useStageResponse } from "./api";

export function StageForm({ scope, responseId, uploadFiles }: { scope: StageScope; responseId: number; uploadFiles?: UploadFormFiles }) {
  const query = useStageResponse(scope, responseId);
  const [savedOperation, setSavedOperation] = useState<string | null>(null);
  if (!query.data) return <p role={query.error ? "alert" : "status"}>{query.error ? "Unable to load this form. Reload to try again." : "Loading form…"}</p>;
  return <><StageEditor key={`${query.data.id}:${query.data.version}`} scope={scope} response={query.data} uploadFiles={uploadFiles} onSaved={setSavedOperation} />
    {savedOperation ? <SaveIntentNotice actorId={scope.actorId} operationId={savedOperation} /> : null}</>;
}
function StageEditor({ scope, response, uploadFiles, onSaved }: { scope: StageScope; response: StageResponse; uploadFiles?: UploadFormFiles; onSaved: (id: string) => void }) {
  const [value, setValue] = useState<FormState>({ answers: Object.fromEntries(response.answers.answers.map(row => [row.id, row.value])),
    derivations: {}, save_choices: {}, saved_detail_versions: {} });
  const mutation = useStageCommand(scope, response.id);
  const prefill = useRegistrationSavedDetails(scope.actorId, {
    context: { subject_kind: "stage_response", subject_id: response.id, stage_form_id: response.assignment.stage_form_id,
      event_id: scope.eventId, makerspace_id: scope.makerspaceId }, form_id: response.schema.form_id,
    form_revision: response.schema.revision, event_date_revision: response.event_date_revision,
  });
  const closed = response.state === "locked" || response.state === "withdrawn" || response.assignment.state === "cancelled"
    || Date.now() >= Date.parse(response.assignment.due_at);
  const submit = (isSubmit: boolean) => mutation.mutate({ submit: isSubmit, body: {
    expected_version: response.version, expected_assignment_version: response.assignment.version,
    form: { schema_version: 2, form_id: response.schema.form_id, revision: response.schema.revision },
    ...value, derivations: {}, event_date_revision: response.event_date_revision,
  } }, { onSuccess: result => { if (result.save_operation_id) onSaved(result.save_operation_id); } });
  return <FormPageLayout header={{ title: response.assignment.title, subtitle: `Due ${new Date(response.assignment.due_at).toLocaleString()}` }}
    state={{ status: "ready" }} submit={{ label: "Submit form", onClick: () => submit(true), pending: mutation.isPending,
      disabled: closed, disabledReason: "This form is closed. Ask the organizer for an extension." }} form={<div className="grid gap-5">
      {closed ? <p role="status">This form is read-only. Your previous submissions remain available.</p> : null}
      {prefill.data && !closed ? <button type="button" className="desk-button min-h-11" onClick={() => {
        const answers = { ...value.answers };
        for (const question of response.schema.questions) if (question.profile_field_key && prefill.data.values[question.profile_field_key] !== undefined) {
          const saved = prefill.data.values[question.profile_field_key];
          answers[question.id] = question.type === "single_choice" ? { option_id: saved } : question.type === "multi_choice" ? { option_ids: saved } : saved;
        }
        setValue({ ...value, answers, saved_detail_versions: prefill.data.saved_detail_versions, save_choices: prefill.data.save_defaults });
      }}>Review my saved suggestions</button> : null}
      <fieldset disabled={closed || mutation.isPending} className="grid min-w-0 gap-4"><legend className="sr-only">Stage answers</legend>
        <FormV2Fields schema={response.schema} value={value} onChange={setValue} context="stage" uploadFiles={uploadFiles} />
      </fieldset>
      <button type="button" className="desk-button min-h-11" disabled={closed || mutation.isPending} onClick={() => submit(false)}>Save draft</button>
      {mutation.error ? <p role="alert">Your form was not saved. Check your answers or reload if the form or deadline changed.</p> : null}
    </div>} />;
}
