import { t } from "@lingui/core/macro";
import { useState } from "react";

import { EmptyState, ErrorBlock, ListRow, Pagination, RelativeTime, Skeleton } from "../../components/ui";
import { useEventCheckIns, type EventCheckInRow } from "./eventPartnersApi";

const sourceLabel = (): Record<EventCheckInRow["source"], string> => ({
  qr: t`QR scan`, manual: t`Manual`, offline: t`Offline sync`, station: t`Venue station`, legacy: t`Earlier record`,
});
const PAGE_SIZE = 24;

/** Who has checked in, newest first. Refreshes after every scan and on an interval for other doors. */
export function EventCheckInList({ eventId, visible = true }: { eventId: number; visible?: boolean }) {
  const [page, setPage] = useState(1);
  const rows = useEventCheckIns(eventId, page, visible);
  if (!visible) return null;
  return <section aria-labelledby="event-checked-in-title" className="grid min-w-0 content-start gap-3">
    <h4 id="event-checked-in-title" className="title-section mt-3">{t`Checked in${rows.data ? ` (${rows.data.count})` : ""}`}</h4>
    {rows.isLoading ? <Skeleton className="h-20 w-full" /> : null}
    {rows.error ? <ErrorBlock error={rows.error} resource={t`the check-in list`} onRetry={() => void rows.refetch()} /> : null}
    {rows.data && !rows.data.count ? <EmptyState message={t`No one has checked in yet. Scanned attendees appear here.`} /> : null}
    {rows.data?.results.length ? <ul className="grid gap-2" aria-label={t`Checked-in attendees`}>
      {rows.data.results.map((row) => <li key={row.registration_id}>
        <ListRow title={row.attendee_name} identity={{ kind: "avatar", name: row.attendee_name, seed: String(row.registration_id) }}
          meta={[row.ticket_type, sourceLabel()[row.source], row.checked_in_by ? t`by ${row.checked_in_by}` : null].filter(Boolean).join(" · ")}
          right={row.attended_at ? <span className="text-sm text-muted"><RelativeTime date={row.attended_at} exact /></span> : null} />
      </li>)}
    </ul> : null}
    {rows.data ? <Pagination page={page} totalPages={Math.ceil(rows.data.count / PAGE_SIZE)} count={rows.data.count} pageSize={PAGE_SIZE} onChange={setPage} /> : null}
  </section>;
}
