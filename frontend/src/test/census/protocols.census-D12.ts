import type { RouteCase } from "./source.census-D12";

export type BrowserCommand = {
  path: string; body: unknown; fragment: string; button: string; idle: string;
  search?: Record<string, string>; inputs?: { label: string; value: string }[];
  checks?: string[]; disclosure?: string; operation?: boolean;
  file?: { label: string; name: string };
};
const PROOF = "d12-enrollment-proof";
const EMAIL = "d12@example.test";
export function effectFor(row: RouteCase) {
  if (row.screen === "HostingInvitePage") return { path: "/public/hosting/invitations/resolve", body: { token: PROOF }, fragment: `#token=${PROOF}` };
  if (row.screen === "HostingRequestStatusPage") return { path: "/public/hosting/requests/open", body: { token: PROOF }, fragment: `#token=${PROOF}` };
}

// Browser proofs and native form validation are absent from response schemas.
// Each adapter names the production protocol; no evidence/OTP gate is bypassed.
export function protocolFor(row: RouteCase): BrowserCommand | undefined {
  if (row.screen === "PublicSelfCheckoutPage") return {
    path: "/public/lab/tools/evidence-url", body: { evidence_type: "issue", content_type: "image/png", size: 3, size_bytes: 3 },
    fragment: "", button: "Issue photo", idle: "Take a photo of the tool, then scan its QR label.",
    file: { label: "Issue photo", name: "d12-evidence.png" },
  };
  if (row.leaves?.includes("BulkImport")) return {
    path: "/admin/makerspace/1/inventory/import/preview", body: { rows: [{ name: "New Kit", total_quantity: "1", available_quantity: "1" }] },
    fragment: "", button: "Preview JSON", disclosure: "Use JSON instead",
    idle: "Add or update inventory from a spreadsheet. Review every change before importing.",
  };
  if (row.screen === "TakeTeamInvitation") return {
    path: `/member/makerspaces/9/events/42/teams/${row.path.split("/").pop()}/accept`, body: { expected_version: 1, token: "a".repeat(64) },
    fragment: `#token=${"a".repeat(64)}`, search: { version: "1" }, button: "Accept invitation",
    idle: "This invitation is private and can be used once. Your own application and eligibility still apply.", checks: ["I want to join this team."], operation: true,
  };
  if (row.screen === "OrdinaryProgrammeRegistration") return {
    path: "/public/workshop/events/11111111-2222-4333-8444-555555555555/register", fragment: "", button: "Register", operation: true,
    idle: "Review what you share and what you save privately.",
    body: { form: { schema_version: 2, form_id: "hackathon-application", revision: 3 }, answers: { institution: "D12 Institute" },
      derivations: {}, save_choices: { institution: false }, saved_detail_versions: { institution: 0 }, event_date_revision: 7,
      host_waiver_accepted: false, ticket_type_id: 8, email: EMAIL, phone: "+919876543210", expected_version: 0 },
    inputs: [{ label: "Ticket", value: "8" }, { label: "Contact email", value: EMAIL }, { label: "Contact phone", value: "+919876543210" },
      { label: "School or organisation", value: "D12 Institute" }],
  };
  if (["KioskStationPage", "EventCheckInStationPage"].includes(row.screen)) {
    const event = row.screen === "EventCheckInStationPage";
    const slugAt = row.pattern.split("/").indexOf(":slug");
    const slug = slugAt < 0 ? undefined : row.path.split("/")[slugAt];
    return { path: `/${event ? "event-checkin-stations" : "kiosk-stations"}/${row.path.split("/").pop()}/session`,
      body: { pin: "12345678", ...(!event && slug ? { makerspace_slug: slug } : {}) }, fragment: "", button: "Unlock station",
      idle: event ? "Ask an organiser for the 8-digit PIN. It unlocks check-in on this device only."
        : "Ask a manager for the 8-digit PIN. It unlocks this device only.", inputs: [{ label: "Station PIN", value: "12345678" }] };
  }
  if (["ResetPasswordPage", "ConsolePasswordResetPage"].includes(row.screen)) {
    const platform = row.screen === "ConsolePasswordResetPage" && row.mode === "central" && !row.pattern.includes(":slug");
    return { path: "/auth/forgot-password", body: { email: EMAIL, ...(platform ? { context: "platform" } : {}) },
      fragment: "", search: { step: "request" }, button: "Request recovery code",
      idle: platform ? "Enter your account username or email to request a six-digit recovery code."
        : "Enter your account email to request a six-digit recovery code.",
      inputs: [{ label: platform ? "Username or email" : "Email", value: EMAIL }] };
  }
  if (row.screen === "AccountRestorePage") return {
    path: "/auth/account/restore/email", body: { email: EMAIL, token: PROOF, new_password: "D12-valid-password-2026!" },
    fragment: `#email=${encodeURIComponent(EMAIL)}&token=${PROOF}`, button: "Restore account",
    idle: "You can come back before the archive deadline and before identity removal starts. Choose a new password. Previous memberships, sessions and device access remain revoked.",
    inputs: [{ label: "New password", value: "D12-valid-password-2026!" }],
  };
  if (row.screen === "StaffInvitationAcceptPage") return {
    path: "/auth/staff-invitations/accept", body: { token: PROOF, makerspace_slug: "lab" },
    fragment: `#token=${PROOF}&space=lab`, button: "Email me a code",
    idle: "The staff role is added to the account you're signed in to. We'll email a code to the invited address to confirm it's yours.",
  };
  if (row.screen === "InviteAcceptPage") return {
    path: "/member/id-programme-invites/accept", body: { card: 1, invite: PROOF }, fragment: "", search: { card: "1", invite: PROOF },
    button: "Accept the invite", idle: "This links the card to the account you're signed in with. Use the account whose email received the invite.",
  };
  if (row.screen === "NotMePage") return {
    path: "/auth/security-alerts/not-me", body: { token: PROOF }, fragment: `#token=${PROOF}`, button: "Secure my account",
    idle: "If you don't recognise the activity in the email, secure your account now. This will:",
  };
  return undefined;
}
