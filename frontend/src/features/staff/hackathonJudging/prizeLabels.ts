import { t } from "@lingui/core/macro";

/** Translated wording for a prize share `state` (the server's code, never shown raw). */
export function shareStateLabel(state: string): string {
  switch (state) {
    case "proposed": return t`Proposed`;
    case "confirmed": return t`Confirmed`;
    case "declined": return t`Declined`;
    case "forfeited": return t`Forfeited`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated wording for a prize status (what the space still owes or has settled). */
export function prizeStatusLabel(status: string): string {
  switch (status) {
    case "owed": return t`Owed`;
    case "part_paid": return t`Partly paid`;
    case "paid": return t`Paid`;
    case "fulfilled": return t`Handed over`;
    case "sponsor_paid": return t`Paid by sponsor`;
    case "forfeited": return t`Forfeited`;
    case "verified": return t`Verified`;
    default: return status.replace(/_/g, " ");
  }
}

/** Translated wording for a prize kind. */
export function prizeKindLabel(kind: string): string {
  switch (kind) {
    case "cash": return t`Cash`;
    case "item": return t`Item`;
    case "credit": return t`Credit`;
    case "perk": return t`Perk`;
    default: return kind.replace(/_/g, " ");
  }
}
