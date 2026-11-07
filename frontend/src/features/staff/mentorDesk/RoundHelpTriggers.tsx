import { t } from "@lingui/core/macro";
import { Field } from '../../../components/ui'
import { SetupText } from './setupFields'

export interface HelpTrigger { key: string; question_id: string; op: 'eq' | 'contains'; value: string | boolean; type_key: string }
export function RoundHelpTriggers({ rules, onChange }: { rules: HelpTrigger[]; onChange: (rules: HelpTrigger[]) => void }) {
  const update = (index: number, fields: Partial<HelpTrigger>) => onChange(rules.map((rule, i) => i === index ? { ...rule, ...fields } : rule))
  return <fieldset className="grid gap-4"><legend className="mb-2 font-semibold">{t`Conditional help requests`}</legend>
    <p className="text-sm text-muted">{t`Use question IDs from the shared form. Matching answers create a deduplicated request in an existing help category.`}</p>
    {rules.map((rule, index) => <div key={index} className="grid gap-3 rounded-xl border border-line p-4">
      <SetupText label={t`Trigger ${index + 1} key`} value={rule.key} onChange={key => update(index, { key })} required />
      <SetupText label={t`Trigger ${index + 1} question ID`} value={rule.question_id} onChange={question_id => update(index, { question_id })} required />
      <Field label={t`Trigger ${index + 1} match`}><select className="desk-input min-h-11" value={rule.op} onChange={event => update(index, { op: event.target.value as HelpTrigger['op'] })}><option value="eq">{t`Equals`}</option><option value="contains">{t`Selected choices contain`}</option></select></Field>
      <Field label={t`Trigger ${index + 1} answer type`}><select className="desk-input min-h-11" value={typeof rule.value} onChange={event => update(index, { value: event.target.value === 'boolean' ? true : '' })}><option value="boolean">{t`Yes/no`}</option><option value="string">{t`Text or choice key`}</option></select></Field>
      {typeof rule.value === 'boolean' ? <Field label={t`Trigger ${index + 1} answer`}><select className="desk-input min-h-11" value={String(rule.value)} onChange={event => update(index, { value: event.target.value === 'true' })}><option value="true">{t`Yes`}</option><option value="false">{t`No`}</option></select></Field>
        : <SetupText label={t`Trigger ${index + 1} answer`} value={rule.value} onChange={value => update(index, { value })} required />}
      <SetupText label={t`Trigger ${index + 1} help category key`} value={rule.type_key} onChange={type_key => update(index, { type_key })} required />
      <button type="button" className="desk-button min-h-11" onClick={() => onChange(rules.filter((_, i) => i !== index))}>{t`Remove trigger ${index + 1}`}</button>
    </div>)}
    <button type="button" className="desk-button min-h-11" disabled={rules.length >= 10} onClick={() => onChange([...rules, { key: '', question_id: '', op: 'eq', value: true, type_key: '' }])}>{t`Add help trigger`}</button>
  </fieldset>
}
