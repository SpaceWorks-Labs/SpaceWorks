import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { CenteredCardLayout } from '../../../components/layouts'
import { ErrorText } from '../../../components/ui'
import { CommandSession } from './transport'
import type { ProgrammeContext } from './types'

export function takeInvitationFragment(location: Pick<Location, 'hash' | 'pathname' | 'search'>, replace: (url: string) => void) {
  const params = new URLSearchParams(location.hash.replace(/^#/, ''))
  const token = params.get('token') ?? ''
  if (token) replace(location.pathname + location.search)
  return /^[a-f0-9]{64}$/.test(token) ? token : ''
}
/** The private share URL carries the command version; no metadata read is needed. */
export function TeamInvitationPage({ context, teamId, teamVersion, token, onJoined }: {
  context: ProgrammeContext; teamId: number; teamVersion: number; token: string; onJoined: () => void
}) {
  const commands = useRef(new CommandSession())
  const [agreed, setAgreed] = useState(false)
  const accept = useMutation({ mutationFn: () => commands.current.send(context.routes.member_base + '/teams/' + teamId + '/accept/',
    'POST', { expected_version: teamVersion, token }), onSuccess: onJoined })
  return <CenteredCardLayout standalone={false} title={t`Join this hackathon team`} state={{ status: 'ready' }}
    body={t`This invitation is private and can be used once. Your own application and eligibility still apply.`}
    content={<div className="grid gap-3"><label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={agreed}
      onChange={e => setAgreed(e.target.checked)} />{t`I want to join this team.`}</label>{accept.error ? <ErrorText message={accept.error.message} /> : null}</div>}
    primary={{ label: t`Accept invitation`, disabled: !agreed || !token, pending: accept.isPending, onClick: () => accept.mutate() }} />
}
