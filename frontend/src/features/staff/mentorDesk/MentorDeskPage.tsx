import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from 'react'
import { Tabs } from '../../../components/ui'
import { HelpQueue } from '../../events/contributions/HelpQueue'
import { HelpDetail } from '../../events/contributions/HelpDetail'
import { HelpComposer } from '../../events/contributions/HelpComposer'
import type { EventScope } from '../../events/contributions/types'
import { MentorAnalytics } from './MentorAnalytics'

/** G mounts this inside the existing AppShell and filters tabs by live authority. */
export function MentorDeskPage({ scope, teams, categories, rounds, contributorTools, assignmentTools, importTools, settingsTools, attentionTools }: {
  scope: EventScope; teams: Array<{ id: number; label: string }>; categories: Array<{ key: string; label: string }>
  rounds?: ReactNode; contributorTools?: ReactNode; assignmentTools?: ReactNode; importTools?: ReactNode
  settingsTools?: ReactNode; attentionTools?: ReactNode
}) {
  const [tab, setTab] = useState('help')
  const [helpId, setHelpId] = useState<number | null>(null)
  const tabs = [{ key: 'help', label: t`Help queue` }, { key: 'metrics', label: t`Your metrics` },
    ...(rounds ? [{ key: 'rounds', label: t`Check-in rounds` }] : []),
    ...(contributorTools ? [{ key: 'contributors', label: t`Contributors` }] : []),
    ...(assignmentTools ? [{ key: 'assignments', label: t`Assignments` }] : []),
    ...(settingsTools ? [{ key: 'settings', label: t`Settings and conflicts` }] : []),
    ...(attentionTools ? [{ key: 'attention', label: t`Attention` }] : []),
    ...(importTools ? [{ key: 'import', label: t`Import / practice` }] : [])]
  return <Tabs tabs={tabs} activeKey={tab} onChange={key => { setTab(key); setHelpId(null) }}>
    {tab === 'help' ? helpId ? <HelpDetail scope={scope} helpId={helpId} surface="admin" onClose={() => setHelpId(null)} /> : <>
      <HelpQueue scope={scope} surface="admin" onOpen={row => setHelpId(row.id)} />
      <div className="mt-6"><HelpComposer scope={scope} surface="admin" teams={teams} categories={categories} /></div>
    </> : tab === 'metrics' ? <MentorAnalytics scope={scope} /> : tab === 'rounds' ? rounds
      : tab === 'contributors' ? contributorTools : tab === 'assignments' ? assignmentTools
        : tab === 'settings' ? settingsTools : tab === 'attention' ? attentionTools : importTools}
  </Tabs>
}
