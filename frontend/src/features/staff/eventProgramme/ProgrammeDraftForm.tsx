import { useEffect, useState } from 'react'
import { FormBuilderV2, FormV2Fields, type FormState } from '../../forms'
import { CustomFormBuilder } from '../../forms/CustomFormBuilder'
import { formSchema } from '../../events/programme/formBridge'
import type { RoleFormBuilder } from '../mentorDesk/PostingEditor'

export function ProgrammeDraftForm({ value, onChange }: { value: unknown; onChange: (value: unknown) => void }) {
  const [blank] = useState(() => ({ schema_version: 2 as const, form_id: crypto.randomUUID(), revision: 1, questions: [] }))
  useEffect(() => { if (value && typeof value === 'object' && !Array.isArray(value) && !('schema_version' in value)) onChange(blank) }, [value, onChange, blank])
  if (Array.isArray(value)) return <CustomFormBuilder value={value} onChange={onChange} />
  const schema = value && typeof value === 'object' && 'schema_version' in value ? formSchema(value) : blank
  return <FormBuilderV2 value={schema} onChange={onChange} />
}
export const renderContributorBuilder: RoleFormBuilder = ({ schema, onChange, disabled }) => <fieldset disabled={disabled}>
  <ProgrammeDraftForm value={schema} onChange={value => onChange(value as Record<string, unknown>)} />
</fieldset>
export function RoundAnswerFields({ schema, answers, onChange, disabled }: { schema: unknown; answers: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void; disabled: boolean }) {
  const value: FormState = { answers, derivations: {}, save_choices: {}, saved_detail_versions: {} }
  return <fieldset disabled={disabled}><FormV2Fields schema={formSchema(schema)} value={value} onChange={next => onChange(next.answers)} /></fieldset>
}
