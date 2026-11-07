import { t } from "@lingui/core/macro";
import { EventTicketTemplates } from "./EventTicketTemplates";
import { CustomFormBuilder } from "../forms/CustomFormBuilder";
import { AudienceOptions } from "./EventAudienceOptions";
import type { EventSeries, EventSeriesPayload } from "./eventSeriesApi";
import { useStaffChargesOn } from "./useStaffChargesOn";

export type SeriesFormValues = EventSeriesPayload & {
  frequency: "DAILY" | "WEEKLY" | "MONTHLY";
  interval: number;
  byday: string;
};

const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
export const emptySeriesForm: SeriesFormValues = {
  title: "", description: "", location: "", location_kind: "other", custom_form: null,
  registration_audience: "members", ticket_types: [],
  capacity: 0, payment_amount: "0.00", registration_requires_approval: false,
  registration_cutoff_lead_minutes: null, is_public: false,
  cancellation_cutoff_hours: null,
  recurrence_timezone: zone, dtstart_local_date: "", dtstart_local_time: "",
  recurrence_rule: "FREQ=WEEKLY;INTERVAL=1", duration_minutes: 60,
  frequency: "WEEKLY", interval: 1, byday: "",
};

export function valuesForSeries(series: EventSeries): SeriesFormValues {
  const parts = Object.fromEntries(series.recurrence_rule.split(";").map((part) => part.split("=", 2)));
  return {
    ...series, ticket_types: undefined,
    frequency: (parts.FREQ as SeriesFormValues["frequency"]) || "WEEKLY",
    interval: Number(parts.INTERVAL || 1),
    byday: parts.BYDAY || "",
  };
}

export function seriesPayload(values: SeriesFormValues): EventSeriesPayload {
  const rule = [`FREQ=${values.frequency}`, `INTERVAL=${Math.max(1, values.interval)}`];
  if (values.frequency === "WEEKLY" && values.byday.trim()) rule.push(`BYDAY=${values.byday.trim().toUpperCase()}`);
  const { frequency: _frequency, interval: _interval, byday: _byday, ...payload } = values;
  return { ...payload, ...(payload.ticket_types ? { ticket_types: payload.ticket_types.map((ticket) => ({ ...ticket, sales_start_at: ticket.sales_start_at ? new Date(ticket.sales_start_at).toISOString() : null, sales_end_at: ticket.sales_end_at ? new Date(ticket.sales_end_at).toISOString() : null })) } : {}), recurrence_rule: rule.join(";"), title: payload.title.trim(), location: payload.location.trim() };
}

