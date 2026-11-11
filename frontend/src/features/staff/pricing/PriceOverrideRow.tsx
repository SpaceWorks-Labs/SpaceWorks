import { t } from "@lingui/core/macro";
import { useId, useState } from "react";

import { SegmentedControl } from "../../../components/ui";
import type { PriceOverrideComponent, PriceOverrideWrite } from "./priceOverrideApi";
import { sourceWords, UNIT_WORDS } from "./priceOverrideApi";

type Mode = PriceOverrideComponent["mode"];

const MODES: { value: Mode; label: string }[] = [
  { value: "inherit", label: t`Inherit` }, { value: "free", label: t`Free` }, { value: "custom", label: t`Custom` },
];

const validAmount = (value: string) => value.trim() !== "" && Number.isFinite(Number(value)) && Number(value) >= 0;

export function effectiveText(row: PriceOverrideComponent, currency: string) {
  return t`Effective: ${currency.toUpperCase()} ${row.effective_amount} (${sourceWords(row.effective_source)})`;
}

/** One price component of an item: Inherit / Free / Custom, with its effective price and source. */
export function PriceOverrideRow({ row, currency, editable, pending, onSave }: {
  row: PriceOverrideComponent; currency: string; editable: boolean; pending: boolean;
  onSave: (body: PriceOverrideWrite) => void;
}) {
  const id = useId();
  const [mode, setMode] = useState<Mode>(row.mode);
  const [amount, setAmount] = useState(row.amount ?? "");
  const [cap, setCap] = useState(row.cap ?? "");
  const code = currency.toUpperCase();
  const unit = UNIT_WORDS[row.unit];
  const dirty = mode !== row.mode || (mode === "custom" && (amount !== (row.amount ?? "") || cap !== (row.cap ?? "")));
  const amountOk = mode !== "custom" || validAmount(amount);
  const capOk = mode !== "custom" || !row.has_cap || cap.trim() === "" || validAmount(cap);
  const save = () => onSave(mode === "custom"
    ? { component: row.component, mode, amount: amount.trim(), ...(row.has_cap ? { cap: cap.trim() || null } : {}) }
    : { component: row.component, mode });

  return <fieldset className="grid min-w-0 gap-3 py-4 first:pt-0 last:pb-0" aria-describedby={`${id}-effective`}>
    <legend className="float-left mb-1 w-full text-sm font-semibold text-ink">
      {row.label}{unit ? <span className="font-normal text-muted"> · {unit}</span> : null}
    </legend>
    {editable ? <SegmentedControl label={`${row.label} price`} value={mode} options={MODES} onChange={value => setMode(value as Mode)} />
      : <p className="text-sm text-ink">{mode === "custom" ? t`Custom: ${code} ${row.amount ?? "0.00"}${row.cap ? ` (cap ${code} ${row.cap})` : ""}`
        : MODES.find(option => option.value === mode)?.label}</p>}
    {editable && mode === "custom" ? <div className="grid gap-3 sm:grid-cols-2">
      <div className="grid gap-1">
        <label className="grid gap-1 text-sm font-semibold text-ink">{t`Custom amount (${code})`}<input className="desk-input" type="number" inputMode="decimal" min="0" step="any" value={amount} required
            aria-invalid={!amountOk} aria-describedby={amountOk ? undefined : `${id}-amount-error`} onChange={event => setAmount(event.target.value)} />
        </label>
        {amountOk ? null : <p id={`${id}-amount-error`} className="text-xs text-danger">{t`Enter an amount of 0 or more.`}</p>}
      </div>
      {row.has_cap ? <div className="grid gap-1">
        <label className="grid gap-1 text-sm font-semibold text-ink">{t`Cap (${code}, optional)`}<input className="desk-input" type="number" inputMode="decimal" min="0" step="any" value={cap}
            aria-invalid={!capOk} aria-describedby={capOk ? undefined : `${id}-cap-error`} onChange={event => setCap(event.target.value)} />
        </label>
        {capOk ? null : <p id={`${id}-cap-error`} className="text-xs text-danger">{t`Enter a cap of 0 or more, or leave it empty.`}</p>}
      </div> : null}
    </div> : null}
    {editable && mode === "inherit" ? <p className="text-xs text-muted">{t`Follows the space default (${code} ${row.default_amount}).`}</p> : null}
    <p id={`${id}-effective`} className="text-sm tabular-nums text-muted">{effectiveText(row, currency)}</p>
    {editable && dirty ? <div className="flex flex-wrap gap-2">
      <button className="desk-button-primary" type="button" disabled={pending || !amountOk || !capOk} onClick={save}>
        {pending ? t`Saving…` : t`Save ${row.label.toLowerCase()}`}
      </button>
      <button className="desk-button-ghost" type="button" disabled={pending}
        onClick={() => { setMode(row.mode); setAmount(row.amount ?? ""); setCap(row.cap ?? ""); }}>{t`Discard`}</button>
    </div> : null}
  </fieldset>;
}
