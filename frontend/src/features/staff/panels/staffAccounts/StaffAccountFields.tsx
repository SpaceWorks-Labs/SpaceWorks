import { Field } from "../../../../components/ui";
import { STAFF_ROLE_NAMES, type StaffAccountDraft, type StaffRoleKey } from "../../../../lib/api/staffAccounts";
import { RoleSetPicker } from "../RoleSetPicker";

export function StaffAccountFields({ machineTypes, draft, onChange, roles, identity = false, pending = false }: {
  machineTypes: { id: number; name: string }[]; draft: StaffAccountDraft; onChange: (draft: StaffAccountDraft) => void;
  roles: StaffRoleKey[]; identity?: boolean; pending?: boolean;
}) {
  const machineManager = draft.roles.includes("machine_manager");
  const choices = Object.entries(STAFF_ROLE_NAMES).map(([slug, name], index) => ({
    id: index + 1, slug: slug as StaffRoleKey, name, exclusive: slug === "space_manager",
  }));
  return <fieldset disabled={pending} className="grid min-w-0 gap-4">
    <legend className="sr-only">Staff account details</legend>
    {identity ? <>
      <Field label="Name"><input className="desk-input w-full" required maxLength={150} autoComplete="name" value={draft.display_name} onChange={e => onChange({ ...draft, display_name: e.target.value })} /></Field>
      <Field label="Email"><input className="desk-input w-full" type="email" maxLength={254} autoComplete="email" value={draft.email ?? ""} onChange={e => onChange({ ...draft, email: e.target.value })} /></Field>
      <Field label="Username"><input className="desk-input w-full" maxLength={150} autoComplete="off" required={!draft.email?.trim()} value={draft.username ?? ""} onChange={e => onChange({ ...draft, username: e.target.value })} /></Field>
      <p className="text-sm text-muted">Provide an email or username. This creates a separate staff account for this makerspace.</p>
    </> : null}
    <RoleSetPicker roles={choices.filter(role => roles.includes(role.slug))}
      value={choices.filter(role => draft.roles.includes(role.slug)).map(role => role.id)}
      onChange={ids => {
        const selected = choices.filter(role => ids.includes(role.id)).map(role => role.slug);
        onChange({ ...draft, roles: selected, machine_type_ids: selected.includes("machine_manager") ? draft.machine_type_ids : [] });
      }} />
    {machineManager ? <fieldset className="grid gap-2">
      <legend className="text-sm font-semibold">Assigned machine types</legend>
      <p className="text-sm text-muted">No selected types means no machines. A type includes machines added to it later.</p>
      {machineTypes.map(type => <label key={type.id} className="flex min-h-11 items-center gap-3 text-sm">
        <input type="checkbox" checked={draft.machine_type_ids.includes(type.id)} onChange={e => onChange({ ...draft,
          machine_type_ids: e.target.checked ? [...draft.machine_type_ids, type.id] : draft.machine_type_ids.filter(id => id !== type.id),
        })} />{type.name}
      </label>)}
    </fieldset> : null}
  </fieldset>;
}
