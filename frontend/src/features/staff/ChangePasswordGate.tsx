import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import { CenteredCardLayout } from "../../components/layouts";
import { PasswordStrength } from "../auth/PasswordStrength";
type ChangePasswordGateProps = {
  username: string;
  onChanged: () => void;
  onSignOut: () => void;
};
// Shown after login when the account still carries must_change_password (the
// generated first-run credential). It blocks the console until the password is rotated.

export function ChangePasswordGate({ username, onChanged, onSignOut }: ChangePasswordGateProps) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      staffRequest("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }),
    onSuccess: onChanged,
  });
  const mismatch = confirm.length > 0 && newPassword !== confirm;
  const canSubmit =
    currentPassword.length > 0 && newPassword.length > 0 && confirm === newPassword && !mismatch && !mutation.isPending;
  return (
    <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Lock", tone: "accent" }}
      eyebrow="Security" title="Set a new password" body={<p><strong>{username}</strong> is using a temporary password. Choose your own to continue.</p>}
      primary={{ label: "Update password", pending: mutation.isPending, pendingLabel: "Updating…", disabled: !canSubmit, disabledReason: "Enter matching passwords to continue.", onClick: () => (document.getElementById("change-password-form") as HTMLFormElement)?.requestSubmit() }}
      escape={{ label: "Sign out", onClick: onSignOut }} content={
      <form
        id="change-password-form" className="grid gap-1"
        onSubmit={(event) => {
          event.preventDefault();
          if (canSubmit) mutation.mutate();
        }}
      >
        <input
          aria-label="Username"
          className="sr-only"
          type="text"
          autoComplete="username"
          value={username}
          readOnly
          tabIndex={-1}
          aria-hidden="true"
        />
        <label className="mt-5 block text-sm font-semibold" htmlFor="change-current-password">Current password</label>
        <input
          className="desk-input mt-1 w-full"
          type="password"
          id="change-current-password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
        />
        <label className="mt-3 block text-sm font-semibold" htmlFor="change-new-password">New password</label>
        <input
          className="desk-input mt-1 w-full"
          type="password"
          id="change-new-password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        <PasswordStrength password={newPassword} />
        <label className="mt-3 block text-sm font-semibold" htmlFor="change-confirm-password">Confirm new password</label>
        <input
          className="desk-input mt-1 w-full"
          type="password"
          id="change-confirm-password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        {mismatch ? <p className="mt-3 text-sm text-danger">Passwords do not match.</p> : null}
        {mutation.error ? (
          <p className="mt-3 text-sm text-danger">{(mutation.error as Error).message}</p>
        ) : null}
      <button type="submit" disabled={!canSubmit} hidden aria-hidden="true" tabIndex={-1} />
    </form>
    } />
  );
}
