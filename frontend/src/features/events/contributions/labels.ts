import { t } from "@lingui/core/macro";

/** Translated wording for a contribution role (`EventRoleAssignment.role`). */
export function contributionRoleLabel(role: string): string {
  switch (role) {
    case "co_organizer": return t`Co-organizer`;
    case "volunteer": return t`Volunteer`;
    case "mentor": return t`Mentor`;
    case "judge": return t`Judge`;
    case "sponsor_rep": return t`Sponsor representative`;
    default: return role.replace(/_/g, " ");
  }
}

/** Translated wording for a role application or shift signup `state`. */
export function contributionStateLabel(state: string): string {
  switch (state) {
    case "draft": return t`Draft`;
    case "proposed": return t`Proposed`;
    case "applied": return t`Applied`;
    case "waitlisted": return t`Waitlisted`;
    case "approved": return t`Approved`;
    case "declined": return t`Declined`;
    case "withdrawn": return t`Withdrawn`;
    case "revoked": return t`Revoked`;
    case "completed": return t`Completed`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated wording for a shift attendance state. */
export function shiftAttendanceLabel(state: string): string {
  switch (state) {
    case "scheduled": return t`Scheduled`;
    case "checked_in": return t`Checked in`;
    case "checked_out": return t`Checked out`;
    case "no_show": return t`No-show`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated button text for a shift-signup action code from `allowed_actions`. */
export function shiftActionLabel(action: string): string {
  switch (action) {
    case "withdraw": return t`Withdraw`;
    case "check-in": return t`Check in`;
    case "check-out": return t`Check out`;
    case "approve": return t`Approve`;
    case "verify-hours": return t`Verify hours`;
    case "adjust-hours": return t`Adjust hours`;
    default: return action.replace(/[-_]/g, " ");
  }
}
