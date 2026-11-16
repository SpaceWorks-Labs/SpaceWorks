import { t } from "@lingui/core/macro";

import type { StaffRole } from "../panels/rolesApi";
import type { MembershipPlan } from "../membershipPlansApi";

/** URL keys for the roster's PE4 filters. `access` carries the server's `standing` (that URL key belongs to the lifecycle tab). */
export const ROSTER_FILTER_DEFAULTS = { status: "", role: "", access: "", joined_after: "", joined_before: "",
  plan: "", staff: "", verified: "", minor: "", volunteer: "", waiver_needed: "" };
/** Decision 248: true/false flags the roster accepts (`waiver_needed` only as true). */
const FLAGS = ["staff", "verified", "minor", "volunteer", "waiver_needed"] as const;
export type RosterFilterValues = typeof ROSTER_FILTER_DEFAULTS;

/** The roster query string for these filters, in the server's names (decision 242 PE4). */
export function rosterFilterQuery(values: RosterFilterValues) {
  const query = new URLSearchParams();
  if (values.status) query.set("status", values.status);
  if (values.role) query.set("role", values.role);
  if (values.access) query.set("standing", values.access);
  if (values.plan) query.set("plan", values.plan);
  if (values.joined_after) query.set("joined_after", values.joined_after);
  if (values.joined_before) query.set("joined_before", values.joined_before);
  for (const flag of FLAGS) if (values[flag]) query.set(flag, values[flag]);
  return query;
}

export const activeRosterFilters = (values: RosterFilterValues) => Object.values(values).filter(Boolean).length;

/** PE3/PE4: membership status, role held, account standing and join dates. */
export function RosterFilters({ values, roles, plans = [], onChange }: {
  values: RosterFilterValues; roles: StaffRole[]; plans?: Pick<MembershipPlan, "id" | "name">[]; onChange: (key: keyof RosterFilterValues, value: string) => void;
}) {
  const select = (key: keyof RosterFilterValues, label: string, options: [string, string][]) =>
    <label className="grid min-w-0 gap-1 text-sm">{label}
      <select className="desk-input max-w-full" value={values[key]} onChange={event => onChange(key, event.target.value)}>
        {options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select></label>;
  const date = (key: "joined_after" | "joined_before", label: string) =>
    <label className="grid min-w-0 gap-1 text-sm">{label}
      <input className="desk-input w-full min-w-0" type="date" value={values[key]} onChange={event => onChange(key, event.target.value)} /></label>;
  return <div className="grid min-w-0 gap-3 sm:grid-cols-2">
    {select("status", t`Status`, [["", t`All`], ["active", t`Active`], ["revoked", t`Revoked`]])}
    {roles.length ? select("role", t`Role`, [["", t`Any role`], ...roles.map(role => [String(role.id), role.name] as [string, string])]) : null}
    {plans.length ? select("plan", t`Plan`, [["", t`Any plan`], ...plans.map(plan => [String(plan.id), plan.name] as [string, string])]) : null}
    {select("access", t`Account standing`, [["", t`Any standing`], ["active", t`In good standing`], ["restricted", t`Restricted`], ["suspended", t`Suspended`]])}
    {date("joined_after", t`Joined on or after`)}
    {date("joined_before", t`Joined on or before`)}
    {select("staff", t`Staff`, [["", t`Staff and members`], ["true", t`Staff only`], ["false", t`Members only`]])}
    {select("verified", t`Verified`, [["", t`Any`], ["true", t`Verified`], ["false", t`Not verified`]])}
    {select("minor", t`Age`, [["", t`Any age`], ["true", t`Minors only`], ["false", t`Adults only`]])}
    {select("volunteer", t`Volunteering`, [["", t`Any`], ["true", t`Volunteers`], ["false", t`Not volunteering`]])}
    {select("waiver_needed", t`Waiver`, [["", t`Any`], ["true", t`Waiver acceptance needed`]])}
  </div>;
}
