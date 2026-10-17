export type SessionContext = "member" | "platform" | `staff:${string}`;

let routeContext: SessionContext | undefined;
const listeners = new Set<(context: SessionContext) => void>();

/** Delegation chooses credentials, never permissions; the API checks the grant. */
export function contextForRoute(pathname: string, search = "", tenantSlug = ""): SessionContext {
  const scoped = /^\/m\/([^/]+)\/(?:admin|guest-admin)(?:\/|$)/.exec(pathname);
  const consoleRoute = Boolean(scoped) || /^\/(?:admin|guest-admin)(?:\/|$)/.test(pathname);
  if (consoleRoute && !scoped && new URLSearchParams(search).get("context") === "platform") return "platform";
  const delegated = new URLSearchParams(search).get("surface") === "delegated"
    || /\/admin\/(?:organizations|assigned-events|organized-events|organization-analytics)(?:\/|$)/.test(pathname);
  if (consoleRoute && delegated) return "member";
  if (scoped) return `staff:${scoped[1]}`;
  if (consoleRoute) return tenantSlug ? `staff:${tenantSlug}` : "platform";
  if (pathname === "/superadmin" || pathname.startsWith("/control/")) return "platform";
  // Account utilities opened from the console retain an explicit context in their URL.
  const context = new URLSearchParams(search).get("context");
  if (/^\/(?:mfa|reauth)(?:\/|$)/.test(pathname) && context
      && (context === "platform" || /^staff:[a-zA-Z0-9_-]+$/.test(context))) return context as SessionContext;
  return "member";
}

export function currentSessionContext(): SessionContext {
  return routeContext ?? contextForRoute(window.location.pathname, window.location.search);
}

export function setRouteSessionContext(context: SessionContext) { routeContext = context; }

export function onSessionCleared(listener: (context: SessionContext) => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export function notifySessionCleared(context: SessionContext) {
  listeners.forEach(listener => listener(context));
}

export const offlineSessionPrefix = (context = currentSessionContext()) => `session:${context}:`;

export function consoleSessionHref(path: string, context = currentSessionContext()) {
  if (context.startsWith("staff:")) return path;
  const url = new URL(path, window.location.origin);
  if (context === "member") url.searchParams.set("surface", "delegated");
  else {
    url.pathname = url.pathname.replace(/^\/m\/[^/]+\/admin(?=\/|$)/, "/admin");
    url.searchParams.set("context", "platform");
  }
  return url.pathname + url.search + url.hash;
}
