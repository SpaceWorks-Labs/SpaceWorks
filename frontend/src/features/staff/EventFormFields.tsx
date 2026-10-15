import { EventField } from "./EventField";
import type { EventPayload, StaffEvent } from "./eventsApi";
import { CustomFormBuilder } from "../forms/CustomFormBuilder";

export type EventFormValues = Omit<EventPayload, "starts_at" | "ends_at" | "registration_cutoff_at"> & {
  starts_at: string;
  ends_at: string;
  registration_cutoff_at: string | null;
};

export const emptyEventForm: EventFormValues = {
  title: "", description: "", starts_at: "", ends_at: "", location: "",
  timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  capacity: 0, payment_amount: "0.00", registration_requires_approval: false,
  registration_cutoff_at: null, registration_cutoff_lead_minutes: null,
  cancellation_cutoff_hours: null,
  is_public: false, registration_audience: "members", category_id: null, tags: [],
  custom_form: null,
};

function localDate(value: string) {
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function valuesFor(event: StaffEvent): EventFormValues {
  return {
    title: event.title, description: event.description,
    starts_at: localDate(event.starts_at), ends_at: localDate(event.ends_at),
    timezone_name: event.timezone_name,
    location: event.location, capacity: event.capacity,
    payment_amount: event.payment_amount,
    registration_requires_approval: event.registration_requires_approval,
    registration_cutoff_at: event.registration_cutoff_at ? localDate(event.registration_cutoff_at) : null,
    registration_cutoff_lead_minutes: event.registration_cutoff_lead_minutes,
    cancellation_cutoff_hours: event.cancellation_cutoff_hours ?? null,
    is_public: event.is_public, registration_audience: event.registration_audience ?? "members", category_id: event.category_id ?? null, tags: event.tags ?? [],
    custom_form: event.custom_form,
  };
}

export function payloadFor(values: EventFormValues): EventPayload {
  return {
    ...values, tags: (values.tags ?? []).map((tag) => tag.trim()).filter(Boolean), title: values.title.trim(), description: values.description.trim(),
    location: values.location.trim(), starts_at: new Date(values.starts_at).toISOString(),
    ends_at: new Date(values.ends_at).toISOString(),
    registration_cutoff_at: values.registration_cutoff_at ? new Date(values.registration_cutoff_at).toISOString() : null,
  };
}

export function EventFields({ values, setValues, disabled = false, approvalLocked = false, settings = false }: {
  values: EventFormValues; setValues: (values: EventFormValues) => void;
  disabled?: boolean; approvalLocked?: boolean; settings?: boolean;
}) {
  const set = <K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) => setValues({ ...values, [key]: value });
  const cutoffMode = values.registration_cutoff_at !== null ? "absolute" : values.registration_cutoff_lead_minutes !== null ? "lead" : "none";
  return <div className={settings ? "divide-y divide-line" : "grid gap-4 sm:grid-cols-2"}>
    <EventField label="Title" settings={settings} wide><input className="desk-input w-full" value={values.title} onChange={(e) => set("title", e.target.value)} required disabled={disabled} maxLength={200} /></EventField>
    <EventField label="Starts" settings={settings}><input className="desk-input w-full min-w-0" type="datetime-local" value={values.starts_at} onChange={(e) => set("starts_at", e.target.value)} required disabled={disabled} /></EventField>
    <EventField label="Ends" settings={settings}><input className="desk-input w-full min-w-0" type="datetime-local" value={values.ends_at} onChange={(e) => set("ends_at", e.target.value)} required disabled={disabled} /></EventField>
    <EventField label="Event time zone" settings={settings} wide helper="Use an IANA name such as Asia/Kolkata. Review migrated events because their original zone was not recorded."><input className="desk-input w-full tabular-nums" value={values.timezone_name} onChange={(e) => set("timezone_name", e.target.value)} required disabled={disabled} maxLength={64} /></EventField>
    <EventField label="Location" settings={settings}><input className="desk-input w-full" value={values.location} onChange={(e) => set("location", e.target.value)} disabled={disabled} maxLength={255} /></EventField>
    <EventField label="Capacity" settings={settings} helper="Use 0 for Unlimited."><input className="desk-input w-full" type="number" min="0" value={values.capacity} onChange={(e) => set("capacity", Number(e.target.value))} disabled={disabled} /></EventField>
    <EventField label="Registration audience" settings={settings} helper="Enable account registration or invitations in makerspace feature settings before selecting that audience."><select className="desk-input w-full" value={values.registration_audience ?? "members"} disabled={disabled} onChange={(e) => set("registration_audience", e.target.value as EventFormValues["registration_audience"])}><option value="members">Members</option><option value="accounts">Authenticated accounts</option><option value="invite">Invited accounts</option></select></EventField>
    <EventField label="Tags (comma separated)" settings={settings}><input className="desk-input w-full" value={(values.tags ?? []).join(",")} disabled={disabled} onChange={(e) => set("tags", e.target.value.split(","))} /></EventField>
    <EventField label="Registration price" settings={settings} helper="Charged only when a place is confirmed."><input className="desk-input w-full" type="number" min="0" step="0.01" value={values.payment_amount} onChange={(e) => set("payment_amount", e.target.value)} disabled={disabled} /></EventField>
    <EventField label="Member cancellation closes hours before" settings={settings} helper="Leave blank to allow cancellation until the event starts. Settled refunds are handled by staff."><input className="desk-input w-full" type="number" min="0" max="8760" value={values.cancellation_cutoff_hours ?? ""} onChange={(e) => set("cancellation_cutoff_hours", e.target.value === "" ? null : Number(e.target.value))} disabled={disabled} /></EventField>
    <EventField label="Registration cutoff" settings={settings}><select className="desk-input w-full" value={cutoffMode} disabled={disabled} onChange={(e) => { const mode = e.target.value; setValues({ ...values, registration_cutoff_at: mode === "absolute" ? (values.starts_at || "") : null, registration_cutoff_lead_minutes: mode === "lead" ? 0 : null }); }}><option value="none">No cutoff</option><option value="absolute">At a date and time</option><option value="lead">Before the event starts</option></select></EventField>
    {cutoffMode === "absolute" ? <EventField label="Cutoff time" settings={settings}><input className="desk-input w-full min-w-0" type="datetime-local" value={values.registration_cutoff_at ?? ""} onChange={(e) => set("registration_cutoff_at", e.target.value)} disabled={disabled} required /></EventField> : null}
    {cutoffMode === "lead" ? <EventField label="Minutes before start" settings={settings}><input className="desk-input w-full" type="number" min="0" value={values.registration_cutoff_lead_minutes ?? 0} onChange={(e) => set("registration_cutoff_lead_minutes", Number(e.target.value))} disabled={disabled} /></EventField> : null}
    <EventField label="Description" settings={settings} wide><textarea className="desk-input w-full min-h-24" value={values.description} onChange={(e) => set("description", e.target.value)} disabled={disabled} /></EventField>
    <label className="flex min-h-11 items-center gap-2 py-3 text-sm text-ink sm:col-span-2"><input type="checkbox" checked={values.registration_requires_approval} onChange={(e) => set("registration_requires_approval", e.target.checked)} disabled={disabled || approvalLocked} />Require staff approval for registrations</label>
    <label className="flex min-h-11 items-center gap-2 py-3 text-sm text-ink sm:col-span-2"><input type="checkbox" checked={values.is_public} onChange={(e) => set("is_public", e.target.checked)} disabled={disabled} />Show this event on the public Events page</label>
    <div className="sm:col-span-2"><CustomFormBuilder value={values.custom_form} onChange={(value) => set("custom_form", value)} disabled={disabled} /></div>
  </div>;
}
