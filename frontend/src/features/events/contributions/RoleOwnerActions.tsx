import { t } from "@lingui/core/macro";
import { useMutation } from '@tanstack/react-query'
import { ActionControl } from '../../../components/ui'
import { basePath, errorText, requestFor, useProgrammeCommand } from './api'
import type { EventScope, RoleApplication } from './types'

export function RoleOwnerActions({ scope, row, completionReady, onSaved }: { scope: EventScope; row: RoleApplication; completionReady: boolean; onSaved: (id: number) => void }) {
  const command = useProgrammeCommand(scope, 'member')
  const archive = useMutation({ retry: false, mutationFn: async () => {
    const data = await requestFor('member')<unknown>(`${basePath(scope, 'member')}/role-applications/${row.id}/export/`)
    const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }))
    try {
      const link = document.createElement('a'); link.href = url; link.download = `my-role-${row.id}.json`
      document.body.appendChild(link); link.click(); link.remove()
    } finally { window.setTimeout(() => URL.revokeObjectURL(url), 1000) }
  } })
  return <div className="mt-4 grid gap-3"><div className="flex flex-wrap gap-2">
    {row.allowed_actions.includes('withdraw') ? <ActionControl action={{ label: t`Withdraw my application`, pending: command.isPending,
      confirm: { title: t`Withdraw this application?`, message: t`Future duty permissions and bookings will end. Work history stays on record.` },
      onClick: () => command.mutate({ path: `/role-applications/${row.id}/withdraw/`, version: row.version, fields: { reason_code: 'availability_changed' } }, { onSuccess: value => onSaved(value.id) }) }} /> : null}
    {completionReady && row.allowed_actions.includes('decline') ? <ActionControl action={{ label: t`Decline role invitation`, pending: command.isPending,
      onClick: () => command.mutate({ path: `/role-applications/${row.id}/decline/`, version: row.version, fields: { reason: t`I cannot take up this role.` } }, { onSuccess: value => onSaved(value.id) }) }} /> : null}
    {completionReady ? <ActionControl action={{ label: t`Export my application and date sources`, pending: archive.isPending, onClick: () => archive.mutate() }} /> : null}
  </div>{command.error || archive.error ? <p role="alert" className="text-danger">{errorText(command.error ?? archive.error)}</p> : null}</div>
}
