import { useState } from 'react'
import { Tabs, Field } from '../../../components/ui'
import { JudgingPanel } from '../hackathonJudging/JudgingPanel'
import { JudgeConsole } from '../hackathonJudging/JudgeConsole'
import { SponsorConsole } from '../hackathonJudging/SponsorConsole'
import type { Scope } from '../hackathonJudging/types'
import { StaffProjectFiles, downloadProgrammeFile } from './StaffProjectFiles'

export function JudgingWorkspace({ scope, manager, judge, sponsor, timezone, galleryEnabled, sponsorIds = [] }: {
  scope: Scope; manager: boolean; judge: boolean; sponsor: boolean; timezone: string; galleryEnabled: boolean; sponsorIds?: number[]
}) {
  const [tab, setTab] = useState(manager ? 'manage' : judge ? 'judge' : 'sponsor')
  const [sponsorId, setSponsorId] = useState(sponsorIds[0] ?? 0)
  return <Tabs label="Judging tools" activeKey={tab} onChange={setTab} tabs={[
    ...(manager ? [{ key: 'manage', label: 'Rounds and results' }] : []), ...(judge ? [{ key: 'judge', label: 'My judging assignments' }] : []),
    ...(sponsor ? [{ key: 'sponsor', label: 'Sponsor projects' }] : []),
  ]}>
    {tab === 'manage' && manager ? <JudgingPanel scope={scope} timezone={timezone} fullManager galleryEnabled={galleryEnabled} /> : null}
    {tab === 'judge' && judge ? <JudgeConsole scope={scope} renderAssets={ids => <StaffProjectFiles scope={scope} assetIds={ids} purpose="judge" />} /> : null}
    {tab === 'sponsor' && sponsor ? <div className="grid gap-5"><Field label="Assigned sponsor"><select className="desk-input" value={sponsorId} onChange={event => setSponsorId(Number(event.target.value))}>
      <option value={0}>Choose an assigned sponsor</option>{sponsorIds.map(id => <option value={id} key={id}>Sponsor {id}</option>)}</select></Field>
      {sponsorId ? <SponsorConsole scope={scope} sponsorId={sponsorId} sponsorName="Your sponsor track"
        renderProjectFiles={(snapshotId, ids) => <StaffProjectFiles scope={scope} assetIds={ids} purpose="sponsor" snapshotId={snapshotId} />}
        downloadResume={id => downloadProgrammeFile(`/admin/events/${scope.eventId}/sponsors/${sponsorId}/resumes/${id}/`, 'consented-resume.pdf')} />
        : <p className="text-sm text-muted">Your assigned sponsor references appear here when the organizer shares your event role.</p>}
    </div> : null}
  </Tabs>
}
