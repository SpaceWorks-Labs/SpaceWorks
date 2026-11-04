import { getAccessToken, staffRequest } from "../../lib/api";
import { browserSessionIdentity } from "../../lib/api/reauthentication";

export type ReauthenticationStatus = {
  verified: boolean;
  password_available: boolean;
  mfa_enabled: boolean;
  providers: string[];
};
export type ReauthenticationResult = { verified: boolean; mfa_required?: boolean; expires_in: number; factor_required?: "totp" | "phone" | "email_code"; factor_token?: string };
export const reauthenticationKey = ["reauthentication-status"] as const;
export const reauthenticationSessionKey = () => [...reauthenticationKey, browserSessionIdentity(getAccessToken())] as const;
export const reauthenticationStatus = () => staffRequest<ReauthenticationStatus>("/auth/reauth");
export const verifyIdentity = (password: string, code: string) => staffRequest<ReauthenticationResult>("/auth/reauth", {
  method: "POST", body: JSON.stringify({ password, code }),
});
export const requestEnrollmentEmail = () => staffRequest<{ sent: boolean }>("/auth/reauth/enrollment/email", { method: "POST", body: "{}" });
export const confirmEnrollmentEmail = (token: string) => staffRequest<{ confirmed: boolean }>("/auth/reauth/enrollment/confirm", {
  method: "POST", body: JSON.stringify({ token }),
});
