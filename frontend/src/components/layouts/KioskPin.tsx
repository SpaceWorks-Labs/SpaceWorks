import { useState } from "react";
import { ErrorBlock, Field } from "../ui";

export type KioskPinProps = { title: string; helper: string; pinLength: number; onSubmit: (pin: string) => void;
  pending: boolean; error?: string; disabledReason?: string };
export function KioskPin({ title, helper, pinLength, onSubmit, pending, error, disabledReason }: KioskPinProps) {
  const [pin, setPin] = useState("");
  const blocked = pending || Boolean(disabledReason);
  const enter = (value: string) => setPin(value.replace(/\D/g, "").slice(0, pinLength));
  return <form className="sw-kiosk-stage items-center" onSubmit={event => { event.preventDefault(); if (!blocked && pin.length === pinLength) onSubmit(pin); }}>
    <div className="grid min-w-0 gap-6"><h2 className="font-display text-4xl text-ink md:text-[52px]">{title}</h2><p className="text-muted">{helper}</p>
      <Field label="Station PIN" hint={`${pinLength} digits. This unlocks this device only.`}>
        <input type="password" inputMode="numeric" autoComplete="off" className="desk-input w-full tracking-widest" value={pin}
          maxLength={pinLength} disabled={blocked} onChange={event => enter(event.target.value)} />
      </Field>
      {error ? <ErrorBlock error={new Error(error)} /> : null}
      {disabledReason ? <p role="status">{disabledReason}</p> : null}
    </div>
    <div className="grid gap-4"><div className="sw-kiosk-pin" aria-label="PIN keypad">
      {["1", "2", "3", "4", "5", "6", "7", "8", "9", "Clear", "0", "Delete"].map(key => <button key={key}
        type="button" className="desk-button text-2xl" disabled={blocked} aria-label={key === "Delete" ? "Delete last digit" : key}
        onClick={() => key === "Clear" ? setPin("") : key === "Delete" ? setPin(pin.slice(0, -1)) : enter(pin + key)}>{key}</button>)}
    </div><button type="submit" className="desk-button-primary" disabled={blocked || pin.length !== pinLength} aria-busy={pending || undefined}>
      {pending ? "Unlocking…" : "Open station"}</button></div>
  </form>;
}
