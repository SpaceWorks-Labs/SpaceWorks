import { useSearchParams } from 'react-router-dom'
import { Tabs } from '../../../components/ui'
import { PlatformDashboardPanel } from '../StaffTabLoaders'
import { PlatformInsightsPage } from '../../platformInsights/PlatformInsightsPage'

/** Mounted inside the existing platform-only staff route and AppShell. */
export function PlatformProgrammeDashboard() {
  const [params, setParams] = useSearchParams()
  const insights = params.get('platformView') === 'insights'
  return <Tabs label="Platform dashboard views" activeKey={insights ? 'insights' : 'operations'} tabs={[
    { key: 'operations', label: 'Operations' }, { key: 'insights', label: 'Platform insights' },
  ]} onChange={key => setParams(previous => { const next = new URLSearchParams(previous); if (key === 'insights') next.set('platformView', key); else next.delete('platformView'); return next })}>
    {insights ? <PlatformInsightsPage /> : <PlatformDashboardPanel />}
  </Tabs>
}
