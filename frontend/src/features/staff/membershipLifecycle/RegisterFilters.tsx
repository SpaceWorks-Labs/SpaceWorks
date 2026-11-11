import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";
import { listPlans, membershipPlanKeys } from "../membershipPlansApi";
import { lifecycleApi, lifecycleKeys } from "../membershipLifecycleApi";
import type { StaffRole } from "../panels/rolesApi";
import { UnitPicker } from "../units/UnitPicker";
import type { RegisterFilterValues } from "./registerModel";

/**
 * Parity O-B2: the register's filters beyond search and standing chips -- plan, title, unit (with every
 * unit beneath it), role, join dates and the roster's yes/no flags. Title and unit appear only while
 * their switches are on; the unit list is the caller's own scope, so a unit lead is offered their subtree.
 */
export function RegisterFilters({ makerspaceId, values, onChange, titlesOn, unitsOn }: {
  makerspaceId: number; values: RegisterFilterValues; onChange: (key: keyof RegisterFilterValues, value: string) => void;
  titlesOn: boolean; unitsOn: boolean;
}) {
  const plans = useQuery({ queryKey: membershipPlanKeys.plans(makerspaceId), queryFn: () => listPlans(makerspaceId) });
  const titles = useQuery({ queryKey: lifecycleKeys.titles(makerspaceId), queryFn: () => lifecycleApi.titles(makerspaceId), enabled: titlesOn });
  const roles = useQuery({ queryKey: ["members", makerspaceId, "roles"], queryFn: () => staffRequest<StaffRole[]>(`/admin/makerspaces/${makerspaceId}/roles`) });
  const select = (key: keyof RegisterFilterValues, label: string, options: [string, string][]) =>
    <label className="grid min-w-0 gap-1 text-sm">{label}
      <select className="desk-input max-w-full" value={values[key]} onChange={(event) => onChange(key, event.target.value)}>
        {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select></label>;
  const date = (key: "joined_after" | "joined_before", label: string) =>
    <label className="grid min-w-0 gap-1 text-sm">{label}
      <input className="desk-input w-full min-w-0" type="date" value={values[key]} onChange={(event) => onChange(key, event.target.value)} /></label>;
  const livePlans = (plans.data ?? []).filter((plan) => !plan.archived_at);
  const liveTitles = (titles.data ?? []).filter((title) => !title.archived_at);
  return <div className="grid min-w-0 gap-3 sm:grid-cols-2">
    {livePlans.length ? select("plan", t`Plan`, [["", t`Any plan`], ...livePlans.map((plan) => [String(plan.id), plan.name] as [string, string])]) : null}
    {titlesOn && liveTitles.length ? select("title", t`Title`, [["", t`Any title`], ...liveTitles.map((title) => [String(title.id), title.name] as [string, string])]) : null}
    {unitsOn ? <UnitPicker makerspaceId={makerspaceId} label={t`Unit`} hint={t`Includes every unit beneath it.`} noneLabel={t`Any unit`}
      value={values.unit ? Number(values.unit) : null} onChange={(unit) => onChange("unit", unit ? String(unit) : "")} /> : null}
    {roles.data?.length ? select("role", t`Role`, [["", t`Any role`], ...roles.data.map((role) => [String(role.id), role.name] as [string, string])]) : null}
    {date("joined_after", t`Joined on or after`)}
    {date("joined_before", t`Joined on or before`)}
    {select("staff", t`Staff`, [["", t`Staff and members`], ["true", t`Staff only`], ["false", t`Members only`]])}
    {select("verified", t`Verified`, [["", t`Any`], ["true", t`Verified`], ["false", t`Not verified`]])}
    {select("minor", t`Age`, [["", t`Any age`], ["true", t`Minors only`], ["false", t`Adults only`]])}
    {select("volunteer", t`Volunteering`, [["", t`Any`], ["true", t`Volunteers`], ["false", t`Not volunteering`]])}
    {select("waiver_needed", t`Waiver`, [["", t`Any`], ["true", t`Waiver acceptance needed`]])}
  </div>;
}
