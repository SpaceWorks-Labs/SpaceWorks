import type { Phase } from "./fetch.census-D12";
import type { RouteCase } from "./source.census-D12";

export const PENDING_COPY = [
  { screen: "SpaceDisplayPage", source: "features/spaceDisplay/SpaceDisplayPage.tsx", text: "Starting…" },
] as const;
export function pendingCopyFor(row: RouteCase) {
  return PENDING_COPY.filter(item => item.screen === row.screen).map(item => item.text as string);
}

// These are presentation contracts, not error-code substitutions. The wire and
// real StructuredApiError assertions still run before any sentence is accepted.
export const SCREEN_COPY: { screen: string; phase: Phase; source: string; text: string }[] = [
  { screen: "PublicEventDetailPage", phase: "empty", source: "features/inventory/PublicEventDetailPage.tsx", text: "This event is no longer available." },
  // AppRoutes.tsx SingleTenantEvent renders PublicEventDetailPage for the configured slug.
  { screen: "SingleTenantEvent", phase: "empty", source: "features/inventory/PublicEventDetailPage.tsx", text: "This event is no longer available." },
  { screen: "PublicEventFeedbackPage", phase: "empty", source: "features/inventory/PublicEventFeedbackPage.tsx", text: "This survey is closed, the event has not ended yet, or the link is invalid." },
  { screen: "PublicBookingResourcePage", phase: "empty", source: "features/bookings/PublicBookingResourcePage.tsx", text: "Resource unavailable. This resource may be private or no longer available." },
  { screen: "PublicWebsiteDetailPage", phase: "empty", source: "features/events/PublicWebsiteDetailPage.tsx", text: "Page not found." },
  { screen: "MemberEventTicketPage", phase: "empty", source: "features/events/MemberEventTicketPage.tsx", text: "This ticket is not available right now." },
  { screen: "GuestGiftPage", phase: "empty", source: "features/donations/GuestGiftPage.tsx", text: "This link isn't valid any more. Check the latest email from the space." },
  { screen: "GuestPledgePage", phase: "empty", source: "features/donations/GuestPledgePage.tsx", text: "This link isn't valid any more. Check the latest email from the space." },
  { screen: "JoinPage", phase: "empty", source: "features/organizations/idProgrammes/JoinPage.tsx", text: "The link may be wrong, or the programme has closed." },
  // Off/missing/closed programmes deliberately share one public 404 answer (JoinPage.tsx).
  { screen: "JoinPage", phase: "module", source: "features/organizations/idProgrammes/JoinPage.tsx", text: "The link may be wrong, or the programme has closed." },
  { screen: "CertificateVerificationPage", phase: "empty", source: "features/events/eventPresentation/CertificateVerificationPage.tsx", text: "This certificate is not available for public checking." },
  { screen: "EventProgrammePage", phase: "empty", source: "features/events/programme/EventProgrammePage.tsx", text: "This account does not currently meet the event admission requirements." },
  { screen: "SpaceDisplayPage", phase: "empty", source: "features/spaceDisplay/SpaceDisplayPage.tsx", text: "This screen address is no longer valid. Ask a manager for a new one." },
  { screen: "SpaceDisplayPage", phase: "empty", source: "features/spaceDisplay/SpaceDisplayPage.tsx", text: "In the staff console, open Settings, then Display screens, and enter this code." },
  { screen: "SpaceDisplayPage", phase: "error", source: "features/spaceDisplay/SpaceDisplayPage.tsx", text: "Can't reach the server. Trying again…" },
  // presence/views_display.py STATE_DESCRIPTION: unknown, revoked or switched-off screens share one 404.
  { screen: "SpaceDisplayPage", phase: "module", source: "features/spaceDisplay/SpaceDisplayPage.tsx", text: "This screen address is no longer valid. Ask a manager for a new one." },
  { screen: "PrizesPage", phase: "empty", source: "features/events/prizes/MyPrizes.tsx", text: "No prizes yet" },
  { screen: "EventPayoutPage", phase: "empty", source: "features/finance/eventPayouts/MemberPayoutDetail.tsx", text: "We couldn't find this reimbursement in your account." },
  // A missing stage response (404) shares privateQueries.commandError's 401/403/404 sentence.
  { screen: "EventAddonPage", phase: "empty", source: "features/events/stagedForms/privateQueries.ts", text: "This content is no longer available for your access." },
  { screen: "HostingRequestStatusPage", phase: "empty", source: "features/hosting/HostingRequestStatusPage.tsx", text: "This request hasn't been sent yet. Use the invitation link from your email to send it." },
  { screen: "SupervisedSessionsPage", phase: "empty", source: "features/supervised-sessions/SupervisedSessionList.tsx", text: "No open supervised sessions." },
  { screen: "SupervisedSessionsPage", phase: "empty", source: "features/supervised-sessions/SupervisedMachineSelect.tsx", text: "No machines are listed for members here." },
  // The intake projection's module_disabled refusal names the fixture space (fetch BOOTSTRAP name).
  { screen: "JobRequestPage", phase: "module", source: "features/machine-jobs/JobRequestPage.tsx", text: "D12 Lab isn't taking job requests right now." },
  { screen: "CardVerifyPage", phase: "module", source: "features/cards/CardVerifyPage.tsx", text: "We couldn't match this code to a card. Check the whole code was scanned, or ask to see the card again." },
  { screen: "CardVerifyPage", phase: "permission", source: "lib/api/errors.ts", text: "Census access denied." },
  { screen: "StaffApp/accountability", phase: "empty", source: "features/staff/panels/AccountabilityPanel.tsx", text: "Nothing to follow up. No overdue loans, open problems or restrictions." },
  { screen: "StaffApp/requests", phase: "empty", source: "features/staff/panels/RequestQueues.tsx", text: "No requests waiting for review. Check Ready for handover for the next step." },
  // Handover-only consoles open on the ready queue (guestOnly), with its own empty sentence.
  { screen: "StaffApp/requests", phase: "empty", source: "features/staff/panels/RequestQueues.tsx", text: "Nothing to hand over. Accepted requests land here." },
  { screen: "StaffApp/tobuy", phase: "empty", source: "features/staff/panels/ProcurementPanel.tsx", text: "Nothing in this stage yet. Add an item or view all stages." },
  { screen: "StaffApp/users", phase: "empty", source: "features/staff/panels/staffRoles/StaffRolesPanel.tsx", text: "No active staff here. Grant a role to a member of this space, or invite someone by email." },
  { screen: "StaffApp/platform-access", phase: "empty", source: "features/staff/platformParity/AccountsSection.tsx", text: 'No account is called "d12-operator".' },
];
// Shared 404s deliberately hide whether a public resource is private, missing or
// switched off. Decision 576 requires that real presentation contract; typed
// 404/module_disabled is independently asserted, never changed to not_found.
const hidden404 = new Set(["PublicOrganizationDirectory", "PublicOrganizationPage", "PublicEventCodePage",
  "ProfileByAccountPage", "PublicHandlePage"]);
