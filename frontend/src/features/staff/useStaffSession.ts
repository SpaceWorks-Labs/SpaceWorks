import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";

import {
  addAuthExpiredListener,
  clearAccessToken,
  fetchMe,
  logout as logoutStaff,
  refreshAccessToken,
  setAccessToken,
  staffRequest,
  type PasswordLoginRequest,
  type PasswordLoginResponse,
  type StaffAuthUser,
} from "../../lib/api";
import { contextForRoute, consoleSessionHref, offlineSessionPrefix } from "../../lib/api/sessionContext";
import { isMfaChallenge, type MfaChallenge, type MfaCompleted } from "../auth/mfaApi";
import { type RecoveryState } from "./RecoveryQuarantinePanel";
import {
  persistSelectedMakerspace,
  persistStaffTab,
  readStoredMakerspace,
  staffBasePath,
  staffMakerspaceSlugFromPath,
  staffTabPath,
  tabFromStaffPath,
} from "./staffTabs";
import { type Makerspace, useStaffGet } from "./panels/shared";
import { useTenant } from "../../lib/tenant";
import { useLiveUpdates } from "../../lib/useLiveUpdates";
import { wipeOfflineScopes } from "./eventCheckInOfflineStore";
import { useSuperadminSpaceHint } from "./useSuperadminSpaceHint";

