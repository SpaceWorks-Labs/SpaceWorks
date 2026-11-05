import { useState } from 'react';
import { Field } from '../../../components/ui';
import type { PayeeTemplate } from '../../../generated/api';

const METHOD_LABELS: Record<string, string> = {
  bank_transfer: 'Bank transfer', upi: 'UPI', paypal: 'PayPal', wise: 'Wise', cash: 'Cash', cheque: 'Cheque', other: 'Other',
};
const FIELD_LABELS: Record<string, string> = {
  holder_name: 'Account holder name', account_number: 'Account number', ifsc: 'IFSC code', bank_name: 'Bank name',
  upi_id: 'UPI ID', routing_number: 'Routing number', account_type: 'Account type', iban: 'IBAN', swift: 'SWIFT / BIC',
  bsb: 'BSB', institution_number: 'Institution number', transit_number: 'Transit number', bank_code: 'Bank code',
  branch_code: 'Branch code', payout_email: 'Payout email', delivery_instructions: 'Delivery instructions',
};
const PAN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

export type ClaimFields = { country: string; method: string; details: Record<string, string>; pan?: string };

/** Where to pay this winner, from the space's accepted payee templates (G4), plus an optional PAN (#181). */
export function PrizeClaimForm({ templates, askPan, pending, onSubmit, onCancel }: {
  templates: PayeeTemplate[]; askPan: boolean; pending: boolean; onSubmit: (fields: ClaimFields) => void; onCancel: () => void;
}) {
  const [choice, setChoice] = useState(templates.length === 1 ? 0 : -1);
  const [details, setDetails] = useState<Record<string, string>>({});
  const [pan, setPan] = useState('');
  const template = choice >= 0 ? templates[choice] : undefined;
  if (!templates.length) {
    return <p className="text-sm text-muted" role="status">This space has not chosen how it pays winners yet. Ask the organisers.</p>;
  }
  const missing = !template || template.fields.some(field => field.required && !(details[field.key] ?? '').trim());
  const panValue = pan.trim().toUpperCase();
  const panBad = Boolean(panValue) && !PAN.test(panValue);
  const submit = () => {
    if (!template || missing || panBad) return;
    const values = Object.fromEntries(template.fields.map(field => [field.key, (details[field.key] ?? '').trim()]));
    onSubmit({ country: template.country, method: template.method, details: values, ...(askPan ? { pan: panValue } : {}) });
    setDetails({}); setPan('');
  };
  return <form className="grid gap-3 rounded-xl border border-line p-4" aria-label="Payee details"
    onSubmit={event => { event.preventDefault(); submit(); }}>
    <fieldset className="grid gap-3" disabled={pending}>
      <legend className="font-semibold">Where should we pay you?</legend>
      <Field label="Country and method">
        <select className="desk-input min-h-11" value={choice}
          onChange={event => { setChoice(Number(event.target.value)); setDetails({}); }}>
          <option value={-1}>Choose how to be paid</option>
          {templates.map((row, index) => <option key={row.template_key + row.country + row.method} value={index}>
            {row.country} · {METHOD_LABELS[row.method] ?? row.method}</option>)}
        </select>
      </Field>
      {template?.fields.map(field => <Field key={field.key} label={FIELD_LABELS[field.key] ?? field.key.replace(/_/g, ' ')}>
        <input className="desk-input min-h-11" autoComplete="off" maxLength={200} required={field.required}
          value={details[field.key] ?? ''} onChange={event => setDetails(value => ({ ...value, [field.key]: event.target.value }))} />
      </Field>)}
      {askPan ? <Field label="PAN (optional)" hint="Five letters, four digits, one letter; stored encrypted and shown only masked."
        error={panBad ? 'Enter a valid PAN, for example ABCDE1234F.' : undefined}>
        <input className="desk-input min-h-11" autoComplete="off" maxLength={10} value={pan}
          onChange={event => setPan(event.target.value.toUpperCase())} />
      </Field> : null}
      <p className="text-sm text-muted">Your details are encrypted. Organisers see them masked; finance reads them only to pay you.</p>
      <div className="flex flex-wrap gap-2">
        <button type="submit" className="desk-button-primary min-h-11" disabled={missing || panBad}>Save payee details</button>
        <button type="button" className="desk-button min-h-11" onClick={onCancel}>Cancel</button>
      </div>
    </fieldset>
  </form>;
}
