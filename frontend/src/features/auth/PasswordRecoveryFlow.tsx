import { useEffect, useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";
import { NewPasswordFields } from "./NewPasswordFields";
import {
  CONFIRM_FAILURE_MESSAGE,
  RESEND_COOLDOWN_SECONDS,
  confirmOtpPasswordReset,
  isRecoveryUnavailable,
  requestPasswordReset,
} from "./passwordRecovery";
type RecoveryStep = "request" | "confirm" | "success" | "unavailable";

export function PasswordRecoveryFlow() {
  const [step, setStep] = useState<RecoveryStep>("request");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [acknowledgement, setAcknowledgement] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(() => {
      setCooldown((seconds) => Math.max(0, seconds - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [cooldown > 0]);
  const requestCode = async (isResend: boolean) => {
    setPending(true);
    setError("");
    try {
      const result = await requestPasswordReset({ email });
      setAcknowledgement(result.detail);
      setCooldown(RESEND_COOLDOWN_SECONDS);
      if (!isResend) setStep("confirm");
    } catch (requestError) {
      if (isRecoveryUnavailable(requestError)) {
        setStep("unavailable");
      } else {
        setError("Unable to request password recovery. Please try again.");
      }
    } finally {
      setPending(false);
    }
  };
  const submitConfirmation = async () => {
    setPending(true);
    setError("");
    try {
      await confirmOtpPasswordReset({ email, code, new_password: newPassword });
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
    && newPassword.length >= 8
    && newPassword === confirmPassword
    && !pending;
  const titles = { request: "Reset password", confirm: "Enter your recovery code", success: "Password updated", unavailable: "Password recovery unavailable" };
  const body = step === "request" ? "Enter your account email to request a six-digit recovery code."
    : step === "confirm" ? acknowledgement
    : step === "success" ? "Your password has been updated. You can now sign in."
    : "Password recovery is unavailable on this deployment — contact your makerspace staff";
  return <CenteredCardLayout state={{ status: "ready" }} eyebrow="Account access"
    media={{ icon: step === "success" ? "Check" : step === "confirm" ? "Mail" : "KeyRound", tone: step === "success" ? "success" : "accent" }}
    title={titles[step]} body={<p role={step === "unavailable" ? "alert" : undefined}>{body}</p>}
    primary={step === "success" || step === "unavailable" ? { label: step === "success" ? "Go to sign in" : "Back to sign in", href: "/admin" } : {
      label: step === "request" ? "Request recovery code" : "Update password", pending,
      pendingLabel: step === "request" ? "Requesting…" : "Updating…", disabled: step === "confirm" && !canConfirm,
      disabledReason: "Enter the six-digit code and matching passwords.",
      onClick: () => (document.getElementById("password-recovery-form") as HTMLFormElement)?.requestSubmit(),
    }}
    escape={step === "request" ? { label: "Back to sign in", href: "/admin" } : step === "confirm" ? {
      label: cooldown > 0 ? `Request another code in ${cooldown}s` : "Request another code",
      disabled: pending || cooldown > 0, disabledReason: "Wait before requesting another code.", onClick: () => void requestCode(true),
    } : undefined}
    content={step === "request" || step === "confirm" ? <form id="password-recovery-form" className="grid gap-2"
      onSubmit={(event) => { event.preventDefault(); if (step === "request" && !pending) void requestCode(false); else if (canConfirm) void submitConfirmation(); }}>
      {step === "request" ? <label className="grid gap-2 text-sm font-semibold" htmlFor="recovery-email">Email
        <input id="recovery-email" className="desk-input w-full" name="email" autoComplete="email" type="email" required
          value={email} onChange={(event) => setEmail(event.target.value)} />
      </label> : <>
        <p className="text-sm text-muted">Email delivery runs on a schedule and may take a few minutes.</p>
        <label className="mt-3 grid gap-2 text-sm font-semibold" htmlFor="recovery-code">Six-digit code
          <input id="recovery-code" className="desk-input w-full" autoComplete="one-time-code" inputMode="numeric"
            pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} />
        </label>
        <NewPasswordFields idPrefix="otp-reset" newPassword={newPassword} confirmPassword={confirmPassword}
          onNewPasswordChange={setNewPassword} onConfirmPasswordChange={setConfirmPassword} />
      </>}
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}
    <button type="submit" disabled={pending} hidden aria-hidden="true" tabIndex={-1} />
    </form> : undefined} />;
}
