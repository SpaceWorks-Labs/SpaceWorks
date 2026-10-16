import { useId } from "react";
import type { StaffRole } from "./rolesApi";
import { ROLE_DESCRIPTIONS } from "./roleSets";

export type RoleChoice = Pick<StaffRole, "id" | "slug" | "name" | "exclusive">;

/** Checkbox cards for a membership's role set: Space Manager and Member replace the set, the rest combine. */
export function RoleSetPicker({ roles, value, onChange, disabled = false, label = "Roles" }: {
  roles: RoleChoice[];
  value: number[];
  onChange: (ids: number[]) => void;
  disabled?: boolean;
  label?: string;
}) {
  const id = useId();
  return <fieldset disabled={disabled} aria-describedby={`${id}-rule`} className="grid min-w-0 gap-2">
    <legend className="text-sm font-semibold text-ink">{label}</legend>
    <p id={`${id}-rule`} className="text-xs text-muted">Space Manager and Member must each be assigned alone. Other roles can be combined.</p>
    <div className="@container"><div className="grid gap-2 @md:grid-cols-2">
      {roles.map((role) => {
        const description = ROLE_DESCRIPTIONS[role.slug];
        return <label key={role.id} className="flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border border-line bg-panel p-3 has-checked:border-accent has-checked:bg-accent-soft has-focus-visible:ring-2 has-focus-visible:ring-focus has-disabled:cursor-not-allowed has-disabled:opacity-60">
          {/* Named by the role alone; the description is announced as a description, not as part of the name. */}
          <input className="mt-0.5 h-5 w-5 shrink-0 accent-accent" type="checkbox" aria-labelledby={`${id}-${role.id}`}
            aria-describedby={description ? `${id}-${role.id}-about` : undefined} checked={value.includes(role.id)} onChange={(event) => {
              if (!event.target.checked) onChange(value.filter((roleId) => roleId !== role.id));
              else if (role.exclusive) onChange([role.id]);
              else onChange([...value.filter((roleId) => !roles.some((other) => other.id === roleId && other.exclusive)), role.id]);
            }} />
          <span className="grid min-w-0 gap-1">
            <span id={`${id}-${role.id}`} className="font-semibold text-ink">{role.name}</span>
            {description ? <span id={`${id}-${role.id}-about`} className="text-xs text-muted">{description}</span> : null}
          </span>
        </label>;
      })}
    </div></div>
  </fieldset>;
}
