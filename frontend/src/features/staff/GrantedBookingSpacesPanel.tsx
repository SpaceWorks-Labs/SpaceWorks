import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListRow } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { BookingDrawer } from "./BookingDrawer";
import { useAccessibleBookingSpaces } from "./bookingStaffGrantsApi";
import { bookingPermissionLabel } from "./bookingStaffPermissions";
import type { GrantedListFrame } from "./GrantedResourcesPanel";
import type { StaffAuthUser } from "../../lib/api";
import { SpaceScope } from "./SpaceScope";

/** Resources this account holds a booking grant on. Opening one replaces the list with its page; Back returns. */
export function GrantedBookingSpacesPanel({ makerspaceId, frame, grants = [] }: { makerspaceId?: number; frame?: GrantedListFrame; grants?: StaffAuthUser["booking_grants"] }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: number; makerspace_id: number } | null>(null);
  const spaces = useAccessibleBookingSpaces(page, makerspaceId);
  // A19: the resource's own space scopes the drawer, so related activity shows for any selected space.
  if (selected) return <SpaceScope makerspaceId={selected.makerspace_id} slug={grants.find(grant => grant.makerspace_id === selected.makerspace_id)?.makerspace_slug ?? ""}>
    <BookingDrawer key={selected.id} spaceId={selected.id} makerspaceId={selected.makerspace_id} onClose={() => setSelected(null)} /></SpaceScope>;
  return <ListLayout header={{ title: t`Assigned booking resources`, subtitle: t`Open a resource to use your assigned permissions.` }} {...frame}
    state={spaces.isLoading ? { status: "loading" } : spaces.error
      ? { status: "error", error: t`Unable to load resources. ${spaces.error.message}`, onRetry: () => { void spaces.refetch(); } } : { status: "ready" }}
    isEmpty={spaces.data?.results.length === 0} empty={{ message: t`No assigned resources. Your access may have been revoked.` }}
    body={{ kind: "rows", rows: spaces.data?.results.map((space) => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Calendar", tone: "info" }} onClick={() => setSelected(space)}
      meta={space.staff_permissions?.map(bookingPermissionLabel).join(", ")} />) }}
    pagination={spaces.data ? { page, pageSize: 24, count: spaces.data.count, onChange: setPage } : undefined} />;
}
