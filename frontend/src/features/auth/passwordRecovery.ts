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

// Kept beside the caller until the reviewed OpenAPI snapshot is regenerated.
export type RecoveryContext = { context: "staff"; makerspace: string } | { context: "platform" };
type ContextFields = RecoveryContext | { context?: "member" };

export function requestPasswordReset(payload: ForgotPasswordRequest & ContextFields) {
  return publicV1Request<PasswordResetAcknowledgement>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify(payload),
    ...(payload.context && payload.context !== "member" ? { headers: { Authorization: "" } } : {}),
  });
}

export function confirmOtpPasswordReset(payload: OtpResetPasswordConfirm & ContextFields) {
  return publicV1Request<PasswordUpdated>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify(payload),
    ...(payload.context && payload.context !== "member" ? { headers: { Authorization: "" } } : {}),
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
