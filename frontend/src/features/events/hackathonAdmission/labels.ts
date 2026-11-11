import { t } from "@lingui/core/macro";

/** Translated wording for a hackathon application or cohort `state`. */
export function applicationStateLabel(state: string): string {
  switch (state) {
    case "draft": return t`Draft`;
    case "submitted": return t`Submitted`;
    case "offered": return t`Place offered`;
    case "waitlisted": return t`Waitlisted`;
    case "confirmed": return t`Confirmed`;
    case "rejected": return t`Not selected`;
    case "declined": return t`Declined`;
    case "expired": return t`Expired`;
    case "withdrawn": return t`Withdrawn`;
    default: return state.replace(/_/g, " ");
  }
}
