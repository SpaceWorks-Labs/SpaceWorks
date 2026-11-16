import { t } from "@lingui/core/macro";
import { BOOKING_PERMISSIONS, bookingPermissionLabel, type BookingPermission } from "./bookingStaffPermissions";

export function BookingPermissionFields({ value, onChange, disabled, legend = t`Resource permissions` }: {
  value: BookingPermission[]; onChange: (next: BookingPermission[]) => void; disabled?: boolean; legend?: string;
}) {
  return <fieldset disabled={disabled} className="grid min-w-0 gap-1"><legend className="mb-1 text-sm font-semibold text-ink">{legend}</legend>
    <div className="grid gap-x-6 sm:grid-cols-2">{BOOKING_PERMISSIONS.map((permission) => <label key={permission} className="flex min-h-11 items-center gap-2 text-sm text-ink">
      <input type="checkbox" checked={value.includes(permission)} onChange={(event) => onChange(event.target.checked ? [...value, permission] : value.filter((entry) => entry !== permission))} />{bookingPermissionLabel(permission)}
    </label>)}</div>
    <p className="text-xs text-muted">{t`Grants exclude pricing, rules, machine links, visibility policy, finance and delegation.`}</p>
  </fieldset>;
}
