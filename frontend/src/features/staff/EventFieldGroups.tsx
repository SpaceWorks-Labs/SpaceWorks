import { t } from "@lingui/core/macro";
import { EventField } from "./EventField";
import { CustomFormBuilder } from "../forms/CustomFormBuilder";
import { AudienceOptions } from "./EventAudienceOptions";
import type { EventFormValues } from "./EventFormFields";
import { EventDeliveryFields, EventVenueFields, EventVisibilityFields } from "./eventPublishing/EventSurfaceFields";
import { EventPriceNote } from "./pricing/PricingNote";
import { useStaffChargesOn } from "./useStaffChargesOn";

export type EventFieldGroupProps = {
  values: EventFormValues; setValues: (values: EventFormValues) => void; settings: boolean;
  /** Each flag is already resolved against `disabled` and the viewer's event staff grant. */
  details: boolean; schedule: boolean; price: boolean; approvalLocked: boolean; organizationAudienceEnabled: boolean;
  onlineEnabled?: boolean;
};

const checkRow = "flex min-h-11 items-center gap-2 py-3 text-sm text-ink sm:col-span-2";

/** What an event needs to exist: a name, a time, a place, a size and who may come. */
export function EventEssentialFields({ values, setValues, settings, details, schedule, organizationAudienceEnabled, onlineEnabled }: EventFieldGroupProps) {
  const set = <K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) => setValues({ ...values, [key]: value });
  return <>
    <EventField label={t`Title`} settings={settings} wide><input className="desk-input w-full" value={values.title} onChange={(e) => set("title", e.target.value)} required disabled={details} maxLength={200} /></EventField>
    <EventField label={t`Starts`} settings={settings}><input className="desk-input w-full min-w-0" type="datetime-local" value={values.starts_at} onChange={(e) => set("starts_at", e.target.value)} required disabled={schedule} /></EventField>
    <EventField label={t`Ends`} settings={settings}><input className="desk-input w-full min-w-0" type="datetime-local" value={values.ends_at} onChange={(e) => set("ends_at", e.target.value)} required disabled={schedule} /></EventField>
    <EventField label={t`Location`} settings={settings}><input className="desk-input w-full" value={values.location} onChange={(e) => set("location", e.target.value)} disabled={details} maxLength={255} /></EventField>
    {onlineEnabled ? <EventDeliveryFields values={values} setValues={setValues} settings={settings} disabled={details} /> : null}
    <EventVenueFields values={values} setValues={setValues} settings={settings} disabled={details} />
    <EventField label={t`Capacity`} settings={settings} helper={t`Use 0 for Unlimited.`}><input className="desk-input w-full" type="number" min="0" value={values.capacity} onChange={(e) => set("capacity", Number(e.target.value))} disabled={details} /></EventField>
    <EventField label={t`Registration audience`} settings={settings} wide helper={t`Who may register. Enable account registration, invitations or organization audiences in feature settings first.`}><select className="desk-input w-full" value={values.registration_audience ?? "members"} disabled={details} onChange={(e) => set("registration_audience", e.target.value as EventFormValues["registration_audience"])}><AudienceOptions value={values.registration_audience} organizationAudienceEnabled={organizationAudienceEnabled} /></select></EventField>
    <EventVisibilityFields values={values} setValues={setValues} settings={settings} disabled={details} />
  </>;
}

