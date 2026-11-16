import { t } from "@lingui/core/macro";
import { useState } from "react";
import { currencyExponent, decimalToMinor, minorToDecimal } from "../../lib/money";
import type { CompoundInputProps } from "./types";

/**
 * People type a decimal amount ("12.50"); the answer stays `{ amount_minor, currency }` in integer minor
 * units. Text that is not a valid amount in the chosen currency is passed through as a string so the
 * server's field error names it, rather than being silently rounded.
 */
export function MoneyInput({ question: q, value, onChange, invalid, describedBy }: CompoundInputProps) {
  const object = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const currencies = q.money?.currencies ?? [];
  const currency = typeof object.currency === "string" ? object.currency : currencies[0] ?? "";
  const stored = object.amount_minor;
  const [text, setText] = useState(() => typeof stored === "number" ? minorToDecimal(stored, currency) : typeof stored === "string" ? stored : "");
  const [seen, setSeen] = useState<unknown>(stored);
  if (seen !== stored) {
    setSeen(stored);
    if ((decimalToMinor(text, currency) ?? (text || undefined)) !== stored) setText(typeof stored === "number" ? minorToDecimal(stored, currency) : typeof stored === "string" ? stored : "");
  }
  const emit = (raw: string, code: string) => {
    setText(raw);
    if (!raw) { onChange(undefined); return; }
    onChange({ ...object, amount_minor: decimalToMinor(raw, code) ?? raw, currency: code });
  };
  const exponent = currencyExponent(currency);
  const props = { className: "desk-input", "aria-invalid": invalid || undefined, "aria-describedby": describedBy };
  return <div className="grid gap-3 sm:grid-cols-2">
    <label className="grid gap-1 text-sm">{t`${q.label} amount`}<input {...props} type="text" inputMode="decimal" required={q.required}
        pattern={exponent ? `[0-9]+(\\.[0-9]{0,${exponent}})?` : "[0-9]+"} value={text} onChange={e => emit(e.target.value, currency)} />
    </label>
    <label className="grid gap-1 text-sm">{t`${q.label} currency`}
      <select {...props} required={q.required} value={currency} onChange={e => text ? emit(text, e.target.value) : onChange({ ...object, currency: e.target.value })}>
        {currencies.map(code => <option key={code} value={code}>{code}</option>)}
      </select>
    </label>
    <p className="text-xs text-muted sm:col-span-2">{t`Enter the amount in the chosen currency, for example 12.50. No currency conversion is applied.`}</p>
  </div>;
}
