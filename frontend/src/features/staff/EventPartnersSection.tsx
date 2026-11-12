import { t } from "@lingui/core/macro";
import { useEffect } from "react";

import type { PickerOption } from "./AsyncSearchPicker";
import { AudienceOrganizationPicker, OrganizerPicker, PartnerMakerspacePicker } from "./EventPartnerPickers";
import type { EventCreatePayload } from "./eventsApiTypes";
import { useOrganizations } from "./organizationsApi";
import { useHostOptions } from "./eventPublishing/eventSurfaceApi";

export type EventPartnerValues = {
  /** null until the actor's own organizations load and become the default organizers. */
  organizers: PickerOption[] | null;
  audience: PickerOption[];
  partners: PickerOption[];
  /** DY-63: another space the actor may host in; null keeps this console's space. */
  hostId?: number | null;
};

const DEFAULT_LIMIT = 5;

export const emptyPartnerValues: EventPartnerValues = { organizers: null, audience: [], partners: [], hostId: null };

export function partnerPayload(values: EventPartnerValues, audienceSelected: boolean): Pick<EventCreatePayload, "organization_ids" | "audience_organization_ids" | "collaborator_slugs"> & { host_makerspace_id?: number } {
  return {
    ...(values.organizers?.length ? { organization_ids: values.organizers.map((row) => row.id) } : {}),
    ...(audienceSelected && values.audience.length ? { audience_organization_ids: values.audience.map((row) => row.id) } : {}),
    ...(values.partners.length ? { collaborator_slugs: values.partners.map((row) => row.detail ?? "").filter(Boolean) } : {}),
    ...(values.hostId ? { host_makerspace_id: values.hostId } : {}),
  };
}

/** DY-63: choose the host space among those where the actor runs events; hidden when there is one. */
function HostPicker({ hostId, consoleId, onChange }: { hostId: number; consoleId: number; onChange: (id: number | null) => void }) {
  const options = useHostOptions();
  const rows = options.data ?? [];
  if (rows.length < 2) return null;
  return <label className="grid gap-1 text-sm font-semibold">{t`Host makerspace`}<select className="desk-input font-normal" value={hostId} onChange={event => { const id = Number(event.target.value); onChange(id === consoleId ? null : id); }}>
      {rows.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
    </select>
    <span className="font-normal text-muted">{t`Only spaces where you run events are listed. Partners are invited separately below.`}</span>
  </label>;
}

/** The "Organizers & partners" part of the create form. Nothing is saved until the event is. */
export function EventPartnersSection({ values, setValues, hostId, audienceSelected }: {
  values: EventPartnerValues; setValues: (next: EventPartnerValues) => void; hostId: number; audienceSelected: boolean;
}) {
  const own = useOrganizations({ active: true });
  const host = values.hostId ?? hostId;
  useEffect(() => {
    // Default the organizers, once, to the actor's own organizations that run events. A
    // superadmin "sees" every organization, so a long list is never auto-selected.
    if (values.organizers === null && own.data) {
      const mine = own.data.count <= DEFAULT_LIMIT ? own.data.results.filter((row) => row.granted_actions.includes("manage_events")) : [];
      setValues({ ...values, organizers: mine.map((row) => ({ id: row.id, label: row.name, detail: row.slug })) });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- values and setValues are omitted: the default organizers are applied once, when own.data arrives while organizers is still null, and re-running on every values change would loop
  }, [own.data, values.organizers]);
  return <section aria-labelledby="event-partners-title" className="mt-6 grid gap-5 border-t border-line pt-5">
    <div>
      <h3 id="event-partners-title" className="title-section">{t`Organizers & partners`}</h3>
      <p className="mt-1 text-sm text-muted">{t`The host space runs the event. Add who organizes it and which makerspaces partner on it. You can change these later under More › Team.`}</p>
    </div>
    <HostPicker hostId={host} consoleId={hostId} onChange={(id) => setValues({ ...values, hostId: id, partners: values.partners.filter(row => row.id !== id) })} />
    <OrganizerPicker selected={values.organizers ?? []} onChange={(organizers) => setValues({ ...values, organizers })} />
    {audienceSelected ? <AudienceOrganizationPicker selected={values.audience} onChange={(audience) => setValues({ ...values, audience })} /> : null}
    <PartnerMakerspacePicker hostId={host} selected={values.partners} onChange={(partners) => setValues({ ...values, partners })} />
  </section>;
}
