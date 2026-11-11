import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Callout } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers } from "../forms/customFormTypes";
import { JoinFormExtras } from "./joinFields/JoinFormExtras";
import { EMPTY_EXTRAS, NO_EXTRAS, asksForAnything, serverExtrasErrors, validateExtras, type JoinExtrasErrors } from "./joinFields/joinFieldsModel";
import { joinFieldsInput } from "./joinFields/uploadJoinPhoto";
import { resubmitAdmission, type AdmissionRequest } from "./membershipAdmissionApi";

// A resubmission may leave a field blank to keep what was sent the first time; the server decides.
const MAYBE_ON_FILE = { phone: true, state: true, photo: true };

function storedAnswers(request: AdmissionRequest): CustomAnswers {
  return Object.fromEntries((request.application_answers?.answers ?? []).map((answer) => [answer.id, answer.value])) as CustomAnswers;
}

/**
 * Parity O-B2, the applicant's side of "ask for changes": the reviewer's note, then the application
 * itself, editable once. Sending it puts the request back in the review queue (or back to vouching).
 */
export function ApplicationChanges({ makerspaceId, request }: { makerspaceId: number; request: AdmissionRequest }) {
  const client = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [answers, setAnswers] = useState<CustomAnswers>(() => storedAnswers(request));
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [extras, setExtras] = useState(EMPTY_EXTRAS);
  const [extrasErrors, setExtrasErrors] = useState<JoinExtrasErrors>({});
  const modes = request.join_fields ?? NO_EXTRAS;
  const schema = request.edit_schema ?? null;
  const loaded = request.edit_schema !== undefined;
  const send = useMutation({
    mutationFn: async () => {
      const fields = await joinFieldsInput(makerspaceId, modes, extras);
      return resubmitAdmission(request.id, { application_answers: answers, ...(fields ? { join_fields: fields } : {}) });
    },
    onSuccess: () => { setEditing(false); void client.invalidateQueries({ queryKey: ["member"] }); },
  });
  const submit = () => {
    const next = validateCustomAnswers(schema, answers);
    const nextExtras = validateExtras(modes, extras, MAYBE_ON_FILE);
    setErrors(next);
    setExtrasErrors(nextExtras);
    if (!Object.keys(next).length && !Object.keys(nextExtras).length) send.mutate();
  };
  const body = send.error instanceof StructuredApiError ? send.error.body : null;
  return <div className="mt-3 grid gap-4">
    <Callout size="panel" tone="warn" lead={t`The team asked for changes.`}
      body={request.changes_note ? t`“${request.changes_note}”` : t`Review your answers and send them back.`}
      action={!editing && loaded ? { label: t`Edit my application`, onClick: () => setEditing(true) } : undefined} />
    <p className="text-sm text-muted">{t`You can edit and send your application back once, before it expires.`}</p>
    {!loaded ? <p className="text-sm text-muted" role="status">{t`Loading your application…`}</p> : null}
    {editing ? <form className="grid gap-4" aria-label={t`Edit your application`} onSubmit={(event) => { event.preventDefault(); submit(); }}>
      {schema ? <CustomFormFields schema={schema} answers={answers} onChange={setAnswers} disabled={send.isPending}
        errors={{ ...errors, ...customAnswerErrors(body?.application_answers) }} /> : null}
      {asksForAnything(modes) ? <JoinFormExtras modes={modes} value={extras} onChange={(next) => { setExtras(next); setExtrasErrors({}); }}
        disabled={send.isPending} onFile={MAYBE_ON_FILE} errors={{ ...serverExtrasErrors(body), ...extrasErrors }} /> : null}
      {!schema && !asksForAnything(modes) ? <p className="text-sm text-muted">{t`There are no questions to change. Send it back when you are ready.`}</p> : null}
      <div className="flex flex-wrap gap-3 [&>button]:flex-1 sm:[&>button]:flex-none">
        <button className="desk-button-brand" type="submit" disabled={send.isPending}>{send.isPending ? t`Sending…` : t`Send my application back`}</button>
        <button className="desk-button" type="button" disabled={send.isPending} onClick={() => setEditing(false)}>{t`Not now`}</button>
      </div>
      {send.error ? <p role="alert" className="text-sm text-danger">{send.error.message}</p> : null}
    </form> : null}
    {send.isSuccess ? <p role="status" className="text-sm text-success-ink">{t`Sent. The team will review your application again.`}</p> : null}
  </div>;
}
