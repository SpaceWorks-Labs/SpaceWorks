import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { memberRequest } from '../../../lib/api'
import { HelpComposer } from '../contributions/HelpComposer'
import { useNavigate } from 'react-router-dom'
import { ErrorBlock } from '../../../components/ui'
import type { ProgrammeContext } from '../contracts/types'
import type { EventScope } from '../contributions/types'
import { useTeams } from '../hackathonAdmission/useTeams'
import { SubmissionEditor } from '../hackathonSubmissions/SubmissionEditor'
import { useSubmission } from '../hackathonSubmissions/api'
import { OfficeHours } from '../contributions/OfficeHours'
import { HelpQueue } from '../contributions/HelpQueue'
import { HelpDetail } from '../contributions/HelpDetail'
import { GalleryPrivacy } from '../hackathonGallery/GalleryPrivacy'
import { EventResumePanel } from './EventResumePanel'
import { makerFormats } from './makerFormats'

import { uploadOrigins } from './uploadPolicy'
export function TeamJourney({ context, scope, section, base }: { context: ProgrammeContext; scope: EventScope; section: string; base: string }) {
  const { teams } = useTeams(context, scope.accountId)
  const team = teams.data?.results[0]
  const [helpId, setHelpId] = useState<number | null>(null)
  const navigate = useNavigate()
  const categories = useQuery({ queryKey: ["member", scope.accountId, "help-topics", scope.makerspaceId, scope.eventId], gcTime: 0,
    queryFn: () => memberRequest<{ results: { key: string; label: string }[] }>(`/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/help-topics/`),
    enabled: section === 'help' && context.programme.capabilities['events.mentoring'], retry: false })
  if (teams.error) return <ErrorBlock error={teams.error} onRetry={() => void teams.refetch()} />
  if (teams.isPending) return <p role="status">{t`Loading your team…`}</p>
  if (!team) return <div className="grid gap-3"><p>{t`Your team must be ready before this step.`}</p><button className="desk-button" onClick={() => navigate(`${base}/team`)}>{t`Open your team`}</button></div>
  const submissionScope = { ...scope, teamId: team.id }
  if (section === 'project') return <SubmissionEditor scope={submissionScope} formats={makerFormats} uploadOrigins={uploadOrigins()} />
  if (section === 'sharing') return <div className="grid gap-6"><TeamSharing scope={submissionScope} leader={team.leader_member_id === scope.accountId} /><EventResumePanel scope={scope} /></div>
  if (!context.programme.capabilities['events.mentoring']) return <p>{t`This event has no mentor programme available.`}</p>
  if (section === 'office-hours') return <OfficeHours scope={scope} teamId={team.id} />
  return helpId ? <HelpDetail scope={scope} helpId={helpId} onClose={() => setHelpId(null)} /> : <div className="grid gap-6">
    <HelpQueue scope={scope} surface="member" onOpen={row => setHelpId(row.id)} />
    {categories.error ? <ErrorBlock error={categories.error} onRetry={() => void categories.refetch()} /> : categories.data?.results.length ? <HelpComposer scope={scope} surface="member" teams={[{ id: team.id, label: team.name }]} categories={categories.data.results} /> : <p className="text-sm text-muted">{t`No help topics are available for this event.`}</p>}
  </div>
}
function TeamSharing({ scope, leader }: { scope: EventScope & { teamId: number }; leader: boolean }) {
  const submission = useSubmission(scope)
  if (submission.error) return <ErrorBlock error={submission.error} />
  if (!submission.data?.snapshot_id) return <p>{t`Submit your project before choosing gallery publication.`}</p>
  return <GalleryPrivacy scope={{ ...scope, actorId: scope.accountId }} teamId={scope.teamId} snapshotId={submission.data.snapshot_id} leader={leader}
    items={(submission.data.project.asset_ids ?? []).map(id => ({ id, kind: 'asset', label: t`Project file ${id}` }))} />
}
