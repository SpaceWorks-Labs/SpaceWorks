import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { staffRequest, staffRequestBlob } from '../../../lib/api';
import { useUrlListState } from '../../../lib/useUrlListState';
import { ErrorBlock, Field, Pagination, Tabs } from '../../../components/ui';
import type { EventStaffListPage } from '../../../generated/api';
import { ListViewControls } from '../ListViewControls';
import type { ListPreset } from '../SavedViewsMenu';
import { useStaffQuery, type CheckInList } from '../eventParticipation/api';
import { sessionScope } from './sessionScope';
import { filterLabel, listLabel, optionLabel } from './staffListLabels';

/** Each list: its saved-view entity and the filters the server allows (anything else answers 400). */
export const LISTS = {
  guests: { entity: 'event_guests', filters: { status: ['registered', 'pending_approval', 'waitlisted', 'attended', 'cancelled', 'rejected'],
    reply: ['yes', 'no', 'waiting', 'not_asked'], list: [], collected: ['yes', 'no'] } },
  teams: { entity: 'event_teams', filters: { state: ['forming', 'locked', 'disbanded'] } },
  submissions: { entity: 'event_submissions', filters: { state: ['draft', 'submitted', 'locked', 'under_review', 'judged', 'disqualified', 'withdrawn'], triage: ['pending', 'eligible', 'ineligible', 'hidden'] } },
  results: { entity: 'event_results', filters: {} },
  progress: { entity: 'event_progress', filters: { below_target: ['true'] } },
} as const;
export type ListKey = keyof typeof LISTS;
// E-B4 (D13): the results list searches the project title or the prize name.
const SEARCHABLE: ListKey[] = ['guests', 'teams', 'submissions', 'results'];
const DEFAULTS = { page: '1', q: '', status: '', state: '', triage: '', below_target: '', reply: '', list: '', collected: '' };

/** Build the exact query string the list and its CSV export share (filters only, never the page). */
export function filterQuery(list: ListKey, values: Record<string, string>) {
  const params = new URLSearchParams();
  const keys = [...Object.keys(LISTS[list].filters), ...(SEARCHABLE.includes(list) ? ['q'] : [])];
  for (const key of keys) if (values[key]) params.set(key, values[key]);
  return params.toString();
}

/** Which guest filters this space offers: the reply needs attendance checks, the per-list ones check-in lists. */
export function guestFilterKeys(features: readonly string[]) {
  return ['status', ...(features.includes('events.attendance_confirmation') ? ['reply'] : []),
    ...(features.includes('events.checkin_lists') ? ['list', 'collected'] : [])];
}

export function EventStaffLists({ eventId, makerspaceId, canSaveViews, features = [], lists = ['teams', 'guests', 'submissions', 'results', 'progress'] }: {
  eventId: number; makerspaceId: number; canSaveViews: boolean; features?: readonly string[];
  /** The lists to offer; the registrations tab shows the guest list alone. */
  lists?: ListKey[];
}) {
  const [list, setList] = useState<ListKey>(lists[0]);
  const body = <StaffList key={list} eventId={eventId} makerspaceId={makerspaceId} list={list} canSaveViews={canSaveViews} features={features} />;
  return <section className="grid gap-4" aria-label={t`Event lists and exports`}>
    {lists.length > 1 ? <h3 className="title-panel">{t`Lists and exports`}</h3> : null}
    {lists.length > 1 ? <Tabs label={t`Event lists`} activeKey={list} onChange={key => setList(key as ListKey)}
      tabs={lists.map(key => ({ key, label: listLabel(key) }))}>{body}</Tabs> : body}
  </section>;
}

function StaffList({ eventId, makerspaceId, list, canSaveViews, features }: { eventId: number; makerspaceId: number; list: ListKey; canSaveViews: boolean; features: readonly string[] }) {
  const spec = LISTS[list];
  const label = listLabel(list);
  const state = useUrlListState(DEFAULTS, `${list}-`);
  const query = filterQuery(list, state.values);
  const guests = list === 'guests';
  const shown = guests ? guestFilterKeys(features) : Object.keys(spec.filters);
  const rows = useQuery({ queryKey: ['event-staff-list', eventId, list, query, state.page, ...sessionScope()], gcTime: 0, retry: false,
    queryFn: () => staffRequest<EventStaffListPage>(`/admin/events/${eventId}/lists/${list}/?${query}${query ? '&' : ''}page=${state.page}`) });
  // Ready-made guest filters with their counts, and the open check-in lists for the per-list filter.
  const presets = useQuery({ queryKey: ['event-staff-list-presets', eventId, list, ...sessionScope()], enabled: guests, retry: false,
    queryFn: () => staffRequest<{ results: ListPreset[] }>(`/admin/events/${eventId}/lists/${list}/presets/`) });
  const checkinLists = useStaffQuery<CheckInList[]>(eventId, '/checkin-lists/', guests && shown.includes('list'));
  const exportCsv = useMutation({ mutationFn: async () => {
    const blob = await staffRequestBlob(`/admin/events/${eventId}/lists/${list}/export/${query ? `?${query}` : ''}`);
    const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `event-${eventId}-${list}.csv`;
    link.click(); URL.revokeObjectURL(link.href);
  } });
  const columns = rows.data?.columns ?? [];
  const options = (key: string): { value: string; label: string }[] => key === 'list'
    ? (checkinLists.data ?? []).filter(row => !row.archived).map(row => ({ value: String(row.id), label: row.name }))
    : ((spec.filters as Record<string, readonly string[]>)[key] ?? []).map(value => ({ value, label: optionLabel(key, value) }));
  const perEvent = features.includes('events.event_saved_views');
  return <div className="grid gap-3">
    <ListViewControls state={state} makerspaceId={makerspaceId} entity={spec.entity} sorts={[]} savedViews={canSaveViews}
      viewOptions={{ eventId: perEvent ? eventId : undefined, presets: presets.data?.results ?? [], linkPrefix: `${list}-` }}
      search={SEARCHABLE.includes(list)} searchLabel={t`Search ${label.toLowerCase()}`}
      controls={<>{shown.map(key => <Field key={key} label={filterLabel(key)}>
        <select className="desk-input min-h-11" value={(state.values as Record<string, string>)[key] ?? ''} onChange={e => state.setFilter(key, e.target.value)}>
          <option value="">{t`Any`}</option>{options(key).map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Field>)}
        <button type="button" className="desk-button min-h-11" disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>{t`Export these rows as CSV`}</button></>} />
    {guests && state.values.list && !state.values.collected ? <p className="text-sm text-muted">{t`Choose whether they collected from this list to filter by it.`}</p> : null}
    <ErrorBlock error={rows.error || exportCsv.error} onRetry={() => void rows.refetch()} />
    {rows.isLoading ? <p role="status">{t`Loading ${label.toLowerCase()}…`}</p> : null}
    {rows.data ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">{label}</caption>
      <thead><tr>{columns.map(column => <th key={column} scope="col">{column.replace(/_/g, ' ')}</th>)}</tr></thead>
      <tbody>{rows.data.results.map((row, index) => <tr key={String(row.id ?? index)}>{columns.map(column =>
        <td key={column}>{column === 'reply' ? optionLabel('reply', String(row[column] || 'not_asked')) : String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div> : null}
    {rows.data && !rows.data.count ? <p className="text-sm text-muted">{t`No rows match these filters.`}</p> : null}
    <Pagination page={state.page} count={rows.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((rows.data?.count ?? 0) / 24)} onChange={state.setPage} />
  </div>;
}
