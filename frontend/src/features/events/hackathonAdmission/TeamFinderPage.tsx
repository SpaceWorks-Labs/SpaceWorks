import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListLayout } from '../../../components/layouts'
import { Card, ErrorText } from '../../../components/ui'
import { memberRequest } from '../../../lib/api'
import { AdmissionArtwork } from './AdmissionArtwork'
import { CommandSession } from './transport'
import type { FinderCard, Page, ProgrammeContext } from './types'

type FinderProfile = { id: number | null; version: number; opted_in: boolean; intro: string; skills: string[] }
export function TeamFinderPage({ context, accountId }: { context: ProgrammeContext; accountId: number }) {
  const [page, setPage] = useState(1), [skills, setSkills] = useState('')
  const [intro, setIntro] = useState(''), [profileSkills, setProfileSkills] = useState('')
  const commands = useRef(new CommandSession()), client = useQueryClient()
  const base = context.routes.member_base, key = ['team-finder', accountId, context.event.id] as const
  const cards = useQuery({ queryKey: [...key, page, skills], queryFn: () => memberRequest<Page<FinderCard>>(
    base.slice('/api/v1'.length) + '/team-finder/?page=' + page + '&skills=' + encodeURIComponent(skills)),
    enabled: context.programme.finder_enabled, staleTime: 0, gcTime: 0, retry: false })
  const own = useQuery({ queryKey: [...key, 'me'], queryFn: () => memberRequest<FinderProfile>(base.slice('/api/v1'.length) + '/team-finder/me/'),
    enabled: context.programme.finder_enabled, staleTime: 0, gcTime: 0, retry: false })
  const action = useMutation({ mutationFn: ({ suffix, body, method = 'POST' }: { suffix: string; body: Record<string, unknown>; method?: 'POST' | 'PATCH' }) =>
    commands.current.send(base + suffix, method, body), onSuccess: () => client.invalidateQueries({ queryKey: key }) })
  return <ListLayout header={{ title: 'Find your next teammate' }} state={cards.isLoading ? { status: 'loading' }
    : cards.error ? { status: 'error', error: cards.error.message, onRetry: () => { void cards.refetch() } } : { status: 'ready' }}
    empty={{ message: 'No teams or participants match these skills.' }}
    pagination={{ page, pageSize: 24, count: cards.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>
      {action.error ? <ErrorText message={action.error.message} /> : null}
      {!context.programme.finder_enabled ? <p className="text-sm text-muted">Team finder is not enabled for this event.</p> : <>
        <label className="grid gap-1 text-sm text-ink">Filter skills (separate with commas)<input className="desk-input" maxLength={800} value={skills} onChange={e => { setSkills(e.target.value); setPage(1) }} /></label>
        <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault(); action.mutate({ suffix: '/team-finder/me/', method: 'PATCH',
          body: { expected_version: own.data?.version ?? 0, opted_in: true, intro,
            skills: profileSkills.split(',').map(v => v.trim()).filter(Boolean) } }) }}>
          <h2 className="title-section">Looking for a team?</h2>
          <label className="grid gap-1 text-sm text-ink">Your public introduction<textarea className="desk-input" maxLength={500} value={intro} onChange={e => setIntro(e.target.value)} /></label>
          <label className="grid gap-1 text-sm text-ink">Your chosen skills<input className="desk-input" maxLength={800} value={profileSkills} onChange={e => setProfileSkills(e.target.value)} /></label>
          <p className="text-sm text-muted">Share chosen skills and a short introduction. Only a currently public member profile can be linked.</p>
          <div className="flex flex-wrap gap-2"><button className="desk-button-primary" type="submit" disabled={action.isPending || own.isPending || Boolean(own.error)}>Show my finder card</button>
            {own.data?.opted_in ? <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate({ suffix: '/team-finder/me/', method: 'PATCH',
              body: { expected_version: own.data!.version, opted_in: false } })}>Hide my card now</button> : null}</div>
        </form></Card>
        {!cards.data?.results.length ? <><AdmissionArtwork kind="teams" /><p className="text-sm text-muted">No matching finder cards yet.</p></> : null}
        {cards.data?.results.map(card => <Card key={card.kind + card.id}>
          <div className="grid gap-2"><h2 className="title-section">{card.name || card.profile?.display_name || 'Participant seeking a team'}</h2>
            <p className="whitespace-pre-wrap break-words text-sm text-ink">{card.intro}</p>
            <p className="text-sm text-muted">{card.skills.join(' · ')}{card.slots !== undefined ? ' · ' + card.slots + ' open places' : ''}</p>
            {card.profile?.url ? <a className="min-h-11 py-3 text-sm text-brand underline" href={card.profile.url}>Public profile</a> : null}
            {card.kind === 'team' ? <button className="desk-button justify-self-start" type="button" disabled={action.isPending || card.slots === 0}
              onClick={() => action.mutate({ suffix: '/teams/' + card.id + '/join-request/', body: { expected_version: card.version } })}>Request to join</button> : null}
          </div></Card>)}
      </>}
    </> }} />
}
