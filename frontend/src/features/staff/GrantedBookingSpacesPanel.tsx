import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListRow } from "../../components/ui";
import { ListLayout } from "../../components/layouts";
import { BookingDrawer } from "./BookingDrawer";
import { useAccessibleBookingSpaces } from "./bookingStaffGrantsApi";
import type { GrantedListFrame } from "./GrantedResourcesPanel";

/** Resources this account holds a booking grant on. Opening one replaces the list with its page; Back returns. */
export function GrantedBookingSpacesPanel({ makerspaceId, frame }: { makerspaceId?: number; frame?: GrantedListFrame }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: number; makerspace_id: number } | null>(null);
  const spaces = useAccessibleBookingSpaces(page, makerspaceId);
  if (selected) return <BookingDrawer key={selected.id} spaceId={selected.id} makerspaceId={selected.makerspace_id} onClose={() => setSelected(null)} />;
  return <ListLayout header={{ title: t`Assigned booking resources`, subtitle: t`Open a resource to use your assigned permissions.` }} {...frame}
    state={spaces.isLoading ? { status: "loading" } : spaces.error
      ? { status: "error", error: `Unable to load resources. ${spaces.error.message}`, onRetry: () => { void spaces.refetch(); } } : { status: "ready" }}
    isEmpty={spaces.data?.results.length === 0} empty={{ message: t`No assigned resources. Your access may have been revoked.` }}
    body={{ kind: "rows", rows: spaces.data?.results.map((space) => <ListRow key={space.id} title={space.name}
      identity={{ kind: "icon", icon: "Calendar", tone: "info" }} onClick={() => setSelected(space)}
      meta={space.staff_permissions?.map((entry) => entry.replace(/_/g, " ")).join(", ")} />) }}
    pagination={spaces.data ? { page, pageSize: 24, count: spaces.data.count, onChange: setPage } : undefined} />;
}
