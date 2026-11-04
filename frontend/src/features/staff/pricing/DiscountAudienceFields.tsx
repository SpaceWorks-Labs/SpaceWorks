import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Field } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { AsyncSearchPicker } from "../AsyncSearchPicker";
import { listPlans, membershipPlanKeys } from "../membershipPlansApi";
import type { DiscountForm } from "./discountForm";

type MemberRow = { id: number; user: { id: number; username: string; display_name: string } };

const AUDIENCES: [DiscountForm["audience"], string][] = [
  ["all_members", "All members"], ["plan", "Members on a plan"], ["member", "One member"],
];

/** Who gets the discount: everyone, a plan's members (from the plans list) or one member (by search). */
export function DiscountAudienceFields({ makerspaceId, form, problems, membershipOn, onChange }: {
  makerspaceId: number; form: DiscountForm; problems: Record<string, string>; membershipOn: boolean;
  onChange: (patch: Partial<DiscountForm>) => void;
}) {
  const [term, setTerm] = useState("");
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId),
    enabled: membershipOn && form.audience === "plan" });
  const members = useQuery({
    queryKey: ["pricing-discount-members", makerspaceId, term],
    queryFn: () => staffRequest<{ results: MemberRow[] }>(`/admin/memberships?${new URLSearchParams({
      makerspace_id: String(makerspaceId), status: "active", q: term })}`),
    enabled: form.audience === "member" && term.length >= 2,
  });
  const options = (members.data?.results ?? []).map(row => ({
    id: row.user.id, label: row.user.display_name || row.user.username, detail: `@${row.user.username}` }));
  const audiences = AUDIENCES.filter(([value]) => value !== "plan" || membershipOn || form.audience === "plan");
  return <div className="grid gap-3">
    <fieldset className="grid gap-1">
      <legend className="text-sm font-semibold text-ink">Who gets it</legend>
      {audiences.map(([value, label]) => <label key={value} className="flex min-h-11 items-center gap-3 text-sm">
        <input type="radio" name="discount-audience" className="h-4 w-4" checked={form.audience === value}
          onChange={() => onChange({ audience: value })} />{label}</label>)}
    </fieldset>
    {form.audience === "plan" ? <Field label="Membership plan" error={problems.plan}
      hint={plans.data && !plans.data.length ? "No membership plans yet. Create one in membership settings." : undefined}>
      <select className="desk-input" value={form.plan ?? ""} disabled={plans.isLoading}
        onChange={event => onChange({ plan: event.target.value ? Number(event.target.value) : null })}>
        <option value="">{plans.isLoading ? "Loading plans…" : "Choose a plan"}</option>
        {(plans.data ?? []).map(plan => <option key={plan.id} value={plan.id}>{plan.name}{plan.is_active ? "" : " (inactive)"}</option>)}
      </select>
    </Field> : null}
    {plans.error ? <p role="alert" className="text-sm text-danger">{plans.error.message}</p> : null}
    {form.audience === "member" ? <AsyncSearchPicker label="Member" placeholder="Search active members"
      helper="Type at least two letters of a name or username." selected={form.member ? [form.member] : []}
      options={options} loading={members.isFetching} onSearch={setTerm}
      error={problems.member ?? (members.error ? members.error.message : null)}
      emptyText={term.length < 2 ? "Type at least two letters." : "No active members match."}
      onChange={next => onChange({ member: next.length ? next[next.length - 1] : null })} /> : null}
  </div>;
}
