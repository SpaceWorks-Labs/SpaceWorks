import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { ContributorDesk, ContributorShifts } from './ContributorDesk'
import { OrdinaryProgrammeRegistration } from './OrdinaryProgrammeRegistration'
import { Route, Routes, Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Tabs, ErrorBlock } from '../../../components/ui'
import { ProgrammeAccess } from './ProgrammeAccess'
import { ProgrammeFields } from './formBridge'
import { programmeHref, programmeRoutes } from './routeNames'
import { HackathonApplicationPage } from '../hackathonAdmission/HackathonApplicationPage'
import { TeamPage } from '../hackathonAdmission/TeamPage'
import { TeamFinderPage } from '../hackathonAdmission/TeamFinderPage'
import { useAdmission } from '../hackathonAdmission/useAdmission'
import type { ProgrammeContext } from '../contracts/types'
import { ContributionsPage } from '../contributions/ContributionsPage'
import type { EventScope } from '../contributions/types'
import { ProgrammeRolePage } from './ProgrammeRolePage'
import { TeamJourney } from './TeamJourney'
import { DropInJourney } from './DropInJourney'
import { PhotoChoice } from '../eventPresentation/PhotoChoice'
import { EventResumePanel } from './EventResumePanel'
import { TakeTeamInvitation } from './TakeTeamInvitation'
import { useTenant } from '../../../lib/tenant'

