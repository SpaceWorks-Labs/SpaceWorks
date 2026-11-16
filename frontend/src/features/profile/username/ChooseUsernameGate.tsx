import { t } from "@lingui/core/macro";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { logout, memberRequest } from "../../../lib/api";
import { hasSessionIdentity } from "../../../lib/api/sessionTokens";
import { fieldError } from "../edit/profileEditApi";
import { UsernameField, usernameUsable } from "./UsernameField";
import { clearUsernameReview, takeUsernameReview, usernameKeys, type UsernameStatus } from "./usernameApi";
import { BoxArt } from "../../../components/BoxSpinner";

type Me = { handle?: string | null; handle_required?: boolean; handle_suggestion?: string | null; display_name?: string; email?: string; username?: string };

/** Re-checks whether a person session exists; sign-in happens without a navigation, so a short poll beats wiring every sign-in path. */
function usePersonSession() {
  const [signedIn, setSignedIn] = useState(() => hasSessionIdentity("person"));
  useEffect(() => {
    const timer = window.setInterval(() => setSignedIn(hasSessionIdentity("person")), 2000);
    return () => window.clearInterval(timer);
  }, []);
  return signedIn;
}

/**
 * Decision 308. Two steps share one dialog:
 *  - `handle_required` (an account with no username): blocking. No close control, Escape ignored, sign-out works. The
 *    server also answers every write with 403 `handle_required` until this is done.
 *  - after a social/OIDC sign-up (the server auto-claimed a suggestion): "Your username is X, change it?", dismissible.
 */
export function ChooseUsernameGate() {
  const signedIn = usePersonSession();
  const me = useQuery({
    queryKey: usernameKeys.required, enabled: signedIn, retry: false, staleTime: 30_000,
    queryFn: async () => { const body = await memberRequest<Me & { user?: Me }>("/auth/me"); return { ...body, ...(body.user ?? {}) } as Me; },
  });
  const [review, setReview] = useState(takeUsernameReview);
  useEffect(() => { if (signedIn) setReview(takeUsernameReview()); }, [signedIn]);
  if (!signedIn || !me.data || me.error) return null;
  if (me.data.handle_required) return <Step me={me.data} blocking />;
  if (review && me.data.handle) return <Step me={me.data} blocking={false} onDone={() => { clearUsernameReview(); setReview(false); }} />;
  return null;
}

function Step({ me, blocking, onDone }: { me: Me; blocking: boolean; onDone?: () => void }) {
  const client = useQueryClient();
  const [value, setValue] = useState(blocking ? "" : me.handle ?? "");
  const [changing, setChanging] = useState(blocking);
  const [status, setStatus] = useState<UsernameStatus>("idle");
  const onStatus = useCallback((next: UsernameStatus) => setStatus(next), []);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => { panel.current?.querySelector<HTMLElement>("input, button")?.focus(); }, [changing]);
  const claim = useMutation({
    mutationFn: () => memberRequest<{ handle: string }>("/member/profile/handle", { method: "POST", body: JSON.stringify({ handle: value.trim().toLowerCase() }) }),
    onSuccess: async () => {
      await Promise.all([client.invalidateQueries({ queryKey: usernameKeys.required }), client.invalidateQueries({ queryKey: ["member", "profile"] })]);
      onDone?.();
    },
  });
  const signOut = () => { void logout("person").catch(() => undefined).finally(() => { client.clear(); }); };
  const handle = value.trim().toLowerCase();
  const title = blocking ? t`Choose your username` : t`Your username is @${me.handle ?? ""}`;
  return <div className="fixed inset-0 z-[1000] grid place-items-center overflow-y-auto bg-ink/60 p-4">
    <div ref={panel} role="dialog" aria-modal="true" aria-labelledby="choose-username-title" aria-describedby="choose-username-body"
      className="w-full max-w-md rounded-xl border border-line bg-panel p-6 shadow-lg"
      onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); if (!blocking) onDone?.(); } }}>
      <h2 id="choose-username-title" className="title-panel">{title}</h2>
      <p id="choose-username-body" className="mt-2 text-sm text-muted">{blocking
        ? t`Every account has a username. It becomes your profile address and is how other members find you. We picked one for you; accept it or change it.`
        : t`We picked it from your sign-in. It is your profile address. Keep it, or change it now.`}</p>
      {changing ? <form className="mt-4 grid gap-4" onSubmit={event => { event.preventDefault(); if (usernameUsable(status) && handle && !claim.isPending) claim.mutate(); }}>
        <UsernameField id="gate-username" value={value} onChange={setValue} onStatus={onStatus} prefill={blocking}
          seed={{ displayName: me.display_name, email: me.email, known: blocking ? me.handle_suggestion ?? undefined : undefined }} />
        {claim.error ? <p role="alert" className="text-sm text-danger">{fieldError(claim.error, "handle")}</p> : null}
        <button type="submit" className="desk-button-primary w-full" disabled={!handle || !usernameUsable(status) || claim.isPending}>
          {claim.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : handle ? t`Use @${handle}` : t`Continue`}</button>
        {blocking ? <button type="button" className="desk-button w-full" onClick={signOut}>{t`Sign out`}</button>
          : <button type="button" className="desk-button w-full" onClick={onDone}>{t`Keep @${me.handle ?? ""}`}</button>}
      </form> : <div className="mt-4 grid gap-3">
        <button type="button" className="desk-button-primary w-full" onClick={onDone}>{t`Keep @${me.handle ?? ""}`}</button>
        <button type="button" className="desk-button w-full" onClick={() => setChanging(true)}>{t`Change it`}</button>
      </div>}
    </div>
  </div>;
}
