import { useState } from "react";
import { Card, ErrorBlock, Field } from "../../components/ui";

// Retains the existing station form and its pinned accessible names until the
// shared KioskPin API supports the required submit label (coordinator-owned).
export function StationUnlockForm({ helper, pending, error, disabledReason, onSubmit }: {
  helper: string; pending: boolean; error?: string; disabledReason?: string; onSubmit: (pin: string) => void;
}) {
  const [pin, setPin] = useState("");
  return <Card><form className="grid gap-5" onSubmit={event => {
    event.preventDefault();
    if (!pending && !disabledReason && pin.length === 8) onSubmit(pin);
  }}>
    <p className="text-muted">{helper}</p>
    <Field label="Station PIN" hint="8 digits. This unlocks this device only.">
      <input className="desk-input w-full text-xl tabular-nums tracking-widest" inputMode="numeric" type="password"
        autoComplete="off" pattern="[0-9]{8}" maxLength={8} required value={pin} disabled={pending || Boolean(disabledReason)}
        onChange={event => setPin(event.target.value.replace(/\D/g, ""))} />
    </Field>
    {error ? <ErrorBlock error={new Error(error)} /> : null}
    {disabledReason ? <p role="status">{disabledReason}</p> : null}
    <button className="desk-button-primary w-full" type="submit" disabled={pending || Boolean(disabledReason) || pin.length !== 8}>
      {pending ? "Unlocking…" : "Unlock station"}
    </button>
  </form></Card>;
}
