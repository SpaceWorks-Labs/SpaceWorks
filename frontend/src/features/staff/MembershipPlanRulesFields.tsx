import { t } from "@lingui/core/macro";
import { Field, SegmentedControl } from "../../components/ui";
import type { MembershipPlan, PlanType } from "./membershipPlansApi";

export type PlanRules = {
  plan_type: PlanType; fixed_end_date: string; renewal_amount: string; joining_fee: string;
  rejoin_rule: string; rejoin_after_days: string; payment_timing: string; join_mode: string; late_renewal: string;
  is_public: boolean; slug: string; description: string; sort_order: string;
};

export const emptyRules: PlanRules = {
  plan_type: "rolling", fixed_end_date: "", renewal_amount: "", joining_fee: "", rejoin_rule: "", rejoin_after_days: "",
  payment_timing: "", join_mode: "", late_renewal: "backdate", is_public: false, slug: "", description: "", sort_order: "0",
};

const TYPES: { value: PlanType; label: string; explain: string }[] = [
  { value: "rolling", label: t`Rolling`, explain: "Each term lasts the interval from the day it starts." },
  { value: "financial_year", label: t`Financial year`, explain: "Every term ends when the space's financial year ends." },
  { value: "fixed_end", label: t`Fixed end date`, explain: "Every term ends on the date you choose." },
  { value: "lifetime", label: t`Lifetime`, explain: "One term that never ends and never renews." },
];

export function rulesFromPlan(plan: MembershipPlan): PlanRules {
  const text = (value: unknown) => (value === null || value === undefined ? "" : String(value));
  return {
    plan_type: plan.plan_type ?? "rolling", fixed_end_date: text(plan.fixed_end_date), renewal_amount: text(plan.renewal_amount),
    joining_fee: text(plan.joining_fee), rejoin_rule: text(plan.rejoin_rule), rejoin_after_days: text(plan.rejoin_after_days),
    payment_timing: text(plan.payment_timing), join_mode: text(plan.join_mode), late_renewal: plan.late_renewal ?? "backdate",
    is_public: Boolean(plan.is_public), slug: plan.slug ?? "", description: plan.description ?? "", sort_order: text(plan.sort_order ?? 0),
  };
}

const money = /^\d+(\.\d{1,2})?$/;
export function validateRules(rules: PlanRules): string | null {
  if (rules.plan_type === "fixed_end" && !rules.fixed_end_date) return "A fixed-end plan needs its end date.";
  for (const [value, label] of [[rules.renewal_amount, "renewal price"], [rules.joining_fee, "joining fee"]] as const) {
    if (value && !money.test(value)) return `Enter the ${label} as a non-negative amount with at most two decimals.`;
  }
  if (rules.rejoin_rule === "after_lapse" && !/^[1-9]\d*$/.test(rules.rejoin_after_days)) return "Say how many days away count as a lapse.";
  if (rules.slug && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(rules.slug)) return "Use lowercase letters, digits and single hyphens in the link name.";
  return null;
}

/** Only the fields whose switch is on are sent, so a switched-off space never writes them. */
export function rulesInput(rules: PlanRules, planRulesOn: boolean, publicPlansOn: boolean) {
  const nullable = (value: string) => (value === "" ? null : value);
  return {
    sort_order: Number(rules.sort_order) || 0,
    ...(planRulesOn ? {
      plan_type: rules.plan_type, fixed_end_date: rules.plan_type === "fixed_end" ? rules.fixed_end_date : null,
      renewal_amount: nullable(rules.renewal_amount), joining_fee: nullable(rules.joining_fee),
      rejoin_rule: nullable(rules.rejoin_rule), rejoin_after_days: rules.rejoin_rule === "after_lapse" ? Number(rules.rejoin_after_days) : null,
      payment_timing: nullable(rules.payment_timing), join_mode: nullable(rules.join_mode), late_renewal: rules.late_renewal,
      ...(rules.plan_type === "lifetime" ? { auto_renew: false } : {}),
    } : {}),
    ...(publicPlansOn ? { is_public: rules.is_public, slug: rules.slug, description: rules.description } : {}),
  };
}

