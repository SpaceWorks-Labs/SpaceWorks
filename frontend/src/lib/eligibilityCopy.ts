import { t } from "@lingui/core/macro";

// Imported from the module itself, not the `lib/api` barrel, so a test that mocks the
// barrel still gets the real class here.
import { StructuredApiError } from "./api/errors";
import { guestRefusalMessage } from "./guestRefusalCopy";

/**
 * Decision 216 item 12: one place that turns the server's member-eligibility and
 * delegated-authority refusals into "what is wrong + what to do / who to ask".
 * Server behaviour is unchanged; anything not listed returns null so each surface keeps
 * its own fallback.
 */

/** The refusal code, including DRF's list shape (`ValidationError({"code": ...})` answers `{code: [...]}`). */
export function refusalCode(error: unknown): string | undefined {
  if (!(error instanceof StructuredApiError)) return undefined;
  if (error.code) return error.code;
  const code = error.body.code;
  return Array.isArray(code) && typeof code[0] === "string" ? code[0] : undefined;
}

function certificationNames(error: StructuredApiError, field = "certifications"): string {
  const names = error.body[field];
  if (!Array.isArray(names)) return "";
  return names.filter((name): name is string => typeof name === "string" && name.trim() !== "").join(", ");
}

/** Clear copy for an eligibility/delegation refusal, or null when the error is something else. */
export function eligibilityMessage(error: unknown): string | null {
  const code = refusalCode(error);
  if (!code || !(error instanceof StructuredApiError)) return null;
  switch (code) {
    // Identity, membership, waiver and presence (presence/guard.py, request_access.require_current_term).
    case "membership_required":
      return t`This needs an active membership of this space. Join or renew from your member area, or ask space staff if you think your membership should be active.`;
    case "membership_inactive":
      return t`Your membership of this space is not active. Ask space staff to review it.`;
    case "membership_lapsed":
      return t`Your membership term has ended. Renew your membership from your member area, then try again.`;
    case "waiver_acceptance_required":
      return t`Accept the space's current waiver in your member area, then try again.`;
    case "presence_required":
      return t`Check in at the space first (in your member area or at the front desk), then try again.`;
    case "borrower_restricted":
    case "member_restricted":
      return t`Your account is restricted at this space. Talk to space staff to resolve it.`;
    // Machine certification (machines/certifications.py) — bookings, sessions, service work.
    case "certification_required": {
      const names = certificationNames(error);
      return names
        ? t`You need machine training or certification first (${names}). Ask space staff how to qualify, then try again.`
        : t`You need machine training or certification first. Ask space staff how to qualify, then try again.`;
    }
    // Event-only lending (decision 221b): request intake, self-checkout and direct handout refuse it.
    case "event_only_product": {
      const names = certificationNames(error, "products");
      return names
        ? t`These items are lent only through an event: ${names}. Remove them, or ask the event organizers to request them for you.`
        : t`This item is lent only through an event. Ask the event organizers to request it for you.`;
    }
    // Loan renewal (hardware_requests/renewal_workflow.py).
    case "self_renewal_off":
      return t`You can't renew loans yourself here. Ask space staff to renew it.`;
    case "renewal_limit":
      return t`This loan has reached its renewal limit. Return it, or ask space staff.`;
    case "renewals_off":
      return t`Loan renewals are switched off in this space. Ask space staff.`;
    case "machine_intake_unavailable":
      return t`Online machine requests aren't available here. Ask space staff for help.`;
    // Organization audiences for events (events/organization_audience.py).
    case "organization_audience_required":
      return t`This event is open to members of its participating organizations. Ask your organization to confirm your membership, or contact the organizers.`;
    case "organization_audience_not_ready":
      return t`Staff must review this event's audience before registration opens. Try again later or contact the organizers.`;
    case "organization_audience_disabled":
      return t`This event isn't taking organization registrations right now. Contact the organizers.`;
    case "organization_audience_changed":
      return t`This event's audience changed. Reload the page to check whether you can still register.`;
    // Organization invitations and delegated authority (organizations/exceptions.py).
    case "invitation_expired":
      return t`This invitation has expired. Ask an organization governor to send a new one.`;
    case "invitation_revoked":
      return t`This invitation was withdrawn. Ask an organization governor if you should still have access.`;
    case "invitation_redeemed":
      return t`This invitation has already been used. If that wasn't you, tell an organization governor.`;
    case "invitation_grant_changed":
      return t`The person who invited you no longer holds all of the access they offered. Ask an organization governor to send a new invitation.`;
    case "organization_membership_suspended":
      return t`Your membership of this organization is suspended. Ask an organization governor to reactivate it.`;
    default:
      return guestRefusalMessage(code);
  }
}
