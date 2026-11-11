import { t } from "@lingui/core/macro";
import { Search } from "lucide-react";
import { useId, useMemo, useState } from "react";

export type ScopeType = { id: number; name: string };
export type ScopeMachine = { id: number; name: string; machine_type_id: number };
export type MachineScope = { machine_type_ids: number[]; machine_ids: number[] };

const card = "flex min-h-11 cursor-pointer items-start gap-3 rounded-lg px-2 py-2 has-checked:bg-accent-soft has-focus-visible:ring-2 has-focus-visible:ring-focus has-disabled:cursor-default";
const box = "mt-0.5 h-5 w-5 shrink-0 accent-accent";

/**
 * Decision 282: a Machine Manager's or Technician's reach is whole machine types (including machines added
 * later) and/or single machines, the union of both; nothing chosen means no machines. Machines are grouped
 * under their type and the list is searchable by type or machine name. A machine whose type is chosen is
 * already covered, so its own box shows checked and locked.
 */
export function MachineScopePicker({ types, machines, value, onChange, disabled = false }: {
  types: ScopeType[]; machines: ScopeMachine[]; value: MachineScope; onChange: (value: MachineScope) => void; disabled?: boolean;
}) {
  const id = useId();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const groups = useMemo(() => types.map(type => {
    const all = machines.filter(machine => machine.machine_type_id === type.id);
    const typeHit = !needle || type.name.toLowerCase().includes(needle);
    return { type, machines: typeHit ? all : all.filter(machine => machine.name.toLowerCase().includes(needle)), visible: typeHit || all.some(machine => machine.name.toLowerCase().includes(needle)) };
  }).filter(group => group.visible), [types, machines, needle]);
  const toggle = (list: number[], item: number, on: boolean) => on ? [...new Set([...list, item])] : list.filter(entry => entry !== item);
  const nothing = !value.machine_type_ids.length && !value.machine_ids.length;
  const count = value.machine_type_ids.length + value.machine_ids.filter(machineId => {
    const machine = machines.find(row => row.id === machineId);
    return !machine || !value.machine_type_ids.includes(machine.machine_type_id);
  }).length;
  return <fieldset disabled={disabled} className="grid min-w-0 gap-2" aria-describedby={`${id}-rule`}>
    <legend className="text-sm font-semibold text-ink">{t`Machines they look after`}</legend>
    <p id={`${id}-rule`} className="text-xs text-muted">{t`Choose whole machine types (they include machines added later), single machines, or both. Nothing chosen means no machines.`}</p>
    {types.length > 4 || machines.length > 8 ? <label className="relative flex items-center">
      <Search aria-hidden="true" size={16} className="pointer-events-none absolute left-3 text-muted" />
      <span className="sr-only">{t`Search machines and types`}</span>
      <input className="desk-input w-full pl-9" type="search" value={query} placeholder={t`Search machines and types`} onChange={event => setQuery(event.target.value)} />
    </label> : null}
    {!types.length ? <p className="text-sm text-muted">{t`This makerspace has no machine types yet.`}</p> : null}
    {types.length && !groups.length ? <p role="status" className="text-sm text-muted">{t`No machines or types match.`}</p> : null}
    <div className="grid max-h-80 gap-2 overflow-y-auto overscroll-contain rounded-xl border border-line p-2">
      {groups.map(({ type, machines: rows }) => {
        const typeOn = value.machine_type_ids.includes(type.id);
        return <div key={type.id} role="group" aria-labelledby={`${id}-type-${type.id}`} className="grid gap-1">
          <label className={card}>
            <input className={box} type="checkbox" checked={typeOn} aria-labelledby={`${id}-type-${type.id}`} aria-describedby={`${id}-type-${type.id}-about`}
              onChange={event => onChange({ ...value, machine_type_ids: toggle(value.machine_type_ids, type.id, event.target.checked) })} />
            <span className="grid min-w-0 gap-0.5">
              <span id={`${id}-type-${type.id}`} className="font-semibold text-ink">{type.name}</span>
              <span id={`${id}-type-${type.id}-about`} className="text-xs text-muted">{t`Every machine of this type`}</span>
            </span>
          </label>
          {rows.length ? <ul className="ml-8 grid gap-0.5 border-l border-line pl-2">{rows.map(machine => <li key={machine.id}><label className={card}>
            <input className={box} type="checkbox" disabled={typeOn} checked={typeOn || value.machine_ids.includes(machine.id)}
              onChange={event => onChange({ ...value, machine_ids: toggle(value.machine_ids, machine.id, event.target.checked) })} />
            <span className="min-w-0 text-sm text-ink [overflow-wrap:anywhere]">{machine.name}
              {typeOn ? <span className="block text-xs text-muted">{t`Covered by the type`}</span> : null}</span>
          </label></li>)}</ul> : null}
        </div>;
      })}
    </div>
    <p role="status" className={`text-sm ${nothing ? "text-danger" : "text-muted"}`}>
      {nothing ? t`Nothing chosen: this person looks after no machines.` : t`${count} chosen`}</p>
  </fieldset>;
}

/** Scope chips for a staff row: type names first, then single machines. */
export function MachineScopeChips({ types, machines }: { types?: { id: number; name: string }[]; machines?: { id: number; name: string }[] }) {
  if (!types?.length && !machines?.length) return null;
  return <ul className="flex flex-wrap gap-1" aria-label={t`Machines they look after`}>
    {(types ?? []).map(type => <li key={`type-${type.id}`} className="rounded-full border border-line bg-surface px-2 py-0.5 text-xs font-semibold text-ink">{t`All ${type.name}`}</li>)}
    {(machines ?? []).map(machine => <li key={`machine-${machine.id}`} className="rounded-full border border-line px-2 py-0.5 text-xs text-ink">{machine.name}</li>)}
  </ul>;
}
