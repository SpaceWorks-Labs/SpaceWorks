import type { NotMeResult } from "../../generated/api";
import { API_V1_URL } from "../../lib/api";
import { apiError } from "../../lib/api/errors";

/**
 * `POST auth/security-alerts/not-me` (S-B). Token-only: no cookie and no bearer travel, and a
 * refusal is `security_alert_used` (400). `mfa_reset` names who may reset two-step sign-in.
 */
export type { NotMeResult };

export async function reportNotMe(token: string): Promise<NotMeResult> {
  const response = await fetch(`${API_V1_URL}/auth/security-alerts/not-me`, {
    method: "POST", credentials: "omit", referrerPolicy: "no-referrer",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw apiError(response.status, data, response.headers);
  return data as NotMeResult;
}
