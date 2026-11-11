import { t } from "@lingui/core/macro";
import { staffRequest } from "../../lib/api";
import { loadScript, requestNonce, type SocialConfig, type SocialProvider } from "./socialSdk";
import type { SocialIdentity } from "./LinkedSignInList";

/**
 * Browser linking. Google and Apple hand the browser an ID token for a member web nonce, linked by
 * `POST auth/social/providers`. GitHub and configured OIDC providers use a server-side code exchange:
 * `…/link/authorize` starts an attempt bound to this signed-in session, the provider redirects back
 * to this page, and `POST auth/social/link/callback` links it (it never signs anyone in).
 */
export type RedirectProvider = "github" | `oidc:${string}`;
export type LinkableProvider =
  | { provider: SocialProvider; clientId: string }
  | { provider: RedirectProvider; label: string };

export function linkableProviders(config: SocialConfig | undefined, linked: readonly string[]): LinkableProvider[] {
  const rows: LinkableProvider[] = [];
  if (config?.google?.enabled && config.google.web_client_id) rows.push({ provider: "google", clientId: config.google.web_client_id });
  if (config?.apple?.enabled && config.apple.service_id) rows.push({ provider: "apple", clientId: config.apple.service_id });
  if (config?.github) rows.push({ provider: "github", label: "GitHub" }); // i18n-ignore: provider brand name
  for (const [key, value] of Object.entries(config ?? {})) {
    if (!key.startsWith("oidc:") || !value || typeof value !== "object" || !("display_name" in value) || !value.enabled) continue;
    rows.push({ provider: key as RedirectProvider, label: value.display_name || key.slice(5) });
  }
  return rows.filter(row => !linked.includes(row.provider));
}

const LINK_NONCE_PREFIX = "spaceworks.social-link.nonce.";
const here = () => `${window.location.origin}${window.location.pathname}`;
type LinkStart = { authorization_url: string; state: string; nonce?: string };

/** Leaves for the provider; the nonce stays in this tab so only this session can finish the link. */
export async function beginRedirectLink(provider: RedirectProvider) {
  let nonce: string;
  let started: LinkStart;
  if (provider === "github") {
    nonce = Array.from(window.crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, "0")).join("");
    started = await staffRequest<LinkStart>("/auth/social/github/link/authorize",
      { method: "POST", body: JSON.stringify({ redirect_uri: here(), nonce }) });
  } else {
    started = await staffRequest<LinkStart>(`/auth/social/oidc/${encodeURIComponent(provider.slice(5))}/link/authorize`,
      { method: "POST", body: JSON.stringify({ redirect_uri: here() }) });
    nonce = started.nonce ?? "";
  }
  try {
    window.sessionStorage.setItem(`${LINK_NONCE_PREFIX}${started.state}`, nonce);
  } catch {
    throw new Error(t`Browser storage is required to link an identity provider.`);
  }
  window.location.assign(started.authorization_url);
}

/** Finishes a link the provider redirected back here; null when this page load is not one. */
export async function completeRedirectLink(): Promise<SocialIdentity | null> {
  const query = new URLSearchParams(window.location.search);
  const state = query.get("state")?.trim() ?? "";
  let nonce: string | null;
  try {
    nonce = state ? window.sessionStorage.getItem(`${LINK_NONCE_PREFIX}${state}`) : null;
    // Removed before the request, so a second (StrictMode) mount finds nothing to finish.
    if (nonce !== null) window.sessionStorage.removeItem(`${LINK_NONCE_PREFIX}${state}`);
  } catch {
    return null;
  }
  if (nonce === null) return null;
  const code = query.get("code")?.trim() ?? "";
  const url = new URL(window.location.href);
  for (const key of ["code", "state", "session_state", "iss", "error", "error_description"]) url.searchParams.delete(key);
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  if (!code || !nonce || query.get("error")) throw new Error(t`Linking was cancelled or refused by the provider.`);
  return staffRequest<SocialIdentity>("/auth/social/link/callback", { method: "POST", body: JSON.stringify({ code, state, nonce }) });
}

const link = (provider: SocialProvider, idToken: string, nonce: string, appleName = "") =>
  staffRequest<SocialIdentity>("/auth/social/providers", { method: "POST", body: JSON.stringify({
    provider, id_token: idToken, nonce, client_platform: "web", ...(appleName ? { apple_name: appleName } : {}),
  }) });

/** Renders Google's own button into `element`; pressing it links the chosen Google account. */
export async function mountGoogleLink(element: HTMLElement, clientId: string,
  onDone: (row: SocialIdentity) => void, onError: (error: Error) => void) {
  const { nonce } = await requestNonce("google", "member");
  await loadScript("https://accounts.google.com/gsi/client");
  if (!window.google) throw new Error(t`Google sign-in is unavailable.`);
  window.google.accounts.id.initialize({ client_id: clientId, nonce, callback: async ({ credential }: { credential?: string }) => {
    if (!credential) return onError(new Error(t`Google sign-in was cancelled.`));
    try { onDone(await link("google", credential, nonce)); }
    catch (error) { onError(error instanceof Error ? error : new Error(t`Couldn't link Google. Try again.`)); }
  } });
  window.google.accounts.id.renderButton(element, { type: "standard", theme: "outline", size: "large", text: "continue_with",
    width: Math.min(360, Math.max(240, element.clientWidth || 320)) });
}

export async function linkApple(serviceId: string) {
  const { nonce } = await requestNonce("apple", "member");
  await loadScript("https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js");
  if (!window.AppleID) throw new Error(t`Apple sign-in is unavailable.`);
  window.AppleID.auth.init({ clientId: serviceId, scope: "name email", redirectURI: window.location.origin, usePopup: true, nonce });
  const result = await window.AppleID.auth.signIn();
  const name = [result.user?.name?.firstName, result.user?.name?.lastName].filter(Boolean).join(" ");
  return link("apple", result.authorization.id_token, nonce, name);
}
