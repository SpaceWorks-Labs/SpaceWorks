import { freezeBeforeAuthMutation } from "./authFreeze";
import { browserSessionIdentity, requestReauthentication } from "./reauthentication";
import { configuredApiUrl } from "../runtimeConfig";
import { currentSessionContext, type SessionContext } from "./sessionContext";
import { notifyMfaEnrollmentRequired, requiresMfaEnrollment } from "./mfaEnrollment";
import { authHeaders, getAccessToken, getSessionGeneration, hasSessionIdentity, refreshAccessToken, expireStaffAuthSession } from "./sessionTokens";
export { authHeaders, getAccessToken, setAccessToken, clearAccessToken, cleanupLegacyAccessToken,
  refreshAccessToken, logout, addAuthExpiredListener, expireStaffAuthSession } from "./sessionTokens";

export const API_URL = configuredApiUrl();

export const API_V1_URL = API_URL.replace(/\/api$/, "/api/v1");
const PUBLIC_CLIENT_ID = (import.meta.env.VITE_PUBLIC_CLIENT_ID ?? "").trim();
let runtimePublishableKey = (import.meta.env.VITE_PUBLIC_API_KEY ?? "").trim();
const tenantPublishableKeys = new Map<string, string>();
// The tenant most recently bootstrapped in this session. Member and status requests
// carry no slug of their own, so without this they would send no client credential at
// all on the central /m/:slug routes -- fine today, a 401 the moment enforcement is on.
let activeTenantSlug = "";

export async function publicHeaders(publishableKey?: string): Promise<HeadersInit> {
  if (PUBLIC_CLIENT_ID) {
    return { "X-Client-Id": PUBLIC_CLIENT_ID };
  }
  const key =
    publishableKey?.trim() ||
    runtimePublishableKey ||
    tenantPublishableKeys.get(activeTenantSlug) ||
    "";
  return key ? { "X-Publishable-Key": key } : {};
}

export function setRuntimePublishableKey(key: string) {
  runtimePublishableKey = key.trim();
}

export function cacheTenantPublishableKey(slug: string, key: string, activate = true) {
  const normalized = slug.trim();
  const normalizedKey = key.trim();
  if (normalized && normalizedKey) {
    tenantPublishableKeys.set(normalized, normalizedKey);
    if (activate) activeTenantSlug = normalized;
  }
}

/** Read a cached tenant key. Internal to the api modules -- not re-exported by the barrel. */
export function getTenantPublishableKey(slug: string) {
  return tenantPublishableKeys.get(slug);
}

async function canRefreshAfterUnauthorized(path: string, response: Response) {
  if (["/auth/login", "/auth/refresh", "/auth/logout"].includes(path)) return false;
  // A limited account still has a live session for its own charges (260/361).
  // Refreshing this refusal would repeat it and then erase that payment session.
  const body = await response.clone().json().catch(() => null) as { code?: string } | null;
  if (["account_restricted", "account_suspended"].includes(body?.code ?? "")) return false;
  // Enrolment is required, not a dead session: never sign the person out for it.
  if (await requiresMfaEnrollment(response)) return false;
  const factorRoute = path.startsWith("/auth/reauth") || /^\/auth\/mfa(?:\/|$)/.test(path);
  if (!factorRoute) return true;
  // SimpleJWT rejects expired access tokens before the factor handler runs.
  // Factor failures also return 401, but refreshing cannot fix those or end the session.
  return body?.code === "token_not_valid";
}

/** The authenticated request, up to but not including reading the body.
 *
 * Extracted so a non-JSON response (an SVG, say) can reuse the refresh-and-retry
 * behaviour rather than carrying a second copy of it. A duplicated refresh path is how one
 * caller silently stops recovering from an expired token.
 */
export async function staffFetch(
  path: string,
  options: RequestInit = {},
  includePublicCredentials = false,
  context: SessionContext = currentSessionContext(),
): Promise<Response> {
  await freezeBeforeAuthMutation(path, options.method ?? "GET");
  const generation = getSessionGeneration(context);
  const routeContext = currentSessionContext();
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const makeRequest = async () =>
    fetch(`${API_V1_URL}${path}`, {
      ...options,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(includePublicCredentials ? await publicHeaders() : {}),
        ...authHeaders(context),
        ...(options.headers ?? {}),
      },
    });

  let response = await makeRequest();

  if (response.status === 401 && await canRefreshAfterUnauthorized(path, response)) {
    const refreshed = generation === getSessionGeneration(context) && await refreshAccessToken(context);
    if (refreshed) {
      response = await makeRequest();
      if (response.status === 401 && await canRefreshAfterUnauthorized(path, response)) {
        if (generation === getSessionGeneration(context) && hasSessionIdentity(context)) expireStaffAuthSession(context);
      }
    } else {
      if (generation === getSessionGeneration(context) && hasSessionIdentity(context)) expireStaffAuthSession(context);
    }
  }
  if (await requiresMfaEnrollment(response)) notifyMfaEnrollmentRequired();
  if (response.status === 403 && !path.startsWith("/auth/reauth")) {
    const body = await response.clone().json().catch(() => ({})) as { code?: string };
    const identity = browserSessionIdentity(getAccessToken(context));
    if (body.code === "recent_reauth_required" && identity && await requestReauthentication(context)
        && identity === browserSessionIdentity(getAccessToken(context))) {
      response = await makeRequest();
    }
  }
  // A completed mutation may otherwise run its success callback in a different
  // account's mounted UI. The server action stands; its old UI result is discarded.
  if (response.ok && (generation !== getSessionGeneration(context) || routeContext !== currentSessionContext())) {
    throw new DOMException("The session context changed while the request was running.", "AbortError");
  }
  return response;
}
