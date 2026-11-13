import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { listPlans, membershipPlanKeys, planErrorText } from "./membershipPlansApi";
import { formatMoney } from "./paymentsApi";
import { useStaffChargesOn } from "./useStaffChargesOn";
import { LogoLoader } from "../../components/LogoLoader";

export function MembershipPlanPicker({ makerspaceId, value, onChange }: {
  makerspaceId: number; value: number | null; onChange: (id: number | null) => void;
}) {
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const active = plans.data?.filter((plan) => plan.is_active) ?? [];
  const chargesOn = useStaffChargesOn("membership", makerspaceId); // #184: free membership lists plans without prices
  return <div><Field label={t`Approval plan (optional)`}><select className="desk-input max-w-full" value={value ?? ""} disabled={plans.isPending || plans.isError} onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}>
    <option value="">{t`No plan`}</option>{active.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}{chargesOn ? ` · ${formatMoney(plan.amount, plan.currency)}` : ""}</option>)}
  </select></Field>
    {plans.isPending ? <LogoLoader label={t`Loading approval plans…`} size={48} className="min-h-16 py-3" /> : null}
    {plans.isError ? <p role="alert" className="text-sm text-danger">{planErrorText(plans.error, "Unable to load plans.")}</p> : null}
    {plans.isSuccess && !active.length ? <p className="text-sm text-muted">{t`No active plans. Approval can continue without a plan.`}</p> : null}
  </div>;
}
