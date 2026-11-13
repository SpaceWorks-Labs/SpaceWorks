import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { PageHelp } from "../help/PageHelp";
import { reportNotMe, type NotMeResult } from "./notMeApi";

// The token survives a second render (React's strict mode runs state initialisers twice) but
// never the address bar: it is read from `#token=` and the fragment is dropped at once.
let heldToken = "";
function takeFragmentToken() {
  if (window.location.hash) {
    heldToken = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") ?? "";
    window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
  }
  return heldToken;
}

/** Keep this page's address (and so any token) out of every request's Referer. */
function useNoReferrer() {
  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "referrer";
    meta.content = "no-referrer";
    document.head.prepend(meta);
    return () => meta.remove();
  }, []);
}

/** Who the MFA-reset rule lets reset two-step sign-in for this person, from the server's answer. */
function resetRule(result: NotMeResult) {
  const spaces = result.mfa_reset.space_managers_of.map(space => space.name);
  const managers = spaces.length ? ` or the Space Manager of ${spaces.join(", ")}` : "";
  return `Your passkeys and authenticator app were not changed. If you can't use them, ask the platform administrator${managers} to reset two-step sign-in.`;
}

/**
 * "This wasn't me" from a security alert email (`/security/not-me#token=...`). Nothing happens on
 * load: the token is held in memory and sent only when the person presses the button.
 */
export function NotMePage() {
  useNoReferrer();
  const help = <PageHelp article="member/security-alerts" topic="security alerts" className="flex justify-center" />;
  const [token] = useState(takeFragmentToken);
  const [state, setState] = useState<"ready" | "sending">("ready");
  const [result, setResult] = useState<NotMeResult>();
  const [error, setError] = useState("");
  const send = async () => {
    setState("sending"); setError("");
    try { setResult(await reportNotMe(token)); heldToken = ""; }
    catch (failure) { setState("ready"); setError(authErrorMessage(failure, "We couldn't secure your account just now. Try again, or reset your password.")); }
  };
  if (result) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldCheck", tone: "success" }} title={t`Your account is secured`}
      body={<div className="grid gap-3" role="status"><p>{t`We signed you out on every device, forgot your remembered devices and turned off your old password.`}</p>
        <p>{result.password_reset_requested ? t`We emailed you a code to choose a new password. Use it to sign in again.`
          : t`Choose a new password from the reset page to sign in again.`}</p><p>{resetRule(result)}</p></div>}
      primary={{ label: t`Choose a new password`, href: "/reset-password" }} footer={help} />;
  }
  if (!token) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldAlert", tone: "warn" }} title={t`This link is incomplete`}
      body={t`Open the link from the security email again. If it still doesn't work, reset your password to secure your account.`}
      primary={{ label: t`Reset your password`, href: "/reset-password" }} footer={help} />;
  }
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldAlert", tone: "warn" }} eyebrow={t`Security alert`}
    title={t`Didn't do this?`}
    body={<div className="grid gap-3"><p>{t`If you don't recognise the activity in the email, secure your account now. This will:`}</p>
      <ul className="grid list-disc gap-1 pl-5"><li>{t`sign you out on every device and app;`}</li><li>{t`forget the devices we remembered for you;`}</li>
        <li>{t`turn off your current password and email you a code to choose a new one.`}</li></ul>
      <p>{t`Your passkeys and authenticator app stay as they are.`}</p></div>}
    content={error ? <p role="alert" className="text-sm text-danger">{error}</p> : undefined}
    primary={{ label: t`Secure my account`, pending: state === "sending", pendingLabel: "Securing your account…", onClick: () => void send() }}
    escape={{ label: t`It was me`, href: "/" }} footer={help} />;
}
