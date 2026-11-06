import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Field } from "../../components/ui/Field";
import { CenteredCardLayout } from "../../components/layouts";
import { PasswordInput } from "./PasswordInput";
import { publicV1Request } from "../../lib/api";

export function AccountRestorePage() {
  const [proof] = useState(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const value = { email: params.get("email") || "", token: params.get("token") || "" };
    return value;
  });
  useEffect(() => { window.history.replaceState(null, "", window.location.pathname); }, []);
  const [password, setPassword] = useState("");
  const restore = useMutation({ mutationFn: () => publicV1Request<{ restored: boolean; detail: string }>(
    "/auth/account/restore/email", { method: "POST", headers: { Authorization: "" }, body: JSON.stringify({ ...proof, new_password: password }) },
  ), onSuccess: () => setPassword("") });
  return <CenteredCardLayout state={{ status: "ready" }} title={t`Restore your account`}
    media={{ icon: "User", tone: "accent" }}
    body={restore.isSuccess ? <p role="status">{restore.data.detail}</p> : "You can come back before the archive deadline and before identity removal starts. Choose a new password. Previous memberships, sessions and device access remain revoked."}
    primary={restore.isSuccess ? { label: t`Return to sign-in`, href: "/member" } : {
      label: t`Restore account`, pending: restore.isPending, disabled: !proof.email || !proof.token,
      disabledReason: "Open the complete restore link from your recovery email.",
      onClick: () => (document.getElementById("account-restore-form") as HTMLFormElement)?.requestSubmit(),
    }}
    escape={!restore.isSuccess ? { label: t`Return to sign-in`, href: "/member" } : undefined}
    content={!restore.isSuccess ? <form id="account-restore-form" className="grid gap-4" onSubmit={event => {
      event.preventDefault(); if (!restore.isPending && proof.email && proof.token) restore.mutate();
    }}>
      <Field label={t`New password`}><PasswordInput autoComplete="new-password" required maxLength={128} value={password} onChange={event => setPassword(event.target.value)} /></Field>
      {restore.error ? <p role="alert" className="text-danger">{restore.error.message}</p> : null}
      {!proof.token ? <p role="status">{t`Open the restore link from your recovery email. To request a fresh link, use password recovery on the sign-in page.`}</p> : null}
      <button type="submit" disabled={restore.isPending} hidden aria-hidden="true" tabIndex={-1} />
    </form> : undefined} />;
}
