import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { fetchMe, refreshAccessToken, staffRequest, type StaffAuthUser } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { bookingStaffGrantKeys, type BookingStaffGrant } from "./bookingStaffGrantsApi";
import { eventErrorText } from "./eventUi";

const INVITE_STORAGE_KEY = "spaceworks.bookingStaffInvite";

export function BookingStaffInvitePage() {
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
  const openStaff = () => navigate("/admin/assigned-events");
  const redeem = useMutation({ mutationFn: () => staffRequest<BookingStaffGrant>("/admin/booking-staff-invites/redeem/", {
    method: "POST", body: JSON.stringify({ token }),
  }), onSuccess: async () => {
    try { window.sessionStorage.removeItem(INVITE_STORAGE_KEY); } catch { /* Storage may be unavailable. */ }
    window.history.replaceState(null, "", window.location.pathname);
    await client.invalidateQueries({ queryKey: bookingStaffGrantKeys.accessible });
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
  // The member sign-in screen is this page while signing in; the invitation names itself in its eyebrow.
  if (!restoring && !user && (token || oidcCallback)) return <MemberAuthPanel eyebrow="Booking resource staff invitation"
    context={<div className="grid gap-2"><p className="text-sm text-muted">Sign in with the invited account to continue.</p>
      {authError ? <p className="text-sm text-danger" role="alert">{authError}</p> : null}</div>}
    footer={<button className="desk-button w-full" type="button" onClick={cancel}>Cancel invitation</button>}
    onAuthenticated={() => { void authenticated(); }} />;
  const cancelAction = { label: "Cancel invitation", onClick: cancel, disabled: redeem.isPending, disabledReason: redeem.isPending ? "Wait for the invitation to finish accepting." : undefined };
  return <CenteredCardLayout width={480} state={{ status: restoring ? "loading" : "ready" }}
    media={{ banner: redeem.isSuccess ? "success" : "accent" }}
    title="Booking resource staff invitation"
    body={redeem.isSuccess ? <p role="status">Your resource staff access is active. Open your helper workspace to use it.</p>
      : "Sign in with the invited account and verify its email before accepting. This invitation can be used once."}
    content={<div className="grid gap-3 empty:hidden">
      {!token ? <p className="text-sm text-danger" role="alert">The invitation link is missing its token. Open the original invitation link again.</p> : null}
      {user && !redeem.isSuccess ? <p className="text-sm text-ink">Signed in as {user.username}.</p> : null}
      {redeem.error ? <p className="text-sm text-danger" role="alert">{eventErrorText(redeem.error)}</p> : null}
    </div>}
    primary={redeem.isSuccess ? { label: "Open helper workspace", onClick: openStaff }
      : user ? { label: "Accept staff invitation", pending: redeem.isPending, pendingLabel: "Accepting...", onClick: () => redeem.mutate(),
        disabled: !token, disabledReason: !token ? "Open the original invitation link again." : undefined }
      : cancelAction}
    escape={!redeem.isSuccess && user ? cancelAction : undefined} />;
}