export function EventSeriesFields({ values, setValues, disabled = false, canEditDetails = true, canEditSchedule = true, canEditPrice = true, organizationAudienceEnabled = false }: {
  values: SeriesFormValues; setValues: (values: SeriesFormValues) => void; disabled?: boolean;
  canEditDetails?: boolean; canEditSchedule?: boolean; canEditPrice?: boolean; organizationAudienceEnabled?: boolean;
}) {
  const set = <K extends keyof SeriesFormValues>(key: K, value: SeriesFormValues[K]) => setValues({ ...values, [key]: value });
  const chargesOn = useStaffChargesOn("events"); // #184: no price input while event charges are off
  const unit = { DAILY: "day", WEEKLY: "week", MONTHLY: "month" }[values.frequency];
  const cadence = `Every ${values.interval > 1 ? values.interval + " " : ""}${unit}${values.interval > 1 ? "s" : ""} at ${values.dtstart_local_time || "the selected time"} (${values.recurrence_timezone}).`;
  return <div className="grid gap-3 sm:grid-cols-2">
    <label className="grid gap-1 text-sm font-semibold text-ink sm:col-span-2">{t`Series title`}<input className="desk-input" required maxLength={200} disabled={disabled || !canEditDetails} value={values.title} onChange={(e) => set("title", e.target.value)} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`First local date`}<input className="desk-input w-full min-w-0" type="date" required disabled={disabled || !canEditSchedule} value={values.dtstart_local_date} onChange={(e) => set("dtstart_local_date", e.target.value)} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Local start time`}<input className="desk-input w-full min-w-0" type="time" required disabled={disabled || !canEditSchedule} value={values.dtstart_local_time} onChange={(e) => set("dtstart_local_time", e.target.value)} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`IANA timezone`}<input className="desk-input" required disabled={disabled || !canEditSchedule} value={values.recurrence_timezone} onChange={(e) => set("recurrence_timezone", e.target.value)} /><span className="text-xs font-normal text-muted">{t`Wall-clock time stays fixed across daylight-saving changes.`}</span></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Duration (minutes)`}<input className="desk-input" type="number" min="1" required disabled={disabled || !canEditSchedule} value={values.duration_minutes} onChange={(e) => set("duration_minutes", Number(e.target.value))} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Repeats`}<select className="desk-input" disabled={disabled || !canEditSchedule} value={values.frequency} onChange={(e) => set("frequency", e.target.value as SeriesFormValues["frequency"])}><option value="DAILY">{t`Daily`}</option><option value="WEEKLY">{t`Weekly`}</option><option value="MONTHLY">{t`Monthly`}</option></select></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Every`}<input className="desk-input" type="number" min="1" disabled={disabled || !canEditSchedule} value={values.interval} onChange={(e) => set("interval", Number(e.target.value))} /></label>
    {values.frequency === "WEEKLY" ? <label className="grid gap-1 text-sm font-semibold text-ink sm:col-span-2">{t`Weekdays (optional)`}<input className="desk-input" disabled={disabled || !canEditSchedule} placeholder={t`MO,WE,FR`} value={values.byday} onChange={(e) => set("byday", e.target.value)} /></label> : null}
    <p className="rounded-lg border border-line bg-surface p-3 text-sm text-muted sm:col-span-2">{cadence}</p>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Location`}<input className="desk-input" maxLength={255} disabled={disabled || !canEditDetails} value={values.location} onChange={(e) => set("location", e.target.value)} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Capacity per occurrence`}<input className="desk-input" type="number" min="0" disabled={disabled || !canEditDetails} value={values.capacity} onChange={(e) => set("capacity", Number(e.target.value))} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Registration audience`}<select className="desk-input" value={values.registration_audience ?? "members"} disabled={disabled || !canEditDetails} onChange={(e) => set("registration_audience", e.target.value as SeriesFormValues["registration_audience"])}><AudienceOptions value={values.registration_audience} organizationAudienceEnabled={organizationAudienceEnabled} /></select></label>
    {values.ticket_types ? <div className="sm:col-span-2"><EventTicketTemplates value={values.ticket_types} onChange={(tickets) => set("ticket_types", tickets)} disabled={disabled || !canEditDetails} /></div> : null}
    {chargesOn ? <label className="grid gap-1 text-sm font-semibold text-ink">{t`Price per occurrence`}<input className="desk-input" type="number" min="0" step="0.01" disabled={disabled || !canEditPrice} value={values.payment_amount} onChange={(e) => set("payment_amount", e.target.value)} /></label>
      : <p className="text-sm text-muted sm:col-span-2">{t`Event charges are off in this space, so events are free.`}</p>}
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Registration closes minutes before`}<input className="desk-input" type="number" min="0" disabled={disabled || !canEditDetails} value={values.registration_cutoff_lead_minutes ?? ""} onChange={(e) => set("registration_cutoff_lead_minutes", e.target.value === "" ? null : Number(e.target.value))} /></label>
    <label className="grid gap-1 text-sm font-semibold text-ink">{t`Member cancellation closes hours before`}<input className="desk-input" type="number" min="0" disabled={disabled || !canEditDetails} value={values.cancellation_cutoff_hours ?? ""} onChange={(e) => set("cancellation_cutoff_hours", e.target.value === "" ? null : Number(e.target.value))} /><span className="text-xs font-normal text-muted">{t`Blank allows cancellation until each occurrence starts.`}</span></label>
    <label className="grid gap-1 text-sm font-semibold text-ink sm:col-span-2">{t`Description`}<textarea className="desk-input min-h-24" disabled={disabled || !canEditDetails} value={values.description} onChange={(e) => set("description", e.target.value)} /></label>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" disabled={disabled || !canEditDetails} checked={values.registration_requires_approval} onChange={(e) => set("registration_requires_approval", e.target.checked)} />{t`Require approval`}</label>
    <label className="flex min-h-11 items-center gap-2 text-sm text-ink"><input type="checkbox" disabled={disabled || !canEditDetails} checked={values.is_public} onChange={(e) => set("is_public", e.target.checked)} />{t`Public occurrences`}</label>
    <div className="sm:col-span-2"><CustomFormBuilder value={values.custom_form} onChange={(value) => set("custom_form", value)} disabled={disabled || !canEditDetails} /></div>
  </div>;
}
