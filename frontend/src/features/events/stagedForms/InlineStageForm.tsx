import { t } from "@lingui/core/macro";
import { useEffect } from "react";
import { FormV2Fields } from "../../forms/FormV2Fields";
import type { FormSchemaV2, FormState } from "../../forms/types";
import { useRegistrationSavedDetails } from "../../accountSavedDetails/RegistrationSavedDetails";
import { applyStageSuggestions } from "./formPayload";
import { useFormUploads } from "./uploads";
import { stagePath } from "./api";
import type { StageScope } from "./types";
import { LogoLoader } from "../../../components/LogoLoader";

export type InlineStageContext = { stage_form_id: number; title: string; schema: FormSchemaV2; form_revision_id: number;
  event_date_revision: number; creation_operation_id: string };
/** The canonical form owns state and the outer submission, including per-form intent notices. */
export function InlineStageForm({ scope, context, value, onChange, onBusyChange, disabled = false }: {
  scope: StageScope; context: InlineStageContext; value: FormState; onChange: (value: FormState) => void;
  onBusyChange: (busy: boolean) => void; disabled?: boolean;
}) {
  const prefill = useRegistrationSavedDetails(scope.actorId, { context: { subject_kind: "stage_response", stage_form_id: context.stage_form_id,
    event_id: scope.eventId, makerspace_id: scope.makerspaceId, creation_operation_id: context.creation_operation_id },
    form_id: context.schema.form_id, form_revision: context.schema.revision, event_date_revision: context.event_date_revision });
  const uploads = useFormUploads(`${stagePath(scope)}/stage-forms/${context.stage_form_id}/files/`, {
    creation_operation_id: context.creation_operation_id, form_revision_id: context.form_revision_id });
  useEffect(() => { onBusyChange(uploads.busy); return () => onBusyChange(false); }, [uploads.busy, onBusyChange]);
  return <section className="grid gap-4" aria-label={context.title}><h2 className="title-section">{context.title}</h2>
    <p className="text-sm text-muted">{t`This form is submitted with your application. Review saved suggestions and choose separately whether to save sensitive details.`}</p>
    {prefill.data ? <button type="button" className="desk-button justify-self-start" disabled={disabled || uploads.busy} onClick={() => onChange(applyStageSuggestions(context.schema, value, prefill.data!))}>{t`Use saved details for empty answers`}</button> : prefill.error ? <p role="status">{t`Saved suggestions are unavailable. You can complete this form yourself.`}</p> : <LogoLoader label={t`Loading saved suggestions…`} size={48} className="min-h-16 py-3" />}
    <fieldset disabled={disabled} className="min-w-0"><legend className="sr-only">{context.title} answers</legend><FormV2Fields context="stage" schema={context.schema} value={value} onChange={onChange} uploadFiles={uploads.upload} /></fieldset>
  </section>;
}
