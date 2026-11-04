import { useState } from "react";
import { createPortal } from "react-dom";

import { Modal } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers, type CustomFormSchema } from "../forms/customFormTypes";
import type { EventRegistration } from "./eventsApi";
import { useEditRegistrationAnswers } from "./eventToolsApi";
import { eventErrorText } from "./eventUi";

export function EventRegistrationAnswers({ row, schema, makerspaceId, eventId }: {
  row: EventRegistration; schema: CustomFormSchema; makerspaceId: number; eventId: number;
}) {
  const [open, setOpen] = useState(false);
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const edit = useEditRegistrationAnswers(makerspaceId, eventId);
  const serverErrors = customAnswerErrors(edit.error instanceof StructuredApiError ? edit.error.body.custom_answers : null);
  if (!schema?.length) return null;
  return <>
    <button className="desk-button" type="button" onClick={() => {
      edit.reset(); setErrors({});
      const allowedIds = new Set(schema.map((question) => question.id));
      setAnswers(Object.fromEntries((row.custom_answers?.answers ?? []).filter((answer) => allowedIds.has(answer.id)).map((answer) => [answer.id, answer.value])));
      setOpen(true);
    }}>Edit answers</button>
    {createPortal(<Modal open={open} title={`Edit answers: ${row.name}`} onClose={() => { if (!edit.isPending) setOpen(false); }}>
      <form className="grid gap-4" noValidate onSubmit={(e) => {
        e.preventDefault(); const nextErrors = validateCustomAnswers(schema, answers); setErrors(nextErrors);
        if (!Object.keys(nextErrors).length) edit.mutate({ registrationId: row.id, answers }, { onSuccess: () => setOpen(false) });
      }}>
        <CustomFormFields schema={schema} answers={answers} onChange={setAnswers} errors={{ ...serverErrors, ...errors }} disabled={edit.isPending} />
        {edit.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(edit.error)}</p> : null}
        <div className="flex justify-end"><button className="desk-button-primary" type="submit" disabled={edit.isPending}>{edit.isPending ? "Saving…" : "Save answers"}</button></div>
      </form>
    </Modal>, document.body)}
  </>;
}
