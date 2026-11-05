// #196: a person's own personal access tokens and connected apps (server state via TanStack Query).
import { memberRequest } from "../../../lib/api";

export type PersonScope = { value: string; label: string; description: string; group: string; needs_space: boolean };
export type PersonScopeCatalog = { scopes: PersonScope[]; staff_spaces: { id: string; name: string }[] };
export type AccessToken = {
  id: number; name: string; scopes: string[]; makerspace: number | null; created_at: string;
  expires_at: string; last_used_at: string | null; revoked_at: string | null;
};
export type ConnectedApp = { application_id: number; app_name: string; space_name: string; scopes: string[]; granted_at: string };
export type ConsentPreview = { app_name: string; space_name: string; redirect_uri: string;
  scopes: { value: string; label: string; description: string }[] };

export const accessTokensKey = ["person", "access-tokens"] as const;
export const connectedAppsKey = ["person", "connected-apps"] as const;
export const personScopesKey = ["person", "access-token-scopes"] as const;

export const listAccessTokens = () => memberRequest<AccessToken[]>("/auth/access-tokens");
export const listConnectedApps = () => memberRequest<ConnectedApp[]>("/auth/connected-apps");
export const getPersonScopes = () => memberRequest<PersonScopeCatalog>("/auth/access-token-scopes");

export function createAccessToken(body: { name: string; scopes: string[]; makerspace: number | null; expires_in_days: number }) {
  return memberRequest<AccessToken & { token: string }>("/auth/access-tokens", { method: "POST", body: JSON.stringify(body) });
}

export const revokeAccessToken = (id: number) => memberRequest<void>(`/auth/access-tokens/${id}`, { method: "DELETE" });
export const disconnectApp = (id: number) => memberRequest<void>(`/auth/connected-apps/${id}`, { method: "DELETE" });

/** The consent API takes the app's own OAuth query string unchanged. */
export const previewConsent = (query: string) => memberRequest<ConsentPreview>(`/auth/oauth/authorize?${query}`);
export function decideConsent(query: string, allow: boolean) {
  return memberRequest<{ redirect_to: string }>(`/auth/oauth/authorize?${query}`, {
    method: "POST", body: JSON.stringify({ allow }),
  });
}
