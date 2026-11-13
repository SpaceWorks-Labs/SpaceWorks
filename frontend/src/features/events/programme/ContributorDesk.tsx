import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { currentSessionContext } from '../../../lib/api/sessionContext'
import { ErrorBlock, Pagination } from '../../../components/ui'
import { MentorWorkspace } from '../../staff/eventProgramme/MentorWorkspace'
import { JudgingWorkspace } from '../../staff/eventProgramme/JudgingWorkspace'
import type { EventScope, RoleApplication } from '../contributions/types'
import type { ProgrammeContext } from '../contracts/types'
import { useProgrammeList, useProgrammeDetail } from '../contributions/api'
import { ShiftBrowser } from '../contributions/ShiftBrowser'

export function ContributorDesk({ scope, context, kind }: { scope: EventScope; context: ProgrammeContext; kind: 'mentor' | 'judge' | 'sponsor_rep' }) {
  const { assignmentId, sponsorId } = useParams()
  const [page, setPage] = useState(1)
  const roles = useProgrammeList<RoleApplication>(scope, 'member', '/role-applications/', page, false, !assignmentId)
  const detail = useProgrammeDetail<RoleApplication>(scope, 'member', `/role-applications/${assignmentId}/`, Boolean(assignmentId))
  if (roles.error || detail.error) return <ErrorBlock error={roles.error || detail.error} onRetry={() => { void roles.refetch(); if (assignmentId) void detail.refetch() }} />
  if (assignmentId ? detail.isPending : roles.isPending) return <LogoLoader label={t`Loading your event assignment…`} />
  const own = (assignmentId ? detail.data ? [detail.data] : [] : roles.data?.results ?? []).find(row => row.role === kind && row.state === 'approved' && row.entitlement_active
    && (kind !== 'mentor' || row.id === Number(assignmentId)))
  if (!own) return <div className="grid gap-3"><p role="status">{t`No active assignment is available on this page for your account.`}</p>{!assignmentId ? <Pagination page={page} count={roles.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((roles.data?.count ?? 0) / 24)} onChange={setPage} /> : null}</div>
  if (kind === 'mentor') return <MentorWorkspace scope={scope} manager={false} roundsEnabled={context.programme.capabilities['events.mentor_rounds']} ownAssignmentId={own.id} />
  return <JudgingWorkspace scope={{ ...scope, actorId: scope.accountId, context: currentSessionContext() }} timezone={context.event.timezone_name}
    manager={false} judge={kind === 'judge'} sponsor={kind === 'sponsor_rep'} galleryEnabled={false}
    sponsorIds={sponsorId && Number.isSafeInteger(Number(sponsorId)) && Number(sponsorId) > 0 ? [Number(sponsorId)] : []} />
}
export function ContributorShifts({ scope }: { scope: EventScope }) {
  const [page, setPage] = useState(1)
  const roles = useProgrammeList<RoleApplication>(scope, 'member', '/role-applications/', page)
  if (roles.error) return <ErrorBlock error={roles.error} onRetry={() => void roles.refetch()} />
  if (!roles.data) return <LogoLoader label={t`Loading your contributor roles…`} />
  return <div className="grid gap-5"><ShiftBrowser key={page} scope={scope} assignments={roles.data.results.filter(row => row.state === 'approved')} /><Pagination page={page} count={roles.data.count} pageSize={24} totalPages={Math.ceil(roles.data.count / 24)} onChange={setPage} /></div>
}
