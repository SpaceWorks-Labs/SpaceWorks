import { Video } from "lucide-react";
import { EventField } from "../EventField";
import type { EventFormValues } from "../EventFormFields";

type Props = { values: EventFormValues; setValues: (values: EventFormValues) => void; settings: boolean; disabled: boolean };

const checkRow = "flex min-h-11 items-center gap-2 py-3 text-sm text-ink sm:col-span-2";

/** "Who can see" and "who can find" for the event editor (the programme panel asks the same questions). */
export function EventVisibilityFields({ values, setValues, settings, disabled }: Props) {
  return <>
    <label className={checkRow}><input type="checkbox" checked={values.is_public} disabled={disabled}
      onChange={(e) => setValues({ ...values, is_public: e.target.checked })} />Anyone with the link can open this event</label>
    <EventField label="Who can find it?" settings={settings} wide helper={values.is_public
      ? "Unlisted events are hidden from the events page, Discover and search engines; only people you send the link to can open them."
      : "A private event is never listed. Make it public first."}>
      <select className="desk-input w-full" value={values.listing ?? "listed"} disabled={disabled || !values.is_public}
        onChange={(e) => setValues({ ...values, listing: e.target.value as EventFormValues["listing"] })}>
        <option value="listed">Listed: events page, Discover and search engines</option>
        <option value="unlisted">Unlisted: only people with the link</option>
      </select>
    </EventField>
  </>;
}

/** G3: how people attend and the join link, released only to confirmed registrants. */
export function EventDeliveryFields({ values, setValues, settings, disabled }: Props) {
  const online = values.delivery_mode === "online" || values.delivery_mode === "hybrid";
  return <>
    <EventField label="How people attend" settings={settings}>
      <select className="desk-input w-full" value={values.delivery_mode ?? "in_person"} disabled={disabled}
        onChange={(e) => setValues({ ...values, delivery_mode: e.target.value as EventFormValues["delivery_mode"] })}>
        <option value="in_person">In person</option><option value="online">Online</option><option value="hybrid">Hybrid (in person and online)</option>
      </select>
    </EventField>
    {online ? <EventField label="Join link" settings={settings} helper="An https:// meeting link. Only people with a confirmed place see it, on their ticket, email and calendar.">
      <span className="flex items-center gap-2"><Video aria-hidden="true" size={18} className="shrink-0 text-muted" />
        <input className="desk-input w-full" type="url" inputMode="url" placeholder="https://" maxLength={2000} value={values.join_url ?? ""} disabled={disabled}
          onChange={(e) => setValues({ ...values, join_url: e.target.value })} /></span>
    </EventField> : null}
  </>;
}
