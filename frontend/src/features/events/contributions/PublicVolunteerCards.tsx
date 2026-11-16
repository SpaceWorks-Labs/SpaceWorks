import { t } from "@lingui/core/macro";
import { useQuery } from '@tanstack/react-query'
import { publicV1Request } from '../../../lib/api'
import { ActionControl, Card } from '../../../components/ui'
import { errorText } from './api'
import { parsePage, type Page, type Posting } from './types'
import { LogoLoader } from '../../../components/LogoLoader'

export function PublicVolunteerCards({ publicToken, onApply }: { publicToken: string; onApply: (id: number) => void }) {
  const query = useQuery({ queryKey: ['public-event-volunteers', publicToken], retry: false,
    queryFn: async () => parsePage(await publicV1Request<Page<Posting>>(`/public/event-programmes/${publicToken}/volunteer-postings/`)) })
  return <section aria-label={t`Volunteers needed`} className="grid gap-3">
    <h2 className="title-section">{t`Volunteers needed`}</h2>
    {query.isPending ? <LogoLoader label={t`Loading opportunities…`} size={48} className="min-h-16 py-3" /> : null}
    {query.error ? <p role="alert" className="text-danger">{errorText(query.error)}</p> : null}
    {query.data?.results.length === 0 ? <p className="text-sm text-muted">{t`No public volunteer postings right now.`}</p> : null}
    {query.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3"><div>
      <h3 className="title-section">{row.title}</h3><p className="mt-1 text-sm text-muted">{row.description}</p></div>
      <ActionControl action={{ label: t`View role`, onClick: () => onApply(row.id) }} /></div></Card>)}
    {query.data?.next ? <p className="text-sm text-muted">{t`Sign in to browse all volunteer postings.`}</p> : null}
  </section>
}
