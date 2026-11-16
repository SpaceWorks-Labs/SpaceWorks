import { t } from "@lingui/core/macro";

import { Field } from "../../components/ui";
import type { MembershipPlan } from "./membershipPlansApi";

/** Decision 221(d): hours per term used before the hourly price. Strings while editing. */
export type IncludedHours = { booking: string; machine: string };
export const emptyIncludedHours: IncludedHours = { booking: "0", machine: "0" };
export const MAX_INCLUDED_HOURS = 8784;

export function planIncludedHours(plan: MembershipPlan): IncludedHours {
  return { booking: String(plan.included_booking_hours ?? 0), machine: String(plan.included_machine_hours ?? 0) };
}

export function validateIncludedHours(value: IncludedHours): string | null {
  const ok = (text: string) => /^\d+$/.test(text.trim()) && Number(text) <= MAX_INCLUDED_HOURS;
  return ok(value.booking) && ok(value.machine) ? null : t`Enter included hours as a whole number from 0 to ${MAX_INCLUDED_HOURS}.`;
}

/** Only the pools the space can use are sent, so a switched-off module never writes them. */
export function includedHoursInput(value: IncludedHours, pools: { booking: boolean; machine: boolean }) {
  return {
    ...(pools.booking ? { included_booking_hours: Number(value.booking) } : {}),
    ...(pools.machine ? { included_machine_hours: Number(value.machine) } : {}),
  };
}

export function MembershipIncludedHoursFields({ value, onChange, pools }: {
  value: IncludedHours; onChange: (value: IncludedHours) => void; pools: { booking: boolean; machine: boolean };
}) {
  if (!pools.booking && !pools.machine) return null;
  const input = (key: keyof IncludedHours) => <input className="desk-input" type="number" inputMode="numeric" min={0} max={MAX_INCLUDED_HOURS} step={1}
    value={value[key]} onChange={(event) => onChange({ ...value, [key]: event.target.value })} />;
  return <fieldset className="grid gap-3 border-t border-line pt-3 sm:col-span-3 sm:grid-cols-3">
    <legend className="font-semibold">{t`Included hours`}</legend>
    <p className="text-sm text-muted sm:col-span-3">{t`Hours each term that the member's bookings use before any hourly price applies. 0 means none.`}</p>
    {pools.booking ? <Field label={t`Room booking hours per term`}>{input("booking")}</Field> : null}
    {pools.machine ? <Field label={t`Machine time hours per term`}>{input("machine")}</Field> : null}
  </fieldset>;
}
