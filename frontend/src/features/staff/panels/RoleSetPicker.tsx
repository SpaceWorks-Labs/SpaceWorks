import type { StaffRole } from "./rolesApi";

export type RoleChoice = Pick<StaffRole, "id" | "slug" | "name" | "exclusive">;

export function RoleSetPicker({ roles, value, onChange, disabled = false, label = "Roles" }: {
  roles: RoleChoice[];
  value: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
  label?: string;
}) {
  return <fieldset disabled={disabled} className="grid gap-1">
    <legend className="eyebrow">{label}</legend>
    <p className="text-xs text-muted">Space Manager and Member must each be assigned alone. Other roles can be combined.</p>
    {roles.map((role) => <label key={role.id} className="flex min-h-11 items-center gap-2 text-sm text-ink">
      <input type="checkbox" checked={value.includes(role.id)} onChange={(event) => {
        if (!event.target.checked) onChange(value.filter((id) => id !== role.id));
        else if (role.exclusive) onChange([role.id]);
        else onChange([...value.filter((id) => !roles.some((other) => other.id === id && other.exclusive)), role.id]);
      }} />{role.name}
    </label>)}
  </fieldset>;
}
