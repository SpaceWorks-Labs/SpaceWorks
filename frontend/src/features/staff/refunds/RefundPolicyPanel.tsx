import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Callout } from "../../../components/ui";
import { RefundPolicyCard } from "./RefundPolicyCard";
import { RefundMembershipPolicies } from "./RefundMembershipPolicies";
import {
  listRefundPolicies, refundPolicyKey, removeRefundPolicy, saveRefundPolicy, type PolicyBody, type RefundPolicy,
} from "./refundsApi";

const AREA_TITLES: Record<RefundPolicy["area"], string> = { events: "Events", bookings: "Bookings", membership: "Memberships" };

/** Read-only for anyone without manage_makerspace; the API enforces it either way. */
export function RefundPolicyPanel({ makerspaceId, canEdit }: { makerspaceId: number; canEdit: boolean }) {
  const policies = useQuery({ queryKey: refundPolicyKey(makerspaceId), queryFn: () => listRefundPolicies(makerspaceId) });
  if (policies.isLoading) return <p className="text-sm text-muted" role="status">Loading refund policy…</p>;
  if (policies.error || !policies.data) return <Callout size="inline" tone="danger" lead="Couldn't load the refund policy."
    body="Try again in a moment." />;
  const defaults = policies.data.filter((row) => row.plan === null);
  const timed = defaults.filter((row) => row.area !== "membership");
  const membership = defaults.find((row) => row.area === "membership");
  return <div className="grid gap-4">
    {timed.map((policy) => <AreaCard key={policy.area} makerspaceId={makerspaceId} policy={policy} canEdit={canEdit} />)}
    {membership ? <RefundMembershipPolicies makerspaceId={makerspaceId} canEdit={canEdit}
      defaultCard={<AreaCard makerspaceId={makerspaceId} policy={membership} canEdit={canEdit} title="All plans" />}
      planRules={policies.data.filter((row) => row.plan !== null)} /> : null}
  </div>;
}

function AreaCard({ makerspaceId, policy, canEdit, title }: {
  makerspaceId: number; policy: RefundPolicy; canEdit: boolean; title?: string;
}) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: refundPolicyKey(makerspaceId) });
  const save = useMutation({ mutationFn: (body: PolicyBody) => saveRefundPolicy(makerspaceId, policy.area, body) });
  const remove = useMutation({ mutationFn: () => removeRefundPolicy(makerspaceId, policy.area), onSuccess: refresh });
  return <RefundPolicyCard title={title ?? AREA_TITLES[policy.area]} policy={policy} canEdit={canEdit}
    saving={save.isPending} removing={remove.isPending} saveError={save.error ?? remove.error}
    onSave={(body, done) => save.mutate(body, { onSuccess: () => { done(); void refresh(); } })}
    onRemove={() => remove.mutate()} />;
}
