import { API_V1_URL } from "../../lib/api";
import type { PasswordLoginResponse, StaffAuthUser } from "../../lib/api";
import { apiError } from "../../lib/api/errors";

/** The frozen `factors[]` vocabulary (`login_security_contract.FACTORS`), in the server's order. */
export type MfaFactor = "totp" | "passkey" | "recovery" | "email_code";

export type MfaChallenge = {
  mfa_required: true;
  enrollment_required: boolean;
  challenge: string;
  expires_in: number;
  // STUB(S-B): S-B adds these to the challenge (its brief: "the challenge gains `purpose` and
  // `factors[]`"; codes allow <=2 resends). Until then they are absent and the flow behaves as
  // before (authenticator or recovery code).
  purpose?: string;
  factors?: MfaFactor[];
  resends_left?: number;
};
export type MfaCompleted = PasswordLoginResponse<StaffAuthUser> & { recovery_codes?: string[] };
export type Enrollment = { secret: string; provisioning_uri: string; qr_data_url: string };
export function isMfaChallenge(value: unknown): value is MfaChallenge {
  return typeof value === "object" && value !== null && "mfa_required" in value && value.mfa_required === true;
}

// A challenge never travels as a full account Authorization header, and must never
// trigger the shared client's refresh retry when a verification attempt gets a 401.
export async function mfaRequest<T>(path: string, body: object, headers: Record<string, string> = {}): Promise<T> {
  const response = await fetch(`${API_V1_URL}${path}`, {
    method: "POST", credentials: "include", headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw apiError(response.status, typeof data?.detail === "string" ? data : { ...data, detail: "Unable to verify. Try again." },
      response.headers);
  }
  return data as T;
}

/** STUB(S-B): `POST auth/login-code/resend` from S-B's brief; the response shape is assumed. */
export const resendLoginCode = (challenge: string, headers?: Record<string, string>) =>
  mfaRequest<{ resends_left?: number }>("/auth/login-code/resend", { challenge }, headers);
