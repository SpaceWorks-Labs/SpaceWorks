import { useEffect, useRef, useState, type ComponentType } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FormPageLayout } from '../../../components/layouts'
import { ErrorText } from '../../../components/ui'
import { CommandSession } from '../../events/hackathonAdmission/transport'
import { MlhPresetPicker, type ProgrammeMlhPreset } from './MlhPresetPicker'
import { RubricEditor } from './RubricEditor'
import { useHackathonConfig } from './useAdmissionAdmin'
import type { Config } from './types'

export type ProgrammeFormEditor = ComponentType<{ value: unknown; onChange: (value: unknown) => void }>
const defaults: Partial<Config> = { enabled: false, review_mode: 'rolling', review_count: 2, rsvp_days: 4,
  team_mode: 'individual_then_team', team_min: 1, team_max: 4, finder_enabled: false, blind_review: false,
  team_eligibility: 'confirmed', attendance_required: true, late_policy: 'reject', submission_grace_minutes: 0,
  review_rubric: { revision: 1, criteria: [] }, application_form: [], offer_capacity: null }
const dateFields = ['application_opens_at', 'application_closes_at', 'team_lock_at', 'submission_opens_at', 'submission_deadline'] as const

export function HackathonConfigPanel({ eventId, FormEditor, mlhPresets }: { eventId: number; FormEditor: ProgrammeFormEditor; mlhPresets: readonly ProgrammeMlhPreset[] }) {
  const query = useHackathonConfig(eventId), client = useQueryClient(), commands = useRef(new CommandSession())
  const [draft, setDraft] = useState<Partial<Config>>(defaults), [body, setBody] = useState(''), [dirty, setDirty] = useState(false)
  useEffect(() => { if (query.data && !dirty) { setDraft({ ...defaults, ...query.data }); setBody(query.data.coc?.body ?? '') } }, [query.data, dirty])
  const set = <K extends keyof Config>(key: K, value: Config[K]) => { setDraft(d => ({ ...d, [key]: value })); setDirty(true) }
  const save = useMutation({ mutationFn: () => {
    const { id: _id, event_id: _event, version, state: _state, coc: _coc, counts: _counts, allowed_actions: _actions, ...editable } = draft
    return commands.current.send('/api/v1/admin/events/' + eventId + '/hackathon/', 'PATCH', {
      ...editable, expected_version: query.data?.version ?? 0,
      ...(body !== query.data?.coc?.body ? { coc_body: body } : {}) }, true)
  }, onSuccess: () => { setDirty(false); void client.invalidateQueries({ queryKey: ['staff-event-admission', eventId] }) } })
  return <FormPageLayout header={{ title: 'Hackathon admission', subtitle: 'Applications, review and teams stay inside this event.' }}
    state={query.isLoading ? { status: 'loading' } : query.error ? { status: 'error', error: query.error.message, onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    submit={{ label: 'Save admission settings', disabled: !dirty, pending: save.isPending, onClick: () => save.mutate() }}
    form={<div className="grid gap-6">
      {save.error ? <ErrorText message={save.error.message} /> : null}
      {dirty ? <p role="status" className="rounded-xl border border-line p-3 text-sm text-ink">You have unsaved changes.</p> : null}
      <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={draft.enabled ?? false} onChange={e => set('enabled', e.target.checked)} />Enable hackathon applications</label>
      <fieldset className="grid gap-3"><legend className="title-section mb-3">Review and RSVP</legend>
        <label className="grid gap-1 text-sm text-ink">Review mode<select className="desk-input" value={draft.review_mode} onChange={e => set('review_mode', e.target.value as Config['review_mode'])}>
          <option value="auto">Automatic offers</option><option value="rolling">Rolling reviewed decisions</option><option value="batch">Batch review and release</option></select></label>
        <label className="grid gap-1 text-sm text-ink">Distinct reviewers per subject<input className="desk-input" type="number" min={1} max={20} value={draft.review_count} onChange={e => set('review_count', Number(e.target.value))} /></label>
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={draft.blind_review} onChange={e => set('blind_review', e.target.checked)} />Use blind-safe review projections</label>
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={draft.review_round_closed ?? false} onChange={e => set('review_round_closed', e.target.checked)} />Close the review round and reveal completed scores to its reviewers</label>
        <p className="text-sm text-muted">Identity fields are withheld. Free text can still identify its author.</p>
        <label className="grid gap-1 text-sm text-ink">Days to RSVP after release<input type="number" className="desk-input" min={1} max={30} value={draft.rsvp_days} onChange={e => set('rsvp_days', Number(e.target.value))} /></label>
        <label className="grid gap-1 text-sm text-ink">Offer ceiling (blank uses event capacity)<input type="number" className="desk-input" min={0} value={draft.offer_capacity ?? ''}
          onChange={e => set('offer_capacity', e.target.value === '' ? null : Number(e.target.value))} /></label>
        <p className="text-sm text-muted">Overbooking changes offers only. RSVP still respects the event's hard capacity and each ticket's capacity.</p>
        {query.data?.counts ? <p className="text-sm text-ink">{query.data.counts.offered} offers · {query.data.counts.confirmed} confirmed · {query.data.counts.hard_spots_left ?? 'Unlimited'} hard places left</p> : null}
      </fieldset>
      <RubricEditor value={draft.review_rubric!} onChange={value => set('review_rubric', value)} />
      <fieldset className="grid gap-3"><legend className="title-section mb-3">Team formation</legend>
        <label className="grid gap-1 text-sm text-ink">Team mode<select className="desk-input" value={draft.team_mode} onChange={e => set('team_mode', e.target.value as Config['team_mode'])}>
          <option value="solo">Solo</option><option value="individual_then_team">Apply individually, then form teams</option><option value="team_together">Apply together as a team</option></select></label>
        {(['team_min', 'team_max'] as const).map(key => <label className="grid gap-1 text-sm text-ink" key={key}>{key === 'team_min' ? 'Minimum team size' : 'Maximum team size'}
          <input type="number" className="desk-input" min={1} max={100} value={draft[key]} onChange={e => set(key, Number(e.target.value))} /></label>)}
        <label className="grid gap-1 text-sm text-ink">When members can form teams<select className="desk-input" value={draft.team_eligibility} onChange={e => set('team_eligibility', e.target.value as Config['team_eligibility'])}><option value="confirmed">After confirming their place</option><option value="offered">After receiving an offer</option></select></label>
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={draft.finder_enabled} onChange={e => set('finder_enabled', e.target.checked)} />Enable team finder for individual applications</label>
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={draft.attendance_required} onChange={e => set('attendance_required', e.target.checked)} />Require every member to check in before project submission</label>
      </fieldset>
      <fieldset className="grid gap-3"><legend className="title-section mb-3">Application and submission windows</legend>
        {dateFields.map(key => <label className="grid gap-1 text-sm text-ink" key={key}>{key.replace(/_/g, ' ')} (UTC)
          <input type="datetime-local" className="desk-input" value={draft[key] ? new Date(draft[key]!).toISOString().slice(0, 16) : ''}
            onChange={e => set(key, e.target.value ? new Date(e.target.value + 'Z').toISOString() : null)} /></label>)}
        <label className="grid gap-1 text-sm text-ink">Late submission policy<select className="desk-input" value={draft.late_policy} onChange={e => set('late_policy', e.target.value as Config['late_policy'])}>
          <option value="reject">Reject late submissions</option><option value="accept_flagged">Accept and flag late submissions</option></select></label>
        <label className="grid gap-1 text-sm text-ink">Submission grace minutes<input type="number" className="desk-input" min={0} max={1440} value={draft.submission_grace_minutes} onChange={e => set('submission_grace_minutes', Number(e.target.value))} /></label>
      </fieldset>
      <fieldset className="grid gap-3"><legend className="title-section mb-3">Project file limits</legend>
        <label className="grid gap-1 text-sm text-ink">Storage budget in bytes (blank uses the deployment limit)<input type="number" min={1} step={1} className="desk-input" value={draft.storage_budget_bytes ?? ''} onChange={e => set('storage_budget_bytes', e.target.value ? Number(e.target.value) : null)} /></label>
        <p className="text-sm text-muted">The server enforces the deployment's ceiling and counts stored files plus active upload reservations.</p>
      </fieldset>
      <MlhPresetPicker presets={mlhPresets} value={draft.optional_mlh_schema ?? {}} disabled={save.isPending}
        onSelect={schema => { setDraft(d => ({ ...d, optional_mlh_schema: schema ?? {}, ...(schema ? { application_form: schema } : {}) })); setDirty(true) }} />
      <FormEditor value={draft.application_form} onChange={value => set('application_form', value)} />
      <label className="grid gap-1 text-sm text-ink">Code of conduct<textarea className="desk-input min-h-40" required maxLength={50000} value={body} onChange={e => { setBody(e.target.value); setDirty(true) }} /></label>
      <p className="text-sm text-muted">Publishing new conduct text creates an immutable revision. Applicants must review and accept that revision themselves.</p>
    </div>} />
}
