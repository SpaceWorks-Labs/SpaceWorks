// Prefix and pattern inputs with token chips, the first problem in plain words and three sample numbers,
// all updated as the person types. Used by the member-card numbering panel and the staff-card numbering.
import { t } from "@lingui/core/macro";

import { Field } from "../ui";
import { patternProblem, samplesOf } from "./numberPattern";

export function NumberPatternFields({ prefix, pattern, tokens, readOnly, onChange }: {
  prefix: string; pattern: string; tokens: readonly string[]; readOnly?: boolean;
  onChange: (next: { prefix: string; pattern: string }) => void;
}) {
  const problem = patternProblem(prefix, pattern, tokens);
  const samples = problem ? [] : samplesOf(prefix, pattern);
  return <div className="grid gap-3">
    <div className="grid gap-3 sm:grid-cols-[8rem_1fr]">
      <Field label={t`Prefix`} hint={t`2 to 6 capital letters or digits.`} error={problem?.field === "prefix" ? problem.message : undefined}>
        <input className="desk-input min-h-11 uppercase" value={prefix} maxLength={6} readOnly={readOnly}
          onChange={(event) => onChange({ prefix: event.target.value.toUpperCase(), pattern })} />
      </Field>
      <Field label={t`Pattern`} hint={t`Empty means no scheme.`} error={problem?.field === "pattern" ? problem.message : undefined}>
        <input className="desk-input min-h-11 uppercase" value={pattern} maxLength={40} readOnly={readOnly}
          onChange={(event) => onChange({ prefix, pattern: event.target.value.toUpperCase() })} />
      </Field>
    </div>
    {!readOnly ? <div className="flex flex-wrap gap-2" role="group" aria-label={t`Insert a token`}>
      {tokens.map((token) => <button key={token} type="button" className="desk-button-ghost min-h-11 font-mono text-xs"
        onClick={() => onChange({ prefix, pattern: `${pattern}${token}` })}>{token}</button>)}
    </div> : null}
    <p className="text-sm text-muted" aria-live="polite">
      {samples.length ? t`Next numbers: ${samples.join(", ")}` : problem ? t`Fix the pattern to see sample numbers.` : t`No scheme: numbers keep their default form.`}
    </p>
  </div>;
}
