import { SettingsRow, SettingsSection } from "../../components/ui";
import { EventCategoriesField } from "./EventCategoriesField";
import { EventFields, valuesFor, type EventFormValues } from "./EventFormFields";
import { ImageUploader } from "./ImageUploader";
import { pageStickyActions } from "./stickyActions";
import type { StaffEvent } from "./eventsApi";
import { eventAccess } from "./eventStaffPermissions";

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
    {access.edit ? <SettingsSection title="Event photo" description="This photo appears on the public event page.">
      <SettingsRow label="Public event image" helper="Choose a wide image for the event listing."><ImageUploader endpoint={`/admin/events/${event.id}/image`} currentUrl={event.image_url} label="Event photo (shown publicly)" shape="wide" disabled={readOnly} onChanged={invalidate} /></SettingsRow>
    </SettingsSection> : null}
    {access.edit || access.publish ? <SettingsSection title={event.series_summary ? "Edit this occurrence" : "Event details"}>
      <form onSubmit={e => { e.preventDefault(); save(); }} className="grid gap-4">
        {access.manager ? <EventCategoriesField makerspaceId={makerspaceId} value={values.category_id ?? null} onChange={category_id => setValues({ ...values, category_id })} disabled={readOnly} /> : null}
        <EventFields values={values} setValues={setValues} disabled={readOnly} approvalLocked={event.status !== "draft"} settings
          organizationAudienceEnabled={event.ticketing_features?.includes("events.organization_audience")}
          canEditDetails={access.edit} canEditSchedule={access.publish} canEditPrice={access.manager} />
        {!readOnly ? <div className={pageStickyActions}>
          <button type="button" className="desk-button" disabled={pending} onClick={() => setValues(valuesFor(event))}>Discard</button>
          <button type="submit" className="desk-button-primary" disabled={pending}>{pending ? "Saving…" : "Save changes"}</button>
        </div> : null}
      </form>
    </SettingsSection> : null}
    {event.series_summary && overrides.length && !readOnly ? <SettingsSection title="Occurrence overrides" description="Reset a field to inherit the current series template again.">
      <div className="flex flex-wrap gap-2">{overrides.map(field => <button key={field} type="button" className="desk-button" disabled={pending} onClick={() => resetField(field)}>Reset {field.replace(/_/g, " ")}</button>)}</div>
    </SettingsSection> : null}
    {event.status === "published" && access.publish ? <SettingsSection title="Finish this event" description="Complete the event after attendance has been recorded."><button className="desk-button" type="button" onClick={complete}>Complete</button></SettingsSection> : null}
  </div>;
}
