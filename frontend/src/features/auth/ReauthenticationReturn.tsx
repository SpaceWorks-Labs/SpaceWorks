import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CenteredCardLayout } from "../../components/layouts";
import { ErrorText } from "../../components/ui";
import { confirmEnrollmentEmail } from "./reauthenticationApi";
import { refreshAccessToken } from "../../lib/api";

export function ReauthenticationReturn({ confirmation }: { confirmation: boolean }) {
  const [token] = useState(() => {
    if (!confirmation) return "";
    const raw = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") || "";
    window.history.replaceState({}, "", window.location.pathname);
    return raw;
  });
  const confirm = useMutation({ mutationFn: async () => {
    if (!await refreshAccessToken()) throw new Error(t`Open this link in the same signed-in browser session that requested it.`);
    return confirmEnrollmentEmail(token);
  } });
  // The provider return is the verification popup; the window that opened it reads the result and closes it.
  if (!confirmation) return <CenteredCardLayout state={{ status: "ready" }} eyebrow={t`Account access`} media={{ icon: "ShieldCheck", tone: "accent" }}
    title={t`Identity provider returned`} body="Return to the browser window that opened this page."
    primary={{ label: t`Close this window`, onClick: () => window.close() }} />;
  return <CenteredCardLayout state={{ status: "ready" }} eyebrow={t`Account access`} media={{ icon: "ShieldCheck", tone: confirm.isSuccess ? "success" : "accent" }}
    title={t`Confirm authenticator enrollment`}
    body={confirm.isSuccess ? "Confirmed. Continue to enroll your authenticator." : "This link works once, in the same browser session that requested it."}
    content={confirm.error ? <ErrorText message={confirm.error.message} /> : undefined}
    primary={confirm.isSuccess ? { label: t`Enroll authenticator`, href: "/mfa" } : { label: t`Confirm enrollment`, pending: confirm.isPending, pendingLabel: "Confirming...",
      disabled: !token, disabledReason: "This confirmation link is missing its token. Request a new one.", onClick: () => confirm.mutate() }} />;
}
