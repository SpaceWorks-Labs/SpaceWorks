import { t } from "@lingui/core/macro";
import type { ClaimSummary } from "./types";

/** Translated wording for a support request, award or expense-claim `state`; unknown codes fall back readable. */
export function reimbursementStateLabel(state: string): string {
  switch (state) {
    case "draft": return t`Draft`;
    case "requested": return t`Requested`;
    case "waitlisted": return t`Waitlisted`;
    case "awarded": return t`Awarded`;
    case "declined": return t`Declined`;
    case "withdrawn": return t`Withdrawn`;
    case "expired": return t`Expired`;
    case "offered": return t`Offered`;
    case "accepted": return t`Accepted`;
    case "forfeited": return t`Forfeited`;
    case "closed": return t`Closed`;
    case "open": return t`Open`;
    case "submitted": return t`Submitted`;
    case "under_review": return t`Under review`;
    case "returned_for_info": return t`More information needed`;
    case "approved": return t`Approved`;
    case "partially_approved": return t`Partly approved`;
    case "rejected": return t`Rejected`;
    case "paid": return t`Paid`;
    default: return state.replace(/_/g, " ");
  }
}

/** Translated wording for a travel-expense category. */
export function travelCategoryLabel(category: string): string {
  switch (category) {
    case "rail": return t`Rail`;
    case "air": return t`Air`;
    case "bus": return t`Bus`;
    case "ground_transport": return t`Ground transport`;
    case "lodging": return t`Lodging`;
    default: return category.replace(/_/g, " ");
  }
}

/** Translated wording for a screener's claim recommendation. */
export function screeningRecommendationLabel(value: string): string {
  switch (value) {
    case "approve": return t`Approve`;
    case "partial": return t`Partially approve`;
    case "reject": return t`Reject`;
    case "request_info": return t`Request more information`;
    default: return value.replace(/_/g, " ");
  }
}

/** The newest finance decision on a claim (its reason is shown to the owner). */
export function latestDecision(claim: ClaimSummary | null | undefined) {
  const decisions = claim?.decisions ?? [];
  return decisions.length ? decisions.reduce((a, b) => (b.sequence > a.sequence ? b : a)) : null;
}
