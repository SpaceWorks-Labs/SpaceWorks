import { useEffect, useState, type ReactNode } from 'react'
import { DetailLayout } from '../../../components/layouts'
import { ActionControl, Card } from '../../../components/ui'
import { StructuredApiError } from '../../../lib/api'
import { errorText, useProgrammeCommand } from './api'
import type { EventScope, Posting, RoleApplication, RoleFormValue } from './types'
import { RoleOwnerActions } from './RoleOwnerActions'

/** F renders/validates form v2; P owns prefill, derivation and save-choice defaults. */
export interface RoleFormBridge {
  prefill(input: { scope: EventScope; posting: Posting; application: RoleApplication | null }): Promise<RoleFormValue>
  render(input: { value: RoleFormValue; onChange: (value: RoleFormValue) => void; disabled: boolean; errors: unknown }): ReactNode
  savedDetailsStatus(intent: NonNullable<RoleApplication['save_intent']>): ReactNode
}

type Props = {
  scope: EventScope; posting: Posting; application: RoleApplication | null; bridge: RoleFormBridge
  onSaved: (id: number) => void; sponsorConsent?: ReactNode; completionReady?: boolean
}

export function RoleApplicationForm(props: Props) {
  const { scope, posting, application } = props
  return <FormContent key={`${scope.accountId}:${scope.makerspaceId}:${scope.eventId}:${posting.id}:${application?.id ?? 'new'}`} {...props} />
}

function FormContent({ scope, posting, application, bridge, onSaved, sponsorConsent, completionReady = false }: Props) {
  const [value, setValue] = useState<RoleFormValue | null>(null)
  const [prefillError, setPrefillError] = useState<unknown>(null)
  const command = useProgrammeCommand(scope, 'member')
  useEffect(() => {
    let active = true
    setValue(null); setPrefillError(null)
    void bridge.prefill({ scope, posting, application }).then(result => { if (active) setValue(result) })
      .catch(error => { if (active) setPrefillError(error) })
    return () => { active = false }
    // A successful revision refresh must not replace unsaved text. Remount this
    // form on a subject/account switch; an explicit reload accepts a new revision.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope.accountId, scope.eventId, scope.makerspaceId, posting.id, application?.id, bridge])
  const locked = Boolean(application && !application.allowed_actions.includes('edit'))
  const submit = (intent: 'draft' | 'submit') => {
    if (!value) return
    const path = application ? `/role-applications/${application.id}/${intent === 'submit' ? 'submit/' : ''}`
      : `/role-postings/${posting.id}/application/`
    command.mutate({ path, version: application?.version ?? 0,
      method: application && intent === 'draft' ? 'PATCH' : 'POST', fields: { ...value } },
    { onSuccess: row => onSaved(row.id) })
  }
  return <DetailLayout title={posting.title} state={prefillError ? { status: 'error', error: errorText(prefillError) }
    : value ? { status: 'ready' } : { status: 'loading' }}
    main={<div className="grid gap-6"><Card>
      <p className="mb-4 text-muted">{posting.description}</p>
      <p className="mb-4 text-sm text-muted">Only the answers you submit go to this event. Choose which details to save for your next registration.</p>
      {command.error ? <p role="alert" className="mb-4 text-danger">{errorText(command.error)}</p> : null}
      {application?.answer_review?.date_review_required && posting.form?.event_context ? <div className="mb-4">
        <p className="mb-2 text-sm">The event start date changed to {posting.form.event_context.as_of_date}. Review this date before submitting.</p>
        <ActionControl action={{ label: 'Confirm updated event date', pending: command.isPending,
          onClick: () => {
            const context = posting.form?.event_context
            if (!context) return
            command.mutate({ path: `/role-applications/${application.id}/date-review/`, version: application.version,
              fields: { event_date_revision: context.event_date_revision, reviewed_as_of_date: context.as_of_date } },
            { onSuccess: () => {
              setValue(previous => previous ? { ...previous, event_date_revision: context.event_date_revision,
                derivations: Object.fromEntries(Object.entries(previous.derivations).map(([key, item]) => [key,
                  { ...item, reviewed_event_date_revision: context.event_date_revision, reviewed_as_of_date: context.as_of_date }])) } : null)
              onSaved(application.id)
            } })
          } }} />
      </div> : null}
      {value ? <form onSubmit={event => { event.preventDefault(); submit(application ? 'submit' : 'draft') }}>
        {bridge.render({ value, onChange: setValue, disabled: locked || command.isPending,
          errors: command.error instanceof StructuredApiError ? command.error.body.fields : undefined })}
        {!locked ? <div className="mt-6 flex flex-wrap gap-3">
          <ActionControl primary action={{ label: application ? 'Submit application' : 'Save draft', pending: command.isPending,
            onClick: () => submit(application ? 'submit' : 'draft') }} />
          {application ? <ActionControl action={{ label: application.state === 'applied' ? 'Save changes' : 'Save draft', pending: command.isPending, onClick: () => submit('draft') }} /> : null}
        </div> : <p className="mt-4 text-sm text-muted">Your submitted answers are locked.</p>}
      </form> : null}
      {application?.save_intent ? <div className="mt-4" role="status">{bridge.savedDetailsStatus(application.save_intent)}</div> : null}
      {application ? <RoleOwnerActions scope={scope} row={application} completionReady={completionReady} onSaved={onSaved} /> : null}
    </Card>{sponsorConsent}</div>} />
}
