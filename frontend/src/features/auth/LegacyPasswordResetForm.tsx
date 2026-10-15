import { useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";
import { NewPasswordFields } from "./NewPasswordFields";
import { CONFIRM_FAILURE_MESSAGE, confirmLegacyPasswordReset } from "./passwordRecovery";

export function LegacyPasswordResetForm({ uid, token }: { uid: string; token: string }) {
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [updated, setUpdated] = useState(false);
  const canSubmit = newPassword.length >= 8
    && newPassword === confirmPassword
    && !pending;
  const submit = async () => {
    setPending(true);
    setError("");
    try {
      await confirmLegacyPasswordReset({ uid, token, new_password: newPassword });
      setUpdated(true);
    } catch {
      setError(CONFIRM_FAILURE_MESSAGE);
    } finally {
      setPending(false);
    }
  };
  return <CenteredCardLayout state={{ status: "ready" }} eyebrow="Account access"
    media={{ icon: updated ? "Check" : "Settings", tone: updated ? "success" : "accent" }}
    title={updated ? "Password updated" : "Set a new password"}
    body={updated ? "Your password has been updated. You can now sign in." : "Choose a new password for your Space Works account."}
    primary={updated ? { label: "Go to sign in", href: "/admin" } : {
      label: "Update password", pending, pendingLabel: "Updating…", disabled: !canSubmit,
      disabledReason: "Enter matching passwords with at least 8 characters.",
      onClick: () => (document.getElementById("legacy-reset-form") as HTMLFormElement)?.requestSubmit(),
    }} content={!updated ? <form id="legacy-reset-form" onSubmit={(event) => { event.preventDefault(); if (canSubmit) void submit(); }}>
      <NewPasswordFields idPrefix="legacy-reset" newPassword={newPassword} confirmPassword={confirmPassword}
        onNewPasswordChange={setNewPassword} onConfirmPasswordChange={setConfirmPassword} />
      {error ? <p className="mt-3 text-sm text-danger" role="alert">{error}</p> : null}
    <button type="submit" disabled={!canSubmit} hidden aria-hidden="true" tabIndex={-1} />
    </form> : undefined} />;
}
