import { staffRequest } from "../../lib/api";

export type ApiKeyRequest = {
  id: number;
  label: string;
  status: "pending" | "approved" | "rejected";
  resolution_note: string;
  created_at: string;
};

/** server: your own backend; peer: another space reading only public data; browser: a site. */
export type ApiClientType = "server" | "browser" | "peer";

export type ApiClient = {
  id: number;
  label: string;
  client_id: string;
  client_type: ApiClientType;
  last_seen_at: string | null;
  allowed_origins: string[];
  scopes: string[];
  is_active: boolean;
  created_at: string;
};

export type ApiClientScopeOption = {
  value: string;
  label: string;
  description: string;
  group: string;
  grantable: boolean;
  lock_reason: string | null;
  client_types?: ApiClientType[];
};

export type ApiClientScopeCatalog = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ApiClientScopeOption[];
};

const typeLockReason: Record<ApiClientType, string> = {
  server: "This scope cannot be granted here.",
  browser: "Browser clients may only use public scopes.",
  peer: "A peer client only reads the public catalogue, events and stats.",
};

/** The catalog says which client types each scope suits; lock the rest for this type. */
export function scopeOptionsForClient(
  options: ApiClientScopeOption[],
  clientType: ApiClientType,
) {
  return options.map((option) => (!option.client_types || option.client_types.includes(clientType)) ? option : {
    ...option,
    grantable: false,
    lock_reason: typeLockReason[clientType],
  });
}

export type ApiClientCreateResponse = ApiClient & {
  client_secret: string;
};

export type ApiSettings = {
  public_code: string;
  cors_allowed_origins: string[];
};

export const apiKeyRequestsQueryKey = (makerspaceId: number) => ["api-key-requests", makerspaceId];
export const apiClientsQueryKey = (makerspaceId: number) => ["api-clients", makerspaceId];
export const apiClientScopesQueryKey = (makerspaceId: number) => ["api-client-scopes", makerspaceId];
export const apiSettingsQueryKey = (makerspaceId: number) => ["api-settings", makerspaceId];

export function requestApiKey(
  makerspaceId: number,
  label: string,
  reason: string,
  allowedOrigins: string[],
) {
  return staffRequest<ApiKeyRequest>("/admin/api-key-requests", {
    method: "POST",
    body: JSON.stringify({
      makerspace: makerspaceId,
      label,
      reason,
      allowed_origins: allowedOrigins,
    }),
  });
}

export function createApiClient(
  makerspaceId: number,
  label: string,
  allowedOrigins: string[],
  scopes: string[],
  clientType: ApiClientType = "server",
) {
  return staffRequest<ApiClientCreateResponse>(`/admin/makerspace/${makerspaceId}/api-clients`, {
    method: "POST",
    body: JSON.stringify({
      label,
      allowed_origins: allowedOrigins,
      scopes,
      client_type: clientType,
    }),
  });
}

/** Revoke (false) keeps the client and its history; reactivate (true) restores it. */
export function setApiClientActive(clientId: number, isActive: boolean) {
  return staffRequest<ApiClient>(`/admin/api-clients/${clientId}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export function updateApiClientScopes(clientId: number, scopes: string[]) {
  return staffRequest<ApiClient>(`/admin/api-clients/${clientId}`, {
    method: "PATCH",
    body: JSON.stringify({ scopes }),
  });
}

export function deleteApiClient(clientId: number) {
  return staffRequest<void>(`/admin/api-clients/${clientId}`, {
    method: "DELETE",
  });
}

export function rotateApiClient(clientId: number) {
  return staffRequest<ApiClientCreateResponse>(`/admin/api-clients/${clientId}/rotate-secret`, {
    method: "POST",
  });
}

export function splitOrigins(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((origin) => origin.trim())
    .filter(Boolean);
}
