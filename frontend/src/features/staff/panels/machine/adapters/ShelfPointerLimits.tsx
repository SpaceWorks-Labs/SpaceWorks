import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { Callout, Field } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Binding, type SafetyConfig } from "./adaptersApi";

const whole = (value: string, max: number) => { const n = Number(value); return value.trim() === "" ? null : Number.isInteger(n) && n >= 1 && n <= max ? n : undefined; };

/**
 * The two hard laser caps for one pointer. The SERVER enforces them on every command it sends (console, "Show on shelf",
 * kiosk scans): power is held at or below the percentage and on-time at or below the seconds. Clearing is never limited.
 * Saving replaces the binding's whole safety config, so the other overrides are sent back unchanged.
 */
export function ShelfPointerLimits({ makerspaceId, binding }: { makerspaceId: number; binding: Binding }) {
  const client = useQueryClient();
  const own = binding.config ?? {};
  const [power, setPower] = useState(own.laser_max_power_pct !== undefined ? String(own.laser_max_power_pct) : "");
  const [seconds, setSeconds] = useState(own.max_on_seconds !== undefined ? String(own.max_on_seconds) : "");
  const powerNow = whole(power, 100);
  const secondsNow = whole(seconds, 600);
  const save = useMutation({
    mutationFn: () => {
      const { laser_max_power_pct: _power, max_on_seconds: _seconds, ...rest } = own;
      const config: SafetyConfig = { ...rest, ...(powerNow ? { laser_max_power_pct: powerNow } : {}), ...(secondsNow ? { max_on_seconds: secondsNow } : {}) };
      return adaptersApi.setConfig(binding.id, config);
    },
    onSuccess: () => void client.invalidateQueries({ queryKey: adapterKeys.root(makerspaceId) }),
  });
  return <form className="grid gap-3" aria-label={t`Laser limits`} onSubmit={event => { event.preventDefault(); if (powerNow !== undefined && secondsNow !== undefined) save.mutate(); }}>
    <Callout size="inline" tone="warn" lead={t`Safety.`} body={t`These limits are enforced by the server on everything sent to this pointer. A laser position with no on-time limit still stops after 60 seconds. Clear is never limited.`} />
    <Field label={t`Strongest laser power (percent, 1 to 100)`}>
      <input className="desk-input w-32" inputMode="numeric" value={power} placeholder={t`No limit`} onChange={event => setPower(event.target.value)} /></Field>
    {powerNow === undefined ? <p role="alert" className="text-xs text-danger">{t`Use a whole number from 1 to 100, or leave it empty.`}</p> : null}
    <Field label={t`Longest time it may stay on (seconds, 1 to 600)`}>
      <input className="desk-input w-32" inputMode="numeric" value={seconds} placeholder={t`No limit`} onChange={event => setSeconds(event.target.value)} /></Field>
    {secondsNow === undefined ? <p role="alert" className="text-xs text-danger">{t`Use a whole number from 1 to 600, or leave it empty.`}</p> : null}
    {save.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(save.error)}</p> : null}
    {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Saved.`}</p> : null}
    <button type="submit" className="desk-button justify-self-start" disabled={save.isPending || powerNow === undefined || secondsNow === undefined}>
      {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save laser limits`}</button>
  </form>;
}
