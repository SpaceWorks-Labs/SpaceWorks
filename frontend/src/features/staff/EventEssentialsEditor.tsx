import { t } from "@lingui/core/macro";
import { useState } from "react";

import { Card } from "../../components/ui";
import { EventFields, valuesFor, type EventFormValues } from "./EventFormFields";
import type { StaffEvent } from "./eventsApi";
import type { eventAccess } from "./eventStaffPermissions";
import { BoxArt } from "../../components/BoxSpinner";

/**
 * Inline edit of the essentials on the Overview tab. It shares the drawer's form state and its
 * changed-fields-only save with More › Settings, so a grant-limited editor sends only what
 * their grant allows and the two forms never disagree about the event.
 */
export function EventEssentialsEditor({ event, access, values, setValues, save, pending }: {
  event: StaffEvent; access: ReturnType<typeof eventAccess>; values: EventFormValues;
  setValues: (value: EventFormValues) => void; save: (onSaved: () => void) => void; pending: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const close = () => { setValues(valuesFor(event)); setEditing(false); };
  return <Card>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0"><h2 className="title-panel">{t`Essentials`}</h2>
        <p className="mt-1 text-sm text-muted">{t`Title, dates, location, capacity, audience and visibility. Everything else is under More › Settings.`}</p></div>
      {!editing ? <button className="desk-button" type="button" onClick={() => { setValues(valuesFor(event)); setEditing(true); }}>{t`Edit essentials`}</button> : null}
    </div>
    {editing ? <form className="mt-4 grid gap-4" aria-label={t`Edit essentials`} onSubmit={(e) => { e.preventDefault(); save(() => setEditing(false)); }}>
      <EventFields layout="essentials" values={values} setValues={setValues}
        organizationAudienceEnabled={event.ticketing_features?.includes("events.organization_audience")}
        canEditDetails={access.edit} canEditSchedule={access.publish} canEditPrice={access.manager} />
      <div className="flex flex-wrap justify-end gap-2">
        <button className="desk-button" type="button" disabled={pending} onClick={close}>{t`Cancel`}</button>
        <button className="desk-button-primary" type="submit" disabled={pending}>{pending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save essentials`}</button>
      </div>
    </form> : null}
  </Card>;
}
