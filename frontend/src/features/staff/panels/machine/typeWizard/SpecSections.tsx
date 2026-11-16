import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";

import type { TemplateSpec } from "./templatesApi";

type Part<K extends keyof TemplateSpec> = { value: NonNullable<TemplateSpec[K]>; onChange: (next: NonNullable<TemplateSpec[K]>) => void };

const Check = ({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) =>
  <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} />{label}</label>;
/** An optional whole number: empty means "not set" and is left out of the spec. */
const Num = ({ label, value, onChange }: { label: string; value: number | undefined; onChange: (value: number | undefined) => void }) =>
  <label className="grid gap-1 text-sm">{label}<input className="desk-input tabular-nums" inputMode="numeric" value={value ?? ""} placeholder={t`Not set`}
    onChange={event => onChange(event.target.value.trim() === "" ? undefined : Number(event.target.value))} /></label>;
const Grid = ({ children }: { children: ReactNode }) => <div className="grid gap-3 sm:grid-cols-2">{children}</div>;
const strip = <T extends object>(value: T): T => Object.fromEntries(Object.entries(value).filter(([, entry]) => entry !== undefined && !Number.isNaN(entry))) as T;

export function SpecBasics({ value, onChange }: Part<"basics">) {
  const units: [TemplateSpec["basics"]["metering_unit"], string][] = [["minutes", t`Minutes`], ["weight", t`Weight (grams)`], ["volume", t`Volume (millilitres)`], ["length", t`Length (millimetres)`], ["count", t`Count`]];
  return <Grid>
    <label className="grid gap-1 text-sm">{t`Metering unit`}<select className="desk-input" value={value.metering_unit}
      onChange={event => onChange({ ...value, metering_unit: event.target.value as typeof value.metering_unit })}>{units.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
    <div><Check label={t`Machines of this type are booked`} checked={value.requires_booking} onChange={requires_booking => onChange({ ...value, requires_booking })} />
      <Check label={t`Shown on the public site`} checked={value.is_public} onChange={is_public => onChange({ ...value, is_public })} /></div>
  </Grid>;
}

export function SpecPricing({ value, onChange }: Part<"pricing">) {
  const options: [typeof value.charge_by, string][] = [["time", t`By time`], ["material", t`By material used`], ["job", t`By job`], ["none", t`No charge`]];
  return <label className="grid gap-1 text-sm sm:max-w-xs">{t`Charge by`}<select className="desk-input" value={value.charge_by}
    onChange={event => onChange({ charge_by: event.target.value as typeof value.charge_by })}>{options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>;
}

export function SpecAccess({ value, onChange }: Part<"access">) {
  return <div><Check label={t`Open to every member`} checked={value.open_to_all_members} onChange={open_to_all_members => onChange({ ...value, open_to_all_members })} />
    <Check label={t`Used under supervision`} checked={value.supervised} onChange={supervised => onChange({ ...value, supervised })} /></div>;
}

export function SpecBookings({ value, onChange }: Part<"bookings">) {
  const approval = value.requires_approval === undefined ? "" : value.requires_approval ? "approve" : "instant";
  return <div className="grid gap-3">
    <Check label={t`Bookable`} checked={value.bookable} onChange={bookable => onChange({ ...value, bookable })} />
    <Grid><Num label={t`Slot length (minutes)`} value={value.slot_minutes} onChange={slot_minutes => onChange(strip({ ...value, slot_minutes }))} />
      <Num label={t`Buffer between bookings (minutes)`} value={value.buffer_minutes} onChange={buffer_minutes => onChange(strip({ ...value, buffer_minutes }))} />
      <label className="grid gap-1 text-sm">{t`Who approves a booking`}<select className="desk-input" value={approval}
        onChange={event => onChange(strip({ ...value, requires_approval: event.target.value === "" ? undefined : event.target.value === "approve" }))}>
        <option value="">{t`No default`}</option><option value="instant">{t`Confirmed straight away`}</option><option value="approve">{t`Staff approve each booking`}</option></select></label></Grid>
  </div>;
}

export function SpecSafety({ value, onChange }: Part<"safety">) {
  return <div className="grid gap-3">
    <Grid><Num label={t`Switch off when idle for (minutes)`} value={value.idle_auto_off_minutes} onChange={idle_auto_off_minutes => onChange(strip({ ...value, idle_auto_off_minutes }))} />
      <Num label={t`Longest session (minutes)`} value={value.max_session_minutes} onChange={max_session_minutes => onChange(strip({ ...value, max_session_minutes }))} /></Grid>
    <div><Check label={t`Work area must be confirmed clear`} checked={value.area_clear_required ?? false} onChange={area_clear_required => onChange({ ...value, area_clear_required })} />
      <Check label={t`Filter must be confirmed working`} checked={value.filter_ok_required ?? false} onChange={filter_ok_required => onChange({ ...value, filter_ok_required })} /></div>
  </div>;
}

export function SpecJob({ value, onChange }: Part<"job">) {
  return <div><Check label={t`Takes job requests`} checked={value.accepts_job_requests} onChange={accepts_job_requests => onChange({ ...value, accepts_job_requests })} />
    <Check label={t`Runs unattended`} checked={value.runs_unattended} onChange={runs_unattended => onChange({ ...value, runs_unattended })} /></div>;
}

export function SpecNotifications({ value, onChange }: Part<"notifications">) {
  return <div><Check label={t`Suggest telling staff when a job finishes`} checked={value.job_finished} onChange={job_finished => onChange({ ...value, job_finished })} />
    <Check label={t`Suggest telling staff when a job fails`} checked={value.job_failed} onChange={job_failed => onChange({ ...value, job_failed })} />
    <Check label={t`Suggest telling staff when stock is low`} checked={value.low_stock} onChange={low_stock => onChange({ ...value, low_stock })} /></div>;
}

export function SpecDocuments({ value, onChange }: Part<"documents">) {
  return <label className="grid gap-1 text-sm">{t`Training notes`}<textarea className="desk-input min-h-24" value={value.training_notes} onChange={event => onChange({ training_notes: event.target.value })} />
    <span className="text-xs text-muted">{`${value.training_notes.length} / 10000`}</span></label>;
}
