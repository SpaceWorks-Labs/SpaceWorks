import { EVENT_PERMISSIONS, type EventPermission } from "./eventStaffPermissions";

export function EventPermissionFields({ value, onChange, disabled = false, legend = "Permissions" }: {
  value: EventPermission[]; onChange: (next: EventPermission[]) => void; disabled?: boolean; legend?: string;
}) {
  return <fieldset disabled={disabled} className="grid min-w-0 gap-x-4 sm:grid-cols-2">
    <legend className="mb-1 text-sm font-semibold text-ink">{legend}</legend>
    {EVENT_PERMISSIONS.map(([permission, label]) => <label key={permission} className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={value.includes(permission)} onChange={(event) => onChange(
        event.target.checked ? [...value, permission] : value.filter((entry) => entry !== permission),
      )} />{label}
    </label>)}
  </fieldset>;
}
