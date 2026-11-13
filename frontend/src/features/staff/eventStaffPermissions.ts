import { t } from "@lingui/core/macro";

export const EVENT_PERMISSIONS = [
  ["edit_details", t`Edit details`],
  ["manage_registrations", t`Manage registrations`],
  ["manage_invitations", t`Manage invitations`],
  ["check_in", t`Check in attendees`],
  ["publish_schedule", t`Publish schedule`],
  ["review_applications", t`Review applications`],
  ["manage_hackathon", t`Manage hackathon`],
  ["manage_team", t`Manage teams`],
  ["manage_volunteers", t`Manage volunteers`],
  ["mentor_queue", t`Mentor Desk`],
  ["judge", t`Judge assigned projects`],
  ["view_sponsor_track", t`View sponsor track`],
  ["review_reimbursements", t`Screen travel support`],
] as const;

export type EventPermission = typeof EVENT_PERMISSIONS[number][0];

/** Translated name of an event permission code; an unknown code reads as words. */
export const eventPermissionLabel = (permission: string) =>
  EVENT_PERMISSIONS.find(([key]) => key === permission)?.[1] ?? permission.replace(/_/g, " ");

export function eventAccess(event: { staff_permissions?: readonly string[]; can_manage_staff?: boolean }) {
  // Older API responses had only full managers. New responses always supply both
  // fields; permissions are checked again by the API on every operation.
  const manager = event.can_manage_staff ?? event.staff_permissions === undefined;
  const has = (permission: EventPermission) => manager || event.staff_permissions?.includes(permission) === true;
  return { manager, edit: has("edit_details"), registrations: has("manage_registrations"),
    invitations: has("manage_invitations"), checkIn: has("check_in"), publish: has("publish_schedule"),
    applications: has("review_applications"), hackathon: has("manage_hackathon"), teams: has("manage_team"),
    volunteers: has("manage_volunteers"), mentors: has("mentor_queue"), judge: has("judge"), sponsor: has("view_sponsor_track"),
    reimbursements: has("review_reimbursements") };
}
