import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useId, useState } from "react";

import { ErrorText } from "../../components/ui";

/** Hand-typed until the integrator regenerates the OpenAPI client. */
export type DepartureOutcome = "all_good" | "issue" | "damaged" | "left_early";
export type DepartureInput = { outcome: DepartureOutcome; remark: string };
export type BookingDeparture = { outcome: DepartureOutcome; remark: string; source: "staff" | "member"; recorded_at: string; recorded_by: string };

export const OUTCOME_LABELS: Record<DepartureOutcome, string> = {
  all_good: t`All good`,
  issue: t`Something was wrong`,
  damaged: t`Something was damaged`,
  left_early: t`Left early`,
};

/**
 * The typed leave remark ("how did it go?") shared by staff check-out and member check-out.
 * Anything but "All good" needs a remark, which staff follow up as an issue.
 */
export function DepartureForm({ onSubmit, pending = false, error, submitLabel = t`Record check-out`, audience }: {
  onSubmit: (input: DepartureInput) => void;
  pending?: boolean;
  error?: string;
  submitLabel?: string;
  /** Wording: a member reports on their own visit, staff report on someone else's. */
  audience: "staff" | "member";
}) {
  const id = useId();
  const [outcome, setOutcome] = useState<DepartureOutcome>("all_good");
  const [remark, setRemark] = useState("");
  const [touched, setTouched] = useState(false);
  const needsRemark = outcome !== "all_good";
  const missing = needsRemark && !remark.trim();
  return (
    <form className="grid gap-3" aria-labelledby={`${id}-legend`} noValidate
      onSubmit={event => { event.preventDefault(); setTouched(true); if (!missing) onSubmit({ outcome, remark: remark.trim() }); }}>
      <fieldset className="grid gap-2">
        <legend id={`${id}-legend`} className="text-sm font-semibold">
          {audience === "member" ? t`How did your booking go?` : t`How did this booking go?`}
        </legend>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-labelledby={`${id}-legend`}>
          {(Object.keys(OUTCOME_LABELS) as DepartureOutcome[]).map(value => (
            <label key={value} className={`flex min-h-11 cursor-pointer items-center gap-2 rounded-control border px-3 text-sm ${outcome === value ? "border-brand bg-brand-soft font-semibold" : "border-line"}`}>
              <input type="radio" name={`${id}-outcome`} value={value} checked={outcome === value} onChange={() => setOutcome(value)} />
              {OUTCOME_LABELS[value]}
            </label>
          ))}
        </div>
      </fieldset>
      <label htmlFor={`${id}-remark`} className="grid gap-1 text-sm">
        <span>{t`Remark${needsRemark ? " (required)" : " (optional)"}`}</span>
        <textarea id={`${id}-remark`} className="desk-input min-h-24" maxLength={2000} value={remark}
          aria-invalid={touched && missing} aria-describedby={touched && missing ? `${id}-hint` : undefined}
          placeholder={needsRemark ? t`What was wrong? Staff will follow up.` : t`Anything staff should know?`}
          onChange={event => setRemark(event.target.value)} />
      </label>
      {touched && missing ? <p id={`${id}-hint`} className="text-sm text-danger">{t`Describe what was wrong so staff can follow up.`}</p> : null}
      <ErrorText message={error} />
      <div><button type="submit" className="desk-button-brand min-h-11" disabled={pending}>{pending ? t`Saving…` : submitLabel}</button></div>
    </form>
  );
}

export function DepartureSummary({ departure }: { departure: BookingDeparture }) {
  return (
    <p className="text-sm">
      <span className="font-semibold">{OUTCOME_LABELS[departure.outcome]}</span>
      {" · "}{departure.source === "member" ? t`reported by the booker` : t`recorded by ${departure.recorded_by}`}
      {" · "}{new Date(departure.recorded_at).toLocaleString(formatLocale())}
      {departure.remark ? <span className="mt-1 block whitespace-pre-wrap text-muted">“{departure.remark}”</span> : null}
    </p>
  );
}
