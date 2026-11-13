import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Page, Team } from './types'
import { PagePager } from "../../../components/ui";

type Comment = { id: number; body: string; created_at: string }
export function TeamComments({ base, team, pending, onSend }: { base: string; team: Team; pending: boolean
  onSend: (body: string, onDone: () => void) => void }) {
  const [body, setBody] = useState(''), [page, setPage] = useState(1)
  const comments = useQuery({ queryKey: ['team-comments', base, team.id, team.version, page],
    queryFn: async () => {
      const { memberRequest } = await import('../../../lib/api')
      return memberRequest<Page<Comment>>(base.slice('/api/v1'.length) + '/teams/' + team.id + '/comments/?page=' + page)
    }, staleTime: 0, gcTime: 0, retry: false })
  return <section className="grid gap-3" aria-label={t`Team conversation`}><h2 className="title-section">{t`Team conversation`}</h2>
    {comments.error ? <p className="text-sm text-danger" role="alert">{t`Could not load comments.`}</p> : null}
    <ol className="grid gap-3">{comments.data?.results.map(comment => <li key={comment.id} className="rounded-xl border border-line bg-panel p-3">
      <p className="whitespace-pre-wrap break-words text-sm text-ink">{comment.body}</p><time className="text-xs text-muted" dateTime={comment.created_at}>{new Date(comment.created_at).toLocaleString(formatLocale())}</time></li>)}</ol>
    <PagePager page={page} setPage={setPage} next={comments.data?.next} />
    <form className="grid gap-2" onSubmit={event => { event.preventDefault(); onSend(body, () => setBody('')) }}>
      <label className="grid gap-1 text-sm text-ink">{t`Message your team`}<textarea required className="desk-input" maxLength={2000} value={body} onChange={e => setBody(e.target.value)} /></label>
      <button className="desk-button justify-self-start" type="submit" disabled={pending || !body.trim()}>{t`Post comment`}</button>
    </form><p className="text-xs text-muted">{t`Only current team members can read this conversation.`}</p>
  </section>
}
