import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import EventCheckInScanner from "./EventCheckInScanner";
import { EventStationSettings } from "./EventStationSettings";
import { EventDisclosure } from "./EventDisclosure";
import { eventKeys } from "./eventsApi";
import { organizedEventKeys } from "./organizedEventsApi";
import { downloadStaffRoster, syncStaffRoster } from "./eventCheckInOfflineApi";
import { OfflineCheckInOperator } from "./OfflineCheckInOperator";
import { wipeOfflineState } from "./eventCheckInOfflineStore";

export function EventCheckInOperator({ visible = true, makerspaceId, eventId, offlineEnabled, canManageStation = true }: {
  visible?: boolean; makerspaceId: number; eventId: number; offlineEnabled: boolean; canManageStation?: boolean;
}) {
  const [scanning, setScanning] = useState(false);
  const queryClient = useQueryClient();
  useEffect(() => {
    if (!offlineEnabled) void wipeOfflineState(`staff:${eventId}`);
  }, [eventId, offlineEnabled]);
  const invalidate = async () => { await Promise.all([
    queryClient.invalidateQueries({ queryKey: eventKeys.registrations(eventId) }),
    queryClient.invalidateQueries({ queryKey: eventKeys.detail(eventId) }),
    queryClient.invalidateQueries({ queryKey: eventKeys.list(makerspaceId) }),
    queryClient.invalidateQueries({ queryKey: eventKeys.checkinHistory(eventId) }),
    queryClient.invalidateQueries({ queryKey: organizedEventKeys.all }),
  ]); };
  if (!visible) return null;
  return <section aria-labelledby="event-checkin-operator-title">
    <h4 id="event-checkin-operator-title" className="title-section mt-3">{t`Attendance check-in`}</h4>
    {scanning ? <EventCheckInScanner makerspaceId={makerspaceId} eventId={eventId} onClose={() => setScanning(false)} /> : <button className="desk-button-primary mt-3 w-full sm:w-auto" type="button" onClick={() => setScanning(true)}>{t`Scan online`}</button>}
    {offlineEnabled ? <><OfflineCheckInOperator scope={`staff:${eventId}`} download={() => downloadStaffRoster(eventId)} synchronize={(roster, operations, receipts) => syncStaffRoster(eventId, roster, operations, receipts)} onSynchronized={invalidate} />{canManageStation ? <div className="mt-3"><EventDisclosure title={t`Check-in stations`}><EventStationSettings eventId={eventId} /></EventDisclosure></div> : null}</> : null}
  </section>;
}
