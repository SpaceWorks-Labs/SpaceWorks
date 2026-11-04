import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { staffRequest, staffRequestBlob } from '../../../lib/api';
import { useUrlListState } from '../../../lib/useUrlListState';
import { ErrorBlock, Field, Pagination, Tabs } from '../../../components/ui';
import type { EventStaffListPage } from '../../../generated/api';
import { ListViewControls } from '../ListViewControls';
import { sessionScope } from './sessionScope';

/** Each list: its saved-view entity and the filters the server allows (anything else answers 400). */
export const LISTS = {
  guests: { label: 'Guests', entity: 'event_guests', filters: { status: ['registered', 'pending_approval', 'waitlisted', 'attended', 'cancelled', 'rejected'] } },
  teams: { label: 'Teams', entity: 'event_teams', filters: { state: ['forming', 'locked', 'disbanded'] } },
  submissions: { label: 'Submissions', entity: 'event_submissions', filters: { state: ['draft', 'submitted', 'locked', 'under_review', 'judged', 'disqualified', 'withdrawn'], triage: ['pending', 'eligible', 'ineligible', 'hidden'] } },
  results: { label: 'Results', entity: 'event_results', filters: {} },
  progress: { label: 'Judging progress', entity: 'event_progress', filters: { below_target: ['true'] } },
} as const;
type ListKey = keyof typeof LISTS;
const SEARCHABLE: ListKey[] = ['guests', 'teams', 'submissions'];
const FILTER_LABELS: Record<string, string> = { status: 'Status', state: 'State', triage: 'Eligibility', below_target: 'Below the review target' };

/** Build the exact query string the list and its CSV export share (filters only, never the page). */
export function filterQuery(list: ListKey, values: Record<string, string>) {
  const params = new URLSearchParams();
  const keys = [...Object.keys(LISTS[list].filters), ...(SEARCHABLE.includes(list) ? ['q'] : [])];
  for (const key of keys) if (values[key]) params.set(key, values[key]);
  return params.toString();
}

export function EventStaffLists({ eventId, makerspaceId, canSaveViews }: { eventId: number; makerspaceId: number; canSaveViews: boolean }) {
  const [list, setList] = useState<ListKey>('teams');
  return <section className="grid gap-4" aria-label="Event lists and exports">
    <h3 className="title-panel">Lists and exports</h3>
    <Tabs label="Event lists" activeKey={list} onChange={key => setList(key as ListKey)}
      tabs={Object.entries(LISTS).map(([key, value]) => ({ key, label: value.label }))}>
      <StaffList key={list} eventId={eventId} makerspaceId={makerspaceId} list={list} canSaveViews={canSaveViews} />
    </Tabs>
  </section>;
}

function StaffList({ eventId, makerspaceId, list, canSaveViews }: { eventId: number; makerspaceId: number; list: ListKey; canSaveViews: boolean }) {
  const spec = LISTS[list];
  const state = useUrlListState({ page: '1', q: '', status: '', state: '', triage: '', below_target: '' }, `${list}-`);
  const query = filterQuery(list, state.values);
  const rows = useQuery({ queryKey: ['event-staff-list', eventId, list, query, state.page, ...sessionScope()], gcTime: 0, retry: false,
    queryFn: () => staffRequest<EventStaffListPage>(`/admin/events/${eventId}/lists/${list}/?${query}${query ? '&' : ''}page=${state.page}`) });
  const exportCsv = useMutation({ mutationFn: async () => {
    const blob = await staffRequestBlob(`/admin/events/${eventId}/lists/${list}/export/${query ? `?${query}` : ''}`);
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `event-${eventId}-${list}.csv`;
    link.click(); URL.revokeObjectURL(link.href);
  } });
  const columns = rows.data?.columns ?? [];
  return <div className="grid gap-3">
    <ListViewControls state={state} makerspaceId={makerspaceId} entity={spec.entity} sorts={[]} savedViews={canSaveViews}
      search={SEARCHABLE.includes(list)} searchLabel={`Search ${spec.label.toLowerCase()}`}
      controls={<>{Object.entries(spec.filters).map(([key, options]) => <Field key={key} label={FILTER_LABELS[key] ?? key}>
        <select className="desk-input min-h-11" value={(state.values as Record<string, string>)[key] ?? ''} onChange={e => state.setFilter(key, e.target.value)}>
          <option value="">Any</option>{(options as readonly string[]).map(option => <option key={option} value={option}>{option.replace('_', ' ')}</option>)}</select></Field>)}
        <button type="button" className="desk-button min-h-11" disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>Export these rows as CSV</button></>} />
    <ErrorBlock error={rows.error || exportCsv.error} onRetry={() => void rows.refetch()} />
    {rows.isLoading ? <p role="status">Loading {spec.label.toLowerCase()}…</p> : null}
    {rows.data ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">{spec.label}</caption>
      <thead><tr>{columns.map(column => <th key={column} scope="col">{column.replace('_', ' ')}</th>)}</tr></thead>
      <tbody>{rows.data.results.map((row, index) => <tr key={String(row.id ?? index)}>{columns.map(column =>
        <td key={column}>{String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div> : null}
    {rows.data && !rows.data.count ? <p className="text-sm text-muted">No rows match these filters.</p> : null}
    <Pagination page={state.page} count={rows.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((rows.data?.count ?? 0) / 24)} onChange={state.setPage} />
  </div>;
}
