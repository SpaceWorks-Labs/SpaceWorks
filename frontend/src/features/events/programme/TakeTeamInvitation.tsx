import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { takeInvitationFragment, TeamInvitationPage } from '../hackathonAdmission/TeamInvitationPage'
import type { ProgrammeContext } from '../contracts/types'

export function TakeTeamInvitation({ context, base }: { context: ProgrammeContext; base: string }) {
  const { teamId } = useParams(), [search] = useSearchParams(), navigate = useNavigate()
  const [token] = useState(() => takeInvitationFragment(window.location, url => window.history.replaceState(null, '', url)))
  const id = Number(teamId), version = Number(search.get('version'))
  if (!token || !Number.isSafeInteger(id) || id < 1 || !Number.isSafeInteger(version) || version < 1) return <p role="alert">{t`This team invitation is unavailable. Ask the team leader for a current link.`}</p>
  return <TeamInvitationPage context={context} teamId={id} teamVersion={version} token={token} onJoined={() => navigate(`${base}/team`, { replace: true })} />
}
