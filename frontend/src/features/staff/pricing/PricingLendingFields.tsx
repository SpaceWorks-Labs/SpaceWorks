import { t } from "@lingui/core/macro";
import { Field } from "../../../components/ui";
import type { DraftProblems, LendingDraft } from "./pricingDraft";

const DEPOSIT_MODES: [LendingDraft["deposit_mode"], string][] = [
  ["none", "No deposit"], ["fixed", "Fixed amount per loan"], ["per_product", "Each item's own deposit"],
];

/** The lending block: deposit and late fee (stored on the same columns the old loan settings edited). */
export function PricingLendingFields({ lending, currency, problems, disabled, onChange }: {
  lending: LendingDraft; currency: string; problems: DraftProblems; disabled: boolean;
  onChange: (patch: Partial<LendingDraft>) => void;
}) {
  const code = currency.toUpperCase();
  return <fieldset className="grid gap-3 rounded-xl border border-line bg-surface p-4">
    <legend className="px-1 font-semibold text-ink">{t`Deposit and late fee`}</legend>
    <p className="text-xs text-muted">{t`Deposits are refundable and never discounted. Late fees start once a loan is overdue and the grace days have passed.`}</p>
    <div className="@container grid gap-3 sm:grid-cols-2">
      <Field label={t`Deposit`}>
        <select className="desk-input" value={lending.deposit_mode} disabled={disabled}
          onChange={event => onChange({ deposit_mode: event.target.value as LendingDraft["deposit_mode"] })}>
          {DEPOSIT_MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </Field>
      {lending.deposit_mode === "fixed" ? <Field label={t`Deposit amount (${code})`} error={problems["lending.deposit_amount"]}>
        <input className="desk-input" inputMode="decimal" value={lending.deposit_amount} disabled={disabled}
          onChange={event => onChange({ deposit_amount: event.target.value })} />
      </Field> : null}
      <Field label={t`Late fee per day (${code})`} error={problems["lending.late_per_day"]}>
        <input className="desk-input" inputMode="decimal" value={lending.late_per_day} disabled={disabled}
          onChange={event => onChange({ late_per_day: event.target.value })} />
      </Field>
      <Field label={t`Late fee cap (${code})`} hint={t`0 means no cap.`} error={problems["lending.late_cap"]}>
        <input className="desk-input" inputMode="decimal" value={lending.late_cap} disabled={disabled}
          onChange={event => onChange({ late_cap: event.target.value })} />
      </Field>
      <Field label={t`Grace days`} hint={t`Days past the due date before late fees start.`} error={problems["lending.grace_days"]}>
        <input className="desk-input" inputMode="numeric" value={lending.grace_days} disabled={disabled}
          onChange={event => onChange({ grace_days: event.target.value })} />
      </Field>
    </div>
    <label className="flex min-h-11 items-start gap-3 text-sm text-ink">
      <input className="mt-1 h-4 w-4" type="checkbox" checked={lending.deposit_blocks_issue}
        disabled={disabled || lending.deposit_mode === "none"}
        onChange={event => onChange({ deposit_blocks_issue: event.target.checked })} />
      <span><span className="font-semibold">{t`Deposit blocks issue`}</span>
        <span className="block text-xs text-muted">{t`Staff cannot hand over a loan until its deposit is paid.`}</span></span>
    </label>
  </fieldset>;
}
