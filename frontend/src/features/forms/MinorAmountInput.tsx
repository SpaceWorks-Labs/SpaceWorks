import { useState, type InputHTMLAttributes } from "react";

import { currencyExponent, decimalToMinor, minorToDecimal } from "../../lib/money";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type" | "pattern" | "inputMode"> & {
  /** The stored amount in the currency's minor units (cents, paise); null/NaN shows an empty box. */
  value: number | null | undefined;
  currency: string;
  /** Receives minor units, or null while the box is empty or not a valid amount in this currency. */
  onChange: (minor: number | null) => void;
  allowNegative?: boolean;
};

/**
 * A decimal money box: people type "12.50", the form keeps integer minor units (1250). The typed text is
 * local state so a half-typed "12." survives a re-render; a different `value` from the parent replaces it.
 */
export function MinorAmountInput({ value, currency, onChange, allowNegative, className, ...rest }: Props) {
  const stored = typeof value === "number" && Number.isSafeInteger(value) ? value : null;
  const [text, setText] = useState(() => minorToDecimal(stored, currency));
  // Re-sync only when the parent's value or currency itself changes and no longer matches the typed text.
  const [seen, setSeen] = useState({ value: stored, currency });
  if (seen.value !== stored || seen.currency !== currency) {
    setSeen({ value: stored, currency });
    if (seen.currency !== currency || decimalToMinor(text, currency) !== stored) setText(minorToDecimal(stored, currency));
  }
  const exponent = currencyExponent(currency);
  const pattern = `${allowNegative ? "-?" : ""}[0-9]+${exponent ? `(\\.[0-9]{0,${exponent}})?` : ""}`;
  return <input {...rest} className={className ?? "desk-input"} type="text" inputMode="decimal" pattern={pattern}
    value={text} onChange={event => {
      const next = event.target.value;
      const minor = decimalToMinor(next, currency);
      setText(next);
      onChange(minor !== null && (allowNegative || minor >= 0) ? minor : null);
    }} />;
}
