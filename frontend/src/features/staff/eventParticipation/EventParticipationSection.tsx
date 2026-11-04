import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import type { StaffEvent } from "../eventsApi";
import type { MoreSection } from "../eventDrawerTabs";
import type { eventAccess } from "../eventStaffPermissions";
import { sessionScope } from "../eventProgramme/sessionScope";
import { AttendancePanel } from "./AttendancePanel";
import { CheckInListsPanel } from "./CheckInListsPanel";
import { CrewPanel } from "./CrewPanel";
import { ReviewStagesPanel } from "./ReviewStagesPanel";

type Addon = { id: number; name: string };

/**
 * Lane L21a's drawer surfaces. Each one shows only when its capability is on and the viewer
 * holds the event permission the API checks again: review stages beside applications, the
 * attendance check in the Emails section, the crew roster and the check-in lists.
 */
export function EventParticipationSection({ event, section, access, features }: {
  event: StaffEvent; section: MoreSection; access: ReturnType<typeof eventAccess>; features: readonly string[];
}) {
  const on = (key: string) => features.includes(key);
  if (section === "applications" && on("events.application_stages") && (access.applications || access.hackathon)) {
    return <ReviewStagesPanel eventId={event.id} />;
  }
  if (section === "broadcasts" && on("events.attendance_confirmation") && access.registrations) {
    return <AttendancePanel eventId={event.id} canConfigure={access.manager} />;
  }
  if (section === "crew" && on("events.crew") && access.volunteers) {
    return <CrewPanel eventId={event.id} signupUrl={`${window.location.origin}/member/events/${event.id}/crew`} />;
  }
  if (section === "checkin-lists" && on("events.checkin_lists") && access.checkIn) {
    return <CheckInLists eventId={event.id} canManage={access.registrations} withAddons={on("events.addons")} />;
  }
  return null;
}

/** Add-ons are read only here, to offer "only for buyers of an add-on" lists (L6 owns them). */
function CheckInLists({ eventId, canManage, withAddons }: { eventId: number; canManage: boolean; withAddons: boolean }) {
  const addons = useQuery({ queryKey: ["staff-event-addons-for-lists", eventId, ...sessionScope()], enabled: withAddons,
    retry: false, queryFn: () => staffRequest<Addon[] | { results: Addon[] }>(`/admin/events/${eventId}/addons/`) });
  const rows = Array.isArray(addons.data) ? addons.data : addons.data?.results ?? [];
  return <CheckInListsPanel eventId={eventId} canManage={canManage} addons={rows.map(row => ({ id: row.id, name: row.name }))} />;
}
