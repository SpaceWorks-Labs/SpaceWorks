import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from 'react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card, Field, StatusPill } from '../../../components/ui'
import type { EventScope, RoleApplication, Shift, Signup } from '../../events/contributions/types'
import { errorText, useProgrammeCommand, useProgrammeDetail, useProgrammeList } from '../../events/contributions/api'

interface AdminSignup extends Signup { member_id: number; assignment_id: number }
interface AdminShift extends Shift { signups: AdminSignup[] }

function ShiftSignups({ scope, shiftId }: { scope: EventScope; shiftId: number }) {
  const query = useProgrammeDetail<AdminShift>(scope, 'admin', `/shifts/${shiftId}/`)
  const command = useProgrammeCommand(scope, 'admin')
  const [minutes, setMinutes] = useState('')
  const [reason, setReason] = useState('')
  return <section className="mt-4 grid gap-3" aria-label={t`Shift signups`}>
    {query.isPending ? <p role="status">{t`Loading signups…`}</p> : null}
    {query.error || command.error ? <p role="alert" className="text-danger">{errorText(query.error ?? command.error)}</p> : null}
    <Field label={t`Corrected minutes`} hint={t`For an already verified shift. Another organizer must verify your own hours.`}><input className="desk-input" type="number" min={0} max={1440} value={minutes} onChange={event => setMinutes(event.target.value)} /></Field>
    <Field label={t`Correction reason`}><textarea className="desk-input" maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
    {query.data?.signups.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3"><div>
      <h3 className="title-section">{t`Member ${row.member_id} · Application ${row.assignment_id}`}</h3>
      <p className="text-sm text-muted">{row.attendance ?? row.state}{row.verified_minutes !== null ? t` · ${row.verified_minutes} verified minutes` : ''}</p></div>
      <div className="flex flex-wrap gap-2">{row.allowed_actions.map(action => <ActionControl key={action} action={{ label: action.replace(/-/g, ' '), pending: command.isPending,
        disabled: action === 'adjust-hours' && (!reason.trim() || minutes === ''),
        disabledReason: action === 'adjust-hours' && (!reason.trim() || minutes === '') ? 'Enter corrected minutes and a reason.' : undefined,
        onClick: () => command.mutate({ path: `/shift-signups/${row.id}/${action}/`, version: row.version,
          fields: action === 'adjust-hours' ? { minutes: Number(minutes), reason } : {} }) }} />)}</div></div></Card>)}
  </section>
}

export function VolunteerManager({ scope, setupTools, renderRoleTools }: {
  scope: EventScope; setupTools?: ReactNode; renderRoleTools?: (row: RoleApplication) => ReactNode
}) {
  const [tab, setTab] = useState('roles')
  const [page, setPage] = useState(1)
  const [selectedShift, setSelectedShift] = useState<number | null>(null)
  const roles = useProgrammeList<RoleApplication>(scope, 'admin', '/roles/', page, false, tab === 'roles')
  const shifts = useProgrammeList<Shift>(scope, 'admin', '/shifts/', page, false, tab === 'shifts')
  const command = useProgrammeCommand(scope, 'admin')
  const query = tab === 'roles' ? roles : shifts
  return <ListLayout header={{ title: t`Event contributors`, subtitle: t`Approve applications, manage shifts, and verify completed work.` }}
    tabs={[{ key: 'roles', label: t`Applications and roles` }, { key: 'shifts', label: t`Shifts and hours` }, ...(setupTools ? [{ key: 'setup', label: t`Setup` }] : [])]} activeTab={tab}
    onTabChange={key => { setTab(key); setPage(1); setSelectedShift(null) }}
    state={tab === 'setup' ? { status: 'ready' } : query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    isEmpty={tab !== 'setup' && !query.data?.results.length} empty={{ message: t`No contributor records yet.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>{command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {tab === 'setup' ? setupTools : tab === 'roles' ? roles.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="title-section">{t`Application ${row.id} · ${row.role.replace(/_/g, ' ')}`}</h2><StatusPill label={row.state} tone="neutral" /></div>
        <div className="flex gap-2">{['applied', 'proposed'].includes(row.state) ? <ActionControl action={{ label: t`Approve`, pending: command.isPending,
          onClick: () => command.mutate({ path: `/roles/${row.id}/approve/`, version: row.version }) }} /> : null}
          {['approved', 'applied', 'proposed'].includes(row.state) ? <ActionControl action={{ label: t`Revoke role`, pending: command.isPending,
            confirm: { title: t`Revoke this role?`, message: t`Its role and future shift permissions will end. Contribution history stays on record.` },
            onClick: () => command.mutate({ path: `/roles/${row.id}/revoke/`, version: row.version }) }} /> : null}</div>
      </div>{renderRoleTools?.(row)}</Card>) : shifts.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3"><div>
        <h2 className="title-section">{row.task}</h2><p className="text-sm text-muted">{new Date(row.starts_at).toLocaleString(formatLocale())} · {row.kind === 'office_hours' ? t`Office hours` : t`Volunteer shift`}</p></div>
        <ActionControl action={{ label: t`View signups and hours`, onClick: () => setSelectedShift(selectedShift === row.id ? null : row.id) }} /></div>
        {selectedShift === row.id ? <ShiftSignups scope={scope} shiftId={row.id} /> : null}</Card>)}
    </> }} />
}
