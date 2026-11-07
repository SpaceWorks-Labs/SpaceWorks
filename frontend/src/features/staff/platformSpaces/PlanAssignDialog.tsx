import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { useAssignPlan, usePlans, useSpacePlan } from "./plansApi";
import type { HealthCard } from "./spacesApi";

/** Assign a hosting plan (with an optional trial) or remove it; without a plan the fair-use defaults apply. */
export function PlanAssignDialog({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const plans = usePlans();
  const current = useSpacePlan(card.id);
  const assign = useAssignPlan(card.id);
  const [planId, setPlanId] = useState("");
  const [trial, setTrial] = useState("");
  const [removing, setRemoving] = useState(false);
  const chosen = planId || (current.data ? String(current.data.plan.id) : "");
  const trialDays = trial.trim() === "" ? null : Number(trial);
  const canSubmit = removing || (Boolean(chosen) && (trialDays === null || (Number.isInteger(trialDays) && trialDays >= 0)));
  const done = (message: string) => { toast(message); onClose(); };
  return <ActionDialog title={t`Plan for ${card.name}`} confirmLabel={removing ? t`Remove plan` : t`Save plan`} tone={removing ? "danger" : "default"}
    pending={assign.isPending} error={assign.error} canSubmit={canSubmit} onCancel={onClose}
    message={current.data ? t`Current plan: ${current.data.plan.name}${current.data.trial_ends_at ? `, trial until ${new Date(current.data.trial_ends_at).toLocaleDateString(formatLocale())}` : ""}.`
      : current.isLoading ? t`Loading the current plan…` : t`No plan assigned: the fair-use defaults apply.`}
    onSubmit={() => removing ? assign.mutate(null, { onSuccess: () => done("Plan removed.") })
      : assign.mutate({ plan_id: Number(chosen), trial_days: trialDays }, { onSuccess: () => done("Plan saved.") })}>
    {!removing ? <>
      <Field label={t`Plan`}>
        <select className="desk-input" value={chosen} onChange={event => setPlanId(event.target.value)}>
          <option value="">{t`Choose a plan`}</option>
          {(plans.data ?? []).filter(plan => plan.is_active || String(plan.id) === chosen).map(plan => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
        </select>
      </Field>
      <Field label={t`Trial days (optional)`} hint={t`Leave empty to use the plan's own trial length. 0 means no trial.`}>
        <input className="desk-input" type="number" min={0} inputMode="numeric" value={trial} onChange={event => setTrial(event.target.value)} />
      </Field>
    </> : <p className="text-sm text-ink">{t`The space falls back to the fair-use defaults.`}</p>}
    {current.data ? <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={removing} onChange={event => setRemoving(event.target.checked)} />{t`Remove the plan instead`}</label> : null}
  </ActionDialog>;
}
