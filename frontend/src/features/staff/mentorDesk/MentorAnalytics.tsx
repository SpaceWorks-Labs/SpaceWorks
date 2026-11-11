import { t } from "@lingui/core/macro";
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
  return <ListLayout header={{ title: row?.scope === 'own' ? t`Your mentoring` : t`Mentoring overview`,
    subtitle: t`Private service diagnostics. Practice rounds are excluded. These figures do not rank mentors or choose winners.` }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    stats={row ? [{ label: t`Completed visits`, value: row.completed_checkins }, { label: t`Open requests`, value: row.open_help }, { label: t`Expired visit leases`, value: row.expired_leases }] : []}
    empty={{ message: t`Mentoring metrics appear after your first visit.` }}
    body={{ kind: 'rows', rows: row ? ([[t`First response`, row.first_response], [t`Help duration`, row.help_duration], [t`Visit duration`, row.visit_duration]] as const).map(([label, value]) => <Card key={label}>
      <h2 className="title-section">{label}</h2><dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div><dt className="text-muted">{t`Samples`}</dt><dd>{value.n}</dd></div><div><dt className="text-muted">{t`Average`}</dt><dd>{minutes(value.average_seconds)}</dd></div>
        <div><dt className="text-muted">{t`Median`}</dt><dd>{minutes(value.median_seconds)}</dd></div><div><dt className="text-muted">{t`90th percentile`}</dt><dd>{minutes(value.p90_seconds)}</dd></div>
      </dl></Card>) : null }} />
}
