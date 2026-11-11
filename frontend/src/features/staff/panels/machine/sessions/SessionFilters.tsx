import { t } from "@lingui/core/macro";

import type { Machine } from "../../../machinesApi";
import { SessionMemberSelect } from "./SessionMemberSelect";

/** URL keys (prefixed `s_`) and saved-view state for the Sessions screen; the API takes the same names. */
export const SESSION_FILTERS = { machine_type: "", machine: "", member: "", source: "", since: "", until: "" };
const KEYS = Object.keys(SESSION_FILTERS);

/** Only the filter keys, never list presentation (columns, density). */
export function sessionFilterQuery(values: Record<string, string>) {
  return new URLSearchParams(KEYS.filter(key => values[key]).map(key => [key, values[key]])).toString();
}

const SOURCES = () => [["member_qr", t`Member scanned the machine`], ["staff", t`Started by staff`], ["device", t`Machine connection`]];

export function SessionFilters({ machines, values, onChange }: {
  machines: Machine[]; values: Record<string, string>; onChange: (patch: Record<string, string>) => void;
}) {
  const types = [...new Map(machines.map(row => [row.machine_type.id, row.machine_type.name])).entries()];
  const shown = values.machine_type ? machines.filter(row => String(row.machine_type.id) === values.machine_type) : machines;
  return <div className="grid gap-3">
    {types.length > 1 ? <label className="eyebrow grid gap-1">{t`Machine type`}
      <select className="desk-input" value={values.machine_type} onChange={event => onChange({ machine_type: event.target.value, machine: "", member: "" })}>
        <option value="">{t`All machine types`}</option>{types.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select></label> : null}
    <label className="eyebrow grid gap-1">{t`Machine`}
      <select className="desk-input" value={values.machine} onChange={event => onChange({ machine: event.target.value, member: "" })}>
        <option value="">{t`All machines`}</option>{shown.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
      </select></label>
    {values.machine ? <SessionMemberSelect machineId={Number(values.machine)} value={values.member} anyLabel={t`All members`}
      onChange={value => onChange({ member: value })} />
      : <p className="text-sm text-muted">{t`Choose a machine to filter by member.`}</p>}
    <label className="eyebrow grid gap-1">{t`Started by`}
      <select className="desk-input" value={values.source} onChange={event => onChange({ source: event.target.value })}>
        <option value="">{t`Anyone`}</option>{SOURCES().map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="eyebrow grid gap-1">{t`From`}<input type="date" className="desk-input" value={values.since} onChange={event => onChange({ since: event.target.value })} /></label>
      <label className="eyebrow grid gap-1">{t`To`}<input type="date" className="desk-input" value={values.until} onChange={event => onChange({ until: event.target.value })} /></label>
    </div>
  </div>;
}
