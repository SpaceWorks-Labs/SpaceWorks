import { formatLocale } from "../../../lib/format";
import { sentenceCase } from '../../../lib/sentenceCase';
import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BellOff } from 'lucide-react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card, Field } from '../../../components/ui'
import type { EventScope } from '../../events/contributions/types'
import { basePath, programmeKey, requestFor, errorText, useProgrammeCommand } from '../../events/contributions/api'

const nudgeText = (reason: string, minutes: number) => reason === 'long_visit' ? t`Long visit · ${minutes} minutes`
  : reason === 'quiet' ? t`Quiet · ${minutes} minutes since the last check-in`
  : reason === 'check_in_due' ? t`Check-in due · ${minutes} minutes since the last check-in`
  : t`${sentenceCase(reason)} · ${minutes} minutes`

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
  return <ListLayout header={{ title: t`Mentor attention`, subtitle: t`Private follow-up signals. Practice data is excluded.` }}
    empty={{ message: t`No attention signals yet.` }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    body={{ kind: 'rows', rows: row ? <>
      <Card><h2 className="title-section flex items-center gap-2"><BellOff size={20} aria-hidden />{t`Nudge preferences`}</h2>
        <Field label={t`Mute nudges`}><select className="desk-input min-h-11" value={minutes} onChange={event => setMinutes(event.target.value)}><option value="0">{t`Resume now`}</option><option value="10">{t`10 minutes`}</option><option value="30">{t`30 minutes`}</option><option value="60">{t`60 minutes`}</option><option value="120">{t`2 hours`}</option></select></Field>
        <div className="mt-3"><ActionControl action={{ label: t`Save nudge preference`, pending: command.isPending,
          onClick: () => command.mutate({ path: '/mentor-attention/mute/', version: row.attention_preference.version, fields: { minutes: Number(minutes) } }) }} /></div>
        {command.error ? <p role="alert" className="mt-2 text-danger">{errorText(command.error)}</p> : null}
        <p className="mt-2 text-sm text-muted">{row.attention_preference.muted_until ? t`Muted until ${new Date(row.attention_preference.muted_until).toLocaleTimeString(formatLocale())}` : t`Nudges are enabled.`}</p>
      </Card>
      {row.per_round.map(round => <Card key={round.round_id}><h2 className="title-section">{t`Round ${round.round_id}`}</h2><p>{t`${round.completed} visits complete`}{round.remaining === null ? '' : t` · ${round.remaining} teams still need a visit`}</p></Card>)}
      {row.attention.map(item => <Card key={`${item.team_id}:${item.reason}`}><h2 className="title-section">{t`Team ${item.team_id} needs a follow-up`}</h2><p>{t`${item.count} away visits`}</p></Card>)}
      {row.nudges.map(item => <Card key={`${item.mentor_assignment_id}:${item.reason}`}><h2 className="title-section">{t`Mentor ${item.mentor_assignment_id}`}</h2><p>{nudgeText(item.reason, item.minutes)}</p></Card>)}
      {row.scope === 'event' ? <Card><h2 className="title-section">{t`Private generosity diagnostic`}</h2><p className="my-3 text-sm text-muted">{t`Small samples and constant scores have no z score. These figures do not select winners or rank productivity.`}</p>
        <div className="overflow-auto"><table className="w-full text-left text-sm"><caption className="sr-only">{t`Mentor rating sample diagnostics`}</caption><thead><tr><th scope="col">{t`Mentor`}</th><th scope="col">{t`Samples`}</th><th scope="col">{t`Mean`}</th><th scope="col">{t`Z score`}</th></tr></thead><tbody>
          {row.generosity.map(item => <tr key={item.mentor_assignment_id}><th scope="row">{item.mentor_assignment_id}</th><td>{item.n}</td><td>{item.mean ?? t`No data`}</td><td>{item.z_score ?? t`Not enough variation`}</td></tr>)}
        </tbody></table></div></Card> : null}
    </> : null }} />
}
