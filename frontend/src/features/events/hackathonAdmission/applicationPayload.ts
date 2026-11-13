import { t } from "@lingui/core/macro";
import { memberFormInput } from '../../forms/conditions'
import { formSchema } from '../programme/formBridge'
import type { AdmissionSelection, Application, FormValue, ProgrammeContext } from './types'

export function applicationPayload(context: ProgrammeContext, application: Application, value: FormValue,
  selection: AdmissionSelection, cocAccepted: boolean, sharing: boolean, draft = false) {
  const schema = context.application_form
  if (!schema) throw new Error(t`Application form is unavailable.`)
  const admission = Object.fromEntries(Object.entries(selection).filter(([key, item]) => item !== undefined
    && (!['invite_code', 'promo_code'].includes(key) || (!draft && typeof item === 'string' && Boolean(item.trim())))))
  return { expected_version: application.version, event_date_revision: context.event.event_date_revision,
    ...(!Array.isArray(schema) ? { form: { schema_version: schema.schema_version, form_id: schema.form_id, revision: schema.revision } } : {}),
    ...(Array.isArray(schema) ? value : memberFormInput(formSchema(schema), value)), ...admission, coc: { revision: context.coc?.revision, accepted: cocAccepted },
    optional_consents: { mlh_data_sharing: sharing } }
}
