import { t } from "@lingui/core/macro";
import { useState } from "react";
import { EmptyState, ErrorText, ListRow, Skeleton, StatusPill } from "../../../components/ui";
import { PlanForm } from "./PlanForm";
import { formatMoney, usePlans, type HostingPlan } from "./plansApi";

function summary(plan: HostingPlan) {
  const price = plan.billing_period === "none" ? "No recurring bill" : `${formatMoney(plan.price_minor, plan.currency)} ${plan.billing_period === "yearly" ? "a year" : "a month"}`;
  const trial = plan.trial_days ? ` · ${plan.trial_days}-day trial` : "";
  const spaces = ` · ${plan.space_count} ${plan.space_count === 1 ? "space" : "spaces"}`;
  return price + trial + spaces;
}

/** Hosting plans: the limits and price a managed space runs under. Assign one from a space's Manage menu. */
export function PlansSection() {
  const plans = usePlans();
  const [editing, setEditing] = useState<HostingPlan | "new" | null>(null);
  if (editing) return <PlanForm plan={editing === "new" ? undefined : editing} onDone={() => setEditing(null)} />;
  return <div className="grid gap-4">
    <button type="button" className="desk-button-primary w-full sm:w-fit" onClick={() => setEditing("new")}>{t`New plan`}</button>
    {plans.isLoading ? <Skeleton className="h-24 w-full" />
      : plans.isError ? <ErrorText resource="hosting plans" onRetry={() => { void plans.refetch(); }} />
      : !plans.data?.length ? <EmptyState message={t`No plans yet. Without a plan, spaces run under the fair-use defaults.`} />
      : <div className="grid gap-3">{plans.data.map(plan => <ListRow key={plan.id} title={plan.name} meta={summary(plan)}
        right={<div className="flex flex-wrap items-center gap-2">
          {!plan.is_active ? <StatusPill label={t`Retired`} /> : null}
          <button type="button" className="desk-button" aria-label={t`Edit ${plan.name}`} onClick={() => setEditing(plan)}>{t`Edit`}</button>
        </div>} />)}</div>}
  </div>;
}
