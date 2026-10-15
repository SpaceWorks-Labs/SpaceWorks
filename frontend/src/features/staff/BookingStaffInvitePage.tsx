import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { Skeleton } from "../../components/ui";
import { fetchMe, logout, refreshAccessToken, staffRequest, type StaffAuthUser } from "../../lib/api";
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
  const openStaff = useMutation({ mutationFn: () => logout(), onSuccess: () => {
    // A member token cannot acquire staff authority in place. A fresh staff login
    // also runs the space's staff MFA policy before opening any booking operations.
    client.clear(); navigate("/admin/assigned-events");
  } });
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
  if (!restoring && !user && (token || oidcCallback)) return <div className="desk-shell">
    <div className="px-5 pt-6 text-center"><h1 className="title-page">Booking resource staff invitation</h1><p className="mt-2 text-sm text-muted">Sign in with the invited account to continue.</p>{authError ? <p className="text-danger" role="alert">{authError}</p> : null}</div>
    <MemberAuthPanel onAuthenticated={() => { void authenticated(); }} />
    <div className="px-5 pb-6 text-center"><button className="desk-button-secondary" type="button" onClick={cancel}>Cancel invitation</button></div>
  </div>;
  return <main className="desk-shell grid min-h-screen place-items-center px-5 py-10">
    <section className="desk-panel grid w-full max-w-lg gap-4 p-6" aria-labelledby="booking-invite-heading">
      <h1 className="title-page" id="booking-invite-heading">Booking resource staff invitation</h1>
      <p className="text-sm text-muted">Sign in with the invited account and verify its email before accepting. This invitation can be used once.</p>
      {restoring ? <Skeleton className="h-32 w-full" /> : null}
      {!token ? <p className="text-danger" role="alert">The invitation link is missing its token. Open the original invitation link again.</p> : null}
      {user && !redeem.isSuccess ? <div className="grid gap-3"><p className="text-sm">Signed in as {user.username}.</p>
        <button className="desk-button-primary" type="button" disabled={redeem.isPending || !token} onClick={() => redeem.mutate()}>{redeem.isPending ? "Accepting..." : "Accept staff invitation"}</button>
      </div> : null}
      {redeem.error ? <p className="text-danger" role="alert">{eventErrorText(redeem.error)}</p> : null}
      {!redeem.isSuccess ? <button className="desk-button-secondary" type="button" disabled={redeem.isPending} onClick={cancel}>Cancel invitation</button> : null}
      {redeem.isSuccess ? <div className="grid gap-3" role="status"><p>Your resource staff access is active. Sign in to the staff console to use it.</p><button className="desk-button-primary" type="button" disabled={openStaff.isPending} onClick={() => openStaff.mutate()}>{openStaff.isPending ? "Opening sign-in..." : "Sign in to staff console"}</button>{openStaff.error ? <p className="text-danger" role="alert">{eventErrorText(openStaff.error)}</p> : null}</div> : null}
    </section>
  </main>;
}
