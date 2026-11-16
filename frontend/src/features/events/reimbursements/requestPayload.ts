import { t } from "@lingui/core/macro";
import type { FormState, ItineraryValue, MoneyValue } from "../../forms/types";
import type { RequestContext, RequestSubmission } from "./types";
export function requestPayload(context: RequestContext, state: FormState, consent: boolean, distance: string): RequestSubmission {
  if (!consent) throw new Error(t`Choose whether to submit a travel support request.`);
  const estimates = context.allowed_categories.flatMap(category => {
    const value = state.answers[`estimate_${category}`] as MoneyValue | undefined;
    if (!value || value.amount_minor === 0) return [];
    if (!Number.isSafeInteger(value.amount_minor) || value.amount_minor < 1 || value.currency !== context.currency) throw new Error(t`Enter positive estimates in the programme currency.`);
    return [{ category, amount_minor: value.amount_minor, currency: value.currency }];
  });
  const total = estimates.reduce((sum, row) => sum + row.amount_minor, 0);
  if (!estimates.length || !Number.isSafeInteger(total) || total > 9000000000000000) throw new Error(t`Enter at least one estimate within the supported amount range.`);
  const itinerary = state.answers.itinerary as ItineraryValue | undefined;
  const need = state.answers.need_statement;
  if (!itinerary?.mode || typeof need !== "string" || !need.trim() || need.trim().length > 5000) throw new Error(t`Complete your journey and support statement.`);
  if ((distance || context.min_distance_km !== null) && (!/^(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,3})?$/.test(distance) || Number(distance) > 40075)) throw new Error(t`Enter a distance from 0 to 40075 km, with up to three decimal places.`);
  return { submit: true, programme_id: context.programme_id, programme_version: context.programme_version,
    form: { schema_version: 2, form_id: context.schema.form_id, revision: context.schema.revision }, estimates,
    itinerary, need_statement: need.trim(), ...(distance ? { distance_km: distance } : {}) };
}
export function requestState(submission?: RequestSubmission): FormState {
  return { answers: submission ? { ...Object.fromEntries(submission.estimates.map(row => [`estimate_${row.category}`, { amount_minor: row.amount_minor, currency: row.currency }])),
    itinerary: submission.itinerary, need_statement: submission.need_statement } : {}, derivations: {}, save_choices: {}, saved_detail_versions: {} };
}
