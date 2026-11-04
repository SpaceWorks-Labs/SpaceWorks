import { Field } from "../../../components/ui";
import { formatMoney } from "../paymentsApi";
import { UNIT_WORDING, type PricingDefault } from "./pricingApi";
import type { DraftProblems, LineDraft } from "./pricingDraft";

type Props = {
  card: PricingDefault;
  lines: LineDraft[];
  problems: DraftProblems;
  disabled: boolean;
  onChange: (component: string, patch: Partial<LineDraft>) => void;
};

function lineNote(spec: PricingDefault["lines"][number]) {
  if (spec.staff_set) return "Suggested default; staff set the actual charge at return.";
  if (spec.prefill_only) return "Prefills new events only; published events keep their own price.";
  if (!spec.discountable) return "Member discounts never touch this unless a discount names it.";
  return undefined;
}

/** One block per price component: the amount, plus cap / grace / increment / minimum when it takes them. */
export function PricingRateRows({ card, lines, problems, disabled, onChange }: Props) {
  return <ul className="grid gap-3" aria-label={`${card.label} rates`}>
    {card.lines.map(spec => {
      const line = lines.find(row => row.component === spec.component);
      if (!line) return null;
      const unit = UNIT_WORDING[spec.unit] ?? spec.unit;
      const key = `line.${spec.component}`;
      if (spec.read_only) {
        return <li key={spec.component} className="rounded-xl border border-line bg-surface p-4">
          <p className="font-semibold text-ink">{spec.label}</p>
          <p className="text-sm text-ink">{Number(spec.amount) > 0 ? `${formatMoney(spec.amount, card.currency)} ${unit}` : "Not charged"}</p>
          <p className="mt-1 text-xs text-muted">Set on each membership plan; plans own their prices.</p>
        </li>;
      }
      const note = lineNote(spec);
      return <li key={spec.component} className="grid gap-3 rounded-xl border border-line bg-surface p-4">
        <div>
          <p className="font-semibold text-ink">{spec.label} <span className="font-normal text-muted">{unit}</span></p>
          {note ? <p className="text-xs text-muted">{note}</p> : null}
        </div>
        <div className="@container grid gap-3 sm:grid-cols-2">
          <Field label={`${spec.label} amount (${card.currency.toUpperCase()})`} error={problems[`${key}.amount`]}>
            <input className="desk-input" inputMode="decimal" value={line.amount} disabled={disabled}
              onChange={event => onChange(spec.component, { amount: event.target.value })} />
          </Field>
          {spec.has_cap ? <Field label={`${spec.label} cap`} hint="The most this can add up to. Empty means no cap."
            error={problems[`${key}.cap`]}>
            <input className="desk-input" inputMode="decimal" value={line.cap} disabled={disabled}
              onChange={event => onChange(spec.component, { cap: event.target.value })} />
          </Field> : null}
          {spec.has_grace ? <Field label={`${spec.label} grace (days)`} error={problems[`${key}.grace_units`]}>
            <input className="desk-input" inputMode="numeric" value={line.grace_units} disabled={disabled}
              onChange={event => onChange(spec.component, { grace_units: event.target.value })} />
          </Field> : null}
          {spec.has_increment ? <Field label={`${spec.label} billing increment (minutes)`} hint="Time is rounded up to this step. 0 bills to the minute."
            error={problems[`${key}.billing_increment`]}>
            <input className="desk-input" inputMode="numeric" value={line.billing_increment} disabled={disabled}
              onChange={event => onChange(spec.component, { billing_increment: event.target.value })} />
          </Field> : null}
          {spec.has_minimum ? <Field label={`${spec.label} minimum (minutes)`} hint="Shorter jobs are billed as this many minutes."
            error={problems[`${key}.minimum`]}>
            <input className="desk-input" inputMode="numeric" value={line.minimum} disabled={disabled}
              onChange={event => onChange(spec.component, { minimum: event.target.value })} />
          </Field> : null}
        </div>
      </li>;
    })}
  </ul>;
}