/** `chargesOn` false (membership charges off, #184) hides every price, fee and payment-timing rule. */
export function MembershipPlanRulesFields({ value, onChange, planRulesOn, publicPlansOn, chargesOn = true }: {
  value: PlanRules; onChange: (value: PlanRules) => void; planRulesOn: boolean; publicPlansOn: boolean; chargesOn?: boolean;
}) {
  const set = <K extends keyof PlanRules>(key: K, next: PlanRules[K]) => onChange({ ...value, [key]: next });
  const type = TYPES.find((item) => item.value === value.plan_type) ?? TYPES[0];
  const select = (key: keyof PlanRules, label: string, options: [string, string][]) => <Field label={label}>
    <select className="desk-input max-w-full" value={String(value[key])} onChange={(event) => set(key, event.target.value as never)}>
      {options.map(([option, text]) => <option key={option} value={option}>{text}</option>)}</select></Field>;
  return <div className="grid gap-3 sm:col-span-3 sm:grid-cols-3">
    {planRulesOn ? <>
      <div className="grid gap-1 sm:col-span-3">
        <SegmentedControl label={t`Plan type`} value={value.plan_type} onChange={(next) => set("plan_type", next as PlanType)}
          options={TYPES.map((item) => ({ value: item.value, label: item.label }))} />
        <p className="text-sm text-muted">{type.explain}</p>
      </div>
      {value.plan_type === "fixed_end" ? <Field label={t`Ends on`}><input className="desk-input" type="date" value={value.fixed_end_date} onChange={(event) => set("fixed_end_date", event.target.value)} /></Field> : null}
      {chargesOn ? <><Field label={t`Renewal price`} hint={t`Blank: same as a new term.`}><input className="desk-input" inputMode="decimal" value={value.renewal_amount} onChange={(event) => set("renewal_amount", event.target.value)} /></Field>
      <Field label={t`Joining fee`} hint={t`Blank: the space default.`}><input className="desk-input" inputMode="decimal" value={value.joining_fee} onChange={(event) => set("joining_fee", event.target.value)} /></Field>
      {select("rejoin_rule", "Joining fee on rejoin", [["", "Space default"], ["never", "No joining fee"], ["once", "First join only"], ["each_join", "Every join"], ["after_lapse", "Again after a lapse"]])}
      {value.rejoin_rule === "after_lapse" ? <Field label={t`Lapse after (days)`}><input className="desk-input" inputMode="numeric" value={value.rejoin_after_days} onChange={(event) => set("rejoin_after_days", event.target.value)} /></Field> : null}</> : null}
      {select("join_mode", "How people join", [["", "Space default"], ["open", "Open"], ["approval", "Staff approve"], ["invite_only", "Invite only"], ["vouch", "Members vouch"], ["closed", "Closed"]])}
      {chargesOn ? select("payment_timing", "When they pay", [["", "Space default"], ["after_activation", "After activation"], ["before_activation", "Before activation"]]) : null}
      {select("late_renewal", "Late renewal starts", [["backdate", "At the old end date"], ["payment_day", "On the renewal day"]])}
    </> : null}
    {publicPlansOn ? <>
      <label className="flex min-h-11 items-center gap-2 self-end text-sm"><input className="h-4 w-4" type="checkbox" checked={value.is_public} onChange={(event) => set("is_public", event.target.checked)} />{t`Show on the public page`}</label>
      <Field label={t`Link name`} hint={t`For the plan's own page, e.g. annual-pass.`}><input className="desk-input" maxLength={80} value={value.slug} onChange={(event) => set("slug", event.target.value)} /></Field>
      <Field label={t`Description`} className="sm:col-span-3"><textarea className="desk-input min-h-16" value={value.description} onChange={(event) => set("description", event.target.value)} /></Field>
    </> : null}
    <Field label={t`Sort order`}><input className="desk-input" inputMode="numeric" value={value.sort_order} onChange={(event) => set("sort_order", event.target.value)} /></Field>
  </div>;
}
