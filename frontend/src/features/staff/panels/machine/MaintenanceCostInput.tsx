/** How a maintenance cost was paid: the finance ledger's own methods (#102: costs go to the ledger). */
export const COST_METHODS = [
  { value: "", label: "Not recorded" }, { value: "cash", label: "Cash" }, { value: "upi", label: "UPI" }, { value: "bank_transfer", label: "Bank transfer" },
  { value: "card", label: "Card" }, { value: "cheque", label: "Cheque" }, { value: "online", label: "Online" },
  { value: "other", label: "Other" },
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
      Cost (optional)
      <input className="desk-input" type="number" min="0" step="0.01" value={value.cost} aria-describedby="maintenance-cost-hint"
        onChange={event => onChange({ ...value, cost: event.target.value })} />
    </label>
    <label className="eyebrow grid gap-1">
      Paid by
      <select className="desk-input" value={value.method} disabled={!value.cost.trim()}
        onChange={event => onChange({ ...value, method: event.target.value })}>
        {COST_METHODS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
    </label>
    <p id="maintenance-cost-hint" className="text-sm text-muted sm:col-span-2">A cost is recorded as maintenance spending in the finance ledger.</p>
  </>;
}
