import { freezeBeforeAuthMutation } from "../../lib/api/authFreeze";
import { t } from "@lingui/core/macro";
import type { MfaChallenge } from "./mfaApi";
import { publicV1Request } from "../../lib/api";
import { safeReturnPath } from "../inventory/publicInventory/cartHandoff";

export type SocialProvider = "google" | "apple";
export type SocialSurface = "member" | "staff";
export type SocialLoginResult = {
  access: string;
  user: Record<string, unknown>;
  outcome: "created" | "existing" | "auto_linked";
  /** 0.12.0: the validated `next` given at the browser-redirect start, echoed by its callback. */
  next?: string;
};
export type SocialConfig = {
  google?: { enabled: boolean; web_client_id: string };
  apple?: { enabled: boolean; service_id: string };
  github?: boolean;
  [provider: `oidc:${string}`]:
    | { enabled: boolean; display_name: string; client_id: string; issuer: string }
    | undefined;
};

type OidcStartResult = {
  authorization_url: string;
  state: string;
  nonce: string;
};

const OIDC_NONCE_PREFIX = "spaceworks.oidc.nonce.";
const GITHUB_NONCE_PREFIX = "spaceworks.github.nonce.";
const RETURN_PREFIX = "spaceworks.social.next.";
const RETURN_PENDING = "spaceworks.social.next";
const MAX_NEXT_LENGTH = 512; // backend safe_next.MAX_NEXT_LENGTH

/**
 * 0.12.0 row 29: a sign-in started on `member?next=<path>` must land on that path. The provider round
 * trip returns to the bare page (the registered redirect URI carries no query), so the same-origin
 * relative `next` rides in session storage under the attempt's state. Never an absolute URL.
 */
function rememberReturnPath(state: string) {
  const next = pageReturnPath();
  if (next) window.sessionStorage.setItem(`${RETURN_PREFIX}${state}`, next);
}

/** This page's `next`, when it is a same-origin relative path the server will also accept. */
function pageReturnPath() {
  const next = safeReturnPath(new URLSearchParams(window.location.search).get("next"));
  return next && next.length <= MAX_NEXT_LENGTH ? next : undefined;
}

/** The start body's `next`: the server binds it to the attempt and echoes it from the callback. */
function nextField() {
  const next = pageReturnPath();
  return next ? { next } : {};
}

/** The `next` a finished provider sign-in should go to, once; re-validated as a same-origin relative path. */
export function takeSocialReturnPath(): string | undefined {
  try {
    const value = window.sessionStorage.getItem(RETURN_PENDING);
    window.sessionStorage.removeItem(RETURN_PENDING);
    return safeReturnPath(value);
  } catch {
    return undefined;
  }
}

/** True on the page load that carries a provider callback this browser started (so its sign-in panel can finish it). */
export function hasPendingSocialCallback(): boolean {
  const state = new URLSearchParams(window.location.search).get("state")?.trim();
  if (!state) return false;
  try {
    return Boolean(window.sessionStorage.getItem(`${OIDC_NONCE_PREFIX}${state}`) || window.sessionStorage.getItem(`${GITHUB_NONCE_PREFIX}${state}`));
  } catch {
    return false;
  }
}

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(options: Record<string, unknown>): void;
          renderButton(element: HTMLElement, options: Record<string, unknown>): void;
        };
      };
    };
    AppleID?: {
      auth: {
        init(options: Record<string, unknown>): void;
        signIn(): Promise<{ authorization: { id_token: string; code?: string }; user?: { name?: { firstName?: string; lastName?: string } } }>;
      };
    };
  }
}

const scripts = new Map<string, Promise<void>>();

export function loadScript(src: string) {
  const existing = scripts.get(src);
  if (existing) return existing;
  const pending = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(t`Unable to load the identity provider.`));
    document.head.appendChild(script);
  });
  scripts.set(src, pending);
  return pending;
}

export async function requestNonce(provider: SocialProvider, surface: SocialSurface) {
  return publicV1Request<{ nonce: string }>("/auth/social/nonce", {
    method: "POST",
    body: JSON.stringify({
      provider,
      surface,
      delivery: "web",
      client_platform: "web",
    }),
  });
}

async function complete(provider: SocialProvider, surface: SocialSurface, idToken: string, nonce: string, appleName = "", authorizationCode = "") {
  return publicV1Request<SocialLoginResult | MfaChallenge>(`/auth/social/${provider}`, {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({
      id_token: idToken,
      nonce,
      surface,
      delivery: "web",
      client_platform: "web",
      ...(appleName ? { apple_name: appleName } : {}),
      ...(authorizationCode ? { authorization_code: authorizationCode, redirect_uri: window.location.origin } : {}),
    }),
  });
}

export async function mountGoogleButton(
  element: HTMLElement,
  clientId: string,
  surface: SocialSurface,
  onSuccess: (result: SocialLoginResult | MfaChallenge) => void,
  onError: (error: Error) => void,
) {
  const { nonce } = await requestNonce("google", surface);
  await loadScript("https://accounts.google.com/gsi/client");
  if (!window.google) throw new Error(t`Google sign-in is unavailable.`);
  window.google.accounts.id.initialize({
    client_id: clientId,
    nonce,
    callback: async ({ credential }: { credential?: string }) => {
      if (!credential) return onError(new Error(t`Google sign-in was cancelled.`));
      try {
        onSuccess(await complete("google", surface, credential, nonce));
      } catch (error) {
        onError(error instanceof Error ? error : new Error(t`Google sign-in failed.`));
      }
    },
  });
  window.google.accounts.id.renderButton(element, {
    type: "standard",
    theme: "outline",
    size: "large",
    width: Math.min(360, Math.max(240, element.clientWidth || 320)),
  });
}

