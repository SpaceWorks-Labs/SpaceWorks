import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import type { PickerOption } from "./AsyncSearchPicker";
import { OrganizerPicker } from "./EventPartnerPickers";
import type { StaffEvent } from "./eventsApi";
import { useReplaceEventOrganizers } from "./eventsApi";
import { BoxArt } from "../../components/BoxSpinner";

const asOptions = (rows: StaffEvent["organizers"]) => rows.map((row) => ({ id: row.id, label: row.name, detail: row.slug }));

export function EventOrganizers({ visible = true, event, makerspaceId, disabled }: { visible?: boolean;
  event: StaffEvent;
  makerspaceId: number;
  disabled: boolean;
}) {
  const [selected, setSelected] = useState<PickerOption[]>(asOptions(event.organizers));
  const replace = useReplaceEventOrganizers(makerspaceId, event.id);
  useEffect(() => setSelected(asOptions(event.organizers)), [event.organizers]);
  const dirty = selected.map((row) => row.id).join() !== event.organizers.map((row) => row.id).join();

  if (!visible) return null;
  return (
    <section className="grid gap-3 rounded-xl border border-line bg-bg p-4" aria-labelledby={`event-${event.id}-organizers`}>
      <div>
        <h3 className="title-section" id={`event-${event.id}-organizers`}>{t`Organization organizers`}</h3>
        <p className="mt-1 text-sm text-muted">{t`Attribution and event-specific authority. The host makerspace remains the owner. Co-organizers someone else added stay until you remove them.`}</p>
      </div>
      <OrganizerPicker selected={selected} onChange={setSelected} disabled={disabled} label={t`Organizers`} helper={t`Search the organizations you belong to.`} />
      {!disabled && dirty ? <button className="desk-button-primary justify-self-start" type="button" disabled={replace.isPending}
        onClick={() => replace.mutate(selected.map((row) => row.id))}>{replace.isPending ? <><BoxArt size={16} mono />{t`Saving...`}</> : t`Save organizers`}</button> : null}
      {replace.error ? <p className="text-sm text-danger" role="alert">{replace.error.message}</p> : null}
    </section>
  );
}
