import { t } from "@lingui/core/macro";

/** Translated wording for a `MakerspaceMembership.status` value. */
export function membershipStatusLabel(status: string): string {
  if (status === "active") return t`Active`;
  if (status === "revoked") return t`Revoked`;
  return status.replace(/_/g, " ");
}

/** Translated wording for a `MembershipRequest.state` (admission application) value. */
export function admissionStateLabel(state: string): string {
  switch (state) {
    case "requested": return t`Requested`;
    case "invited": return t`Invited`;
    case "awaiting_vouches": return t`Awaiting vouches`;
    case "awaiting_payment": return t`Awaiting payment`;
    case "changes_requested": return t`Changes requested`;
    case "expired": return t`Expired`;
    case "canceled": return t`Cancelled`;
    case "active": return t`Active`;
    case "revoked": return t`Revoked`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated wording for a built-in membership role code; custom roles fall back to their code. */
export function membershipRoleLabel(role: string): string {
  switch (role) {
    case "member": return t`Member`;
    case "space_manager": return t`Space Manager`;
    case "inventory_manager": return t`Inventory Manager`;
    case "machine_manager": return t`Machine Manager`;
    case "event_manager": return t`Event Manager`;
    case "booking_manager": return t`Booking Manager`;
    case "shop_manager": return t`Shop Manager`;
    case "fundraising": return t`Fundraising`;
    case "print_manager": return t`Print Manager`;
    case "handover": return t`Handover`;
    case "technician": return t`Technician`;
    default: return role.replace(/_/g, " ");
  }
}
