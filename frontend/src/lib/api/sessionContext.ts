/**
 * Which browser session a route uses: the PERSON's (everyone, members and staff alike: one
 * account per person) or the separate PLATFORM superadmin's. A staff role is a person's, so
 * the staff console, the member area, kiosks and scanners all share the person session; the
 * server decides what that session may do in each makerspace.
 */
export type SessionContext = "person" | "platform";

let routeContext: SessionContext | undefined;
const listeners = new Set<(context: SessionContext) => void>();

const CONSOLE = /^\/(?:admin|guest-admin)(?:\/|$)/;

/** Credentials only, never permissions; the API checks every grant. */
export function contextForRoute(pathname: string, search = ""): SessionContext {
  const platformParam = new URLSearchParams(search).get("context") === "platform";
  if (pathname === "/superadmin" || pathname.startsWith("/control/")) return "platform";
  // The superadmin's console and the account utilities it opens carry ?context=platform.
  if (platformParam && (CONSOLE.test(pathname) || /^\/(?:mfa|reauth)(?:\/|$)/.test(pathname))) return "platform";
  return "person";
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

/** A console link that keeps the session it was opened in (the platform one says so in the URL). */
export function consoleSessionHref(path: string, context = currentSessionContext()) {
  if (context === "person") return path;
  const url = new URL(path, window.location.origin);
  url.pathname = url.pathname.replace(/^\/m\/[^/]+\/admin(?=\/|$)/, "/admin");
  url.searchParams.set("context", "platform");
  return url.pathname + url.search + url.hash;
}
