import { t } from "@lingui/core/macro";
/** How a maintenance cost was paid: the finance ledger's own methods (#102: costs go to the ledger). */
export const COST_METHODS = [
  { value: "", label: t`Not recorded` }, { value: "cash", label: t`Cash` }, { value: "upi", label: "UPI" }, { value: "bank_transfer", label: t`Bank transfer` },
  { value: "card", label: t`Card` }, { value: "cheque", label: t`Cheque` }, { value: "online", label: t`Online` },
  { value: "other", label: t`Other` },
];

export type CostValue = { cost: string; method: string };
export const EMPTY_COST: CostValue = { cost: "", method: "" };

/** The request fields for a cost: the method only when one was chosen (the server records "other"). */
export function costBody({ cost, method }: CostValue): { cost: string | null; cost_method?: string } {
  const amount = cost.trim();
  return amount ? { cost: amount, ...(method ? { cost_method: method } : {}) } : { cost: null };
}

/** Cost plus "Paid by"; a cost above zero is recorded as maintenance spending in the finance ledger. */
export function MaintenanceCostInput({ value, onChange }: { value: CostValue; onChange: (value: CostValue) => void }) {
  return <>
    <label className="eyebrow grid gap-1">
      {t`Cost (optional)`}<input className="desk-input" type="number" min="0" step="any" value={value.cost} aria-describedby="maintenance-cost-hint"
        onChange={event => onChange({ ...value, cost: event.target.value })} />
    </label>
    <label className="eyebrow grid gap-1">
      {t`Paid by`}<select className="desk-input" value={value.method} disabled={!value.cost.trim()}
        onChange={event => onChange({ ...value, method: event.target.value })}>
        {COST_METHODS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
    <p id="maintenance-cost-hint" className="text-sm text-muted sm:col-span-2">{t`A cost is recorded as maintenance spending in the finance ledger.`}</p>
  </>;
}
