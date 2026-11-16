import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorBlock, ListRow, Pagination, SegmentedControl, StatusBadge } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { staffRequest } from "../../lib/api";
import { formatLocale } from "../../lib/format";
import type { Paginated } from "../../lib/usePaginatedQuery";
import { eventKeys } from "./eventsApiTypes";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";

export type QueueRow = {
  id: number; status: "pending_approval" | "waitlisted"; created_at: string; name: string;
  event: { id: number; title: string; starts_at: string; capacity: number };
};
type Filter = "all" | QueueRow["status"];

export const registrationQueueKey = (makerspaceId: number) => ["event-registration-queue", makerspaceId] as const;

/**
 * Open item A22 (EB6): registrations waiting on staff across every upcoming event this person may manage
 * registrations for. Approving and promoting use the same per-registration routes as the event roster.
 */
export function EventRegistrationQueue({ makerspaceId, onOpenEvent }: { makerspaceId: number; onOpenEvent: (eventId: number) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(1);
  const client = useQueryClient();
  const query = new URLSearchParams({ page: String(page), ...(filter === "all" ? {} : { status: filter }) });
  const queue = useQuery({
    queryKey: [...registrationQueueKey(makerspaceId), filter, page],
    queryFn: () => staffRequest<Paginated<QueueRow>>(`/admin/makerspace/${makerspaceId}/event-registration-queue?${query}`),
  });
  const action = useMutation({
    mutationFn: (row: QueueRow) => staffRequest(`/admin/event-registrations/${row.id}/${row.status === "waitlisted" ? "promote" : "approve"}/`,
      { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (_data, row) => Promise.all([
      client.invalidateQueries({ queryKey: registrationQueueKey(makerspaceId) }),
      client.invalidateQueries({ queryKey: eventKeys.registrations(row.event.id) }),
      client.invalidateQueries({ queryKey: eventKeys.detail(row.event.id) }),
      client.invalidateQueries({ queryKey: eventKeys.list(makerspaceId) }),
      client.invalidateQueries({ queryKey: ["dashboard", makerspaceId] }),
    ]),
  });
  const data = queue.data;
  const when = (value: string) => new Date(value).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
  return <section aria-labelledby="event-queue-title" className="grid gap-4">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 id="event-queue-title" className="title-panel">{t`Waiting on you`} <span className="tabular-nums">({data?.count ?? 0})</span></h2>
        <p className="mt-1 text-sm text-muted">{t`Registrations to approve and waitlisted places to fill, across your upcoming events. People are told either way.`}</p>
      </div>
      <SegmentedControl label={t`Waiting status`} value={filter} onChange={value => { setFilter(value as Filter); setPage(1); }}
        options={[{ value: "all", label: t`All` }, { value: "pending_approval", label: t`To approve` }, { value: "waitlisted", label: t`Waitlist` }]} />
    </div>
    {action.error ? <ErrorBlock error={action.error} /> : null}
    <QueryContent state={opsQueryState(queue, "waiting registrations")} isEmpty={data?.results.length === 0}
      empty={{ message: filter === "waitlisted" ? t`No one is on a waitlist.` : filter === "pending_approval"
        ? t`No registrations to approve.` : t`Nothing is waiting. New registrations that need you appear here.` }}>
      <ul className="grid gap-3">{data?.results.map(row => {
        const busy = action.isPending && action.variables?.id === row.id;
        return <li key={row.id}><ListRow title={row.name || t`Unnamed registration`} identity={{ kind: "date", date: row.event.starts_at }}
          meta={<><span className="block font-medium text-ink">{row.event.title}</span>
            <span className="block">{t`Event ${when(row.event.starts_at)} · registered ${when(row.created_at)}`}</span></>}
          right={<div className="flex flex-wrap items-center justify-end gap-2">
            <StatusBadge domain="event" status={row.status} label={opsStatusLabel(row.status)} />
            <button type="button" className="desk-button-brand min-h-11" disabled={busy} onClick={() => action.mutate(row)}>
              {row.status === "waitlisted" ? busy ? t`Giving a place…` : t`Give a place` : busy ? t`Approving…` : t`Approve`}</button>
            <button type="button" className="desk-button-ghost min-h-11" onClick={() => onOpenEvent(row.event.id)}>{t`Open event`}</button>
          </div>} /></li>;
      })}</ul>
      {data && data.count > 24 ? <Pagination page={page} pageSize={24} count={data.count} totalPages={Math.ceil(data.count / 24)} onChange={setPage} /> : null}
    </QueryContent>
  </section>;
}
