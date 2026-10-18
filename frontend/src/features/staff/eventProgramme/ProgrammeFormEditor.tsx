import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { FormBuilderV2, FormV2Fields, type FormSchemaV2, type FormState } from "../../forms";
import { CustomFormBuilder } from "../../forms/CustomFormBuilder";
import { CustomFormFields } from "../../forms/CustomFormFields";
import { customAnswerErrors, type CustomAnswers, type VersionedCustomFormSchema } from "../../forms/customFormTypes";
import { upgradeLegacyForm } from "../../forms/upgradeLegacyForm";
import { eventErrorText } from "../eventUi";
import { DirtySaveBar } from "./DirtySaveBar";
import { useOperationId } from "./useOperationId";
import { isProtectedDenial, sessionScope, useClearDeniedQuery } from "./sessionScope";

type FormDocument = { version: number; schema: VersionedCustomFormSchema };
type Selector = { posting_id?: number; round_id?: number; track_id?: number };
function editorSchema(schema: VersionedCustomFormSchema) {
  if (!schema || Array.isArray(schema)) return schema;
  const { event_context: _context, ...editor } = schema;
  return editor as FormSchemaV2;
}
export function ProgrammeFormEditor({ eventId, formKey, selector = {} }: { eventId: number; formKey: "registration" | "application" | "volunteer" | "mentor" | "round" | "track"; selector?: Selector }) {
  const path = `/admin/events/${eventId}/forms/${formKey}/`;
  const client = useQueryClient();
  const key = ["event-form-v2", eventId, formKey, selector, ...sessionScope()];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<FormDocument>(`${path}?${new URLSearchParams(Object.entries(selector).map(([k, v]) => [k, String(v)]))}`) });
  const [draft, setDraft] = useState<FormDocument | null>(null);
  const [sample, setSample] = useState<FormState>({ answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {} });
  const [preview, setPreview] = useState(false);
  const operationId = useOperationId();
  const row = draft ?? query.data;
  const validation = useMutation({ mutationFn: () => staffRequest<{ valid: boolean; errors: Record<string, string>; visible_question_ids: string[] }>(`${path}validate/`, { method: "POST", body: JSON.stringify({ ...selector, schema: editorSchema(row?.schema ?? null), sample_answers: sample.answers }) }) });
  const save = useMutation({ mutationFn: (command: { operation_id: string; expected_version: number; schema: VersionedCustomFormSchema }) => staffRequest<FormDocument>(path, { method: "PUT", headers: { "Idempotency-Key": command.operation_id }, body: JSON.stringify({ ...command, ...selector }) }), onSuccess: data => { client.setQueryData(key, data); setDraft(null); } });
  const denied = [query.error, save.error, validation.error].some(isProtectedDenial);
  useClearDeniedQuery([query.error, save.error, validation.error].find(isProtectedDenial), key);
  useEffect(() => { if (denied) { setDraft(null); setSample({ answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {} }); setPreview(false); } }, [denied]);
  if (denied) return <p role="alert" className="text-sm text-danger">This form is no longer available for your access.</p>;
  return <section className="grid gap-4" aria-label="Registration form editor"><h3 className="title-section">Questions and saved details</h3>
    {query.isLoading ? <p role="status">Loading form…</p> : null}{query.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(query.error)}</p> : null}
    {row ? <>{row.schema && !Array.isArray(row.schema) ? <FormBuilderV2 value={row.schema} onChange={schema => { setDraft({ ...row, schema }); validation.reset(); }} errors={customAnswerErrors(validation.data?.errors)} /> : <><CustomFormBuilder value={row.schema} onChange={schema => setDraft({ ...row, schema })} /><button className="desk-button justify-self-start" type="button" onClick={() => setDraft({ ...row, schema: upgradeLegacyForm(row.schema as import("../../forms/customFormTypes").CustomFormSchema, `${formKey}-${eventId}`) })}>Upgrade draft to form v2</button><p className="text-sm text-muted">Upgrading changes new submissions to stable option IDs and enables conditions. Existing answer snapshots keep their original revision.</p></>}
      <div className="flex flex-wrap gap-2"><button className="desk-button" type="button" aria-expanded={preview} onClick={() => setPreview(!preview)}>Preview questions</button><button className="desk-button" type="button" disabled={validation.isPending} onClick={() => validation.mutate()}>Validate sample</button></div>
      {preview ? row.schema && !Array.isArray(row.schema) ? <FormV2Fields schema={row.schema} value={sample} onChange={setSample} /> : <CustomFormFields schema={row.schema} answers={sample.answers as CustomAnswers} onChange={answers => setSample({ ...sample, answers })} /> : null}
      {validation.data ? <p role="status" className="text-sm">{validation.data.valid ? "Sample is valid." : "Review sample answers and conditions."}</p> : null}
      {validation.error ? <p role="alert" className="text-sm text-danger">{eventErrorText(validation.error)}</p> : null}
      <DirtySaveBar dirty={Boolean(draft)} pending={save.isPending} error={save.error ? eventErrorText(save.error) : undefined} onDiscard={() => { setDraft(null); save.reset(); }} onSave={() => save.mutate({ operation_id: operationId(row), expected_version: row.version, schema: editorSchema(row.schema) })} />
    </> : null}
  </section>;
}
