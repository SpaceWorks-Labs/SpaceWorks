import { useQuery } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { listPlans, membershipPlanKeys, planErrorText } from "./membershipPlansApi";
import { formatMoney } from "./paymentsApi";
import { useStaffChargesOn } from "./useStaffChargesOn";

export function MembershipPlanPicker({ makerspaceId, value, onChange }: {
  makerspaceId: number; value: number | null; onChange: (id: number | null) => void;
}) {
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const active = plans.data?.filter((plan) => plan.is_active) ?? [];
  const chargesOn = useStaffChargesOn("membership", makerspaceId); // #184: free membership lists plans without prices
  return <div><Field label="Approval plan (optional)"><select className="desk-input max-w-full" value={value ?? ""} disabled={plans.isPending || plans.isError} onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}>
    <option value="">No plan</option>{active.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}{chargesOn ? ` · ${formatMoney(plan.amount, plan.currency)}` : ""}</option>)}
  </select></Field>
    {plans.isPending ? <p className="text-sm text-muted">Loading approval plans…</p> : null}
    {plans.isError ? <p role="alert" className="text-sm text-danger">{planErrorText(plans.error, "Unable to load plans.")}</p> : null}
    {plans.isSuccess && !active.length ? <p className="text-sm text-muted">No active plans. Approval can continue without a plan.</p> : null}
  </div>;
}
