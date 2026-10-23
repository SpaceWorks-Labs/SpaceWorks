import type { CompoundInputProps } from "./types";

export function MoneyInput({ question: q, value, onChange, invalid, describedBy }: CompoundInputProps) {
  const object = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const currencies = q.money?.currencies ?? [];
  const currency = typeof object.currency === "string" ? object.currency : currencies[0] ?? "";
  const props = { className: "desk-input", "aria-invalid": invalid || undefined, "aria-describedby": describedBy };
  return <div className="grid gap-3 sm:grid-cols-2">
    <label className="grid gap-1 text-sm">{q.label} amount (minor units)
      <input {...props} type="text" inputMode="numeric" pattern="[0-9]+" required={q.required}
        value={typeof object.amount_minor === "number" || typeof object.amount_minor === "string" ? object.amount_minor : ""}
        onChange={e => {
          const raw = e.target.value;
          if (!raw) { onChange(undefined); return; }
          const amount = /^[0-9]+$/.test(raw) && Number.isSafeInteger(Number(raw)) ? Number(raw) : raw;
          onChange({ ...object, amount_minor: amount, currency });
        }} />
    </label>
    <label className="grid gap-1 text-sm">{q.label} currency
      <select {...props} required={q.required} value={currency} onChange={e => onChange({ ...object, currency: e.target.value })}>
        {currencies.map(code => <option key={code} value={code}>{code}</option>)}
      </select>
    </label>
    <p className="text-xs text-muted sm:col-span-2">Enter a whole number of the currency’s smallest units. No currency conversion is applied.</p>
  </div>;
}
