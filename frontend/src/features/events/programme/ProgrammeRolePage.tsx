import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { RoleApplicationForm, type RoleFormBridge } from '../contributions/RoleApplicationForm'
import { useProgrammeDetail } from '../contributions/api'
import type { EventScope, Posting, RoleApplication, RoleFormValue } from '../contributions/types'
import type { ProgrammeContext } from '../contracts/types'
import { prefillDetails } from '../../accountSavedDetails/api'
import { SaveIntentNotice } from '../../accountSavedDetails/RegistrationSavedDetails'
import { FormV2Fields, memberFormInput, type FormState, type FieldErrors } from '../../forms'
import { filledState, formSchema, ownerAnswers } from './formBridge'
import { ErrorBlock } from '../../../components/ui'

export function ProgrammeRolePage({ scope, context, postingId, applicationId, base }: {
  scope: EventScope; context: ProgrammeContext; postingId?: number; applicationId?: number; base: string
}) {
  const navigate = useNavigate()
  const application = useProgrammeDetail<RoleApplication>(scope, 'member', `/role-applications/${applicationId}/`, Boolean(applicationId))
  const id = postingId ?? application.data?.posting_id
  const posting = useProgrammeDetail<Posting>(scope, 'member', `/role-postings/${id}/`, Boolean(id))
  const bridge = useMemo<RoleFormBridge>(() => ({
    prefill: async ({ posting: row, application: own }) => {
      const schema = formSchema(own?.form ?? row.form)
      const answers = ownerAnswers(own?.answers, schema)
      let state: FormState = { answers, derivations: {}, save_choices: {}, saved_detail_versions: {} }
      if (!own && context.saved_details.readiness === 'ready') {
        const suggestions = await prefillDetails({ context: { event_id: scope.eventId, makerspace_id: scope.makerspaceId,
          subject_kind: 'role_assignment', posting_id: row.id }, form_id: schema.form_id, form_revision: schema.revision,
          event_date_revision: context.event.event_date_revision })
        state = filledState(schema, state, suggestions)
      }
      return { ...memberFormInput(schema, state), event_date_revision: context.event.event_date_revision,
        coc: { revision: row.coc?.revision ?? context.coc?.revision ?? 0, accepted: false } } as RoleFormValue
    },
    render: ({ value, onChange, disabled, errors }) => {
      const schema = formSchema(application.data?.form ?? posting.data?.form)
      return <fieldset disabled={disabled} className="grid gap-5"><FormV2Fields schema={schema} value={value} allowSavedDetails={context.saved_details.readiness === 'ready'}
        errors={errors as FieldErrors} onChange={next => onChange({ ...value, ...next, event_date_revision: context.event.event_date_revision,
          save_choices: context.saved_details.readiness === 'ready' ? next.save_choices : {} })} />
        <p className="whitespace-pre-wrap text-sm">{posting.data?.coc?.body ?? context.coc?.body}</p>
        <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={value.coc?.accepted ?? false}
          onChange={event => onChange({ ...value, coc: { revision: value.coc?.revision ?? 0, accepted: event.target.checked } })} />I agree to this code of conduct.</label>
        {posting.data?.host_waiver?.acceptance_required ? <section className="grid gap-2">
          <p className="whitespace-pre-wrap text-sm">{posting.data.host_waiver.body}</p>
          <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={value.host_waiver_accepted === true && value.host_waiver_id === posting.data.host_waiver.id && value.host_waiver_version === posting.data.host_waiver.version}
            onChange={event => onChange({ ...value, host_waiver_id: posting.data!.host_waiver!.id,
              host_waiver_version: posting.data!.host_waiver!.version, host_waiver_accepted: event.target.checked })} />I accept this host waiver for my contributor role.</label>
        </section> : null}
      </fieldset>
    },
    savedDetailsStatus: intent => <SaveIntentNotice actorId={scope.accountId} operationId={intent.operation_id} />,
  }), [scope.accountId, scope.eventId, scope.makerspaceId, context, application.data?.form, posting.data])
  const error = application.error || posting.error
  if (error) return <ErrorBlock error={error} onRetry={() => { void application.refetch(); void posting.refetch() }} />
  if (!posting.data || (applicationId && !application.data)) return <p role="status">Loading your role application…</p>
  return <RoleApplicationForm scope={scope} posting={posting.data} application={application.data ?? posting.data.application ?? null}
    bridge={bridge} completionReady onSaved={savedId => navigate(`${base}/role-applications/${savedId}`)} />
}
