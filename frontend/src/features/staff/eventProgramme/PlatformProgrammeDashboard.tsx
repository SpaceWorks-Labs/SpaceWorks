import { t } from "@lingui/core/macro";
import { useSearchParams } from 'react-router-dom'
import { Tabs } from '../../../components/ui'
import { PlatformDashboardPanel } from '../StaffTabLoaders'
import { PlatformInsightsPage } from '../../platformInsights/PlatformInsightsPage'
import { PlatformOverviewPage } from '../../platformOverview/PlatformOverviewPage'

const VIEWS = ['overview', 'insights'] as const

/** Mounted inside the existing platform-only staff route and AppShell. */
export function PlatformProgrammeDashboard() {
  const [params, setParams] = useSearchParams()
  const requested = params.get('platformView')
  const view = VIEWS.find(key => key === requested) ?? 'operations'
  return <Tabs label={t`Platform dashboard views`} activeKey={view} tabs={[
    { key: 'operations', label: t`Operations` }, { key: 'overview', label: t`Platform overview` },
    { key: 'insights', label: t`Platform insights` },
  ]} onChange={key => setParams(previous => { const next = new URLSearchParams(previous); if (key === 'operations') next.delete('platformView'); else next.set('platformView', key); return next })}>
    {view === 'overview' ? <PlatformOverviewPage /> : view === 'insights' ? <PlatformInsightsPage /> : <PlatformDashboardPanel />}
  </Tabs>
}
