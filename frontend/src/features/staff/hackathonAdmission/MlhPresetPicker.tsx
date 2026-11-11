import { t } from "@lingui/core/macro";
/** F supplies approved, age-free preset schemas; A owns selecting an application preset. */
export interface ProgrammeMlhPreset {
  id: string; label: string
  schema: { schema_version: 2; form_id: string; revision: number; questions: unknown[] }
}
export function MlhPresetPicker({ presets, value, disabled, onSelect }: {
  presets: readonly ProgrammeMlhPreset[]; value: Record<string, unknown>; disabled: boolean
  onSelect: (schema: ProgrammeMlhPreset['schema'] | null) => void
}) {
  const current = presets.find(p => p.schema.form_id === value.form_id && p.schema.revision === value.revision)?.id
  const configured = Object.keys(value).length > 0
  return <fieldset className="grid gap-3" disabled={disabled}><legend className="title-section mb-3">{t`Optional MLH sharing`}</legend>
    <label className="grid gap-1 text-sm text-ink">{t`Application preset`}<select className="desk-input" value={current ?? (configured ? 'current' : '')}
      onChange={event => onSelect(presets.find(p => p.id === event.target.value)?.schema ?? null)}>
      <option value="">{t`Sharing off · keep the current application form`}</option>
      {configured && !current ? <option value="current" disabled>{t`Current MLH preset`}</option> : null}
      {presets.map(preset => <option key={preset.id} value={preset.id}>{preset.label}</option>)}
    </select></label>
    <p className="text-sm text-muted">{presets.length
      ? t`Choosing a preset replaces the application form below. Each applicant can separately opt in to sharing; consent starts off. Review the questions before enabling applications.`
      : t`No MLH presets are available on this server, so MLH sharing cannot be turned on here.`}</p>
  </fieldset>
}
