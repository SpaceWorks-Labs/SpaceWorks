import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { Skeleton } from "../../components/ui";
import { CenteredCardLayout } from "../../components/layouts";
import { fetchMe, logout, refreshAccessToken, staffRequest, type StaffAuthUser } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { eventStaffGrantKeys, type EventStaffGrant } from "./eventStaffGrantsApi";
import { eventErrorText } from "./eventUi";

const INVITE_STORAGE_KEY = "spaceworks.eventStaffInvite";

export function EventStaffInvitePage() {
  const [oidcCallback] = useState(() => {
    const query = new URLSearchParams(window.location.search);
    return ["code", "state", "error"].some((key) => query.has(key));
  });
  const [token] = useState(() => {
    const fragmentToken = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (fragmentToken) return fragmentToken;
    try { return window.sessionStorage.getItem(INVITE_STORAGE_KEY) ?? ""; }
    catch { return ""; }
  });
  const [user, setUser] = useState<StaffAuthUser | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [authError, setAuthError] = useState("");
  const client = useQueryClient();
  const navigate = useNavigate();
  const cancel = () => {
    try { window.sessionStorage.removeItem(INVITE_STORAGE_KEY); } catch { /* Storage may be unavailable. */ }
    navigate("/", { replace: true });
  };
  const openStaff = useMutation({ mutationFn: () => logout(), onSuccess: () => {
    // A member token cannot acquire staff authority in place. A fresh staff login
    // also runs the space's staff MFA policy before opening any event operations.
    client.clear(); navigate("/admin/assigned-events");
  } });
  const redeem = useMutation({ mutationFn: () => staffRequest<EventStaffGrant>("/admin/event-staff-invites/redeem/", {
    method: "POST", body: JSON.stringify({ token }),
  }), onSuccess: async () => {
    try { window.sessionStorage.removeItem(INVITE_STORAGE_KEY); } catch { /* Storage may be unavailable. */ }
    window.history.replaceState(null, "", window.location.pathname);
    await client.invalidateQueries({ queryKey: eventStaffGrantKeys.accessible });
  } });
  useEffect(() => {
    let active = true;
    // Keep the invitation in this tab across OIDC's full-page redirect. Only the
    // sign-in callback consumes its query parameters; strip the bearer fragment now.
    try { if (token) window.sessionStorage.setItem(INVITE_STORAGE_KEY, token); } catch { /* OIDC also requires storage. */ }
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    // Mount MemberAuthPanel even if a prior cookie could restore a session: the
    // returned OIDC code must finish before showing invitation acceptance.
    if (oidcCallback) { setRestoring(false); return; }
    refreshAccessToken().then((refreshed) => refreshed ? fetchMe() : null)
      .then((current) => { if (active) setUser(current); })
      .catch(() => {})
      .finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, [oidcCallback, token]);
  const authenticated = async () => {
    try { setUser(await fetchMe()); setAuthError(""); }
    catch (error) { setAuthError(eventErrorText(error)); }
  };
  // MemberAuthPanel owns this screen's page heading and main landmark; the invitation context sits above it.
  if (!restoring && !user && (token || oidcCallback)) return <div className="desk-shell">
    <section aria-label="Event staff invitation" className="mx-auto grid w-full max-w-lg gap-1 px-4 pt-6 text-center">
      <p className="eyebrow">Event staff invitation</p>
      <p className="text-sm text-muted">Sign in with the invited account to continue.</p>
      {authError ? <p className="text-sm text-danger" role="alert">{authError}</p> : null}
    </section>
    <MemberAuthPanel onAuthenticated={() => { void authenticated(); }} />
    <div className="px-4 pb-6 text-center"><button className="desk-button" type="button" onClick={cancel}>Cancel invitation</button></div>
  </div>;
  const cancelAction = { label: "Cancel invitation", onClick: cancel, disabled: redeem.isPending, disabledReason: redeem.isPending ? "Wait for the invitation to finish." : undefined };
  const primary = redeem.isSuccess
    ? { label: "Sign in to staff console", pending: openStaff.isPending, pendingLabel: "Opening sign-in…", onClick: () => openStaff.mutate() }
    : user ? { label: "Accept staff invitation", pending: redeem.isPending, pendingLabel: "Accepting…", disabled: !token,
      disabledReason: !token ? "The invitation link is missing its token." : undefined, onClick: () => redeem.mutate() }
    : cancelAction;
  return <CenteredCardLayout state={{ status: "ready" }} width={480} media={{ icon: "Calendar", tone: "accent" }}
    title="Event staff invitation"
    body={<p>Sign in with the invited account and verify its email before accepting. This invitation can be used once.</p>}
    content={<div className="grid gap-3 empty:hidden">
      {restoring ? <Skeleton className="h-32 w-full" /> : null}
      {!token ? <p className="text-sm text-danger" role="alert">The invitation link is missing its token. Open the original invitation link again.</p> : null}
      {user && !redeem.isSuccess ? <p className="text-sm text-ink">Signed in as {user.username}.</p> : null}
      {redeem.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(redeem.error)}</p> : null}
      {redeem.isSuccess ? <div className="grid gap-3 rounded-xl border border-line bg-surface p-4 text-sm text-ink" role="status"><p>Your event staff access is active. Sign in to the staff console to use it.</p>{openStaff.error ? <p className="text-danger" role="alert">{eventErrorText(openStaff.error)}</p> : null}</div> : null}
    </div>}
    primary={primary}
    escape={user && !redeem.isSuccess ? cancelAction : undefined} />;
}
