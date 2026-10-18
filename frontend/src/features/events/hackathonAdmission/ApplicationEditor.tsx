import { useEffect, useState } from 'react'
import { FormPageLayout } from '../../../components/layouts'
import { ErrorText } from '../../../components/ui'
import { StructuredApiError } from '../../../lib/api'
import { AdmissionArtwork } from './AdmissionArtwork'
import { AdmissionFields } from './AdmissionFields'
import { applicationPayload } from './applicationPayload'
import type { AdmissionSelection, Application, FormFields, FormValue, Prefill, ProgrammeContext } from './types'

export function ApplicationEditor({ context, application, Fields, prefill, pending, error, onSave }: {
  context: ProgrammeContext; application: Application; Fields: FormFields; prefill?: Prefill
  pending: boolean; error: Error | null
  onSave: (body: Record<string, unknown>, draft: boolean) => Promise<Application> | void
}) {
  const [value, setValue] = useState<FormValue>({ answers: Object.fromEntries(application.answers
    .filter(answer => typeof answer.id === 'string' && answer.type !== 'age_at_event' && 'value' in answer).map(a => [a.id as string, a.value])),
    derivations: {}, save_choices: {}, saved_detail_versions: {} })
  const [selection, setSelection] = useState<AdmissionSelection>({ ticket_type_id: application.admission.ticket_type_id ?? undefined,
    email: application.admission.contact.email, phone: application.admission.contact.phone, host_waiver_accepted: false })
  const [coc, setCoc] = useState(false)
  const [sharing, setSharing] = useState(application.optional_consents?.mlh_data_sharing?.accepted ?? false)
  const [dirty, setDirty] = useState(false)
  const [baseVersion, setBaseVersion] = useState(application.version)
  const conflict = dirty && application.version !== baseVersion
  useEffect(() => { if (!dirty) setBaseVersion(application.version) }, [application.version, dirty])
  const editingSubmitted = application.state === 'submitted'
  const waiver = application.admission_requirements.host_waiver
  useEffect(() => { setSelection(s => ({ ...s, host_waiver_accepted: false, host_waiver_id: null, host_waiver_version: null })) }, [waiver?.id, waiver?.version])
  useEffect(() => { setCoc(false) }, [context.coc?.revision])
  useEffect(() => {
    if (error instanceof StructuredApiError && error.code === 'host_waiver_required') {
      setSelection(s => ({ ...s, host_waiver_accepted: false }))
    }
  }, [error])
  useEffect(() => {
    if (!prefill || dirty || application.answers.length) return
    setValue(v => ({ ...v, save_choices: prefill.save_defaults, saved_detail_versions: prefill.saved_detail_versions }))
  }, [prefill, dirty, application.answers.length])
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
  const save = (draft: boolean) => {
    const result = onSave(applicationPayload(context, { ...application, version: baseVersion }, value, selection, coc, sharing, draft), draft)
    if (result) void result.then(saved => { setBaseVersion(saved.version); setDirty(false) }).catch(() => { /* The mutation's typed error stays visible. */ })
  }
  const fields = error instanceof StructuredApiError && error.body.fields && typeof error.body.fields === 'object'
    ? error.body.fields as Record<string, unknown> : {}
  return <FormPageLayout header={{ title: 'Apply to make something together', subtitle: 'Review your own answers, ticket and agreements before submitting.' }}
    state={{ status: 'ready' }} submit={{ label: editingSubmitted ? 'Save answers' : 'Submit application', pending, disabled: !coc || conflict, onClick: () => save(editingSubmitted) }}
    cancel={editingSubmitted ? undefined : { label: 'Save draft', disabled: pending || conflict, onClick: () => save(true) }}
    form={<div className="grid gap-6">
      <AdmissionArtwork kind="hackathon" />
      {dirty ? <p className="rounded-xl border border-line bg-panel p-3 text-sm text-ink" role="status">You have unsaved changes.</p> : null}
      {conflict ? <div role="alert" className="grid gap-3 rounded-xl border border-line p-4"><p>The application changed. Your draft is preserved. Review the current questions before reapplying your answers.</p>
        <button className="desk-button" type="button" onClick={() => { setBaseVersion(application.version); setCoc(false) }}>Keep my draft and review the new version</button>
        <button className="desk-button" type="button" onClick={() => { setValue({ answers: Object.fromEntries(application.answers.filter(answer => typeof answer.id === 'string' && answer.type !== 'age_at_event' && 'value' in answer).map(answer => [answer.id as string, answer.value])), derivations: {}, save_choices: {}, saved_detail_versions: {} }); setBaseVersion(application.version); setDirty(false); setCoc(false) }}>Reload server answers</button>
      </div> : null}
      {error ? <ErrorText message={error.message} /> : null}
      {context.application_form ? <Fields schema={context.application_form} value={value} prefill={prefill}
        onChange={next => { setValue(next); setDirty(true) }} errors={fields} disabled={pending}
        savedDetailsAvailable={context.saved_details.readiness === 'ready'} /> : null}
      {context.saved_details.readiness === 'unavailable' ? <p className="text-sm text-muted">Saved details are unavailable. You can apply with saving switched off.</p> : null}
      <AdmissionFields requirements={application.admission_requirements} value={selection} disabled={pending || editingSubmitted}
        onChange={next => { setSelection(next); setDirty(true) }} />
      <fieldset disabled={pending} className="grid gap-3"><legend className="title-section mb-3">Code of conduct</legend>
        <p className="whitespace-pre-wrap text-sm text-ink">{context.coc?.body}</p>
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" required checked={coc}
          onChange={event => { setCoc(event.target.checked); setDirty(true) }} />I agree to this code of conduct.</label>
        {application.optional_consent_purposes?.includes('mlh_data_sharing') ? <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={sharing}
          onChange={event => { setSharing(event.target.checked); setDirty(true) }} />I choose to share my submitted details with MLH (optional).</label> : null}
      </fieldset>
      <p className="text-sm text-muted">An offer needs your RSVP before you have a confirmed place. Saved details remain private until you submit them to an event.</p>
    </div>} />
}
