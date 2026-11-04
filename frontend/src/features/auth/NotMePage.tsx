import { useEffect, useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import { reportNotMe } from "./notMeApi";

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

const RESET_RULE = "Your two-step sign-in was not changed. If you can't use it, the platform administrator can reset it; "
  + "a Space Manager can too when all your staff roles are in their space and you are not a Space Manager there.";

/**
 * "This wasn't me" from a security alert email (`/security/not-me#token=...`). Nothing happens on
 * load: the token is held in memory and sent only when the person presses the button.
 */
export function NotMePage() {
  useNoReferrer();
  const [token] = useState(takeFragmentToken);
  const [state, setState] = useState<"ready" | "sending" | "done">("ready");
  const [error, setError] = useState("");
  const send = async () => {
    setState("sending"); setError("");
    try { await reportNotMe(token); heldToken = ""; setState("done"); }
    catch (failure) { setState("ready"); setError(authErrorMessage(failure, "We couldn't secure your account just now. Try again, or reset your password.")); }
  };
  if (!token) {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldAlert", tone: "warn" }} title="This link is incomplete"
      body="Open the link from the security email again. If it still doesn't work, reset your password to secure your account."
      primary={{ label: "Reset your password", href: "/reset-password" }} />;
  }
  if (state === "done") {
    return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldCheck", tone: "success" }} title="Your account is secured"
      body={<div className="grid gap-3" role="status"><p>We signed you out on every device, forgot your remembered devices and turned off your old password.</p>
        <p>We emailed you a link to choose a new password. Use it to sign in again.</p><p>{RESET_RULE}</p></div>}
      primary={{ label: "Go to sign-in", href: "/member" }} />;
  }
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldAlert", tone: "warn" }} eyebrow="Security alert"
    title="Didn't do this?"
    body={<div className="grid gap-3"><p>If you don't recognise the activity in the email, secure your account now. This will:</p>
      <ul className="grid list-disc gap-1 pl-5"><li>sign you out on every device and app;</li><li>forget the devices we remembered for you;</li>
        <li>turn off your current password and email you a link to choose a new one.</li></ul>
      <p>Your passkeys and authenticator app stay as they are.</p></div>}
    content={error ? <p role="alert" className="text-sm text-danger">{error}</p> : undefined}
    primary={{ label: "Secure my account", pending: state === "sending", pendingLabel: "Securing your account…", onClick: () => void send() }}
    escape={{ label: "It was me", href: "/" }} />;
}
