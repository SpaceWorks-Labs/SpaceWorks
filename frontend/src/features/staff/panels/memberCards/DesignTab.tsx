// Card design: the space default plus per-plan and per-title overrides (a title beats a plan,
// a plan beats the default). Each opens in the free designer.
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CardDesigner } from "../../../../components/card-designer/CardDesigner";
import { ErrorBlock, Skeleton } from "../../../../components/ui";
import { listPlans } from "../../membershipPlansApi";
import { lifecycleApi, lifecycleKeys } from "../../membershipLifecycleApi";
import { useCreateCardOverride, useMemberCardDesigns } from "./apiCards";

export function DesignTab({ makerspaceId }: { makerspaceId: number }) {
  const designs = useMemberCardDesigns(makerspaceId);
  const plans = useQuery({ queryKey: ["membership-plans", makerspaceId, "card-designs"], queryFn: () => listPlans(makerspaceId) });
  const titles = useQuery({ queryKey: lifecycleKeys.titles(makerspaceId), queryFn: () => lifecycleApi.titles(makerspaceId) });
  const create = useCreateCardOverride(makerspaceId);
  const [chosen, setChosen] = useState<number | null>(null);
  const [target, setTarget] = useState("");
  if (designs.isLoading) return <Skeleton className="h-64 w-full" />;
  if (designs.isError || !designs.data) return <ErrorBlock error={designs.error} resource="card designs" onRetry={() => void designs.refetch()} />;
  const rows = designs.data;
  const current = rows.find((row) => row.id === chosen) ?? rows.find((row) => !row.plan_id && !row.title_id) ?? rows[0];
  const taken = new Set(rows.map((row) => (row.plan_id ? `plan:${row.plan_id}` : row.title_id ? `title:${row.title_id}` : "")));
  const options = [
    ...(titles.data ?? []).filter((title) => !title.archived_at).map((title) => ({ value: `title:${title.id}`, label: t`Title: ${title.name}` })),
    ...(plans.data ?? []).map((plan) => ({ value: `plan:${plan.id}`, label: t`Plan: ${plan.name}` })),
  ].filter((option) => !taken.has(option.value));
  const canEdit = Boolean(current?.can_edit);

  return <div className="grid gap-4">
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Design`}</span>
        <select className="desk-input min-h-11" value={current?.id ?? ""} onChange={(event) => setChosen(Number(event.target.value))}>
          {rows.map((row) => <option key={row.id} value={row.id}>
            {row.target_label}{row.pending_approval ? t` (waiting for approval)` : row.published_at ? "" : t` (not published)`}</option>)}
        </select>
      </label>
      {canEdit && options.length ? <div className="flex flex-wrap items-end gap-2">
        <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Add a design for`}</span>
          <select className="desk-input min-h-11" value={target} onChange={(event) => setTarget(event.target.value)}>
            <option value="">{t`Choose a plan or title…`}</option>
            {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <button type="button" className="desk-button min-h-11" disabled={!target || create.isPending} onClick={() => {
          const [kind, id] = target.split(":");
          create.mutate(kind === "plan" ? { plan_id: Number(id) } : { title_id: Number(id) }, {
            onSuccess: (row) => { setChosen(row.id); setTarget(""); },
          });
        }}>{create.isPending ? t`Adding…` : t`Add`}</button>
      </div> : null}
    </div>
    {create.error ? <ErrorBlock error={create.error} /> : null}
    <p className="text-sm text-muted">{t`A member's card uses their primary title's design, then their plan's, then the space default.`}</p>
    {current ? <CardDesigner key={current.id} designId={current.id} canEdit={canEdit} title={t`${current.target_label} card design`} /> : null}
  </div>;
}
