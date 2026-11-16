// The one mount that replaces the three DeskBadgePanel mounts. With `events.badge_desk_print` on, the desk
// route answers and the bulk badge panel shows (the designer lives in the Cards panel); with it off the route
// answers 404 and the older panel stays, so switching the feature off removes this behaviour everywhere.
import { useQuery } from "@tanstack/react-query";

import { StructuredApiError } from "../../../lib/api";
import { DeskBadgePanel } from "../eventCredentials/DeskBadgePanel";
import { sessionScope } from "../eventProgramme/sessionScope";
import { BulkBadgesPanel } from "./BulkBadgesPanel";
import { deskKey, fetchDesk } from "./deskBadgeApi";

export function DeskBadgeSwitch({ eventId, eventVersion, registrationIds, canEdit, canPrint }: {
  eventId: number; eventVersion?: number; registrationIds: number[]; canEdit: boolean; canPrint: boolean;
}) {
  const probe = useQuery({ queryKey: [...deskKey(eventId), "probe", ...sessionScope()], enabled: canPrint || canEdit, retry: false, staleTime: 60_000,
    queryFn: () => fetchDesk(eventId) });
  if (probe.isPending && (canPrint || canEdit)) return null;
  const off = probe.error instanceof StructuredApiError && probe.error.status === 404;
  if (probe.data || (probe.error && !off && !canEdit)) return <BulkBadgesPanel eventId={eventId} canPrint={canPrint} />;
  return <DeskBadgePanel eventId={eventId} eventVersion={eventVersion} registrationIds={registrationIds} canEdit={canEdit} canPrint={canPrint} />;
}