export function EventProgrammePage() {
  const { publicToken = '', slug } = useParams()
  const tenant = useTenant()
  return <ProgrammeAccess slug={slug ?? tenant.slug}>{user => <MemberContent publicToken={publicToken} accountId={user.id} />}</ProgrammeAccess>
}
function MemberContent({ publicToken, accountId }: { publicToken: string; accountId: number }) {
  const location = useLocation(), navigate = useNavigate()
  const { context, application } = useAdmission(publicToken, accountId)
  if (context.error) return <ErrorBlock error={context.error} onRetry={() => void context.refetch()} />
  if (!context.data) return <LogoLoader label={t`Loading the current event requirements…`} />
  const current = context.data
  const base = programmeHref(publicToken, '', current.makerspace.slug).replace(/\/$/, '')
  const scope = { accountId, eventId: current.event.id, makerspaceId: current.makerspace.id }
  const choices = availableJourneys(current)
  const active = location.pathname.split('/programme/')[1]?.split('/')[0] || 'application'
  if (!current.eligibility.eligible) return <p role="status">{t`This account does not currently meet the event admission requirements.`}</p>
  return <div className="grid gap-6">
    <Tabs label={t`Event programme`} tabs={choices.map(row => ({ key: row.suffix, label: row.label, href: `${base}/${row.suffix}` })).concat([
        { key: 'history', label: t`Tickets and certificates`, href: `/m/${current.makerspace.slug}/member/events/history` },
        ...(application?.data?.registration_id ? [{ key: 'ticket', label: t`Event ticket`, href: `/m/${current.makerspace.slug}/member/events/${application.data.registration_id}/ticket` }] : []),
      ])}
      activeKey={active} />
    <Routes>
      <Route index element={<Navigate to="application" replace />} />
      <Route path="application" element={current.programme.kind === 'ordinary' ? <OrdinaryProgrammeRegistration context={current} accountId={accountId} /> : <HackathonApplicationPage publicToken={publicToken} accountId={accountId} Fields={ProgrammeFields}
        onSignIn={() => navigate(`${base}/application`)} onOrdinaryRegister={() => navigate(`/m/${current.makerspace.slug}/events/${publicToken}`)} />} />
      {current.programme.kind === 'hackathon' && current.programme.capabilities['events.hackathons'] ? <>
        <Route path="team" element={<TeamPage context={current} accountId={accountId} inviteUrl={(teamId, token, version) =>
          `${window.location.origin}${base}/invitation/${teamId}?version=${version}#token=${token}`} />} />
        <Route path="invitation/:teamId" element={<TakeTeamInvitation context={current} base={base} />} />
        {current.programme.finder_enabled ? <Route path="finder" element={<TeamFinderPage context={current} accountId={accountId} />} /> : null}
        {['project', 'help', 'office-hours', 'sharing'].map(section => <Route key={section} path={`${section}/*`}
          element={<TeamJourney context={current} scope={scope} section={section} base={base} />} />)}
      </> : null}
      {current.programme.kind !== 'hackathon' && current.programme.capabilities['events.mentoring'] ? ['help', 'office-hours'].map(section =>
        <Route key={section} path={`${section}/*`} element={<DropInJourney scope={scope} section={section} />} />) : null}
      {current.routes.role_postings ? <>
        <Route path="contribute" element={<ContributionsPage scope={scope} onApply={posting => navigate(`${base}/roles/${posting.id}`)}
          onOpenApplication={application => navigate(`${base}/role-applications/${application.id}`)}
          onDesk={row => navigate(row.role === 'mentor' ? `${base}/mentor-desk/${row.id}` : row.role === 'judge' ? `${base}/judge/${row.id}` : `${base}/sponsor-role/${row.id}`)} />} />
        <Route path="roles/:postingId" element={<RoleRoute scope={scope} context={current} base={base} />} />
        <Route path="role-applications/:applicationId" element={<RoleRoute scope={scope} context={current} base={base} />} />
      </> : null}
      {current.programme.capabilities['events.mentoring'] ? <Route path="mentor-desk/:assignmentId" element={<ContributorDesk scope={scope} context={current} kind="mentor" />} /> : null}
      <Route path="judge/:assignmentId" element={<ContributorDesk scope={scope} context={current} kind="judge" />} />
      <Route path="sponsor-role/:assignmentId" element={<ContributorDesk scope={scope} context={current} kind="sponsor_rep" />} />
      <Route path="judge" element={<ContributorDesk scope={scope} context={current} kind="judge" />} />
      <Route path="sponsor" element={<ContributorDesk scope={scope} context={current} kind="sponsor_rep" />} />
      <Route path="sponsor/:sponsorId" element={<ContributorDesk scope={scope} context={current} kind="sponsor_rep" />} />
      {current.programme.capabilities['events.volunteering'] ? <Route path="shifts" element={<ContributorShifts scope={scope} />} /> : null}
      <Route path="presentation" element={<PhotoChoice makerspaceId={scope.makerspaceId} eventId={scope.eventId} eventName="this event" actorId={accountId} />} />
      <Route path="resume" element={<EventResumePanel scope={scope} />} />
      <Route path="*" element={<p role="status">{t`This part of the programme is unavailable. Choose an available step above.`}</p>} />
    </Routes>
  </div>
}
export function availableJourneys(context: ProgrammeContext) {
  const { programme, routes } = context
  const hackathon = programme.kind === 'hackathon' && programme.capabilities['events.hackathons']
  return [programmeRoutes.application, ...(hackathon ? [programmeRoutes.team,
    ...(programme.finder_enabled ? [programmeRoutes.finder] : []), programmeRoutes.project,
    ...(programme.capabilities['events.mentoring'] ? [programmeRoutes.help, programmeRoutes.officeHours] : []), programmeRoutes.sharing]
    // Mentor Desk on any event (#128 C-36, E2-f): attendees drop in without a team.
    : programme.capabilities['events.mentoring'] ? [programmeRoutes.help, programmeRoutes.officeHours] : []),
    ...(routes.role_postings ? [programmeRoutes.contribute] : []), programmeRoutes.presentation, ...(programme.capabilities['events.volunteering'] ? [{ suffix: 'shifts', label: t`Available shifts`, name: 'event-programme-shifts' }] : [])]
}
function RoleRoute({ scope, context, base }: { scope: EventScope; context: ProgrammeContext; base: string }) {
  const { postingId, applicationId } = useParams()
  const id = Number(postingId ?? applicationId)
  if (!Number.isSafeInteger(id) || id < 1) return <p role="alert">{t`This role application is unavailable.`}</p>
  return <ProgrammeRolePage scope={scope} context={context} base={base} postingId={postingId ? id : undefined} applicationId={applicationId ? id : undefined} />
}
