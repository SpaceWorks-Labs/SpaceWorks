import { matchRoutes } from "react-router-dom";

type AnalyticsConfig = { scriptUrl: string; collectUrl: string; domain: string };
declare global { interface Window { __WEB_ANALYTICS__?: AnalyticsConfig; plausible?: unknown } }

// This allow-list is also the shared extension point for public booking websites.
export const analyticsPublicRoutes = [
  "/", "/about", "/o/:organizationSlug", "/m/:slug", "/items/:itemId",
  "/events", "/events/:id", "/machines", "/bookings", "/bookings/:id", "/stats",
  "/m/:slug/items/:itemId", "/m/:slug/events", "/m/:slug/events/:id",
  "/m/:slug/machines", "/m/:slug/bookings", "/m/:slug/bookings/:id", "/m/:slug/stats",
].map(path => ({ path }));

export function analyticsTemplate(url: URL): string | null {
  // Unknown, private, credential, embed and query-bearing pages never load third-party JS.
  if (url.search || url.hash) return null;
  return matchRoutes(analyticsPublicRoutes, url.pathname)?.[0]?.route.path ?? null;
}

let controller: AbortController | undefined;
let analyticsEverLoaded = false;
export function isBearerUrl(url: URL): boolean {
  if (url.hash || /(?:^|\/)(?:ticket|tickets|claim|claims|reset-password|station|event-check-in|kiosk|invites?|.*-invite|.*invitations?|embed|reauth)(?:\/|$)/i.test(url.pathname)) return true;
  if (Array.from(url.searchParams.keys()).some(key => /token|secret|code|nonce|claim|invite|state/i.test(key))) return true;
  // Preserve ordinary console navigation. New/unrecognised public routes fail closed.
  if (/^\/(?:m\/[^/]+\/)?(?:admin|guest-admin|member)(?:\/|$)/.test(url.pathname)) return false;
  return Boolean(url.search) || !analyticsTemplate(url);
}
export function removeAnalytics() {
  controller?.abort();
  controller = undefined;
  document.getElementById("web-analytics")?.remove();
  delete window.plausible;
}

function config(): AnalyticsConfig | null {
  const value = window.__WEB_ANALYTICS__;
  if (!value?.scriptUrl || !value.collectUrl || !/^[A-Za-z0-9.-]{1,253}$/.test(value.domain)) return null;
  try {
    for (const raw of [value.scriptUrl, value.collectUrl]) {
      const url = new URL(raw);
      if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash) return null;
    }
    if (!/[./-]manual[.-]/.test(new URL(value.scriptUrl).pathname)) return null;
    return value;
  } catch { return null; }
}

export function pageView(url: URL) {
  const template = analyticsTemplate(url);
  const settings = config();
  if (!template || !settings) { removeAnalytics(); return; }
  if (!document.getElementById("web-analytics")) {
    analyticsEverLoaded = true;
    const script = document.createElement("script");
    script.id = "web-analytics";
    script.src = settings.scriptUrl;
    script.defer = true;
    script.referrerPolicy = "no-referrer";
    script.dataset.manual = "true";
    script.dataset.autoPageviews = "false";
    script.dataset.domain = settings.domain;
    script.dataset.api = settings.collectUrl;
    document.head.append(script);
  }
  // Explicit protocol instead of a provider helper that might read location/referrer.
  controller = new AbortController();
  void fetch(settings.collectUrl, {
    method: "POST", mode: "cors", credentials: "omit", referrerPolicy: "no-referrer",
    headers: { "Content-Type": "text/plain" }, signal: controller.signal,
    body: JSON.stringify({ n: "pageview", u: `${url.origin}${template}`, d: settings.domain, r: "" }),
  }).catch(() => undefined);
}

export function installAnalyticsNavigationGuard() {
  if (!config()) return;
  let previous = new URL(window.location.href);
  const documentStartedBearer = isBearerUrl(previous);
  const originals = { pushState: window.history.pushState, replaceState: window.history.replaceState };
  // A third-party script must never survive a same-document visit to a bearer URL.
  // Reload both boundaries, before React can render or another listener can observe it.
  for (const method of ["pushState", "replaceState"] as const) {
    const original = originals[method].bind(window.history);
    window.history[method] = (data, unused, target) => {
      const next = new URL(String(target ?? window.location.href), window.location.href);
      // Credential screens consume a token into component memory, then scrub the URL.
      // A document that never loaded analytics can safely remove only these suffixes.
      const scrub = method === "replaceState" && documentStartedBearer && !analyticsEverLoaded
        && !document.getElementById("web-analytics") && next.origin === previous.origin
        && next.pathname === previous.pathname && Boolean(previous.search || previous.hash)
        && !next.search && !next.hash;
      if (!scrub && next.href !== previous.href && (isBearerUrl(previous) || isBearerUrl(next))) {
        removeAnalytics();
        window.location.assign(next.href);
        return;
      }
      previous = next;
      original(data, unused, target);
    };
  }
  const onPopstate = () => {
    const next = new URL(window.location.href);
    if (isBearerUrl(previous) || isBearerUrl(next)) {
      removeAnalytics();
      window.location.reload();
    }
    previous = next;
  };
  window.addEventListener("popstate", onPopstate, true);
  return () => {
    window.history.pushState = originals.pushState;
    window.history.replaceState = originals.replaceState;
    window.removeEventListener("popstate", onPopstate, true);
  };
}
