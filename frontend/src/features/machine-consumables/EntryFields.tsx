import { t } from "@lingui/core/macro";

import { ATTRIBUTE_LABELS } from "./attributeLabels";
import { isWhole, quantityProblem, unitText, type EntryRow, type EntryValues } from "./entries";

/** One amount field per profile row, with the attribute pickers the row asks about. Shared by the member request and the staff job. */
export function EntryFields({ rows, values, onChange, disabled }: { rows: EntryRow[]; values: EntryValues; onChange: (values: EntryValues) => void; disabled?: boolean }) {
  const set = (key: string, patch: Partial<EntryValues[string]>) => onChange({ ...values, [key]: { ...(values[key] ?? { quantity: "", attributes: {} }), ...patch } });
  return <div className="grid gap-4">{rows.map(row => {
    const quantity = values[row.key]?.quantity ?? "";
    const problem = quantityProblem(row, quantity);
    const unit = unitText(row.unit);
    const attributes = Object.entries(row.attributes) as [keyof typeof ATTRIBUTE_LABELS, string[]][];
    return <fieldset key={row.key} disabled={disabled} className="grid gap-2 rounded-lg border border-line p-3 sm:grid-cols-2">
      <legend className="px-1 text-sm font-semibold text-ink">{row.name}{row.required ? <span className="text-muted"> · {t`required`}</span> : null}</legend>
      <label className="grid gap-1 text-sm">{t`Amount (${unit})`}
        <input className="desk-input w-full tabular-nums" inputMode={isWhole(row.unit) ? "numeric" : "decimal"} type="number" min={isWhole(row.unit) ? 1 : 0} step={isWhole(row.unit) ? 1 : "any"}
          value={quantity} aria-invalid={problem ? true : undefined} onChange={event => set(row.key, { quantity: event.target.value })} />
        {problem ? <span role="alert" className="text-xs text-danger">{problem}</span> : null}</label>
      {attributes.map(([attribute, choices]) => {
        const label = ATTRIBUTE_LABELS[attribute]();
        const value = values[row.key]?.attributes[attribute] ?? "";
        const change = (next: string) => set(row.key, { attributes: { ...values[row.key]?.attributes, [attribute]: next } });
        return choices.length ? <label key={attribute} className="grid gap-1 text-sm">{label}
          <select className="desk-input w-full" value={value} onChange={event => change(event.target.value)}><option value="">{t`Choose`}</option>
            {choices.map(choice => <option key={choice} value={choice}>{choice}</option>)}</select></label>
          : <label key={attribute} className="grid gap-1 text-sm">{label}<input className="desk-input w-full" maxLength={80} value={value} onChange={event => change(event.target.value)} /></label>;
      })}
    </fieldset>;
  })}</div>;
}
