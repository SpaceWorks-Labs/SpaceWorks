import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { Skeleton } from "../../components/ui";
import { memberRequest, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { MemberAuthPanel } from "../members/MemberAuthPanel";

const CLAIM_STORAGE_KEY = "spaceworks.speakerClaim";
type Claimed = { speaker_id: number; display_name: string; event: { id: number; title: string; starts_at: string; ends_at: string } };

function claimError(error: unknown) {
  if (error instanceof StructuredApiError && error.status === 404) return "This speaker link is no longer valid. It may have expired, been used already, or been withdrawn. Ask the organizer for a new one.";
  if (error instanceof StructuredApiError && error.status === 403) return "This account can't claim speaker links right now. Contact the organizer.";
  return error instanceof Error ? error.message : "Unable to claim this speaker link.";
}

/**
 * `member/speaker-claim#token=…`: links the signed-in account to a speaker slot. The token rides
 * in the fragment so it never reaches a server log or a Referer header; it is read once, the
 * fragment is cleared, and only this tab's session storage keeps it across an OIDC redirect.
 */
export function SpeakerClaimPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const tenantPath = useTenantPath(tenant.mode === "single" ? tenant.slug : slug ?? "");
  const navigate = useNavigate();
  const client = useQueryClient();
  const [oidcCallback] = useState(() => ["code", "state", "error"].some((key) => new URLSearchParams(window.location.search).has(key)));
  const [token] = useState(() => {
    const fragmentToken = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (fragmentToken) return fragmentToken;
    try { return window.sessionStorage.getItem(CLAIM_STORAGE_KEY) ?? ""; } catch { return ""; }
  });
  const [account, setAccount] = useState<{ username?: string } | null>(null);
  const [restoring, setRestoring] = useState(true);
  const forget = () => { try { window.sessionStorage.removeItem(CLAIM_STORAGE_KEY); } catch { /* Storage may be unavailable. */ } };
  const loadAccount = () => memberRequest<{ username?: string }>("/auth/me").then(setAccount);
  useEffect(() => {
    let active = true;
    try { if (token) window.sessionStorage.setItem(CLAIM_STORAGE_KEY, token); } catch { /* OIDC sign-in also needs storage. */ }
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    // Let a returning OIDC sign-in finish inside the auth panel before claiming anything.
    if (oidcCallback) { setRestoring(false); return; }
    refreshAccessToken().then((refreshed) => refreshed ? memberRequest<{ username?: string }>("/auth/me") : null)
      .then((current) => { if (active) setAccount(current); })
      .catch(() => {})
      .finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, [oidcCallback, token]);
  const claim = useMutation({
    mutationFn: () => memberRequest<Claimed>("/member/event-speaker-claims/", { method: "POST", body: JSON.stringify({ token }) }),
    onSuccess: () => { forget(); void client.invalidateQueries({ queryKey: ["member", "event-history"] }); },
    onError: (error) => { if (error instanceof StructuredApiError && error.status === 404) forget(); },
  });
  const cancel = () => { forget(); navigate(tenantPath(""), { replace: true }); };
  if (!restoring && !account && (token || oidcCallback)) return <MemberAuthPanel eyebrow="Speaker invitation"
    context={<p className="text-sm text-muted">Sign in or create an account to be listed as a speaker.</p>}
    footer={<button className="desk-button w-full" type="button" onClick={cancel}>Not now</button>}
    onAuthenticated={() => { void loadAccount().catch(() => {}); }} />;
  const done = claim.data;
  return <CenteredCardLayout state={{ status: "ready" }} width={480} media={{ icon: "Calendar", tone: "accent" }}
    title={done ? "You're listed as a speaker" : "Speaker invitation"}
    body={done ? <p>{done.display_name} is now linked to {done.event.title}, {new Date(done.event.starts_at).toLocaleString()}. It appears in your event history.</p>
      : <p>Claim this invitation to link your account to the event as a speaker. The link works once.</p>}
    content={<div className="grid gap-3 empty:hidden">
      {restoring ? <Skeleton className="h-24 w-full" /> : null}
      {!token && !done ? <p className="text-sm text-danger" role="alert">The speaker link is missing its token. Open the original link again.</p> : null}
      {account && !done ? <p className="text-sm text-ink">Signed in{account.username ? ` as ${account.username}` : ""}.</p> : null}
      {claim.error ? <p className="text-sm text-danger" role="alert">{claimError(claim.error)}</p> : null}
    </div>}
    primary={done ? { label: "View your event history", href: tenantPath("member/events/history") }
      : { label: "Claim speaker invitation", pending: claim.isPending, pendingLabel: "Claiming…", disabled: !token || !account,
        disabledReason: !token ? "The speaker link is missing its token." : !account ? "Sign in first." : undefined, onClick: () => claim.mutate() }}
    escape={done ? undefined : { label: "Not now", onClick: cancel }} />;
}
