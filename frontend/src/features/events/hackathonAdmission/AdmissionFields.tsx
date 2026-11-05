import { useParams } from 'react-router-dom'
import { useChargesOn } from '../../../lib/charges'
import type { AdmissionRequirements, AdmissionSelection } from './types'

export function AdmissionFields({ requirements: r, value, onChange, disabled }: {
  requirements: AdmissionRequirements; value: AdmissionSelection
  onChange: (value: AdmissionSelection) => void; disabled: boolean
}) {
  const set = (update: Partial<AdmissionSelection>) => onChange({ ...value, ...update })
  const showPrice = useChargesOn('events', useParams().slug) // #184: free events list tickets without prices
  return <fieldset disabled={disabled} className="grid gap-4">
    <legend className="title-section mb-3">Your admission details</legend>
    {r.ticket_selection_required || r.ticket_types.length ? <label className="grid gap-1 text-sm text-ink">Ticket
      <select className="desk-input" required={r.ticket_selection_required} value={value.ticket_type_id ?? ''}
        onChange={e => set({ ticket_type_id: e.target.value ? Number(e.target.value) : undefined })}>
        <option value="">Choose a ticket</option>{r.ticket_types.map(t => <option key={t.id} value={t.id}>
          {t.name}{showPrice ? ` · ${r.currency} ${t.amount}` : ''}{t.spots_left === null ? '' : ' · ' + t.spots_left + ' places'}</option>)}
      </select></label> : null}
    {r.contact_requirements.email.fallback_required ? <label className="grid gap-1 text-sm text-ink">Contact email
      <input required type="email" maxLength={254} autoComplete="email" className="desk-input" value={value.email ?? ''} onChange={e => set({ email: e.target.value })} /></label> : null}
    {r.contact_requirements.phone.fallback_required ? <label className="grid gap-1 text-sm text-ink">Contact phone
      <input required type="tel" maxLength={64} autoComplete="tel" className="desk-input" value={value.phone ?? ''} onChange={e => set({ phone: e.target.value })} /></label> : null}
    {r.invite_code_allowed ? <label className="grid gap-1 text-sm text-ink">Invitation code (optional)
      <input maxLength={128} autoComplete="off" className="desk-input" value={value.invite_code ?? ''} onChange={e => set({ invite_code: e.target.value || undefined })} /></label> : null}
    {r.promo_codes_enabled ? <label className="grid gap-1 text-sm text-ink">Promo code (optional)
      <input maxLength={128} autoComplete="off" className="desk-input" value={value.promo_code ?? ''} onChange={e => set({ promo_code: e.target.value || undefined })} /></label> : null}
    {r.host_waiver?.acceptance_required ? <div className="grid gap-3 rounded-xl border border-line p-4">
      <h3 className="title-section">Host waiver</h3><p className="whitespace-pre-wrap text-sm text-ink">{r.host_waiver.body}</p>
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" required
        checked={value.host_waiver_accepted === true} onChange={e => set({ host_waiver_id: r.host_waiver!.id,
          host_waiver_version: r.host_waiver!.version, host_waiver_accepted: e.target.checked })} />I accept this host waiver.</label>
    </div> : null}
  </fieldset>
}
