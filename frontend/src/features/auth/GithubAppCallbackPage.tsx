import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { CenteredCardLayout } from "../../components/layouts";

/** The app link GitHub returns a native sign-in to (decision 358 A). */
export const GITHUB_APP_CALLBACK_PATH = "/app/auth/github/callback";

/** The one-time link, kept in memory only; "" once it carries no code (already used or reloaded). */
function readLink(): string {
  return new URL(window.location.href).searchParams.has("code") ? window.location.href : "";
}

/**
 * Shown when a phone opened GitHub's redirect in the browser instead of the Space Works app
 * (decision 361). The page never sends, stores or renders the code: it keeps the link in memory
 * so "Open the app" can hand the very same URL back to the operating system, and takes the code
 * and state out of the address bar. The route loads no analytics or replay
 * (`analyticsExcludedScreens`) and sends no referrer.
 */
export function GithubAppCallbackPage({ open = href => window.location.assign(href) }: { open?: (href: string) => void } = {}) {
  const [link] = useState(readLink);
  useEffect(() => {
    if (window.location.search || window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    const meta = document.createElement("meta");
    meta.name = "referrer";
    meta.content = "no-referrer";
    document.head.prepend(meta);
    return () => meta.remove();
  }, []);
  return <CenteredCardLayout state={{ status: "ready" }} eyebrow={t`GitHub sign-in`} media={{ icon: "KeyRound", tone: "accent" }}
    title={t`Open in the Space Works app`}
    body={t`This sign-in finishes in the Space Works app on this phone. If the app did not open, try again, or sign in on the website instead.`}
    primary={{ label: t`Open the app`, onClick: () => open(link), disabled: !link,
      disabledReason: t`This link has already been used. Start the GitHub sign-in again in the app.` }}
    escape={{ label: t`Sign in on the website`, href: "/member" }} />;
}
