import type { Rubric } from './types'

export function RubricEditor({ value, onChange }: { value: Rubric; onChange: (rubric: Rubric) => void }) {
  const change = (index: number, key: string, text: string) => onChange({ ...value, revision: value.revision + 1,
    criteria: value.criteria.map((criterion, i) => i === index ? key === 'label' ? { ...criterion, label: text }
      : { ...criterion, anchors: { ...criterion.anchors, [key]: text } } : criterion) })
  return <fieldset className="grid gap-4"><legend className="title-section mb-3">Anchored review rubric</legend>
    {value.criteria.map((criterion, index) => <div key={criterion.key} className="grid gap-2 rounded-xl border border-line p-4">
      <label className="grid gap-1 text-sm text-ink">Criterion<input className="desk-input" maxLength={200} value={criterion.label} onChange={e => change(index, 'label', e.target.value)} /></label>
      {[1, 2, 3, 4, 5].map(score => <label className="grid gap-1 text-sm text-ink" key={score}>Score {score} anchor<input className="desk-input" maxLength={500} value={criterion.anchors[score] ?? ''} onChange={e => change(index, String(score), e.target.value)} /></label>)}
      <button className="desk-button-danger-outline justify-self-start" type="button" onClick={() => onChange({ ...value, revision: value.revision + 1, criteria: value.criteria.filter((_, i) => i !== index) })}>Remove criterion</button>
    </div>)}
    <button className="desk-button justify-self-start" type="button" disabled={value.criteria.length >= 20} onClick={() => onChange({ ...value, revision: value.revision + 1,
      criteria: [...value.criteria, { key: 'criterion_' + crypto.randomUUID().replace(/-/g, '').slice(0, 24), label: 'New criterion', anchors: { '1': '', '2': '', '3': '', '4': '', '5': '' } }] })}>Add criterion</button>
  </fieldset>
}
