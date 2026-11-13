import { t } from "@lingui/core/macro";
import { Plus, Trash2 } from 'lucide-react';
import { Field } from '../../../components/ui';
import type { Criterion } from './types';

export function newCriterion(index: number): Criterion {
  return { key: `criterion_${index}`, label: '', weight: '1.0000',
    anchors: { '1': 'Needs development', '2': 'Early progress', '3': 'Meets the criterion', '4': 'Strong work', '5': 'Exceptional work' } };
}
export function RubricEditor({ value, onChange, disabled }: { value: Criterion[]; onChange: (value: Criterion[]) => void; disabled: boolean }) {
  const update = (index: number, change: Partial<Criterion>) => onChange(value.map((row, i) => i === index ? { ...row, ...change } : row));
  return <fieldset className="grid gap-4" disabled={disabled}>
    <legend className="title-section mb-3">{t`Anchored rubric`}</legend>
    <p className="text-sm text-muted">{t`Each criterion has a positive weight and a clear description for every score. Opening the round freezes this rubric.`}</p>
    {value.map((row, index) => <fieldset key={index} className="grid gap-3 rounded-xl border border-line p-4">
      <legend className="px-1 text-sm font-semibold">{t`Criterion ${index + 1}`}</legend>
      <Field label={t`Criterion key`}><input className="desk-input min-h-11" required pattern="[a-z][a-z0-9_-]{0,63}" value={row.key} onChange={e => update(index, { key: e.target.value })} /></Field>
      <Field label={t`Criterion label`}><input className="desk-input min-h-11" required maxLength={160} value={row.label} onChange={e => update(index, { label: e.target.value })} /></Field>
      <Field label={t`Weight`}><input className="desk-input min-h-11" type="number" min="0.0001" max="999999" step="0.0001" required value={row.weight} onChange={e => update(index, { weight: e.target.value })} /></Field>
      {[1, 2, 3, 4, 5].map(score => <Field key={score} label={t`Score ${score} description`}>
        <input className="desk-input min-h-11" required maxLength={500} value={row.anchors[String(score)] ?? ''}
          onChange={e => update(index, { anchors: { ...row.anchors, [score]: e.target.value } })} />
      </Field>)}
      {value.length > 1 ? <button type="button" className="desk-button min-h-11" onClick={() => onChange(value.filter((_, i) => i !== index))}>
        <Trash2 size={18} aria-hidden="true" /> {t` Remove criterion ${index + 1}`}</button> : null}
    </fieldset>)}
    <button type="button" className="desk-button min-h-11" disabled={value.length >= 30} onClick={() => onChange([...value, newCriterion(value.length + 1)])}>
      <Plus size={18} aria-hidden="true" /> {t` Add criterion`}</button>
  </fieldset>;
}
