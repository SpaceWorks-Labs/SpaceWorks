import { useState } from "react";
import { X } from "lucide-react";
import type { SecuritySetting } from "../../../lib/api/securitySettings";
import { INT_RULES, asList, choiceLabel, strictnessProblem } from "./securityRules";

type Props = { setting: SecuritySetting; id: string; disabled: boolean; onChange: (value: unknown) => void };

/** The editor for one security setting: a switch, a number, a choice or a list of networks. */
export function SecurityValueControl(props: Props) {
  if (props.setting.kind === "bool") return <BoolControl {...props} />;
  if (props.setting.kind === "int") return <IntControl {...props} />;
  if (props.setting.kind === "choice") return <ChoiceControl {...props} />;
  return <ListControl {...props} />;
}

function BoolControl({ setting, id, disabled, onChange }: Props) {
  // A lock forces the stricter value (on for most switches, off for an "..._allowed" one).
  const forced = setting.lock != null && setting.value === setting.lock.floor;
  const on = setting.value === true;
  return <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
    <input id={id} className="h-4 w-4" type="checkbox" checked={on} disabled={disabled || forced}
      onChange={event => onChange(event.target.checked)} />
    <span>{on ? "On" : "Off"}</span>
  </label>;
}

function Problem({ id, message }: { id: string; message: string | null }) {
  return <p id={id} role="alert" className="text-sm text-danger empty:hidden">{message ?? ""}</p>;
}

function IntControl({ setting, id, disabled, onChange }: Props) {
  const rule = INT_RULES[setting.key];
  const [draft, setDraft] = useState(String(setting.value ?? ""));
  const dirty = draft !== String(setting.value ?? "");
  const problem = dirty ? strictnessProblem(setting, draft.trim() === "" ? Number.NaN : Number(draft)) : null;
  return <form className="grid gap-2" onSubmit={event => { event.preventDefault(); if (!problem && dirty) onChange(Number(draft)); }}>
    <div className="flex flex-wrap items-center gap-2">
      <input id={id} className="desk-input w-28" type="number" inputMode="numeric" step={1} min={rule?.min} max={rule?.max}
        value={draft} disabled={disabled} aria-invalid={Boolean(problem) || undefined} aria-describedby={rule ? `${id}-problem ${id}-range` : `${id}-problem`}
        onChange={event => setDraft(event.target.value)} />
      {rule ? <span id={`${id}-range`} className="text-sm text-muted">{rule.unit}, {rule.min}–{rule.max}{rule.zeroOff ? " (0 turns it off)" : ""}</span> : null}
      <button type="submit" className="desk-button min-h-11" disabled={disabled || !dirty || Boolean(problem)}>Save</button>
    </div>
    <Problem id={`${id}-problem`} message={problem} />
  </form>;
}

function ChoiceControl({ setting, id, disabled, onChange }: Props) {
  return <select id={id} className="desk-input w-full sm:w-auto" value={String(setting.value)} disabled={disabled}
    onChange={event => onChange(event.target.value)}>
    {setting.choices.map(choice => <option key={String(choice)} value={String(choice)}
      disabled={strictnessProblem(setting, choice) !== null}>{choiceLabel(choice)}</option>)}
  </select>;
}

function ListControl({ setting, id, disabled, onChange }: Props) {
  const saved = asList(setting.value);
  const [entries, setEntries] = useState(saved);
  const [entry, setEntry] = useState("");
  const dirty = entries.join("\n") !== saved.join("\n");
  const problem = dirty ? strictnessProblem(setting, entries) : null;
  const add = () => { const next = entry.trim(); if (next && !entries.includes(next)) setEntries([...entries, next]); setEntry(""); };
  return <div className="grid gap-3">
    {entries.length ? <ul className="flex flex-wrap gap-2" aria-label="Allowed networks">
      {entries.map(value => <li key={value} className="inline-flex min-h-11 items-center gap-1 rounded-full border border-line bg-surface pl-3 text-sm text-ink">
        <span className="code-text">{value}</span>
        <button type="button" className="grid h-11 w-11 place-items-center rounded-full hover:bg-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
          aria-label={`Remove ${value}`} disabled={disabled} onClick={() => setEntries(entries.filter(item => item !== value))}><X aria-hidden="true" size={16} /></button>
      </li>)}
    </ul> : <p className="text-sm text-muted">Any network (no allow-list).</p>}
    <div className="flex flex-wrap items-end gap-2">
      <label className="grid gap-1 text-sm font-semibold text-ink" htmlFor={id}>Add a network
        <input id={id} className="desk-input w-60 max-w-full" value={entry} disabled={disabled} placeholder="203.0.113.0/24"
          aria-invalid={Boolean(problem) || undefined} aria-describedby={`${id}-problem`}
          onChange={event => setEntry(event.target.value)} onKeyDown={event => { if (event.key === "Enter") { event.preventDefault(); add(); } }} /></label>
      <button type="button" className="desk-button min-h-11" disabled={disabled || !entry.trim()} onClick={add}>Add</button>
      <button type="button" className="desk-button-primary min-h-11" disabled={disabled || !dirty || Boolean(problem)} onClick={() => onChange(entries)}>Save list</button>
    </div>
    <Problem id={`${id}-problem`} message={problem} />
  </div>;
}