export function screenCopyFor(row: RouteCase, phase: Phase) {
  const text = SCREEN_COPY.filter(item => item.screen === row.screen && item.phase === phase).map(item => item.text);
  if ((phase === "empty" || phase === "module") && hidden404.has(row.screen)) text.push("We couldn't find that page");
  if (["permission", "module"].includes(phase) || phase === "empty" && row.screen === "UseMachinePage") {
    if (row.screen === "MachineJobPage") text.push("We couldn't find that job in your account.");
    if (row.screen === "UseMachinePage") text.push("This machine isn't available for sessions here. Ask staff if you think it should be.");
  }
  if (phase === "module" && row.screen === "PresenceNowPage") text.push("This display isn't available for this makerspace.");
  if (phase === "module" && row.screen === "SupervisedSessionsPage") text.push("Machines are switched off for this space.");
  if (phase === "module" && row.screen === "DonatePage") text.push("This space isn't taking donations online right now.");
  if (phase === "permission" && row.screen === "MemberEventHistoryPage") text.push("No event history here yet. Events you register for or speak at will appear here.");
  if (phase === "empty" && row.screen === "PublicMachineServiceStatusPage") text.push("We couldn't find that job, or it isn't trackable any more.");
  if (row.screen === "StaffApp/settings" && ["empty", "error", "permission", "module"].includes(phase)) {
    const detail = { empty: "Census record not found.", error: "Census service unavailable.",
      permission: "Census access denied.", module: "Census module is disabled." }[phase as Exclude<Phase, "loading">];
    text.push(`Couldn't load the latest settings (${detail}). Showing the last known values.`);
  }
  return text;
}

