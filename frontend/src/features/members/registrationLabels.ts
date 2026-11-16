import { t } from "@lingui/core/macro";

/** Member-facing wording for an `EventRegistration.Status` value; built per call so a locale switch applies. */
export function registrationStatusLabel(status: string): string {
  switch (status) {
    case "pending_approval": return t`Awaiting approval`;
    case "registered": return t`Confirmed`;
    case "waitlisted": return t`Waitlisted`;
    case "rejected": return t`Not approved`;
    case "cancelled": return t`Cancelled`;
    case "attended": return t`Attended`;
    default: return status.replace(/_/g, " ");
  }
}
