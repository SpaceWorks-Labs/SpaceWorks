import { t } from "@lingui/core/macro";
import { useState } from "react";
import { DetailDrawer, ErrorText, ListRow, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import type { HealthCard } from "../platformSpaces/spacesApi";
import { useCapabilityPlans, usePurgeCapability, type CapabilityPlan } from "./spaceKeysApi";
import { TypedConfirmDialog } from "./TypedConfirmDialog";
import { LogoLoader } from "../../../components/LogoLoader";

const total = (plan: CapabilityPlan) => Object.values(plan.counts).reduce((sum, count) => sum + count, 0);
// What a purge preview counts (backend makerspaces/capability_purge_plans*.py), as people read it.
const COUNT_NAMES = (): Record<string, string> => ({
  actions: t`Actions`, amendments: t`Amendments`, calendar_feeds: t`Calendar feeds`, card_designs: t`Card designs`,
  dispatches: t`Dispatches`, documents: t`Documents`, downtime_periods: t`Downtime periods`, event_id_cards: t`Event ID cards`,
  guest_certifications: t`Guest certifications`, id_programmes: t`ID programmes`, incidents: t`Incidents`,
  induction_links: t`Induction links`, inventory: t`Inventory`, issues: t`Issues`, logs: t`Logs`,
  organization_hours_banks: t`Organization hour banks`, organization_hours_ledger_rows: t`Organization hour entries`,
  organization_links: t`Organization links`, photos: t`Photos`, programme_cards: t`Programme cards`, receipts: t`Receipts`,
  rooms: t`Rooms`, schedules: t`Schedules`, sessions: t`Sessions`, supervised_sessions: t`Supervised sessions`,
  supervisees: t`Supervisees`, to_buy_items: t`To-buy items`, uses: t`Uses`, warranties: t`Warranties`, work_orders: t`Work orders`,
});
const counts = (plan: CapabilityPlan) => {
  const names = COUNT_NAMES();
  return Object.entries(plan.counts).map(([name, count]) => `${names[name] ?? name.replace(/_/g, " ")}: ${count}`).join(" · ");
};

/** Delete a switched-off capability's data for good: a preview of every row first, the key typed back, then a fresh sign-in. */
export function CapabilityPurgeDrawer({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const plans = useCapabilityPlans(card.id);
  const purge = usePurgeCapability(card.id);
  const [chosen, setChosen] = useState<CapabilityPlan | null>(null);
  return <DetailDrawer open title={t`Feature data of ${card.name}`} onClose={onClose}>
    <div className="grid gap-4">
      <p className="text-sm text-muted">{t`Switching a feature off keeps its data, and switching it back on restores everything. Purging deletes that data for good. It is recorded in this space's audit log, which its managers can read.`}</p>
      {plans.isLoading ? <LogoLoader size={48} className="min-h-40 py-3" /> : plans.isError || !plans.data
        ? <ErrorText resource={t`capability data`} onRetry={() => { void plans.refetch(); }} />
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
