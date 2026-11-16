import { t } from "@lingui/core/macro";
import { useEffect, useRef } from 'react'
import { FormV2Fields, type FormSchemaV2, type FormState, type FieldErrors } from '../../forms'
import { QUESTION_TYPES } from '../../forms/types'
import { CustomFormFields } from '../../forms/CustomFormFields'
import type { CustomFormSchema } from '../../forms/customFormTypes'
import type { FieldsProps, Prefill } from '../hackathonAdmission/types'

/** OpenAPI intentionally leaves authored JSON open. Check the shape before rendering it. */
export function formSchema(value: unknown): FormSchemaV2 {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(t`The event form is unavailable. Refresh its current revision.`)
  const form = value as Partial<FormSchemaV2>
  if (form.schema_version !== 2 || typeof form.form_id !== 'string' || !Number.isSafeInteger(form.revision)
    || !Array.isArray(form.questions) || form.questions.some(q => !q || typeof q.id !== 'string'
      || typeof q.label !== 'string' || !QUESTION_TYPES.includes(q.type))) throw new Error(t`This event form version is unsupported.`)
  return form as FormSchemaV2
}
export function ownerAnswers(value: unknown, schema: FormSchemaV2): Record<string, unknown> {
  if (value === undefined || value === null) return {}
  const questions = new Set(schema.questions.filter(q => q.type !== 'age_at_event').map(q => q.id))
  const rows = Array.isArray(value) ? value : typeof value === 'object' && 'answers' in value ? value.answers : null
  if (Array.isArray(rows)) return Object.fromEntries(rows.filter(row => row && typeof row.id === 'string'
    && questions.has(row.id) && row.type !== 'age_at_event' && 'value' in row).map(row => [row.id, row.value]))
  if (typeof value === 'object' && !Array.isArray(value)) return Object.fromEntries(Object.entries(value).filter(([id]) => questions.has(id)))
  throw new Error(t`Your submitted answers could not be loaded. Refresh this application.`)
}
export function filledState(schema: FormSchemaV2, state: FormState, prefill?: Prefill): FormState {
  if (!prefill) return state
  const derivations = { ...state.derivations }
  for (const q of schema.questions.filter(q => q.type === 'age_at_event')) {
    const input = prefill.derivation_inputs[q.id] as { source?: unknown } | undefined
    if (input?.source && !derivations[q.id]) derivations[q.id] = {
      source: input.source as FormState['derivations'][string]['source'],
      // Suggestions never assert that the member reviewed the event date.
      reviewed_event_date_revision: 0, reviewed_as_of_date: '',
    }
  }
  return { answers: { ...prefill.values, ...state.answers }, derivations,
    save_choices: { ...prefill.save_defaults, ...state.save_choices },
    saved_detail_versions: { ...prefill.saved_detail_versions, ...state.saved_detail_versions } }
}
export function ProgrammeFields({ schema, value, onChange, prefill, errors, disabled, savedDetailsAvailable }: FieldsProps) {
  const hydrated = useRef(false)
  useEffect(() => {
    if (!prefill || hydrated.current || Array.isArray(schema) || Object.keys(value.answers).length) return
    hydrated.current = true
    onChange(filledState(formSchema(schema), value, prefill))
  }, [prefill, schema, value, onChange])
  if (Array.isArray(schema)) return <CustomFormFields schema={schema as CustomFormSchema}
    answers={value.answers as Record<string, string>} onChange={answers => onChange({ ...value, answers })} disabled={disabled} />
  return <fieldset disabled={disabled}><FormV2Fields schema={formSchema(schema)} value={value} errors={errors as FieldErrors}
    onChange={next => {
      onChange({ ...next, save_choices: savedDetailsAvailable ? next.save_choices
        : Object.fromEntries(Object.keys(next.save_choices).map(key => [key, false])) })
    }} /></fieldset>
}