export function useStaffSession(guestOnly: boolean) {
  const tenant = useTenant();
  const queryClient = useQueryClient();
  const location = useLocation();
  const context = contextForRoute(location.pathname, location.search, tenant.slug);
  const delegated = context === "member";
  const navigate = useNavigate();
  const [restoring, setRestoring] = useState(true);
  // Hydration seeds this query; invalidation after authority changes now refreshes
  // the same user consumed by navigation and capability checks.
  const authUser = useQuery<StaffAuthUser | null>({
    queryKey: ["staff", "me"],
    queryFn: () => fetchMe(context, delegated ? "delegated" : undefined),
    enabled: query => !restoring && Boolean(query.state.data),
    staleTime: Infinity,
    retry: false,
  });
  const user = restoring ? null : authUser.data ?? null;
  const setUser = useCallback((value: StaffAuthUser | null) => {
    queryClient.setQueryData<StaffAuthUser | null>(["staff", "me"], value);
  }, [queryClient]);
  const [mfaChallenge, setMfaChallenge] = useState<MfaChallenge>();
  const [selected, setSelectedState] = useState<number | null>(() => readStoredMakerspace(context));
  const [staffSignInRequested] = useState(() => new URLSearchParams(location.search).get("sign-in") === "staff");
  const [oidcCallback] = useState(() => {
    const query = new URLSearchParams(window.location.search);
    return ["code", "state", "error"].some((key) => query.has(key));
  });
  const routeMakerspaceSlug = staffMakerspaceSlugFromPath(location.pathname, guestOnly);
  const routeMakerspaceSlugRef = useRef(routeMakerspaceSlug);
  const singleTenantLocked = tenant.mode === "single" && tenant.makerspaceId !== null;
  const setSelected = useCallback((value: number | null) => {
    setSelectedState(value);
    persistSelectedMakerspace(value, context);
  }, [context]);
  const setTab = useCallback((value: string) => {
    persistStaffTab(value, context);
  }, [context]);

  useEffect(() => {
    routeMakerspaceSlugRef.current = routeMakerspaceSlug;
  }, [routeMakerspaceSlug]);
  const hydrateUser = useCallback((nextUser: StaffAuthUser) => {
    setUser(nextUser);
    if (tenant.mode === "single" && tenant.makerspaceId !== null) {
      setSelected(tenant.makerspaceId);
      return;
    }
    const superadmin = nextUser.is_superuser || nextUser.role === "superadmin";
    const routeMembership = nextUser.makerspaces.find((item) => item.slug === routeMakerspaceSlugRef.current);
    if (routeMembership) {
      setSelected(routeMembership.id);
      return;
    }
    const saved = readStoredMakerspace(context);
    const staffSaved = nextUser.makerspaces.some((item) => item.id === saved) ? saved : null;
    setSelected(superadmin ? saved : staffSaved ?? nextUser.makerspaces[0]?.id ?? null);
  }, [context, setSelected, setUser, tenant.makerspaceId, tenant.mode]);

  useEffect(() => {
    if (authUser.data) hydrateUser(authUser.data);
  }, [authUser.data, hydrateUser]);

  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (!user || !staffSignInRequested || query.get("sign-in") !== "staff") return;
    query.delete("sign-in");
    navigate({ search: query.toString() }, { replace: true });
  }, [location.search, navigate, staffSignInRequested, user]);

  // Refetch /auth/me and re-hydrate after a role edit/assignment may have changed the
  // current actor's own effective actions, so tabs/capabilities recompute immediately.
  const refreshAuthUser = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["staff", "me"] });
  }, [queryClient]);

  const expireSession = useCallback(() => {
    void wipeOfflineScopes(offlineSessionPrefix(context)).catch(() => undefined);
    setUser(null);
    setSelected(null);
    setTab("");
    queryClient.clear();
  }, [context, queryClient, setSelected, setTab, setUser]);

  useEffect(() => addAuthExpiredListener(expireSession, context), [expireSession, context]);

  useEffect(() => {
    let active = true;

    // Finish the pending provider login before consulting any previous cookie.
    if (oidcCallback) { setUser(null); setRestoring(false); return; }
    // An explicit staff sign-in restarts only this console context.
    // Delegated workspaces reuse the existing member session.
    if (staffSignInRequested && !delegated) { clearAccessToken(context); setUser(null); setRestoring(false); return; }

    async function restoreSession() {
      const refreshed = await refreshAccessToken(context);
      if (refreshed) {
        try {
          const currentUser = await fetchMe(context, delegated ? "delegated" : undefined);
          if (active) {
            hydrateUser(currentUser);
          }
        } catch {
          clearAccessToken(context);
          if (active) {
            setUser(null);
          }
        }
      } else if (active) {
        clearAccessToken(context);
        setUser(null);
      }
      if (active) {
        setRestoring(false);
      }
    }

    restoreSession();
    return () => {
      active = false;
    };
  }, [context, delegated, hydrateUser, oidcCallback, staffSignInRequested, setUser]);

  const login = useMutation({
    mutationFn: (payload: { username: string; password: string }) =>
      staffRequest<PasswordLoginResponse<StaffAuthUser> | MfaChallenge>("/auth/login", {
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ ...payload, surface: delegated ? "delegated" : "staff",
          context: context.startsWith("staff:") ? "staff" : context === "platform" ? "platform" : "member",
          ...(context.startsWith("staff:") ? { makerspace: context.slice(6) } : {}),
        } satisfies PasswordLoginRequest),
      }, context),
    onSuccess: (data) => {
      if (isMfaChallenge(data)) { clearAccessToken(context); setMfaChallenge(data); return; }
      setAccessToken(data.access, context);
      hydrateUser(data.user);
    },
  });
  const mfaCompleted = (result: MfaCompleted) => {
    setMfaChallenge(undefined); setAccessToken(result.access, context); hydrateUser(result.user);
  };
  const delegatedAuthenticated = async () => {
    hydrateUser(await fetchMe(context, "delegated"));
  };

  const makerspaces = useStaffGet<Makerspace[]>(
    ["staff", "makerspaces"],
    "/admin/makerspaces",
    Boolean(user) && !user?.must_change_password,
  );
  const recovery = useQuery({
    queryKey: ["deployment-recovery-state"],
    queryFn: () => staffRequest<RecoveryState>("/recovery"),
    enabled: Boolean(user && (user.is_superuser || user.role === "superadmin")),
    retry: false,
  });
  const chooseMakerspace = useCallback((id: number | null) => {
    if (singleTenantLocked) return;
    if (id === null) {
      setSelected(null);
      navigate(staffBasePath(guestOnly));
      return;
    }
    const ms = makerspaces.data?.find((m) => m.id === id);
    setSelected(id);
    // Only the non-guest staff console uses slug-scoped /m/<slug>/admin routes.
    // Guest-admin keeps its own shell, so leave its switching as-is (a slug
    // navigate here would remount the non-guest app and drop the guest UI).
    if (ms?.slug && !guestOnly) {
      const currentTab = tabFromStaffPath(location.pathname, guestOnly);
      navigate(consoleSessionHref(staffTabPath(currentTab, guestOnly, context === "platform" ? undefined : ms.slug), context));
    }
  }, [context, guestOnly, location.pathname, makerspaces.data, navigate, setSelected, singleTenantLocked]);
  const activeMakerspace = useMemo(
    () => {
      return makerspaces.data?.find((item) => item.id === selected);
    },
    [makerspaces.data, selected],
  );

  const routeMakerspace = useMemo(() => {
    if (!routeMakerspaceSlug || !makerspaces.data || !user) {
      return undefined;
    }
    const space = makerspaces.data.find((item) => item.slug === routeMakerspaceSlug);
    // An old makerspace-list response must not restore a venue just removed by
    // /auth/me. Event/booking grants remain valid routes without a membership.
    const canReach = user.is_superuser || user.role === "superadmin"
      || user.makerspaces.some(item => item.id === space?.id)
      || user.event_grants?.some(item => item.makerspace_id === space?.id)
      || user.booking_grants?.some(item => item.makerspace_id === space?.id);
    return canReach ? space : undefined;
  }, [makerspaces.data, routeMakerspaceSlug, user]);

  useEffect(() => {
    if (singleTenantLocked || !routeMakerspace || routeMakerspace.id === selected) {
      return;
    }
    setSelected(routeMakerspace.id);
  }, [routeMakerspace, selected, setSelected, singleTenantLocked]);

  useSuperadminSpaceHint({ context, user, makerspaces: makerspaces.data, selected, setSelected });

  // Live hints for the signed-in console: every committed change invalidates the matching
  // queries instead of waiting for a poll. Off when signed out; pauses while the tab is hidden.
  useLiveUpdates(Boolean(user));

  const signOut = async () => {
    try { await logoutStaff(context); }
    finally {
      await wipeOfflineScopes(offlineSessionPrefix(context)).catch(() => undefined);
      setUser(null); setSelected(null); queryClient.clear();
    }
  };

  return {
    activeMakerspace,
    chooseMakerspace,
    login,
    mfaChallenge,
    setMfaChallenge,
    mfaCompleted,
    makerspaces,
    queryClient,
    recovery,
    refreshAuthUser,
    restoring,
    routeMakerspace,
    routeMakerspaceSlug,
    selected,
    setTab,
    setUser,
    signOut,
    singleTenantLocked,
    delegated,
    delegatedAuthenticated,
    tenant,
    user,
  };
}
