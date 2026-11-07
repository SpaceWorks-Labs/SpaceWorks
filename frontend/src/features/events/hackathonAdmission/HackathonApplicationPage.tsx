import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { CenteredCardLayout } from '../../../components/layouts'
import { ApplicationEditor } from './ApplicationEditor'
import { ApplicationStatus } from './ApplicationStatus'
import { AdmissionArtwork } from './AdmissionArtwork'
import { useAdmission } from './useAdmission'
import type { FormFields } from './types'
import type { RsvpInput } from '../../../generated/api'

/** G mounts inside AppShell and supplies F's versioned form renderer. */
export function HackathonApplicationPage({ publicToken, accountId, Fields, onSignIn, onOrdinaryRegister }: {
  publicToken: string; accountId: number; Fields: FormFields; onSignIn: () => void; onOrdinaryRegister: (context: import('./types').ProgrammeContext) => void
}) {
  const { context, application, prefill, mutation } = useAdmission(publicToken, accountId)
  const [editing, setEditing] = useState(false)
  if (!accountId) return <CenteredCardLayout standalone={false} eyebrow={t`Space Works`} title={t`Sign in to apply`}
    state={{ status: 'ready' }} body={t`Your application belongs to your member account. A makerspace membership is not required for account events.`}
    primary={{ label: t`Sign in`, onClick: onSignIn }} />
  const current = context.data, row = application.data
  const error = context.error || application.error
  if (error || !current || (!row && current.routes.application)) return <CenteredCardLayout standalone={false} title={t`Event application`}
    state={error ? { status: 'error', error: error.message, onRetry: () => { void context.refetch(); void application.refetch() } } : { status: 'loading' }}
    body={t`Load the event to review its current requirements.`} primary={{ label: t`Refresh event`, onClick: () => { void context.refetch() } }} content={<AdmissionArtwork kind="applications" />} />
  if (!current.eligibility.eligible) return <CenteredCardLayout standalone={false} title={t`Application requirements`}
    state={{ status: 'ready' }} body={t`This account does not currently meet the event's admission requirements.`} primary={{ label: t`Back to event`, onClick: () => window.history.back() }} />
  if (current.programme.kind === 'ordinary' || !row) return <CenteredCardLayout standalone={false} title={t`Event registration`}
    state={{ status: 'ready' }} body={t`This event uses ordinary registration.`} primary={{ label: t`Continue registration`, onClick: () => onOrdinaryRegister(current) }} />
  if (row.state === 'draft' || (editing && row.allowed_actions.includes('edit'))) return <ApplicationEditor context={current} application={row} Fields={Fields} prefill={prefill.data}
    pending={mutation.isPending} error={mutation.error} onSave={(body, draft) => mutation.mutateAsync({
      route: draft ? 'application' : 'application_submit', method: draft ? 'PATCH' : 'POST', body }).then(saved => { setEditing(false); return saved })} />
  return <ApplicationStatus application={row} pending={mutation.isPending} error={mutation.error}
    onDateReview={body => mutation.mutate({ route: 'application_date_review', body })}
    onRepair={body => mutation.mutate({ route: 'application_submit', body })}
    onReapply={() => { if (row.state === 'submitted') { setEditing(true); return }; mutation.mutate({ route: 'application', method: 'PATCH', body: { expected_version: row.version,
      event_date_revision: current.event.event_date_revision, answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {},
      ...(current.application_form && !Array.isArray(current.application_form) ? { form: { schema_version: 2,
        form_id: current.application_form.form_id, revision: current.application_form.revision } } : {}) } }) }}
    onAction={action => {
      // CommandSession supplies operation_id; RSVP has its own closed payload.
      const body = action === 'withdraw' ? { expected_version: row.version, reason_code: 'participant_withdrew' }
        : ({ expected_version: row.version, decision: action } satisfies Pick<RsvpInput, 'expected_version' | 'decision'>)
      mutation.mutate({ route: action === 'withdraw' ? 'application_withdraw' : 'application_rsvp', body })
    }} />
}
