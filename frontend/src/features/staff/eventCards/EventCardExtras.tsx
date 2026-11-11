// First-aid extras (blood group, emergency contact) that consenting card holders added (Q-I5).
// Organisers read them only while this event switched them on; every read is audited server-side,
// so the list is fetched on an explicit click, never cached, and never pre-loaded.
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorBlock } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";

type Extras = { card_id: number; name: string; blood_group: string; emergency_contact_name: string; emergency_contact_phone: string };
type Settings = { extras_visible_to_organizers: boolean };

export function EventCardExtras({ eventId }: { eventId: number }) {
  const client = useQueryClient();
  const key = ["event-card-settings", eventId];
  const path = `/admin/events/${eventId}/card-settings`;
  const settings = useQuery({ queryKey: key, queryFn: () => staffRequest<Settings>(path) });
  const toggle = useMutation({
    mutationFn: (value: boolean) => staffRequest<Settings>(path, { method: "PUT", body: JSON.stringify({ extras_visible_to_organizers: value }) }),
    onSuccess: (saved) => { client.setQueryData(key, saved); read.reset(); },
  });
  const read = useMutation({ mutationFn: () => staffRequest<Extras[]>(`/admin/events/${eventId}/id-cards/extras`, { cache: "no-store" }) });
  if (!settings.data) return settings.error ? <ErrorBlock error={settings.error} resource={t`card settings`} /> : null;
  const on = settings.data.extras_visible_to_organizers;
  return <section className="grid gap-3 rounded-control border border-line p-3" aria-label={t`Emergency details`}>
    <h4 className="font-semibold text-ink">{t`Emergency details`}</h4>
    <p className="text-sm text-muted">{t`Blood group and emergency contact, only for card holders who chose to share them. Each view is recorded in the audit log.`}</p>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={on} disabled={toggle.isPending} onChange={(event) => toggle.mutate(event.target.checked)} />
      {t`Let organisers of this event see shared emergency details`}</label>
    {on ? <button type="button" className="desk-button min-h-11 justify-self-start" disabled={read.isPending} onClick={() => read.mutate()}>
      {read.data ? t`Refresh emergency details` : t`Show emergency details`}</button> : null}
    {[toggle.error, read.error].find(Boolean) ? <ErrorBlock error={[toggle.error, read.error].find(Boolean)} /> : null}
    {on && read.data ? read.data.length ? <ul className="grid gap-2 text-sm">{read.data.map((row) => <li key={row.card_id} className="grid gap-0.5 rounded-control bg-panel p-2">
      <span className="font-semibold text-ink">{row.name}</span>
      <span className="text-muted">{[row.blood_group && t`Blood group ${row.blood_group}`,
        row.emergency_contact_name && t`Contact ${row.emergency_contact_name}`, row.emergency_contact_phone].filter(Boolean).join(" · ")}</span>
    </li>)}</ul> : <p className="text-sm text-muted">{t`No card holder has shared emergency details.`}</p> : null}
  </section>;
}
