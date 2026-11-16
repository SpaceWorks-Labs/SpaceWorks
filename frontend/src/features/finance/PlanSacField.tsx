import { t } from "@lingui/core/macro";

import { Field } from "../../components/ui";

/** Mirrors `payments/tax/plan_sac.validate_plan_sac`: blank, or 4 to 8 digits. */
export function validatePlanSac(value: string): string | null {
  const code = value.trim();
  return code && !/^\d{4,8}$/.test(code) ? t`A SAC code is 4 to 8 digits, or leave it blank.` : null;
}

/** True while a plan may carry its own SAC (`billing.plan_sac`, which needs `billing.tax`). */
export function planSacOn(features: string[]): boolean {
  return features.includes("billing.plan_sac") && features.includes("billing.tax");
}

/**
 * Parity O-B3: a membership plan's own SAC code for GST invoices. Frozen on each charge when it is raised, so
 * editing it never changes an invoice already issued.
 */
export function PlanSacField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const problem = value.trim() ? validatePlanSac(value) : null;
  return <Field label={t`SAC code (optional)`} error={problem ?? undefined}
    hint={t`4 to 8 digits printed on this plan's GST invoices. Leave blank to use the space-wide SAC code from Tax settings. Charges already raised keep the code they had.`}>
    <input className="desk-input tabular-nums" inputMode="numeric" maxLength={8} value={value} placeholder="999599"
      onChange={(event) => onChange(event.target.value.replace(/\s/g, ""))} />
  </Field>;
}
