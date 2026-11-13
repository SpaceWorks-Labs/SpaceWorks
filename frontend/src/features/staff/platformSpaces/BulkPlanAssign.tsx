import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../../components/ui";
import { StructuredApiError, staffRequest } from "../../../lib/api";
import { usePlans } from "./plansApi";
import { healthKey, type HealthCard } from "./spacesApi";
import { BoxArt } from "../../../components/BoxSpinner";

const LIMIT = 50;

/**
 * Decision 248 (C1b): give up to 50 HOSTED spaces on this page the same plan at once. Own spaces have no
 * plan (decision 236), so they are not offered. All-or-nothing: on a 409 the server names the space it
 * refused and nothing changes.
 */
export function BulkPlanAssign({ cards }: { cards: HealthCard[] }) {
  const client = useQueryClient();
  const hosted = cards.filter(card => card.hosted === true || card.hosting_type === "hosted");
  const plans = usePlans(hosted.length > 0);
  const [open, setOpen] = useState(false);
  const [picked, setPicked] = useState<number[]>([]);
  const [planId, setPlanId] = useState("");
  const [trial, setTrial] = useState("");
  const selected = picked.filter(id => hosted.some(card => card.id === id));
  const trialDays = trial.trim() === "" ? undefined : Number(trial);
  const assign = useMutation({
    mutationFn: () => staffRequest<{ assigned: number; makerspace_ids: number[] }>("/admin/platform/spaces/plan-bulk", { method: "POST",
      body: JSON.stringify({ makerspace_ids: selected, plan_id: Number(planId), ...(trialDays === undefined ? {} : { trial_days: trialDays }) }) }, "platform"),
    onSuccess: () => { setPicked([]); void client.invalidateQueries({ queryKey: healthKey }); void client.invalidateQueries({ queryKey: ["platform-space-plan"] }); },
  });
  if (!hosted.length) return null;
  const error = assign.error;
  const failed = error instanceof StructuredApiError && error.status === 409 && typeof error.body.failed_id === "number"
    ? t`No plans changed. ${hosted.find(card => card.id === error.body.failed_id)?.name ?? t`Space #${String(error.body.failed_id)}`} could not take this plan: ${typeof error.body.cause === "string" ? error.body.cause : error.message}`
    : error ? error.message : "";
  const validTrial = trialDays === undefined || (Number.isInteger(trialDays) && trialDays >= 0);
  return <div className="grid gap-2">
    <button type="button" className="desk-button min-h-11 w-fit" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      {open ? t`Close plan assignment` : t`Give several hosted spaces a plan`}</button>
    {open ? <fieldset className="grid gap-3 rounded-xl border border-line bg-panel p-3">
      <legend className="title-section px-1">{t`Hosted spaces on this page`}</legend>
      <ul className="grid gap-1 sm:grid-cols-2">{hosted.slice(0, LIMIT).map(card => <li key={card.id}><label className="flex min-h-11 items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4" checked={selected.includes(card.id)}
          onChange={() => setPicked(current => current.includes(card.id) ? current.filter(id => id !== card.id) : [...current, card.id])} />{card.name}
      </label></li>)}</ul>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t`Plan`}><select className="desk-input" value={planId} onChange={event => setPlanId(event.target.value)}>
          <option value="">{t`Choose a plan`}</option>
          {(plans.data ?? []).filter(plan => plan.is_active).map(plan => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
        </select></Field>
        <Field label={t`Trial days (optional)`} hint={t`Leave empty to use the plan's own trial length.`}>
          <input className="desk-input" type="number" min={0} inputMode="numeric" value={trial} onChange={event => setTrial(event.target.value)} />
        </Field>
      </div>
      <button type="button" className="desk-button-primary min-h-11 w-fit" disabled={!selected.length || !planId || !validTrial || assign.isPending}
        onClick={() => assign.mutate()}>{assign.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Assign to ${selected.length} spaces`}</button>
      {assign.isSuccess ? <p role="status" className="text-sm text-muted">{t`Plan assigned to ${assign.data.assigned} spaces.`}</p> : null}
      {failed ? <p role="alert" className="text-sm text-danger">{failed}</p> : null}
    </fieldset> : null}
  </div>;
}
