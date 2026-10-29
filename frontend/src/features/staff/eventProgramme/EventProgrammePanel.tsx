import { IssueRoleCertificate } from '../eventCredentials/IssueRoleCertificate'
import { useQuery } from '@tanstack/react-query'
import { staffRequest } from '../../../lib/api'
import type { AuthUserPayload } from '../../../generated/api'
import { currentSessionContext } from '../../../lib/api/sessionContext'
import type { StaffEvent } from '../eventsApi'
import type { MoreSection } from '../eventDrawerTabs'
import type { eventAccess } from '../eventStaffPermissions'
import { ErrorBlock } from '../../../components/ui'
import { HackathonConfigPanel } from '../hackathonAdmission/HackathonConfigPanel'
import { VolunteerManager } from '../mentorDesk/VolunteerManager'
import { ContributorSetupPanel } from '../mentorDesk/ContributorSetupPanel'
import { RoleLifecycleActions } from '../mentorDesk/RoleLifecycleActions'
import { JudgingWorkspace } from './JudgingWorkspace'
import { MentorWorkspace } from './MentorWorkspace'
import { AdmissionWorkspace } from './AdmissionWorkspace'
import { ProgrammeDraftForm, renderContributorBuilder } from './ProgrammeDraftForm'
import { ProgrammeFormEditor } from './ProgrammeFormEditor'
import { EventPublishingPanel } from './EventPublishingPanel'
import { EventCertificateDesigner } from '../EventCertificateDesigner'
import { BulkCertificates } from '../eventCredentials/BulkCertificates'
import { DeskBadgePanel } from '../eventCredentials/DeskBadgePanel'
import { ProgrammeTeamsPanel } from './ProgrammeTeamsPanel'
import { sessionScope } from './sessionScope'

export function EventProgrammePanel({ event, makerspaceId, section, access, features }: {
  event: StaffEvent; makerspaceId: number; section: MoreSection; access: ReturnType<typeof eventAccess>; features: readonly string[]
}) {
  const programmeSection = ['programme-setup', 'applications', 'volunteers', 'mentor-desk', 'judging', 'programme-teams', 'certificates', 'settings'].includes(section)
  const account = useQuery({ queryKey: ['event-programme-actor', ...sessionScope()], queryFn: () => staffRequest<AuthUserPayload>('/auth/me'), gcTime: 0, retry: false, enabled: programmeSection })
  if (!programmeSection) return null
  if (account.error) return <ErrorBlock error={account.error} />
  if (!account.data) return <p role="status">Loading your programme access…</p>
  const scope = { makerspaceId, eventId: event.id, accountId: account.data.id }
  if (section === 'programme-setup') return <div className="grid gap-8"><HackathonConfigPanel eventId={event.id} FormEditor={ProgrammeDraftForm} mlhPresets={[]} />
    <ProgrammeFormEditor eventId={event.id} formKey="application" /></div>
  if (section === 'applications') return <AdmissionWorkspace event={event} canManage={access.hackathon} />
  if (section === 'volunteers') return <VolunteerManager scope={scope}
    setupTools={<ContributorSetupPanel scope={scope} renderFormBuilder={renderContributorBuilder} />}
    renderRoleTools={row => <><RoleLifecycleActions scope={scope} row={row} />{access.manager ? <IssueRoleCertificate eventId={event.id} role={row} /> : null}</>} />
  if (section === 'mentor-desk') return <MentorWorkspace scope={scope} manager={access.hackathon || access.manager} roundsEnabled={features.includes('events.mentor_rounds')} />
  if (section === 'judging') return <JudgingWorkspace scope={{ ...scope, actorId: account.data.id, context: currentSessionContext() }} manager={access.hackathon}
    judge={access.judge} sponsor={access.sponsor} timezone={event.timezone_name} galleryEnabled={features.includes('events.project_gallery')}
    pairwiseEnabled={features.includes('events.pairwise_judging')} />
  if (section === 'programme-teams') return <ProgrammeTeamsPanel eventId={event.id} canTriage={access.hackathon} />
  if (section === 'certificates') return <div className="grid gap-6">
    {access.edit ? <EventCertificateDesigner makerspaceId={makerspaceId} eventId={event.id} /> : access.manager ? <BulkCertificates eventId={event.id} /> : null}
    <DeskBadgePanel eventId={event.id} registrationIds={[]} canEdit={access.edit} canPrint={access.checkIn} />
  </div>
  if (section === 'settings') return <div className="grid gap-6">
    {access.edit ? <ProgrammeFormEditor eventId={event.id} formKey="registration" /> : null}
    {access.publish ? <EventPublishingPanel eventId={event.id} /> : null}
  </div>
  return null
}
