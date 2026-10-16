import { useState } from "react";
import { EmptyState, ErrorBlock, Pagination, Skeleton } from "../../components/ui";
import { eventRange } from "./profileFormat";
import { usePublicProfileEvents, type PublicProfileEvent } from "./publicProfileApi";

const BADGE_COPY: Record<PublicProfileEvent["badge"], { label: string; className: string }> = {
  HOSTED: { label: "Hosted", className: "border-transparent bg-brand-soft text-brand-ink" },
  SPOKE: { label: "Spoke", className: "border-transparent bg-accent-soft text-accent-ink" },
  ATTENDED: { label: "Attended", className: "border-line bg-surface text-ink" },
};

export function ProfileEventsTab({ handle, preview }: { handle: string; preview: boolean }) {
  const [page, setPage] = useState(1);
  const events = usePublicProfileEvents(handle, page, !preview);
  if (preview) return <p className="text-sm text-muted">Events you attended, hosted or spoke at appear here once the page is published.</p>;
  return <section aria-labelledby="profile-events" className="grid gap-4">
    <h2 id="profile-events" className="title-panel">Past events</h2>
    {events.isLoading ? <div aria-label="Loading past events" className="grid gap-3">{[0, 1, 2].map(row => <Skeleton key={row} className="h-16" />)}</div> : null}
    {events.error ? <ErrorBlock error={new Error("Couldn't load events. Try again.")} onRetry={() => { void events.refetch(); }} /> : null}
    {events.data && !events.data.results.length ? <EmptyState message="No past events yet." /> : null}
    {events.data?.results.length ? <ul className="divide-y divide-line">
      {events.data.results.map((event, index) => <li key={`${event.starts_at}-${index}`} className="flex flex-wrap items-start justify-between gap-3 py-4">
        <div className="min-w-0 basis-56 grow">
          <p className="break-words font-semibold text-ink">{event.title}</p>
          <p className="text-sm text-muted"><time dateTime={event.starts_at}>{eventRange(event.starts_at, event.ends_at)}</time>{event.host ? ` · ${event.host}` : ""}</p>
        </div>
        <span className={`chip uppercase tracking-[0.06em] ${BADGE_COPY[event.badge]?.className ?? ""}`}>{BADGE_COPY[event.badge]?.label ?? event.badge}</span>
      </li>)}
    </ul> : null}
    {events.data && events.data.count > 24 ? <Pagination page={page} pageSize={24} count={events.data.count}
      totalPages={Math.ceil(events.data.count / 24)} onChange={setPage} /> : null}
  </section>;
}
