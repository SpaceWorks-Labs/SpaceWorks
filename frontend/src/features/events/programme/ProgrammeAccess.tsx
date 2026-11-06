import { t } from "@lingui/core/macro";
import { BrandLoader } from '../../../components/delight'
import { ProgrammeMakerToggle } from './ProgrammeDelight'
import { useEffect, useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { AppShell } from '../../../components/shell'
import { CenteredCardLayout } from '../../../components/layouts'
import { CalendarDays, UserRound } from 'lucide-react'
import { getAccessToken, logout, memberRequest, StructuredApiError } from '../../../lib/api'
import { onSessionCleared } from '../../../lib/api/sessionContext'
import { browserSessionIdentity } from '../../../lib/api/reauthentication'
import type { AuthUserPayload as User } from '../../../generated/api'
import { MemberAuthPanel } from '../../members/MemberAuthPanel'
import { clearUploadSessions } from '../hackathonSubmissions/upload'

/** Personal programme pages never depend on a membership list. */
export function ProgrammeAccess({ slug = '', children }: { slug?: string; children: (user: User) => ReactNode }) {
  const [generation, setGeneration] = useState(0)
  useEffect(() => onSessionCleared(context => {
    if (context === 'person') { clearUploadSessions(); setGeneration(value => value + 1) }
  }), [])
  const identity = `${generation}:${browserSessionIdentity(getAccessToken('person'))}`
  return <PrivateSession key={`${slug}:${identity}`} slug={slug} onAuthenticated={() => setGeneration(value => value + 1)}>{children}</PrivateSession>
}
function PrivateSession({ slug, children, onAuthenticated }: { slug: string; children: (user: User) => ReactNode; onAuthenticated: () => void }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } } }))
  useEffect(() => () => { void client.cancelQueries(); client.clear(); clearUploadSessions() }, [client])
  return <QueryClientProvider client={client}><AccountScreen slug={slug} onAuthenticated={onAuthenticated}>{children}</AccountScreen></QueryClientProvider>
}
function AccountScreen({ slug, children, onAuthenticated }: { slug: string; children: (user: User) => ReactNode; onAuthenticated: () => void }) {
  const account = useQuery({ queryKey: ['programme-account', window.location.host], queryFn: () => memberRequest<User>('/auth/me') })
  const denied = (account.error instanceof StructuredApiError && account.error.status === 401) || Boolean(account.data && account.data.kind !== 'person')
  const home = slug ? `/m/${encodeURIComponent(slug)}` : ''
  return <AppShell variant="member" compactNav="drawer" activeKey="programme" nav={[{ key: 'events', items: [
    { key: 'programme', label: t`Events`, href: `${home}/events`, icon: CalendarDays },
    { key: 'saved-details', label: t`Saved details`, href: `${home}/member/account/saved-details`, icon: UserRound },
  ] }]} user={{ menu: [{ label: t`Account`, href: `${home}/member/account` }], name: account.data?.display_name || account.data?.username || 'Your account',
    onSignOut: () => { void logout().finally(onAuthenticated) } }}>
    <div className="mb-4 flex justify-end"><ProgrammeMakerToggle /></div>
    {denied ? <MemberAuthPanel makerspaceSlug={slug} onAuthenticated={onAuthenticated} /> : account.isPending
      ? <BrandLoader label={t`Opening your event programme`} />
      : account.error || !account.data ? <CenteredCardLayout standalone={false} title={t`Account unavailable`} body={account.error?.message || 'Sign in to continue.'}
        state={{ status: 'ready' }} primary={{ label: t`Try again`, onClick: () => void account.refetch() }} />
        : children(account.data)}
  </AppShell>
}
