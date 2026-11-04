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
  // STUB(S-B): S-B's `MFAChallengeResponseSerializer` (lane/r2-s-b efae28ce) adds these; swap
  // for the generated type at the S-B merge. A challenge from before S-B has neither, and the
  // flow then behaves as before (authenticator or recovery code). `risk` is the unusual-sign-in
  // check: a 6-digit code was emailed (factor `email_code`, two resends).
  purpose?: "login" | "risk";
  factors?: MfaFactor[];
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

/** STUB(S-B): `POST auth/login-code/resend`, typed from S-B's `LoginCodeResentSerializer` (efae28ce). */
export type LoginCodeResent = { sent: boolean; expires_in: number; resends_left: number };
export const resendLoginCode = (challenge: string, headers?: Record<string, string>) =>
  mfaRequest<LoginCodeResent>("/auth/login-code/resend", { challenge }, headers);
