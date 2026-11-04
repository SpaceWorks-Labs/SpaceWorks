import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { memberRequest } from '../../../lib/api'
import { ErrorBlock, Field, Pagination } from '../../../components/ui'
import { useProgrammeList } from '../../events/contributions/api'
import type { Aggregate, EventScope, RoleApplication } from '../../events/contributions/types'
import { MentorDeskPage } from '../mentorDesk/MentorDeskPage'
import { MentorAssignmentsPanel } from '../mentorDesk/MentorAssignmentsPanel'
import { MentorRoundSetup } from '../mentorDesk/MentorRoundSetup'
import { MentorRoundsPanel } from '../mentorDesk/MentorRoundsPanel'
import { MentorSettingsPanel, HelpCategoryEditor } from '../mentorDesk/MentorSettingsPanel'
import { MentorConflictForm } from '../mentorDesk/MentorConflictForm'
import { MentorAttentionPanel } from '../mentorDesk/MentorAttentionPanel'
import { MentorAlertRooms } from '../mentorDesk/MentorAlertRooms'
import { TeamImportPanel } from '../mentorDesk/TeamImportPanel'
import { VolunteerManager } from '../mentorDesk/VolunteerManager'
import { ContributorSetupPanel } from '../mentorDesk/ContributorSetupPanel'
import { RoleLifecycleActions } from '../mentorDesk/RoleLifecycleActions'
import { renderContributorBuilder, RoundAnswerFields } from './ProgrammeDraftForm'
import { sessionScope } from './sessionScope'
import { useProgrammeQuery, type Readiness } from './api'

type Round = Aggregate & { label: string }
type Mapping = Aggregate & { team_id: number; mentor_assignment_id: number }
type HelpType = Aggregate & { key: string; label: string; skill_tags: string[]; priority: number; open_limit: number;
  claim_minutes: number; expiry_minutes: number; organizer_contact_action: string }
export function MentorWorkspace({ scope, manager, roundsEnabled, ownAssignmentId }: {
  scope: EventScope; manager: boolean; roundsEnabled: boolean; ownAssignmentId?: number
}) {
  const [page, setPage] = useState(1), [mentorId, setMentorId] = useState(ownAssignmentId ?? 0), [roundId, setRoundId] = useState(0)
  const roles = useProgrammeList<RoleApplication>(scope, 'admin', '/roles/', page, false, manager)
  const assignments = useProgrammeList<Mapping>(scope, 'admin', '/mentor-assignments/', page, false, manager)
  const rounds = useProgrammeList<Round>(scope, 'admin', '/mentor-rounds/', page, true, roundsEnabled)
  const categories = useProgrammeList<HelpType>(scope, 'admin', '/help-types/', page, false, manager)
  const availableTeams = useProgrammeList<Aggregate & { name: string }>(scope, 'admin', '/teams/', page, false, manager)
  const memberCategories = useQuery({ queryKey: ['member', scope.accountId, 'help-topics', scope.eventId, ...sessionScope()], enabled: !manager, gcTime: 0, retry: false,
    queryFn: () => memberRequest<{ results: { key: string; label: string }[] }>(`/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/help-topics/`) })
  const readiness = useProgrammeQuery<Readiness>(scope.eventId, 'readiness')
  const teams = manager ? (availableTeams.data?.results ?? []).map(row => ({ id: row.id, label: row.name })) : [...new Set(assignments.data?.results.map(row => row.team_id) ?? [])].map(id => ({ id, label: `Team ${id}` }))
  const mentors = (roles.data?.results ?? []).filter(row => row.role === 'mentor' && row.state === 'approved').map(row => ({ id: row.id, label: `Mentor ${row.id}` }))
  const error = roles.error || assignments.error || categories.error || rounds.error || availableTeams.error || memberCategories.error
  return <div className="grid gap-5">
    {error ? <ErrorBlock error={error} onRetry={() => { if (manager) { void roles.refetch(); void assignments.refetch() }; void categories.refetch(); if (roundsEnabled) void rounds.refetch() }} /> : null}
    <MentorDeskPage scope={scope} teams={teams} categories={categories.data?.results ?? memberCategories.data?.results ?? []}
      rounds={roundsEnabled ? <div className="grid gap-5">
        {manager ? <MentorRoundSetup scope={scope} renderFormBuilder={renderContributorBuilder} /> : null}
        <Field label="Mentor check-in round"><select className="desk-input" value={roundId} onChange={event => setRoundId(Number(event.target.value))}>
          <option value={0}>Choose a round</option>{rounds.data?.results.map(row => <option value={row.id} key={row.id}>{row.label}</option>)}</select></Field>
        {roundId ? <MentorRoundsPanel key={roundId} scope={scope} roundId={roundId} sessionId={JSON.stringify(sessionScope())}
          renderForm={props => <RoundAnswerFields {...props} />} /> : null}
      </div> : undefined}
      assignmentTools={manager && readiness.data ? <MentorAssignmentsPanel scope={scope} eventVersion={readiness.data.version} teams={teams} mentors={mentors} completionReady /> : undefined}
      contributorTools={manager ? <VolunteerManager scope={scope} setupTools={<ContributorSetupPanel scope={scope} renderFormBuilder={renderContributorBuilder} />}
        renderRoleTools={row => <RoleLifecycleActions scope={scope} row={row} />} /> : undefined}
      settingsTools={<div className="grid gap-5">{manager ? <Field label="Mentor profile to configure"><select className="desk-input" value={mentorId} onChange={event => setMentorId(Number(event.target.value))}>
        <option value={0}>Choose a mentor</option>{mentors.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></Field> : null}
        {mentorId ? <><MentorSettingsPanel key={mentorId} scope={scope} assignmentId={mentorId} /><MentorConflictForm key={`conflict-${mentorId}`} scope={scope} assignmentId={mentorId} /></> : null}
        {manager ? <MentorAlertRooms scope={scope} /> : null}
        {manager ? <><HelpCategoryEditor scope={scope} />{categories.data?.results.map(row => <HelpCategoryEditor key={row.id} scope={scope} initial={row} />)}</> : null}
      </div>}
      attentionTools={roundsEnabled ? <MentorAttentionPanel scope={scope} /> : undefined}
      importTools={manager ? <TeamImportPanel scope={scope} /> : undefined} />
    <Pagination page={page} count={Math.max(availableTeams.data?.count ?? 0, roles.data?.count ?? 0, assignments.data?.count ?? 0, rounds.data?.count ?? 0, categories.data?.count ?? 0)}
      pageSize={24} totalPages={Math.ceil(Math.max(availableTeams.data?.count ?? 0, roles.data?.count ?? 0, assignments.data?.count ?? 0, rounds.data?.count ?? 0, categories.data?.count ?? 0) / 24)} onChange={setPage} />
  </div>
}
