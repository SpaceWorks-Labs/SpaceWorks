import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";

import {
  addAuthExpiredListener, clearAccessToken, fetchMe, logout, refreshAccessToken, setAccessToken, staffRequest,
  type PasswordLoginResponse, type StaffAuthUser,
} from "../../lib/api";
import { contextForRoute, consoleSessionHref, offlineSessionPrefix } from "../../lib/api/sessionContext";
import { useTenant } from "../../lib/tenant";
import { useLiveUpdates } from "../../lib/useLiveUpdates";
import { isMfaChallenge, type MfaChallenge, type MfaCompleted } from "../auth/mfaApi";
import { consoleSpaceIds, isSuperadminUser } from "./consoleAccess";
import { wipeOfflineScopes } from "./eventCheckInOfflineStore";
import { type Makerspace, useStaffGet } from "./panels/shared";
import { type RecoveryState } from "./RecoveryQuarantinePanel";
import {
  persistSelectedMakerspace, persistStaffTab, readStoredMakerspace, staffBasePath, staffMakerspaceSlugFromPath,
  staffTabPath, tabFromStaffPath,
} from "./staffTabs";
import { useSuperadminSpaceHint } from "./useSuperadminSpaceHint";

/**
 * The console's session (one account per person). A person signs in once (MemberAuthPanel)
 * and the console opens for the spaces where they hold staff roles or a delegated grant;
 * only the platform superadmin signs in separately (`?context=platform`).
 */
