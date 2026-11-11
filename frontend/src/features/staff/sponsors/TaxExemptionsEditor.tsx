import { t } from "@lingui/core/macro";

import { Field } from "../../../components/ui";
import { TAX_SCHEMES, type TaxExemption } from "./staffDonationsApi";

const blank: TaxExemption = { scheme: "in_80g", number: "", valid_from: "", valid_until: "" };

/** Decision 242(m): the typed list of tax-exemption registrations (scheme, number, validity). */
export function TaxExemptionsEditor({ rows, onChange }: { rows: TaxExemption[]; onChange: (rows: TaxExemption[]) => void }) {
  const update = (index: number, patch: Partial<TaxExemption>) =>
    onChange(rows.map((row, at) => at === index ? { ...row, ...patch } : row));
  return <fieldset className="grid gap-3">
    <legend className="text-sm font-semibold text-ink">{t`Tax-exemption registrations`}</legend>
    <p className="text-sm text-muted">{t`Givers can ask for a tax receipt while at least one of these is valid. India 12A alone does not allow tax receipts; add your 80G registration too.`}</p>
    {rows.map((row, index) => <div key={index} className="grid gap-3 rounded-md border border-line p-3 sm:grid-cols-2"
      role="group" aria-label={t`Registration ${index + 1}`}>
      <Field label={t`Scheme`}><select className="desk-input" value={row.scheme}
        onChange={event => update(index, { scheme: event.target.value })}>
        {Object.entries(TAX_SCHEMES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
      <Field label={t`Registration number`}><input className="desk-input" required maxLength={64} value={row.number}
        onChange={event => update(index, { number: event.target.value })} /></Field>
      <Field label={t`Valid from (optional)`}><input className="desk-input" type="date" value={row.valid_from}
        onChange={event => update(index, { valid_from: event.target.value })} /></Field>
      <Field label={t`Valid until (optional)`}><input className="desk-input" type="date" value={row.valid_until}
        onChange={event => update(index, { valid_until: event.target.value })} /></Field>
      <button type="button" className="desk-button-ghost justify-self-start"
        onClick={() => onChange(rows.filter((_, at) => at !== index))}>{t`Remove registration`}</button>
    </div>)}
    {rows.length < 10 ? <button type="button" className="desk-button justify-self-start"
      onClick={() => onChange([...rows, { ...blank }])}>{t`Add a registration`}</button> : null}
  </fieldset>;
}
