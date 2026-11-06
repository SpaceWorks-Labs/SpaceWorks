import { t } from "@lingui/core/macro";
import { Field } from "../../../components/ui/Field";
import { CATEGORIES } from "../../events/reimbursements/types";
import { localDateTime, utcInstant } from "../../events/stagedForms/formPayload";
import type { PolicySettings } from "./types";
import { CommaListField } from "../../events/stagedForms/CommaListField";
import { RequiredSubmissionField } from "./RequiredSubmissionField";

export function PolicyFields({ value, onChange }: { value: PolicySettings; onChange: (value: PolicySettings) => void }) {
  const change = <K extends keyof PolicySettings>(key: K, next: PolicySettings[K]) => onChange({ ...value, [key]: next });
  const tokens = (key: "eligible_countries" | "eligible_cohorts" | "exclusions" | "permitted_venue_sources", label: string) => <CommaListField label={label} hint={t`Comma separated; empty means no additional filter.`} values={value[key]} onChange={parts => change(key, parts)} />;
  const instant = (key: "request_opens_at" | "request_closes_at" | "claim_due_at", label: string) => <Field label={label}><input className="desk-input" type="datetime-local" required={key === "claim_due_at"} value={localDateTime(value[key])}
    onChange={event => change(key, event.target.value ? utcInstant(event.target.value) : key === "claim_due_at" ? "" : null)} /></Field>;
  return <section className="grid gap-5" aria-label={t`Reimbursement policy`}>
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.enabled} onChange={event => change("enabled", event.target.checked)} />{t`Enable support requests`}</label>
    <Field label={t`Request phase`}><select className="desk-input" value={value.request_phase} onChange={event => change("request_phase", event.target.value as PolicySettings["request_phase"])}><option value="application">{t`During application`}</option><option value="after_acceptance">{t`After acceptance`}</option><option value="both">{t`Both phases`}</option></select></Field>
    <div className="grid gap-4 md:grid-cols-2">{instant("request_opens_at", "Requests open (your local time)")}{instant("request_closes_at", "Requests close (your local time)")}{instant("claim_due_at", "Claims due (your local time)")}</div>
    <Field label={t`Award mode`}><select className="desk-input" value={value.award_mode} onChange={event => onChange({ ...value, award_mode: event.target.value as PolicySettings["award_mode"], tier_rules: event.target.value === "percentage" ? { basis_points: 10000, cap_minor: 1 } : {} })}>
      <option value="need_based">{t`Need based`}</option><option value="fixed_tier">{t`Fixed tier`}</option><option value="route_cap">{t`Route cap`}</option><option value="percentage">{t`Percentage of estimate`}</option></select></Field>
    <RuleFields value={value} onChange={onChange} />
    <fieldset><legend>{t`Eligible categories and category caps (minor units)`}</legend>{CATEGORIES.map(category => <div key={category} className="grid items-center gap-3 sm:grid-cols-2">
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.allowed_categories.includes(category)} onChange={event => change("allowed_categories", event.target.checked ? [...value.allowed_categories, category] : value.allowed_categories.filter(item => item !== category))} />{category.replace(/_/g, " ")}</label>
      <Field label={`${category.replace(/_/g, " ")} cap`}><input className="desk-input" type="number" min={0} step={1} max={9000000000000000} value={value.category_limits[category] ?? ""} onChange={event => {
        const limits = { ...value.category_limits }; if (event.target.value) limits[category] = event.target.valueAsNumber; else delete limits[category]; change("category_limits", limits);
      }} /></Field></div>)}</fieldset>
    <Field label={t`Minimum self-reported travel distance (km)`}><input className="desk-input" inputMode="decimal" pattern="(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,3})?" value={value.min_distance_km ?? ""} onChange={event => change("min_distance_km", event.target.value || null)} /></Field>
    <Field label={t`Award acceptance window (days)`}><input className="desk-input" type="number" min={1} max={365} required value={value.award_accept_days} onChange={event => change("award_accept_days", event.target.valueAsNumber)} /></Field>
    {tokens("eligible_countries", "Eligible country codes")}{tokens("eligible_cohorts", "Eligible cohort keys")}{tokens("exclusions", "Excluded expenses")}{tokens("permitted_venue_sources", "Permitted venue attendance sources")}
    <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={value.attendance_required} onChange={event => change("attendance_required", event.target.checked)} />{t`Require venue attendance evidence`}</label>
    <RequiredSubmissionField value={value} onChange={onChange} />
  </section>;
}
function RuleFields({ value, onChange }: { value: PolicySettings; onChange: (value: PolicySettings) => void }) {
  if (value.award_mode === "need_based") return null;
  if (value.award_mode === "percentage") {
    const rules = value.tier_rules as { basis_points: number; cap_minor: number };
    return <div className="grid gap-4 md:grid-cols-2"><Field label={t`Percentage in basis points`} hint={t`10000 means 100%.`}><input className="desk-input" type="number" min={1} max={10000} step={1} required value={rules.basis_points} onChange={event => onChange({ ...value, tier_rules: { ...rules, basis_points: event.target.valueAsNumber } })} /></Field>
      <Field label={t`Percentage award cap (minor units)`}><input className="desk-input" type="number" required min={1} max={9000000000000000} step={1} value={rules.cap_minor} onChange={event => onChange({ ...value, tier_rules: { ...rules, cap_minor: event.target.valueAsNumber } })} /></Field></div>;
  }
  const rules = value.tier_rules as Record<string, { amount_minor: number }>;
  return <section className="grid gap-3" aria-label={t`Award tier rules`}>{Object.entries(rules).map(([key, rule], index) => <div key={index} className="grid gap-3 rounded-xl border border-line p-3 md:grid-cols-2">
    <Field label={t`Tier ${index + 1} key`}><input className="desk-input" required value={key} onChange={event => { const entries = Object.entries(rules); entries[index] = [event.target.value, rule]; onChange({ ...value, tier_rules: Object.fromEntries(entries) }); }} /></Field>
    <Field label={t`Tier ${index + 1} cap (minor units)`}><input className="desk-input" type="number" required min={1} max={9000000000000000} step={1} value={rule.amount_minor} onChange={event => onChange({ ...value, tier_rules: { ...rules, [key]: { amount_minor: event.target.valueAsNumber } } })} /></Field>
    <button type="button" className="desk-button" onClick={() => onChange({ ...value, tier_rules: Object.fromEntries(Object.entries(rules).filter(([item]) => item !== key)) })}>{t`Remove tier`}</button></div>)}
    <button type="button" className="desk-button" onClick={() => onChange({ ...value, tier_rules: { ...rules, [`tier_${Object.keys(rules).length + 1}`]: { amount_minor: 1 } } })}>{t`Add tier`}</button></section>;
}
