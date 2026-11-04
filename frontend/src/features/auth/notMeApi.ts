import { API_V1_URL } from "../../lib/api";
import { apiError } from "../../lib/api/errors";

/**
 * STUB(S-B): `POST auth/security-alerts/not-me` from S-B's brief (token-only, no cookie, no
 * session). The body is the fragment token; the response shape is not frozen, so only success
 * or a structured error (`security_alert_used`) is read.
 */
export async function reportNotMe(token: string) {
  const response = await fetch(`${API_V1_URL}/auth/security-alerts/not-me`, {
    method: "POST", credentials: "omit", referrerPolicy: "no-referrer",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }),
  });
  if (!response.ok) throw apiError(response.status, await response.json().catch(() => ({})), response.headers);
}