// A wall display has no input device (decision 307, Anthias kiosks): its outage
// retry is the poll itself, so the census waits for the next real request instead.
export const AUTO_RETRY = [
  { screen: "SpaceDisplayPage", source: "features/spaceDisplay/useDisplayScreen.ts", ms: 5000,
    reason: "refetchInterval polls again RETRY_MS after a failure and keeps the last good state." },
] as const;
export function autoRetryFor(row: RouteCase) { return AUTO_RETRY.find(item => item.screen === row.screen); }

export const EMPTY_FORMS = [
  { screen: "OrganizationInvitationRedeemPage", source: "features/organizations/OrganizationInvitationRedeemPage.tsx",
    reason: "Redeeming a valid single-use invitation returns access, not a collection with an empty state.",
    role: "heading", name: "You're in" },
  { screen: "DonatePage", source: "features/donations/DonatePage.tsx",
    reason: "A donation page with no campaigns or suggested amounts still presents its custom-amount form.",
    role: "form", name: "Give to this space" },
  { screen: "HostingInvitePage", source: "features/hosting/HostingInvitePage.tsx",
    reason: "Resolving a valid invitation opens an editable hosting request; it is not an empty list.",
    role: "heading", name: "Host your makerspace" },
  { screen: "MemberAccountPage", source: "features/members/MemberAccountProfile.tsx",
    reason: "A successful singleton account profile is edited in place; blank optional contact fields do not form an empty list.",
    role: "textbox", name: "Display name" },
  { screen: "MemberProfilePage", source: "features/profile/edit/StatusAboutFields.tsx",
    reason: "A successful blank account profile opens its editor; optional profile fields have no list-empty state.",
    role: "textbox", name: "Headline" },
  { screen: "MemberArea/account", source: "features/profile/edit/StatusAboutFields.tsx",
    reason: "The account portal uses the same singleton profile editor when no optional profile values are saved.",
    role: "textbox", name: "Headline" },
  { screen: "TeamPage", source: "features/events/hackathonAdmission/TeamEditor.tsx",
    reason: "No team opens the real creation form; the solo alternative has its own explanatory sentence.",
    role: "button", name: "Create team" },
  { screen: "HackathonApplicationPage", source: "features/events/hackathonAdmission/ApplicationStatus.tsx",
    reason: "An application is a singleton: a successful record with no answers opens its own status page, not an empty list.",
    role: "heading", name: "Your application" },
  { screen: "ProgrammeAccountPage", path: "/saved-details", source: "features/accountSavedDetails/SavedDetailsPage.tsx",
    reason: "An empty private vault renders the same editable fields for first entry; security activity remains a list.",
    role: "heading", name: "Your private account vault" },
  { screen: "MemberEventTicketPage", source: "features/events/MemberEventTicketPage.tsx",
    reason: "A registration's ticket is a singleton; a successful unconfirmed registration explains when its download appears.",
    role: "heading", name: "Your event ticket" },
  { screen: "AttendanceReplyPage", source: "features/events/participation/AttendanceReplyPage.tsx",
    reason: "A successful attendance record is a singleton question with the member's own answer; it is not a collection.",
    role: "heading", name: "Are you still coming?" },
  { screen: "CrewSignupPage", source: "features/events/participation/CrewSignupPage.tsx",
    reason: "A successful crew state with no crew place opens the sign-up form; it is not a collection.",
    role: "heading", name: "Join the crew" },
  { leaf: "SecuritySettingsPanel", source: "features/staff/SecuritySettingsPanel.tsx",
    reason: "The singleton sign-in policy always explains required staff MFA, even with no delegated settings.",
    role: "heading", name: "Sign-in requirements" },
] as const;
export function emptyFormFor(row: RouteCase) {
  return EMPTY_FORMS.find(item => "leaf" in item ? row.leaves?.includes(item.leaf)
    : row.screen === item.screen && (!("path" in item) || row.path.endsWith(item.path)));
}
