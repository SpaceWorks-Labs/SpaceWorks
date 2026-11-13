import { t } from "@lingui/core/macro";
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Card, Field } from "../../../components/ui";
import { listPlans, membershipPlanKeys } from "../membershipPlansApi";
import { RefundPolicyCard } from "./RefundPolicyCard";
import { refundPolicyKey, removePlanPolicy, savePlanPolicy, type PolicyBody, type RefundPolicy } from "./refundsApi";

/**
 * The membership area: one default every plan follows, plus optional per-plan rules.
 * Cancelling a paid term opens a refund due for staff approval; dues and admission
 * charges have no term, so members can only ask for those.
 */
export function RefundMembershipPolicies({ makerspaceId, canEdit, defaultCard, planRules }: {
  makerspaceId: number; canEdit: boolean; defaultCard: ReactNode; planRules: RefundPolicy[];
}) {
  // Plan names come from the membership plans API, which needs the membership module;
  // without it the default rule still shows and per-plan rules are simply not offered.
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId),
    enabled: canEdit, retry: false });
  const [adding, setAdding] = useState<number | null>(null);
  const ruled = new Set(planRules.map((row) => row.plan));
  const available = (plans.data ?? []).filter((plan) => !ruled.has(plan.id));
  const currency = planRules[0]?.currency ?? "";
  const draft = adding === null ? null : available.find((plan) => plan.id === adding);
  return <Card>
    <div className="grid gap-4">
      <div className="grid gap-1">
        <h3 className="title-section">{t`Memberships`}</h3>
        <p className="text-sm text-muted">{t`Cancelling a paid membership term opens a refund for you to approve. Dues and joining fees have no term: members can ask, and you decide.`}</p>
      </div>
      {defaultCard}
      {planRules.map((rule) => <PlanCard key={rule.plan} makerspaceId={makerspaceId} policy={rule} canEdit={canEdit} />)}
      {draft ? <PlanCard key={`new-${draft.id}`} makerspaceId={makerspaceId} canEdit={canEdit} startEditing
        onCancel={() => setAdding(null)} onSaved={() => setAdding(null)}
        policy={{ area: "membership", plan: draft.id, plan_name: draft.name, configured: false,
          currency: currency || draft.currency, updated_at: "" }} /> : null}
      {canEdit && available.length && !draft ? <Field label={t`Add a rule for one plan`}>
        <select className="desk-input" value="" onChange={(event) => setAdding(Number(event.target.value))}>
          <option value="">{t`Choose a plan…`}</option>
          {available.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
        </select>
      </Field> : null}
    </div>
  </Card>;
}

function PlanCard({ makerspaceId, policy, canEdit, startEditing, onCancel, onSaved }: {
  makerspaceId: number; policy: RefundPolicy; canEdit: boolean; startEditing?: boolean;
  onCancel?: () => void; onSaved?: () => void;
}) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: refundPolicyKey(makerspaceId) });
  const planId = policy.plan as number;
  const save = useMutation({ mutationFn: (body: PolicyBody) => savePlanPolicy(makerspaceId, planId, body) });
  const remove = useMutation({ mutationFn: () => removePlanPolicy(makerspaceId, planId), onSuccess: refresh });
  return <RefundPolicyCard title={t`Plan: ${policy.plan_name}`} policy={policy} canEdit={canEdit}
    startEditing={startEditing} onCancel={onCancel}
    saving={save.isPending} removing={remove.isPending} saveError={save.error ?? remove.error}
    onSave={(body, done) => save.mutate(body, { onSuccess: () => { done(); onSaved?.(); void refresh(); } })}
    onRemove={() => remove.mutate()} />;
}
