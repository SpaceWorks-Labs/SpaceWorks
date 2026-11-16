// Locale headers on every SpaceWorks API request, from ONE place (phase 8 i18n).
//
// The app issues API requests from hundreds of call sites (central helpers, the generated
// client, the station and live-event fetches). Rather than thread headers through each,
// `main.tsx` wraps `fetch` once: a request whose URL is the configured API (or this origin's
// `/api/`) gets `Accept-Language` and, for an explicit choice only, `X-SpaceWorks-Locale`,
// applied after the caller's headers. Every other URL -- above all signed object-storage
// uploads and downloads -- passes through untouched, so no signed contract or storage CORS
// policy ever sees an extra header.
//
// The same wrapper reads the locale fields the API returns: `preferred_locale` from the
// auth payloads and `default_locale` from the tenant bootstrap.
import { configuredApiUrl } from "./runtimeConfig";
import { setMakerspaceLocale, setUserLocale, withLocaleHeaders } from "./i18n";

type Fetch = typeof fetch;
const MARK = Symbol.for("spaceworks.localeFetch");
const AUTH_PAYLOAD = /\/api\/v1\/auth\/(?:me|login|refresh|mfa\/[a-z-]+|passkeys\/[a-z-]+\/complete)\/?$/;
const LOGOUT = /\/api\/v1\/auth\/logout(?:-all)?\/?$/;
const BOOTSTRAP = /\/api\/v1\/bootstrap\/?$/;

function requestUrl(input: RequestInfo | URL): URL | null {
  try {
    const raw = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return new URL(raw, window.location.href);
  } catch {
    return null;
  }
}

export function isSpaceWorksApi(url: URL): boolean {
  const api = configuredApiUrl();
  if (url.href === api || url.href.startsWith(`${api}/`)) return true;
  return url.origin === window.location.origin && url.pathname.startsWith("/api/");
}

function observe(url: URL, response: Response) {
  if (!response.ok) return;
  if (LOGOUT.test(url.pathname)) {
    setUserLocale(null);
    return;
  }
  const isAuth = AUTH_PAYLOAD.test(url.pathname);
  if (!isAuth && !BOOTSTRAP.test(url.pathname)) return;
  if (!(response.headers.get("Content-Type") ?? "").includes("json")) return;
  response.clone().json().then((body) => {
    if (isAuth) {
      const user = body && typeof body === "object" && "user" in body ? body.user : body;
      if (user && typeof user === "object" && "preferred_locale" in user) setUserLocale(user.preferred_locale);
    } else if (body && typeof body === "object" && "default_locale" in body) {
      setMakerspaceLocale(body.default_locale);
    }
  }).catch(() => undefined);
}

export function installLocaleFetch(target: { fetch: Fetch } = window) {
  const original = target.fetch;
  if (!original || (original as unknown as Record<symbol, boolean>)[MARK]) return;
  const wrapped = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input);
    if (!url || !isSpaceWorksApi(url)) return original.call(target, input, init);
    const base = init?.headers ?? (input instanceof Request ? input.headers : undefined);
    const response = await original.call(target, input, { ...init, headers: withLocaleHeaders(base) });
    observe(url, response);
    return response;
  }) as Fetch;
  (wrapped as unknown as Record<symbol, boolean>)[MARK] = true;
  target.fetch = wrapped;
}