export async function signInWithApple(serviceId: string, surface: SocialSurface) {
  const { nonce } = await requestNonce("apple", surface);
  await loadScript("https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js");
  if (!window.AppleID) throw new Error(t`Apple sign-in is unavailable.`);
  window.AppleID.auth.init({
    clientId: serviceId,
    scope: "name email",
    redirectURI: window.location.origin,
    usePopup: true,
    nonce,
  });
  const result = await window.AppleID.auth.signIn();
  const name = [result.user?.name?.firstName, result.user?.name?.lastName].filter(Boolean).join(" ");
  return complete("apple", surface, result.authorization.id_token, nonce, name, result.authorization.code);
}

export async function beginOidcBrowser(
  slug: string,
  email: string,
  makerspaceSlug: string,
  surface: SocialSurface = "member",
) {
  const redirectUri = `${window.location.origin}${window.location.pathname}`;
  const started = await publicV1Request<OidcStartResult>(
    `/auth/social/oidc/${encodeURIComponent(slug)}/authorize`,
    {
      method: "POST",
      body: JSON.stringify({
        redirect_uri: redirectUri,
        surface,
        ...(email.trim() ? { email: email.trim() } : {}),
        ...(makerspaceSlug ? { makerspace_slug: makerspaceSlug } : {}),
        ...nextField(),
      }),
    },
  );
  try {
    window.sessionStorage.setItem(`${OIDC_NONCE_PREFIX}${started.state}`, started.nonce);
    rememberReturnPath(started.state);
  } catch {
    throw new Error(t`Browser storage is required for secure identity-provider sign-in.`);
  }
  await freezeBeforeAuthMutation("/auth/social/redirect", "POST");
  window.location.assign(started.authorization_url);
}

export async function beginGithubBrowser() {
  const bytes = window.crypto.getRandomValues(new Uint8Array(32));
  const nonce = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  const started = await publicV1Request<Omit<OidcStartResult, "nonce">>(
    "/auth/social/github/authorize",
    { method: "POST", body: JSON.stringify({
      redirect_uri: `${window.location.origin}${window.location.pathname}`, nonce, ...nextField(),
    }) },
  );
  try {
    window.sessionStorage.setItem(`${GITHUB_NONCE_PREFIX}${started.state}`, nonce);
    rememberReturnPath(started.state);
  } catch {
    throw new Error(t`Browser storage is required for secure identity-provider sign-in.`);
  }
  await freezeBeforeAuthMutation("/auth/social/redirect", "POST");
  window.location.assign(started.authorization_url);
}

export async function completeOidcBrowserCallback(): Promise<SocialLoginResult | MfaChallenge | null> {
  const query = new URLSearchParams(window.location.search);
  const code = query.get("code")?.trim() ?? "";
  const state = query.get("state")?.trim() ?? "";
  if (!code && !state && !query.get("error")) return null;
  if (!code || !state || query.get("error")) {
    clearOidcQuery();
    throw new Error(t`Identity-provider sign-in was cancelled or refused.`);
  }
  let nonce = "";
  let provider = "oidc";
  try {
    const githubNonce = window.sessionStorage.getItem(`${GITHUB_NONCE_PREFIX}${state}`);
    const prefix = githubNonce ? GITHUB_NONCE_PREFIX : OIDC_NONCE_PREFIX;
    provider = githubNonce ? "github" : "oidc";
    nonce = window.sessionStorage.getItem(`${prefix}${state}`) ?? "";
    window.sessionStorage.removeItem(`${prefix}${state}`);
    const next = window.sessionStorage.getItem(`${RETURN_PREFIX}${state}`);
    window.sessionStorage.removeItem(`${RETURN_PREFIX}${state}`);
    if (next) window.sessionStorage.setItem(RETURN_PENDING, next);
  } catch {
    // The backend still refuses the callback because the nonce is mandatory.
  }
  clearOidcQuery();
  if (!nonce) throw new Error(t`Identity-provider sign-in expired. Please try again.`);
  const result = await publicV1Request<SocialLoginResult | MfaChallenge>(`/auth/social/${provider}/callback`, {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({ code, state, nonce }),
  });
  // The server's `next` wins over the copy kept locally; an MFA challenge carries none, so the
  // local copy stays as the fallback for that path. Re-validated: never an off-site target.
  const serverNext = "next" in result && typeof result.next === "string" ? safeReturnPath(result.next) : undefined;
  if (serverNext) {
    try { window.sessionStorage.setItem(RETURN_PENDING, serverNext); } catch { /* storage refused: no return path */ }
  }
  return result;
}

function clearOidcQuery() {
  const url = new URL(window.location.href);
  for (const key of ["code", "state", "session_state", "iss", "error", "error_description"]) {
    url.searchParams.delete(key);
  }
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
}
