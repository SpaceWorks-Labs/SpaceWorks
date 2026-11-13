import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { FormPageLayout } from '../../../components/layouts'
import { ErrorBlock } from '../../../components/ui'
import { memberRequest, StructuredApiError } from '../../../lib/api'
import type { PublicEventRegistrationResponse } from '../../../generated/api'
import type { ProgrammeContext } from '../contracts/types'
import type { AdmissionRequirements, AdmissionSelection, FormValue } from '../hackathonAdmission/types'
import { AdmissionFields } from '../hackathonAdmission/AdmissionFields'
import { ProgrammeFields, formSchema } from './formBridge'
import { memberFormInput } from '../../forms'
import { prefillDetails } from '../../accountSavedDetails/api'
import { SaveIntentNotice } from '../../accountSavedDetails/RegistrationSavedDetails'
import { registrationStatusLabel } from '../../members/registrationLabels'

export function OrdinaryProgrammeRegistration({ context, accountId }: { context: ProgrammeContext; accountId: number }) {
  const [value, setValue] = useState<FormValue>({ answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {} })
  const [selection, setSelection] = useState<AdmissionSelection>({ host_waiver_accepted: false })
  const operation = useRef(crypto.randomUUID())
  const schema = context.registration_form
  const prefill = useQuery({ queryKey: ['ordinary-event-prefill', accountId, context.makerspace.id, context.event.id,
    !Array.isArray(schema) && schema?.revision, context.event.event_date_revision], retry: false, gcTime: 0,
    enabled: Boolean(schema && !Array.isArray(schema) && context.saved_details.readiness === 'ready'), queryFn: () => {
      const descriptor = formSchema(schema)
      return prefillDetails({ context: { event_id: context.event.id, makerspace_id: context.makerspace.id, subject_kind: 'registration' },
        form_id: descriptor.form_id, form_revision: descriptor.revision, event_date_revision: context.event.event_date_revision })
    } })
  const registration = useMutation({ mutationFn: () => {
    const target = context.routes.ordinary_register
    if (!target) throw new Error(t`Registration is unavailable.`)
    const formInput = schema && !Array.isArray(schema) ? memberFormInput(formSchema(schema), value) : { custom_answers: value.answers }
    return memberRequest<PublicEventRegistrationResponse & { save_intent?: { operation_id: string } }>(target.url.slice('/api/v1'.length), {
      method: 'POST', headers: { 'Idempotency-Key': operation.current }, body: JSON.stringify({ ...formInput, ...selection,
        event_date_revision: context.event.event_date_revision, operation_id: operation.current, expected_version: 0 }),
    })
  } })
  if (registration.data) return <div className="grid gap-4"><p role="status">{t`Registration received: ${registrationStatusLabel(registration.data.status)}.`}</p>
    {registration.data.save_intent ? <SaveIntentNotice actorId={accountId} operationId={registration.data.save_intent.operation_id} /> : null}
    <a className="desk-button" href={`/m/${context.makerspace.slug}/member/events/history`}>{t`Tickets and certificates`}</a>
  </div>
  const errors = registration.error instanceof StructuredApiError ? registration.error.body.fields as Record<string, unknown> : {}
  return <FormPageLayout header={{ title: t`Register for this event`, subtitle: t`Review what you share and what you save privately.` }} state={{ status: 'ready' }}
    submit={{ label: t`Register`, pending: registration.isPending, onClick: () => registration.mutate() }} form={<div className="grid gap-5">
      <ErrorBlock error={registration.error || prefill.error} />
      <AdmissionFields requirements={context.admission_requirements as AdmissionRequirements} value={selection} disabled={registration.isPending}
        onChange={next => { setSelection(next); operation.current = crypto.randomUUID() }} />
      {schema ? <ProgrammeFields schema={schema} value={value} prefill={prefill.data} savedDetailsAvailable={context.saved_details.readiness === 'ready'}
        errors={errors ?? {}} disabled={registration.isPending} onChange={next => { setValue(next); operation.current = crypto.randomUUID() }} /> : null}
    </div>} />
}
