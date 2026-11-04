import type {
  ForgotPasswordRequest,
  LegacyResetPasswordConfirm,
  OtpResetPasswordConfirm,
  PasswordResetAcknowledgement,
  PasswordUpdated,
} from "../../generated/api";
import { publicV1Request } from "../../lib/api";

export const CONFIRM_FAILURE_MESSAGE = "Invalid or expired verification code.";
export const RESEND_COOLDOWN_SECONDS = 60;

// Release 2 (one account per person): recovery is person (the default) or platform only.
export type RecoveryContext = { context: "platform" };
type ContextFields = RecoveryContext | { context?: "member" | "person" };

export function requestPasswordReset(payload: ForgotPasswordRequest & ContextFields) {
  return publicV1Request<PasswordResetAcknowledgement>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
    ...(payload.context === "platform" ? { headers: { Authorization: "" } } : {}),
  });
}

export function confirmOtpPasswordReset(payload: OtpResetPasswordConfirm & ContextFields) {
  return publicV1Request<PasswordUpdated>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
    ...(payload.context === "platform" ? { headers: { Authorization: "" } } : {}),
  });
}

export function confirmLegacyPasswordReset(payload: LegacyResetPasswordConfirm) {
  return publicV1Request<PasswordUpdated>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function isRecoveryUnavailable(error: unknown) {
  return Boolean(
    error
      && typeof error === "object"
      && "code" in error
      && error.code === "recovery_unavailable",
  );
}
