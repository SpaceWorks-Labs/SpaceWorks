import { t } from "@lingui/core/macro";

export const BOOKING_PERMISSIONS = ["edit_details", "manage_reservations", "check_in", "publish_page"] as const;
export type BookingPermission = typeof BOOKING_PERMISSIONS[number];

export function bookingAccess(space?: { can_manage_grants?: boolean; staff_permissions?: readonly string[] }) {
  const manager = space?.can_manage_grants === true;
  return { manager, edit: manager || Boolean(space?.staff_permissions?.includes("edit_details")),
    reservations: manager || Boolean(space?.staff_permissions?.includes("manage_reservations")) };
}

/** Translated wording for a booking resource staff permission. */
export function bookingPermissionLabel(permission: string): string {
  switch (permission) {
    case "edit_details": return t`Edit details`;
    case "manage_reservations": return t`Manage reservations`;
    case "check_in": return t`Check in`;
    case "publish_page": return t`Publish page`;
    default: return permission.replace(/_/g, " ");
  }
}
