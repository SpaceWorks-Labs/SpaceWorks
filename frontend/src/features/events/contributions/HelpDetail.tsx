import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { DetailLayout } from '../../../components/layouts'
import { ActionControl, Card, Field, StatusPill, Pagination } from '../../../components/ui'
import type { EventScope, HelpComment, HelpRequest, Page } from './types'
import { basePath, errorText, programmeKey, requestFor, useProgrammeCommand, useProgrammeDetail, type Surface } from './api'

export function HelpDetail({ scope, helpId, surface = 'member', onClose }: {
  scope: EventScope; helpId: number; surface?: Surface; onClose: () => void
}) {
  const path = `/help/${helpId}/`
  const query = useProgrammeDetail<HelpRequest>(scope, surface, path)
  const [page, setPage] = useState(1)
  const comments = useQuery({ queryKey: [...programmeKey(scope, surface), path, 'comments', page],
    queryFn: () => requestFor(surface)<Page<HelpComment>>(`${basePath(scope, surface)}${path}comments/?page=${page}`),
    enabled: Boolean(query.data), retry: false, gcTime: 0 })
  const [body, setBody] = useState('')
  const [note, setNote] = useState('')
  const command = useProgrammeCommand(scope, surface)
  const row = query.data
  const perform = (action: string) => {
    if (!row) return
    const fields = action === 'resolve' ? { resolution_note: note } : action === 'reopen' ? { reason: note } : {}
    command.mutate({ path: `${path}${action}/`, version: row.version, fields },
      { onSuccess: () => { if (['release', 'resolve'].includes(action) && surface === 'admin') onClose() } })
  }
  return <DetailLayout title={row?.category ?? 'Help request'} back={{ label: 'Back to queue', onClick: onClose }}
    status={row ? <StatusPill label={row.state} tone={row.state === 'resolved' ? 'success' : 'neutral'} /> : undefined}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    main={<div className="grid gap-4"><Card><p className="whitespace-pre-wrap break-words">{row?.summary}</p>
      <p className="mt-3 text-sm text-muted">{row?.team_alias}{row?.zone?.table ? ` · Table ${row.zone.table}` : ''}</p></Card>
      {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {row?.allowed_actions.some(x => ['resolve', 'reopen'].includes(x)) ? <Field label="Resolution or follow-up note">
        <textarea className="desk-input min-h-24" maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></Field> : null}
      <div className="flex flex-wrap gap-2">{['release', 'resolve', 'reopen', 'cancel'].filter(action => row?.allowed_actions.includes(action)).map(action =>
        <ActionControl key={action} action={{ label: action === 'cancel' ? 'Cancel help request' : action.replace(/^./, x => x.toUpperCase()),
          pending: command.isPending, disabled: ['resolve', 'reopen'].includes(action) && !note.trim(),
          disabledReason: ['resolve', 'reopen'].includes(action) && !note.trim() ? 'Add a short note first.' : undefined,
          confirm: action === 'cancel' ? { title: 'Cancel this help request?', message: 'A claimed mentor will be released. Your team stays together.' } : undefined,
          onClick: () => perform(action) }} />)}</div>
      <section aria-label="Comments" className="grid gap-3"><h2 className="title-section">Conversation</h2>
        {comments.isPending ? <p role="status">Loading comments…</p> : null}
        {comments.error ? <p role="alert" className="text-danger">{errorText(comments.error)}</p> : null}
        {comments.data?.results.map(item => <Card key={item.id}><p className="mb-2 text-xs text-muted">{item.origin === 'team' ? 'Team' : 'Mentor'} · {new Date(item.created_at).toLocaleString()}</p><p className="whitespace-pre-wrap break-words">{item.body}</p></Card>)}
        <Pagination page={page} totalPages={Math.ceil((comments.data?.count ?? 0) / 24)} onChange={setPage} />
        {row?.allowed_actions.includes('comment') ? <form className="grid gap-3" onSubmit={event => {
          event.preventDefault()
          command.mutate({ path: `${path}comments/`, version: row.version, fields: { body } }, { onSuccess: () => setBody('') })
        }}><Field label="Add a comment"><textarea className="desk-input min-h-24" maxLength={2000} required value={body} onChange={event => setBody(event.target.value)} /></Field>
          <button className="desk-button min-h-11 justify-self-start" type="submit" disabled={command.isPending}>Send comment</button></form> : null}
      </section></div>} />
}
