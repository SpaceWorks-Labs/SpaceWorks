import { removeStorage } from "../safeStorage";
import { configuredApiUrl } from "../runtimeConfig";
import { clearOfflineCards, rememberOfflineCardOwner } from "../../features/members/memberCard/offlineCard";
import { clearToasts } from "../../components/ui/toastStore";
import { clearJobs } from "../../components/ui/jobStore";
import { wipeOfflineScopes } from "../../features/staff/eventCheckInOfflineStore";
import { currentSessionContext, notifySessionCleared, offlineSessionPrefix, type SessionContext } from "./sessionContext";
import { browserSessionIdentity } from "./reauthentication";

type Session = { token: string; owner?: string; generation: number; refresh: Promise<boolean> | null };
const sessions = new Map<SessionContext, Session>();
const expiredListeners = new Map<SessionContext, Set<() => void>>();
const session = (context: SessionContext) => {
  if (!sessions.has(context)) sessions.set(context, { token: "", generation: 0, refresh: null });
  return sessions.get(context)!;
};
export const getSessionGeneration = (context: SessionContext) => session(context).generation;
export const getAccessToken = (context = currentSessionContext()) => session(context).token;
export function offlineAccountScope(resource: string, context = currentSessionContext()) {
  const identity = browserSessionIdentity(getAccessToken(context)) || session(context).owner || "anonymous";
  return `${offlineSessionPrefix(context)}${encodeURIComponent(identity)}:${resource}`;
}
export function cleanupLegacyAccessToken() { removeStorage("makerspace.access"); }
export function authHeaders(context = currentSessionContext()): HeadersInit {
  const token = getAccessToken(context);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Cache privacy only. Account kind and tenant authorization stay server-owned. */
function tokenOwner(token: string): string | undefined {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.user_id || payload.sub ? String(payload.user_id ?? payload.sub) : undefined;
  } catch { return undefined; }
}

export function setAccessToken(token: string, context = currentSessionContext()) {
  const state = session(context);
  state.generation++;
  state.refresh = null;
  const owner = tokenOwner(token);
  if (!owner || owner !== state.owner) { clearJobs(context); clearToasts(context); }
  state.owner = owner;
  notifySessionCleared(context);
  void wipeOfflineScopes(offlineSessionPrefix(context)).catch(() => undefined);
  if (context === "member") rememberOfflineCardOwner(token);
  state.token = token;
  cleanupLegacyAccessToken();
}

export function clearAccessToken(context = currentSessionContext()) {
  const state = session(context);
  state.generation++;
  state.token = "";
  state.owner = undefined;
  state.refresh = null;
  clearJobs(context); clearToasts(context);
  if (context === "member") clearOfflineCards();
  const cleanup = wipeOfflineScopes(offlineSessionPrefix(context)).catch(() => undefined);
  notifySessionCleared(context);
  cleanupLegacyAccessToken();
  return cleanup;
}

export function addAuthExpiredListener(listener: () => void, context = currentSessionContext()) {
  if (!expiredListeners.has(context)) expiredListeners.set(context, new Set());
  expiredListeners.get(context)!.add(listener);
  return () => { expiredListeners.get(context)?.delete(listener); };
}
export function expireStaffAuthSession(context = currentSessionContext()) {
  const cleanup = clearAccessToken(context);
  expiredListeners.get(context)?.forEach(listener => listener());
  return cleanup;
}

/** A principal may have both member and delegated browser contexts. Never clear
 * another account merely because it shares an email or the same browser. */
export async function clearAccountSessions(context = currentSessionContext()) {
  const owner = session(context).owner;
  const contexts = [...sessions.keys()].filter(key => key === context || (owner && session(key).owner === owner));
  await Promise.all(contexts.map(expireStaffAuthSession));
  return owner;
}

const authUrl = (action: string) => `${configuredApiUrl().replace(/\/api$/, "/api/v1")}/auth/${action}`;
const refreshOptions = (context: SessionContext): RequestInit => ({
  method: "POST", credentials: "include",
  headers: { "X-Refresh-CSRF": "1", "Content-Type": "application/json" },
  body: JSON.stringify({ context }),
});

export function refreshAccessToken(context = currentSessionContext()): Promise<boolean> {
  const state = session(context);
  if (state.refresh) return state.refresh;
  const generation = state.generation;
  const pending = (async () => {
    const response = await fetch(authUrl("refresh"), refreshOptions(context)).catch(() => null);
    if (!response?.ok) return false;
    const body = await response.json().catch(() => ({})) as { access?: string };
    if (typeof body.access !== "string" || !body.access || state.generation !== generation) return false;
    const owner = tokenOwner(body.access);
    if (state.owner && owner && state.owner !== owner) {
      // A different tab may have replaced this context's cookie. Never replay the
      // old account's request under that account or retain its cached data.
      expireStaffAuthSession(context);
      return false;
    }
    // Rotation keeps the generation: concurrent requests from this session can retry.
    state.token = body.access;
    state.owner = owner;
    if (context === "member") rememberOfflineCardOwner(body.access);
    return true;
  })().finally(() => { if (state.refresh === pending) state.refresh = null; });
  state.refresh = pending;
  return pending;
}

export async function logout(context = currentSessionContext()): Promise<void> {
  // Fence an in-flight refresh before waiting for the server's cookie deletion.
  clearAccessToken(context);
  await fetch(authUrl("logout"), refreshOptions(context));
}