/** Everything else: time zone, description, price, cutoffs, approval and the registration form. */
export function EventMoreFields({ values, setValues, settings, details, price, approvalLocked }: EventFieldGroupProps) {
  const set = <K extends keyof EventFormValues>(key: K, value: EventFormValues[K]) => setValues({ ...values, [key]: value });
  // #184: with event charges off the price is not asked for (the stored value is left untouched).
  const chargesOn = useStaffChargesOn("events");
  const cutoffMode = values.registration_cutoff_at !== null ? "absolute" : values.registration_cutoff_lead_minutes !== null ? "lead" : "none";
  return <>
    <EventField label={t`Event time zone`} settings={settings} wide helper={t`Use an IANA name such as Asia/Kolkata. Review migrated events because their original zone was not recorded.`}><input className="desk-input w-full tabular-nums" value={values.timezone_name} onChange={(e) => set("timezone_name", e.target.value)} required disabled={details} maxLength={64} /></EventField>
    <EventField label={t`Event accent`} settings={settings} helper={t`A Space Works colour for this event's decorative accents.`}><select className="desk-input w-full" disabled={details} value={values.accent_preset ?? ""} onChange={event => set("accent_preset", event.target.value as EventFormValues["accent_preset"])}>
      {[["", "Use site theme"], ["maker_teal", "Maker Teal"], ["workshop_orange", "Workshop Orange"], ["citron", "Citron"], ["sky_blue", "Sky Blue"], ["warm_yellow", "Warm Yellow"]].map(([key, label]) => <option key={key} value={key}>{label}</option>)}
    </select></EventField>
    <EventField label={t`Description`} settings={settings} wide><textarea className="desk-input w-full min-h-24" value={values.description} onChange={(e) => set("description", e.target.value)} disabled={details} /></EventField>
    <EventField label={t`Tags (comma separated)`} settings={settings}><input className="desk-input w-full" value={(values.tags ?? []).join(",")} disabled={details} onChange={(e) => set("tags", e.target.value.split(","))} /></EventField>
    {chargesOn ? <><EventField label={t`Registration price`} settings={settings} helper={t`Charged only when a place is confirmed.`}><input className="desk-input w-full" type="number" min="0" step="any" value={values.payment_amount} onChange={(e) => set("payment_amount", e.target.value)} disabled={price} /></EventField>
    <EventPriceNote settings={settings} /></> : <p className="text-sm text-muted sm:col-span-2">{t`Event charges are off in this space, so events are free.`}</p>}
    <EventField label={t`Member cancellation closes hours before`} settings={settings} helper={t`Leave blank to allow cancellation until the event starts. Settled refunds are handled by staff.`}><input className="desk-input w-full" type="number" min="0" max="8760" value={values.cancellation_cutoff_hours ?? ""} onChange={(e) => set("cancellation_cutoff_hours", e.target.value === "" ? null : Number(e.target.value))} disabled={details} /></EventField>
    <EventField label={t`Registration cutoff`} settings={settings}><select className="desk-input w-full" value={cutoffMode} disabled={details} onChange={(e) => { const mode = e.target.value; setValues({ ...values, registration_cutoff_at: mode === "absolute" ? (values.starts_at || "") : null, registration_cutoff_lead_minutes: mode === "lead" ? 0 : null }); }}><option value="none">{t`No cutoff`}</option><option value="absolute">{t`At a date and time`}</option><option value="lead">{t`Before the event starts`}</option></select></EventField>
    {cutoffMode === "absolute" ? <EventField label={t`Cutoff time`} settings={settings}><input className="desk-input w-full min-w-0" type="datetime-local" value={values.registration_cutoff_at ?? ""} onChange={(e) => set("registration_cutoff_at", e.target.value)} disabled={details} required /></EventField> : null}
    {cutoffMode === "lead" ? <EventField label={t`Minutes before start`} settings={settings}><input className="desk-input w-full" type="number" min="0" value={values.registration_cutoff_lead_minutes ?? 0} onChange={(e) => set("registration_cutoff_lead_minutes", Number(e.target.value))} disabled={details} /></EventField> : null}
    <label className={checkRow}><input type="checkbox" checked={values.registration_requires_approval} onChange={(e) => set("registration_requires_approval", e.target.checked)} disabled={details || approvalLocked} />{t`Organizer approves each registration`}</label>
    <label className={checkRow}><input type="checkbox" checked={values.show_registration_count ?? true} onChange={(e) => set("show_registration_count", e.target.checked)} disabled={details} />{t`Show registration count publicly`}</label>
    <div className="sm:col-span-2"><CustomFormBuilder value={values.custom_form} onChange={(value) => set("custom_form", value)} disabled={details} /></div>
  </>;
}
