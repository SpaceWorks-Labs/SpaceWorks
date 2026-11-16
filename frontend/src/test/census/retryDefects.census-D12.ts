import type { RouteCase } from "./source.census-D12";

// Decision 573 / checklist D12 requires an operational failure to be retryable.
// These source-confirmed GET/effect error branches expose only text or a link.
// Strict runtime parameters still establish admission and exact 503/code first.
export const RETRY_DEFECTS = [
  { id: "CENSUS-D12-32", screen: "FirebaseBridgePage", source: "features/notifications/firebase/FirebaseBridgePage.tsx:50", fix: "Distinguish config.error from configured=false and expose config.refetch() with operational failure copy." },
  { id: "CENSUS-D12-33", leaf: "AnalyticsPanel", source: "features/staff/analytics/AnalyticsPanel.tsx:32", fix: "Add a native summary.refetch retry on summary-error; retain the summary's status/code." },
  { id: "CENSUS-D12-34", screen: "UnsubscribePage", source: "features/notifications/UnsubscribePage.tsx:31", fix: "Offer an explicit retry of the failed mutation; never unsubscribe automatically on URL open." },
  { id: "CENSUS-D12-55", screen: "PhotoChoice", source: "features/events/eventPresentation/PhotoChoice.tsx:53", fix: "Offer an enabled native retry of current.refetch() and options.refetch() on operational failure inside the open disclosure; never save consent as a retry." },
  { id: "CENSUS-D12-38", screen: "OrganizationInvitationRedeemPage", source: "features/organizations/OrganizationInvitationRedeemPage.tsx:68", fix: "Offer a retry that calls redeem.mutate() after an operational failure; keep the captured token and single-use server verification." },
  { id: "CENSUS-D12-39", screen: "PublicEventFeedbackPage", source: "features/inventory/PublicEventFeedbackPage.tsx:61", fix: "Separate 5xx from closed/missing surveys; show operational copy and form.refetch()." },
  { id: "CENSUS-D12-40", screen: "TechnicianOptInPage", source: "features/repairs/TechnicianOptInPage.tsx:31", fix: "Separate 5xx from unavailable invitations and expose query.refetch()." },
  { id: "CENSUS-D12-41", screen: "MemberEventTicketPage", source: "features/events/MemberEventTicketPage.tsx:83", fix: "Offer ticket.refetch() and failed bootstrap/identity retries in the error branch." },
  { id: "CENSUS-D12-42", screen: "MemberEventHistoryPage", source: "features/events/MemberEventHistoryPage.tsx:48", fix: "Offer history.refetch() for an operational failure, preserving the existing 403 history policy." },
  { id: "CENSUS-D12-43", screen: "ApplicationReviewsPage", source: "features/events/participation/ApplicationReviewsPage.tsx:29", fix: "Attach a keyboard-operable retry to stages.refetch() on GET failure." },
  { id: "CENSUS-D12-44", screen: "MemberOrdersPage", source: "features/events/ticketing/MemberOrdersPage.tsx:38", fix: "Supply onRetry: orders.refetch to the ListLayout error state." },
  { id: "CENSUS-D12-45", screen: "MemberSeriesPassPage", source: "features/events/ticketing/MemberSeriesPassPage.tsx:53", fix: "Offer passes.refetch() after an operational GET failure." },
  { id: "CENSUS-D12-46", screen: "TicketClaimPage", source: "features/events/ticketing/TicketClaimPage.tsx:51", fix: "Offer preview.refetch() on an operational GET failure without redeeming the ticket." },
  { id: "CENSUS-D12-47", screen: "ShopOrderStatusPage", source: "features/shop/ShopOrderStatusPage.tsx:19", fix: "Separate an operational outage from an invalid bearer link and supply query.refetch()." },
  { id: "CENSUS-D12-48", screen: "OAuthConsentPage", source: "features/members/apiAccess/OAuthConsentPage.tsx:34", fix: "Offer preview.refetch() after a failed consent preview without approving scopes." },
  { id: "CENSUS-D12-49", screen: "CertificateVerificationPage", source: "features/events/eventPresentation/CertificateVerificationPage.tsx:53", fix: "Separate 5xx from enumeration-safe missing/private certificates; expose query.refetch()." },
  { id: "CENSUS-D12-50", leaf: "FinancePanel", source: "features/finance/FinancePanel.tsx:54", fix: "Render a distinct access.error explanation and access.refetch() instead of presenting an outage as switches off." },
] as const;
export function retryDefect(row: RouteCase) {
  return RETRY_DEFECTS.find(defect => "screen" in defect ? row.screen === defect.screen : row.leaves?.includes(defect.leaf));
}
