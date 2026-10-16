import { useEffect } from "react";

import type { PickerOption } from "./AsyncSearchPicker";
import { AudienceOrganizationPicker, OrganizerPicker, PartnerMakerspacePicker } from "./EventPartnerPickers";
import type { EventCreatePayload } from "./eventsApiTypes";
import { useOrganizations } from "./organizationsApi";

export type EventPartnerValues = {
  /** null until the actor's own organizations load and become the default organizers. */
  organizers: PickerOption[] | null;
  audience: PickerOption[];
  partners: PickerOption[];
};

const DEFAULT_LIMIT = 5;

export const emptyPartnerValues: EventPartnerValues = { organizers: null, audience: [], partners: [] };

export function partnerPayload(values: EventPartnerValues, audienceSelected: boolean): Pick<EventCreatePayload, "organization_ids" | "audience_organization_ids" | "collaborator_slugs"> {
  return {
    ...(values.organizers?.length ? { organization_ids: values.organizers.map((row) => row.id) } : {}),
    ...(audienceSelected && values.audience.length ? { audience_organization_ids: values.audience.map((row) => row.id) } : {}),
    ...(values.partners.length ? { collaborator_slugs: values.partners.map((row) => row.detail ?? "").filter(Boolean) } : {}),
  };
}

/** The "Organizers & partners" part of the create form. Nothing is saved until the event is. */
export function EventPartnersSection({ values, setValues, hostId, audienceSelected }: {
  values: EventPartnerValues; setValues: (next: EventPartnerValues) => void; hostId: number; audienceSelected: boolean;
}) {
  const own = useOrganizations({ active: true });
  useEffect(() => {
    // Default the organizers, once, to the actor's own organizations that run events. A
    // superadmin "sees" every organization, so a long list is never auto-selected.
    if (values.organizers === null && own.data) {
      const mine = own.data.count <= DEFAULT_LIMIT ? own.data.results.filter((row) => row.granted_actions.includes("manage_events")) : [];
      setValues({ ...values, organizers: mine.map((row) => ({ id: row.id, label: row.name, detail: row.slug })) });
    }
  }, [own.data, values.organizers]);
  return <section aria-labelledby="event-partners-title" className="mt-6 grid gap-5 border-t border-line pt-5">
    <div>
      <h3 id="event-partners-title" className="title-section">Organizers & partners</h3>
      <p className="mt-1 text-sm text-muted">This space hosts the event. Add who organizes it and which makerspaces partner on it. You can change these later under More › Team.</p>
    </div>
    <OrganizerPicker selected={values.organizers ?? []} onChange={(organizers) => setValues({ ...values, organizers })} />
    {audienceSelected ? <AudienceOrganizationPicker selected={values.audience} onChange={(audience) => setValues({ ...values, audience })} /> : null}
    <PartnerMakerspacePicker hostId={hostId} selected={values.partners} onChange={(partners) => setValues({ ...values, partners })} />
  </section>;
}
