import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { ErrorBlock } from "../ui";

export type KioskPinProps = { title: string; helper: string; length?: number; pinLength?: number; onSubmit: (pin: string) => void;
  pending: boolean; error?: string; disabledReason?: string; submitLabel?: string; pendingLabel?: string };
export function KioskPin({ title, helper, length, pinLength, onSubmit, pending, error, disabledReason,
  submitLabel = t`Open station`, pendingLabel = t`Unlocking…` }: KioskPinProps) {
  const [pin, setPin] = useState("");
  const hintId = useId();
  const digits = length ?? pinLength ?? 8;
  const blocked = pending || Boolean(disabledReason);
  const enter = (value: string) => setPin(value.replace(/\D/g, "").slice(0, digits));
  return <form className="sw-kiosk-stage items-center" onSubmit={event => { event.preventDefault(); if (!blocked && pin.length === digits) onSubmit(pin); }}>
    <div className="grid min-w-0 gap-6"><h2 className="font-display text-4xl text-ink md:text-[52px]">{title}</h2><p className="text-muted">{helper}</p>
      <label className="grid gap-2"><span className="text-sm font-semibold text-ink">{t`Station PIN`}</span>
        <span className="relative block rounded-control focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus">
          <input aria-label={t`Station PIN`} aria-describedby={hintId} type="password" inputMode="numeric" autoComplete="off" className="sr-only" value={pin}
            maxLength={digits} required disabled={blocked} onChange={event => enter(event.target.value)} />
          <span aria-hidden="true" className="grid gap-2" style={{ gridTemplateColumns: `repeat(${digits}, minmax(0, 1fr))` }}>
            {Array.from({ length: digits }, (_, index) => <span key={index} className="grid min-h-14 place-items-center rounded-control border border-outline bg-panel text-2xl tabular-nums">
              {index < pin.length ? "•" : ""}
            </span>)}
          </span>
        </span>
        <span id={hintId} className="text-xs text-muted">{t`${digits} digits. This unlocks this device only.`}</span>
      </label>
      {error ? <ErrorBlock error={new Error(error)} /> : null}
      {disabledReason ? <p role="status">{disabledReason}</p> : null}
    </div>
    <div className="grid gap-4"><div className="sw-kiosk-pin" aria-label={t`PIN keypad`}>
      {["1", "2", "3", "4", "5", "6", "7", "8", "9", "Clear", "0", "Delete"].map(key => <button key={key}
        type="button" className="desk-button text-2xl" disabled={blocked} aria-label={key === "Delete" ? t`Delete last digit` : key}
        onClick={() => key === "Clear" ? setPin("") : key === "Delete" ? setPin(pin.slice(0, -1)) : enter(pin + key)}>{key}</button>)}
    </div><button type="submit" className="desk-button-primary" disabled={blocked || pin.length !== digits} aria-busy={pending || undefined}>
      {pending ? pendingLabel : submitLabel}</button></div>
  </form>;
}
