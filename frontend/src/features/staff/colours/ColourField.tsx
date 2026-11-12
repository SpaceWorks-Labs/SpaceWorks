import { t } from "@lingui/core/macro";
import { useId } from "react";
import { rgb } from "../../../lib/brandColours";
import { toHex } from "../../../lib/colourFix";

type EyeDropperCtor = new () => { open: () => Promise<{ sRGBHex: string }> };

type Props = { label: string; helper: string; value: string; placeholder: string; disabled?: boolean; invalid?: boolean; onChange: (value: string) => void };

/** Picker + hex field + eyedropper (where the browser offers one) for one space colour. */
export function ColourField({ label, helper, value, placeholder, disabled, invalid, onChange }: Props) {
  const id = useId();
  const parsed = rgb(value.trim());
  const EyeDropper = (globalThis as { EyeDropper?: EyeDropperCtor }).EyeDropper;
  const pick = () => { if (EyeDropper) void new EyeDropper().open().then((r) => onChange(r.sRGBHex)).catch(() => undefined); };
  return <div className="grid gap-1 text-sm">
    <label htmlFor={`${id}-hex`} className="font-semibold text-ink">{label}</label>
    <div className="flex flex-wrap items-center gap-2">
      <input type="color" aria-label={t`${label} picker`} className="h-11 w-11 shrink-0 cursor-pointer rounded-control border border-outline bg-panel p-1"
        disabled={disabled} value={parsed ? toHex(parsed) : "#006e63"} onChange={(event) => onChange(event.target.value)} />
      <input id={`${id}-hex`} aria-describedby={`${id}-help`} aria-invalid={invalid || undefined} className="desk-input min-w-[9rem] flex-1"
        placeholder={placeholder} value={value} disabled={disabled} spellCheck={false} onChange={(event) => onChange(event.target.value)} />
      {EyeDropper ? <button type="button" className="desk-button" disabled={disabled} onClick={pick}>{t`Eyedropper`}</button> : null}
      <button type="button" className="min-h-11 px-2 text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:text-muted disabled:no-underline" aria-label={t`Clear ${label}`} disabled={disabled || !value} onClick={() => onChange("")}>{t`Clear`}</button>
    </div>
    <p id={`${id}-help`} className="text-xs text-muted">{helper}</p>
  </div>;
}
