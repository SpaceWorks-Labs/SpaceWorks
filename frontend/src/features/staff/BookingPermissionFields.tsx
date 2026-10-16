import { BOOKING_PERMISSIONS, type BookingPermission } from "./bookingStaffPermissions";

export function BookingPermissionFields({ value, onChange, disabled, legend = "Resource permissions" }: {
  value: BookingPermission[]; onChange: (next: BookingPermission[]) => void; disabled?: boolean; legend?: string;
}) {
  return <fieldset disabled={disabled} className="grid gap-2"><legend className="mb-2 text-sm font-semibold">{legend}</legend>
    {BOOKING_PERMISSIONS.map((permission) => <label key={permission} className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={value.includes(permission)} onChange={(event) => onChange(event.target.checked ? [...value, permission] : value.filter((entry) => entry !== permission))} />{permission.replace(/_/g, " ")}
    </label>)}
    <p className="text-xs text-muted">Grants exclude pricing, rules, machine links, visibility policy, finance and delegation.</p>
  </fieldset>;
}
