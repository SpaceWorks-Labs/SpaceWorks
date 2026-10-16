import { useEffect, useState } from "react";

import { SettingsSection } from "../../components/ui";
import type { PickerOption } from "./AsyncSearchPicker";
import { AudienceOrganizationPicker } from "./EventPartnerPickers";
import { useReplaceAudienceOrganizations } from "./eventPartnersApi";
import type { StaffEvent } from "./eventsApi";
import { eventErrorText } from "./eventUi";

const asOptions = (rows: StaffEvent["audience_organizations"]) => (rows ?? []).map((row) => ({ id: row.id, label: row.name, detail: row.slug }));

/** "Selected organizations" audience editor. Saving admits members; it never shares management. */
export function EventAudienceOrganizations(props: { event: StaffEvent; makerspaceId: number; disabled: boolean }) {
  return props.event.registration_audience === "participating_organizations" ? <AudienceEditor {...props} /> : null;
}

function AudienceEditor({ event, makerspaceId, disabled }: { event: StaffEvent; makerspaceId: number; disabled: boolean }) {
  const [selected, setSelected] = useState<PickerOption[]>(asOptions(event.audience_organizations));
  const replace = useReplaceAudienceOrganizations(makerspaceId, event.id);
  useEffect(() => setSelected(asOptions(event.audience_organizations)), [event.audience_organizations]);
  const dirty = selected.map((row) => row.id).join() !== asOptions(event.audience_organizations).map((row) => row.id).join();
  return <SettingsSection title="Selected organizations"
    description="Members of these organizations, of the organizers, and of the venue's owning organization may register.">
    <div className="grid gap-3">
      <AudienceOrganizationPicker selected={selected} onChange={setSelected} disabled={disabled || replace.isPending} label="Audience organizations" />
      {!disabled && dirty ? <button type="button" className="desk-button-primary justify-self-start" disabled={replace.isPending}
        onClick={() => replace.mutate(selected.map((row) => row.id))}>{replace.isPending ? "Saving…" : "Save audience"}</button> : null}
      {replace.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(replace.error)}</p> : null}
    </div>
  </SettingsSection>;
}
