import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorText } from "../../components/ui";
import { publicV1Request } from "../../lib/api";
import { authErrorMessage } from "../../lib/api/authErrorCopy";
import type { SocialIdentity } from "./LinkedSignInList";
import {
  beginRedirectLink, completeRedirectLink, linkableProviders, linkApple, mountGoogleLink,
  type LinkableProvider, type RedirectProvider,
} from "./socialLink";
import type { SocialConfig } from "./socialSdk";
import { BoxArt } from "../../components/BoxSpinner";

type IdTokenChoice = Extract<LinkableProvider, { clientId: string }>;

/**
 * "Link another way to sign in": offered only for providers this deployment has configured for the
 * browser (public `/config`), and only those not linked yet. Nothing renders when none qualify.
 * GitHub and OIDC leave for the provider and return here, where the link is finished on mount.
 */
export function LinkSignInProviders({ linked, onLinked }: { linked: readonly string[]; onLinked: (row: SocialIdentity) => void }) {
  const config = useQuery({ queryKey: ["public-config", "social-auth"], retry: false, staleTime: 300_000,
    queryFn: async () => (await publicV1Request<{ social_auth?: SocialConfig }>("/config")).social_auth ?? {} });
  const [error, setError] = useState<unknown>();
  const returned = useRef(onLinked); returned.current = onLinked;
  useEffect(() => {
    completeRedirectLink().then(row => { if (row) returned.current(row); }, reason => setError(reason));
  }, []);
  const choices = linkableProviders(config.data, linked);
  const message = error ? <ErrorText message={authErrorMessage(error, "Couldn't link that account. Try again.")} /> : null;
  if (!choices.length) return message;
  const fail = (reason: unknown) => setError(reason);
  const done = (row: SocialIdentity) => { setError(undefined); onLinked(row); };
  return <section className="grid gap-3" aria-label={t`Link another sign-in`}>
    <h3 className="font-semibold text-ink">{t`Link another way to sign in`}</h3>
    <div className="flex flex-wrap items-start gap-3">
      {choices.map(choice => !("clientId" in choice)
        ? <RedirectLink key={choice.provider} provider={choice.provider} label={choice.label} onError={fail} />
        : choice.provider === "google"
          ? <GoogleLink key="google" choice={choice} onLinked={done} onError={fail} />
          : <AppleLink key="apple" choice={choice} onLinked={done} onError={fail} />)}
    </div>
    {message}
  </section>;
}

function RedirectLink({ provider, label, onError }: { provider: RedirectProvider; label: string; onError: (error: unknown) => void }) {
  const [pending, setPending] = useState(false);
  return <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => {
    setPending(true);
    beginRedirectLink(provider).catch(error => { setPending(false); onError(error); });
  }}>{pending ? t`Opening ${label}…` : t`Link ${label}`}</button>;
}

function GoogleLink({ choice, onLinked, onError }: { choice: IdTokenChoice; onLinked: (row: SocialIdentity) => void; onError: (error: unknown) => void }) {
  const [open, setOpen] = useState(false);
  const host = useRef<HTMLDivElement>(null);
  const done = useRef(onLinked); done.current = onLinked;
  const failed = useRef(onError); failed.current = onError;
  useEffect(() => {
    if (!open || !host.current) return;
    // Each opening asks for a fresh one-time nonce; the provider button links on press.
    mountGoogleLink(host.current, choice.clientId, row => done.current(row), error => failed.current(error))
      .catch(error => { setOpen(false); failed.current(error); });
  }, [open, choice.clientId]);
  return open ? <div ref={host} aria-label={t`Google account chooser`} />
    : <button type="button" className="desk-button min-h-11" onClick={() => setOpen(true)}>{t`Link Google`}</button>;
}

function AppleLink({ choice, onLinked, onError }: { choice: IdTokenChoice; onLinked: (row: SocialIdentity) => void; onError: (error: unknown) => void }) {
  const [pending, setPending] = useState(false);
  return <button type="button" className="desk-button min-h-11" disabled={pending} onClick={() => {
    setPending(true);
    linkApple(choice.clientId).then(onLinked, onError).finally(() => setPending(false));
  }}>{pending ? <><BoxArt size={16} mono />{t`Linking Apple…`}</> : t`Link Apple`}</button>;
}
