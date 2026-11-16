import { t } from "@lingui/core/macro";
import { FormV2Fields } from "../../forms/FormV2Fields";
import { Field } from "../../../components/ui/Field";
import type { FormState } from "../../forms/types";
import type { RequestContext } from "./types";

/** G/A embed this step in the canonical registration/application submit. */
export function ReimbursementRequestFields({ context, value, onChange, distance, onDistanceChange, consent, onConsentChange }: {
  context: RequestContext; value: FormState; onChange: (value: FormState) => void; distance: string;
  onDistanceChange: (value: string) => void; consent: boolean; onConsentChange: (value: boolean) => void;
}) {
  return <section className="grid gap-5" aria-label={t`Travel support request`}><p className="text-sm text-muted">{t`Requesting support does not confirm your place or guarantee an award. Keep estimates in ${context.currency}.`}</p>
    <FormV2Fields schema={context.schema} value={value} onChange={onChange} />
    <Field label={t`Self-reported travel distance (km)`} hint={context.min_distance_km === null ? t`Optional. This is not verified evidence.` : t`Required. Programme minimum: ${context.min_distance_km} km.`}>
      <input className="desk-input" inputMode="decimal" required={context.min_distance_km !== null} value={distance} onChange={event => onDistanceChange(event.target.value)} /></Field>
    <label className="flex min-h-11 items-start gap-3"><input type="checkbox" required checked={consent} onChange={event => onConsentChange(event.target.checked)} />
      <span>{t`I choose to submit this travel support request with these estimates and details.`}</span></label>
  </section>;
}