export function useConsoleSession(guestOnly: boolean) {
  const tenant = useTenant();
  const queryClient = useQueryClient();
  const location = useLocation();
  const navigate = useNavigate();
  const context = contextForRoute(location.pathname, location.search);
  const platform = context === "platform";
  const [restoring, setRestoring] = useState(true);
  const authUser = useQuery<StaffAuthUser | null>({
    queryKey: ["staff", "me"], queryFn: () => fetchMe(context),
    enabled: query => !restoring && Boolean(query.state.data), staleTime: Infinity, retry: false,
  });
  const user = restoring ? null : authUser.data ?? null;
  const setUser = useCallback((value: StaffAuthUser | null) => {
    queryClient.setQueryData<StaffAuthUser | null>(["staff", "me"], value);
  }, [queryClient]);
  const [mfaChallenge, setMfaChallenge] = useState<MfaChallenge>();
  const [selected, setSelectedState] = useState<number | null>(() => readStoredMakerspace(context));
  const [oidcCallback] = useState(() => ["code", "state", "error"].some(key => new URLSearchParams(window.location.search).has(key)));
  const routeMakerspaceSlug = staffMakerspaceSlugFromPath(location.pathname, guestOnly);
  const routeSlugRef = useRef(routeMakerspaceSlug);
  const singleTenantLocked = tenant.mode === "single" && tenant.makerspaceId !== null;
  const setSelected = useCallback((value: number | null) => {
    setSelectedState(value); persistSelectedMakerspace(value, context);
  }, [context]);
  const setTab = useCallback((value: string) => { persistStaffTab(value, context); }, [context]);
  useEffect(() => { routeSlugRef.current = routeMakerspaceSlug; }, [routeMakerspaceSlug]);

  const hydrateUser = useCallback((next: StaffAuthUser) => {
    setUser(next);
    if (tenant.mode === "single" && tenant.makerspaceId !== null) { setSelected(tenant.makerspaceId); return; }
    const saved = readStoredMakerspace(context);
    if (isSuperadminUser(next)) { setSelected(saved); return; }
    const allowed = consoleSpaceIds(next);
    const routed = next.makerspaces.find(item => item.slug === routeSlugRef.current)?.id
      ?? next.staff_roles?.find(entry => entry.makerspace.slug === routeSlugRef.current)?.makerspace.id;
    if (routed !== undefined && allowed.has(routed)) { setSelected(routed); return; }
    // A person with roles in several spaces picks one (MakerspacePicker); one space opens directly.
    setSelected(saved !== null && allowed.has(saved) ? saved : allowed.size === 1 ? [...allowed][0] : null);
  }, [context, setSelected, setUser, tenant.makerspaceId, tenant.mode]);

  useEffect(() => { if (authUser.data) hydrateUser(authUser.data); }, [authUser.data, hydrateUser]);
  // A role grant or change refreshes /auth/me so tabs and capabilities recompute at once.
  const refreshAuthUser = useCallback(() => { void queryClient.invalidateQueries({ queryKey: ["staff", "me"] }); }, [queryClient]);
  const expireSession = useCallback(() => {
    void wipeOfflineScopes(offlineSessionPrefix(context)).catch(() => undefined);
    setUser(null); setSelected(null); setTab(""); queryClient.clear();
  }, [context, queryClient, setSelected, setTab, setUser]);
  useEffect(() => addAuthExpiredListener(expireSession, context), [expireSession, context]);

  useEffect(() => {
    let active = true;
    // Finish a pending provider sign-in before consulting any previous cookie.
    if (oidcCallback) { setUser(null); setRestoring(false); return; }
    void (async () => {
      const refreshed = await refreshAccessToken(context);
      let next: StaffAuthUser | null = null;
      if (refreshed) next = await fetchMe(context).catch(() => null);
      if (!next) clearAccessToken(context);
      if (!active) return;
      if (next) hydrateUser(next); else setUser(null);
      setRestoring(false);
    })();
    return () => { active = false; };
  }, [context, hydrateUser, oidcCallback, setUser]);

  // Only the platform console has its own sign-in; people use the one person sign-in.
  const login = useMutation({
    mutationFn: (payload: { username: string; password: string }) =>
      staffRequest<PasswordLoginResponse<StaffAuthUser> | MfaChallenge>("/auth/login", {
        method: "POST", credentials: "include", body: JSON.stringify(payload),
      }, "platform"),
    onSuccess: data => {
      if (isMfaChallenge(data)) { clearAccessToken(context); setMfaChallenge(data); return; }
      setAccessToken(data.access, context); hydrateUser(data.user);
    },
  });
  const mfaCompleted = (result: MfaCompleted) => { setMfaChallenge(undefined); setAccessToken(result.access, context); hydrateUser(result.user); };
  const personAuthenticated = async () => { hydrateUser(await fetchMe(context)); };

  const makerspaces = useStaffGet<Makerspace[]>(["staff", "makerspaces"], "/admin/makerspaces", Boolean(user) && !user?.must_change_password);
  const recovery = useQuery({
    queryKey: ["deployment-recovery-state"], queryFn: () => staffRequest<RecoveryState>("/recovery"),
    enabled: Boolean(user && isSuperadminUser(user)), retry: false,
  });
  const reachable = useMemo(() => {
    if (!user || isSuperadminUser(user)) return null;
    return consoleSpaceIds(user);
  }, [user]);
  // A person only ever sees the spaces they hold staff authority in, never every community space.
  const consoleMakerspaces = useMemo(() => (makerspaces.data ?? []).filter(item => !reachable || reachable.has(item.id)),
    [makerspaces.data, reachable]);
  const chooseMakerspace = useCallback((id: number | null) => {
    if (singleTenantLocked) return;
    setSelected(id);
    if (id === null) { navigate(staffBasePath(guestOnly)); return; }
    const space = consoleMakerspaces.find(item => item.id === id);
    if (space?.slug && !guestOnly) {
      const currentTab = tabFromStaffPath(location.pathname, guestOnly);
      navigate(consoleSessionHref(staffTabPath(currentTab, guestOnly, platform ? undefined : space.slug), context));
    }
  }, [consoleMakerspaces, context, guestOnly, location.pathname, navigate, platform, setSelected, singleTenantLocked]);
  const activeMakerspace = useMemo(() => consoleMakerspaces.find(item => item.id === selected), [consoleMakerspaces, selected]);
  const routeMakerspace = useMemo(() => routeMakerspaceSlug && user
    ? consoleMakerspaces.find(item => item.slug === routeMakerspaceSlug) : undefined, [consoleMakerspaces, routeMakerspaceSlug, user]);
  useEffect(() => {
    if (!singleTenantLocked && routeMakerspace && routeMakerspace.id !== selected) setSelected(routeMakerspace.id);
  }, [routeMakerspace, selected, setSelected, singleTenantLocked]);
  useSuperadminSpaceHint({ context, user, makerspaces: makerspaces.data, selected, setSelected });
  // Live hints for the signed-in console; off when signed out.
  useLiveUpdates(Boolean(user));

  const signOut = async () => {
    try { await logout(context); }
    finally {
      await wipeOfflineScopes(offlineSessionPrefix(context)).catch(() => undefined);
      setUser(null); setSelected(null); queryClient.clear();
    }
  };

  return {
    activeMakerspace, chooseMakerspace, consoleMakerspaces, login, mfaChallenge, setMfaChallenge, mfaCompleted,
    makerspaces, personAuthenticated, platform, queryClient, recovery, refreshAuthUser, restoring, routeMakerspace,
    routeMakerspaceSlug, selected, setTab, setUser, signOut, singleTenantLocked, tenant, user,
  };
}
