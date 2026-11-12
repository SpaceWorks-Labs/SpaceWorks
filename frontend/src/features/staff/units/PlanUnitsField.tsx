import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { isSurfaceOff } from "../../../lib/api";
import { orderedUnits } from "./unitHierarchy";
import { unitErrorText, unitKeys, unitsApi, useMemberUnits } from "./unitsApi";
import { LogoLoader } from "../../../components/LogoLoader";
import { BoxArt } from "../../../components/BoxSpinner";

/**
 * Which units a plan is offered in (`PUT membership-plans/<pid>/units`). Ticking a unit offers the plan
 * there and in every unit beneath it, so those rows show as included; nothing ticked offers it in every
 * unit. Saved on its own, because the plan form saves a different resource.
 */
export function PlanUnitsField({ makerspaceId, planId, planName }: { makerspaceId: number; planId: number; planName: string }) {
  const client = useQueryClient();
  const key = unitKeys.planUnits(makerspaceId, planId);
  const saved = useQuery({ queryKey: key, queryFn: () => unitsApi.planUnits(makerspaceId, planId), retry: false });
  const units = useMemberUnits(makerspaceId);
  const [draft, setDraft] = useState<number[] | null>(null);
  const save = useMutation({
    mutationFn: (ids: number[]) => unitsApi.setPlanUnits(makerspaceId, planId, ids),
    onSuccess: data => { client.setQueryData(key, data); setDraft(null); },
  });
  if (isSurfaceOff(saved.error) || isSurfaceOff(units.error)) return null;
  const failure = saved.error ?? units.error;
  const current = saved.data?.unit_ids ?? [];
  const chosen = new Set(draft ?? current);
  const rows = orderedUnits((units.data?.units ?? []).filter(unit => !unit.archived || chosen.has(unit.id)));
  const byId = new Map(rows.map(unit => [unit.id, unit]));
  const coveredBy = (unitId: number) => {
    for (let parent = byId.get(unitId)?.parent_id ?? null; parent !== null; parent = byId.get(parent)?.parent_id ?? null) {
      if (chosen.has(parent)) return byId.get(parent);
    }
    return undefined;
  };
  const toggle = (unitId: number, on: boolean) => {
    save.reset();
    setDraft(on ? [...chosen, unitId] : [...chosen].filter(id => id !== unitId));
  };
  const dirty = draft !== null && [...chosen].sort().join() !== [...current].sort().join();
  return <fieldset className="grid gap-3 rounded-xl border border-line p-4">
    <legend className="px-1 text-sm font-semibold text-ink">{t`Units offering ${planName}`}</legend>
    <p className="text-sm text-muted">{chosen.size
      ? t`Offered only in the ticked units and the units beneath them.`
      : t`Offered in every unit. Tick units to limit it.`}</p>
    {failure ? <ErrorText message={unitErrorText(failure)} onRetry={() => { void saved.refetch(); void units.refetch(); }} /> : null}
    {saved.isPending || units.isPending ? <LogoLoader label={t`Loading units…`} size={48} className="min-h-16 py-3" /> : null}
    {units.isSuccess && !rows.length ? <p className="text-sm text-muted">{t`This space has no units yet.`}</p> : null}
    <ul className="grid gap-1">{rows.map(unit => {
      const parent = coveredBy(unit.id);
      return <li key={unit.id} style={{ paddingInlineStart: `${unit.depth * 1.5}rem` }}>
        <label className="flex min-h-11 items-center gap-3 text-sm">
          <input type="checkbox" className="h-5 w-5 accent-accent" checked={chosen.has(unit.id) || Boolean(parent)}
            disabled={Boolean(parent) || save.isPending} onChange={event => toggle(unit.id, event.target.checked)} />
          <span className="grid">
            <span className="text-ink">{unit.name} <span className="text-muted">· {unit.code}</span></span>
            {parent ? <span className="text-xs text-muted">{t`Included through ${parent.name}`}</span> : null}
          </span>
        </label>
      </li>;
    })}</ul>
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" className="desk-button min-h-11" disabled={!dirty || save.isPending}
        onClick={() => save.mutate([...chosen].filter(id => !coveredBy(id)))}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save units`}</button>
      {chosen.size ? <button type="button" className="desk-button min-h-11" disabled={save.isPending} onClick={() => { save.reset(); setDraft([]); }}>{t`Offer in every unit`}</button> : null}
      {save.isSuccess && !dirty ? <span role="status" className="text-sm text-muted">{t`Plan units saved.`}</span> : null}
    </div>
    {save.error ? <ErrorText message={unitErrorText(save.error)} /> : null}
  </fieldset>;
}
