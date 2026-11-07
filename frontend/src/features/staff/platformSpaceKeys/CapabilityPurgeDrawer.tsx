import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DetailDrawer, ErrorText, ListRow, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import type { HealthCard } from "../platformSpaces/spacesApi";
import { useCapabilityPlans, usePurgeCapability, type CapabilityPlan } from "./spaceKeysApi";
import { TypedConfirmDialog } from "./TypedConfirmDialog";

const total = (plan: CapabilityPlan) => Object.values(plan.counts).reduce((sum, count) => sum + count, 0);
const counts = (plan: CapabilityPlan) => Object.entries(plan.counts).map(([name, count]) => `${name.replace(/_/g, " ")}: ${count}`).join(" · ");

/** Delete a switched-off capability's data for good: a preview of every row first, the key typed back, then a fresh sign-in. */
export function CapabilityPurgeDrawer({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const plans = useCapabilityPlans(card.id);
  const purge = usePurgeCapability(card.id);
  const [chosen, setChosen] = useState<CapabilityPlan | null>(null);
  return <DetailDrawer open title={t`Capability data of ${card.name}`} onClose={onClose}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`Switching a capability off keeps its data, and switching it back on restores everything. Purging deletes that data for good. It is recorded in this space's audit log, which its managers can read.`}</p>
      {plans.isLoading ? <Skeleton className="h-40 w-full" /> : plans.isError || !plans.data
        ? <ErrorText resource="capability data" onRetry={() => { void plans.refetch(); }} />
        : <div className="grid gap-2">{plans.data.map(plan => <ListRow key={plan.key} title={plan.key}
          meta={<>{plan.summary}<br />{counts(plan) || t`Nothing stored.`}</>}
          right={plan.switched_on ? <StatusPill label={t`Switched on`} tone="neutral" />
            : <button type="button" className="desk-button-danger-outline" disabled={!total(plan)}
              aria-label={t`Purge ${plan.key} data`} onClick={() => { purge.reset(); setChosen(plan); }}>{t`Purge…`}</button>} />)}
        </div>}
    </div>
    {chosen ? <TypedConfirmDialog title={t`Purge ${chosen.key} data`} confirmLabel={t`Purge for good`} expected={chosen.key}
      what="capability key" pending={purge.isPending} error={purge.error} onCancel={() => setChosen(null)}
      message={<>{t`This deletes, at ${card.name}: ${counts(chosen)}. It cannot be undone.`}</>}
      onConfirm={typed => purge.mutate({ key: chosen.key, confirm: typed },
        { onSuccess: () => { toast(t`${chosen.key} data purged.`); setChosen(null); } })} /> : null}
  </DetailDrawer>;
}
