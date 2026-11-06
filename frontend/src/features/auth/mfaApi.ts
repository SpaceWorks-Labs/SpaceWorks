import { t } from "@lingui/core/macro";
import type { FactorsEnum, LoginCodeResent, MFAChallengeResponse } from "../../generated/api";
import { API_V1_URL } from "../../lib/api";
import type { PasswordLoginResponse, StaffAuthUser } from "../../lib/api";
import { apiError } from "../../lib/api/errors";

/** The frozen `factors[]` vocabulary (`login_security_contract.FACTORS`), in the server's order. */
export type MfaFactor = FactorsEnum;

// S-B's challenge: `purpose` and `factors[]` are optional, and without them the flow behaves as
// before (authenticator or recovery code). `risk` is the unusual-sign-in check: a 6-digit code
// was emailed (factor `email_code`, two resends). `mfa_required` is narrowed for the type guard.
export type MfaChallenge = Omit<MFAChallengeResponse, "mfa_required"> & { mfa_required: true };
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
    throw apiError(response.status, typeof data?.detail === "string" ? data : { ...data, detail: t`Unable to verify. Try again.` },
      response.headers);
  }
  return data as T;
}

/** `POST auth/login-code/resend` (S-B). */
export type { LoginCodeResent };
export const resendLoginCode = (challenge: string, headers?: Record<string, string>) =>
  mfaRequest<LoginCodeResent>("/auth/login-code/resend", { challenge }, headers);
