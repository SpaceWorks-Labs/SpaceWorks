import { EVENT_PERMISSIONS, type EventPermission } from "./eventStaffPermissions";

export function EventPermissionFields({ value, onChange, disabled = false, legend = "Permissions" }: {
  value: EventPermission[]; onChange: (next: EventPermission[]) => void; disabled?: boolean; legend?: string;
}) {
  return <fieldset disabled={disabled} className="grid gap-2">
    <legend className="mb-2 font-semibold text-ink">{legend}</legend>
    {EVENT_PERMISSIONS.map(([permission, label]) => <label key={permission} className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={value.includes(permission)} onChange={(event) => onChange(
        event.target.checked ? [...value, permission] : value.filter((entry) => entry !== permission),
      )} />{label}
    </label>)}
  </fieldset>;
}
