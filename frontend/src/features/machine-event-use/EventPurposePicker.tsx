import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { eventUseKeys, fetchMyEvents } from "./api";

/**
 * "This is for an event" (decision 342): optional, always available. Lists only the events this person may act
 * for in this makerspace; with none, nothing is shown, so a member with no events never sees an empty control.
 */
export function EventPurposePicker({ makerspaceId, value, onChange, disabled }: {
  makerspaceId: number | undefined; value: string; onChange: (eventId: string) => void; disabled?: boolean;
}) {
  const events = useQuery({ queryKey: eventUseKeys.mine(makerspaceId ?? 0), queryFn: () => fetchMyEvents(makerspaceId ?? 0),
    enabled: makerspaceId !== undefined && makerspaceId > 0, retry: false, staleTime: 60_000 });
  if (!events.data?.length) return null;
  return <Field label={t`This is for an event`} hint={t`Optional. Staff and the event's organisers can see this use.`}>
    <select className="desk-input min-h-11 w-full" value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
      <option value="">{t`Not for an event`}</option>
      {events.data.map(row => <option key={row.id} value={String(row.id)}>{row.title}</option>)}
    </select>
  </Field>;
}
