import { t } from "@lingui/core/macro";
import { useState } from "react";

import { AsyncSearchPicker, type PickerOption } from "./AsyncSearchPicker";
import { useOrganizationDirectory, usePartnerMakerspaces } from "./eventPartnersApi";
import { useOrganizations } from "./organizationsApi";

type PickerProps = { selected: PickerOption[]; onChange: (next: PickerOption[]) => void; disabled?: boolean; label?: string; helper?: string };

const message = (error: unknown) => error instanceof Error ? error.message : error ? "Could not search." : null;

/** Organizers are limited to the actor's own organizations: an organizer becomes a
 * co-manager of the event, so no organization is attached without one of its members. */
export function OrganizerPicker({ selected, onChange, disabled, label = t`Organizing organizations`,
  helper = t`Your organizations co-manage the event with this space. Other organizations can be its audience instead.` }: PickerProps) {
  const [search, setSearch] = useState("");
  const rows = useOrganizations({ search, active: true });
  const options = (rows.data?.results ?? []).map((row) => ({ id: row.id, label: row.name, detail: row.slug }));
  return <AsyncSearchPicker label={label} helper={helper} placeholder={t`Search your organizations`} selected={selected}
    options={options} loading={rows.isFetching && !rows.data} error={message(rows.error)} onSearch={setSearch}
    onChange={onChange} disabled={disabled} emptyText={t`No more of your organizations match.`} />;
}

/** Audience organizations come from the opt-in directory and grant no authority. */
export function AudienceOrganizationPicker({ selected, onChange, disabled, label = t`Selected organizations`,
  helper = t`Members of these organizations may register. Choosing one gives it no say over the event.` }: PickerProps) {
  const [search, setSearch] = useState("");
  const rows = useOrganizationDirectory(search);
  const options = (rows.data?.results ?? []).map((row) => ({ id: row.id, label: row.name, detail: row.slug }));
  return <AsyncSearchPicker label={label} helper={helper} placeholder={t`Search organizations`} selected={selected}
    options={options} loading={rows.isFetching && !rows.data} error={message(rows.error)} onSearch={setSearch}
    onChange={onChange} disabled={disabled} emptyText={t`No listed organization matches. Organizations appear here once they choose to be discoverable.`} />;
}

/** Partner makerspaces; `detail` carries the slug the invitation API takes. */
export function PartnerMakerspacePicker({ selected, onChange, disabled, hostId, label = t`Partner makerspaces`,
  helper = t`Each partner must accept before its members can register.` }: PickerProps & { hostId: number }) {
  const [search, setSearch] = useState("");
  const rows = usePartnerMakerspaces(search, hostId);
  const options = (rows.data?.results ?? []).map((row) => ({ id: row.id, label: row.name, detail: row.slug }));
  return <AsyncSearchPicker label={label} helper={helper} placeholder={t`Search makerspaces`} selected={selected}
    options={options} loading={rows.isFetching && !rows.data} error={message(rows.error)} onSearch={setSearch}
    onChange={onChange} disabled={disabled} emptyText={t`No listed makerspace matches.`} />;
}
