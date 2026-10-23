import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BellOff } from 'lucide-react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card, Field } from '../../../components/ui'
import type { EventScope } from '../../events/contributions/types'
import { basePath, programmeKey, requestFor, errorText, useProgrammeCommand } from '../../events/contributions/api'

interface Attention {
  scope: 'own' | 'event'; per_round: Array<{ round_id: number; completed: number; remaining: number | null }>
  attention: Array<{ team_id: number; reason: string; count: number }>
  nudges: Array<{ mentor_assignment_id: number; reason: string; minutes: number }>
  generosity: Array<{ mentor_assignment_id: number; n: number; mean: number | null; z_score: number | null }>
  attention_preference: { version: number; muted_until: string | null }
}
export function MentorAttentionPanel({ scope }: { scope: EventScope }) {
  const query = useQuery({ queryKey: [...programmeKey(scope, 'admin'), 'mentor-analytics'], retry: false, gcTime: 0,
    queryFn: () => requestFor('admin')<Attention>(`${basePath(scope, 'admin')}/mentor-analytics/`) })
  const [minutes, setMinutes] = useState('30')
  const command = useProgrammeCommand(scope, 'admin')
  const row = query.data
  return <ListLayout header={{ title: 'Mentor attention', subtitle: 'Private follow-up signals. Practice data is excluded.' }}
    empty={{ message: 'No attention signals yet.' }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    body={{ kind: 'rows', rows: row ? <>
      <Card><h2 className="title-section flex items-center gap-2"><BellOff size={20} aria-hidden />Nudge preferences</h2>
        <Field label="Mute nudges"><select className="desk-input min-h-11" value={minutes} onChange={event => setMinutes(event.target.value)}><option value="0">Resume now</option><option value="10">10 minutes</option><option value="30">30 minutes</option><option value="60">60 minutes</option><option value="120">2 hours</option></select></Field>
        <div className="mt-3"><ActionControl action={{ label: 'Save nudge preference', pending: command.isPending,
          onClick: () => command.mutate({ path: '/mentor-attention/mute/', version: row.attention_preference.version, fields: { minutes: Number(minutes) } }) }} /></div>
        {command.error ? <p role="alert" className="mt-2 text-danger">{errorText(command.error)}</p> : null}
        <p className="mt-2 text-sm text-muted">{row.attention_preference.muted_until ? `Muted until ${new Date(row.attention_preference.muted_until).toLocaleTimeString()}` : 'Nudges are enabled.'}</p>
      </Card>
      {row.per_round.map(round => <Card key={round.round_id}><h2 className="title-section">Round {round.round_id}</h2><p>{round.completed} visits complete{round.remaining === null ? '' : ` · ${round.remaining} teams still need a visit`}</p></Card>)}
      {row.attention.map(item => <Card key={`${item.team_id}:${item.reason}`}><h2 className="title-section">Team {item.team_id} needs a follow-up</h2><p>{item.count} away visits</p></Card>)}
      {row.nudges.map(item => <Card key={`${item.mentor_assignment_id}:${item.reason}`}><h2 className="title-section">Mentor {item.mentor_assignment_id}</h2><p>{item.reason.replace(/_/g, ' ')} · {item.minutes} minutes</p></Card>)}
      {row.scope === 'event' ? <Card><h2 className="title-section">Private generosity diagnostic</h2><p className="my-3 text-sm text-muted">Small samples and constant scores have no z score. These figures do not select winners or rank productivity.</p>
        <div className="overflow-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Mentor rating sample diagnostics</caption><thead><tr><th scope="col">Mentor</th><th scope="col">Samples</th><th scope="col">Mean</th><th scope="col">Z score</th></tr></thead><tbody>
          {row.generosity.map(item => <tr key={item.mentor_assignment_id}><th scope="row">{item.mentor_assignment_id}</th><td>{item.n}</td><td>{item.mean ?? 'No data'}</td><td>{item.z_score ?? 'Not enough variation'}</td></tr>)}
        </tbody></table></div></Card> : null}
    </> : null }} />
}
