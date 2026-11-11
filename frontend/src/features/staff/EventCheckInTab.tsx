import { t } from "@lingui/core/macro";
import { Card, StatCard } from "../../components/ui";
import { EventCheckInOperator } from "./EventCheckInOperator";
import { EventCheckInList } from "./EventCheckInList";
import type { StaffEvent } from "./eventsApi";

/**
 * The Check-in tab. A draft keeps the tab so door staff know what to expect, but there is no
 * scanner until the event is published: the API refuses check-ins for unpublished events.
 * The scanner and list stay mounted off-tab so an open scanner keeps its state.
 */
export function EventCheckInTab({ event, makerspaceId, active, checkable, canManageStation }: {
  event: StaffEvent; makerspaceId: number; active: boolean; checkable: boolean; canManageStation: boolean;
}) {
  if (!checkable) return active ? <Card><h2 className="title-panel">{t`Check-in opens once the event is published`}</h2>
    <p className="mt-2 text-sm text-muted">{event.offline_checkin_enabled ? t`This event is still a draft. When it is published, this tab gives you the attendance scanner, the checked-in list and offline check-in.` : t`This event is still a draft. When it is published, this tab gives you the attendance scanner and the checked-in list.`}</p></Card> : null;
  if (!active) return null;
  const counts = event.registration_counts;
  return <>
    {active ? <StatCard label={t`Checked in`} value={counts.attended} of={counts.registered + counts.attended || undefined} /> : null}
    <div className="grid gap-6 lg:grid-cols-2" hidden={!active}>
      <EventCheckInOperator visible={active} makerspaceId={makerspaceId} eventId={event.id} offlineEnabled={event.offline_checkin_enabled} canManageStation={canManageStation} />
      <EventCheckInList eventId={event.id} visible={active} />
    </div>
  </>;
}
