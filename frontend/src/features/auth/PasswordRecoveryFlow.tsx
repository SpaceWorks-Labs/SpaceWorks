import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";
import { NewPasswordFields } from "./NewPasswordFields";
import {
  CONFIRM_FAILURE_MESSAGE,
  RESEND_COOLDOWN_SECONDS,
  confirmOtpPasswordReset,
  isRecoveryUnavailable,
  requestPasswordReset,
  type RecoveryContext,
} from "./passwordRecovery";
type RecoveryStep = "request" | "confirm" | "success" | "unavailable";

export function PasswordRecoveryFlow({ recoveryContext, signInHref = "/admin", initialStep = "request" }: {
  recoveryContext?: RecoveryContext;
  signInHref?: string;
  initialStep?: "request" | "confirm";
}) {
  const [step, setStep] = useState<RecoveryStep>(initialStep);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [acknowledgement, setAcknowledgement] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const counting = cooldown > 0;
  useEffect(() => {
    if (!counting) return;
    const timer = window.setInterval(() => {
      setCooldown((seconds) => Math.max(0, seconds - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [counting]);
  const requestCode = async (isResend: boolean) => {
    setPending(true);
    setError("");
    try {
      const result = await requestPasswordReset({ email: email.trim(), ...recoveryContext });
      setAcknowledgement(result.detail);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      if (!isResend) setStep("confirm");
    } catch (requestError) {
      if (isRecoveryUnavailable(requestError)) {
        setStep("unavailable");
      } else {
        setError(t`Unable to request password recovery. Please try again.`);
      }
    } finally {
      setPending(false);
    }
  };
  const submitConfirmation = async () => {
    setPending(true);
    setError("");
    try {
      await confirmOtpPasswordReset({ email: email.trim(), code, new_password: newPassword, ...recoveryContext });
      setStep("success");
    } catch {
      // All server rejections intentionally share one message. Showing password-policy
      // details only after a valid OTP would recreate an account-existence oracle.
      setError(CONFIRM_FAILURE_MESSAGE);
    } finally {
      setPending(false);
    }
  };
  const canConfirm = /^\d{6}$/.test(code)
    && Boolean(email.trim())
    && newPassword.length >= 8
    && newPassword === confirmPassword
    && !pending;
  const titles = { request: "Reset password", confirm: "Enter your recovery code", success: "Password updated", unavailable: "Password recovery unavailable" };
  const body = step === "request" ? recoveryContext ? t`Enter your account username or email to request a six-digit recovery code.` : t`Enter your account email to request a six-digit recovery code.`
    : step === "confirm" ? acknowledgement || "Enter your username or email and the six-digit recovery code from your email."
    : step === "success" ? `Your password has been updated. You can now sign in.${recoveryContext ? " Authenticator verification is still required if enabled for your account." : ""}`
    : "Password recovery is unavailable on this deployment — contact your makerspace staff";
  return <CenteredCardLayout state={{ status: "ready" }} eyebrow={recoveryContext ? t`Platform account access` : t`Account access`}
    media={{ icon: step === "success" ? "Check" : step === "confirm" ? "Mail" : "KeyRound", tone: step === "success" ? "success" : "accent" }}
    title={titles[step]} body={<p role={step === "unavailable" ? "alert" : undefined}>{body}</p>}
    primary={step === "success" || step === "unavailable" ? { label: step === "success" ? t`Go to sign in` : t`Back to sign in`, href: signInHref } : {
      label: step === "request" ? t`Request recovery code` : t`Update password`, pending,
      pendingLabel: step === "request" ? t`Requesting…` : t`Updating…`, disabled: step === "confirm" && !canConfirm,
      disabledReason: "Enter the six-digit code and matching passwords.",
      onClick: () => (document.getElementById("password-recovery-form") as HTMLFormElement)?.requestSubmit(),
    }}
    escape={step === "request" ? { label: t`Back to sign in`, href: signInHref } : step === "confirm" ? {
      label: cooldown > 0 ? t`Request another code in ${cooldown}s` : t`Request another code`,
      disabled: pending || cooldown > 0 || !email.trim(), disabledReason: "Enter your account identifier and wait before requesting another code.", onClick: () => void requestCode(true),
    } : undefined}
    content={step === "request" || step === "confirm" ? <form id="password-recovery-form" className="grid gap-2"
      onSubmit={(event) => { event.preventDefault(); if (step === "request" && !pending) void requestCode(false); else if (canConfirm) void submitConfirmation(); }}>
      {step === "request" || recoveryContext ? <label className="grid gap-2 text-sm font-semibold" htmlFor="recovery-email">{recoveryContext ? t`Username or email` : t`Email`}
        <input id="recovery-email" className="desk-input w-full" name="email" autoComplete={recoveryContext ? "username" : "email"} type={recoveryContext ? "text" : "email"} required
          value={email} onChange={(event) => setEmail(event.target.value)} />
      </label> : null}
      {step === "confirm" ? <>
        <p className="text-sm text-muted">{t`Email delivery runs on a schedule and may take a few minutes.`}</p>
        <label className="mt-3 grid gap-2 text-sm font-semibold" htmlFor="recovery-code">{t`Six-digit code`}<input id="recovery-code" className="desk-input w-full" autoComplete="one-time-code" inputMode="numeric"
            pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} />
        </label>
        <NewPasswordFields idPrefix="otp-reset" newPassword={newPassword} confirmPassword={confirmPassword}
          onNewPasswordChange={setNewPassword} onConfirmPasswordChange={setConfirmPassword} />
      </> : null}
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}
    <button type="submit" disabled={pending} hidden aria-hidden="true" tabIndex={-1} />
    </form> : undefined} />;
}
