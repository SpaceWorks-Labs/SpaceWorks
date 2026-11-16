/**
 * The shared "set up two-step sign-in" signal (#128 C-1; shared with S-D).
 *
 * After a person's 3-day staff grace, every staff API call (and a refresh) answers
 * `mfa_enrollment_required`. `staffFetch` reports it here and the staff console listens,
 * so it can swap to the enrolment screen in place. Member screens never subscribe: their
 * features are never blocked.
 */
export const MFA_ENROLLMENT_REQUIRED = "mfa_enrollment_required";

const listeners = new Set<() => void>();

export function onMfaEnrollmentRequired(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function notifyMfaEnrollmentRequired() {
  listeners.forEach(listener => listener());
}

/** True when an API error body names the enrolment requirement. */
export async function requiresMfaEnrollment(response: Response) {
  if (response.status !== 401 && response.status !== 403) return false;
  const body = await response.clone().json().catch(() => null) as { code?: string; detail?: { code?: string } } | null;
  return body?.code === MFA_ENROLLMENT_REQUIRED || body?.detail?.code === MFA_ENROLLMENT_REQUIRED;
}
