import { t } from "@lingui/core/macro";
import { useContext, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow, StatusPill } from "../../components/ui";
import {
  PLAN_INTERVALS,
  createPlan,
  listPlans,
  membershipPlanKeys,
  planErrorText,
  planIntervalLabel,
  setPlanArchived,
  updatePlan,
  type MembershipPlan,
  type MembershipPlanInput,
  type PlanInterval,
} from "./membershipPlansApi";
import { formatMoney } from "./paymentsApi";
import { usePriceDropCheck } from "./priceDrop/usePriceDropCheck";
import { Panel } from "./panels/shared";
import { PlanPriceNote } from "./pricing/PricingNote";
import { useStaffChargesOn } from "./useStaffChargesOn";
import { MembershipRenewalFields, emptyRenewal, planRenewal, renewalInput, validateRenewal } from "./MembershipRenewalFields";
import { MembershipPlanRulesFields, emptyRules, rulesFromPlan, rulesInput, validateRules } from "./MembershipPlanRulesFields";
import { MembershipIncludedHoursFields, emptyIncludedHours, includedHoursInput, planIncludedHours, validateIncludedHours } from "./MembershipIncludedHoursFields";
import { StaffListContext } from "./StaffListContext";
import { PlanUnitsField } from "./units/PlanUnitsField";
import { PlanSacField, planSacOn, validatePlanSac } from "../finance/PlanSacField";
import { EMPTY_JOIN_FIELDS, JoinFieldsSection, joinPlanFields, joinPlanInput, type JoinPlanFields } from "./JoinFieldsSection";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxArt } from "../../components/BoxSpinner";

type PlanForm = {
  name: string;
  interval: PlanInterval;
  custom_days: string;
  amount: string;
  currency: string;
  is_active: boolean;
  sac_code?: string; // parity O-B3, sent only while `billing.plan_sac` is on
  join?: JoinPlanFields; // parity O-B2, each part sent only while its switch is on
};

const EMPTY: PlanForm = { name: "", interval: "monthly", custom_days: "", amount: "0.00", currency: "usd", is_active: true, sac_code: "", join: EMPTY_JOIN_FIELDS };

/** Mirrors `MembershipPlanSerializer.validate`: custom days only with the custom interval. */
export function validatePlanForm(form: PlanForm): string | null {
  if (!form.name.trim()) return "Give the plan a name.";
  if (!/^\d+(\.\d{1,3})?$/.test(form.amount.trim())) return "Enter a non-negative amount with no more decimals than the currency has.";
  if (!/^[A-Za-z]{3}$/.test(form.currency.trim())) return "Use a three-letter ISO 4217 currency code.";
  if (form.interval === "custom_days" && !/^[1-9]\d*$/.test(form.custom_days.trim())) {
    return "A custom interval needs a whole number of days (1 or more).";
  }
  return null;
}

function toInput(form: PlanForm): MembershipPlanInput {
  return {
    name: form.name.trim(),
    interval: form.interval,
    // The serializer refuses a day count on a non-custom interval, so send null there.
    custom_days: form.interval === "custom_days" ? Number(form.custom_days.trim()) : null,
    amount: form.amount.trim(),
    currency: form.currency.trim().toLowerCase(),
    is_active: form.is_active,
  };
}

function toForm(plan: MembershipPlan): PlanForm {
  return {
    name: plan.name,
    interval: plan.interval,
    custom_days: plan.custom_days == null ? "" : String(plan.custom_days),
    amount: plan.amount,
    currency: plan.currency,
    is_active: plan.is_active,
    sac_code: plan.sac_code ?? "",
    join: joinPlanFields(plan),
  };
}

