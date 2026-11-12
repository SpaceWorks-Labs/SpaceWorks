import { t } from "@lingui/core/macro";
import { SettingsRow, SettingsSection } from "../../components/ui";
import { EventCategoriesField } from "./EventCategoriesField";
import { EventFields, valuesFor, type EventFormValues } from "./EventFormFields";
import { EventCoverUploader } from "./eventProgramme/EventCoverUploader";
import { pageStickyActions } from "./stickyActions";
import type { StaffEvent } from "./eventsApi";
import { eventAccess } from "./eventStaffPermissions";
import { BoxArt } from "../../components/BoxSpinner";

/** Names of the series template fields an occurrence can override (backend INHERITABLE_FIELDS). */
const overrideFieldLabel = (field: string) => ({ title: t`title`, description: t`description`, starts_at: t`start time`,
  ends_at: t`end time`, location: t`location`, location_kind: t`location type`, custom_form: t`registration questions`,
  capacity: t`capacity`, is_public: t`public listing`, payment_amount: t`price`,
  registration_requires_approval: t`registration approval`, registration_cutoff_at: t`registration deadline`,
  registration_cutoff_lead_minutes: t`registration deadline`, cancellation_cutoff_hours: t`cancellation deadline`,
  timezone_name: t`time zone`, registration_audience: t`who can register`, image_key: t`image` } as Record<string, string>)[field]
  ?? field.replace(/_/g, " ");

export function EventSettings({ event, makerspaceId, values, setValues, save, pending, invalidate, resetField, complete }: {
  event: StaffEvent; makerspaceId: number; values: EventFormValues;
  setValues: (value: EventFormValues) => void; save: () => void; pending: boolean;
  invalidate: () => void; resetField: (field: string) => void; complete: () => void;
}) {
  const readOnly = event.status === "cancelled" || event.status === "completed";
  // Event staff grants: details/photo need edit, dates need publish, price and category need a full manager.
  const access = eventAccess(event);
  const overrides = event.series_override_fields.filter(field => field === "payment_amount" ? access.manager
    : ["starts_at", "ends_at"].includes(field) ? access.publish : access.edit);
  return <div className="grid gap-6">
    {access.edit ? <SettingsSection title={t`Event photo`} description={t`This photo appears on the public event page.`}>
      <SettingsRow label={t`Public event image`} helper={t`Crop, straighten and adjust it here; cards and social previews are marked on the frame.`}><EventCoverUploader endpoint={`/admin/events/${event.id}/image`} currentUrl={event.image_url} label={t`Event photo (shown publicly)`} disabled={readOnly} onChanged={invalidate} /></SettingsRow>
    </SettingsSection> : null}
    {access.edit || access.publish ? <SettingsSection title={event.series_summary ? t`Edit this occurrence` : t`Event details`}>
      <form onSubmit={e => { e.preventDefault(); save(); }} className="grid gap-4">
        {access.manager ? <EventCategoriesField makerspaceId={makerspaceId} value={values.category_id ?? null} onChange={category_id => setValues({ ...values, category_id })} disabled={readOnly} /> : null}
        <EventFields values={values} setValues={setValues} disabled={readOnly} approvalLocked={event.status !== "draft"} settings
          organizationAudienceEnabled={event.ticketing_features?.includes("events.organization_audience")}
          onlineEnabled={event.ticketing_features?.includes("events.online_delivery")}
          canEditDetails={access.edit} canEditSchedule={access.publish} canEditPrice={access.manager} />
        {!readOnly ? <div className={pageStickyActions}>
          <button type="button" className="desk-button" disabled={pending} onClick={() => setValues(valuesFor(event))}>{t`Discard`}</button>
          <button type="submit" className="desk-button-primary" disabled={pending}>{pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save changes`}</button>
        </div> : null}
      </form>
    </SettingsSection> : null}
    {event.series_summary && overrides.length && !readOnly ? <SettingsSection title={t`Occurrence overrides`} description={t`Reset a field to inherit the current series template again.`}>
      <div className="flex flex-wrap gap-2">{overrides.map(field => <button key={field} type="button" className="desk-button" disabled={pending} onClick={() => resetField(field)}>{t`Reset ${overrideFieldLabel(field)}`}</button>)}</div>
    </SettingsSection> : null}
    {event.status === "published" && access.publish ? <SettingsSection title={t`Finish this event`} description={t`Complete the event after attendance has been recorded.`}><button className="desk-button" type="button" onClick={complete}>{t`Complete`}</button></SettingsSection> : null}
  </div>;
}
