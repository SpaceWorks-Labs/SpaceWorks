export const BOOKING_PERMISSIONS = ["edit_details", "manage_reservations", "check_in", "publish_page"] as const;
export type BookingPermission = typeof BOOKING_PERMISSIONS[number];

export function bookingAccess(space?: { can_manage_grants?: boolean; staff_permissions?: readonly string[] }) {
  const manager = space?.can_manage_grants === true;
  return { manager, edit: manager || Boolean(space?.staff_permissions?.includes("edit_details")),
    reservations: manager || Boolean(space?.staff_permissions?.includes("manage_reservations")) };
}
