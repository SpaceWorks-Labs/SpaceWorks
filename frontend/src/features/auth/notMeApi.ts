import { API_V1_URL } from "../../lib/api";
import { apiError } from "../../lib/api/errors";

/**
 * STUB(S-B): `POST auth/security-alerts/not-me`, hand-typed from S-B's `NotMeResultSerializer`
 * on lane/r2-s-b (efae28ce); swap for the generated type at the S-B merge. Token-only: no
 * cookie and no bearer travel, and a refusal is `security_alert_used` (400).
 */
export type NotMeResult = {
  signed_out: boolean;
  /** A reset code was requested for the account email (sent unless recovery mail is off). */
  password_reset_requested: boolean;
  /** Who may reset two-step sign-in for this person (the MFA-reset rule). */
  mfa_reset: { superadmin: boolean; space_managers_of: { name: string; slug: string }[] };
};

export async function reportNotMe(token: string): Promise<NotMeResult> {
  const response = await fetch(`${API_V1_URL}/auth/security-alerts/not-me`, {
    method: "POST", credentials: "omit", referrerPolicy: "no-referrer",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw apiError(response.status, data, response.headers);
  return data as NotMeResult;
}
