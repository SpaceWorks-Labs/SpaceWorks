import { useQuery } from '@tanstack/react-query'
import { ListLayout } from '../../../components/layouts'
import { Card } from '../../../components/ui'
import type { EventScope } from '../../events/contributions/types'
import { basePath, errorText, programmeKey, requestFor } from '../../events/contributions/api'

interface Distribution { n: number; average_seconds: number | null; median_seconds: number | null; p90_seconds: number | null }
interface Analytics { completed_checkins: number; open_help: number; first_response: Distribution; help_duration: Distribution; visit_duration: Distribution; expired_leases: number; scope: 'own' | 'event' }
const minutes = (value: number | null) => value === null ? 'No data yet' : `${(value / 60).toFixed(1)} min`

export function MentorAnalytics({ scope }: { scope: EventScope }) {
  const query = useQuery({ queryKey: [...programmeKey(scope, 'admin'), 'mentor-analytics'], retry: false,
    queryFn: () => requestFor('admin')<Analytics>(`${basePath(scope, 'admin')}/mentor-analytics/`) })
  const row = query.data
  return <ListLayout header={{ title: row?.scope === 'own' ? 'Your mentoring' : 'Mentoring overview',
    subtitle: 'Private service diagnostics. Practice rounds are excluded. These figures do not rank mentors or choose winners.' }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    stats={row ? [{ label: 'Completed visits', value: row.completed_checkins }, { label: 'Open requests', value: row.open_help }, { label: 'Expired visit leases', value: row.expired_leases }] : []}
    empty={{ message: 'Mentoring metrics appear after your first visit.' }}
    body={{ kind: 'rows', rows: row ? Object.entries({ 'First response': row.first_response, 'Help duration': row.help_duration, 'Visit duration': row.visit_duration }).map(([label, value]) => <Card key={label}>
      <h2 className="title-section">{label}</h2><dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div><dt className="text-muted">Samples</dt><dd>{value.n}</dd></div><div><dt className="text-muted">Average</dt><dd>{minutes(value.average_seconds)}</dd></div>
        <div><dt className="text-muted">Median</dt><dd>{minutes(value.median_seconds)}</dd></div><div><dt className="text-muted">90th percentile</dt><dd>{minutes(value.p90_seconds)}</dd></div>
      </dl></Card>) : null }} />
}
