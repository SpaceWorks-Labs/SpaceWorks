import type { StaffAuthUser } from "../../lib/api";

/** The platform superadmin: a separate account that holds every Space-Manager action (#115). */
export const isSuperadminUser = (user: StaffAuthUser) => user.is_superuser || user.role === "superadmin";

/**
 * Makerspaces a PERSON may open the console for (one account per person): every space
 * where this session holds a staff role, plus spaces reached through organization authority
 * or an event/booking grant. A community membership alone never opens the console.
 */
export function consoleSpaceIds(user: StaffAuthUser): Set<number> {
  const ids = new Set<number>();
  user.staff_roles?.forEach(entry => ids.add(entry.makerspace.id));
  user.makerspaces.forEach(space => { if (space.source === "organization" && space.actions.length) ids.add(space.id); });
  user.event_grants?.forEach(grant => ids.add(grant.makerspace_id));
  user.booking_grants?.forEach(grant => ids.add(grant.makerspace_id));
  return ids;
}

/** Whether the console is for this account at all (staff role, delegated grant or organization authority). */
export function hasConsoleAccess(user: StaffAuthUser) {
  return isSuperadminUser(user) || Boolean(user.has_elevated_authority) || consoleSpaceIds(user).size > 0;
}

export type MfaGate = "none" | "grace" | "required";

/**
 * #128 C-1: an unenrolled staff person may use staff screens for 3 days with a banner at each
 * sign-in; after that the console asks them to set up two-step sign-in. The server enforces
 * it (403 `mfa_enrollment_required`); this only picks the screen. The superadmin is exempt.
 */
export function mfaGate(user: StaffAuthUser, now = Date.now()): MfaGate {
  if (isSuperadminUser(user) || !user.mfa_enrolment_due) return "none";
  const ends = user.mfa_grace_ends_at ? Date.parse(user.mfa_grace_ends_at) : Number.NaN;
  return Number.isFinite(ends) && ends > now ? "grace" : "required";
}
