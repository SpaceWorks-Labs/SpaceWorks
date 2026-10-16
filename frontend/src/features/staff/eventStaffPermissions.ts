export const EVENT_PERMISSIONS = [
  ["edit_details", "Edit details"],
  ["manage_registrations", "Manage registrations"],
  ["manage_invitations", "Manage invitations"],
  ["check_in", "Check in attendees"],
  ["publish_schedule", "Publish schedule"],
] as const;

export type EventPermission = typeof EVENT_PERMISSIONS[number][0];

export function eventAccess(event: { staff_permissions?: readonly string[]; can_manage_staff?: boolean }) {
  // Older API responses had only full managers. New responses always supply both
  // fields; permissions are checked again by the API on every operation.
  const manager = event.can_manage_staff ?? event.staff_permissions === undefined;
  const has = (permission: EventPermission) => manager || event.staff_permissions?.includes(permission) === true;
  return { manager, edit: has("edit_details"), registrations: has("manage_registrations"),
    invitations: has("manage_invitations"), checkIn: has("check_in"), publish: has("publish_schedule") };
}
