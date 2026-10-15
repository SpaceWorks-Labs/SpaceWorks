import type { InputHTMLAttributes } from "react";
import { Minus, Plus } from "lucide-react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "onChange" | "min" | "max" | "step"> & {
  value: string | number;
  onValueChange: (value: string) => void;
  min?: number;
  max?: number;
  /** Names the field in the − / + button tooltips, e.g. "returned". */
  label?: string;
};

/**
 * A whole-number field with 44px − and + buttons on either side, so counter staff can set counts
 * one-handed on a phone. The buttons only nudge the same string value the caller already validates;
 * they are hidden from assistive tech and the tab order because the spinbutton itself already takes
 * arrow keys, and a wrapping <label> would otherwise fold their names into the field's name.
 */
export function QuantityStepper({ value, onValueChange, min = 0, max, label, disabled, className = "", ...input }: Props) {
  const current = String(value).trim() === "" ? Number.NaN : Number(value);
  const base = Number.isFinite(current) ? current : min;
  const clamp = (next: number) => String(Math.min(max ?? Infinity, Math.max(min, next)));
  // From an empty field, + lands on the first countable unit and − on the minimum.
  const nudge = (delta: number) => onValueChange(Number.isFinite(current) ? clamp(Math.trunc(current) + delta) : clamp(delta > 0 ? Math.max(min, 1) : min));
  const suffix = label ? ` ${label}` : "";
  const button = "desk-button w-11 shrink-0 px-0";
  // The input comes first in the DOM so a wrapping <label> still names it (a label names its
  // FIRST labelable descendant, and buttons are labelable); `order` puts the − button visually left.
  return <span className={`flex w-48 min-w-0 max-w-full shrink-0 items-stretch gap-1 ${className}`}>
    <input {...input} type="number" inputMode="numeric" step={1} min={min} max={max} value={value} disabled={disabled}
      onChange={event => onValueChange(event.target.value)} className="desk-input order-2 w-full min-w-0 flex-1 px-1 text-center tabular-nums" />
    <button type="button" tabIndex={-1} className={`${button} order-1`} aria-hidden="true" title={`Decrease${suffix}`}
      disabled={disabled || base <= min} onClick={() => nudge(-1)}><Minus aria-hidden="true" className="h-4 w-4" /></button>
    <button type="button" tabIndex={-1} className={`${button} order-3`} aria-hidden="true" title={`Increase${suffix}`}
      disabled={disabled || (max !== undefined && base >= max)} onClick={() => nudge(1)}><Plus aria-hidden="true" className="h-4 w-4" /></button>
  </span>;
}
