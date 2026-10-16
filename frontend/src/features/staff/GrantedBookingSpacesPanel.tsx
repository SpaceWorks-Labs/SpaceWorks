import { useState } from "react";
import { EmptyState, Skeleton } from "../../components/ui";
import { BookingDrawer } from "./BookingDrawer";
import { useAccessibleBookingSpaces } from "./bookingStaffGrantsApi";
import { Panel } from "./panels/shared";

export function GrantedBookingSpacesPanel({ makerspaceId }: { makerspaceId?: number }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<{ id: number; makerspace_id: number } | null>(null);
  const spaces = useAccessibleBookingSpaces(page, makerspaceId);
  return <Panel title="Assigned booking resources">
    {spaces.isLoading ? <Skeleton className="h-32 w-full" /> : null}
    {spaces.error ? <EmptyState title="Unable to load resources" description={spaces.error.message} action={<button className="desk-button" type="button" onClick={() => spaces.refetch()}>Retry</button>} /> : null}
    {spaces.data?.results.length === 0 ? <EmptyState title="No assigned resources" description="Your access may have been revoked." /> : null}
    <div className="grid gap-2">{spaces.data?.results.map((space) => <button className="desk-button-ghost h-auto justify-start border border-line p-4 text-left" type="button" key={space.id} onClick={() => setSelected(space)}><span>{space.name}<span className="mt-1 block text-xs text-muted">{space.staff_permissions?.map((entry) => entry.replace(/_/g, " ")).join(", ")}</span></span></button>)}</div>
    {spaces.data ? <div className="mt-4 flex gap-3"><button className="desk-button" disabled={!spaces.data.previous} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page}</span><button className="desk-button" disabled={!spaces.data.next} onClick={() => setPage(page + 1)}>Next</button></div> : null}
    {selected ? <BookingDrawer spaceId={selected.id} makerspaceId={selected.makerspace_id} onClose={() => setSelected(null)} /> : null}
  </Panel>;
}
