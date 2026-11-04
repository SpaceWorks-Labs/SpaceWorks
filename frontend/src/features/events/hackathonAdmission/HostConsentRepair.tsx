import { useEffect, useState } from 'react'
import { Card } from '../../../components/ui'
import type { Application } from './types'

export function HostConsentRepair({ application, pending, onRepair }: { application: Application; pending: boolean
  onRepair: (body: Record<string, unknown>) => void }) {
  const waiver = application.admission_requirements.host_waiver
  const [accepted, setAccepted] = useState(false)
  useEffect(() => { setAccepted(false) }, [waiver?.id, waiver?.version, application.version])
  if (!waiver || !application.allowed_actions.includes('repair_host_consent')) return null
  return <Card><form className="grid gap-3" onSubmit={event => { event.preventDefault(); onRepair({
    expected_version: application.version, host_waiver_id: waiver.id, host_waiver_version: waiver.version,
    host_waiver_accepted: accepted }) }}><h2 className="title-section">Review the current host waiver</h2>
    <p className="whitespace-pre-wrap text-sm text-ink">{waiver.body}</p>
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input required type="checkbox" checked={accepted}
      onChange={event => setAccepted(event.target.checked)} />I accept this current host waiver.</label>
    <button className="desk-button-primary justify-self-start" disabled={!accepted || pending} type="submit">Save host consent</button>
    <p className="text-sm text-muted">This updates your consent only. Your ticket, quote, answers and admission state stay as they are.</p>
  </form></Card>
}
