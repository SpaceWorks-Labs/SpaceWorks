import { plural, t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { EmptyState, ErrorText, Skeleton } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { formatDate, formatLocale } from "../../../lib/format";

export type EventInsights = {
  window_days: number; k: number;
  top_events: { event_id: number; title: string; starts_at: string; attended: number }[];
  returning: { suppressed: boolean; attendees: number | null; returning_percent: number | null };
};

/** Space insights live at `admin/events/insights/?makerspace=`, an organisation's at `admin/organizations/<id>/events/insights/`. */
export const spaceInsightsPath = (makerspaceId: number) => `/admin/events/insights/?makerspace=${makerspaceId}`;
export const organizationInsightsPath = (organizationId: number) => `/admin/organizations/${organizationId}/events/insights/`;

/**
 * The best-attended events of the last six months and how many attendees came back (parity E-F3, A21).
 * Counts only: no person is ever named, and the returning share stays hidden for groups under k.
 */
export function EventInsightsCard({ path, onOpenEvent }: { path: string; onOpenEvent?: (eventId: number) => void }) {
  const query = useQuery({ queryKey: ["event-insights", path], retry: false, queryFn: () => staffRequest<EventInsights>(path) });
  if (query.isLoading) return <Skeleton className="h-40 w-full" />;
  if (query.error || !query.data) return <ErrorText resource={t`event insights`} onRetry={() => { void query.refetch(); }} />;
  const { top_events: top, returning, window_days: days, k } = query.data;
  const most = Math.max(1, ...top.map(row => row.attended));
  return <section className="grid gap-5" aria-label={t`Event insights`}>
    <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(12rem,1fr)]">
      <div className="grid content-start gap-2">
        <h3 className="title-section">{plural(days, { one: "Best attended in the last # day", other: "Best attended in the last # days" })}</h3>
        {top.length ? <ol className="grid gap-2">{top.map((row, index) => <li key={row.event_id} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-3 text-sm">
          <span className="tabular-nums text-muted">{index + 1}</span>
          <span className="grid min-w-0 gap-1">
            {onOpenEvent ? <button type="button" className="min-h-11 truncate text-left font-semibold text-ink underline-offset-4 hover:underline" onClick={() => onOpenEvent(row.event_id)}>{row.title}</button>
              : <span className="truncate font-semibold text-ink">{row.title}</span>}
            <span aria-hidden="true" className="h-1.5 rounded-full bg-surface"><span className="block h-1.5 rounded-full bg-brand" style={{ width: `${(row.attended / most) * 100}%` }} /></span>
            <span className="text-xs text-muted">{formatDate(row.starts_at)}</span>
          </span>
          <span className="tabular-nums font-semibold">{plural(row.attended, { one: "# came", other: "# came" })}</span>
        </li>)}</ol> : <EmptyState message={t`No events with check-ins in this period yet.`} />}
      </div>
      <div className="grid content-start gap-1 rounded-xl border border-line bg-panel p-4">
        <p className="text-sm font-semibold text-ink">{t`Returning attendees`}</p>
        {returning.suppressed || returning.returning_percent === null
          ? <p className="text-sm text-muted">{plural(k, { one: "Shown once at least # person has attended, so nobody can be singled out.", other: "Shown once at least # people have attended, so nobody can be singled out." })}</p>
          : <><p className="order-first text-3xl font-semibold tabular-nums text-ink">{returning.returning_percent.toLocaleString(formatLocale(), { maximumFractionDigits: 1 })}%</p>
            <p className="text-sm text-muted">{plural(returning.attendees ?? 0, { one: "of # attendee came to more than one event.", other: "of # attendees came to more than one event." })}</p></>}
      </div>
    </div>
  </section>;
}