export function MembershipPlansSection({ makerspaceId, features = [] }: { makerspaceId: number; features?: string[] }) {
  const planRulesOn = features.includes("membership.plan_rules");
  const publicPlansOn = features.includes("membership.public_plans");
  const sacOn = planSacOn(features);
  const [rules, setRules] = useState(emptyRules);
  const [hours, setHours] = useState(emptyIncludedHours);
  // Included hours apply only while the space runs bookings (machine time also needs machines).
  const modules = useContext(StaffListContext).makerspace?.enabled_modules ?? [];
  const pools = { booking: modules.includes("bookings"), machine: modules.includes("bookings") && modules.includes("machines") };
  const client = useQueryClient();
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const [editing, setEditing] = useState<MembershipPlan | null>(null);
  const [form, setForm] = useState<PlanForm>(EMPTY);
  const [problem, setProblem] = useState<string | null>(null);
  const [renewal, setRenewal] = useState(emptyRenewal);
  const refresh = () => client.invalidateQueries({ queryKey: membershipPlanKeys.plans(makerspaceId) });
  const planInput = () => ({ ...toInput(form), ...renewalInput(renewal), ...rulesInput(rules, planRulesOn, publicPlansOn), ...includedHoursInput(hours, pools), ...(sacOn ? { sac_code: (form.sac_code ?? "").trim() } : {}), ...joinPlanInput(form.join ?? EMPTY_JOIN_FIELDS, features) }) as MembershipPlanInput;
  const save = useMutation({
    mutationFn: () => {
      const input = planInput();
      return editing ? updatePlan(editing.id, input) : createPlan(makerspaceId, input);
    },
    onSuccess: () => {
      setEditing(null);
      setForm(EMPTY);
      setRenewal(emptyRenewal);
      setRules(emptyRules);
      setHours(emptyIncludedHours);
      refresh();
    },
  });
  const archive = useMutation({ mutationFn: (plan: MembershipPlan) => setPlanArchived(plan.id, !plan.archived_at), onSuccess: refresh });
  const toggleActive = useMutation({
    mutationFn: (plan: MembershipPlan) => updatePlan(plan.id, { is_active: !plan.is_active }),
    onSuccess: refresh,
  });
  const set = <K extends keyof PlanForm>(key: K, value: PlanForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setProblem(null);
  };
  // Lane L24: a cheaper plan may owe terms paid but not started yet a refund.
  const drop = usePriceDropCheck(makerspaceId);
  // #184: with membership charges off no price is asked for or shown (stored values stay as they are).
  const chargesOn = useStaffChargesOn("membership", makerspaceId);
  const submit = async () => {
    const next = validatePlanForm(form) ?? validateRenewal(renewal) ?? validateRules(rules) ?? (pools.booking ? validateIncludedHours(hours) : null) ?? (sacOn ? validatePlanSac(form.sac_code ?? "") : null);
    setProblem(next);
    if (next) return;
    if (editing && !(await drop.check(`/admin/membership-plans/${editing.id}`, "PATCH", planInput()))) return;
    save.mutate();
  };
  const startEdit = (plan: MembershipPlan) => {
    setEditing(plan);
    setForm(toForm(plan));
    setRenewal(planRenewal(plan));
    setRules(rulesFromPlan(plan));
    setHours(planIncludedHours(plan));
    setProblem(null);
  };
  const cancelEdit = () => {
    setEditing(null);
    setForm(EMPTY);
    setRenewal(emptyRenewal);
    setRules(emptyRules);
    setHours(emptyIncludedHours);
    setProblem(null);
  };
  const error = problem ?? (save.error ? planErrorText(save.error, "Could not save the plan.") : null)
    ?? (toggleActive.error ?? archive.error ? planErrorText(toggleActive.error ?? archive.error, "Could not update the plan.") : null);

  return (
    <Panel title={t`Membership plans`}>
      <p className="mb-3 text-sm text-muted">
        {t`Plans price a membership term. Members are put on a plan from the roster ("Terms"); a plan with terms cannot be deleted, only deactivated.`}</p>
      <PlanPriceNote makerspaceId={makerspaceId} />
      {chargesOn ? null : <p className="mb-3 text-sm text-muted">{t`Membership charges are off in this space, so membership is free.`}</p>}
      {plans.isLoading ? <LogoLoader label={t`Loading plans…`} size={48} className="min-h-16 py-3" /> : null}
      {plans.isError ? <p className="text-sm text-danger" role="alert">{planErrorText(plans.error, "Could not load plans.")}</p> : null}
      {plans.data?.length === 0 ? <EmptyState message={t`No plans yet. Add your first membership plan below.`} /> : null}
      {plans.data?.map((plan) => (
        <ListRow key={plan.id} title={plan.name} identity={{ kind: "icon", icon: "Calendar", tone: "accent" }}
          meta={<>{planIntervalLabel(plan)}{chargesOn ? ` · ${formatMoney(plan.amount, plan.currency)}` : ""}</>}
          right={<div className="flex flex-wrap items-center gap-2">
            <StatusPill tone={plan.archived_at ? "neutral" : plan.is_active ? "success" : "neutral"} label={plan.archived_at ? t`Archived` : plan.is_active ? t`Active` : t`Inactive`} />
            {plan.is_public ? <StatusPill tone="info" label={t`Public`} /> : null}
            <button className="desk-button" type="button" onClick={() => startEdit(plan)}>{t`Edit`}</button>
            <button className="desk-button" type="button" disabled={toggleActive.isPending} onClick={() => toggleActive.mutate(plan)}>
              {plan.is_active ? t`Deactivate` : t`Activate`}
            </button>
            <button className="desk-button" type="button" disabled={archive.isPending} onClick={() => archive.mutate(plan)}>
              {plan.archived_at ? t`Restore` : t`Archive`}
            </button>
          </div>} />
      ))}
      <form
        className="mt-4 grid gap-2 border-t border-line pt-4 sm:grid-cols-3"
        aria-label={editing ? t`Edit plan ${editing.name}` : t`New membership plan`}
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <Field label={t`Plan name`} className="sm:col-span-3">
          <input className="desk-input" maxLength={120} value={form.name} onChange={(event) => set("name", event.target.value)} />
        </Field>
        <Field label={t`Interval`}>
          <select className="desk-input max-w-full" value={form.interval} onChange={(event) => set("interval", event.target.value as PlanInterval)}>
            {PLAN_INTERVALS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field label={t`Custom days`} hint={form.interval === "custom_days" ? undefined : t`Only for a custom interval.`}>
          <input
            className="desk-input"
            inputMode="numeric"
            value={form.custom_days}
            disabled={form.interval !== "custom_days"}
            onChange={(event) => set("custom_days", event.target.value)}
          />
        </Field>
        <label className="flex min-h-11 items-center gap-2 self-end text-sm text-ink">
          <input className="h-4 w-4" type="checkbox" checked={form.is_active} onChange={(event) => set("is_active", event.target.checked)} />
          {t`Active`}</label>
        {chargesOn ? <><Field label={t`Amount`}>
          <input className="desk-input" inputMode="decimal" value={form.amount} onChange={(event) => set("amount", event.target.value)} />
        </Field>
        <Field label={t`Currency`}>
          <input className="desk-input" maxLength={3} value={form.currency} onChange={(event) => set("currency", event.target.value.toLowerCase())} />
        </Field></> : null}
        {sacOn ? <PlanSacField value={form.sac_code ?? ""} onChange={(value) => set("sac_code", value)} /> : null}
        <div className="flex flex-wrap items-end gap-2">
          <button className="desk-button-primary" type="submit" disabled={save.isPending}>
            {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : editing ? t`Save plan` : t`Create plan`}
          </button>
          {editing ? <button className="desk-button" type="button" onClick={cancelEdit}>{t`Cancel`}</button> : null}
        </div>
        <MembershipRenewalFields value={renewal} chargesOn={chargesOn} onChange={(value) => { setRenewal(value); setProblem(null); }} />
        <MembershipPlanRulesFields value={rules} onChange={(value) => { setRules(value); setProblem(null); }} planRulesOn={planRulesOn} publicPlansOn={publicPlansOn} chargesOn={chargesOn} />
        <JoinFieldsSection value={form.join ?? EMPTY_JOIN_FIELDS} features={features} onChange={(value) => set("join", value)} />
        <MembershipIncludedHoursFields value={hours} pools={pools} onChange={(value) => { setHours(value); setProblem(null); }} />
      </form>
      {editing && features.includes("membership.units") ? <div className="mt-4"><PlanUnitsField key={editing.id} makerspaceId={makerspaceId} planId={editing.id} planName={editing.name} /></div> : null}
      {error ? <p className="mt-2 text-sm text-danger" role="alert">{error}</p> : null}
      {drop.dialog}
    </Panel>
  );
}
