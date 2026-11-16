import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { Field } from "../../components/ui";
import { eventUseKeys, fetchStaffEventOptions } from "./api";

/**
 * "This is for an event" on the staff booking form for a machine space (decision 342). Staff with machine
 * authority may pick any open event of the space; the server holds everyone else to the member's own events.
 * Hidden when the space has no open events or the staff member may not see the list.
 */
export function StaffBookingEventPicker({ makerspaceId, value, onChange, disabled }: {
  makerspaceId: number; value: string; onChange: (eventId: string) => void; disabled?: boolean;
}) {
  const events = useQuery({ queryKey: eventUseKeys.staffOptions(makerspaceId), queryFn: () => fetchStaffEventOptions(makerspaceId),
    retry: false, staleTime: 60_000 });
  if (!events.data?.length) return null;
  return <Field label={t`This is for an event`} hint={t`Optional. Logged with the booking for the event's organisers.`} className="sm:col-span-2">
    <select className="desk-input min-h-11 w-full" value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
      <option value="">{t`Not for an event`}</option>
      {events.data.map(row => <option key={row.id} value={String(row.id)}>{row.title}</option>)}
    </select>
  </Field>;
}
